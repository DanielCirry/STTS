"""
STTS Engine - Main processing engine
Coordinates STT, translation, TTS, and AI assistant functionality
"""

import asyncio
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from core.events import EventType, create_event
from core.audio_manager import AudioManager
from core.speaker_capture import SpeakerCapture
from ai.stt import SpeechToText
from ai.translator import Translator
from ai.tts import TTSManager
from ai.assistant import AIAssistantManager, AssistantConfig
from ai.assistant.fallback import FallbackAIManager
from ai.translator_cloud import CloudTranslationManager
from ai.translator_free import FreeTranslationManager
from integrations.vrchat_osc import VRChatOSC
from integrations.vr_overlay import VROverlay

logger = logging.getLogger('stts.engine')


class STTSEngine:
    """Main STTS processing engine."""

    def __init__(self, broadcast_callback: Callable):
        """Initialize the engine.

        Args:
            broadcast_callback: Async function to broadcast events to all clients
        """
        self.broadcast = broadcast_callback
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.initialized = False
        self.listening = False
        self._mic_testing = False

        # Settings
        self.settings: Dict[str, Any] = {
            'stt': {
                'model': 'tiny',
                'language': None,  # Auto-detect
                'device': 'auto',
            },
            'translation': {
                'enabled': False,
                'source': 'auto',
                'target': 'ja',
            },
            'tts': {
                'enabled': False,
                'engine': 'edge',  # Default to Edge TTS (no setup needed)
                'voice': 'en-US-AriaNeural',
                'speed': 1.0,
                'pitch': 1.0,
                'volume': 0.8,
                'output_device': None,
            },
            'ai': {
                'enabled': False,
                'keyword': 'jarvis',
                'provider': 'local',  # Default to local LLM (no API key needed)
                'max_response_length': 140,
                'speak_responses': True,
                'send_to_vrchat': True,
            },
            'audio': {
                'input_device': None,
                'output_device': None,
                'vad_enabled': True,
                'vad_sensitivity': 0.5,
            },
            'vrchat': {
                'osc_enabled': True,
                'osc_ip': '127.0.0.1',
                'osc_port': 9000,
                'typing_indicator': True,
                'send_translations': True,  # Send translated text instead of original
            },
            'vrOverlay': {
                'enabled': False,
                'show_incoming_text': True,
                'show_own_text': True,
                'show_ai_responses': True,
                'show_translations': True,
                'distance': 1.5,
                'vertical_offset': 0.2,
                'horizontal_offset': 0.0,
                'width': 0.4,
                'opacity': 0.9,
                'font_size': 24,
                'display_duration': 5.0,
                'background_color': [0, 0, 0, 180],
                'text_color': [255, 255, 255],
            },
            'speakerCapture': {
                'enabled': False,
                'device': None,  # None = default speaker
                'translate': True,
                'show_in_overlay': True,
                'show_in_chat': True,
            }
        }

        # Module instances
        self._audio_manager: Optional[AudioManager] = None
        self._stt: Optional[SpeechToText] = None
        self._translator: Optional[Translator] = None
        self._cloud_translator: Optional[CloudTranslationManager] = None
        self._free_translator: Optional[FreeTranslationManager] = None
        self._active_translation_provider: Optional[str] = None
        self._tts: Optional[TTSManager] = None
        self._ai_assistant: Optional[AIAssistantManager] = None
        self._fallback_manager: Optional[FallbackAIManager] = None
        self._vrchat: Optional[VRChatOSC] = None
        self._vr_overlay: Optional[VROverlay] = None
        self._speaker_capture: Optional[SpeakerCapture] = None
        self._speaker_stt: Optional[SpeechToText] = None  # Separate STT for speaker

        # Speaker capture processing
        self._speaker_process_thread: Optional[threading.Thread] = None
        self._should_process_speaker = False
        self._speaker_listening = False

        # Processing thread
        self._process_thread: Optional[threading.Thread] = None
        self._should_process = False

        # Translation failure tracking
        self._translation_failure_count = 0
        self._TRANSLATION_FAILURE_THRESHOLD = 3

    # Mapping from NLLB language codes to Whisper language codes
    NLLB_TO_WHISPER = {
        'eng_Latn': 'en',
        'jpn_Jpan': 'ja',
        'zho_Hans': 'zh',
        'zho_Hant': 'zh',
        'kor_Hang': 'ko',
        'spa_Latn': 'es',
        'fra_Latn': 'fr',
        'deu_Latn': 'de',
        'ita_Latn': 'it',
        'por_Latn': 'pt',
        'rus_Cyrl': 'ru',
        'arb_Arab': 'ar',
        'hin_Deva': 'hi',
        'tha_Thai': 'th',
        'vie_Latn': 'vi',
        'ind_Latn': 'id',
        'nld_Latn': 'nl',
        'pol_Latn': 'pl',
        'tur_Latn': 'tr',
        'ukr_Cyrl': 'uk',
    }

    # Reverse mapping: Whisper ISO 639-1 codes to NLLB codes
    WHISPER_TO_NLLB = {v: k for k, v in NLLB_TO_WHISPER.items()}

    def _nllb_to_whisper(self, nllb_code: str) -> str:
        """Convert NLLB language code to Whisper language code."""
        whisper_code = self.NLLB_TO_WHISPER.get(nllb_code)
        if whisper_code:
            return whisper_code
        # Fallback: try extracting the 3-letter ISO 639-3 prefix
        # e.g. 'eng_Latn' -> 'eng' -> look up common ones
        prefix = nllb_code.split('_')[0] if '_' in nllb_code else nllb_code
        logger.warning(f"Unknown NLLB code '{nllb_code}', falling back to prefix '{prefix}'")
        return prefix

    def _whisper_to_nllb(self, whisper_code: str) -> Optional[str]:
        """Convert Whisper ISO 639-1 code to NLLB language code."""
        return self.WHISPER_TO_NLLB.get(whisper_code)

    def _find_translation_pair(self, detected_nllb: str) -> Optional[dict]:
        """Find the best translation pair for a detected language.

        Priority order:
        1. Active pair's source language matches -> translate source -> target
        2. Active pair's target language matches -> translate target -> source
        3. Other pairs' source matches -> translate source -> target
        4. Other pairs' target matches -> translate target -> source

        Returns:
            Dict with 'source' and 'target' NLLB codes, or None if no match
        """
        translation_settings = self.settings.get('translation', {})
        language_pairs = translation_settings.get('language_pairs', [])
        active_index = translation_settings.get('active_pair_index', 0)

        if not language_pairs:
            # Fallback to legacy single-pair settings
            source = translation_settings.get('source', 'eng_Latn')
            target = translation_settings.get('target', 'jpn_Jpan')
            return {'source': source, 'target': target}

        # Build ordered list: active pair first, then others
        ordered_pairs = []
        if 0 <= active_index < len(language_pairs):
            ordered_pairs.append(language_pairs[active_index])
        for i, pair in enumerate(language_pairs):
            if i != active_index:
                ordered_pairs.append(pair)

        # Search for a match
        for pair in ordered_pairs:
            pair_source = pair.get('source', 'eng_Latn')
            pair_target = pair.get('target', 'jpn_Jpan')

            if detected_nllb == pair_source:
                # Detected language is the source -> translate to target
                return {'source': pair_source, 'target': pair_target}
            if detected_nllb == pair_target:
                # Detected language is the target -> translate to source (reverse)
                return {'source': pair_target, 'target': pair_source}

        # No matching pair found - use active pair as fallback
        active = language_pairs[active_index] if active_index < len(language_pairs) else language_pairs[0]
        return {'source': active.get('source', 'eng_Latn'), 'target': active.get('target', 'jpn_Jpan')}

    def _translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using a 3-tier fallback chain.

        Tier 1: Paid cloud (DeepL / Google Cloud) — only if keys configured
        Tier 2: Free providers (MyMemory -> LibreTranslate -> Lingva)
        Tier 3: Local NLLB — if model is loaded

        Args:
            text: Text to translate
            source_lang: Source language (NLLB code)
            target_lang: Target language (NLLB code)

        Returns:
            Translated text

        Raises:
            RuntimeError: If no translation provider is available
        """
        # Tier 1: Paid cloud (DeepL/Google) — only if keys configured and active
        if self._cloud_translator and self._cloud_translator.active_provider:
            try:
                cloud_result = self._cloud_translator.translate(text, source_lang, target_lang)
                if cloud_result:
                    self._notify_provider_if_changed(self._cloud_translator.active_provider)
                    logger.info(
                        f"Cloud translation [{self._cloud_translator.active_provider}]: "
                        f"{cloud_result[:80]}"
                    )
                    return cloud_result
            except Exception as e:
                logger.warning(f"Paid cloud translation failed, trying free chain: {e}")

        # Tier 2: Free chain (MyMemory -> LibreTranslate -> Lingva)
        if self._free_translator:
            try:
                free_result = self._free_translator.translate(text, source_lang, target_lang)
                if free_result:
                    active = self._free_translator.get_active_provider()
                    self._notify_provider_if_changed(active)
                    return free_result
            except Exception as e:
                logger.warning(f"Free translation chain failed: {e}")

        # Tier 3: Local NLLB fallback
        if self._translator and self._translator.is_loaded:
            self._notify_provider_if_changed('nllb')
            return self._translator.translate(text, source_lang, target_lang)

        raise RuntimeError("No translation provider available")

    def _notify_provider_if_changed(self, new_provider: Optional[str]):
        """Broadcast a translation_provider_switched event only when the provider changes."""
        if new_provider == self._active_translation_provider:
            return  # No change — suppress event
        old = self._active_translation_provider
        self._active_translation_provider = new_provider
        logger.info(f"Translation provider switched: {old} -> {new_provider}")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.TRANSLATION_PROVIDER_SWITCHED, {
                    'provider': new_provider,
                    'previous': old,
                })),
                self._loop
            )

    async def _switch_translation_provider(self):
        """Switch to fallback translation provider after consecutive failures."""
        current = self.settings.get('translation', {}).get('provider', 'local')
        # Phase 1 simple fallback: cloud -> local, local -> log warning
        if current != 'local':
            logger.info(f"Switching translation from {current} to local NLLB fallback")
            self.settings['translation']['provider'] = 'local'
            # Notify frontend about the switch
            await self.broadcast(create_event(EventType.SETTINGS_UPDATED, {
                'translation_provider_switched': True,
                'new_provider': 'local',
                'reason': 'consecutive_failures',
            }))
        else:
            logger.warning("Local translation also failing — no further fallback available in Phase 1")

    async def initialize(self):
        """Initialize the engine and detect available hardware."""
        logger.info("Initializing STTS engine...")

        # Store event loop reference
        self._loop = asyncio.get_event_loop()

        # Detect GPU
        self._detect_compute_device()

        # Initialize audio manager
        self._audio_manager = AudioManager()
        self._audio_manager.on_audio_level = self._on_audio_level

        # Initialize STT
        self._stt = SpeechToText()
        self._stt.on_final_transcript = self._on_transcript

        # Initialize Cloud Translation Manager
        self._cloud_translator = CloudTranslationManager()

        # Initialize Free Translation Manager (always available as middle-tier fallback)
        # Lightweight — no model downloads, just HTTP clients
        self._free_translator = FreeTranslationManager()

        # Initialize TTS Manager
        self._tts = TTSManager()
        self._tts.on_speaking_started = self._on_tts_started
        self._tts.on_speaking_finished = self._on_tts_finished
        self._tts.on_error = self._on_tts_error

        # Apply TTS settings
        tts_settings = self.settings.get('tts', {})
        if tts_settings.get('engine'):
            self._tts.set_engine(tts_settings['engine'])
        if tts_settings.get('voice'):
            self._tts.set_voice(tts_settings['voice'])
        if tts_settings.get('speed'):
            self._tts.set_speed(tts_settings['speed'])
        if tts_settings.get('volume'):
            self._tts.set_volume(tts_settings['volume'])
        if tts_settings.get('output_device'):
            self._tts.set_output_device(tts_settings['output_device'])

        # Initialize AI Assistant
        self._ai_assistant = AIAssistantManager()
        self._ai_assistant.on_response = self._on_ai_response
        self._ai_assistant.on_error = self._on_ai_error

        # Initialize FallbackAIManager (wraps AIAssistantManager)
        self._fallback_manager = FallbackAIManager(
            self._ai_assistant,
            notify_callback=self._on_ai_provider_event
        )

        # Apply AI settings
        ai_settings = self.settings.get('ai', {})
        if ai_settings.get('keyword'):
            self._ai_assistant.set_keyword(ai_settings['keyword'])
        if ai_settings.get('provider'):
            self._ai_assistant.set_provider(ai_settings['provider'])
        if ai_settings.get('max_response_length'):
            self._ai_assistant.update_config(max_response_length=ai_settings['max_response_length'])

        # Initialize VRChat OSC
        self._vrchat = VRChatOSC()
        self._vrchat.set_status_callback(self._on_vrchat_status)
        if self.settings['vrchat']['osc_enabled']:
            self._vrchat.connect(
                self.settings['vrchat']['osc_ip'],
                self.settings['vrchat']['osc_port']
            )
            self._vrchat.set_typing_indicator(self.settings['vrchat']['typing_indicator'])

        # Initialize VR Overlay (optional - only if SteamVR is available)
        self._vr_overlay = VROverlay()
        if self._vr_overlay.is_available:
            overlay_settings = self.settings.get('vrOverlay', {})
            if overlay_settings.get('enabled', False):
                if self._vr_overlay.initialize():
                    self._vr_overlay.update_settings(overlay_settings)
                    logger.info("VR overlay initialized")
                else:
                    logger.info("VR overlay initialization failed (SteamVR may not be running)")
        else:
            logger.info("VR overlay not available (SteamVR not installed or no HMD)")

        # Initialize Speaker Capture (for capturing system audio)
        self._speaker_capture = SpeakerCapture()
        self._speaker_capture.on_audio_level = self._on_speaker_audio_level
        self._speaker_capture.on_error = self._on_speaker_error
        if self._speaker_capture.is_available():
            logger.info("Speaker capture available")
        else:
            logger.info("Speaker capture not available (soundcard library may not be installed)")

        self.initialized = True
        logger.info("STTS engine initialized")

    def _detect_compute_device(self):
        """Detect available compute devices (CPU/CUDA)."""
        self.cuda_available = False
        self.device = 'cpu'

        try:
            import torch
            if torch.cuda.is_available():
                self.cuda_available = True
                self.device = 'cuda'
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"CUDA available: {gpu_name}")
            else:
                logger.info("CUDA not available, using CPU")
        except ImportError:
            logger.info("PyTorch not installed, using CPU")

    def _on_audio_level(self, level: float):
        """Handle audio level updates."""
        if level > 0.05:  # Only log notable levels
            logger.info(f"Sending audio level: {level:.3f}")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.AUDIO_LEVEL, {'level': level})),
                self._loop
            )

    def _on_vrchat_status(self, event_type: str, data: dict):
        """Handle VRChat status updates."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.VRCHAT_STATUS, {
                    'event': event_type,
                    **data
                })),
                self._loop
            )

    def _on_tts_started(self):
        """Handle TTS started event."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.TTS_STARTED, {})),
                self._loop
            )

    def _on_tts_finished(self):
        """Handle TTS finished event."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.TTS_FINISHED, {})),
                self._loop
            )

    def _on_tts_error(self, error: str):
        """Handle TTS error event."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.ERROR, {'message': f'TTS error: {error}'})),
                self._loop
            )

    def _on_ai_response(self, response):
        """Handle AI assistant response."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._handle_ai_response(response),
                self._loop
            )

    async def _handle_ai_response(self, response):
        """Process AI response - send to chat, VRChat, and optionally speak."""
        from ai.assistant import AssistantResponse

        content = response.content

        # Broadcast AI response to frontend
        await self.broadcast(create_event(EventType.AI_RESPONSE, {
            'response': content,
            'model': response.model,
            'truncated': response.truncated
        }))

        ai_settings = self.settings.get('ai', {})

        # Send to VRChat if enabled
        if ai_settings.get('send_to_vrchat', True):
            if self._vrchat and self._vrchat.is_connected:
                await self._vrchat.send_text(content)

        # Show on VR overlay if enabled
        if self._vr_overlay and self._vr_overlay.is_initialized:
            self._vr_overlay.show_text(content, message_type='ai')

        # Speak response if enabled
        if ai_settings.get('speak_responses', True):
            if self._tts:
                await self._tts.speak(content)

    def _on_ai_error(self, error: str):
        """Handle AI assistant error."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.ERROR, {'message': f'AI error: {error}'})),
                self._loop
            )

    async def _on_ai_provider_event(self, event_type: str, data: dict):
        """Bridge FallbackAIManager events to WebSocket broadcast."""
        event_map = {
            'ai_provider_switched': EventType.AI_PROVIDER_SWITCHED,
            'ai_offline_mode': EventType.AI_OFFLINE_MODE,
            'ai_online_restored': EventType.AI_ONLINE_RESTORED,
        }
        if event_type in event_map:
            await self.broadcast(create_event(event_map[event_type], data))

    def _on_transcript(self, text: str, detected_language: Optional[str] = None):
        """Handle transcription results."""
        logger.info(f"[stt-callback] _on_transcript called: '{text[:100]}' lang={detected_language} (loop={self._loop is not None})")
        if self._loop and text.strip():
            asyncio.run_coroutine_threadsafe(
                self._process_transcript(text, detected_language),
                self._loop
            )

    def _on_speaker_transcript(self, text: str, detected_language: Optional[str] = None):
        """Handle speaker transcription results."""
        if self._loop and text.strip():
            asyncio.run_coroutine_threadsafe(
                self._process_speaker_transcript(text, detected_language),
                self._loop
            )

    def _on_speaker_audio_level(self, level: float):
        """Handle speaker audio level updates."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.AUDIO_LEVEL, {
                    'level': level,
                    'source': 'speaker'
                })),
                self._loop
            )

    def _on_speaker_error(self, error: str):
        """Handle speaker capture error."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.ERROR, {
                    'message': f'Speaker capture error: {error}'
                })),
                self._loop
            )

    async def _process_transcript(self, text: str, detected_language: Optional[str] = None):
        """Process a final transcript."""
        logger.info(f"Transcript [{detected_language}]: {text}")

        # Send to frontend
        await self.broadcast(create_event(EventType.TRANSCRIPT_FINAL, {
            'text': text,
            'detected_language': detected_language,
        }))

        translated = None

        # Translate if enabled (supports paid cloud, free chain, and local NLLB)
        if self.settings.get('translation', {}).get('enabled', False):
            has_cloud = self._cloud_translator and self._cloud_translator.active_provider is not None
            has_free = self._free_translator is not None
            has_local = self._translator and self._translator.is_loaded
            if has_cloud or has_free or has_local:
                try:
                    # Convert detected Whisper language to NLLB code
                    detected_nllb = self._whisper_to_nllb(detected_language) if detected_language else None

                    if detected_nllb:
                        # Smart routing: find best pair for detected language
                        pair = self._find_translation_pair(detected_nllb)
                        if pair:
                            source_lang = pair['source']
                            target_lang = pair['target']
                            # Only translate if source != target
                            if source_lang != target_lang:
                                translated = self._translate_text(text, source_lang, target_lang)
                                self._translation_failure_count = 0  # Reset on success
                                logger.info(f"Translation [{source_lang} -> {target_lang}]: {translated}")
                    else:
                        # Fallback: use active pair
                        language_pairs = self.settings['translation'].get('language_pairs', [])
                        active_index = self.settings['translation'].get('active_pair_index', 0)
                        if language_pairs and active_index < len(language_pairs):
                            active = language_pairs[active_index]
                            source_lang = active.get('source', 'eng_Latn')
                            target_lang = active.get('target', 'jpn_Jpan')
                        else:
                            source_lang = self.settings['translation'].get('source', 'eng_Latn')
                            target_lang = self.settings['translation'].get('target', 'jpn_Jpan')
                        translated = self._translate_text(text, source_lang, target_lang)
                        self._translation_failure_count = 0  # Reset on success
                        logger.info(f"Translation (fallback) [{source_lang} -> {target_lang}]: {translated}")
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    translated = None
                    self._translation_failure_count += 1

                    # Broadcast translation failure to frontend
                    await self.broadcast(create_event(EventType.TRANSLATION_FAILED, {
                        'original': text,
                        'error': str(e),
                    }))

                    # Auto-switch provider after consecutive failures
                    if self._translation_failure_count >= self._TRANSLATION_FAILURE_THRESHOLD:
                        logger.warning(f"Translation failed {self._translation_failure_count} times consecutively, attempting provider switch")
                        self._translation_failure_count = 0
                        await self._switch_translation_provider()

            if translated:
                await self.broadcast(create_event(EventType.TRANSLATION_COMPLETE, {
                    'original': text,
                    'translated': translated
                }))

        # Check for AI keyword and process query
        if self.settings.get('ai', {}).get('enabled', False):
            if self._ai_assistant:
                query = self._ai_assistant.check_keyword(text)
                if query:
                    logger.info(f"AI keyword detected, query: {query}")
                    try:
                        response = await self._fallback_manager.generate(query)
                        if response.model != 'fallback':
                            await self._handle_ai_response(response)
                        else:
                            # AI unavailable — show in chat only, NOT TTS/VRChat
                            await self.broadcast(create_event(EventType.AI_RESPONSE, {
                                'response': response.content,
                                'model': 'fallback',
                                'truncated': False,
                            }))
                        # Don't send the keyword-containing text to VRChat
                        return
                    except Exception as e:
                        logger.error(f"AI query error: {e}")

        # Send to VRChat — only when translation succeeded (or translation is disabled)
        translation_enabled = self.settings.get('translation', {}).get('enabled', False)
        if not translation_enabled or translated:
            if self._vrchat and self._vrchat.is_connected:
                vrchat_settings = self.settings.get('vrchat', {})
                if vrchat_settings.get('osc_enabled', True):
                    if translated and vrchat_settings.get('send_translations', True):
                        text_to_send = f"{text} - {translated}"
                    else:
                        text_to_send = text
                    await self._vrchat.send_text(text_to_send)

            # Show on VR overlay
            if self._vr_overlay and self._vr_overlay.is_initialized:
                overlay_settings = self.settings.get('vrOverlay', {})
                if overlay_settings.get('show_own_text', True):
                    display_text = text
                    if translated and overlay_settings.get('show_translations', True):
                        display_text = translated
                    self._vr_overlay.show_text(display_text, message_type='user')
        # When translation is enabled but failed: send nothing to VRChat or VR overlay

    async def process_text_input(self, text: str):
        """Process text input from the frontend (same as voice transcript).

        This method handles text typed in the UI the same way as voice transcripts:
        - Translates if enabled
        - Checks for AI keyword
        - Sends to VRChat
        """
        logger.info(f"Text input: {text}")

        # Send to frontend as a transcript
        await self.broadcast(create_event(EventType.TRANSCRIPT_FINAL, {'text': text}))

        translated = None

        # Debug: log translation settings
        translation_enabled = self.settings.get('translation', {}).get('enabled', False)
        has_cloud = self._cloud_translator and self._cloud_translator.active_provider is not None
        has_free = self._free_translator is not None
        has_local = self._translator and self._translator.is_loaded if self._translator else False
        logger.info(f"Translation check: enabled={translation_enabled}, has_cloud={has_cloud}, has_free={has_free}, has_local={has_local}")

        # Translate if enabled - text input uses active pair (no auto-detect)
        if translation_enabled:
            if has_cloud or has_free or has_local:
                try:
                    language_pairs = self.settings['translation'].get('language_pairs', [])
                    active_index = self.settings['translation'].get('active_pair_index', 0)
                    if language_pairs and active_index < len(language_pairs):
                        active = language_pairs[active_index]
                        source_lang = active.get('source', 'eng_Latn')
                        target_lang = active.get('target', 'jpn_Jpan')
                    else:
                        source_lang = self.settings['translation'].get('source', 'eng_Latn')
                        target_lang = self.settings['translation'].get('target', 'jpn_Jpan')
                    translated = self._translate_text(text, source_lang, target_lang)
                    self._translation_failure_count = 0  # Reset on success
                    logger.info(f"Translation: {translated}")
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    translated = None
                    self._translation_failure_count += 1

                    # Broadcast translation failure to frontend
                    await self.broadcast(create_event(EventType.TRANSLATION_FAILED, {
                        'original': text,
                        'error': str(e),
                    }))

                    # Auto-switch provider after consecutive failures
                    if self._translation_failure_count >= self._TRANSLATION_FAILURE_THRESHOLD:
                        logger.warning(f"Translation failed {self._translation_failure_count} times consecutively, attempting provider switch")
                        self._translation_failure_count = 0
                        await self._switch_translation_provider()

            if translated:
                await self.broadcast(create_event(EventType.TRANSLATION_COMPLETE, {
                    'original': text,
                    'translated': translated
                }))

        # Check for AI keyword and process query
        if self.settings.get('ai', {}).get('enabled', False):
            if self._ai_assistant:
                query = self._ai_assistant.check_keyword(text)
                if query:
                    logger.info(f"AI keyword detected, query: {query}")
                    try:
                        response = await self._fallback_manager.generate(query)
                        if response.model != 'fallback':
                            await self._handle_ai_response(response)
                        else:
                            # AI unavailable — show in chat only, NOT TTS/VRChat
                            await self.broadcast(create_event(EventType.AI_RESPONSE, {
                                'response': response.content,
                                'model': 'fallback',
                                'truncated': False,
                            }))
                        # Don't send the keyword-containing text to VRChat
                        return
                    except Exception as e:
                        logger.error(f"AI query error: {e}")

        # Send to VRChat — only when translation succeeded (or translation is disabled)
        if not translation_enabled or translated:
            if self._vrchat and self._vrchat.is_connected:
                vrchat_settings = self.settings.get('vrchat', {})
                if vrchat_settings.get('osc_enabled', True):
                    if translated and vrchat_settings.get('send_translations', True):
                        text_to_send = f"{text} - {translated}"
                    else:
                        text_to_send = text
                    await self._vrchat.send_text(text_to_send)

            # Show on VR overlay
            if self._vr_overlay and self._vr_overlay.is_initialized:
                overlay_settings = self.settings.get('vrOverlay', {})
                if overlay_settings.get('show_own_text', True):
                    display_text = text
                    if translated and overlay_settings.get('show_translations', True):
                        display_text = translated
                    self._vr_overlay.show_text(display_text, message_type='user')
        # When translation is enabled but failed: send nothing to VRChat or VR overlay

    async def _process_speaker_transcript(self, text: str, detected_language: Optional[str] = None):
        """Process a transcript from speaker capture (incoming speech)."""
        logger.info(f"Speaker transcript [{detected_language}]: {text}")

        speaker_settings = self.settings.get('speakerCapture', {})

        # Send to frontend
        await self.broadcast(create_event(EventType.TRANSCRIPT_FINAL, {
            'text': text,
            'source': 'speaker',
            'detected_language': detected_language,
        }))

        translated = None

        # Translate if enabled (supports paid cloud, free chain, and local NLLB)
        if speaker_settings.get('translate', True):
            if self.settings.get('translation', {}).get('enabled', False):
                has_cloud = self._cloud_translator and self._cloud_translator.active_provider is not None
                has_free = self._free_translator is not None
                has_local = self._translator and self._translator.is_loaded
                if has_cloud or has_free or has_local:
                    try:
                        detected_nllb = self._whisper_to_nllb(detected_language) if detected_language else None
                        if detected_nllb:
                            pair = self._find_translation_pair(detected_nllb)
                            if pair and pair['source'] != pair['target']:
                                source_lang = pair['source']
                                target_lang = pair['target']
                                translated = self._translate_text(text, source_lang, target_lang)
                                logger.info(f"Speaker translation [{source_lang} -> {target_lang}]: {translated}")
                        else:
                            # Fallback: use active pair
                            language_pairs = self.settings['translation'].get('language_pairs', [])
                            active_index = self.settings['translation'].get('active_pair_index', 0)
                            if language_pairs and active_index < len(language_pairs):
                                active = language_pairs[active_index]
                                source_lang = active.get('source', 'eng_Latn')
                                target_lang = active.get('target', 'jpn_Jpan')
                            else:
                                source_lang = self.settings['translation'].get('source', 'eng_Latn')
                                target_lang = self.settings['translation'].get('target', 'jpn_Jpan')
                            translated = self._translate_text(text, source_lang, target_lang)
                            logger.info(f"Speaker translation (fallback): {translated}")
                    except Exception as e:
                        logger.error(f"Speaker translation error: {e}")
                        translated = None

                if translated:
                    await self.broadcast(create_event(EventType.TRANSLATION_COMPLETE, {
                        'original': text,
                        'translated': translated,
                        'source': 'speaker'
                    }))

        # Show on VR overlay if enabled
        if speaker_settings.get('show_in_overlay', True):
            if self._vr_overlay and self._vr_overlay.is_initialized:
                overlay_settings = self.settings.get('vrOverlay', {})
                if overlay_settings.get('show_incoming_text', True):
                    display_text = translated if translated else text
                    self._vr_overlay.show_text(display_text, message_type='speaker')

    def _audio_processing_loop(self):
        """Background thread for processing microphone audio."""
        logger.info("Audio processing loop started")
        chunk_count = 0
        has_manager = self._audio_manager is not None
        has_stt = self._stt is not None
        stt_loaded = self._stt.is_loaded if self._stt else False
        logger.info(f"[audio-loop] audio_manager={has_manager}, stt={has_stt}, stt_loaded={stt_loaded}")

        while self._should_process:
            if self._audio_manager and self._stt:
                chunk = self._audio_manager.get_audio_chunk(timeout=0.1)
                if chunk is not None:
                    chunk_count += 1
                    if chunk_count <= 3 or chunk_count % 50 == 0:
                        logger.info(f"[audio-loop] Feeding chunk #{chunk_count} to STT (len={len(chunk)}, stt_loaded={self._stt.is_loaded})")
                    self._stt.process_audio_chunk(chunk)

        logger.info(f"Audio processing loop stopped (processed {chunk_count} chunks)")

    def _speaker_processing_loop(self):
        """Background thread for processing speaker audio."""
        logger.info("Speaker processing loop started")

        while self._should_process_speaker:
            if self._speaker_capture and self._speaker_stt:
                chunk = self._speaker_capture.get_audio_chunk(timeout=0.1)
                if chunk is not None:
                    self._speaker_stt.process_audio_chunk(chunk)

        logger.info("Speaker processing loop stopped")

    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information for display."""
        info: Dict[str, Any] = {
            'available': getattr(self, 'cuda_available', False),
            'name': None,
            'vram_total_mb': 0,
            'vram_used_mb': 0,
            'vram_free_mb': 0,
        }
        try:
            import torch
            if torch.cuda.is_available():
                info['name'] = torch.cuda.get_device_name(0)
                total = torch.cuda.get_device_properties(0).total_mem
                info['vram_total_mb'] = round(total / (1024 * 1024))
                # Get current usage
                reserved = torch.cuda.memory_reserved(0)
                allocated = torch.cuda.memory_allocated(0)
                info['vram_used_mb'] = round(allocated / (1024 * 1024))
                info['vram_free_mb'] = round((total - reserved) / (1024 * 1024))
        except Exception:
            pass
        return info

    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        gpu_info = self._get_gpu_info()
        return {
            'initialized': self.initialized,
            'listening': self.listening,
            'cuda_available': getattr(self, 'cuda_available', False),
            'device': getattr(self, 'device', 'cpu'),
            'gpu': gpu_info,
            'models': {
                'stt': self._stt is not None and self._stt.is_loaded,
                'stt_model': self._stt.current_model if self._stt else None,
                'translator': self._translator is not None and self._translator.is_loaded,
                'translator_model': self._translator.current_model if self._translator else None,
                'tts': self._tts is not None,
                'ai': self._ai_assistant is not None
            },
            'tts': {
                'available': self._tts is not None,
                'engine': self._tts.get_current_engine() if self._tts else None,
                'engines': self._tts.get_available_engines() if self._tts else [],
                'speaking': self._tts.is_speaking if self._tts else False
            },
            'ai': {
                'available': self._ai_assistant is not None,
                'provider': self._ai_assistant.get_current_provider() if self._ai_assistant else None,
                'providers': self._ai_assistant.get_available_providers() if self._ai_assistant else [],
                'keyword': self.settings.get('ai', {}).get('keyword', 'jarvis'),
                'fallback_provider': self._fallback_manager.get_active_provider() if self._fallback_manager else None,
            },
            'vrchat': {
                'connected': self._vrchat.is_connected if self._vrchat else False,
                'queue_size': self._vrchat.queue_size if self._vrchat else 0,
                'processing': self._vrchat.is_processing if self._vrchat else False
            },
            'vrOverlay': {
                'available': self._vr_overlay.is_available if self._vr_overlay else False,
                'initialized': self._vr_overlay.is_initialized if self._vr_overlay else False,
                'steamvr_installed': self._vr_overlay.is_runtime_installed if self._vr_overlay else False,
                'hmd_present': self._vr_overlay.is_hmd_present if self._vr_overlay else False
            },
            'speakerCapture': {
                'available': self._speaker_capture.is_available() if self._speaker_capture else False,
                'capturing': self._speaker_listening,
                'device': self._speaker_capture.device_name if self._speaker_capture else None
            },
            'cloudTranslation': {
                'active_provider': self._cloud_translator.active_provider if self._cloud_translator else None,
                'providers': self._cloud_translator.get_providers() if self._cloud_translator else [],
            },
            'translation': {
                'active_provider': self._active_translation_provider,
                'free_providers': self._free_translator.get_status() if self._free_translator else [],
            }
        }

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages for translation."""
        return Translator.get_supported_languages()

    def get_audio_devices(self) -> Dict[str, List[Dict]]:
        """Get available audio devices."""
        if self._audio_manager:
            return {
                'inputs': self._audio_manager.get_input_devices(),
                'outputs': self._audio_manager.get_output_devices()
            }
        return {'inputs': [], 'outputs': []}

    def _reload_models_on_device_change(self, new_device: str):
        """Reload STT and translation models on a new compute device.

        Runs in a background thread to avoid blocking the WebSocket handler.
        """
        def _reload():
            # Reload STT model
            if self._stt and self._stt.is_loaded:
                model_name = self._stt.model_name or self.settings.get('stt', {}).get('model', 'base')
                logger.info(f"Reloading STT model '{model_name}' on {new_device}")
                try:
                    self._stt.unload_model()
                    success = self._stt.load_model(model_name, new_device)
                    if success:
                        logger.info(f"STT model reloaded on {new_device}")
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast(create_event(EventType.MODEL_LOADED, {
                                    'type': 'stt', 'id': model_name
                                })),
                                self._loop
                            )
                    else:
                        logger.error(f"Failed to reload STT model on {new_device}")
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast(create_event(EventType.MODEL_ERROR, {
                                    'type': 'stt', 'id': model_name,
                                    'error': f'Failed to reload on {new_device}'
                                })),
                                self._loop
                            )
                except Exception as e:
                    logger.error(f"Error reloading STT model: {e}")

            # Reload translation model
            if self._translator and self._translator.is_loaded:
                model_name = self._translator.current_model or self.settings.get('translation', {}).get('model', 'nllb-200-distilled-600M')
                logger.info(f"Reloading translation model '{model_name}' on {new_device}")
                try:
                    self._translator.unload_model()
                    success = self._translator.load_model(model_name, new_device)
                    if success:
                        logger.info(f"Translation model reloaded on {new_device}")
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast(create_event(EventType.MODEL_LOADED, {
                                    'type': 'translation', 'id': model_name
                                })),
                                self._loop
                            )
                    else:
                        logger.error(f"Failed to reload translation model on {new_device}")
                except Exception as e:
                    logger.error(f"Error reloading translation model: {e}")

        # Broadcast that we're reloading
        if self._loop:
            if self._stt and self._stt.is_loaded:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(EventType.MODEL_LOADING, {
                        'type': 'stt',
                        'id': self._stt.model_name or 'unknown'
                    })),
                    self._loop
                )
            if self._translator and self._translator.is_loaded:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(EventType.MODEL_LOADING, {
                        'type': 'translation',
                        'id': self._translator.current_model or 'unknown'
                    })),
                    self._loop
                )

        # Run reload in background thread (model loading is blocking)
        thread = threading.Thread(target=_reload, daemon=True)
        thread.start()

    def update_settings(self, settings: Dict[str, Any]):
        """Update engine settings."""
        # Track old device setting before merge
        old_device = self.settings.get('stt', {}).get('device', 'auto')

        # Deep merge settings
        for key, value in settings.items():
            if key in self.settings and isinstance(self.settings[key], dict) and isinstance(value, dict):
                self.settings[key].update(value)
            else:
                self.settings[key] = value

        # Reload models if compute device changed
        new_device = self.settings.get('stt', {}).get('device', 'auto')
        if 'stt' in settings and 'device' in settings.get('stt', {}) and new_device != old_device:
            logger.info(f"Compute device changed: {old_device} -> {new_device}, reloading models...")
            self._reload_models_on_device_change(new_device)

        # Apply VAD settings
        if self._audio_manager and 'audio' in settings:
            audio_settings = settings['audio']
            if 'vad_enabled' in audio_settings:
                self._audio_manager.vad_enabled = audio_settings['vad_enabled']
            if 'vad_sensitivity' in audio_settings:
                self._audio_manager.vad_sensitivity = audio_settings['vad_sensitivity']

        # Apply TTS settings
        if self._tts and 'tts' in settings:
            tts_settings = settings['tts']
            if 'engine' in tts_settings:
                self._tts.set_engine(tts_settings['engine'])
            if 'voice' in tts_settings:
                self._tts.set_voice(tts_settings['voice'])
            if 'speed' in tts_settings:
                self._tts.set_speed(tts_settings['speed'])
            if 'volume' in tts_settings:
                self._tts.set_volume(tts_settings['volume'])
            if 'output_device' in tts_settings:
                self._tts.set_output_device(tts_settings['output_device'])
            # VOICEVOX-specific settings
            if 'voicevox_url' in tts_settings:
                voicevox = self._tts._engines.get('voicevox')
                if voicevox:
                    voicevox.engine_url = tts_settings['voicevox_url']
            if 'voicevox_english_phonetic' in tts_settings:
                voicevox = self._tts._engines.get('voicevox')
                if voicevox:
                    voicevox.enable_english_phonetic = tts_settings['voicevox_english_phonetic']

        # Apply AI settings
        if self._ai_assistant and 'ai' in settings:
            ai_settings = settings['ai']
            if 'keyword' in ai_settings:
                self._ai_assistant.set_keyword(ai_settings['keyword'])
            if 'provider' in ai_settings:
                self._ai_assistant.set_provider(ai_settings['provider'])
            if 'max_response_length' in ai_settings:
                self._ai_assistant.update_config(max_response_length=ai_settings['max_response_length'])

        # Apply VRChat settings
        if self._vrchat and 'vrchat' in settings:
            vrchat_settings = settings['vrchat']

            # Handle typing indicator
            if 'typing_indicator' in vrchat_settings:
                self._vrchat.set_typing_indicator(vrchat_settings['typing_indicator'])

            # Handle OSC connection changes
            if 'osc_enabled' in vrchat_settings or 'osc_ip' in vrchat_settings or 'osc_port' in vrchat_settings:
                new_enabled = self.settings['vrchat'].get('osc_enabled', True)
                new_ip = self.settings['vrchat'].get('osc_ip', '127.0.0.1')
                new_port = self.settings['vrchat'].get('osc_port', 9000)

                if new_enabled:
                    self._vrchat.connect(new_ip, new_port)
                else:
                    self._vrchat.disconnect()

        # Apply Translation settings - handle cloud provider and load local model if needed
        if 'translation' in settings:
            translation_settings = settings['translation']

            # Handle cloud translation provider switching
            # 'free' and 'local' are not cloud providers — don't pass them to CloudTranslationManager
            if 'provider' in translation_settings and self._cloud_translator:
                provider = translation_settings['provider']
                if provider in ('local', 'free'):
                    cloud_provider = None
                else:
                    cloud_provider = provider
                self._cloud_translator.set_provider(cloud_provider)
                logger.info(f"Translation provider set to: {provider}")

            if translation_settings.get('enabled', False):
                # Only load local NLLB model if using local provider (or no provider set)
                active_provider = self.settings.get('translation', {}).get('provider', 'local')
                if active_provider == 'local' or not active_provider:
                    # Check if translator needs to be loaded
                    if self._translator is None or not self._translator.is_loaded:
                        logger.info("Translation enabled (local), loading translator model...")
                        # Initialize translator if needed
                        if self._translator is None:
                            self._translator = Translator()
                        # Load the model synchronously (it will take a moment)
                        model_name = self.settings.get('translation', {}).get('model', 'nllb-200-distilled-600M')
                        device = self.settings.get('stt', {}).get('device', 'auto')
                        try:
                            success = self._translator.load_model(model_name, device)
                            if success:
                                logger.info(f"Translation model loaded: {model_name}")
                                # Broadcast model loaded event
                                if self._loop:
                                    asyncio.run_coroutine_threadsafe(
                                        self.broadcast(create_event(EventType.MODEL_LOADED, {
                                            'type': 'translation',
                                            'id': model_name
                                        })),
                                        self._loop
                                    )
                            else:
                                error_detail = self._translator.last_error or 'Unknown error'
                                logger.error(f"Failed to load translation model: {model_name} - {error_detail}")
                                if self._loop:
                                    asyncio.run_coroutine_threadsafe(
                                        self.broadcast(create_event(EventType.MODEL_ERROR, {
                                            'type': 'translation',
                                            'id': model_name,
                                            'error': error_detail
                                        })),
                                        self._loop
                                    )
                        except Exception as e:
                            import traceback
                            logger.error(f"Error loading translation model: {type(e).__name__}: {e}")
                            logger.error(f"Translation load traceback:\n{traceback.format_exc()}")
                            if self._loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.broadcast(create_event(EventType.MODEL_ERROR, {
                                        'type': 'translation',
                                        'id': model_name,
                                        'error': f'{type(e).__name__}: {e}'
                                    })),
                                    self._loop
                                )

        # Apply cloud translation API keys and free provider settings
        if 'credentials' in settings:
            creds = settings['credentials']
            if self._cloud_translator:
                if 'deepl_api_key' in creds and creds['deepl_api_key']:
                    self._cloud_translator.set_api_key('deepl', creds['deepl_api_key'])
                if 'google_translate_api_key' in creds and creds['google_translate_api_key']:
                    self._cloud_translator.set_api_key('google', creds['google_translate_api_key'])
            if self._free_translator:
                if 'mymemory_email' in creds:
                    self._free_translator.set_mymemory_email(creds['mymemory_email'])

        # Apply VR Overlay settings
        if 'vrOverlay' in settings:
            overlay_settings = settings['vrOverlay']
            if self._vr_overlay:
                # Handle enable/disable
                if 'enabled' in overlay_settings:
                    if overlay_settings['enabled'] and not self._vr_overlay.is_initialized:
                        # Initialize overlay if not already
                        if self._vr_overlay.is_available:
                            self._vr_overlay.initialize()
                    elif not overlay_settings['enabled'] and self._vr_overlay.is_initialized:
                        self._vr_overlay.shutdown()

                # Update other settings if initialized
                if self._vr_overlay.is_initialized:
                    self._vr_overlay.update_settings(self.settings.get('vrOverlay', {}))

        logger.info(f"Settings updated: {list(settings.keys())}")

    async def start_listening(self):
        """Start listening for audio input."""
        if self.listening:
            logger.info("[start_listening] Already listening, skipping")
            return

        # Ensure STT model is loaded
        if not self._stt or not self._stt.is_loaded:
            model = self.settings.get('stt', {}).get('model', 'base')
            device = self.settings.get('stt', {}).get('device', 'auto')
            logger.info(f"[start_listening] STT not loaded, loading model='{model}' device='{device}'")
            await self.load_model('stt', model)
        else:
            logger.info(f"[start_listening] STT already loaded: {self._stt.model_name}")

        # Set STT to auto-detect language for multi-pair routing
        if self._stt:
            self._stt.language = None  # Auto-detect for multi-language pair support
            logger.info(f"[start_listening] STT language set to auto-detect (multi-pair mode)")

        # Verify STT is actually loaded after load attempt
        stt_loaded = self._stt.is_loaded if self._stt else False
        logger.info(f"[start_listening] After load: stt={self._stt is not None}, is_loaded={stt_loaded}, callback={self._stt.on_final_transcript is not None if self._stt else 'N/A'}")

        # Start audio capture
        if self._audio_manager:
            device_id = self.settings.get('audio', {}).get('input_device')
            logger.info(f"[start_listening] Starting microphone capture (device_id={device_id})")
            self._audio_manager.start_microphone(device_id)
        else:
            logger.error("[start_listening] No audio manager!")

        # Start processing thread
        self._should_process = True
        self._process_thread = threading.Thread(target=self._audio_processing_loop, daemon=True)
        self._process_thread.start()

        self.listening = True
        logger.info("[start_listening] Started listening successfully")
        await self.broadcast(create_event(EventType.LISTENING_STARTED, {}))

    async def stop_listening(self):
        """Stop listening for audio input."""
        if not self.listening:
            return

        # Stop processing thread
        self._should_process = False
        if self._process_thread:
            self._process_thread.join(timeout=2)
            self._process_thread = None

        # Stop audio capture
        if self._audio_manager:
            self._audio_manager.stop_microphone()

        self.listening = False
        logger.info("Stopped listening")
        await self.broadcast(create_event(EventType.LISTENING_STOPPED, {}))

    async def start_mic_test(self, device_id: int = None):
        """Start microphone test - captures audio and sends levels without loading STT."""
        if self._mic_testing:
            return

        if self._audio_manager:
            # Use specified device or current setting
            if device_id is None:
                device_id = self.settings.get('audio', {}).get('input_device')
            self._audio_manager.start_microphone(device_id)
            self._mic_testing = True
            logger.info(f"Started microphone test (device: {device_id or 'default'})")

    async def stop_mic_test(self):
        """Stop microphone test."""
        if not self._mic_testing:
            return

        if self._audio_manager:
            self._audio_manager.stop_microphone()
            self._mic_testing = False
            logger.info("Stopped microphone test")

    async def start_speaker_capture(self):
        """Start capturing speaker/system audio."""
        if self._speaker_listening:
            return

        if not self._speaker_capture or not self._speaker_capture.is_available():
            logger.warning("Speaker capture not available")
            await self.broadcast(create_event(EventType.ERROR, {
                'message': 'Speaker capture not available'
            }))
            return

        # Initialize speaker STT if needed (separate from microphone STT)
        if self._speaker_stt is None:
            self._speaker_stt = SpeechToText()
            self._speaker_stt.on_final_transcript = self._on_speaker_transcript

        # Ensure STT model is loaded for speaker
        if not self._speaker_stt.is_loaded:
            model = self.settings.get('stt', {}).get('model', 'tiny')
            device = self.settings.get('stt', {}).get('device', 'auto')
            self._speaker_stt.load_model(model, device)

        # Start speaker capture
        speaker_settings = self.settings.get('speakerCapture', {})
        device_id = speaker_settings.get('device')
        if not self._speaker_capture.start_capture(device_id):
            await self.broadcast(create_event(EventType.ERROR, {
                'message': 'Failed to start speaker capture'
            }))
            return

        # Start processing thread
        self._should_process_speaker = True
        self._speaker_process_thread = threading.Thread(
            target=self._speaker_processing_loop, daemon=True
        )
        self._speaker_process_thread.start()

        self._speaker_listening = True
        logger.info("Started speaker capture")
        await self.broadcast(create_event(EventType.LISTENING_STARTED, {'source': 'speaker'}))

    async def stop_speaker_capture(self):
        """Stop capturing speaker/system audio."""
        if not self._speaker_listening:
            return

        # Stop processing thread
        self._should_process_speaker = False
        if self._speaker_process_thread:
            self._speaker_process_thread.join(timeout=2)
            self._speaker_process_thread = None

        # Stop capture
        if self._speaker_capture:
            self._speaker_capture.stop_capture()

        self._speaker_listening = False
        logger.info("Stopped speaker capture")
        await self.broadcast(create_event(EventType.LISTENING_STOPPED, {'source': 'speaker'}))

    def _broadcast_download_progress(self, model_id: str, progress: float):
        """Broadcast model download progress to frontend."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.MODEL_DOWNLOAD_PROGRESS, {
                    'id': model_id,
                    'progress': round(progress, 1),
                })),
                self._loop
            )

    async def load_model(self, model_type: str, model_id: str) -> bool:
        """Load a model.

        Args:
            model_type: Type of model (stt, translation, tts, llm)
            model_id: Model identifier

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Loading model: {model_type}/{model_id}")

        await self.broadcast(create_event(EventType.MODEL_LOADING, {
            'type': model_type,
            'id': model_id
        }))

        try:
            if model_type == 'stt':
                if self._stt is None:
                    self._stt = SpeechToText()
                    self._stt.on_final_transcript = self._on_transcript

                device = self.settings.get('stt', {}).get('device', 'auto')
                logger.info(f"[stt] Loading STT model: {model_id} on device: {device}")

                # Wrap with download progress tracking
                try:
                    from utils.download import patch_transformers_download_progress
                    with patch_transformers_download_progress(model_id, self._broadcast_download_progress):
                        success = self._stt.load_model(model_id, device)
                except ImportError:
                    success = self._stt.load_model(model_id, device)

                if success:
                    logger.info(f"[stt] STT model loaded successfully: {model_id}")
                    await self.broadcast(create_event(EventType.MODEL_LOADED, {
                        'type': model_type,
                        'id': model_id
                    }))
                    return True
                else:
                    raise RuntimeError(f"Failed to load STT model: {model_id}")

            elif model_type == 'translation':
                if self._translator is None:
                    self._translator = Translator()

                device = self.settings.get('stt', {}).get('device', 'auto')  # Share device setting

                # Wrap with download progress tracking
                try:
                    from utils.download import patch_transformers_download_progress
                    with patch_transformers_download_progress(model_id, self._broadcast_download_progress):
                        success = self._translator.load_model(model_id, device)
                except ImportError:
                    success = self._translator.load_model(model_id, device)

                if success:
                    await self.broadcast(create_event(EventType.MODEL_LOADED, {
                        'type': model_type,
                        'id': model_id
                    }))
                    return True
                else:
                    error_detail = self._translator.last_error or 'Unknown error'
                    raise RuntimeError(f"Failed to load translation model: {error_detail}")

            elif model_type == 'llm':
                # Load local LLM model
                if self._ai_assistant is None:
                    return False

                success = await self._ai_assistant.load_local_model(model_id)

                if success:
                    await self.broadcast(create_event(EventType.MODEL_LOADED, {
                        'type': model_type,
                        'id': model_id
                    }))
                    return True
                else:
                    raise RuntimeError("Failed to load LLM model")

            else:
                # Unknown model type
                logger.warning(f"Unknown model type: {model_type}")
                return False

        except Exception as e:
            import traceback
            logger.error(f"Error loading model {model_type}/{model_id}: {type(e).__name__}: {e}")
            logger.error(f"Model load traceback:\n{traceback.format_exc()}")
            await self.broadcast(create_event(EventType.MODEL_ERROR, {
                'type': model_type,
                'id': model_id,
                'error': f'{type(e).__name__}: {e}'
            }))
            return False

    async def speak(self, text: str):
        """Convert text to speech and play it.

        Args:
            text: Text to speak
        """
        if not self._tts:
            logger.warning("TTS not initialized")
            return

        logger.info(f"Speaking: {text[:50]}...")

        try:
            success = await self._tts.speak(text)
            if not success:
                logger.warning("TTS speak returned False")

        except Exception as e:
            logger.error(f"Error in TTS: {e}")
            await self.broadcast(create_event(EventType.ERROR, {'message': f'TTS error: {e}'}))

    def stop_speaking(self):
        """Stop current TTS playback."""
        if self._tts:
            self._tts.stop()

    async def ai_query(self, query: str) -> str:
        """Send a query to the AI assistant.

        Args:
            query: User query

        Returns:
            AI response
        """
        logger.info(f"AI query: {query[:50]}...")

        if not self._ai_assistant:
            return "AI assistant not available"

        try:
            response = await self._fallback_manager.generate(query)
            return response.content

        except Exception as e:
            logger.error(f"Error in AI query: {e}")
            return f"Error: {e}"

    async def cleanup(self):
        """Clean up resources."""
        await self.stop_listening()

        if self._audio_manager:
            self._audio_manager.cleanup()

        if self._stt:
            self._stt.unload_model()

        if self._translator:
            self._translator.unload_model()

        if self._tts:
            self._tts.cleanup()

        if self._ai_assistant:
            self._ai_assistant.cleanup()

        if self._vrchat:
            self._vrchat.disconnect()

        if self._vr_overlay:
            self._vr_overlay.shutdown()

        if self._speaker_capture:
            self._speaker_capture.cleanup()

        if self._speaker_stt:
            self._speaker_stt.unload_model()

        logger.info("Engine cleanup complete")

    async def send_to_vrchat(self, text: str, use_queue: bool = True):
        """Send text directly to VRChat chatbox.

        Args:
            text: Text to send
            use_queue: If True, use message queue with chunking; if False, send directly
        """
        if not self._vrchat or not self._vrchat.is_connected:
            logger.warning("VRChat OSC not connected")
            return

        if use_queue:
            await self._vrchat.send_text(text)
        else:
            self._vrchat.send_text_sync(text)

    def clear_vrchat_chatbox(self):
        """Clear the VRChat chatbox."""
        if self._vrchat and self._vrchat.is_connected:
            self._vrchat.clear_chatbox()

    def get_tts_voices(self, engine_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available TTS voices for an engine.

        Args:
            engine_id: Engine ID, or None for current engine

        Returns:
            List of voice info dicts
        """
        if not self._tts:
            return []

        voices = self._tts.get_voices(engine_id)
        return [
            {
                'id': v.id,
                'name': v.name,
                'language': v.language,
                'gender': v.gender,
                'description': v.description
            }
            for v in voices
        ]

    def get_tts_output_devices(self) -> List[Dict[str, Any]]:
        """Get available TTS output devices.

        Returns:
            List of device info dicts
        """
        if not self._tts:
            return []
        return self._tts.get_output_devices()

    def get_ai_providers(self) -> List[Dict[str, Any]]:
        """Get available AI providers.

        Returns:
            List of provider info dicts
        """
        if not self._ai_assistant:
            return []
        return self._ai_assistant.get_available_providers()

    def get_local_llm_models(self) -> List[Dict[str, Any]]:
        """Get available local LLM models.

        Returns:
            List of model info dicts
        """
        if not self._ai_assistant:
            return []
        return self._ai_assistant.get_local_models()

    def set_local_models_directory(self, path: str) -> bool:
        """Set the local models directory.

        Args:
            path: Path to the models directory

        Returns:
            True if successful
        """
        if not self._ai_assistant:
            return False
        return self._ai_assistant.set_local_models_directory(path)

    def get_local_models_directory(self) -> str:
        """Get the current local models directory.

        Returns:
            Path to models directory
        """
        if not self._ai_assistant:
            return ""
        return self._ai_assistant.get_local_models_directory()

    def set_ai_api_key(self, provider_id: str, api_key: str) -> bool:
        """Set API key for an AI provider.

        Args:
            provider_id: Provider ID
            api_key: API key

        Returns:
            True if successful
        """
        if not self._ai_assistant:
            return False
        return self._ai_assistant.set_api_key(provider_id, api_key)

    def has_ai_api_key(self, provider_id: str) -> bool:
        """Check if AI provider has API key configured.

        Args:
            provider_id: Provider ID

        Returns:
            True if API key is configured
        """
        if not self._ai_assistant:
            return False
        return self._ai_assistant.has_api_key(provider_id)

    def clear_ai_conversation(self):
        """Clear AI conversation history."""
        if self._fallback_manager:
            self._fallback_manager.clear_conversation()
        elif self._ai_assistant:
            self._ai_assistant.clear_conversation()

    # VR Overlay methods
    def show_overlay_text(self, text: str, message_type: str = 'system', duration: Optional[float] = None):
        """Show text on VR overlay.

        Args:
            text: Text to display
            message_type: Type of message ('user', 'incoming', 'ai', 'system')
            duration: Display duration in seconds (None for default)
        """
        if self._vr_overlay and self._vr_overlay.is_initialized:
            self._vr_overlay.show_text(text, message_type, duration)

    def clear_overlay(self):
        """Clear the VR overlay display."""
        if self._vr_overlay and self._vr_overlay.is_initialized:
            self._vr_overlay.clear()

    def get_vr_overlay_status(self) -> Dict[str, Any]:
        """Get detailed VR overlay status.

        Returns:
            Dict with overlay status details
        """
        if not self._vr_overlay:
            return {
                'available': False,
                'initialized': False,
                'steamvr_installed': False,
                'hmd_present': False
            }

        return {
            'available': self._vr_overlay.is_available,
            'initialized': self._vr_overlay.is_initialized,
            'steamvr_installed': self._vr_overlay.is_runtime_installed,
            'hmd_present': self._vr_overlay.is_hmd_present,
            'settings': self._vr_overlay.settings.__dict__ if self._vr_overlay.settings else None
        }

    # Speaker capture methods
    def get_loopback_devices(self) -> List[Dict[str, Any]]:
        """Get available loopback devices for speaker capture.

        Returns:
            List of device info dicts
        """
        if not self._speaker_capture:
            return []
        return self._speaker_capture.get_loopback_devices()

    def is_speaker_capture_available(self) -> bool:
        """Check if speaker capture is available."""
        if not self._speaker_capture:
            return False
        return self._speaker_capture.is_available()

    @property
    def is_speaker_listening(self) -> bool:
        """Check if speaker capture is active."""
        return self._speaker_listening
