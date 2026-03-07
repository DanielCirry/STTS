"""
Piper TTS Engine
Fast local neural TTS using ONNX models
Works offline with low latency
"""

import io
import json
import logging
import wave
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger('stts.tts.piper')


# Piper HuggingFace base URL
PIPER_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# Common Piper voice models
# url_path is relative to PIPER_HF_BASE
PIPER_VOICES = {
    'en_US-amy-medium': {
        'name': 'Amy (US)',
        'language': 'en-US',
        'gender': 'Female',
        'quality': 'medium',
        'url_path': 'en/en_US/amy/medium',
    },
    'en_US-lessac-medium': {
        'name': 'Lessac (US)',
        'language': 'en-US',
        'gender': 'Female',
        'quality': 'medium',
        'url_path': 'en/en_US/lessac/medium',
    },
    'en_US-ryan-medium': {
        'name': 'Ryan (US)',
        'language': 'en-US',
        'gender': 'Male',
        'quality': 'medium',
        'url_path': 'en/en_US/ryan/medium',
    },
    'en_GB-alba-medium': {
        'name': 'Alba (UK)',
        'language': 'en-GB',
        'gender': 'Female',
        'quality': 'medium',
        'url_path': 'en/en_GB/alba/medium',
    },
    'de_DE-thorsten-medium': {
        'name': 'Thorsten (DE)',
        'language': 'de-DE',
        'gender': 'Male',
        'quality': 'medium',
        'url_path': 'de/de_DE/thorsten/medium',
    },
    'es_ES-carlfm-x_low': {
        'name': 'Carlfm (ES)',
        'language': 'es-ES',
        'gender': 'Male',
        'quality': 'low',
        'url_path': 'es/es_ES/carlfm/x_low',
    },
    'fr_FR-siwis-medium': {
        'name': 'Siwis (FR)',
        'language': 'fr-FR',
        'gender': 'Female',
        'quality': 'medium',
        'url_path': 'fr/fr_FR/siwis/medium',
    },
}


class PiperTTSEngine:
    """Piper TTS engine using piper-tts library."""

    def __init__(self, models_dir: Optional[Path] = None):
        """Initialize Piper TTS engine.

        Args:
            models_dir: Directory containing Piper voice models
        """
        from ai.tts.base import TTSEngine, TTSResult, Voice

        self.name = "piper"
        self.is_online = False
        self._voice = 'en_US-amy-medium'
        self._speed = 1.0
        self._pitch = 1.0
        self._volume = 1.0

        # Model paths
        if models_dir is None:
            # Default to %APPDATA%/STTS/models/piper
            import os
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            models_dir = Path(appdata) / 'STTS' / 'models' / 'piper'

        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)

        # Piper instance
        self._piper = None
        self._current_model: Optional[str] = None

    @property
    def voice(self) -> Optional[str]:
        return self._voice

    @voice.setter
    def voice(self, voice_id: str):
        self._voice = voice_id
        # Model will be loaded on next synthesis

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float):
        self._speed = max(0.5, min(2.0, value))

    def get_voices(self) -> List:
        """Get list of available/downloaded voices."""
        from ai.tts.base import Voice

        voices = []

        # Check which models are downloaded
        for voice_id, info in PIPER_VOICES.items():
            model_path = self._models_dir / f"{voice_id}.onnx"
            is_downloaded = model_path.exists()

            voices.append(Voice(
                id=voice_id,
                name=info['name'],
                language=info['language'],
                gender=info.get('gender'),
                description=f"{'Downloaded' if is_downloaded else 'Not downloaded'} - {info['quality']} quality"
            ))

        return voices

    def _download_model(self, voice_id: str) -> bool:
        """Download a Piper voice model from HuggingFace.

        Args:
            voice_id: Voice model ID (e.g. 'en_US-amy-medium')

        Returns:
            True if downloaded successfully
        """
        voice_info = PIPER_VOICES.get(voice_id)
        if not voice_info or 'url_path' not in voice_info:
            logger.error(f"No download URL for Piper voice: {voice_id}")
            return False

        import urllib.request

        url_path = voice_info['url_path']
        files = [f"{voice_id}.onnx", f"{voice_id}.onnx.json"]

        for filename in files:
            dest = self._models_dir / filename
            if dest.exists():
                continue

            url = f"{PIPER_HF_BASE}/{url_path}/{filename}"
            logger.debug(f"Downloading Piper model: {url}")

            try:
                urllib.request.urlretrieve(url, str(dest))
                logger.debug(f"Downloaded: {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
                # Clean up partial download
                if dest.exists():
                    dest.unlink()
                return False

        return True

    def _load_model(self, voice_id: str) -> bool:
        """Load a Piper voice model, downloading if necessary.

        Args:
            voice_id: Voice model ID

        Returns:
            True if loaded successfully
        """
        if self._current_model == voice_id and self._piper is not None:
            return True

        try:
            from piper import PiperVoice

            model_path = self._models_dir / f"{voice_id}.onnx"
            config_path = self._models_dir / f"{voice_id}.onnx.json"

            if not model_path.exists():
                logger.debug(f"Piper model not found, attempting download: {voice_id}")
                if not self._download_model(voice_id):
                    raise RuntimeError(f"Failed to download Piper model: {voice_id}")

            if not model_path.exists():
                logger.error(f"Piper model not found: {model_path}")
                return False

            logger.info(f"Loading Piper model: {voice_id}")

            self._piper = PiperVoice.load(
                str(model_path),
                config_path=str(config_path) if config_path.exists() else None
            )
            self._current_model = voice_id

            logger.info(f"Piper model loaded: {voice_id}")
            return True

        except ImportError:
            logger.error("piper-tts not installed")
            return False
        except Exception as e:
            logger.error(f"Error loading Piper model: {e}")
            return False

    async def synthesize(self, text: str):
        """Synthesize speech from text using Piper.

        Args:
            text: Text to synthesize

        Returns:
            TTSResult with WAV audio data
        """
        from ai.tts.base import TTSResult

        if not text.strip():
            raise ValueError("Text cannot be empty")

        # Load model if needed
        if not self._load_model(self._voice):
            raise RuntimeError(f"Failed to load Piper model: {self._voice}")

        try:
            # Synthesize to bytes
            audio_bytes = io.BytesIO()

            with wave.open(audio_bytes, 'wb') as wav_file:
                self._piper.synthesize_wav(text, wav_file)

            audio_data = audio_bytes.getvalue()
            logger.debug(f"Synthesized {len(audio_data)} bytes of audio")

            return TTSResult(
                audio_data=audio_data,
                sample_rate=22050,
                channels=1,
                sample_width=2
            )

        except Exception as e:
            logger.error(f"Piper TTS synthesis error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Piper is available."""
        try:
            from piper import PiperVoice
            return True
        except ImportError:
            return False

    def is_model_downloaded(self, voice_id: str) -> bool:
        """Check if a voice model is downloaded."""
        model_path = self._models_dir / f"{voice_id}.onnx"
        return model_path.exists()

    async def download_model(self, voice_id: str, progress_callback=None) -> bool:
        """Download a voice model from Hugging Face.

        Args:
            voice_id: Voice model ID
            progress_callback: Optional callback for download progress

        Returns:
            True if downloaded successfully
        """
        if voice_id not in PIPER_VOICES:
            logger.error(f"Unknown voice: {voice_id}")
            return False

        try:
            from huggingface_hub import hf_hub_download

            # Piper models are on Hugging Face
            repo_id = "rhasspy/piper-voices"
            model_file = f"{voice_id}.onnx"
            config_file = f"{voice_id}.onnx.json"

            # Construct path based on voice ID
            voice_parts = voice_id.split('-')
            lang = voice_parts[0]
            subfolder = f"{lang}/{voice_id}"

            logger.debug(f"Downloading Piper voice: {voice_id}")

            # Download model file
            model_path = hf_hub_download(
                repo_id=repo_id,
                filename=model_file,
                subfolder=subfolder,
                local_dir=self._models_dir,
                local_dir_use_symlinks=False
            )

            # Download config file
            config_path = hf_hub_download(
                repo_id=repo_id,
                filename=config_file,
                subfolder=subfolder,
                local_dir=self._models_dir,
                local_dir_use_symlinks=False
            )

            logger.debug(f"Downloaded Piper voice: {voice_id}")
            return True

        except Exception as e:
            logger.error(f"Error downloading Piper model: {e}")
            return False

    def cleanup(self):
        """Clean up resources."""
        self._piper = None
        self._current_model = None
