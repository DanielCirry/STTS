"""
RVC Post-Processor for TTS pipeline.

Wraps the RVC inference package with a clean async interface.
Sits between TTS synthesis and audio playback as an optional
voice conversion step.
"""

import asyncio
import gc
import io
import logging
import os
import threading
import wave
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from ai.tts.base import TTSResult

logger = logging.getLogger('stts.tts.rvc_postprocess')

# Default directories under %LOCALAPPDATA%\STTS\models\rvc
_APPDATA = Path(os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', Path.home() / '.stts')))
DEFAULT_MODELS_DIR = str(_APPDATA / 'STTS' / 'models' / 'rvc' / 'voices')
DEFAULT_PRETRAINED_DIR = str(_APPDATA / 'STTS' / 'models' / 'rvc' / 'pretrained')

# HuBERT and RMVPE download URLs
HUBERT_URL = 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt'
RMVPE_URL = 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.pt'


class RVCPostProcessor:
    """Async wrapper for RVC voice conversion.

    Provides model loading, inference, and lifecycle management
    with thread-safe operation for use in the async TTS pipeline.
    """

    def __init__(self):
        self._enabled: bool = False
        self._model_path: Optional[str] = None
        self._index_path: Optional[str] = None

        # Loaded model state (lazy - only populated when a model is loaded)
        self._hubert = None
        self._rmvpe = None
        self._pipeline = None
        self._net_g = None
        self._tgt_sr: int = 40000
        self._version: str = 'v1'
        self._index = None
        self._loaded_model_name: Optional[str] = None
        self._device = None

        # Conversion parameters with sensible defaults
        self.f0_up_key: int = 0            # Semitone shift (-12 to +12)
        self.index_rate: float = 0.75      # FAISS influence (0.0-1.0)
        self.filter_radius: int = 3        # Pitch smoothing (1-7)
        self.rms_mix_rate: float = 0.25    # Loudness matching (0.0-1.0)
        self.protect: float = 0.33         # Consonant protection (0.0-0.5)
        self.resample_sr: int = 0          # 0 = no resample
        self.volume_envelope: float = 0.0  # Volume envelope mix

        # Callbacks
        self.on_progress: Optional[Callable[[str, float], None]] = None
        self.on_status: Optional[Callable[[str, dict], None]] = None

        # Thread safety for model load/unload
        self._lock = threading.Lock()

    def _report_progress(self, stage: str, progress: float):
        """Report loading progress via callback."""
        if self.on_progress:
            try:
                self.on_progress(stage, progress)
            except Exception:
                pass

    def _report_status(self, event: str, data: dict):
        """Report status change via callback."""
        if self.on_status:
            try:
                self.on_status(event, data)
            except Exception:
                pass

    def _ensure_device(self):
        """Lazily initialize the torch device."""
        if self._device is None:
            from ai.rvc.config import safe_import_torch
            torch = safe_import_torch()
            if torch is None:
                raise RuntimeError("PyTorch is not available. Install it from the Features page.")
            from ai.rvc.config import get_device
            self._device = get_device()

    def _check_base_models(self) -> dict:
        """Check if HuBERT and RMVPE base models exist.

        Returns:
            Dict with 'hubert_path', 'rmvpe_path', and 'needs_download' flag.
        """
        pretrained_dir = Path(DEFAULT_PRETRAINED_DIR)
        # HuBERT is stored as a transformers model directory
        hubert_dir = pretrained_dir / 'hubert'
        hubert_exists = (hubert_dir / 'config.json').exists()
        rmvpe_path = pretrained_dir / 'rmvpe.pt'

        return {
            'hubert_path': str(hubert_dir),
            'rmvpe_path': str(rmvpe_path),
            'hubert_exists': hubert_exists,
            'rmvpe_exists': rmvpe_path.exists(),
            'needs_download': not hubert_exists or not rmvpe_path.exists(),
        }

    async def download_base_models(self) -> bool:
        """Download HuBERT and RMVPE base models.

        Downloads should only be called after user confirmation.

        Returns:
            True if both models downloaded successfully.
        """
        pretrained_dir = Path(DEFAULT_PRETRAINED_DIR)
        pretrained_dir.mkdir(parents=True, exist_ok=True)

        check = self._check_base_models()

        # Download ContentVec (HuBERT fine-tuned for voice conversion) via HTTP
        # IMPORTANT: RVC models were trained with ContentVec features, NOT vanilla HuBERT.
        # Using vanilla facebook/hubert-base-ls960 produces completely wrong features
        # and results in gibberish output. We download the files directly to avoid
        # needing torch at download time (torch may not be importable yet in frozen exe).
        if not check['hubert_exists']:
            try:
                import aiohttp
                hubert_dir = Path(check['hubert_path'])
                hubert_dir.mkdir(parents=True, exist_ok=True)
                # ContentVec model files from HuggingFace
                CONTENTVEC_REPO = 'https://huggingface.co/lengyue233/content-vec-best/resolve/main'
                hubert_files = ['config.json', 'pytorch_model.bin']
                self._report_progress('downloading_hubert_base', 0.0)
                logger.debug("Downloading ContentVec model files from HuggingFace")

                async with aiohttp.ClientSession() as session:
                    for i, fname in enumerate(hubert_files):
                        url = f'{CONTENTVEC_REPO}/{fname}'
                        dest = hubert_dir / fname
                        logger.debug(f"Downloading {fname} from {url}")
                        async with session.get(url) as resp:
                            if resp.status != 200:
                                logger.error(f"Download failed for {fname}: HTTP {resp.status}")
                                return False
                            total = int(resp.headers.get('content-length', 0))
                            downloaded = 0
                            with open(dest, 'wb') as f:
                                async for chunk in resp.content.iter_chunked(1024 * 1024):
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if total > 0:
                                        file_pct = downloaded / total
                                        # Scale progress: file 0 = 0-0.4, file 1 = 0.4-0.9
                                        base = i * 0.45
                                        self._report_progress('downloading_hubert_base', base + file_pct * 0.45)
                self._report_progress('downloading_hubert_base', 1.0)
                logger.debug(f"ContentVec model saved to {hubert_dir}")
            except Exception as e:
                logger.error(f"Failed to download HuBERT: {e}")
                return False

        # Download RMVPE via HTTP
        if not check['rmvpe_exists']:
            try:
                import aiohttp
                self._report_progress('downloading_rmvpe.pt', 0.0)
                logger.debug(f"Downloading rmvpe.pt from {RMVPE_URL}")

                async with aiohttp.ClientSession() as session:
                    async with session.get(RMVPE_URL) as resp:
                        if resp.status != 200:
                            logger.error(f"Download failed for rmvpe.pt: HTTP {resp.status}")
                            return False

                        total = int(resp.headers.get('content-length', 0))
                        downloaded = 0

                        with open(check['rmvpe_path'], 'wb') as f:
                            async for chunk in resp.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    pct = downloaded / total
                                    self._report_progress(
                                        'downloading_rmvpe.pt',
                                        pct
                                    )

                logger.debug(f"Downloaded rmvpe.pt ({downloaded} bytes)")

            except Exception as e:
                logger.error(f"Failed to download rmvpe.pt: {e}")
                if os.path.exists(check['rmvpe_path']):
                    os.remove(check['rmvpe_path'])
                return False

        return True

    async def load_model(self, model_path: str, index_path: Optional[str] = None) -> bool:
        """Load an RVC voice model.

        Args:
            model_path: Path to the .pth voice model file.
            index_path: Optional path to .index file. Auto-detected if None.

        Returns:
            True on success, False on failure.
        """
        if not os.path.isfile(model_path):
            logger.error(f"Model file not found: {model_path}")
            return False

        # Auto-detect .index file if not provided
        if index_path is None:
            model_dir = os.path.dirname(model_path)
            model_stem = os.path.splitext(os.path.basename(model_path))[0]
            candidate_index = os.path.join(model_dir, model_stem + '.index')
            if os.path.isfile(candidate_index):
                index_path = candidate_index
                logger.debug(f"Auto-detected index file: {index_path}")

        # Check base models
        check = self._check_base_models()
        if check['needs_download']:
            logger.warning("Base models (HuBERT/RMVPE) not found")
            self._report_status('base_models_needed', {
                'size_mb': 400,
                'hubert_exists': check['hubert_exists'],
                'rmvpe_exists': check['rmvpe_exists'],
            })
            return False

        loop = asyncio.get_event_loop()

        def _load_sync():
            with self._lock:
                self._ensure_device()
                device = self._device

                # Step 1: Load HuBERT
                self._report_progress('loading_hubert', 0.1)
                from ai.rvc.pipeline import load_hubert
                self._hubert = load_hubert(check['hubert_path'], device)
                self._report_progress('loading_hubert', 0.3)

                # Step 2: Load RMVPE
                self._report_progress('loading_rmvpe', 0.35)
                from ai.rvc.rmvpe import RMVPE
                self._rmvpe = RMVPE(check['rmvpe_path'], device)
                self._report_progress('loading_rmvpe', 0.5)

                # Step 3: Load voice model
                self._report_progress('loading_voice', 0.55)
                from ai.rvc.pipeline import load_synthesizer
                self._net_g, self._tgt_sr, self._version = load_synthesizer(
                    model_path, device
                )
                self._report_progress('loading_voice', 0.75)

                # Step 4: Create pipeline
                from ai.rvc.pipeline import Pipeline
                self._pipeline = Pipeline(self._tgt_sr, device)

                # Step 5: Load FAISS index (optional)
                self._index = None
                if index_path and os.path.isfile(index_path):
                    self._report_progress('loading_index', 0.8)
                    try:
                        import faiss
                        self._index = faiss.read_index(index_path)
                        logger.debug(f"Loaded FAISS index: {index_path}")
                    except ImportError:
                        logger.warning("faiss-cpu not installed, skipping index")
                    except Exception as e:
                        logger.warning(f"Failed to load index: {e}")

                self._model_path = model_path
                self._index_path = index_path
                self._loaded_model_name = os.path.splitext(
                    os.path.basename(model_path)
                )[0]

                self._report_progress('ready', 1.0)

        try:
            await loop.run_in_executor(None, _load_sync)

            self._report_status('model_loaded', {
                'model_name': self._loaded_model_name,
                'has_index': self._index is not None,
                'memory_mb': self._estimate_memory_mb(),
                'version': self._version,
                'target_sr': self._tgt_sr,
            })

            logger.info(
                f"RVC model loaded: {self._loaded_model_name} "
                f"({self._version}, {self._tgt_sr}Hz)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load RVC model: {e}")
            self._cleanup_model_state()
            return False

    async def process(self, result: TTSResult) -> TTSResult:
        """Process TTS output through RVC voice conversion.

        Args:
            result: TTSResult from TTS engine.

        Returns:
            New TTSResult with converted audio, or original on failure.
        """
        if not self.is_enabled():
            return result

        loop = asyncio.get_event_loop()

        def _process_sync():
            import time
            import torch

            audio_data = result.audio_data
            logger.debug(
                f"TTS→RVC: input {len(audio_data)} bytes, "
                f"declared sr={result.sample_rate}"
            )

            # Decode audio bytes to float32 numpy array
            audio_array, input_sr = self._decode_audio(audio_data, result.sample_rate)

            if audio_array is None:
                logger.warning("Could not decode TTS audio for RVC processing")
                return None

            logger.debug(
                f"TTS→RVC: decoded {len(audio_array)} samples at {input_sr}Hz "
                f"({len(audio_array)/input_sr:.2f}s)"
            )

            # Speaker ID tensor (always 0 for RVC single-speaker models)
            sid = torch.LongTensor([0]).to(self._device)

            # Run voice conversion
            t0 = time.monotonic()
            converted = self._pipeline.vc_single(
                hubert_model=self._hubert,
                net_g=self._net_g,
                sid=sid,
                audio=audio_array,
                input_sr=input_sr,
                f0_up_key=self.f0_up_key,
                rmvpe_model=self._rmvpe,
                index=self._index,
                index_rate=self.index_rate,
                filter_radius=self.filter_radius,
                rms_mix_rate=self.rms_mix_rate,
                protect=self.protect,
                resample_sr=self.resample_sr,
            )
            elapsed = time.monotonic() - t0

            # Determine output sample rate
            output_sr = self.resample_sr if self.resample_sr > 0 else self._tgt_sr

            logger.debug(
                f"TTS→RVC: converted {len(converted)} samples at {output_sr}Hz "
                f"({len(converted)/output_sr:.2f}s) in {elapsed:.2f}s"
            )

            # Encode back to WAV bytes
            wav_bytes = self._encode_wav(converted, output_sr)

            return TTSResult(
                audio_data=wav_bytes,
                sample_rate=output_sr,
                channels=1,
                sample_width=2,
            )

        try:
            new_result = await loop.run_in_executor(None, _process_sync)
            if new_result is None:
                return result
            return new_result

        except Exception as e:
            logger.error(f"RVC processing failed: {e}")
            # Fail-safe: return original audio
            return result

    def convert_raw(self, audio: np.ndarray, input_sr: int):
        """Convert raw float32 audio through RVC without TTSResult overhead.

        Args:
            audio: Float32 numpy array (mono).
            input_sr: Sample rate of the input audio.

        Returns:
            Tuple of (converted float32 numpy array, output sample rate),
            or (None, 0) on failure.
        """
        if self._pipeline is None:
            logger.warning("convert_raw: pipeline is None, cannot convert")
            return None, 0

        try:
            import torch

            logger.debug(f"convert_raw: starting conversion, audio shape={audio.shape}, sr={input_sr}")
            sid = torch.LongTensor([0]).to(self._device)

            converted = self._pipeline.vc_single(
                hubert_model=self._hubert,
                net_g=self._net_g,
                sid=sid,
                audio=audio,
                input_sr=input_sr,
                f0_up_key=self.f0_up_key,
                rmvpe_model=self._rmvpe,
                index=self._index,
                index_rate=self.index_rate,
                filter_radius=self.filter_radius,
                rms_mix_rate=self.rms_mix_rate,
                protect=self.protect,
                resample_sr=self.resample_sr,
            )

            output_sr = self.resample_sr if self.resample_sr > 0 else self._tgt_sr
            logger.debug(f"convert_raw: success, output shape={converted.shape}, sr={output_sr}")
            return converted, output_sr

        except Exception as e:
            import traceback
            logger.error(f"RVC convert_raw failed: {e}\n{traceback.format_exc()}")
            return None, 0

    def convert_streaming(
        self,
        audio_16k,
        block_samples: int,
        pitch_cache=None,
        pitchf_cache=None,
        sola_extra_frames: int = 4,
    ):
        """Streaming voice conversion for real-time mic processing.

        Uses rolling buffer + skip_head/return_length for efficient conversion.
        Much faster than convert_raw for real-time use because:
        - RMVPE only processes the new block (not full context)
        - Synthesizer decoder only generates the block portion
        - Pitch is cached across calls

        Args:
            audio_16k: Full rolling buffer at 16kHz (context + new block).
            block_samples: Number of new samples at the end.
            pitch_cache: Previous pitch values (or None for first call).
            pitchf_cache: Previous F0 values (or None for first call).
            sola_extra_frames: Extra feature frames for SOLA crossfading.

        Returns:
            Tuple of (converted_audio, pitch_cache, pitchf_cache, output_sr)
            or (None, pitch_cache, pitchf_cache, 0) on failure.
        """
        if self._pipeline is None:
            return None, pitch_cache, pitchf_cache, 0

        try:
            import torch

            sid = torch.LongTensor([0]).to(self._device)

            converted, pitch_cache, pitchf_cache, output_sr = self._pipeline.vc_streaming(
                hubert_model=self._hubert,
                net_g=self._net_g,
                sid=sid,
                audio_16k=audio_16k,
                block_samples=block_samples,
                f0_up_key=self.f0_up_key,
                rmvpe_model=self._rmvpe,
                pitch_cache=pitch_cache,
                pitchf_cache=pitchf_cache,
                sola_extra_frames=sola_extra_frames,
                index=self._index,
                index_rate=self.index_rate,
                filter_radius=self.filter_radius,
                protect=self.protect,
            )

            return converted, pitch_cache, pitchf_cache, output_sr

        except Exception as e:
            import traceback
            logger.error(f"RVC convert_streaming failed: {e}\n{traceback.format_exc()}")
            return None, pitch_cache, pitchf_cache, 0

    def move_to_device(self, device_str: str) -> bool:
        """Move loaded models to a different torch device.

        For DirectML: HuBERT and synthesizer go on GPU, RMVPE stays on CPU
        (RMVPE uses ComplexFloat/FFT which DirectML doesn't support).

        Args:
            device_str: Target device ('cpu', 'cuda', 'directml').

        Returns:
            True if device was changed, False if it failed (stays on current device).
        """
        import torch

        if device_str == 'cuda' and not torch.cuda.is_available():
            # Log diagnostic info to help debug CUDA availability issues
            logger.warning(f"CUDA not available — torch.version.cuda={getattr(torch.version, 'cuda', 'None')}, "
                           f"torch.backends.cudnn.enabled={getattr(torch.backends.cudnn, 'enabled', 'N/A')}, "
                           f"torch.__version__={torch.__version__}")
            try:
                import subprocess
                result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                                        capture_output=True, text=True, timeout=5)
                logger.warning(f"nvidia-smi GPU: {result.stdout.strip() if result.returncode == 0 else 'FAILED'}")
            except Exception:
                logger.warning("nvidia-smi not found or failed")
            logger.warning("CUDA not available — staying on current device")
            return False

        if device_str == 'directml':
            try:
                import torch_directml
                new_device = torch_directml.device()
            except ImportError:
                logger.error("torch-directml not available")
                return False
        else:
            new_device = torch.device(device_str)

        # RMVPE always stays on CPU (uses ComplexFloat/FFT, unsupported on DirectML)
        rmvpe_device = torch.device('cpu') if device_str == 'directml' else new_device

        with self._lock:
            try:
                if self._hubert:
                    self._hubert = self._hubert.to(new_device)
                if self._rmvpe:
                    self._rmvpe.model = self._rmvpe.model.to(rmvpe_device)
                    self._rmvpe.device = rmvpe_device
                if self._net_g:
                    self._net_g = self._net_g.to(new_device)
                    # Re-strip weight_norm after device move (critical for DirectML)
                    if device_str == 'directml':
                        from ai.rvc.pipeline import _safe_remove_weight_norm
                        _safe_remove_weight_norm(self._net_g)
                        logger.debug("Stripped weight_norm from synthesizer after DirectML move")
                if self._pipeline:
                    self._pipeline.device = new_device
                self._device = new_device
            except Exception as e:
                logger.error(f"Failed to move models to {new_device}: {e}")
                # Try to recover back to CPU
                try:
                    cpu = torch.device('cpu')
                    if self._hubert:
                        self._hubert = self._hubert.to(cpu)
                    if self._rmvpe:
                        self._rmvpe.model = self._rmvpe.model.to(cpu)
                        self._rmvpe.device = cpu
                    if self._net_g:
                        self._net_g = self._net_g.to(cpu)
                    if self._pipeline:
                        self._pipeline.device = cpu
                    self._device = cpu
                    logger.debug("Recovered back to CPU after failed device move")
                except Exception:
                    pass
                return False

        if device_str == 'directml':
            logger.debug(f"RVC: HuBERT+synth on {new_device}, RMVPE on CPU (FFT not supported on DirectML)")
        else:
            logger.debug(f"RVC models moved to {new_device}")
        return True

    @staticmethod
    def _is_mp3(data: bytes) -> bool:
        """Check if data looks like MP3 audio.

        Detects ID3 tags and all MPEG frame sync patterns (0xFF followed by
        any byte with the top 3 bits set: 0xE0-0xFF). This covers MPEG1/2,
        Layer I/II/III, with and without CRC.
        """
        if len(data) < 3:
            return False
        if data[:3] == b'ID3':
            return True
        if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            return True
        return False

    def _decode_audio(self, audio_data: bytes, sample_rate: int):
        """Decode audio bytes to float32 numpy array.

        Handles WAV, MP3, and raw PCM formats.

        Returns:
            Tuple of (float32 numpy array, sample rate) or (None, 0) on failure.
        """
        try:
            header_hex = audio_data[:4].hex() if len(audio_data) >= 4 else 'short'
            logger.debug(f"_decode_audio: {len(audio_data)} bytes, header={header_hex}")

            # Check format by header
            if audio_data[:4] == b'RIFF':
                # WAV format
                with wave.open(io.BytesIO(audio_data), 'rb') as wf:
                    sr = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                    sw = wf.getsampwidth()

                if sw == 2:
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                elif sw == 4:
                    audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

                logger.debug(f"_decode_audio: WAV {sr}Hz, {len(audio)} samples, {sw*8}-bit")
                return audio, sr

            elif self._is_mp3(audio_data):
                # MP3 format (Edge TTS and others)
                return self._decode_mp3(audio_data)

            else:
                # Assume raw PCM int16
                audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                logger.debug(f"_decode_audio: raw PCM {sample_rate}Hz, {len(audio)} samples")
                return audio, sample_rate

        except Exception as e:
            logger.error(f"Audio decode error: {e}")
            return None, 0

    @staticmethod
    def _decode_mp3(audio_data: bytes):
        """Decode MP3 audio bytes to float32 numpy array.

        Tries pydub (with static_ffmpeg for ffmpeg binary) first,
        falls back to miniaudio if pydub/ffmpeg is unavailable.

        Returns:
            Tuple of (float32 numpy array, sample rate) or (None, 0) on failure.
        """
        # Strategy 1: miniaudio (pure built-in MP3 decoder, no ffmpeg needed)
        try:
            import miniaudio
            decoded = miniaudio.decode(audio_data, nchannels=1, output_format=miniaudio.SampleFormat.FLOAT32)
            audio = np.frombuffer(decoded.samples, dtype=np.float32)
            logger.debug(
                f"_decode_mp3 (miniaudio): {decoded.sample_rate}Hz, "
                f"{len(audio)} samples"
            )
            return audio, decoded.sample_rate
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"miniaudio MP3 decode failed: {e}, trying pydub fallback")

        # Strategy 2: pydub + ffmpeg (needs ffmpeg on PATH)
        try:
            # Ensure ffmpeg is on PATH for pydub
            try:
                import static_ffmpeg
                static_ffmpeg.add_paths()
            except ImportError:
                pass

            from pydub import AudioSegment
            seg = AudioSegment.from_mp3(io.BytesIO(audio_data))
            if seg.channels > 1:
                seg = seg.set_channels(1)
            audio = np.array(seg.get_array_of_samples()).astype(np.float32) / 32768.0
            logger.debug(
                f"_decode_mp3 (pydub): {seg.frame_rate}Hz, "
                f"{len(audio)} samples, {seg.duration_seconds:.2f}s"
            )
            return audio, seg.frame_rate
        except Exception as e:
            logger.error(f"MP3 decoding failed (no miniaudio or ffmpeg): {e}")
            return None, 0

    @staticmethod
    def _encode_wav(audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode float32 numpy audio to WAV bytes.

        Args:
            audio: Float32 audio array.
            sample_rate: Output sample rate.

        Returns:
            WAV file bytes.
        """
        # Clip and convert to int16
        audio = np.clip(audio, -1.0, 1.0)
        int_data = (audio * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int_data.tobytes())

        return buf.getvalue()

    def unload(self):
        """Unload the current model and free memory."""
        with self._lock:
            self._cleanup_model_state()

        gc.collect()

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        self._enabled = False
        self._report_status('unloaded', {})
        logger.info("RVC model unloaded")

    def _cleanup_model_state(self):
        """Reset model state to unloaded."""
        self._hubert = None
        self._rmvpe = None
        self._pipeline = None
        self._net_g = None
        self._index = None
        self._loaded_model_name = None
        self._model_path = None
        self._index_path = None

    def is_enabled(self) -> bool:
        """Check if RVC is enabled and a model is loaded."""
        return self._enabled and self._pipeline is not None

    def enable(self, enabled: bool):
        """Enable or disable RVC for TTS post-processing.

        Does NOT unload the model — just toggles whether TTS output
        gets converted. Use unload() to free the model.
        """
        self._enabled = enabled

    def get_status(self) -> dict:
        """Get current RVC state."""
        return {
            'enabled': self._enabled,
            'loaded': self._pipeline is not None,
            'model_name': self._loaded_model_name,
            'model_path': self._model_path,
            'has_index': self._index is not None,
            'memory_mb': self._estimate_memory_mb() if self._pipeline else 0,
            'device': str(self._device) if self._device else 'cpu',
            'version': self._version if self._pipeline else None,
            'target_sr': self._tgt_sr if self._pipeline else None,
            'params': {
                'f0_up_key': self.f0_up_key,
                'index_rate': self.index_rate,
                'filter_radius': self.filter_radius,
                'rms_mix_rate': self.rms_mix_rate,
                'protect': self.protect,
                'resample_sr': self.resample_sr,
                'volume_envelope': self.volume_envelope,
            },
        }

    def set_params(self, **kwargs):
        """Update conversion parameters.

        Accepts any combination of:
            f0_up_key, index_rate, filter_radius, rms_mix_rate,
            protect, resample_sr, volume_envelope
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.debug(f"RVC param {key} = {value}")
            else:
                logger.warning(f"Unknown RVC parameter: {key}")

    def scan_models(self, directory: Optional[str] = None) -> List[Dict]:
        """Scan a directory for .pth voice model files.

        Args:
            directory: Directory to scan. Defaults to the standard models dir.

        Returns:
            List of model info dicts sorted by modified date (newest first).
        """
        if directory is None:
            directory = DEFAULT_MODELS_DIR

        models = []
        scan_dir = Path(directory)

        if not scan_dir.exists():
            scan_dir.mkdir(parents=True, exist_ok=True)
            return models

        for pth_file in scan_dir.glob('*.pth'):
            try:
                stat = pth_file.stat()
                models.append({
                    'name': pth_file.stem,
                    'path': str(pth_file),
                    'size_mb': round(stat.st_size / (1024 * 1024), 1),
                    'modified': stat.st_mtime,
                })
            except Exception as e:
                logger.warning(f"Error scanning {pth_file}: {e}")

        # Sort by modified date (newest first)
        models.sort(key=lambda m: m['modified'], reverse=True)

        return models

    def _estimate_memory_mb(self) -> float:
        """Estimate current memory usage of loaded models."""
        total = 0.0

        try:
            import torch

            for obj in [self._hubert, self._net_g, self._rmvpe]:
                if obj is None:
                    continue
                if hasattr(obj, 'parameters'):
                    for p in obj.parameters():
                        total += p.nelement() * p.element_size()
                elif hasattr(obj, 'model') and hasattr(obj.model, 'parameters'):
                    for p in obj.model.parameters():
                        total += p.nelement() * p.element_size()

        except Exception:
            # Rough estimate if we can't introspect
            total = 1.5 * 1024 * 1024 * 1024  # ~1.5 GB estimate

        return round(total / (1024 * 1024), 1)
