"""STTS TTS module - Text-to-Speech engines."""

from ai.tts.base import TTSEngine, TTSResult, Voice
from ai.tts.manager import TTSManager
from ai.tts.edge_tts import EdgeTTSEngine
from ai.tts.piper_tts import PiperTTSEngine
from ai.tts.sapi_tts import SAPITTSEngine
from ai.tts.voicevox import VoicevoxEngine

__all__ = [
    'TTSEngine',
    'TTSResult',
    'Voice',
    'TTSManager',
    'EdgeTTSEngine',
    'PiperTTSEngine',
    'SAPITTSEngine',
    'VoicevoxEngine',
]
