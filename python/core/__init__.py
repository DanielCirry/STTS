"""STTS Core module."""

from core.engine import STTSEngine
from core.events import EventType, create_event
from core.audio_manager import AudioManager
from core.speaker_capture import SpeakerCapture, get_speaker_capture

__all__ = [
    'STTSEngine',
    'EventType',
    'create_event',
    'AudioManager',
    'SpeakerCapture',
    'get_speaker_capture',
]
