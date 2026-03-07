"""
Cloud Translation providers: DeepL and Google Cloud Translation.
Simple HTTP API wrappers as alternatives to local NLLB translation.
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger('stts.translator_cloud')

# Map NLLB codes to DeepL language codes
NLLB_TO_DEEPL: Dict[str, str] = {
    'eng_Latn': 'EN',
    'jpn_Jpan': 'JA',
    'zho_Hans': 'ZH',
    'zho_Hant': 'ZH',
    'kor_Hang': 'KO',
    'spa_Latn': 'ES',
    'fra_Latn': 'FR',
    'deu_Latn': 'DE',
    'ita_Latn': 'IT',
    'por_Latn': 'PT-PT',
    'rus_Cyrl': 'RU',
    'arb_Arab': 'AR',
    'hin_Deva': 'HI',
    'tha_Thai': 'TH',  # Not supported by DeepL free
    'vie_Latn': 'VI',  # Not supported by DeepL free
    'ind_Latn': 'ID',
    'nld_Latn': 'NL',
    'pol_Latn': 'PL',
    'tur_Latn': 'TR',
    'ukr_Cyrl': 'UK',
}

# Map NLLB codes to Google Translate language codes (ISO 639-1)
NLLB_TO_GOOGLE: Dict[str, str] = {
    'eng_Latn': 'en',
    'jpn_Jpan': 'ja',
    'zho_Hans': 'zh-CN',
    'zho_Hant': 'zh-TW',
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


class DeepLTranslator:
    """DeepL Translation API wrapper."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('DEEPL_API_KEY', '')
        self._base_url = 'https://api-free.deepl.com/v2'  # Free tier by default

    def set_api_key(self, api_key: str):
        """Set API key and auto-detect free vs pro."""
        self.api_key = api_key
        # DeepL Pro keys end with ':fx', free keys end with ':fx' too but use different URL
        if api_key and not api_key.endswith(':fx'):
            self._base_url = 'https://api.deepl.com/v2'
        else:
            self._base_url = 'https://api-free.deepl.com/v2'

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using DeepL API.

        Args:
            text: Text to translate
            source_lang: Source language (NLLB code or DeepL code)
            target_lang: Target language (NLLB code or DeepL code)

        Returns:
            Translated text
        """
        if not self.api_key:
            raise RuntimeError("DeepL API key not configured")

        import urllib.request
        import urllib.parse
        import json

        # Convert NLLB codes to DeepL codes
        deepl_source = NLLB_TO_DEEPL.get(source_lang, source_lang.upper())
        deepl_target = NLLB_TO_DEEPL.get(target_lang, target_lang.upper())

        # DeepL source language uses 2-letter codes (no region)
        if len(deepl_source) > 2 and '-' in deepl_source:
            deepl_source = deepl_source.split('-')[0]

        data = urllib.parse.urlencode({
            'auth_key': self.api_key,
            'text': text,
            'source_lang': deepl_source,
            'target_lang': deepl_target,
        }).encode('utf-8')

        try:
            url = f'{self._base_url}/translate'
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                translations = result.get('translations', [])
                if translations:
                    translated = translations[0].get('text', '')
                    logger.debug(f"DeepL: '{text[:50]}...' -> '{translated[:50]}...'")
                    return translated
                else:
                    raise RuntimeError("No translation returned from DeepL")

        except Exception as e:
            logger.error(f"DeepL translation error: {e}")
            raise

    def test_connection(self) -> bool:
        """Test DeepL API connection."""
        if not self.api_key:
            return False

        import urllib.request
        import json

        try:
            url = f'{self._base_url}/usage'
            req = urllib.request.Request(url, method='GET')
            req.add_header('Authorization', f'DeepL-Auth-Key {self.api_key}')

            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                logger.debug(f"DeepL usage: {result.get('character_count', 0)}/{result.get('character_limit', 0)}")
                return True

        except Exception as e:
            logger.error(f"DeepL connection test failed: {e}")
            return False


class GoogleCloudTranslator:
    """Google Cloud Translation API v2 wrapper."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('GOOGLE_CLOUD_TRANSLATION_KEY', '')

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using Google Cloud Translation API.

        Args:
            text: Text to translate
            source_lang: Source language (NLLB code or ISO code)
            target_lang: Target language (NLLB code or ISO code)

        Returns:
            Translated text
        """
        if not self.api_key:
            raise RuntimeError("Google Cloud Translation API key not configured")

        import urllib.request
        import urllib.parse
        import json

        # Convert NLLB codes to Google codes
        google_source = NLLB_TO_GOOGLE.get(source_lang, source_lang.split('_')[0] if '_' in source_lang else source_lang)
        google_target = NLLB_TO_GOOGLE.get(target_lang, target_lang.split('_')[0] if '_' in target_lang else target_lang)

        params = urllib.parse.urlencode({
            'key': self.api_key,
            'q': text,
            'source': google_source,
            'target': google_target,
            'format': 'text',
        })

        try:
            url = f'https://translation.googleapis.com/language/translate/v2?{params}'
            req = urllib.request.Request(url, method='POST')
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                translations = result.get('data', {}).get('translations', [])
                if translations:
                    translated = translations[0].get('translatedText', '')
                    logger.debug(f"Google: '{text[:50]}...' -> '{translated[:50]}...'")
                    return translated
                else:
                    raise RuntimeError("No translation returned from Google")

        except Exception as e:
            logger.error(f"Google Cloud translation error: {e}")
            raise

    def test_connection(self) -> bool:
        """Test Google Cloud Translation API connection."""
        if not self.api_key:
            return False

        try:
            result = self.translate("hello", "eng_Latn", "jpn_Jpan")
            return bool(result)
        except Exception as e:
            logger.error(f"Google Cloud connection test failed: {e}")
            return False


class CloudTranslationManager:
    """Manages cloud translation providers as alternatives to local NLLB."""

    def __init__(self):
        self.deepl = DeepLTranslator()
        self.google = GoogleCloudTranslator()
        self._active_provider: Optional[str] = None  # 'deepl' or 'google' or None (use local)

    @property
    def active_provider(self) -> Optional[str]:
        return self._active_provider

    def set_provider(self, provider: Optional[str]):
        """Set the active cloud translation provider.

        Args:
            provider: 'deepl', 'google', or None to use local NLLB
        """
        if provider not in (None, 'deepl', 'google', 'local'):
            logger.warning(f"Unknown cloud translation provider: {provider}")
            return
        self._active_provider = None if provider == 'local' else provider
        logger.info(f"Cloud translation provider set to: {self._active_provider or 'local (NLLB)'}")

    def set_api_key(self, provider: str, api_key: str):
        """Set API key for a cloud provider.

        Args:
            provider: 'deepl' or 'google'
            api_key: API key string
        """
        if provider == 'deepl':
            self.deepl.set_api_key(api_key)
        elif provider == 'google':
            self.google.set_api_key(api_key)

    def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Translate using the active cloud provider.

        Returns None if no cloud provider is active (caller should fall through to local).

        Args:
            text: Text to translate
            source_lang: Source language (NLLB code)
            target_lang: Target language (NLLB code)

        Returns:
            Translated text, or None if no cloud provider is active
        """
        if self._active_provider == 'deepl' and self.deepl.is_available:
            return self.deepl.translate(text, source_lang, target_lang)
        elif self._active_provider == 'google' and self.google.is_available:
            return self.google.translate(text, source_lang, target_lang)
        return None

    def get_providers(self) -> List[Dict[str, str]]:
        """Get list of available cloud translation providers."""
        return [
            {
                'id': 'local',
                'name': 'Local NLLB',
                'description': 'Offline, runs on your device',
                'available': 'true',
            },
            {
                'id': 'deepl',
                'name': 'DeepL',
                'description': 'High-quality cloud translation',
                'available': str(self.deepl.is_available).lower(),
            },
            {
                'id': 'google',
                'name': 'Google Cloud',
                'description': 'Google Translate API',
                'available': str(self.google.is_available).lower(),
            },
        ]
