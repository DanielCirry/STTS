"""
STTS Engine - Main processing engine
Coordinates STT, translation, TTS, and AI assistant functionality
"""

import asyncio
import logging
import random
import re
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

import numpy as np


# Keyword-to-emoji mapping for post-processing emoji insertion
_EMOJI_MAP = {
    'hello': '👋', 'hi': '👋', 'hey': '👋', 'greet': '👋',
    'funny': '😂', 'laugh': '😂', 'lol': '🤣', 'haha': '😄', 'joke': '😜',
    'love': '❤️', 'heart': '❤️', 'like': '👍',
    'sad': '😢', 'cry': '😢', 'sorry': '😔',
    'angry': '😠', 'mad': '😤',
    'happy': '😊', 'great': '😊', 'good': '👍', 'nice': '👍', 'awesome': '🔥',
    'cool': '😎', 'wow': '😮', 'amazing': '✨', 'beautiful': '✨',
    'thanks': '🙏', 'thank': '🙏',
    'yes': '✅', 'no': '❌', 'sure': '👍',
    'think': '🤔', 'wonder': '🤔', 'hmm': '🤔',
    'music': '🎵', 'sing': '🎵', 'song': '🎶',
    'food': '🍕', 'eat': '🍽️', 'drink': '🍹', 'coffee': '☕',
    'sleep': '😴', 'tired': '😴', 'night': '🌙',
    'sun': '☀️', 'rain': '🌧️', 'star': '⭐',
    'fire': '🔥', 'hot': '🔥', 'cold': '🥶',
    'fast': '⚡', 'slow': '🐢',
    'smart': '🧠', 'brain': '🧠',
    'money': '💰', 'rich': '💰',
    'time': '⏰', 'wait': '⏳',
    'dog': '🐕', 'cat': '🐱', 'chicken': '🐔',
    'world': '🌍', 'earth': '🌍',
    'game': '🎮', 'play': '🎮', 'win': '🏆',
    'help': '🤝', 'work': '💪', 'strong': '💪',
}

# Fallback emojis when no keyword matches
_FALLBACK_EMOJIS = ['😊', '✨', '👍', '🙂', '💫']

# NLLB language code → EasyOCR language code mapping
NLLB_TO_EASYOCR = {
    'eng_Latn': 'en', 'jpn_Jpan': 'ja', 'kor_Hang': 'ko',
    'zho_Hans': 'ch_sim', 'zho_Hant': 'ch_tra',
    'spa_Latn': 'es', 'fra_Latn': 'fr', 'deu_Latn': 'de',
    'ita_Latn': 'it', 'por_Latn': 'pt', 'rus_Cyrl': 'ru',
    'arb_Arab': 'ar', 'hin_Deva': 'hi', 'tha_Thai': 'th',
    'vie_Latn': 'vi', 'ind_Latn': 'id', 'nld_Latn': 'nl',
    'pol_Latn': 'pl', 'tur_Latn': 'tr', 'ukr_Cyrl': 'uk',
}


def _insert_emojis(text: str, max_emojis: int = 3) -> str:
    """Insert emojis into text based on keyword matching. Pure post-processing."""
    if not text or not text.strip():
        return text

    words = text.lower().split()
    # Find matching emojis from keywords in the text
    matched = []
    for word in words:
        clean = re.sub(r'[^a-z]', '', word)
        if clean in _EMOJI_MAP and _EMOJI_MAP[clean] not in matched:
            matched.append(_EMOJI_MAP[clean])
            if len(matched) >= max_emojis:
                break

    # If no keyword matches, pick 1 random fallback
    if not matched:
        matched = [random.choice(_FALLBACK_EMOJIS)]

    # Insert emojis: one after first sentence/clause, rest at end
    result = text
    if len(matched) >= 2:
        # Try to insert first emoji after first sentence boundary
        for sep in ['. ', '! ', '? ', ', ']:
            pos = result.find(sep)
            if pos > 0 and pos < len(result) - 2:
                insert_at = pos + len(sep)
                result = result[:insert_at] + matched[0] + ' ' + result[insert_at:]
                matched = matched[1:]
                break

    # Append remaining emojis at end
    result = result.rstrip() + ' ' + ' '.join(matched)
    return result.strip()

from core.events import EventType, create_event
from core.audio_manager import AudioManager
from core.speaker_capture import SpeakerCapture
from ai.stt import SpeechToText
from ai.translator import Translator, LANGUAGE_CODES
from ai.tts import TTSManager
from ai.assistant import AIAssistantManager, AssistantConfig
from ai.assistant.fallback import FallbackAIManager
from ai.translator_cloud import CloudTranslationManager
from ai.translator_free import FreeTranslationManager
from integrations.vrchat_osc import VRChatOSC
from integrations.vr_overlay import VROverlay
from integrations.vr_ocr_overlay import VROCROverlay, get_vr_ocr_overlay
from ai.ocr.ocr_engine import OCREngine
from ai.ocr.ocr_renderer import render_translation_texture

logger = logging.getLogger('stts.engine')

# Map NLLB language codes to TTS language prefixes for auto voice selection
_NLLB_TO_TTS_LANG = {
    'eng_Latn': 'en', 'jpn_Jpan': 'ja', 'zho_Hans': 'zh', 'zho_Hant': 'zh',
    'kor_Hang': 'ko', 'spa_Latn': 'es', 'fra_Latn': 'fr', 'deu_Latn': 'de',
    'por_Latn': 'pt', 'rus_Cyrl': 'ru', 'ita_Latn': 'it', 'arb_Arab': 'ar',
    'hin_Deva': 'hi', 'tha_Thai': 'th', 'vie_Latn': 'vi',
}


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
        self._mic_rvc = None
        self._voicevox_manager = None

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
                'showOriginalText': True,
                'showTranslatedText': True,
                'showAIResponses': True,
                'showListenText': True,
            },
            'speakerCapture': {
                'enabled': False,
                'device': None,  # None = default speaker
                'translate': True,
                'show_in_chat': True,
            },
            'rvc': {
                'enabled': False,
                'model_path': None,
                'index_path': None,
                'models_directory': 'models/rvc/voices',
                'f0_up_key': 0,
                'index_rate': 0.75,
                'filter_radius': 3,
                'rms_mix_rate': 0.25,
                'protect': 0.33,
                'resample_sr': 0,
                'volume_envelope': 0.0,
            },
            'ocr': {
                'enabled': False,
                'device': 'cpu',
                'mode': 'manual',
                'interval': 3,
                'languages': ['en'],
                'confidence': 0.3,
                'crop_region': None,
            }
        }

        # Module instances
        self._audio_manager: Optional[AudioManager] = None
        self._stt: Optional[SpeechToText] = None
        self._translator: Optional[Translator] = None
        self._translator_load_failed: bool = False
        self._cloud_translator: Optional[CloudTranslationManager] = None
        self._free_translator: Optional[FreeTranslationManager] = None
        self._active_translation_provider: Optional[str] = None
        self._tts: Optional[TTSManager] = None
        self._ai_assistant: Optional[AIAssistantManager] = None
        self._fallback_manager: Optional[FallbackAIManager] = None
        self._vrchat: Optional[VRChatOSC] = None
        self._osc_clients: Dict[str, VRChatOSC] = {}  # profile_id -> OSC client
        self._vr_overlay: Optional[VROverlay] = None
        self._speaker_capture: Optional[SpeakerCapture] = None
        self._speaker_stt: Optional[SpeechToText] = None  # Separate STT for speaker

        # OCR Engine
        self._ocr_engine: Optional[OCREngine] = None
        self._vr_ocr_overlay: Optional[VROCROverlay] = None

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

    # Extended ISO 639-1 to NLLB mapping for langdetect results
    _LANGDETECT_TO_NLLB = {
        **{v: k for k, v in NLLB_TO_WHISPER.items()},
        # langdetect uses 'zh-cn'/'zh-tw' instead of plain 'zh'
        'zh-cn': 'zho_Hans',
        'zh-tw': 'zho_Hant',
    }

    # Common fallback languages to try (in priority order) when no pair matches
    _COMMON_FALLBACK_LANGS = [
        'eng_Latn', 'rus_Cyrl', 'zho_Hans', 'spa_Latn',
        'fra_Latn', 'deu_Latn', 'por_Latn', 'arb_Arab',
    ]

    def _detect_text_language(self, text: str) -> Optional[str]:
        """Detect the language of text and return NLLB code.

        Uses langdetect library. Returns None if detection fails.
        """
        try:
            from langdetect import detect
            iso_code = detect(text)
            nllb = self._LANGDETECT_TO_NLLB.get(iso_code)
            if nllb:
                return nllb
            # Try mapping via LANGUAGE_CODES (short codes like 'en' -> 'eng_Latn')
            nllb = LANGUAGE_CODES.get(iso_code)
            if nllb:
                return nllb
            logger.debug(f"langdetect returned '{iso_code}' but no NLLB mapping found")
            return None
        except Exception as e:
            logger.debug(f"Language detection failed: {e}")
            return None

    def _get_user_native_language(self) -> str:
        """Get the user's native language (source of active translation pair)."""
        translation_settings = self.settings.get('translation', {})
        language_pairs = translation_settings.get('language_pairs', [])
        active_index = translation_settings.get('active_pair_index', 0)
        if language_pairs and active_index < len(language_pairs):
            return language_pairs[active_index].get('source', 'eng_Latn')
        return translation_settings.get('source', 'eng_Latn')

    def _detect_and_translate_to_user(self, text: str, whisper_lang: Optional[str] = None) -> Optional[tuple]:
        """Detect text language and translate TO the user's native language.

        Used for speaker capture: translates incoming speech to the user's language.
        If the text is already in the user's language, returns None (no translation).

        Detection priority:
        1. Whisper detected language (from STT, if available)
        2. langdetect on the text
        3. Try pair languages as candidates
        4. Try common fallback languages

        Args:
            text: Text to translate
            whisper_lang: Optional Whisper ISO 639-1 code from STT detection

        Returns:
            Tuple of (translated_text, source_nllb, target_nllb) or None
        """
        user_lang = self._get_user_native_language()

        # Step 1: Try Whisper detection first (most reliable for speech)
        detected = self._whisper_to_nllb(whisper_lang) if whisper_lang else None

        # Step 2: Fall back to langdetect on text
        if not detected:
            detected = self._detect_text_language(text)

        if detected:
            if detected == user_lang:
                logger.debug(f"Speaker text already in user's language ({user_lang}), skipping translation")
                return None
            try:
                translated = self._translate_text(text, detected, user_lang)
                return (translated, detected, user_lang)
            except Exception as e:
                logger.warning(f"Speaker translation failed [{detected} -> {user_lang}]: {e}")

        # Step 3: Detection failed — try pair languages as candidates
        translation_settings = self.settings.get('translation', {})
        language_pairs = translation_settings.get('language_pairs', [])
        active_index = translation_settings.get('active_pair_index', 0)

        candidates = []
        pair_langs = set()

        # Active pair's target first (most likely for speaker capture)
        if language_pairs and active_index < len(language_pairs):
            active = language_pairs[active_index]
            target = active.get('target', 'jpn_Jpan')
            if target != user_lang:
                candidates.append(target)
            pair_langs.add(active.get('source', 'eng_Latn'))
            pair_langs.add(target)

        for i, pair in enumerate(language_pairs):
            if i == active_index:
                continue
            for key in ('target', 'source'):
                lang = pair.get(key, 'eng_Latn')
                if lang != user_lang and lang not in candidates:
                    candidates.append(lang)
                pair_langs.add(lang)

        # Step 4: Common fallback languages
        for lang in self._COMMON_FALLBACK_LANGS:
            if lang != user_lang and lang not in pair_langs and lang not in candidates:
                candidates.append(lang)

        for candidate_source in candidates:
            try:
                translated = self._translate_text(text, candidate_source, user_lang)
                return (translated, candidate_source, user_lang)
            except Exception as e:
                logger.debug(f"Speaker candidate translation failed [{candidate_source} -> {user_lang}]: {e}")

        logger.warning("Speaker translation: could not detect language or translate")
        return None

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

    @staticmethod
    def _split_emojis(text: str) -> list:
        """Split text into alternating [text, emoji, text, emoji, ...] segments.

        Preserves emojis and trailing punctuation so they survive translation.
        """
        # Match common emoji ranges using built-in re (no regex dependency needed)
        # Covers: emoticons, dingbats, symbols, supplemental symbols, flags, etc.
        emoji_pattern = re.compile(
            '['
            '\U0001F600-\U0001F64F'  # emoticons
            '\U0001F300-\U0001F5FF'  # misc symbols & pictographs
            '\U0001F680-\U0001F6FF'  # transport & map
            '\U0001F700-\U0001F77F'  # alchemical symbols
            '\U0001F780-\U0001F7FF'  # geometric shapes extended
            '\U0001F800-\U0001F8FF'  # supplemental arrows-C
            '\U0001F900-\U0001F9FF'  # supplemental symbols
            '\U0001FA00-\U0001FA6F'  # chess symbols
            '\U0001FA70-\U0001FAFF'  # symbols extended-A
            '\U00002702-\U000027B0'  # dingbats
            '\U0000FE00-\U0000FE0F'  # variation selectors
            '\U0000200D'             # ZWJ
            '\U00002600-\U000026FF'  # misc symbols
            '\U00002300-\U000023FF'  # misc technical
            '\U00002764'             # heart
            '\U00002B50'             # star
            '\U00002B05-\U00002B07'  # arrows
            '\U00002934-\U00002935'  # arrows
            '\U000025AA-\U000025AB'  # squares
            '\U000025FB-\U000025FE'  # squares
            '\U00003030\U0000303D'   # wavy dash, part alternation mark
            '\U0000200D'             # ZWJ
            ']+',
            re.UNICODE
        )
        parts = []
        last_end = 0
        for m in emoji_pattern.finditer(text):
            if m.start() > last_end:
                parts.append(('text', text[last_end:m.start()]))
            parts.append(('emoji', m.group()))
            last_end = m.end()
        if last_end < len(text):
            parts.append(('text', text[last_end:]))
        return parts

    def _translate_preserving_emojis(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text while preserving emoji positions.

        Splits text around emojis, translates each text chunk, and reassembles
        with emojis in their original positions. Trailing punctuation after emojis
        is preserved without translation.
        """
        parts = self._split_emojis(text)

        # If no emojis found, translate directly
        if not any(p[0] == 'emoji' for p in parts):
            return self._translate_text_raw(text, source_lang, target_lang)

        result_parts = []
        for kind, segment in parts:
            if kind == 'emoji':
                result_parts.append(segment)
            else:
                # Strip trailing punctuation that doesn't need translation
                stripped = segment.rstrip()
                trailing_ws = segment[len(stripped):]
                punct_end = ''
                while stripped and stripped[-1] in '!?.,;:…':
                    punct_end = stripped[-1] + punct_end
                    stripped = stripped[:-1]

                clean = stripped.strip()
                if clean:
                    translated_chunk = self._translate_text_raw(clean, source_lang, target_lang)
                    result_parts.append(translated_chunk + punct_end + trailing_ws)
                else:
                    # Only punctuation/whitespace, keep as-is
                    result_parts.append(segment)

        return ''.join(result_parts)

    def _translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text respecting the user's selected provider.

        Preserves emojis in their original positions through translation.

        Provider routing:
        - 'local': Direct to local NLLB only
        - 'free': Free providers only (MyMemory -> LibreTranslate -> Lingva), fall back to NLLB
        - 'google'/'deepl': Paid cloud first, fall back to free, then NLLB

        Args:
            text: Text to translate
            source_lang: Source language (NLLB code)
            target_lang: Target language (NLLB code)

        Returns:
            Translated text

        Raises:
            RuntimeError: If no translation provider is available
        """
        # Check if text contains emojis — if so, use emoji-preserving path
        parts = self._split_emojis(text)
        if any(p[0] == 'emoji' for p in parts):
            logger.debug(f"[translate] Text contains emojis, using emoji-preserving translation")
            return self._translate_preserving_emojis(text, source_lang, target_lang)

        return self._translate_text_raw(text, source_lang, target_lang)

    def _translate_text_raw(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text without emoji handling (raw translation).

        Provider routing:
        - 'local': Direct to local NLLB only
        - 'free': Free providers only (MyMemory -> LibreTranslate -> Lingva), fall back to NLLB
        - 'google'/'deepl': Paid cloud first, fall back to free, then NLLB
        """
        provider = self.settings.get('translation', {}).get('provider', 'local')

        # If user selected local NLLB, try it first
        if provider == 'local':
            if self._translator and self._translator.is_loaded:
                self._notify_provider_if_changed('nllb')
                return self._translator.translate(text, source_lang, target_lang)
            # NLLB not loaded — fall through to free providers as fallback
            logger.warning("Local NLLB not loaded, falling back to free providers")

        # Tier 1: Paid cloud (DeepL/Google) — only for cloud providers, not 'free' or 'local'
        if provider not in ('free', 'local') and self._cloud_translator and self._cloud_translator.active_provider:
            try:
                cloud_result = self._cloud_translator.translate(text, source_lang, target_lang)
                if cloud_result:
                    self._notify_provider_if_changed(self._cloud_translator.active_provider)
                    logger.debug(
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

        # Initialize VRChat OSC via output profiles
        self._sync_osc_clients()
        self._sync_tts_output_devices()
        # Legacy fallback: also init from vrchat settings if no profiles
        if not self._osc_clients:
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
                    logger.debug("VR overlay initialized")
                else:
                    logger.debug("VR overlay initialization failed (SteamVR may not be running)")
        else:
            logger.debug("VR overlay not available (SteamVR not installed or no HMD)")

        # Initialize OCR Engine (optional - requires easyocr + mss)
        self._ocr_engine = OCREngine()
        self._ocr_engine.on_ocr_complete = self._on_ocr_complete
        self._ocr_engine.on_status_change = self._on_ocr_status_change
        self._ocr_engine.set_translate_fn(self._ocr_translate_text)
        logger.debug("OCR engine initialized (model loads lazily on first use)")

        # Initialize VR OCR Overlay (depends on VR overlay being initialized)
        self._vr_ocr_overlay = get_vr_ocr_overlay()
        if self._vr_overlay and self._vr_overlay.is_initialized:
            if self._vr_ocr_overlay.initialize(self._vr_overlay._openvr):
                self._vr_ocr_overlay.on_capture_triggered = self._on_vr_ocr_capture
                self._vr_ocr_overlay.on_toggle_region = self._on_vr_ocr_region_toggle
                self._vr_ocr_overlay.on_region_changed = self._on_vr_ocr_region_changed
                self._vr_ocr_overlay.start_event_polling()
                # Apply saved OCR settings
                ocr_settings = self.settings.get('ocr', {})
                self._vr_ocr_overlay.update_settings(ocr_settings)
                if ocr_settings.get('enabled', False):
                    self._vr_ocr_overlay.set_enabled(True)
                logger.debug("VR OCR overlay initialized and polling")
            else:
                logger.debug("VR OCR overlay initialization failed")
        else:
            logger.debug("VR OCR overlay skipped (VR overlay not initialized)")

        # Initialize Speaker Capture (for capturing system audio)
        self._speaker_capture = SpeakerCapture()
        self._speaker_capture.on_audio_level = self._on_speaker_audio_level
        self._speaker_capture.on_error = self._on_speaker_error
        if self._speaker_capture.is_available():
            logger.debug("Speaker capture available")
        else:
            logger.debug("Speaker capture not available (soundcard library may not be installed)")

        self.initialized = True
        logger.info("STTS engine initialized")

    def _detect_compute_device(self):
        """Detect available compute devices (CPU/CUDA)."""
        self.cuda_available = False
        self.device = 'cpu'

        if getattr(sys, 'frozen', False):
            # In frozen exe, don't try importing torch at startup — it may not
            # be installed yet (lives in external venv). Importing and failing
            # would poison sys.modules and break later imports after install.
            logger.debug("Frozen exe: skipping torch detection at startup (CPU default)")
        else:
            try:
                import torch
                if torch.cuda.is_available():
                    self.cuda_available = True
                    self.device = 'cuda'
                    gpu_name = torch.cuda.get_device_name(0)
                    logger.debug(f"CUDA available: {gpu_name}")
                else:
                    logger.debug("CUDA not available, using CPU")
            except ImportError:
                logger.debug("PyTorch not installed, using CPU")

    def _on_audio_level(self, level: float):
        """Handle audio level updates."""
        if level > 0.05:  # Only log notable levels
            logger.debug(f"Sending audio level: {level:.3f}")
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
        """Process AI response - translate, send to chat, VRChat, and optionally speak."""
        content = response.content

        # Post-process: insert emojis if emoji mode is on
        if self.settings.get('ai', {}).get('emoji_mode', False):
            content = _insert_emojis(content)

        # Translate AI response if translation is enabled
        translated = None
        target_lang = None
        if self.settings.get('translation', {}).get('enabled', False):
            try:
                language_pairs = self.settings['translation'].get('language_pairs', [])
                active_index = self.settings['translation'].get('active_pair_index', 0)
                if language_pairs and active_index < len(language_pairs):
                    active = language_pairs[active_index]
                    source_lang = active.get('source', 'eng_Latn')
                    target_lang = active.get('target', 'jpn_Jpan')
                else:
                    source_lang = 'eng_Latn'
                    target_lang = 'jpn_Jpan'
                if source_lang != target_lang:
                    translated = self._translate_text(content, source_lang, target_lang)
                    logger.debug(f"AI response translated: {translated[:80]}")
            except Exception as e:
                logger.warning(f"AI response translation failed: {e}")

        # Broadcast AI response to frontend
        await self.broadcast(create_event(EventType.AI_RESPONSE, {
            'response': content,
            'translated': translated,
            'model': response.model,
            'truncated': response.truncated
        }))

        ai_settings = self.settings.get('ai', {})

        # Send AI response to OSC profiles
        ai_text = translated or content
        await self._route_text_to_osc(ai_text, 'ai')

        # Show on VR overlay if enabled
        if self._vr_overlay and self._vr_overlay.is_initialized:
            overlay_settings = self.settings.get('vrOverlay', {})
            if overlay_settings.get('showAIResponses', True):
                self._send_to_overlay(content, translated, 'ai')

        # Speak response if enabled
        if ai_settings.get('speak_responses', True):
            if self._tts:
                speak_text = translated or content
                tts_lang = _NLLB_TO_TTS_LANG.get(target_lang) if translated and target_lang else None
                await self._tts.speak(speak_text, language=tts_lang)

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
        logger.debug(f"[stt-callback] _on_transcript called: '{text[:100]}' lang={detected_language} (loop={self._loop is not None})")
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
        """Process a final transcript.

        Pipeline order:
        1. AI keyword check FIRST (only if AI is enabled)
           - If keyword found: send query to AI, AI response gets translated/spoken
           - Return early (don't translate or speak the keyword text itself)
        2. If no AI keyword: translate user text, speak only if mic→RVC is off
        """
        logger.info(f"[transcript] text='{text[:80]}' detected_lang={detected_language}")

        # Send to frontend
        await self.broadcast(create_event(EventType.TRANSCRIPT_FINAL, {
            'text': text,
            'detected_language': detected_language,
        }))

        # --- Step 1: AI keyword check (BEFORE translation) ---
        if self.settings.get('ai', {}).get('enabled', False):
            if self._ai_assistant:
                query = self._ai_assistant.check_keyword(text)
                if query:
                    logger.debug(f"AI keyword detected, query: {query}")
                    try:
                        response = await self._fallback_manager.generate(query)
                        if response.model != 'fallback':
                            await self._handle_ai_response(response)
                        else:
                            await self.broadcast(create_event(EventType.AI_RESPONSE, {
                                'response': response.content,
                                'model': 'fallback',
                                'truncated': False,
                            }))
                    except Exception as e:
                        logger.error(f"AI query error: {e}")
                    # Don't translate/speak/send the keyword text itself
                    return

        # --- Step 2: Translate user text ---
        translated = None
        target_lang = None

        if self.settings.get('translation', {}).get('enabled', False):
            has_cloud = self._cloud_translator and self._cloud_translator.active_provider is not None
            has_free = self._free_translator is not None
            has_local = self._translator and self._translator.is_loaded
            logger.info(f"[translate] enabled=True, has_cloud={has_cloud}, has_free={has_free}, has_local={has_local}")
            if has_cloud or has_free or has_local:
                try:
                    detected_nllb = self._whisper_to_nllb(detected_language) if detected_language else None
                    logger.info(f"[translate] detected_nllb={detected_nllb}")

                    if detected_nllb:
                        pair = self._find_translation_pair(detected_nllb)
                        logger.info(f"[translate] found pair for detected lang: {pair}")
                        if pair:
                            source_lang = pair['source']
                            target_lang = pair['target']
                            if source_lang != target_lang:
                                translated = self._translate_text(text, source_lang, target_lang)
                                self._translation_failure_count = 0
                                logger.info(f"[translate] [{source_lang} -> {target_lang}]: '{translated[:80] if translated else 'NONE'}'")
                    else:
                        language_pairs = self.settings['translation'].get('language_pairs', [])
                        active_index = self.settings['translation'].get('active_pair_index', 0)
                        logger.info(f"[translate] no detected lang, using active pair: index={active_index}, pairs={language_pairs}")
                        if language_pairs and active_index < len(language_pairs):
                            active = language_pairs[active_index]
                            source_lang = active.get('source', 'eng_Latn')
                            target_lang = active.get('target', 'jpn_Jpan')
                        else:
                            source_lang = self.settings['translation'].get('source', 'eng_Latn')
                            target_lang = self.settings['translation'].get('target', 'jpn_Jpan')
                        logger.info(f"[translate] fallback path: {source_lang} -> {target_lang}")
                        translated = self._translate_text(text, source_lang, target_lang)
                        self._translation_failure_count = 0
                        logger.info(f"[translate] result: '{translated[:80] if translated else 'NONE'}'")
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    translated = None
                    self._translation_failure_count += 1
                    await self.broadcast(create_event(EventType.TRANSLATION_FAILED, {
                        'original': text,
                        'error': str(e),
                    }))
                    if self._translation_failure_count >= self._TRANSLATION_FAILURE_THRESHOLD:
                        self._translation_failure_count = 0
                        await self._switch_translation_provider()

            if translated:
                await self.broadcast(create_event(EventType.TRANSLATION_COMPLETE, {
                    'original': text,
                    'translated': translated
                }))

        # --- Step 3: TTS — only if mic→RVC is NOT active ---
        # When mic→RVC is on, the user's real voice is already being output
        # through RVC, so TTS would create a duplicate voice
        mic_rvc_active = self._mic_rvc and self._mic_rvc.is_running
        tts_enabled = self.settings.get('tts', {}).get('enabled', True)
        if tts_enabled and self._tts and not mic_rvc_active:
            speak_text = translated or text
            tts_lang = _NLLB_TO_TTS_LANG.get(target_lang) if translated and target_lang else None
            try:
                await self._tts.speak(speak_text, language=tts_lang)
            except Exception as e:
                logger.warning(f"TTS failed: {e}")

        # --- Step 4: Send to OSC profiles / VR overlay ---
        await self._route_text_to_osc(text, 'original')
        if translated:
            await self._route_text_to_osc(translated, 'translated')

        if self._vr_overlay and self._vr_overlay.is_initialized:
            self._send_to_overlay(text, translated, 'user')

    async def process_text_input(self, text: str):
        """Process text input from the frontend.

        Same pipeline as _process_transcript:
        1. AI keyword check first (if AI enabled)
        2. Translate user text
        3. TTS only if mic→RVC is off
        4. Send to VRChat/overlay
        """
        logger.debug(f"Text input: {text}")

        await self.broadcast(create_event(EventType.TRANSCRIPT_FINAL, {'text': text}))

        # --- Step 1: AI keyword check FIRST ---
        if self.settings.get('ai', {}).get('enabled', False):
            if self._ai_assistant:
                query = self._ai_assistant.check_keyword(text)
                if query:
                    logger.debug(f"AI keyword detected, query: {query}")
                    try:
                        response = await self._fallback_manager.generate(query)
                        if response.model != 'fallback':
                            await self._handle_ai_response(response)
                        else:
                            await self.broadcast(create_event(EventType.AI_RESPONSE, {
                                'response': response.content,
                                'model': 'fallback',
                                'truncated': False,
                            }))
                    except Exception as e:
                        logger.error(f"AI query error: {e}")
                    return

        # --- Step 2: Translate ---
        translated = None
        target_lang = None
        translation_enabled = self.settings.get('translation', {}).get('enabled', False)

        if translation_enabled:
            has_cloud = self._cloud_translator and self._cloud_translator.active_provider is not None
            has_free = self._free_translator is not None
            has_local = self._translator and self._translator.is_loaded if self._translator else False
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
                    self._translation_failure_count = 0
                    logger.debug(f"Translation: {translated}")
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    translated = None
                    self._translation_failure_count += 1
                    await self.broadcast(create_event(EventType.TRANSLATION_FAILED, {
                        'original': text, 'error': str(e),
                    }))
                    if self._translation_failure_count >= self._TRANSLATION_FAILURE_THRESHOLD:
                        self._translation_failure_count = 0
                        await self._switch_translation_provider()

            if translated:
                await self.broadcast(create_event(EventType.TRANSLATION_COMPLETE, {
                    'original': text, 'translated': translated
                }))

        # --- Step 3: TTS only if mic→RVC is NOT active ---
        mic_rvc_active = self._mic_rvc and self._mic_rvc.is_running
        tts_enabled = self.settings.get('tts', {}).get('enabled', True)
        if tts_enabled and self._tts and not mic_rvc_active:
            speak_text = translated or text
            tts_lang = _NLLB_TO_TTS_LANG.get(target_lang) if translated and target_lang else None
            try:
                await self._tts.speak(speak_text, language=tts_lang)
            except Exception as e:
                logger.warning(f"TTS failed: {e}")

        # --- Step 4: OSC profiles / overlay ---
        await self._route_text_to_osc(text, 'original')
        if translated:
            await self._route_text_to_osc(translated, 'translated')

        if self._vr_overlay and self._vr_overlay.is_initialized:
            self._send_to_overlay(text, translated, 'user')

    async def _process_speaker_transcript(self, text: str, detected_language: Optional[str] = None):
        """Process a transcript from speaker capture (incoming speech)."""
        logger.debug(f"Speaker transcript [{detected_language}]: {text}")

        speaker_settings = self.settings.get('speakerCapture', {})

        # Send to frontend
        await self.broadcast(create_event(EventType.TRANSCRIPT_FINAL, {
            'text': text,
            'source': 'speaker',
            'detected_language': detected_language,
        }))

        # AI keyword check (same as user mic — keyword triggers AI, skips translation)
        if self.settings.get('ai', {}).get('enabled', False):
            if self._ai_assistant:
                query = self._ai_assistant.check_keyword(text)
                if query:
                    logger.debug(f"AI keyword detected in speaker capture, query: {query}")
                    try:
                        response = await self._fallback_manager.generate(query)
                        if response.model != 'fallback':
                            await self._handle_ai_response(response)
                        else:
                            await self.broadcast(create_event(EventType.AI_RESPONSE, {
                                'response': response.content,
                                'model': 'fallback',
                                'truncated': False,
                            }))
                    except Exception as e:
                        logger.error(f"AI query error from speaker: {e}")
                    return

        translated = None

        # Translate speaker capture TO the user's language (reverse of normal translation)
        # English video with eng→jpn pair: already user's lang, skip translation
        # Japanese song with eng→jpn pair: translate jpn→eng for the user
        if speaker_settings.get('translate', True):
            if self.settings.get('translation', {}).get('enabled', False):
                has_cloud = self._cloud_translator and self._cloud_translator.active_provider is not None
                has_free = self._free_translator is not None
                has_local = self._translator and self._translator.is_loaded
                if has_cloud or has_free or has_local:
                    try:
                        result = self._detect_and_translate_to_user(text, detected_language)
                        if result:
                            translated, _src, _tgt = result
                            logger.debug(f"Speaker translation [{_src} -> {_tgt}]: {translated}")
                    except Exception as e:
                        logger.error(f"Speaker translation error: {e}")
                        translated = None

                if translated:
                    await self.broadcast(create_event(EventType.TRANSLATION_COMPLETE, {
                        'original': text,
                        'translated': translated,
                        'source': 'speaker'
                    }))

        # Send listen text to OSC profiles
        listen_text = translated if translated else text
        await self._route_text_to_osc(listen_text, 'listen')

        # Show on VR overlay if enabled
        if self._vr_overlay and self._vr_overlay.is_initialized:
            overlay_settings = self.settings.get('vrOverlay', {})
            show_listen = overlay_settings.get('showListenText', True)
            if show_listen:
                self._send_to_overlay(text, translated, 'speaker')

    def _audio_processing_loop(self):
        """Background thread for processing microphone audio."""
        logger.debug("Audio processing loop started")
        chunk_count = 0
        has_manager = self._audio_manager is not None
        has_stt = self._stt is not None
        stt_loaded = self._stt.is_loaded if self._stt else False
        logger.debug(f"[audio-loop] audio_manager={has_manager}, stt={has_stt}, stt_loaded={stt_loaded}")

        while self._should_process:
            if self._audio_manager and self._stt:
                chunk = self._audio_manager.get_audio_chunk(timeout=0.1)
                if chunk is not None:
                    chunk_count += 1
                    if chunk_count <= 3 or chunk_count % 50 == 0:
                        logger.debug(f"[audio-loop] Feeding chunk #{chunk_count} to STT (len={len(chunk)}, stt_loaded={self._stt.is_loaded})")
                    self._stt.process_audio_chunk(chunk)

        logger.debug(f"Audio processing loop stopped (processed {chunk_count} chunks)")

    def _speaker_processing_loop(self):
        """Background thread for processing speaker audio."""
        logger.debug("Speaker processing loop started")

        while self._should_process_speaker:
            if self._speaker_capture and self._speaker_stt:
                chunk = self._speaker_capture.get_audio_chunk(timeout=0.1)
                if chunk is not None:
                    self._speaker_stt.process_audio_chunk(chunk)

        logger.debug("Speaker processing loop stopped")

    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information for display."""
        info: Dict[str, Any] = {
            'available': getattr(self, 'cuda_available', False),
            'name': None,
            'vram_total_mb': 0,
            'vram_used_mb': 0,
            'vram_free_mb': 0,
        }

        # In frozen exe, check if CUDA torch is installed in venv (dist-info check)
        if getattr(sys, 'frozen', False) and not info['available']:
            try:
                from utils.package_manager import _get_venv_package_version
                torch_ver = _get_venv_package_version('torch')
                if torch_ver and 'cu' in torch_ver:
                    info['available'] = True
                    info['name'] = 'NVIDIA GPU (CUDA torch installed)'
            except Exception:
                pass

        try:
            if 'torch' not in sys.modules and getattr(sys, 'frozen', False):
                raise ImportError("skip torch in frozen exe")
            import torch
            if torch.cuda.is_available():
                info['available'] = True
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
            self._translator_load_failed = False
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
        logger.info(f"[update_settings] keys={list(settings.keys())}")

        # Log translation settings in detail
        if 'translation' in settings:
            t = settings['translation']
            pairs = t.get('language_pairs', [])
            idx = t.get('active_pair_index', '?')
            logger.info(f"[update_settings] translation: active_pair_index={idx}, pairs={pairs}")

        # Track old device setting before merge
        old_device = self.settings.get('stt', {}).get('device', 'auto')

        # Deep merge settings
        for key, value in settings.items():
            if key in self.settings and isinstance(self.settings[key], dict) and isinstance(value, dict):
                self.settings[key].update(value)
            else:
                self.settings[key] = value

        # Log effective translation state after merge
        if 'translation' in settings:
            t = self.settings.get('translation', {})
            pairs = t.get('language_pairs', [])
            idx = t.get('active_pair_index', '?')
            active = pairs[idx] if isinstance(idx, int) and idx < len(pairs) else 'NONE'
            logger.info(f"[update_settings] EFFECTIVE translation: active_pair_index={idx}, active_pair={active}, total_pairs={len(pairs)}")

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
            if 'enableNoiseSuppression' in audio_settings:
                # Enable/disable noise gate (0.005 threshold when on, 0 when off)
                enabled = audio_settings['enableNoiseSuppression']
                self._audio_manager.noise_gate_threshold = 0.005 if enabled else 0.0
                logger.info(f"[audio] Noise gate {'enabled (0.005)' if enabled else 'disabled'}")

        # Apply TTS settings
        if self._tts and 'tts' in settings:
            tts_settings = settings['tts']
            if 'engine' in tts_settings:
                requested = tts_settings['engine']
                if not self._tts.set_engine(requested):
                    # Requested engine not available, prefer edge (always online)
                    if requested != 'edge' and self._tts.set_engine('edge'):
                        actual = 'edge'
                    else:
                        actual = self._tts.get_current_engine()
                    logger.warning(
                        f"TTS engine '{requested}' not available, using '{actual}'"
                    )
                    self.settings['tts']['engine'] = actual
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

            # Auto-start/stop VOICEVOX engine on engine switch
            new_engine = tts_settings.get('engine')
            if new_engine == 'voicevox':
                mgr = self._get_voicevox_manager()
                if mgr.get_install_status()['installed'] and not mgr.is_engine_running():
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._auto_start_voicevox(), self._loop
                        )
            elif new_engine and new_engine != 'voicevox':
                if self._voicevox_manager and self._voicevox_manager.is_engine_running():
                    self._voicevox_manager.stop_engine()

        # Apply AI settings
        if self._ai_assistant and 'ai' in settings:
            ai_settings = settings['ai']
            if 'keyword' in ai_settings:
                self._ai_assistant.set_keyword(ai_settings['keyword'])
            if 'provider' in ai_settings:
                self._ai_assistant.set_provider(ai_settings['provider'])
            if 'max_response_length' in ai_settings:
                self._ai_assistant.update_config(max_response_length=ai_settings['max_response_length'])

        # Apply output profiles (convert camelCase from frontend to snake_case)
        if 'output_profiles' in settings:
            camel_to_snake = {
                'audioOutputDeviceId': 'audio_output_device_id',
                'sendTtsAudio': 'send_tts_audio',
                'sendRvcAudio': 'send_rvc_audio',
                'oscEnabled': 'osc_enabled',
                'oscIP': 'osc_ip',
                'oscPort': 'osc_port',
                'sendOriginalText': 'send_original_text',
                'sendTranslatedText': 'send_translated_text',
                'sendAiResponses': 'send_ai_responses',
                'sendListenText': 'send_listen_text',
            }
            converted = []
            for p in settings['output_profiles']:
                cp = {}
                for k, v in p.items():
                    cp[camel_to_snake.get(k, k)] = v
                converted.append(cp)
            self.settings['output_profiles'] = converted
            self._sync_osc_clients()
            self._sync_tts_output_devices()

        # Apply VRChat settings (legacy)
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

            # Reset translator load failure flag when provider or model changes
            if 'provider' in translation_settings or 'model' in translation_settings:
                self._translator_load_failed = False

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
                    # Check if translator needs to be loaded (skip if previous load failed)
                    if (self._translator is None or not self._translator.is_loaded) and not self._translator_load_failed:
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
                                self._translator_load_failed = True
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
                            self._translator_load_failed = True
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

                    # Late-init VR OCR overlay if VR just became available
                    if self._vr_ocr_overlay and not self._vr_ocr_overlay.is_initialized:
                        if self._vr_ocr_overlay.initialize(self._vr_overlay._openvr):
                            self._vr_ocr_overlay.on_capture_triggered = self._on_vr_ocr_capture
                            self._vr_ocr_overlay.on_toggle_region = self._on_vr_ocr_region_toggle
                            self._vr_ocr_overlay.on_region_changed = self._on_vr_ocr_region_changed
                            self._vr_ocr_overlay.start_event_polling()
                            ocr_s = self.settings.get('ocr', {})
                            self._vr_ocr_overlay.update_settings(ocr_s)
                            if ocr_s.get('enabled', False):
                                self._vr_ocr_overlay.set_enabled(True)
                            logger.debug("VR OCR overlay late-initialized")

        # Apply OCR settings
        if 'ocr' in settings:
            ocr_settings = settings['ocr']
            logger.info(f"[update_settings] OCR: {ocr_settings}")
            if self._ocr_engine:
                self._ocr_engine.update_settings(ocr_settings)

                # Handle enable/disable
                if 'enabled' in ocr_settings:
                    if ocr_settings['enabled']:
                        # Initialize OCR if languages or device changed
                        if 'languages' in ocr_settings or 'device' in ocr_settings:
                            if self._loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.ocr_initialize(),
                                    self._loop
                                )
                        # Start auto mode if configured
                        mode = self.settings.get('ocr', {}).get('mode', 'manual')
                        if mode == 'automatic' and self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self.ocr_start_auto(),
                                self._loop
                            )
                    else:
                        self.ocr_stop_auto()

                # Handle mode changes
                if 'mode' in ocr_settings:
                    enabled = self.settings.get('ocr', {}).get('enabled', False)
                    if enabled:
                        if ocr_settings['mode'] == 'automatic':
                            if self._loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.ocr_start_auto(),
                                    self._loop
                                )
                        else:
                            self.ocr_stop_auto()

            # Forward OCR settings to VR OCR overlay
            if self._vr_ocr_overlay and self._vr_ocr_overlay.is_initialized:
                self._vr_ocr_overlay.update_settings(ocr_settings)
                if 'enabled' in ocr_settings:
                    self._vr_ocr_overlay.set_enabled(ocr_settings['enabled'])

        # Apply RVC settings
        if 'rvc' in settings:
            rvc_settings = settings['rvc']
            rvc = self._tts.get_rvc() if self._tts else None
            if rvc:
                if 'enabled' in rvc_settings:
                    rvc.enable(rvc_settings['enabled'])
                # Update conversion parameters
                param_keys = ['f0_up_key', 'index_rate', 'filter_radius',
                              'rms_mix_rate', 'protect', 'resample_sr', 'volume_envelope']
                params = {k: rvc_settings[k] for k in param_keys if k in rvc_settings}
                if params:
                    rvc.set_params(**params)

        logger.debug(f"Settings updated: {list(settings.keys())}")

    async def start_listening(self):
        """Start listening for audio input."""
        if self.listening:
            logger.debug("[start_listening] Already listening, skipping")
            return

        # Ensure STT model is loaded
        if not self._stt or not self._stt.is_loaded:
            model = self.settings.get('stt', {}).get('model', 'base')
            device = self.settings.get('stt', {}).get('device', 'auto')
            logger.debug(f"[start_listening] STT not loaded, loading model='{model}' device='{device}'")
            await self.load_model('stt', model)
        else:
            logger.debug(f"[start_listening] STT already loaded: {self._stt.model_name}")

        # Set STT to auto-detect language for multi-pair routing
        if self._stt:
            self._stt.language = None  # Auto-detect for multi-language pair support
            logger.debug(f"[start_listening] STT language set to auto-detect (multi-pair mode)")

        # Verify STT is actually loaded after load attempt
        stt_loaded = self._stt.is_loaded if self._stt else False
        logger.debug(f"[start_listening] After load: stt={self._stt is not None}, is_loaded={stt_loaded}, callback={self._stt.on_final_transcript is not None if self._stt else 'N/A'}")

        if not stt_loaded:
            logger.error("[start_listening] STT model failed to load — aborting listen")
            return

        # Stop mic test if active (it holds the mic stream open)
        if self._mic_testing:
            await self.stop_mic_test()

        # Start audio capture
        if self._audio_manager:
            device_id = self.settings.get('audio', {}).get('input_device')
            logger.debug(f"[start_listening] Starting microphone capture (device_id={device_id})")
            self._audio_manager.start_microphone(device_id)
        else:
            logger.error("[start_listening] No audio manager!")

        # Start processing thread
        self._should_process = True
        self._process_thread = threading.Thread(target=self._audio_processing_loop, daemon=True)
        self._process_thread.start()

        self.listening = True
        logger.debug("[start_listening] Started listening successfully")
        await self.broadcast(create_event(EventType.LISTENING_STARTED, {}))

    async def stop_listening(self):
        """Stop listening for audio input."""
        logger.debug("[stop_listening] Called, currently listening=%s", self.listening)
        if not self.listening:
            return

        # Stop processing thread
        self._should_process = False
        if self._process_thread:
            self._process_thread.join(timeout=2)
            self._process_thread = None

        # Stop audio capture (only if mic RVC is not active)
        if self._audio_manager:
            mic_rvc_active = self._mic_rvc and self._mic_rvc.is_running
            if not mic_rvc_active:
                self._audio_manager.stop_microphone()

        self.listening = False
        logger.debug("Stopped listening")
        await self.broadcast(create_event(EventType.LISTENING_STOPPED, {}))

    async def start_mic_test(self, device_id: int = None):
        """Start microphone test - captures audio and sends levels without loading STT."""
        logger.debug(f"[start_mic_test] Called, device_id={device_id}, already_testing={self._mic_testing}")
        if self._mic_testing:
            return

        if self._audio_manager:
            # Use specified device or current setting
            if device_id is None:
                device_id = self.settings.get('audio', {}).get('input_device')
            self._audio_manager.start_microphone(device_id)
            self._mic_testing = True
            logger.debug(f"Started microphone test (device: {device_id or 'default'})")

    async def stop_mic_test(self):
        """Stop microphone test."""
        logger.debug(f"[stop_mic_test] Called, currently_testing={self._mic_testing}")
        if not self._mic_testing:
            return

        if self._audio_manager:
            self._audio_manager.stop_microphone()
            self._mic_testing = False
            logger.debug("Stopped microphone test")

    async def test_speaker(self, device_id: int = None):
        """Play a short test tone on the specified output device."""
        logger.debug(f"[test_speaker] Called, device_id={device_id}")
        import asyncio
        try:
            import sounddevice as sd

            # Query device's default sample rate instead of hardcoding
            sample_rate = None
            try:
                dev_info = sd.query_devices(device_id, 'output')
                sample_rate = int(dev_info['default_samplerate'])
            except Exception:
                pass
            if not sample_rate:
                # Fallback through common rates
                for sr in [48000, 44100, 22050, 16000]:
                    try:
                        sd.check_output_settings(device=device_id, samplerate=sr)
                        sample_rate = sr
                        break
                    except Exception:
                        continue
            if not sample_rate:
                sample_rate = 44100  # last resort

            duration = 0.5  # seconds
            freq = 440  # A4 note

            # Generate a sine wave with fade in/out
            t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
            tone = 0.3 * np.sin(2 * np.pi * freq * t)
            # Fade in/out to avoid clicks
            fade_len = int(sample_rate * 0.05)
            tone[:fade_len] *= np.linspace(0, 1, fade_len)
            tone[-fade_len:] *= np.linspace(1, 0, fade_len)

            def play_sync():
                sd.play(tone, samplerate=sample_rate, device=device_id)
                sd.wait()

            await asyncio.get_event_loop().run_in_executor(None, play_sync)
            logger.debug(f"Speaker test completed on device {device_id} at {sample_rate}Hz")
        except Exception as e:
            logger.error(f"Speaker test failed: {e}")
            await self.broadcast(create_event(EventType.ERROR, {
                'message': f'Speaker test failed: {str(e)}'
            }))

    async def test_loopback(self, device_id: int = None):
        """Test loopback capture by playing a tone on the device and capturing it."""
        logger.info(f"[test_loopback] Testing loopback capture on device {device_id}")
        try:
            import sounddevice as sd

            # Resolve device — use speaker capture device from settings if not specified
            if device_id is None:
                device_id = self.settings.get('audio', {}).get('speaker_capture_device')

            # Play a tone on the default output, then try to capture via loopback
            # For now, just verify the loopback device can be opened
            if self._speaker_capture and self._speaker_capture.is_available():
                # Quick test: start and stop capture
                success = self._speaker_capture.start_capture(device_id)
                if success:
                    logger.info(f"[test_loopback] Loopback capture started successfully on device {device_id}")
                    await self.broadcast({'type': 'loopback_test_result', 'payload': {'success': True, 'message': 'Loopback capture working!'}})
                    # Capture for 1 second to verify
                    import time
                    await asyncio.get_event_loop().run_in_executor(None, lambda: time.sleep(1))
                    self._speaker_capture.stop_capture()
                    logger.info("[test_loopback] Loopback test passed")
                else:
                    logger.error("[test_loopback] Failed to start loopback capture")
                    await self.broadcast({'type': 'loopback_test_result', 'payload': {'success': False, 'message': 'Loopback capture failed to start'}})
                    await self.broadcast(create_event(EventType.ERROR, {
                        'message': 'Loopback capture failed to start. Check your audio device.'
                    }))
            else:
                logger.error("[test_loopback] Speaker capture not available")
                await self.broadcast({'type': 'loopback_test_result', 'payload': {'success': False, 'message': 'WASAPI loopback not available'}})
                await self.broadcast(create_event(EventType.ERROR, {
                    'message': 'Speaker capture (WASAPI loopback) not available'
                }))
        except Exception as e:
            logger.error(f"[test_loopback] Failed: {e}")
            await self.broadcast(create_event(EventType.ERROR, {
                'message': f'Loopback test failed: {str(e)}'
            }))

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
        logger.debug("Started speaker capture")
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
        logger.debug("Stopped speaker capture")
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
                logger.debug(f"[stt] Loading STT model: {model_id} on device: {device}")

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
                self._translator_load_failed = False
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

        logger.debug(f"Speaking: {text[:50]}...")

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
        logger.info(f"[ai_query] query='{query[:80]}' assistant={self._ai_assistant is not None} fallback={self._fallback_manager is not None}")

        if not self._ai_assistant:
            logger.warning("[ai_query] AI assistant not initialized")
            return "AI assistant not available"

        try:
            candidates = self._fallback_manager._get_candidates()
            logger.info(f"[ai_query] available providers: {candidates}")
            response = await self._fallback_manager.generate(query)
            logger.info(f"[ai_query] response model={response.model}, content='{response.content[:80]}', truncated={response.truncated}")
            return response.content

        except Exception as e:
            import traceback
            logger.error(f"[ai_query] error: {e}\n{traceback.format_exc()}")
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

        # Disconnect all OSC clients
        for client in self._osc_clients.values():
            client.disconnect()
        self._osc_clients.clear()

        if self._vr_ocr_overlay:
            self._vr_ocr_overlay.shutdown()

        if self._vr_overlay:
            self._vr_overlay.shutdown()

        if self._voicevox_manager:
            self._voicevox_manager.stop_engine()

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

    def _get_output_profiles(self) -> list:
        """Get output profiles from settings, falling back to legacy VRChat config."""
        profiles = self.settings.get('output_profiles', [])
        if profiles:
            return profiles
        # Legacy fallback: build a single profile from VRChat settings
        vrchat = self.settings.get('vrchat', {})
        return [{
            'id': 'default',
            'name': 'Profile 1',
            'audio_output_device_id': self.settings.get('tts', {}).get('output_device'),
            'send_tts_audio': True,
            'send_rvc_audio': True,
            'osc_enabled': vrchat.get('osc_enabled', True),
            'osc_ip': vrchat.get('osc_ip', '127.0.0.1'),
            'osc_port': vrchat.get('osc_port', 9000),
            'send_original_text': True,
            'send_translated_text': True,
            'send_ai_responses': True,
            'send_listen_text': True,
        }]

    def _sync_osc_clients(self):
        """Sync OSC clients to match current output profiles."""
        profiles = self._get_output_profiles()
        active_ids = set()

        for profile in profiles:
            pid = profile.get('id', 'default')
            active_ids.add(pid)

            if not profile.get('osc_enabled', False):
                # Disconnect if disabled
                if pid in self._osc_clients:
                    self._osc_clients[pid].disconnect()
                    del self._osc_clients[pid]
                continue

            ip = profile.get('osc_ip', '127.0.0.1')
            port = profile.get('osc_port', 9000)

            if pid in self._osc_clients:
                client = self._osc_clients[pid]
                # Reconnect if IP/port changed
                if client._ip != ip or client._port != port:
                    client.disconnect()
                    client.connect(ip, port)
            else:
                client = VRChatOSC()
                client.connect(ip, port)
                self._osc_clients[pid] = client

        # Remove clients for deleted profiles
        for pid in list(self._osc_clients.keys()):
            if pid not in active_ids:
                self._osc_clients[pid].disconnect()
                del self._osc_clients[pid]

        # Keep legacy _vrchat pointing to default profile's client
        self._vrchat = self._osc_clients.get('default')

    def _sync_tts_output_devices(self):
        """Sync TTS manager output devices from profiles."""
        if not self._tts:
            return
        profiles = self._get_output_profiles()

        primary_device = None
        extra_devices = []

        for i, profile in enumerate(profiles):
            if not (profile.get('send_tts_audio') or profile.get('send_rvc_audio')):
                continue
            dev_id = profile.get('audio_output_device_id')
            if dev_id is not None:
                try:
                    dev_id = int(dev_id)
                except (ValueError, TypeError):
                    dev_id = None

            if i == 0:
                primary_device = dev_id
            elif dev_id is not None:
                extra_devices.append(dev_id)

        self._tts.set_output_device(primary_device)
        self._tts.set_extra_output_devices(extra_devices)

    async def _route_text_to_osc(self, text: str, text_type: str):
        """Route text to OSC clients based on profile settings.

        Args:
            text: Text to send
            text_type: One of 'original', 'translated', 'ai', 'listen'
        """
        profiles = self._get_output_profiles()
        toggle_map = {
            'original': 'send_original_text',
            'translated': 'send_translated_text',
            'ai': 'send_ai_responses',
            'listen': 'send_listen_text',
        }
        toggle_key = toggle_map.get(text_type)
        if not toggle_key:
            return

        for profile in profiles:
            pid = profile.get('id', 'default')
            if not profile.get('osc_enabled', False):
                continue
            if not profile.get(toggle_key, False):
                continue
            client = self._osc_clients.get(pid)
            if client and client.is_connected:
                await client.send_text(text)

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

    def get_llm_status(self) -> Dict[str, Any]:
        """Get current local LLM status."""
        if not self._ai_assistant:
            return {'loaded': False, 'model': None, 'model_path': None}
        return self._ai_assistant.get_llm_status()

    def unload_llm(self) -> bool:
        """Unload the current local LLM model."""
        if not self._ai_assistant:
            return False
        try:
            from ai.assistant.local_llm import LocalLLMProvider
            provider = self._ai_assistant._providers.get('local')
            if isinstance(provider, LocalLLMProvider):
                provider.unload_model()
                logger.info("[llm] Local LLM unloaded")
                return True
            return False
        except Exception as e:
            logger.error(f"[llm] Failed to unload LLM: {e}")
            return False

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
    def _send_to_overlay(self, original: str, translated: Optional[str], message_type: str):
        """Send text to VR overlay respecting showOriginalText/showTranslatedText toggles.
        Stacks both when both toggles are on."""
        overlay_settings = self.settings.get('vrOverlay', {})
        show_original = overlay_settings.get('showOriginalText', True)
        show_translated = overlay_settings.get('showTranslatedText', True)
        parts = []
        if show_original:
            parts.append(original)
        if translated and show_translated and translated != original:
            parts.append(translated)
        if parts:
            self._vr_overlay.show_text('\n'.join(parts), message_type=message_type)

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

    # RVC Voice Conversion methods

    def _wire_rvc_failed_callback(self):
        """Wire TTSManager's on_rvc_failed to broadcast rvc_conversion_failed event."""
        def on_rvc_failed(error_msg: str):
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(EventType.RVC_CONVERSION_FAILED, {
                        'error': error_msg,
                        'message': 'Voice conversion failed — playing original audio.'
                    })),
                    self._loop
                )
        if self._tts:
            self._tts.set_on_rvc_failed(on_rvc_failed)

    def _init_rvc_with_callbacks(self):
        """Initialize RVC post-processor with event callbacks wired."""
        if not self._tts:
            return None
        rvc = self._tts.init_rvc()

        # Wire progress callback
        def on_progress(stage: str, pct: float):
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(EventType.RVC_MODEL_LOADING, {
                        'stage': stage,
                        'progress': pct,
                    })),
                    self._loop
                )
        rvc.on_progress = on_progress

        # Wire status callback
        def on_status(event: str, data: dict):
            if event == 'base_models_needed':
                evt = EventType.RVC_BASE_MODELS_NEEDED
            elif event == 'model_loaded':
                evt = EventType.RVC_MODEL_LOADED
            elif event == 'unloaded':
                evt = EventType.RVC_UNLOADED
            else:
                evt = EventType.RVC_STATUS
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(evt, data)),
                    self._loop
                )
        rvc.on_status = on_status

        # Wire failure callback
        self._wire_rvc_failed_callback()

        return rvc

    async def rvc_scan_models(self, directory: Optional[str] = None):
        """Scan for RVC voice models."""
        rvc = self._init_rvc_with_callbacks()
        if not rvc:
            return []
        scan_dir = directory or self.settings.get('rvc', {}).get('models_directory')
        models = rvc.scan_models(scan_dir)
        import time as _time
        await self.broadcast({
            'type': 'rvc_models_list',
            'payload': {'models': models[:20]},
            'timestamp': _time.time(),
        })
        return models

    async def rvc_load_model(self, model_path: str, index_path: Optional[str] = None):
        """Load an RVC voice model. Auto-downloads base models if missing."""
        logger.info(f"[rvc] rvc_load_model called: path={model_path}, index={index_path}")
        # Stop mic RVC if active — avoids stream errors during model swap
        if self._mic_rvc and self._mic_rvc.is_running:
            logger.info("[rvc] Stopping mic RVC before model switch")
            await self.mic_rvc_stop()
        rvc = self._init_rvc_with_callbacks()
        if not rvc:
            logger.error("[rvc] TTS manager not available")
            await self.broadcast(create_event(EventType.RVC_MODEL_ERROR, {
                'error': 'TTS manager not available'
            }))
            return False

        # Save pending path so download-then-retry can find it
        self.settings['rvc']['model_path'] = model_path
        self.settings['rvc']['index_path'] = index_path

        # Auto-download base models if missing (no modal needed)
        check = rvc._check_base_models()
        if check['needs_download']:
            logger.info(f"[rvc] Base models missing (hubert={check['hubert_exists']}, rmvpe={check['rmvpe_exists']}), auto-downloading...")
            await self.broadcast(create_event(EventType.RVC_MODEL_LOADING, {
                'stage': 'Downloading base models (HuBERT + RMVPE)...',
                'progress': 0.0,
            }))
            dl_success = await self.rvc_download_base_models()
            if not dl_success:
                logger.error("[rvc] Base models download failed")
                self.settings['rvc']['model_path'] = None
                self.settings['rvc']['index_path'] = None
                await self.broadcast(create_event(EventType.RVC_MODEL_ERROR, {
                    'error': 'Failed to download base models (HuBERT + RMVPE)',
                }))
                return False
            logger.info("[rvc] Base models downloaded successfully, proceeding to load model")

        success = await rvc.load_model(model_path, index_path)
        if success:
            logger.info(f"[rvc] Model loaded successfully: {model_path}")
            rvc.enable(True)
            self.settings['rvc']['enabled'] = True
        else:
            logger.error(f"[rvc] Failed to load model: {model_path}")
            # Clear pending path on real failure
            self.settings['rvc']['model_path'] = None
            self.settings['rvc']['index_path'] = None
            await self.broadcast(create_event(EventType.RVC_MODEL_ERROR, {
                'error': 'Failed to load model',
            }))
        return success

    async def rvc_download_base_models(self):
        """Download RVC base models (HuBERT + RMVPE) after user confirmation."""
        rvc = self._init_rvc_with_callbacks()
        if not rvc:
            return False

        # Wire download progress
        original_progress = rvc.on_progress
        def download_progress(stage: str, pct: float):
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(EventType.RVC_DOWNLOAD_PROGRESS, {
                        'file': stage,
                        'progress': pct,
                        'total_mb': 400,
                    })),
                    self._loop
                )
        rvc.on_progress = download_progress

        success = await rvc.download_base_models()

        # Restore original progress callback
        rvc.on_progress = original_progress

        if success:
            # Retry pending model load if there was one
            pending_model = self.settings.get('rvc', {}).get('model_path')
            if pending_model:
                await self.rvc_load_model(pending_model)

        return success

    async def rvc_enable(self, enabled: bool):
        """Enable or disable RVC."""
        logger.debug(f"[rvc_enable] enabled={enabled}")
        rvc = self._tts.get_rvc() if self._tts else None
        if rvc:
            rvc.enable(enabled)
            self.settings['rvc']['enabled'] = enabled
            await self.broadcast(create_event(EventType.RVC_STATUS, rvc.get_status()))

    async def rvc_set_params(self, **params):
        """Update RVC conversion parameters."""
        rvc = self._tts.get_rvc() if self._tts else None
        if rvc:
            rvc.set_params(**params)
            # Update settings
            for key, value in params.items():
                if key in self.settings.get('rvc', {}):
                    self.settings['rvc'][key] = value
            await self.broadcast(create_event(EventType.RVC_PARAMS_UPDATED, rvc.get_status().get('params', {})))

    async def rvc_unload(self):
        """Unload RVC model."""
        rvc = self._tts.get_rvc() if self._tts else None
        if rvc:
            rvc.unload()
            self.settings['rvc']['enabled'] = False
            self.settings['rvc']['model_path'] = None
            await self.broadcast(create_event(EventType.RVC_UNLOADED, {}))

    async def rvc_get_status(self):
        """Get current RVC status."""
        rvc = self._tts.get_rvc() if self._tts else None
        status = rvc.get_status() if rvc else {
            'enabled': False, 'loaded': False, 'model_name': None, 'memory_mb': 0
        }
        await self.broadcast(create_event(EventType.RVC_STATUS, status))

        # Also send available devices (avoids race condition with separate message)
        try:
            from ai.rvc.config import get_available_devices
            devices = get_available_devices()
            await self.broadcast({
                'type': 'rvc_available_devices',
                'payload': {'devices': devices},
            })
        except Exception as e:
            logger.error(f"Failed to get available RVC devices: {e}")

        return status

    async def rvc_test_voice(self):
        """Record 3 seconds from mic, convert through RVC, send back for playback."""
        logger.info("[rvc_test_voice] Starting RVC voice test")
        rvc = self._tts.get_rvc() if self._tts else None
        if not rvc:
            logger.error("[rvc_test_voice] No RVC instance (TTS not initialized?)")
            await self.broadcast(create_event(EventType.RVC_TEST_VOICE_ERROR, {
                'error': 'RVC is not available (TTS not initialized)'
            }))
            return
        if not rvc.is_enabled():
            logger.error(f"[rvc_test_voice] RVC not enabled. Status: {rvc.get_status()}")
            await self.broadcast(create_event(EventType.RVC_TEST_VOICE_ERROR, {
                'error': 'RVC is not enabled or no model loaded'
            }))
            return

        try:
            import sounddevice as sd
            import base64
            import io
            import wave
            from ai.tts.base import TTSResult

            sample_rate = 16000
            duration = 3
            input_device = self.settings.get('audio', {}).get('input_device', None)
            logger.info(f"[rvc_test_voice] Recording {duration}s from device={input_device}, sr={sample_rate}")

            # Record in executor
            def record_sync():
                recording = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype='float32',
                    device=input_device,
                )
                sd.wait()
                return recording.flatten()

            audio_data = await asyncio.get_event_loop().run_in_executor(None, record_sync)

            # Create TTSResult from recording
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                int_data = (audio_data * 32767).astype(np.int16)
                wf.writeframes(int_data.tobytes())

            tts_result = TTSResult(
                audio_data=wav_buffer.getvalue(),
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
            )

            # Process through RVC
            converted = await rvc.process(tts_result)

            # Encode as base64 WAV
            audio_b64 = base64.b64encode(converted.audio_data).decode('utf-8')

            await self.broadcast(create_event(EventType.RVC_TEST_VOICE_READY, {
                'audio_base64': audio_b64,
                'sample_rate': converted.sample_rate,
            }))

        except Exception as e:
            logger.error(f"Test voice failed: {e}")
            await self.broadcast(create_event(EventType.RVC_TEST_VOICE_ERROR, {
                'error': str(e),
            }))

    # ── Real-Time Mic RVC ─────────────────────────────────────────────

    async def mic_rvc_start(self, output_device_id: Optional[int] = None):
        """Start real-time mic voice conversion."""
        rvc = self._tts.get_rvc() if self._tts else None
        if not rvc or not rvc._pipeline:
            await self.broadcast(create_event(EventType.RVC_MIC_ERROR, {
                'error': 'Load an RVC voice model first'
            }))
            return

        from ai.rvc.mic_rvc import MicRVCProcessor

        # Always recreate MicRVCProcessor — model switch changes _tgt_sr
        # and keeping the old instance causes sample rate mismatch errors
        if self._mic_rvc is not None:
            logger.debug("[mic_rvc] Recreating MicRVCProcessor for new model/config")
            if self._mic_rvc.is_running:
                self._mic_rvc.stop()

        self._mic_rvc = MicRVCProcessor(rvc)

        def _on_mic_rvc_error(msg):
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(create_event(EventType.RVC_MIC_ERROR, {'error': msg})),
                    self._loop
                )

        self._mic_rvc.on_error = _on_mic_rvc_error

        # MicRVCProcessor now uses its own sd.Stream for mic capture
        # (no AudioManager wiring needed)
        input_device_id = self.settings.get('audio', {}).get('input_device')
        self._mic_rvc.start(output_device_id, input_device_id=input_device_id)
        await self.broadcast(create_event(EventType.RVC_MIC_STARTED, {}))

    async def mic_rvc_stop(self):
        """Stop real-time mic voice conversion."""
        if self._mic_rvc:
            self._mic_rvc.stop()

        if self._audio_manager:
            self._audio_manager.on_mic_rvc_data = None

            # Only stop mic if STT listening is not active
            if not self.listening and self._audio_manager.is_recording:
                self._audio_manager.stop_microphone()

        await self.broadcast(create_event(EventType.RVC_MIC_STOPPED, {}))

    async def mic_rvc_set_output_device(self, device_id: Optional[int]):
        """Change the output device for mic RVC."""
        if self._mic_rvc:
            self._mic_rvc.set_output_device(device_id)

    async def rvc_set_device(self, device_str: str):
        """Switch RVC compute device (CPU/GPU).

        Auto-detects DirectML when 'cuda' is requested but not available.
        The frontend sends 'cuda' for any GPU; we translate to DirectML
        when that's what's actually installed (AMD/Intel GPUs).
        """
        import torch

        # Auto-detect: if 'cuda' requested but unavailable, try DirectML
        if device_str == 'cuda' and not torch.cuda.is_available():
            logger.warning(f"CUDA not available for RVC — torch.version.cuda={getattr(torch.version, 'cuda', 'None')}, "
                           f"torch.__version__={torch.__version__}")
            try:
                import torch_directml
                device_str = 'directml'
                logger.debug("CUDA not available, using DirectML instead")
            except ImportError:
                pass  # Will fail in move_to_device and show error

        rvc = self._tts.get_rvc() if self._tts else None
        if not rvc:
            return

        was_running = self._mic_rvc and self._mic_rvc.is_running
        if was_running:
            self._mic_rvc.stop()

        success = rvc.move_to_device(device_str)
        if not success:
            # Device change failed (e.g. CUDA not available) — notify frontend
            await self.broadcast(create_event(EventType.ERROR, {
                'message': f'Cannot use {device_str.upper()}: not available on this system',
                'source': 'rvc',
            }))
            # Send current device status back so frontend toggle reverts
            await self.broadcast(create_event(EventType.RVC_STATUS, rvc.get_status()))
            # Restart mic if it was running (still on old device)
            if was_running:
                self._mic_rvc.start(self._mic_rvc._output_device_id)
            return

        # Adjust block duration based on device
        if self._mic_rvc:
            if device_str == 'cpu':
                self._mic_rvc.set_buffer_duration(0.5)  # 0.5s blocks on CPU
            else:
                self._mic_rvc.set_buffer_duration(0.25)  # 0.25s blocks on GPU

        if was_running:
            self._mic_rvc.start(self._mic_rvc._output_device_id)

        await self.broadcast(create_event(EventType.RVC_STATUS, rvc.get_status()))

    # ── VOICEVOX Engine Management ──────────────────────────────────────

    def _get_voicevox_manager(self):
        """Lazily initialize the VOICEVOX Engine manager."""
        if self._voicevox_manager is None:
            from utils.voicevox_setup import VoicevoxEngineManager

            def on_progress(stage: str, pct: float, detail: str):
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast(create_event(EventType.VOICEVOX_SETUP_PROGRESS, {
                            'stage': stage,
                            'progress': pct,
                            'detail': detail,
                        })),
                        self._loop
                    )

            self._voicevox_manager = VoicevoxEngineManager(
                on_progress=on_progress,
            )
        return self._voicevox_manager

    async def voicevox_check_install(self) -> Dict:
        """Check VOICEVOX Engine installation status (fast, no network)."""
        mgr = self._get_voicevox_manager()
        status = mgr.get_install_status()
        # Skip GitHub API call here — it's slow (15s timeout) and only needed at install time.
        # The download handler fetches release info when actually needed.
        status['latest_version'] = None
        status['available_builds'] = []
        return status

    async def voicevox_download_engine(self, build_type: str = 'directml'):
        """Download and install VOICEVOX Engine, then auto-start."""
        mgr = self._get_voicevox_manager()
        success = await mgr.download_and_install(build_type)
        if success:
            # Notify frontend that VOICEVOX is now installed
            await self.broadcast(create_event(EventType.VOICEVOX_SETUP_STATUS, {
                'installed': True,
            }))
            started = await mgr.start_engine()
            if started and self._tts:
                voicevox = self._tts._engines.get('voicevox')
                if voicevox:
                    voicevox.engine_url = f'http://127.0.0.1:{50021}'
                await self.broadcast(create_event(EventType.VOICEVOX_ENGINE_STATUS, {
                    'running': True,
                    'port': 50021,
                    'pid': mgr._process.pid if mgr._process else None,
                    'error': None,
                }))

    def voicevox_cancel_download(self):
        """Cancel in-progress VOICEVOX download."""
        if self._voicevox_manager:
            self._voicevox_manager.cancel()

    async def voicevox_start_engine(self) -> bool:
        """Start the local VOICEVOX Engine."""
        mgr = self._get_voicevox_manager()
        success = await mgr.start_engine()
        if success and self._tts:
            voicevox = self._tts._engines.get('voicevox')
            if voicevox:
                voicevox.engine_url = f'http://127.0.0.1:{50021}'
        return success

    def voicevox_stop_engine(self):
        """Stop the local VOICEVOX Engine."""
        if self._voicevox_manager:
            self._voicevox_manager.stop_engine()

    def voicevox_uninstall_engine(self) -> bool:
        """Remove the VOICEVOX Engine installation."""
        if self._voicevox_manager:
            return self._voicevox_manager.uninstall()
        return False

    async def _auto_start_voicevox(self):
        """Auto-start VOICEVOX engine when selected as TTS engine."""
        mgr = self._get_voicevox_manager()
        try:
            success = await mgr.start_engine()
            if success and self._tts:
                voicevox = self._tts._engines.get('voicevox')
                if voicevox:
                    voicevox.engine_url = f'http://127.0.0.1:{50021}'
                await self.broadcast(create_event(EventType.VOICEVOX_ENGINE_STATUS, {
                    'running': True,
                    'port': 50021,
                    'pid': mgr._process.pid if mgr._process else None,
                    'error': None,
                }))
        except Exception as e:
            logger.error(f"Failed to auto-start VOICEVOX: {e}")

    # ── OCR Methods ──────────────────────────────────────────────────────

    def _on_ocr_complete(self, ocr_results, translations):
        """Handle OCR completion — render VR overlay + broadcast to frontend."""
        logger.info(f"[ocr] OCR complete: {len(translations)} blocks translated")

        # Render translation overlay texture and apply to VR
        if self._vr_ocr_overlay and self._vr_ocr_overlay.is_initialized:
            try:
                # Get crop region pixel size from OCR engine for texture dimensions
                crop = self._ocr_engine._crop_region if self._ocr_engine else None
                if crop:
                    # Use a reasonable render size (match capture region proportions)
                    render_w = max(256, int(crop.get('w', 0.5) * 1920))
                    render_h = max(128, int(crop.get('h', 0.15) * 1080))
                else:
                    render_w, render_h = 960, 270

                texture = render_translation_texture(
                    ocr_results, translations, (render_w, render_h)
                )
                self._vr_ocr_overlay.update_translation_texture(texture)
                logger.debug(f"[ocr] VR translation texture applied: {render_w}x{render_h}")
            except Exception as e:
                logger.error(f"[ocr] Failed to render VR translation texture: {e}")

        # Broadcast to frontend
        if self._loop:
            payload = {
                'blocks': [
                    {'original': text, 'translated': trans, 'confidence': conf}
                    for (bbox, text, conf), trans in zip(ocr_results, translations)
                ],
                'count': len(translations),
            }
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.OCR_RESULT, payload)),
                self._loop
            )

    def _on_ocr_status_change(self, status: dict):
        """Handle OCR status change — broadcast to frontend."""
        logger.debug(f"[ocr] Status change: {status}")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.OCR_STATUS, status)),
                self._loop
            )

    async def _ocr_translate_text(self, text: str) -> str:
        """Translate text using the active translation provider (for OCR).

        Uses the same translation pipeline as speech translation.
        """
        if not text or not text.strip():
            return text

        # Get active translation pair
        translation_settings = self.settings.get('translation', {})
        pairs = translation_settings.get('language_pairs', [])
        active_idx = translation_settings.get('active_pair_index', 0)

        if not pairs:
            return text

        if isinstance(active_idx, int) and active_idx < len(pairs):
            pair = pairs[active_idx]
        else:
            pair = pairs[0]

        source = pair.get('source', 'eng_Latn')
        target = pair.get('target', 'jpn_Jpan')

        # Try translation providers in order
        translated = await self._try_translate(text, source, target)
        return translated if translated else text

    async def _try_translate(self, text: str, source: str, target: str) -> Optional[str]:
        """Try translating with available providers."""
        provider = self.settings.get('translation', {}).get('provider', 'free')

        # Try local NLLB first
        if provider == 'local' and self._translator and self._translator.is_loaded:
            try:
                result = self._translator.translate(text, source, target)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"[ocr] Local translation failed: {e}")

        # Try free provider
        if self._free_translator:
            try:
                result = await self._free_translator.translate(text, source, target)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"[ocr] Free translation failed: {e}")

        # Try cloud provider
        if self._cloud_translator:
            try:
                result = await self._cloud_translator.translate(text, source, target)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"[ocr] Cloud translation failed: {e}")

        return None

    async def ocr_initialize(self, languages: list = None, device: str = None):
        """Initialize the OCR engine with languages derived from translation pairs."""
        if not self._ocr_engine:
            return False

        ocr_settings = self.settings.get('ocr', {})
        dev = device or ocr_settings.get('device', 'cpu')

        if languages:
            langs = languages
        else:
            # Derive from all translation pairs
            langs = self._get_ocr_languages_from_pairs()

        logger.info(f"[ocr] Initializing OCR: languages={langs}, device={dev}")
        return await self._ocr_engine.initialize(langs, dev)

    def _get_ocr_languages_from_pairs(self) -> list:
        """Extract OCR languages from all translation pair targets + active source."""
        translation_settings = self.settings.get('translation', {})
        pairs = translation_settings.get('language_pairs', [])

        if not pairs:
            return ['en']

        nllb_codes = set()
        for pair in pairs:
            target = pair.get('target', '')
            if target:
                nllb_codes.add(target)

        # Also add source of active pair (user speaks this language, OCR should detect it too)
        active_idx = translation_settings.get('active_pair_index', 0)
        if isinstance(active_idx, int) and active_idx < len(pairs):
            source = pairs[active_idx].get('source', '')
            if source:
                nllb_codes.add(source)

        # Convert NLLB codes to EasyOCR codes
        ocr_langs = []
        for code in nllb_codes:
            easyocr_code = NLLB_TO_EASYOCR.get(code)
            if easyocr_code and easyocr_code not in ocr_langs:
                ocr_langs.append(easyocr_code)

        logger.info(f"[ocr] Derived OCR languages from translation pairs: {ocr_langs}")
        return ocr_langs if ocr_langs else ['en']

    async def ocr_capture(self) -> Optional[dict]:
        """Trigger a manual OCR capture."""
        if not self._ocr_engine:
            logger.warning("[ocr] OCR engine not available")
            return None

        if not self._ocr_engine.is_loaded:
            # Check if easyocr is installed before trying to initialize
            try:
                import importlib
                importlib.import_module('easyocr')
            except ImportError:
                logger.warning("[ocr] EasyOCR not installed — cannot capture")
                await self.broadcast(create_event(EventType.OCR_ERROR, {
                    'error': 'OCR feature not installed. Go to Settings → Install Features to install it.'
                }))
                return None
            # Auto-initialize on first capture
            success = await self.ocr_initialize()
            if not success:
                await self.broadcast(create_event(EventType.OCR_ERROR, {
                    'error': 'Failed to load OCR model. Install the OCR feature first.'
                }))
                return None

        result = await self._ocr_engine.trigger_manual_capture()
        return result

    async def ocr_start_auto(self):
        """Start automatic OCR capture loop."""
        if not self._ocr_engine:
            return

        if not self._ocr_engine.is_loaded:
            # Check if easyocr is installed before trying to initialize
            try:
                import importlib
                importlib.import_module('easyocr')
            except ImportError:
                logger.warning("[ocr] EasyOCR not installed — cannot start auto capture")
                await self.broadcast(create_event(EventType.OCR_ERROR, {
                    'error': 'OCR feature not installed. Go to Settings → Install Features to install it.'
                }))
                return
            success = await self.ocr_initialize()
            if not success:
                await self.broadcast(create_event(EventType.OCR_ERROR, {
                    'error': 'Failed to load OCR model for auto capture.'
                }))
                return

        if self._ocr_engine._loop_task and not self._ocr_engine._loop_task.done():
            return  # Already running

        self._ocr_engine._loop_task = asyncio.create_task(
            self._ocr_engine.start_auto_loop()
        )

    def ocr_stop_auto(self):
        """Stop automatic OCR capture loop."""
        if self._ocr_engine:
            self._ocr_engine.stop_auto_loop()

    # ── VR OCR Overlay Callbacks ──────────────────────────────────────

    def _on_vr_ocr_capture(self):
        """Called when VR camera button or controller binding triggers OCR capture."""
        logger.info("[ocr] VR capture triggered")
        if self._loop:
            asyncio.run_coroutine_threadsafe(self.ocr_capture(), self._loop)

    def _on_vr_ocr_region_toggle(self, visible: bool):
        """Called when VR cyan button toggles region visibility."""
        logger.info(f"[ocr] VR region toggled: visible={visible}")
        # Update crop region from VR position → pixel fractions
        if visible and self._vr_ocr_overlay:
            crop = self._vr_ocr_overlay.get_crop_region_pixels()
            if crop and self._ocr_engine:
                self._ocr_engine._crop_region = crop
                logger.debug(f"[ocr] Crop region updated from VR: {crop}")

        # Broadcast region state to frontend
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.OCR_STATUS, {
                    'region_visible': visible,
                })),
                self._loop
            )

    def _on_vr_ocr_region_changed(self, region_pos: dict):
        """Called when VR region is moved/resized (drag in VR)."""
        logger.debug(f"[ocr] VR region changed: {region_pos}")
        # Update crop region pixels
        if self._vr_ocr_overlay:
            crop = self._vr_ocr_overlay.get_crop_region_pixels()
            if crop and self._ocr_engine:
                self._ocr_engine._crop_region = crop

        # Broadcast to frontend for canvas sync
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(create_event(EventType.OCR_STATUS, {
                    'region_updated': region_pos,
                })),
                self._loop
            )
