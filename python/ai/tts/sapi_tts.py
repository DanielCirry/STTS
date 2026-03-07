"""
Windows SAPI TTS Engine
Uses Windows built-in text-to-speech via COM
Works offline, no additional downloads needed
"""

import io
import logging
import sys
import wave
from typing import List, Optional

from ai.tts.base import TTSEngine, TTSResult, Voice

logger = logging.getLogger('stts.tts.sapi')


class SAPITTSEngine(TTSEngine):
    """Windows SAPI (Speech API) TTS engine."""

    def __init__(self):
        super().__init__()
        self.name = "sapi"
        self.is_online = False
        self._voice = None
        self._voices_cache: Optional[List[Voice]] = None
        self._sapi = None

        if sys.platform != 'win32':
            logger.warning("SAPI TTS is only available on Windows")

    def _init_sapi(self):
        """Initialize SAPI COM object."""
        if self._sapi is not None:
            return True

        if sys.platform != 'win32':
            return False

        try:
            import win32com.client

            self._sapi = win32com.client.Dispatch("SAPI.SpVoice")

            # Set default voice if not set
            if self._voice is None and self._sapi.GetVoices().Count > 0:
                self._voice = self._sapi.GetVoices().Item(0).Id

            logger.debug("SAPI TTS initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize SAPI: {e}")
            return False

    def get_voices(self) -> List[Voice]:
        """Get list of available SAPI voices."""
        if self._voices_cache is not None:
            return self._voices_cache

        if not self._init_sapi():
            return []

        try:
            voices = []
            sapi_voices = self._sapi.GetVoices()

            for i in range(sapi_voices.Count):
                voice = sapi_voices.Item(i)
                voice_id = voice.Id

                # Parse voice attributes
                name = voice.GetDescription()
                language = "en-US"  # Default

                # Try to get language from attributes
                try:
                    attrs = voice.GetAttribute("Language")
                    if attrs:
                        # SAPI uses LCID, convert common ones
                        lcid_map = {
                            "409": "en-US",
                            "809": "en-GB",
                            "411": "ja-JP",
                            "804": "zh-CN",
                            "404": "zh-TW",
                            "412": "ko-KR",
                            "40A": "es-ES",
                            "40C": "fr-FR",
                            "407": "de-DE",
                        }
                        language = lcid_map.get(attrs, attrs)
                except:
                    pass

                # Try to determine gender from name
                gender = None
                name_lower = name.lower()
                if any(x in name_lower for x in ['female', 'woman', 'girl']):
                    gender = 'Female'
                elif any(x in name_lower for x in ['male', 'man', 'boy']):
                    gender = 'Male'

                voices.append(Voice(
                    id=voice_id,
                    name=name,
                    language=language,
                    gender=gender
                ))

            self._voices_cache = voices
            return voices

        except Exception as e:
            logger.error(f"Error getting SAPI voices: {e}")
            return []

    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize speech from text using SAPI.

        Args:
            text: Text to synthesize

        Returns:
            TTSResult with WAV audio data
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        if not self._init_sapi():
            raise RuntimeError("SAPI not available")

        try:
            import win32com.client
            import pythoncom

            # Initialize COM in this thread
            pythoncom.CoInitialize()

            try:
                # Create new SAPI instance for this operation
                sapi = win32com.client.Dispatch("SAPI.SpVoice")

                # Set voice
                if self._voice:
                    voices = sapi.GetVoices()
                    for i in range(voices.Count):
                        if voices.Item(i).Id == self._voice:
                            sapi.Voice = voices.Item(i)
                            break

                # Set rate (-10 to 10, default 0)
                # Convert speed multiplier (0.5-2.0) to SAPI rate
                sapi.Rate = int((self._speed - 1.0) * 10)

                # Set volume (0-100)
                sapi.Volume = int(self._volume * 100)

                # Use a temp WAV file instead of SpMemoryStream
                # SpMemoryStream.GetData() often returns empty on modern Windows
                import tempfile
                import os

                tmp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()

                try:
                    # Create file stream for output
                    stream = win32com.client.Dispatch("SAPI.SpFileStream")
                    stream.Format.Type = 22  # SAFT22kHz16BitMono
                    stream.Open(tmp_path, 3)  # SSFMCreateForWrite = 3

                    # Set output to file stream
                    old_output = sapi.AudioOutputStream
                    sapi.AudioOutputStream = stream

                    # Synthesize
                    sapi.Speak(text, 0)  # SVSFDefault

                    # Close stream and restore output
                    stream.Close()
                    sapi.AudioOutputStream = old_output

                    # Read the WAV file
                    with open(tmp_path, 'rb') as f:
                        wav_data = f.read()

                    if len(wav_data) < 50:
                        raise RuntimeError(f"SAPI produced empty audio ({len(wav_data)} bytes)")

                    logger.debug(f"Synthesized {len(wav_data)} bytes of audio")
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                return TTSResult(
                    audio_data=wav_data,
                    sample_rate=22050,
                    channels=1,
                    sample_width=2
                )

            finally:
                pythoncom.CoUninitialize()

        except Exception as e:
            logger.error(f"SAPI TTS synthesis error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if SAPI is available."""
        if sys.platform != 'win32':
            return False

        try:
            import win32com.client
            return True
        except ImportError:
            return False

    def cleanup(self):
        """Clean up resources."""
        self._sapi = None
        self._voices_cache = None
