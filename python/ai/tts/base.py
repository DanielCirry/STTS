"""
Base TTS interface and common utilities
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger('stts.tts.base')


@dataclass
class Voice:
    """TTS voice information."""
    id: str
    name: str
    language: str
    gender: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TTSResult:
    """Result of TTS synthesis."""
    audio_data: bytes
    sample_rate: int
    channels: int = 1
    sample_width: int = 2  # 16-bit audio


class TTSEngine(ABC):
    """Base class for TTS engines."""

    def __init__(self):
        self.name: str = "base"
        self.is_online: bool = False
        self._voice: Optional[str] = None
        self._speed: float = 1.0
        self._pitch: float = 1.0
        self._volume: float = 1.0
        self._on_progress: Optional[Callable[[float], None]] = None

    @property
    def voice(self) -> Optional[str]:
        """Get current voice ID."""
        return self._voice

    @voice.setter
    def voice(self, voice_id: str):
        """Set current voice ID."""
        self._voice = voice_id

    @property
    def speed(self) -> float:
        """Get speech speed multiplier."""
        return self._speed

    @speed.setter
    def speed(self, value: float):
        """Set speech speed multiplier (0.5-2.0)."""
        self._speed = max(0.5, min(2.0, value))

    @property
    def pitch(self) -> float:
        """Get pitch multiplier."""
        return self._pitch

    @pitch.setter
    def pitch(self, value: float):
        """Set pitch multiplier (0.5-2.0)."""
        self._pitch = max(0.5, min(2.0, value))

    @property
    def volume(self) -> float:
        """Get volume level."""
        return self._volume

    @volume.setter
    def volume(self, value: float):
        """Set volume level (0.0-1.0)."""
        self._volume = max(0.0, min(1.0, value))

    def set_progress_callback(self, callback: Callable[[float], None]):
        """Set callback for synthesis progress updates."""
        self._on_progress = callback

    @abstractmethod
    def get_voices(self) -> List[Voice]:
        """Get list of available voices.

        Returns:
            List of Voice objects
        """
        pass

    @abstractmethod
    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize

        Returns:
            TTSResult with audio data
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the engine is available and ready to use.

        Returns:
            True if available
        """
        pass

    def cleanup(self):
        """Clean up engine resources."""
        pass
