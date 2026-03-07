"""
Microsoft Edge TTS Engine
Uses the free Edge TTS API for high-quality neural voices
Requires internet connection
"""

import asyncio
import io
import logging
from typing import List, Optional

import edge_tts

from ai.tts.base import TTSEngine, TTSResult, Voice

logger = logging.getLogger('stts.tts.edge')


# Common Edge TTS voices
COMMON_VOICES = [
    # English (US)
    ('en-US-AriaNeural', 'Aria', 'en-US', 'Female'),
    ('en-US-GuyNeural', 'Guy', 'en-US', 'Male'),
    ('en-US-JennyNeural', 'Jenny', 'en-US', 'Female'),
    ('en-US-ChristopherNeural', 'Christopher', 'en-US', 'Male'),
    # English (UK)
    ('en-GB-SoniaNeural', 'Sonia', 'en-GB', 'Female'),
    ('en-GB-RyanNeural', 'Ryan', 'en-GB', 'Male'),
    # Japanese
    ('ja-JP-NanamiNeural', 'Nanami', 'ja-JP', 'Female'),
    ('ja-JP-KeitaNeural', 'Keita', 'ja-JP', 'Male'),
    # Chinese
    ('zh-CN-XiaoxiaoNeural', 'Xiaoxiao', 'zh-CN', 'Female'),
    ('zh-CN-YunxiNeural', 'Yunxi', 'zh-CN', 'Male'),
    # Korean
    ('ko-KR-SunHiNeural', 'Sun-Hi', 'ko-KR', 'Female'),
    ('ko-KR-InJoonNeural', 'In-Joon', 'ko-KR', 'Male'),
    # Spanish
    ('es-ES-ElviraNeural', 'Elvira', 'es-ES', 'Female'),
    ('es-ES-AlvaroNeural', 'Alvaro', 'es-ES', 'Male'),
    # French
    ('fr-FR-DeniseNeural', 'Denise', 'fr-FR', 'Female'),
    ('fr-FR-HenriNeural', 'Henri', 'fr-FR', 'Male'),
    # German
    ('de-DE-KatjaNeural', 'Katja', 'de-DE', 'Female'),
    ('de-DE-ConradNeural', 'Conrad', 'de-DE', 'Male'),
    # Portuguese (Brazil)
    ('pt-BR-FranciscaNeural', 'Francisca', 'pt-BR', 'Female'),
    # Russian
    ('ru-RU-SvetlanaNeural', 'Svetlana', 'ru-RU', 'Female'),
    # Italian
    ('it-IT-ElsaNeural', 'Elsa', 'it-IT', 'Female'),
    # Arabic
    ('ar-SA-ZariyahNeural', 'Zariyah', 'ar-SA', 'Female'),
    # Hindi
    ('hi-IN-SwaraNeural', 'Swara', 'hi-IN', 'Female'),
    # Thai
    ('th-TH-PremwadeeNeural', 'Premwadee', 'th-TH', 'Female'),
    # Vietnamese
    ('vi-VN-HoaiMyNeural', 'HoaiMy', 'vi-VN', 'Female'),
]

# Default voice per language prefix — used for auto-selection when speaking translations
DEFAULT_LANG_VOICES = {
    'en': 'en-US-AriaNeural',
    'ja': 'ja-JP-NanamiNeural',
    'zh': 'zh-CN-XiaoxiaoNeural',
    'ko': 'ko-KR-SunHiNeural',
    'es': 'es-ES-ElviraNeural',
    'fr': 'fr-FR-DeniseNeural',
    'de': 'de-DE-KatjaNeural',
    'pt': 'pt-BR-FranciscaNeural',
    'ru': 'ru-RU-SvetlanaNeural',
    'it': 'it-IT-ElsaNeural',
    'ar': 'ar-SA-ZariyahNeural',
    'hi': 'hi-IN-SwaraNeural',
    'th': 'th-TH-PremwadeeNeural',
    'vi': 'vi-VN-HoaiMyNeural',
}


class EdgeTTSEngine(TTSEngine):
    """Microsoft Edge TTS engine using edge-tts library."""

    def __init__(self):
        super().__init__()
        self.name = "edge"
        self.is_online = True
        self._voice = 'en-US-AriaNeural'
        self._voices_cache: Optional[List[Voice]] = None

    def get_voices(self) -> List[Voice]:
        """Get list of available voices."""
        if self._voices_cache is not None:
            return self._voices_cache

        # Return common voices for quick access
        # Full list can be fetched via get_all_voices()
        voices = []
        for voice_id, name, language, gender in COMMON_VOICES:
            voices.append(Voice(
                id=voice_id,
                name=name,
                language=language,
                gender=gender
            ))

        self._voices_cache = voices
        return voices

    async def get_all_voices(self) -> List[Voice]:
        """Fetch all available voices from Edge TTS API."""
        try:
            all_voices = await edge_tts.list_voices()
            voices = []

            for v in all_voices:
                voices.append(Voice(
                    id=v['ShortName'],
                    name=v['FriendlyName'],
                    language=v['Locale'],
                    gender=v.get('Gender')
                ))

            self._voices_cache = voices
            return voices

        except Exception as e:
            logger.error(f"Error fetching Edge TTS voices: {e}")
            return self.get_voices()  # Return cached/default

    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize speech from text using Edge TTS.

        Args:
            text: Text to synthesize

        Returns:
            TTSResult with MP3 audio data
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            # Create communicate instance
            communicate = edge_tts.Communicate(
                text,
                self._voice,
                rate=self._speed_to_rate(),
                volume=self._volume_to_volume(),
                pitch=self._pitch_to_pitch()
            )

            # Collect audio data
            audio_data = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])

            audio_bytes = audio_data.getvalue()

            if len(audio_bytes) == 0:
                raise RuntimeError("No audio data received from Edge TTS")

            logger.debug(f"Synthesized {len(audio_bytes)} bytes of audio")

            # Edge TTS returns MP3, we'll need to decode it later
            # For now, return raw MP3 data with placeholder sample rate
            return TTSResult(
                audio_data=audio_bytes,
                sample_rate=24000,  # Edge TTS typically uses 24kHz
                channels=1,
                sample_width=2
            )

        except Exception as e:
            logger.error(f"Edge TTS synthesis error: {e}")
            raise

    def _speed_to_rate(self) -> str:
        """Convert speed multiplier to Edge TTS rate string."""
        # Edge TTS uses percentage strings like "+50%" or "-25%"
        percent = int((self._speed - 1.0) * 100)
        if percent >= 0:
            return f"+{percent}%"
        return f"{percent}%"

    def _volume_to_volume(self) -> str:
        """Convert volume to Edge TTS volume string."""
        # Edge TTS volume is percentage from 0-100
        percent = int((self._volume - 1.0) * 100)
        if percent >= 0:
            return f"+{percent}%"
        return f"{percent}%"

    def _pitch_to_pitch(self) -> str:
        """Convert pitch multiplier to Edge TTS pitch string."""
        # Edge TTS uses Hz adjustment, e.g., "+10Hz" or "-5Hz"
        hz = int((self._pitch - 1.0) * 50)
        if hz >= 0:
            return f"+{hz}Hz"
        return f"{hz}Hz"

    def get_voice_for_language(self, language: str) -> Optional[str]:
        """Get a default voice matching the given language.

        Args:
            language: Language prefix like 'ja', 'en', 'zh', or locale like 'ja-JP'.

        Returns:
            Voice ID if a match is found, None otherwise.
        """
        prefix = language.split('-')[0].lower()
        return DEFAULT_LANG_VOICES.get(prefix)

    def is_available(self) -> bool:
        """Check if Edge TTS is available (requires internet)."""
        # Edge TTS requires internet but no local setup
        return True

    def cleanup(self):
        """Clean up resources."""
        self._voices_cache = None
