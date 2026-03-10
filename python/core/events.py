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
    SPEAKER_TEST_DONE = 'speaker_test_done'

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

    # RVC Voice Conversion
    RVC_MODEL_LOADING = 'rvc_model_loading'
    RVC_MODEL_LOADED = 'rvc_model_loaded'
    RVC_MODEL_ERROR = 'rvc_model_error'
    RVC_UNLOADED = 'rvc_unloaded'
    RVC_STATUS = 'rvc_status'
    RVC_PARAMS_UPDATED = 'rvc_params_updated'
    RVC_DOWNLOAD_PROGRESS = 'rvc_download_progress'
    RVC_BASE_MODELS_NEEDED = 'rvc_base_models_needed'
    RVC_TEST_VOICE_READY = 'rvc_test_voice_ready'
    RVC_TEST_VOICE_ERROR = 'rvc_test_voice_error'
    RVC_CONVERSION_FAILED = 'rvc_conversion_failed'
    RVC_MIC_STARTED = 'rvc_mic_started'
    RVC_MIC_STOPPED = 'rvc_mic_stopped'
    RVC_MIC_ERROR = 'rvc_mic_error'

    # VOICEVOX Engine Setup
    VOICEVOX_SETUP_STATUS = 'voicevox_setup_status'
    VOICEVOX_SETUP_PROGRESS = 'voicevox_setup_progress'
    VOICEVOX_ENGINE_STATUS = 'voicevox_engine_status'

    # VRChat
    VRCHAT_SENT = 'vrchat_sent'
    VRCHAT_STATUS = 'vrchat_status'

    # VR Overlay
    OVERLAY_TEXT_SHOWN = 'overlay_text_shown'
    OVERLAY_CLEARED = 'overlay_cleared'
    OVERLAY_STATUS = 'overlay_status'

    # OCR
    OCR_RESULT = 'ocr_result'
    OCR_STATUS = 'ocr_status'
    OCR_ERROR = 'ocr_error'

    # Settings
    SETTINGS_UPDATED = 'settings_updated'
    SETTINGS_BACKUP_SAVED = 'settings_backup_saved'
    SETTINGS_BACKUP_LOADED = 'settings_backup_loaded'


def create_event(event_type: EventType, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create an event message."""
    return {
        'type': event_type.value,
        'payload': payload,
        'timestamp': time.time()
    }
