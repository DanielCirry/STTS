"""
OCR Engine - Screen capture, text recognition, and translation pipeline.

Uses EasyOCR for text detection and NLLB for translation.
Captures the screen via mss, crops to the user-defined region,
runs OCR, deduplicates results, translates, and renders overlays.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger('stts.ocr')

# Thread pool for blocking OCR calls
_ocr_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ocr')


class OCREngine:
    """Screen OCR capture + translate pipeline."""

    def __init__(self):
        self._reader = None           # EasyOCR Reader (lazy loaded)
        self._languages: List[str] = ['en']
        self._device: str = 'cpu'
        self._confidence: float = 0.3
        self._running: bool = False
        self._mode: str = 'manual'
        self._interval: float = 3.0
        self._last_results: List[Tuple] = []  # Last OCR results for dedup
        self._last_capture_time: float = 0
        self._loop_task: Optional[asyncio.Task] = None
        self._loaded: bool = False
        self._loading: bool = False
        self._sct = None              # mss screen capture instance (lazy)

        # Capture region as pixel percentages (0.0-1.0)
        self._crop_region: Optional[Dict[str, float]] = None  # {x, y, w, h} as fractions

        # Callbacks
        self.on_ocr_complete: Optional[Callable] = None  # (ocr_results, translations, region_size)
        self.on_status_change: Optional[Callable] = None  # (status_dict)

        # Translation function (set by engine)
        self._translate_fn: Optional[Callable] = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def is_loading(self) -> bool:
        return self._loading

    def _notify_status(self):
        """Broadcast current status."""
        if self.on_status_change:
            self.on_status_change({
                'loaded': self._loaded,
                'loading': self._loading,
                'running': self._running,
                'mode': self._mode,
                'languages': self._languages,
                'device': self._device,
            })

    async def initialize(self, languages: List[str], device: str = 'cpu'):
        """Load EasyOCR model (lazy, first call only).

        Args:
            languages: List of EasyOCR language codes (e.g. ['en', 'ja'])
            device: 'cpu' or 'gpu'
        """
        if self._loaded and self._languages == languages and self._device == device:
            logger.debug("[ocr] Already loaded with same config, skipping")
            return True

        self._loading = True
        self._notify_status()

        try:
            logger.info(f"[ocr] Loading EasyOCR reader: languages={languages}, device={device}")

            def _load():
                import easyocr
                gpu = device == 'gpu' or device == 'cuda'
                return easyocr.Reader(languages, gpu=gpu)

            loop = asyncio.get_event_loop()
            self._reader = await loop.run_in_executor(_ocr_executor, _load)
            self._languages = languages
            self._device = device
            self._loaded = True
            self._loading = False
            logger.info(f"[ocr] EasyOCR reader loaded successfully")
            self._notify_status()
            return True

        except Exception as e:
            logger.error(f"[ocr] Failed to load EasyOCR: {e}")
            self._loaded = False
            self._loading = False
            self._notify_status()
            return False

    def update_settings(self, settings: Dict[str, Any]):
        """Update OCR settings from frontend."""
        logger.debug(f"[ocr] update_settings: keys={list(settings.keys())}")

        if 'mode' in settings:
            self._mode = settings['mode']
        if 'interval' in settings:
            self._interval = float(settings['interval'])
        if 'confidence' in settings:
            self._confidence = float(settings['confidence'])
        if 'crop_region' in settings:
            self._crop_region = settings['crop_region']
            logger.debug(f"[ocr] Updated crop region: {self._crop_region}")

    def set_translate_fn(self, fn: Callable):
        """Set the translation function to use for translating OCR results."""
        self._translate_fn = fn

    def _get_screen_capture(self) -> Optional[np.ndarray]:
        """Capture the primary monitor screen using mss.

        Returns numpy array (H, W, 3) BGR or None on failure.
        """
        try:
            import mss
            if self._sct is None:
                self._sct = mss.mss()

            # Capture primary monitor
            monitor = self._sct.monitors[1]  # Primary monitor (0 = all monitors combined)
            screenshot = self._sct.grab(monitor)

            # Convert to numpy array (BGRA -> BGR)
            img = np.array(screenshot)
            img = img[:, :, :3]  # Drop alpha channel
            return img

        except Exception as e:
            logger.error(f"[ocr] Screen capture failed: {e}")
            return None

    def _crop_image(self, img: np.ndarray) -> np.ndarray:
        """Crop image to the configured capture region.

        crop_region is {x, y, w, h} as fractions (0.0-1.0) of the full image.
        """
        if not self._crop_region:
            return img

        h, w = img.shape[:2]
        x = int(self._crop_region.get('x', 0) * w)
        y = int(self._crop_region.get('y', 0) * h)
        cw = int(self._crop_region.get('w', 1.0) * w)
        ch = int(self._crop_region.get('h', 1.0) * h)

        # Clamp to image bounds
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        cw = max(1, min(cw, w - x))
        ch = max(1, min(ch, h - y))

        logger.debug(f"[ocr] Cropping: ({x},{y}) {cw}x{ch} from {w}x{h}")
        return img[y:y+ch, x:x+cw]

    async def capture_and_ocr(self) -> List[Tuple]:
        """Capture screen -> crop -> OCR -> return [(bbox, text, confidence), ...].

        Runs EasyOCR in a thread executor to avoid blocking the event loop.
        """
        if not self._reader:
            logger.warning("[ocr] Reader not loaded, cannot run OCR")
            return []

        loop = asyncio.get_event_loop()

        def _do_ocr():
            img = self._get_screen_capture()
            if img is None:
                return []

            cropped = self._crop_image(img)
            logger.debug(f"[ocr] Running OCR on image {cropped.shape}")

            # EasyOCR returns list of (bbox, text, confidence)
            # bbox = [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            results = self._reader.readtext(cropped)

            # Filter by confidence
            filtered = [(bbox, text, conf) for bbox, text, conf in results
                       if conf >= self._confidence]

            logger.info(f"[ocr] OCR found {len(results)} blocks, {len(filtered)} above confidence {self._confidence}")
            return filtered

        results = await loop.run_in_executor(_ocr_executor, _do_ocr)
        return results

    async def capture_translate_render(self) -> Optional[Dict]:
        """Full pipeline: capture -> OCR -> dedup -> translate -> callback.

        Returns dict with results or None if skipped.
        """
        self._last_capture_time = time.time()

        results = await self.capture_and_ocr()
        if not results:
            logger.debug("[ocr] No text detected")
            return None

        # Dedup: skip if text hasn't changed
        if not self._text_changed(results, self._last_results):
            logger.debug("[ocr] Text unchanged, skipping translation")
            return None

        self._last_results = results

        # Translate each text block
        translations = []
        for bbox, text, conf in results:
            if self._translate_fn:
                try:
                    translated = await self._translate_fn(text)
                    translations.append(translated)
                except Exception as e:
                    logger.warning(f"[ocr] Translation failed for '{text[:50]}': {e}")
                    translations.append(text)  # Fallback to original
            else:
                translations.append(text)  # No translation function set

        logger.info(f"[ocr] Translated {len(translations)} blocks")

        # Callback to engine with results + translations
        if self.on_ocr_complete:
            self.on_ocr_complete(results, translations)

        return {
            'blocks': [
                {'original': text, 'translated': trans, 'confidence': conf,
                 'bbox': [[int(p[0]), int(p[1])] for p in bbox]}
                for (bbox, text, conf), trans in zip(results, translations)
            ],
            'count': len(translations),
        }

    async def start_auto_loop(self):
        """Start automatic OCR capture loop."""
        if self._running:
            logger.debug("[ocr] Auto loop already running")
            return

        self._running = True
        self._notify_status()
        logger.info(f"[ocr] Starting auto capture loop, interval={self._interval}s")

        try:
            while self._running:
                try:
                    await self.capture_translate_render()
                except Exception as e:
                    logger.error(f"[ocr] Auto capture error: {e}")
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            self._notify_status()
            logger.info("[ocr] Auto capture loop stopped")

    def stop_auto_loop(self):
        """Stop the automatic capture loop."""
        logger.info("[ocr] Stopping auto capture loop")
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None
        self._notify_status()

    async def trigger_manual_capture(self) -> Optional[Dict]:
        """Trigger a single OCR capture (manual mode)."""
        logger.info("[ocr] Manual capture triggered")
        return await self.capture_translate_render()

    def _text_changed(self, new_results: List[Tuple], old_results: List[Tuple]) -> bool:
        """Compare OCR results to avoid re-translating identical text."""
        if len(new_results) != len(old_results):
            return True
        new_texts = sorted([r[1] for r in new_results])
        old_texts = sorted([r[1] for r in old_results])
        return new_texts != old_texts

    def shutdown(self):
        """Shut down the OCR engine."""
        logger.info("[ocr] Shutting down OCR engine")
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
        if self._sct:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
        self._reader = None
        self._loaded = False
        self._notify_status()
