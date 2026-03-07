"""
VOICEVOX TTS Engine
Uses the VOICEVOX Engine REST API for high-quality Japanese neural TTS.
Requires VOICEVOX Engine running locally (http://localhost:50021).
Supports English text via automatic katakana phonetic conversion.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional

import aiohttp

from ai.tts.base import TTSEngine, TTSResult, Voice

logger = logging.getLogger('stts.tts.voicevox')

DEFAULT_ENGINE_URL = 'http://localhost:50021'

# Cache TTL: 7 days (icons/speakers rarely change)
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


class VoicevoxEngine(TTSEngine):
    """VOICEVOX TTS engine using the VOICEVOX Engine REST API."""

    def __init__(self, engine_url: str = DEFAULT_ENGINE_URL):
        super().__init__()
        self.name = "voicevox"
        self.is_online = False  # Local engine, but external process
        self._engine_url = engine_url.rstrip('/')
        self._voice = '3'  # Default: Zundamon (Normal)
        self._voices_cache: Optional[List[Voice]] = None
        self._speakers_cache: Optional[List[Dict]] = None
        self._speaker_icons: Dict[str, str] = {}  # style_id -> base64 icon
        self._connected: bool = False
        self._enable_english_phonetic: bool = True

    @property
    def engine_url(self) -> str:
        """Get the VOICEVOX engine URL."""
        return self._engine_url

    @engine_url.setter
    def engine_url(self, url: str):
        """Set the VOICEVOX engine URL and invalidate caches."""
        self._engine_url = url.rstrip('/')
        self._voices_cache = None
        self._speakers_cache = None
        self._speaker_icons = {}
        self._connected = False

    @property
    def enable_english_phonetic(self) -> bool:
        """Whether to convert English text to katakana before synthesis."""
        return self._enable_english_phonetic

    @enable_english_phonetic.setter
    def enable_english_phonetic(self, value: bool):
        self._enable_english_phonetic = value

    async def test_connection(self) -> bool:
        """Test connection to the VOICEVOX engine.

        Returns:
            True if engine is reachable
        """
        try:
            url = f"{self._engine_url}/version"
            client_timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        version = await resp.text()
                        logger.debug(f"VOICEVOX engine connected, version: {version}")
                        self._connected = True
                        return True
            self._connected = False
            return False
        except Exception as e:
            logger.debug(f"VOICEVOX engine not reachable: {e}")
            self._connected = False
            return False

    def get_voices(self) -> List[Voice]:
        """Get list of available voices (synchronous, returns cached or defaults)."""
        if self._voices_cache is not None:
            return self._voices_cache

        # Try to load from disk cache
        try:
            from utils.cache import get_cache
            cached = get_cache('voicevox_speakers', ttl_seconds=CACHE_TTL_SECONDS)
            if cached:
                voices = []
                for v in cached.get('voices', []):
                    voices.append(Voice(
                        id=v['id'], name=v['name'],
                        language=v.get('language', 'ja-JP'),
                        gender=v.get('gender'),
                        description=v.get('description', ''),
                    ))
                if voices:
                    self._voices_cache = voices
                    # Also restore icons
                    self._speaker_icons = cached.get('icons', {})
                    logger.debug(f"Loaded {len(voices)} VOICEVOX voices from cache")
                    return voices
        except Exception as e:
            logger.debug(f"Could not load VOICEVOX cache: {e}")

        # Return some well-known VOICEVOX defaults
        default_voices = [
            Voice(id='0', name='Shikoku Metan (Normal)', language='ja-JP', gender='Female'),
            Voice(id='2', name='Shikoku Metan (Sexy)', language='ja-JP', gender='Female'),
            Voice(id='3', name='Zundamon (Normal)', language='ja-JP', gender='Female'),
            Voice(id='1', name='Zundamon (Amama)', language='ja-JP', gender='Female'),
            Voice(id='4', name='Kasukabe Tsumugu (Normal)', language='ja-JP', gender='Male'),
            Voice(id='8', name='Shunichi Haru (Normal)', language='ja-JP', gender='Male'),
            Voice(id='10', name='Namine Ritsu (Normal)', language='ja-JP', gender='Female'),
            Voice(id='14', name='Mei (Normal)', language='ja-JP', gender='Female'),
        ]
        return default_voices

    async def fetch_speakers(self) -> List[Voice]:
        """Fetch all available speakers from the VOICEVOX engine.

        Returns:
            List of Voice objects from the engine
        """
        try:
            url = f"{self._engine_url}/speakers"
            client_timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch speakers: HTTP {resp.status}")
                        return self.get_voices()

                    speakers_data = await resp.json()

            voices = []
            self._speakers_cache = speakers_data

            for speaker in speakers_data:
                speaker_name = speaker.get('name', 'Unknown')
                for style in speaker.get('styles', []):
                    style_name = style.get('name', 'Normal')
                    style_id = str(style.get('id', 0))

                    voices.append(Voice(
                        id=style_id,
                        name=f"{speaker_name} ({style_name})",
                        language='ja-JP',
                        gender=None,
                        description=f"VOICEVOX speaker: {speaker_name}, style: {style_name}"
                    ))

            self._voices_cache = voices
            self._connected = True
            logger.debug(f"Fetched {len(voices)} VOICEVOX voices")
            return voices

        except Exception as e:
            logger.error(f"Error fetching VOICEVOX speakers: {e}")
            return self.get_voices()

    async def fetch_speakers_with_icons(self) -> List[Dict]:
        """Fetch all speakers with their style icons.

        Fetches /speakers for the list, then /speaker_info for each speaker's icons.
        Results are cached to disk.

        Returns:
            List of dicts: [{id, name, language, gender, icon}, ...]
        """
        # Check disk cache first
        try:
            from utils.cache import get_cache, set_cache
            cached = get_cache('voicevox_speakers', ttl_seconds=CACHE_TTL_SECONDS)
            if cached and cached.get('icons'):
                # Restore in-memory state
                voices = []
                for v in cached['voices']:
                    voices.append(Voice(
                        id=v['id'], name=v['name'],
                        language=v.get('language', 'ja-JP'),
                        gender=v.get('gender'),
                        description=v.get('description', ''),
                    ))
                self._voices_cache = voices
                self._speaker_icons = cached.get('icons', {})
                logger.debug(f"Loaded {len(voices)} VOICEVOX voices with icons from cache")
                return cached['voices']
        except Exception as e:
            logger.debug(f"No VOICEVOX cache available: {e}")

        # Fetch fresh data from engine
        try:
            client_timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                # Step 1: Get speakers list
                async with session.get(f"{self._engine_url}/speakers") as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch speakers: HTTP {resp.status}")
                        return []
                    speakers_data = await resp.json()

                # Step 2: Fetch speaker_info for each speaker (with icons)
                icons = {}  # style_id -> base64 icon string
                for speaker in speakers_data:
                    speaker_uuid = speaker.get('speaker_uuid')
                    if not speaker_uuid:
                        continue

                    try:
                        async with session.get(
                            f"{self._engine_url}/speaker_info",
                            params={'speaker_uuid': speaker_uuid}
                        ) as info_resp:
                            if info_resp.status == 200:
                                info = await info_resp.json()
                                style_infos = info.get('style_infos', [])

                                # Map style icons by style ID
                                styles = speaker.get('styles', [])
                                for i, style_info in enumerate(style_infos):
                                    icon_data = style_info.get('icon')
                                    if icon_data and i < len(styles):
                                        style_id = str(styles[i].get('id', ''))
                                        if style_id:
                                            icons[style_id] = icon_data
                    except Exception as e:
                        logger.debug(f"Could not fetch info for speaker {speaker.get('name')}: {e}")

                self._speaker_icons = icons
                logger.debug(f"Fetched icons for {len(icons)} VOICEVOX styles")

            # Build voices list
            voice_dicts = []
            voices = []
            for speaker in speakers_data:
                speaker_name = speaker.get('name', 'Unknown')
                for style in speaker.get('styles', []):
                    style_name = style.get('name', 'Normal')
                    style_id = str(style.get('id', 0))

                    voice = Voice(
                        id=style_id,
                        name=f"{speaker_name} ({style_name})",
                        language='ja-JP',
                        gender=None,
                        description=f"VOICEVOX speaker: {speaker_name}, style: {style_name}"
                    )
                    voices.append(voice)
                    voice_dicts.append({
                        'id': style_id,
                        'name': f"{speaker_name} ({style_name})",
                        'language': 'ja-JP',
                        'gender': None,
                        'description': f"VOICEVOX speaker: {speaker_name}, style: {style_name}",
                        'icon': icons.get(style_id),
                    })

            self._voices_cache = voices
            self._speakers_cache = speakers_data
            self._connected = True

            # Save to disk cache
            try:
                set_cache('voicevox_speakers', {
                    'voices': [
                        {'id': v['id'], 'name': v['name'], 'language': v['language'],
                         'gender': v['gender'], 'description': v['description']}
                        for v in voice_dicts
                    ],
                    'icons': icons,
                })
            except Exception as e:
                logger.warning(f"Could not save VOICEVOX cache: {e}")

            logger.debug(f"Fetched {len(voice_dicts)} VOICEVOX voices with {len(icons)} icons")
            return voice_dicts

        except Exception as e:
            logger.error(f"Error fetching VOICEVOX speakers with icons: {e}")
            return []

    def get_speaker_icon(self, style_id: str) -> Optional[str]:
        """Get the cached icon for a speaker style.

        Args:
            style_id: VOICEVOX style ID

        Returns:
            Base64-encoded PNG icon string, or None
        """
        return self._speaker_icons.get(style_id)

    def _prepare_text(self, text: str) -> str:
        """Prepare text for VOICEVOX synthesis.

        If english_phonetic is enabled, converts English text to katakana.

        Args:
            text: Input text

        Returns:
            Text ready for VOICEVOX (Japanese or katakana-converted)
        """
        import re

        if not self._enable_english_phonetic:
            return text

        # Check if text is already mostly Japanese
        jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
        total_alpha = len(re.findall(r'[a-zA-Z]', text))

        if jp_chars > total_alpha:
            # Mostly Japanese, pass through
            return text

        if total_alpha > 0:
            # Has English text, convert to katakana
            try:
                from utils.phoneme import english_to_katakana
                converted = english_to_katakana(text)
                logger.debug(f"English->Katakana: '{text}' -> '{converted}'")
                return converted
            except ImportError:
                logger.warning("phoneme module not available, sending English directly")
                return text
            except Exception as e:
                logger.warning(f"Phoneme conversion error: {e}, sending original text")
                return text

        return text

    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize speech from text using VOICEVOX.

        Args:
            text: Text to synthesize

        Returns:
            TTSResult with WAV audio data
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        # Convert English to katakana if needed
        synth_text = self._prepare_text(text)
        speaker_id = int(self._voice) if self._voice else 3

        try:
            client_timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                # Step 1: Create audio query
                query_url = f"{self._engine_url}/audio_query"
                query_params = {
                    'text': synth_text,
                    'speaker': str(speaker_id),
                }

                async with session.post(query_url, params=query_params) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(f"VOICEVOX audio_query failed: {body[:200]}")
                    audio_query = await resp.json()

                # Step 2: Apply speed, pitch, volume adjustments
                audio_query['speedScale'] = self._speed
                audio_query['pitchScale'] = (self._pitch - 1.0) * 0.15  # Map 0.5-2.0 -> -0.075 to +0.15
                audio_query['volumeScale'] = self._volume

                # Step 3: Synthesize audio
                synth_url = f"{self._engine_url}/synthesis"
                synth_params = {'speaker': str(speaker_id)}

                async with session.post(
                    synth_url,
                    params=synth_params,
                    json=audio_query,
                    headers={'Content-Type': 'application/json'}
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(f"VOICEVOX synthesis failed: {body[:200]}")

                    audio_data = await resp.read()

            if len(audio_data) == 0:
                raise RuntimeError("No audio data received from VOICEVOX")

            logger.debug(f"Synthesized {len(audio_data)} bytes of audio from VOICEVOX")

            # VOICEVOX returns WAV data at 24kHz by default
            return TTSResult(
                audio_data=audio_data,
                sample_rate=24000,
                channels=1,
                sample_width=2
            )

        except aiohttp.ClientError as e:
            raise RuntimeError(
                f"Cannot connect to VOICEVOX engine at {self._engine_url}. "
                f"Make sure VOICEVOX is running. Error: {e}"
            )
        except Exception as e:
            logger.error(f"VOICEVOX synthesis error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if VOICEVOX engine is available.

        Note: This is a synchronous check. For async connection test,
        use test_connection() instead.
        """
        # Try a quick synchronous check
        try:
            import urllib.request
            url = f"{self._engine_url}/version"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    self._connected = True
                    return True
        except Exception:
            pass

        self._connected = False
        return False

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to VOICEVOX engine."""
        return self._connected

    def cleanup(self):
        """Clean up resources."""
        self._voices_cache = None
        self._speakers_cache = None
        self._speaker_icons = {}
        self._connected = False
