"""Event types and utilities for WebSocket communication."""

from enum import Enum
from typing import Any, Dict
import time


class EventType(str, Enum):
    """Event types for WebSocket communication."""

    # Connection
    PONG = 'pong'
    STATUS = 'status'
    ERROR = 'error'

    # Audio
    AUDIO_DEVICES = 'audio_devices'
    AUDIO_LEVEL = 'audio_level'

    # Listening
    LISTENING_STARTED = 'listening_started'
    LISTENING_STOPPED = 'listening_stopped'

    # Transcription
    TRANSCRIPT_PARTIAL = 'transcript_partial'
    TRANSCRIPT_FINAL = 'transcript_final'

    # Translation
    TRANSLATION_COMPLETE = 'translation_complete'
    TRANSLATION_FAILED = 'translation_failed'
    TRANSLATION_PROVIDER_SWITCHED = 'translation_provider_switched'

    # TTS
    TTS_STARTED = 'tts_started'
    TTS_FINISHED = 'tts_finished'

    # AI
    AI_RESPONSE = 'ai_response'
    AI_PROVIDER_SWITCHED = 'ai_provider_switched'
    AI_OFFLINE_MODE = 'ai_offline_mode'
    AI_ONLINE_RESTORED = 'ai_online_restored'

    # Models
    MODEL_LOADING = 'model_loading'
    MODEL_LOADED = 'model_loaded'
    MODEL_ERROR = 'model_error'
    MODEL_DOWNLOAD_PROGRESS = 'model_download_progress'

    # VRChat
    VRCHAT_SENT = 'vrchat_sent'
    VRCHAT_STATUS = 'vrchat_status'

    # VR Overlay
    OVERLAY_TEXT_SHOWN = 'overlay_text_shown'
    OVERLAY_CLEARED = 'overlay_cleared'
    OVERLAY_STATUS = 'overlay_status'

    # Settings
    SETTINGS_UPDATED = 'settings_updated'


def create_event(event_type: EventType, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create an event message."""
    return {
        'type': event_type.value,
        'payload': payload,
        'timestamp': time.time()
    }
