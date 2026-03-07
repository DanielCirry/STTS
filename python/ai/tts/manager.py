"""
TTS Manager
Unified interface for managing multiple TTS engines
"""

import asyncio
import io
import logging
import re
from typing import Dict, List, Optional, Callable

import sounddevice as sd
import numpy as np

from ai.tts.base import TTSEngine, TTSResult, Voice
from ai.tts.edge_tts import EdgeTTSEngine
from ai.tts.piper_tts import PiperTTSEngine
from ai.tts.sapi_tts import SAPITTSEngine
from ai.tts.voicevox import VoicevoxEngine

logger = logging.getLogger('stts.tts.manager')


class TTSManager:
    """Manages multiple TTS engines and audio playback."""

    def __init__(self):
        self._engines: Dict[str, TTSEngine] = {}
        self._current_engine: Optional[str] = None
        self._output_device: Optional[int] = None
        self._extra_output_devices: List[int] = []  # Additional devices for multi-profile routing
        self._is_speaking: bool = False
        self._stop_requested: bool = False

        # Callbacks
        self.on_speaking_started: Optional[Callable[[], None]] = None
        self.on_speaking_finished: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # RVC post-processor (lazily initialized)
        self._rvc = None
        self._on_rvc_failed: Optional[Callable[[str], None]] = None

        # Initialize available engines
        self._init_engines()

    def _init_engines(self):
        """Initialize all available TTS engines."""
        # Edge TTS (always available if edge-tts is installed)
        try:
            self._engines['edge'] = EdgeTTSEngine()
            logger.debug("Edge TTS engine available")
        except Exception as e:
            logger.warning(f"Edge TTS not available: {e}")

        # Piper TTS (local neural TTS)
        try:
            piper = PiperTTSEngine()
            if piper.is_available():
                self._engines['piper'] = piper
                logger.debug("Piper TTS engine available")
        except Exception as e:
            logger.warning(f"Piper TTS not available: {e}")

        # Windows SAPI (built-in Windows TTS)
        try:
            sapi = SAPITTSEngine()
            if sapi.is_available():
                self._engines['sapi'] = sapi
                logger.debug("SAPI TTS engine available")
        except Exception as e:
            logger.warning(f"SAPI TTS not available: {e}")

        # VOICEVOX (external Japanese TTS engine)
        try:
            voicevox = VoicevoxEngine()
            # Always register VOICEVOX - availability is checked on use
            # since the engine may be started/stopped independently
            self._engines['voicevox'] = voicevox
            if voicevox.is_available():
                logger.debug("VOICEVOX engine available and running")
            else:
                logger.debug("VOICEVOX engine registered (not currently running)")
        except Exception as e:
            logger.warning(f"VOICEVOX not available: {e}")

        # Set default engine
        if 'edge' in self._engines:
            self._current_engine = 'edge'
        elif 'piper' in self._engines:
            self._current_engine = 'piper'
        elif 'sapi' in self._engines:
            self._current_engine = 'sapi'

    def get_available_engines(self) -> List[Dict[str, str]]:
        """Get list of available TTS engines.

        Returns:
            List of dicts with engine info
        """
        engines = []
        for name, engine in self._engines.items():
            engines.append({
                'id': name,
                'name': engine.name,
                'is_online': engine.is_online
            })
        return engines

    def get_current_engine(self) -> Optional[str]:
        """Get current engine ID."""
        return self._current_engine

    def set_engine(self, engine_id: str) -> bool:
        """Set the current TTS engine.

        Args:
            engine_id: Engine ID ('edge', 'piper', 'sapi')

        Returns:
            True if successful
        """
        if engine_id not in self._engines:
            logger.error(f"Unknown engine: {engine_id}")
            return False

        self._current_engine = engine_id
        logger.info(f"TTS engine set to: {engine_id}")
        return True

    def get_voices(self, engine_id: Optional[str] = None) -> List[Voice]:
        """Get available voices for an engine.

        Args:
            engine_id: Engine ID, or None for current engine

        Returns:
            List of Voice objects
        """
        if engine_id is None:
            engine_id = self._current_engine

        if engine_id not in self._engines:
            return []

        return self._engines[engine_id].get_voices()

    def set_voice(self, voice_id: str, engine_id: Optional[str] = None):
        """Set the voice for an engine.

        Args:
            voice_id: Voice ID
            engine_id: Engine ID, or None for current engine
        """
        if engine_id is None:
            engine_id = self._current_engine

        if engine_id in self._engines:
            self._engines[engine_id].voice = voice_id

    def set_speed(self, speed: float, engine_id: Optional[str] = None):
        """Set speech speed for an engine.

        Args:
            speed: Speed multiplier (0.5-2.0)
            engine_id: Engine ID, or None for current engine
        """
        if engine_id is None:
            engine_id = self._current_engine

        if engine_id in self._engines:
            self._engines[engine_id].speed = speed

    def set_volume(self, volume: float, engine_id: Optional[str] = None):
        """Set volume for an engine.

        Args:
            volume: Volume level (0.0-1.0)
            engine_id: Engine ID, or None for current engine
        """
        if engine_id is None:
            engine_id = self._current_engine

        if engine_id in self._engines:
            self._engines[engine_id].volume = volume

    def set_output_device(self, device_id: Optional[int]):
        """Set primary audio output device.

        Args:
            device_id: Output device ID, or None for default
        """
        self._output_device = device_id

    def set_extra_output_devices(self, device_ids: List[int]):
        """Set additional output devices for multi-profile audio routing.

        Args:
            device_ids: List of device IDs to also play audio to
        """
        self._extra_output_devices = device_ids

    def get_output_devices(self) -> List[Dict]:
        """Get available audio output devices.

        Returns:
            List of device info dicts
        """
        devices = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev['max_output_channels'] > 0:
                    devices.append({
                        'id': i,
                        'name': dev['name'],
                        'channels': dev['max_output_channels'],
                        'sample_rate': dev['default_samplerate']
                    })
        except Exception as e:
            logger.error(f"Error getting output devices: {e}")

        return devices

    async def speak(self, text: str, language: Optional[str] = None) -> bool:
        """Synthesize and play text.

        Args:
            text: Text to speak
            language: Optional language hint (e.g. 'ja', 'en'). When provided,
                      auto-selects a voice matching this language for engines
                      that support it, then restores the original voice.

        Returns:
            True if successful
        """
        # Strip emoji and other symbol characters before speaking
        text = re.sub(
            r'[\U0001F600-\U0001F64F'  # emoticons
            r'\U0001F300-\U0001F5FF'   # symbols & pictographs
            r'\U0001F680-\U0001F6FF'   # transport & map
            r'\U0001F1E0-\U0001F1FF'   # flags
            r'\U0001F900-\U0001F9FF'   # supplemental symbols
            r'\U0001FA00-\U0001FA6F'   # chess symbols
            r'\U0001FA70-\U0001FAFF'   # symbols extended-A
            r'\U00002702-\U000027B0'   # dingbats
            r'\U0000FE00-\U0000FE0F'   # variation selectors
            r'\U0000200D'              # zero-width joiner
            r'\U000020E3'              # combining enclosing keycap
            r'\U00002600-\U000026FF'   # misc symbols
            r'\U0000231A-\U0000231B'   # watch/hourglass
            r'\U00002934-\U00002935'   # arrows
            r'\U000025AA-\U000025AB'   # squares
            r'\U000025FB-\U000025FE'   # squares
            r'\U00002B05-\U00002B07'   # arrows
            r'\U00002B1B-\U00002B1C'   # squares
            r'\U00002B50\U00002B55'    # star/circle
            r'\U00003030\U0000303D'    # wavy dash
            r'\U00003297\U00003299'    # circled ideograph
            r']+', '', text
        ).strip()

        if not text:
            return False

        if self._current_engine is None:
            logger.error("No TTS engine available")
            return False

        # If already speaking, stop current playback first so new speech takes priority
        if self._is_speaking:
            logger.debug("New speak() call while already speaking — stopping current playback")
            self.stop()
            # Brief pause to let the stream fully stop
            await asyncio.sleep(0.05)

        engine = self._engines[self._current_engine]

        # Auto-select a voice matching the target language
        original_voice = None
        if language and hasattr(engine, 'get_voice_for_language'):
            lang_voice = engine.get_voice_for_language(language)
            if lang_voice and lang_voice != engine.voice:
                original_voice = engine.voice
                engine.voice = lang_voice
                logger.debug(f"Auto-selected voice {lang_voice} for language '{language}'")

        try:
            self._is_speaking = True
            self._stop_requested = False

            if self.on_speaking_started:
                self.on_speaking_started()

            # Synthesize audio
            logger.debug(f"Synthesizing with {self._current_engine}: {text[:50]}...")
            result = await engine.synthesize(text)

            if self._stop_requested:
                return False

            # RVC post-processing (optional)
            if self._rvc and self._rvc.is_enabled():
                try:
                    result = await self._rvc.process(result)
                except Exception as e:
                    logger.warning(f"RVC processing failed, using original audio: {e}")
                    if self._on_rvc_failed:
                        self._on_rvc_failed(str(e))

            # Play audio
            await self._play_audio(result)

            return True

        except Exception as e:
            logger.error(f"TTS error: {e}")
            if self.on_error:
                self.on_error(str(e))
            return False

        finally:
            # Restore original voice if we switched for language
            if original_voice is not None:
                engine.voice = original_voice
            self._is_speaking = False
            if self.on_speaking_finished:
                self.on_speaking_finished()

    async def _play_audio(self, result: TTSResult):
        """Play synthesized audio.

        Args:
            result: TTSResult with audio data
        """
        try:
            # Handle different audio formats
            audio_data = result.audio_data

            if audio_data[:4] == b'RIFF':
                # WAV data
                audio_array, sample_rate = await self._decode_wav(audio_data)
            elif self._is_mp3(audio_data):
                # MP3 data (Edge TTS) - decode via pydub
                audio_array, sample_rate = await self._decode_mp3(audio_data)
            else:
                # Assume raw PCM
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                sample_rate = result.sample_rate

            if self._stop_requested:
                return

            # Play audio
            duration_s = len(audio_array) / sample_rate
            logger.debug(f"Playing audio: {len(audio_array)} samples at {sample_rate}Hz ({duration_s:.2f}s)")

            # Play to extra output devices (non-blocking, fire-and-forget)
            self._active_extra_streams = []
            for extra_dev in self._extra_output_devices:
                try:
                    extra_stream = sd.OutputStream(
                        samplerate=sample_rate,
                        channels=1,
                        device=extra_dev,
                        dtype='float32',
                    )
                    extra_stream.start()
                    extra_stream.write(audio_array.reshape(-1, 1))
                    self._active_extra_streams.append(extra_stream)
                except Exception as e:
                    logger.warning(f"Failed to play to extra device {extra_dev}: {e}")

            # Play to primary device
            sd.play(
                audio_array,
                samplerate=sample_rate,
                device=self._output_device,
                blocking=False
            )

            # Wait for playback to complete, checking for stop requests
            # Use duration-based timeout as fallback in case sd.get_stream() is unreliable
            import time
            play_start = time.monotonic()
            max_wait = duration_s + 1.0  # Extra second buffer
            while time.monotonic() - play_start < max_wait:
                if self._stop_requested:
                    sd.stop()
                    return
                try:
                    stream = sd.get_stream()
                    if stream is None or not stream.active:
                        break
                except Exception:
                    break
                await asyncio.sleep(0.05)

            # Clean up extra streams
            for extra_stream in getattr(self, '_active_extra_streams', []):
                try:
                    extra_stream.stop()
                    extra_stream.close()
                except Exception:
                    pass
            self._active_extra_streams = []

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            raise

    @staticmethod
    def _is_mp3(data: bytes) -> bool:
        """Check if data looks like MP3 audio.

        Detects ID3 tags and MPEG frame sync words (0xFF followed by 0xE0-0xFF).
        """
        if len(data) < 3:
            return False
        # ID3v2 tag
        if data[:3] == b'ID3':
            return True
        # MPEG frame sync: first byte 0xFF, second byte high nibble >= 0xE
        if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            return True
        return False

    async def _decode_mp3(self, mp3_data: bytes) -> tuple:
        """Decode MP3 data to numpy array.

        Args:
            mp3_data: MP3 audio data

        Returns:
            Tuple of (audio samples as float32 array, sample rate)
        """
        import miniaudio

        decoded = miniaudio.decode(mp3_data, output_format=miniaudio.SampleFormat.SIGNED16)
        samples = np.array(decoded.samples, dtype=np.float32) / 32768.0

        # Convert to mono if needed
        if decoded.nchannels > 1:
            samples = samples[::decoded.nchannels]

        return samples, decoded.sample_rate

    async def _decode_wav(self, wav_data: bytes) -> tuple:
        """Decode WAV data to numpy array.

        Args:
            wav_data: WAV audio data

        Returns:
            Tuple of (audio samples, sample rate)
        """
        import wave

        with wave.open(io.BytesIO(wav_data), 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            audio_bytes = wav_file.readframes(n_frames)

            # Convert to float32
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            return audio_array, sample_rate

    def stop(self):
        """Stop current speech playback."""
        self._stop_requested = True
        try:
            sd.stop()
        except:
            pass

    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._is_speaking

    def get_rvc(self):
        """Get the RVC post-processor instance (may be None)."""
        return self._rvc

    def init_rvc(self):
        """Lazily initialize the RVC post-processor.

        Returns:
            RVCPostProcessor instance.
        """
        if self._rvc is None:
            from ai.tts.rvc_postprocess import RVCPostProcessor
            self._rvc = RVCPostProcessor()
        return self._rvc

    def set_on_rvc_failed(self, callback: Optional[Callable[[str], None]]):
        """Set callback for RVC processing failures."""
        self._on_rvc_failed = callback

    def cleanup(self):
        """Clean up resources."""
        self.stop()
        if self._rvc is not None:
            self._rvc.unload()
            self._rvc = None
        for engine in self._engines.values():
            engine.cleanup()
        self._engines.clear()
