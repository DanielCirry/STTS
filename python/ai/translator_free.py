"""
Free translation providers: MyMemory, LibreTranslate, Lingva.
Zero-configuration fallback chain that works without any API keys.
Uses only Python stdlib (urllib, json, datetime, logging).
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

logger = logging.getLogger('stts.translator_free')


# Maps NLLB codes to per-provider language codes
NLLB_TO_FREE_API: Dict[str, Dict[str, str]] = {
    'eng_Latn': {'mymemory': 'en',    'libretranslate': 'en', 'lingva': 'en'},
    'jpn_Jpan': {'mymemory': 'ja',    'libretranslate': 'ja', 'lingva': 'ja'},
    'zho_Hans': {'mymemory': 'zh-CN', 'libretranslate': 'zh', 'lingva': 'zh'},
    'zho_Hant': {'mymemory': 'zh-TW', 'libretranslate': 'zh', 'lingva': 'zh-TW'},
    'kor_Hang': {'mymemory': 'ko',    'libretranslate': 'ko', 'lingva': 'ko'},
    'spa_Latn': {'mymemory': 'es',    'libretranslate': 'es', 'lingva': 'es'},
    'fra_Latn': {'mymemory': 'fr',    'libretranslate': 'fr', 'lingva': 'fr'},
    'deu_Latn': {'mymemory': 'de',    'libretranslate': 'de', 'lingva': 'de'},
    'ita_Latn': {'mymemory': 'it',    'libretranslate': 'it', 'lingva': 'it'},
    'por_Latn': {'mymemory': 'pt',    'libretranslate': 'pt', 'lingva': 'pt'},
    'rus_Cyrl': {'mymemory': 'ru',    'libretranslate': 'ru', 'lingva': 'ru'},
    'arb_Arab': {'mymemory': 'ar',    'libretranslate': 'ar', 'lingva': 'ar'},
    'hin_Deva': {'mymemory': 'hi',    'libretranslate': 'hi', 'lingva': 'hi'},
    'tha_Thai': {'mymemory': 'th',    'libretranslate': 'th', 'lingva': 'th'},
    'vie_Latn': {'mymemory': 'vi',    'libretranslate': 'vi', 'lingva': 'vi'},
    'ind_Latn': {'mymemory': 'id',    'libretranslate': 'id', 'lingva': 'id'},
    'nld_Latn': {'mymemory': 'nl',    'libretranslate': 'nl', 'lingva': 'nl'},
    'pol_Latn': {'mymemory': 'pl',    'libretranslate': 'pl', 'lingva': 'pl'},
    'tur_Latn': {'mymemory': 'tr',    'libretranslate': 'tr', 'lingva': 'tr'},
    'ukr_Cyrl': {'mymemory': 'uk',    'libretranslate': 'uk', 'lingva': 'uk'},
}


class RateLimitError(Exception):
    """Provider is rate-limited (daily quota or HTTP 429)."""
    pass


class ProviderUnavailableError(Exception):
    """Provider is down, unreachable, or language pair unsupported."""
    pass


class FreeTranslationProvider:
    """State tracker for a single free translation provider."""

    def __init__(self, name: str, translate_fn: Callable):
        self.name = name
        self._translate = translate_fn
        self.enabled = True
        self.rate_limited_until: Optional[datetime] = None
        self.consecutive_failures: int = 0

    @property
    def is_available(self) -> bool:
        """Returns False if disabled or currently in rate-limit/cooldown period."""
        if not self.enabled:
            return False
        if self.rate_limited_until and datetime.utcnow() < self.rate_limited_until:
            return False
        return True

    def mark_rate_limited(self, duration_seconds: int = 86400):
        """Mark provider as rate-limited.

        MyMemory daily limit uses 86400s (UTC midnight reset).
        Transient errors use 300s (5 min).
        """
        self.rate_limited_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        self.consecutive_failures = 0
        logger.warning(
            f"{self.name}: rate limited for {duration_seconds}s "
            f"(until {self.rate_limited_until.isoformat()})"
        )

    def mark_failure(self):
        """Track a transient failure. After 3 consecutive failures, set 5-minute cooldown."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.mark_rate_limited(300)
            logger.warning(
                f"{self.name}: set 5-min cooldown after {self.consecutive_failures} consecutive failures"
            )

    def mark_success(self):
        """Reset failure counters and clear any rate-limit state."""
        self.consecutive_failures = 0
        self.rate_limited_until = None


class FreeTranslationManager:
    """
    Manages a fallback chain of free translation providers.

    Provider order: MyMemory -> LibreTranslate -> Lingva.

    Each provider tracks its own rate-limit and failure state.
    Returns None when all providers fail (caller should fall through to local NLLB).
    """

    def __init__(self, mymemory_email: str = ""):
        self._email = mymemory_email
        self._libretranslate_instances = [
            "https://translate.argosopentech.com",
            "https://translate.terraprint.co",
            "https://lt.vern.cc",
        ]
        self._lingva_instances = [
            "https://lingva.ml",
            "https://translate.plausibility.cloud",
            "https://lingva.tiekoetter.com",
        ]
        self._providers: List[FreeTranslationProvider] = []
        self._setup_providers()

    def _setup_providers(self):
        """Create provider instances in fallback order."""
        self._providers = [
            FreeTranslationProvider("MyMemory", self._mymemory_translate),
            FreeTranslationProvider("LibreTranslate", self._libretranslate_translate),
            FreeTranslationProvider("Lingva", self._lingva_translate),
        ]

    def set_mymemory_email(self, email: str):
        """Set email for MyMemory 50K/day tier (vs 5K anonymous)."""
        self._email = email
        logger.debug(f"MyMemory email set: {email[:3]}***")

    def translate(self, text: str, source_nllb: str, target_nllb: str) -> Optional[str]:
        """Try each available free provider in order.

        Returns translated text on success, or None if all providers fail.
        Caller should fall through to local NLLB when None is returned.

        Args:
            text: Text to translate
            source_nllb: Source language in NLLB code format (e.g. 'eng_Latn')
            target_nllb: Target language in NLLB code format (e.g. 'jpn_Jpan')

        Returns:
            Translated text, or None if all providers failed
        """
        for provider in self._providers:
            if not provider.is_available:
                logger.debug(f"Skipping {provider.name} (unavailable/rate-limited)")
                continue

            # Look up per-provider language codes
            provider_key = provider.name.lower().replace(" ", "")
            src = NLLB_TO_FREE_API.get(source_nllb, {}).get(provider_key)
            tgt = NLLB_TO_FREE_API.get(target_nllb, {}).get(provider_key)

            if not src or not tgt:
                logger.debug(
                    f"Skipping {provider.name}: unsupported language pair "
                    f"{source_nllb}->{target_nllb}"
                )
                continue

            try:
                result = provider._translate(text, src, tgt)
                if result:
                    provider.mark_success()
                    logger.debug(
                        f"Free translation [{provider.name}]: "
                        f"'{text[:40]}' -> '{result[:40]}'"
                    )
                    return result
            except RateLimitError as e:
                logger.debug(f"{provider.name} rate limited ({e}), trying next provider...")
                provider.mark_rate_limited(86400)
                continue
            except ProviderUnavailableError as e:
                logger.warning(f"{provider.name} unavailable ({e}), trying next provider...")
                provider.mark_failure()
                continue
            except Exception as e:
                logger.warning(f"{provider.name} failed ({e}), trying next provider...")
                provider.mark_failure()
                continue

        logger.warning(
            f"All free translation providers failed for {source_nllb}->{target_nllb}"
        )
        return None

    def get_active_provider(self) -> Optional[str]:
        """Return the name of the first available provider, or None if all are unavailable."""
        for provider in self._providers:
            if provider.is_available:
                return provider.name
        return None

    def get_status(self) -> List[dict]:
        """Return status of all providers for monitoring/UI display."""
        return [
            {
                'name': p.name,
                'available': p.is_available,
                'rate_limited_until': (
                    p.rate_limited_until.isoformat() if p.rate_limited_until else None
                ),
                'consecutive_failures': p.consecutive_failures,
            }
            for p in self._providers
        ]

    def _mymemory_translate(self, text: str, source: str, target: str) -> str:
        """Translate using MyMemory API.

        Uses GET to api.mymemory.translated.net with 5s timeout.
        Checks responseStatus in JSON body for 429 (not HTTP status).
        Raises RateLimitError for daily limit, ProviderUnavailableError for network/parse errors.
        """
        params: dict = {"q": text, "langpair": f"{source}|{target}"}
        if self._email:
            params["de"] = self._email

        url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)

        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderUnavailableError(f"MyMemory network error: {e}") from e

        status = data.get("responseStatus", 0)
        details = data.get("responseDetails", "")

        # Check for rate limit signals in body (MyMemory returns 200 with error in body)
        if status == 429 or "QUERY LENGTH LIMIT" in details:
            raise RateLimitError("MyMemory daily limit reached")

        if status not in (200, "200"):
            raise ProviderUnavailableError(
                f"MyMemory status {status}: {details}"
            )

        translated = data.get("responseData", {}).get("translatedText", "")
        if not translated:
            raise ProviderUnavailableError("MyMemory returned empty translation")

        return translated

    def _libretranslate_translate(self, text: str, source: str, target: str) -> str:
        """Translate using LibreTranslate API.

        Tries each instance in order with POST to {instance}/translate.
        Skips instances that require an API key (HTTP 403).
        Raises ProviderUnavailableError if all instances fail.
        All requests use timeout=5.
        """
        last_error = None

        for instance in self._libretranslate_instances:
            try:
                payload = json.dumps({
                    "q": text,
                    "source": source,
                    "target": target,
                    "format": "text",
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{instance}/translate",
                    data=payload,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if "error" in data:
                    error_msg = data["error"]
                    # Instance requires a key; try next
                    if "key" in error_msg.lower() or "api" in error_msg.lower():
                        last_error = f"key required: {error_msg}"
                        continue
                    last_error = error_msg
                    continue

                translated = data.get("translatedText", "")
                if translated:
                    return translated
                last_error = "empty translatedText"
                continue

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise RateLimitError("LibreTranslate rate limited")
                if e.code == 403:
                    # API key required on this instance; try next
                    last_error = f"HTTP 403 (key required) from {instance}"
                    continue
                last_error = f"HTTP {e.code} from {instance}"
                continue
            except urllib.error.URLError as e:
                last_error = f"URLError from {instance}: {e}"
                continue
            except Exception as e:
                last_error = f"Error from {instance}: {e}"
                continue

        raise ProviderUnavailableError(
            f"All LibreTranslate instances failed. Last error: {last_error}"
        )

    def _lingva_translate(self, text: str, source: str, target: str) -> str:
        """Translate using Lingva Translate API.

        Uses GET to {instance}/api/v1/{source}/{target}/{url_encoded_text}.
        Detects HTML responses (scraper blocked by Google) and skips that instance.
        All requests use timeout=5.
        """
        last_error = None

        for instance in self._lingva_instances:
            try:
                encoded = urllib.parse.quote(text, safe="")
                url = f"{instance}/api/v1/{source}/{target}/{encoded}"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    raw = resp.read().decode("utf-8")

                # Detect HTML response (Lingva returns HTML when Google blocks the instance)
                if "text/html" in content_type or raw.strip().startswith("<!DOCTYPE"):
                    last_error = f"HTML response from {instance} (scraper blocked)"
                    logger.debug(f"Lingva {instance}: received HTML, skipping")
                    continue

                data = json.loads(raw)

                if "error" in data:
                    last_error = f"API error from {instance}: {data['error']}"
                    continue

                translation = data.get("translation", "")
                if translation:
                    return translation
                last_error = f"empty translation from {instance}"
                continue

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise RateLimitError("Lingva rate limited")
                last_error = f"HTTP {e.code} from {instance}"
                continue
            except urllib.error.URLError as e:
                last_error = f"URLError from {instance}: {e}"
                continue
            except json.JSONDecodeError as e:
                last_error = f"JSON parse error from {instance}: {e}"
                continue
            except Exception as e:
                last_error = f"Error from {instance}: {e}"
                continue

        raise ProviderUnavailableError(
            f"All Lingva instances failed. Last error: {last_error}"
        )
