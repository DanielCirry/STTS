"""
Speech-to-Text module using faster-whisper
Provides real-time transcription with streaming support
"""

import asyncio
import logging
import threading
import time
from typing import Callable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger('stts.stt')

# Silence detection settings
SILENCE_THRESHOLD = 0.01
MIN_AUDIO_LENGTH = 0.5  # Minimum audio length in seconds
MAX_AUDIO_LENGTH = 30.0  # Maximum audio length before forced processing


class SpeechToText:
    """Speech-to-Text using faster-whisper."""

    def __init__(self):
        self.model = None
        self.model_name: Optional[str] = None
        self.device = 'cpu'
        self.compute_type = 'int8'
        self.language: Optional[str] = 'en'  # Default to English for speed + accuracy

        # Audio buffer for accumulating speech
        self.audio_buffer: List[np.ndarray] = []
        self.buffer_start_time: Optional[float] = None
        self.silence_start: Optional[float] = None
        self.silence_duration = 0.5  # Seconds of silence before processing

        # Callbacks
        # on_final_transcript(text, detected_language) where detected_language is a Whisper ISO 639-1 code or None
        self.on_partial_transcript: Optional[Callable[[str], None]] = None
        self.on_final_transcript: Optional[Callable[[str, Optional[str]], None]] = None

        # Processing
        self._processing = False
        self._lock = threading.Lock()

    def detect_device(self) -> Tuple[str, bool]:
        """Detect available compute device.

        Returns:
            Tuple of (device_name, cuda_available)
        """
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                logger.debug(f"CUDA available: {gpu_name}")
                return 'cuda', True
        except ImportError:
            pass

        logger.debug("Using CPU for inference")
        return 'cpu', False

    def load_model(self, model_name: str = 'tiny', device: Optional[str] = None) -> bool:
        """Load a Whisper model.

        Args:
            model_name: Model size (tiny, base, small, medium, large-v3-turbo)
                        Also accepts 'whisper-tiny', 'whisper-base', etc.
            device: Device to use (cpu, cuda, or auto)

        Returns:
            True if successful
        """
        try:
            from faster_whisper import WhisperModel

            # Strip common prefixes (frontend may send 'whisper-tiny' instead of 'tiny')
            if model_name.startswith('whisper-'):
                model_name = model_name[len('whisper-'):]
                logger.debug(f"Stripped 'whisper-' prefix, using model name: {model_name}")

            # Determine device
            if device is None or device == 'auto':
                device, _ = self.detect_device()

            self.device = device

            # Set compute type based on device
            if device == 'cuda':
                self.compute_type = 'float16'
            else:
                self.compute_type = 'int8'

            logger.info(f"Loading model: {model_name} on {device} ({self.compute_type})")

            # Load model
            self.model = WhisperModel(
                model_name,
                device=device,
                compute_type=self.compute_type,
                download_root=None,  # Use default cache
            )
            self.model_name = model_name

            logger.info(f"Model loaded successfully: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = None
            return False

    def unload_model(self):
        """Unload the current model."""
        self.model = None
        self.model_name = None
        logger.info("Model unloaded")

    def process_audio_chunk(self, audio_data: np.ndarray, sample_rate: int = 16000):
        """Process an incoming audio chunk.

        Accumulates audio in a buffer and processes when silence is detected.

        Args:
            audio_data: Audio samples as float32 numpy array
            sample_rate: Sample rate of the audio
        """
        if self.model is None:
            return

        current_time = time.time()

        # Calculate RMS to detect silence
        rms = np.sqrt(np.mean(audio_data ** 2))
        is_silence = rms < SILENCE_THRESHOLD

        # Periodic debug logging (every ~2 seconds based on 100ms chunks)
        if not hasattr(self, '_chunk_count'):
            self._chunk_count = 0
        self._chunk_count += 1
        if self._chunk_count % 20 == 0:
            buf_len = len(self.audio_buffer)
            buf_dur = (current_time - self.buffer_start_time) if self.buffer_start_time else 0
            logger.debug(f"[stt-debug] chunk#{self._chunk_count} rms={rms:.4f} silence={is_silence} buf_chunks={buf_len} buf_dur={buf_dur:.1f}s")

        with self._lock:
            if not is_silence:
                # We have speech
                if self.buffer_start_time is None:
                    self.buffer_start_time = current_time

                self.audio_buffer.append(audio_data)
                self.silence_start = None

                # Check if buffer is getting too long
                buffer_duration = current_time - self.buffer_start_time
                if buffer_duration >= MAX_AUDIO_LENGTH:
                    self._trigger_processing()

            else:
                # Silence detected
                if self.audio_buffer:
                    if self.silence_start is None:
                        self.silence_start = current_time
                    else:
                        silence_duration = current_time - self.silence_start
                        if silence_duration >= self.silence_duration:
                            # Process buffered audio
                            self._trigger_processing()

    def _trigger_processing(self):
        """Trigger transcription of buffered audio."""
        if not self.audio_buffer or self._processing:
            return

        buffer_duration = 0
        if self.buffer_start_time:
            buffer_duration = time.time() - self.buffer_start_time

        # Check minimum duration
        if buffer_duration < MIN_AUDIO_LENGTH:
            self._clear_buffer()
            return

        # Concatenate audio buffer
        audio = np.concatenate(self.audio_buffer)
        self._clear_buffer()

        # Process in background thread
        threading.Thread(
            target=self._transcribe_audio,
            args=(audio,),
            daemon=True
        ).start()

    def _clear_buffer(self):
        """Clear the audio buffer."""
        self.audio_buffer = []
        self.buffer_start_time = None
        self.silence_start = None

    def _transcribe_audio(self, audio: np.ndarray):
        """Transcribe audio data.

        Args:
            audio: Audio samples as float32 numpy array
        """
        if self.model is None:
            return

        self._processing = True

        try:
            # Transcribe
            # Note: vad_filter=False because we already do VAD in AudioManager
            # (Silero VAD onnx file is not bundled by PyInstaller)
            # Use language=None for auto-detect so we can route translation
            # based on detected language across multiple language pairs
            segments, info = self.model.transcribe(
                audio,
                beam_size=1,  # Greedy decoding for speed (beam_size=1 is fastest)
                language=None,  # Auto-detect language for multi-pair routing
                vad_filter=False,
            )

            # Capture detected language (ISO 639-1 code, e.g. 'en', 'ja')
            detected_language = getattr(info, 'language', None)

            # Collect transcription
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            full_text = ' '.join(text_parts).strip()

            if full_text:
                logger.debug(f"Transcription [{detected_language}]: {full_text[:100]}...")
                if self.on_final_transcript:
                    self.on_final_transcript(full_text, detected_language)

        except Exception as e:
            logger.error(f"Transcription error: {e}")

        finally:
            self._processing = False

    def transcribe_file(self, file_path: str) -> str:
        """Transcribe an audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Transcribed text
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        try:
            segments, info = self.model.transcribe(
                file_path,
                beam_size=5,
                vad_filter=True,
            )

            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            return ' '.join(text_parts).strip()

        except Exception as e:
            logger.error(f"Error transcribing file: {e}")
            raise

    def transcribe_array(self, audio: np.ndarray, language: Optional[str] = None) -> str:
        """Transcribe audio from numpy array.

        Args:
            audio: Audio samples as float32 numpy array (16kHz)
            language: Language code (e.g., 'en', 'ja') or None for auto-detect

        Returns:
            Transcribed text
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        try:
            segments, info = self.model.transcribe(
                audio,
                beam_size=5,
                language=language,
                vad_filter=True,
            )

            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            return ' '.join(text_parts).strip()

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise

    @property
    def is_loaded(self) -> bool:
        """Check if a model is loaded."""
        return self.model is not None

    @property
    def current_model(self) -> Optional[str]:
        """Get the name of the currently loaded model."""
        return self.model_name
