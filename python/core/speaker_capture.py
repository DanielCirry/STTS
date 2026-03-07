"""
Speaker Capture - WASAPI Loopback for capturing system audio
Captures audio from speakers/headphones for transcription
"""

import asyncio
import logging
import threading
import queue
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger('stts.speaker_capture')

# Audio settings
SAMPLE_RATE = 16000  # Required by Whisper
CHANNELS = 1  # Mono for STT
CHUNK_DURATION = 0.1  # 100ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)


class SpeakerCapture:
    """Captures system audio using WASAPI loopback."""

    def __init__(self):
        self._is_capturing = False
        self._capture_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=100)

        # Device info
        self._loopback_device = None
        self._device_name: Optional[str] = None

        # Callbacks
        self.on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Audio level tracking
        self._current_level: float = 0.0
        self.on_audio_level: Optional[Callable[[float], None]] = None

    def get_loopback_devices(self) -> list:
        """Get available loopback devices.

        Returns:
            List of device info dicts
        """
        devices = []

        try:
            import soundcard as sc

            # Get all speakers (which can be used for loopback)
            speakers = sc.all_speakers()

            for i, speaker in enumerate(speakers):
                devices.append({
                    'id': i,
                    'name': speaker.name,
                    'is_default': speaker == sc.default_speaker()
                })

        except ImportError:
            logger.warning("soundcard not installed")
        except Exception as e:
            logger.error(f"Error getting loopback devices: {e}")

        return devices

    def set_device(self, device_id: Optional[int] = None) -> bool:
        """Set the loopback device to use.

        Args:
            device_id: Device index or None for default

        Returns:
            True if successful
        """
        try:
            import soundcard as sc

            if device_id is None:
                speaker = sc.default_speaker()
            else:
                speakers = sc.all_speakers()
                if 0 <= device_id < len(speakers):
                    speaker = speakers[device_id]
                else:
                    logger.error(f"Invalid device ID: {device_id}")
                    return False

            # Find the loopback microphone matching this speaker
            loopback_mics = sc.all_microphones(include_loopback=True)
            loopback = None
            for mic in loopback_mics:
                if mic.isloopback and mic.id == speaker.id:
                    loopback = mic
                    break

            if loopback is None:
                # Fallback: pick any loopback mic with matching name
                for mic in loopback_mics:
                    if mic.isloopback and speaker.name in mic.name:
                        loopback = mic
                        break

            if loopback is None:
                logger.error(f"No loopback microphone found for speaker: {speaker.name}")
                return False

            self._loopback_device = loopback
            self._device_name = speaker.name
            logger.debug(f"Loopback device set: {self._device_name}")
            return True

        except ImportError:
            logger.error("soundcard not installed")
            return False
        except Exception as e:
            logger.error(f"Error setting loopback device: {e}")
            return False

    def start_capture(self, device_id: Optional[int] = None) -> bool:
        """Start capturing audio from loopback.

        Args:
            device_id: Device to capture from (None for default)

        Returns:
            True if started successfully
        """
        if self._is_capturing:
            logger.warning("Already capturing")
            return True

        # Set device if not already set
        if self._loopback_device is None or device_id is not None:
            if not self.set_device(device_id):
                return False

        # Start capture thread
        self._is_capturing = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        logger.debug("Speaker capture started")
        return True

    def stop_capture(self):
        """Stop capturing audio."""
        if not self._is_capturing:
            return

        self._is_capturing = False

        if self._capture_thread:
            self._capture_thread.join(timeout=2)
            self._capture_thread = None

        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.debug("Speaker capture stopped")

    def _capture_loop(self):
        """Background thread for audio capture."""
        logger.debug("Capture loop started")

        try:
            import soundcard as sc

            # COM must be initialized on this thread (Windows WASAPI requirement)
            try:
                import comtypes
                comtypes.CoInitialize()
            except ImportError:
                import pythoncom
                pythoncom.CoInitialize()

            # _loopback_device is already a loopback microphone (set in set_device)
            with self._loopback_device.recorder(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=CHUNK_SIZE
            ) as recorder:
                while self._is_capturing:
                    try:
                        # Record a chunk
                        data = recorder.record(numframes=CHUNK_SIZE)

                        # Convert to mono float32 if needed
                        if len(data.shape) > 1:
                            data = data.mean(axis=1)
                        data = data.astype(np.float32)

                        # Calculate audio level (RMS)
                        rms = np.sqrt(np.mean(data ** 2))
                        self._current_level = min(1.0, rms * 10)  # Scale for visibility

                        if self.on_audio_level:
                            self.on_audio_level(self._current_level)

                        # Put in queue for processing
                        try:
                            self._audio_queue.put_nowait(data)
                        except queue.Full:
                            # Drop oldest if queue is full
                            try:
                                self._audio_queue.get_nowait()
                                self._audio_queue.put_nowait(data)
                            except queue.Empty:
                                pass

                        # Call callback if set
                        if self.on_audio_chunk:
                            self.on_audio_chunk(data)

                    except Exception as e:
                        logger.error(f"Error in capture loop: {e}")
                        if self.on_error:
                            self.on_error(str(e))
                        break

        except ImportError:
            error_msg = "soundcard library not installed. Install with: pip install soundcard"
            logger.error(error_msg)
            if self.on_error:
                self.on_error(error_msg)
        except Exception as e:
            error_msg = f"Error starting loopback capture: {e}"
            logger.error(error_msg)
            if self.on_error:
                self.on_error(error_msg)

        logger.debug("Capture loop stopped")

    def get_audio_chunk(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Get an audio chunk from the queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Audio data or None if timeout
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_capturing(self) -> bool:
        """Check if currently capturing."""
        return self._is_capturing

    @property
    def current_level(self) -> float:
        """Get current audio level (0-1)."""
        return self._current_level

    @property
    def device_name(self) -> Optional[str]:
        """Get current device name."""
        return self._device_name

    def is_available(self) -> bool:
        """Check if speaker capture is available."""
        try:
            import soundcard as sc
            # Check if we can get speakers
            speakers = sc.all_speakers()
            return len(speakers) > 0
        except ImportError:
            return False
        except Exception:
            return False

    def cleanup(self):
        """Clean up resources."""
        self.stop_capture()


# Singleton instance
_speaker_capture: Optional[SpeakerCapture] = None


def get_speaker_capture() -> SpeakerCapture:
    """Get the singleton speaker capture instance."""
    global _speaker_capture
    if _speaker_capture is None:
        _speaker_capture = SpeakerCapture()
    return _speaker_capture
