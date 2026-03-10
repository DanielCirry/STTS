"""
Translation module using Facebook NLLB (No Language Left Behind)
Supports 200+ languages with local inference
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger('stts.translator')

# NLLB language codes for common languages
# Full list: https://github.com/facebookresearch/fairseq/tree/nllb
LANGUAGE_CODES: Dict[str, str] = {
    # Major languages
    'en': 'eng_Latn',      # English
    'ja': 'jpn_Jpan',      # Japanese
    'zh': 'zho_Hans',      # Chinese (Simplified)
    'zh-tw': 'zho_Hant',   # Chinese (Traditional)
    'ko': 'kor_Hang',      # Korean
    'es': 'spa_Latn',      # Spanish
    'fr': 'fra_Latn',      # French
    'de': 'deu_Latn',      # German
    'it': 'ita_Latn',      # Italian
    'pt': 'por_Latn',      # Portuguese
    'ru': 'rus_Cyrl',      # Russian
    'ar': 'arb_Arab',      # Arabic
    'hi': 'hin_Deva',      # Hindi
    'th': 'tha_Thai',      # Thai
    'vi': 'vie_Latn',      # Vietnamese
    'id': 'ind_Latn',      # Indonesian
    'ms': 'zsm_Latn',      # Malay
    'tl': 'tgl_Latn',      # Tagalog
    'nl': 'nld_Latn',      # Dutch
    'pl': 'pol_Latn',      # Polish
    'tr': 'tur_Latn',      # Turkish
    'uk': 'ukr_Cyrl',      # Ukrainian
    'cs': 'ces_Latn',      # Czech
    'sv': 'swe_Latn',      # Swedish
    'da': 'dan_Latn',      # Danish
    'fi': 'fin_Latn',      # Finnish
    'no': 'nob_Latn',      # Norwegian
    'el': 'ell_Grek',      # Greek
    'he': 'heb_Hebr',      # Hebrew
    'hu': 'hun_Latn',      # Hungarian
    'ro': 'ron_Latn',      # Romanian
    'bg': 'bul_Cyrl',      # Bulgarian
    'hr': 'hrv_Latn',      # Croatian
    'sk': 'slk_Latn',      # Slovak
    'sl': 'slv_Latn',      # Slovenian
    'et': 'est_Latn',      # Estonian
    'lv': 'lvs_Latn',      # Latvian
    'lt': 'lit_Latn',      # Lithuanian
}

# Reverse mapping for display names
LANGUAGE_NAMES: Dict[str, str] = {
    'eng_Latn': 'English',
    'jpn_Jpan': 'Japanese',
    'zho_Hans': 'Chinese (Simplified)',
    'zho_Hant': 'Chinese (Traditional)',
    'kor_Hang': 'Korean',
    'spa_Latn': 'Spanish',
    'fra_Latn': 'French',
    'deu_Latn': 'German',
    'ita_Latn': 'Italian',
    'por_Latn': 'Portuguese',
    'rus_Cyrl': 'Russian',
    'arb_Arab': 'Arabic',
    'hin_Deva': 'Hindi',
    'tha_Thai': 'Thai',
    'vie_Latn': 'Vietnamese',
    'ind_Latn': 'Indonesian',
    'zsm_Latn': 'Malay',
    'tgl_Latn': 'Tagalog',
    'nld_Latn': 'Dutch',
    'pol_Latn': 'Polish',
    'tur_Latn': 'Turkish',
    'ukr_Cyrl': 'Ukrainian',
    'ces_Latn': 'Czech',
    'swe_Latn': 'Swedish',
    'dan_Latn': 'Danish',
    'fin_Latn': 'Finnish',
    'nob_Latn': 'Norwegian',
    'ell_Grek': 'Greek',
    'heb_Hebr': 'Hebrew',
    'hun_Latn': 'Hungarian',
    'ron_Latn': 'Romanian',
    'bul_Cyrl': 'Bulgarian',
    'hrv_Latn': 'Croatian',
    'slk_Latn': 'Slovak',
    'slv_Latn': 'Slovenian',
    'est_Latn': 'Estonian',
    'lvs_Latn': 'Latvian',
    'lit_Latn': 'Lithuanian',
}

# Available NLLB models
NLLB_MODELS = {
    'nllb-200-distilled-600M': {
        'hf_name': 'facebook/nllb-200-distilled-600M',
        'size': '1.2 GB',
        'quality': 'Good',
    },
    'nllb-200-distilled-1.3B': {
        'hf_name': 'facebook/nllb-200-distilled-1.3B',
        'size': '2.6 GB',
        'quality': 'Better',
    },
    'nllb-200-3.3B': {
        'hf_name': 'facebook/nllb-200-3.3B',
        'size': '6.6 GB',
        'quality': 'Best',
    },
}


class Translator:
    """Translation using NLLB models."""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_name: Optional[str] = None
        self.device = 'cpu'
        self.last_error: Optional[str] = None

    def detect_device(self) -> Tuple[str, bool]:
        """Detect available compute device."""
        try:
            import torch
            if torch.cuda.is_available():
                return 'cuda', True
        except ImportError:
            pass
        return 'cpu', False

    def load_model(self, model_name: str = 'nllb-200-distilled-600M', device: Optional[str] = None) -> bool:
        """Load an NLLB model.

        Args:
            model_name: Model identifier (e.g., 'nllb-200-distilled-600M')
            device: Device to use (cpu, cuda, or None for auto)

        Returns:
            True if successful
        """
        import traceback
        self.last_error = None

        # Step 1: Import dependencies
        try:
            import torch
            logger.debug(f"[translate] Step 1a: PyTorch version: {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
        except Exception as e:
            self.last_error = f"Missing dependency: torch - {e}"
            logger.error(f"[translate] {self.last_error}")
            return False

        try:
            import transformers
            logger.debug(f"[translate] Step 1b: Transformers version: {transformers.__version__}")
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except Exception as e:
            self.last_error = f"Missing dependency: transformers - {e}"
            logger.error(f"[translate] {self.last_error}")
            return False

        try:
            import sentencepiece
            logger.debug(f"[translate] Step 1c: SentencePiece version: {sentencepiece.__version__}")
        except ImportError as e:
            self.last_error = f"Missing dependency: sentencepiece (required for NLLB tokenizer) - {e}"
            logger.error(f"[translate] {self.last_error}")
            return False

        # Step 2: Resolve model name
        if model_name not in NLLB_MODELS:
            hf_name = model_name
            logger.debug(f"[translate] Step 2: Using model name directly as HuggingFace ID: {hf_name}")
        else:
            hf_name = NLLB_MODELS[model_name]['hf_name']
            logger.debug(f"[translate] Step 2: Resolved '{model_name}' -> '{hf_name}' (size: {NLLB_MODELS[model_name]['size']})")

        # Step 3: Determine device
        if device is None or device == 'auto':
            device, has_cuda = self.detect_device()
            logger.debug(f"[translate] Step 3: Auto-detected device: {device} (CUDA available: {has_cuda})")
        else:
            # Validate CUDA availability — fall back to CPU if not available
            if device == 'cuda':
                _, cuda_ok = self.detect_device()
                if not cuda_ok:
                    logger.warning("[translate] CUDA requested but not available, falling back to CPU")
                    device = 'cpu'
            logger.debug(f"[translate] Step 3: Using specified device: {device}")
        self.device = device

        # Step 4: Load tokenizer (retry once on corruption by clearing cache)
        try:
            logger.debug(f"[translate] Step 4: Loading tokenizer for {hf_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(hf_name)
            logger.debug(f"[translate] Step 4: Tokenizer loaded. Vocab size: {self.tokenizer.vocab_size}")
        except (OSError, ValueError, RuntimeError) as e:
            # Likely corrupted/incomplete download — clear cache and retry once
            logger.warning(f"[translate] Step 4: Tokenizer load failed, attempting cache repair: {e}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(hf_name, force_download=True)
                logger.info(f"[translate] Step 4: Tokenizer loaded after re-download. Vocab size: {self.tokenizer.vocab_size}")
            except Exception as retry_e:
                self.last_error = f"Failed to load tokenizer (even after re-download): {type(retry_e).__name__}: {retry_e}"
                logger.error(f"[translate] {self.last_error}")
                logger.error(f"[translate] Tokenizer traceback:\n{traceback.format_exc()}")
                self.tokenizer = None
                self.model = None
                return False
        except Exception as e:
            self.last_error = f"Failed to load tokenizer: {type(e).__name__}: {e}"
            logger.error(f"[translate] {self.last_error}")
            logger.error(f"[translate] Tokenizer traceback:\n{traceback.format_exc()}")
            self.tokenizer = None
            self.model = None
            return False

        # Step 5: Load model — try safetensors first, fall back to pytorch .bin
        try:
            logger.debug(f"[translate] Step 5: Loading model {hf_name} on {device}...")
            kwargs = {}
            if device == 'cuda':
                kwargs['dtype'] = torch.float16

            # Try safetensors first, then fall back to regular pytorch format
            load_attempts = [
                {'use_safetensors': True, **kwargs},
                {'use_safetensors': False, **kwargs},
            ]
            load_ok = False
            for attempt_idx, attempt_kwargs in enumerate(load_attempts):
                fmt = 'safetensors' if attempt_kwargs.get('use_safetensors') else 'pytorch'
                try:
                    logger.debug(f"[translate] Step 5: Trying {fmt} format (attempt {attempt_idx + 1})...")
                    self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name, **attempt_kwargs)
                    self.model = self.model.to(device)
                    if self._verify_model_integrity(model_name):
                        load_ok = True
                        break
                    else:
                        logger.warning(f"[translate] Step 5: {fmt} format loaded but integrity check FAILED")
                        self.model = None
                except Exception as fmt_e:
                    logger.warning(f"[translate] Step 5: {fmt} format failed: {fmt_e}")
                    self.model = None

            if not load_ok:
                # All formats failed — nuke entire cache and force re-download
                logger.warning("[translate] Step 5: All formats failed integrity — deleting cache and re-downloading...")
                self.model = None
                self._delete_hf_cache(hf_name)
                # Also delete tokenizer cache to ensure clean slate
                for attempt_kwargs in load_attempts:
                    fmt = 'safetensors' if attempt_kwargs.get('use_safetensors') else 'pytorch'
                    try:
                        logger.info(f"[translate] Step 5: Force re-download ({fmt})...")
                        self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name, force_download=True, **attempt_kwargs)
                        self.model = self.model.to(device)
                        if self._verify_model_integrity(model_name):
                            load_ok = True
                            break
                        else:
                            logger.warning(f"[translate] Step 5: Re-downloaded {fmt} still failed integrity")
                            self.model = None
                    except Exception as retry_e:
                        logger.warning(f"[translate] Step 5: Re-download {fmt} failed: {retry_e}")
                        self.model = None

            if not load_ok:
                self.last_error = f"Model {model_name} corrupted — all download attempts failed. Try deleting ~/.cache/huggingface and reinstalling."
                logger.error(f"[translate] {self.last_error}")
                self.model = None
                self.tokenizer = None
                return False

            self.model_name = model_name
            param_count = sum(p.numel() for p in self.model.parameters())
            logger.info(f"[translate] Step 5: Model loaded! {model_name} ({param_count:,} params) on {device}")
            return True

        except Exception as e:
            self.last_error = f"Failed to load model: {type(e).__name__}: {e}"
            logger.error(f"[translate] {self.last_error}")
            logger.error(f"[translate] Model load traceback:\n{traceback.format_exc()}")
            self.model = None
            self.tokenizer = None
            return False

    def _verify_model_integrity(self, model_name: str) -> bool:
        """Verify loaded model weights are not corrupted (all zeros, missing, or NaN).

        Returns True if model appears healthy, False if corrupted.
        Detects: empty models, all-zero weights, NaN weights, and models where
        checkpoint had no actual weight data (all keys MISSING from checkpoint).
        """
        if self.model is None:
            logger.error("[translate] Integrity check: model is None")
            return False

        import torch

        total_params = 0
        zero_params = 0
        nan_params = 0
        named_count = 0

        for name, param in self.model.named_parameters():
            named_count += 1
            numel = param.numel()
            total_params += numel
            if torch.all(param == 0).item():
                zero_params += numel
            if torch.any(torch.isnan(param)).item():
                nan_params += numel

        logger.info(f"[translate] Integrity check for {model_name}: "
                     f"{named_count} layers, {total_params:,} total params, "
                     f"{zero_params:,} zero params, {nan_params:,} NaN params")

        if total_params == 0:
            logger.error("[translate] Integrity check FAILED: model has 0 parameters")
            return False

        # If >90% of parameters are zero, model is likely corrupted
        zero_ratio = zero_params / total_params if total_params > 0 else 1.0
        if zero_ratio > 0.9:
            logger.error(f"[translate] Integrity check FAILED: {zero_ratio:.1%} of params are zero — model likely corrupted")
            return False

        if nan_params > 0:
            logger.error(f"[translate] Integrity check FAILED: {nan_params:,} NaN parameters detected")
            return False

        # Sanity check: NLLB-600M should have at least 100M params
        if total_params < 100_000_000:
            logger.error(f"[translate] Integrity check FAILED: only {total_params:,} params — too small for NLLB (expect >100M)")
            return False

        # Check for "all weights missing from checkpoint" — when from_pretrained
        # loads architecture but no weights, params are random init. Detect by
        # checking that the embedding weights have reasonable magnitude.
        # Trained NLLB embeddings have mean magnitude ~0.01-0.1; random init from
        # nn.Embedding has much larger variance.
        try:
            # Find embedding layer
            embed = None
            for name, param in self.model.named_parameters():
                if 'embed_tokens.weight' in name:
                    embed = param
                    break
            if embed is not None:
                mean_abs = embed.abs().mean().item()
                std_val = embed.std().item()
                logger.info(f"[translate] Integrity: embed mean_abs={mean_abs:.6f}, std={std_val:.6f}")
                # Trained NLLB embeddings: mean_abs ~0.02-0.08, std ~0.02-0.10
                # Random init (missing weights): mean_abs ~0.5-1.0, std ~0.5-1.0
                if mean_abs > 0.3 or std_val > 0.3:
                    logger.error(f"[translate] Integrity check FAILED: embedding weights look randomly initialized "
                                 f"(mean_abs={mean_abs:.4f}, std={std_val:.4f}) — checkpoint likely had no data")
                    return False
        except Exception as e:
            logger.warning(f"[translate] Integrity: embedding check skipped: {e}")

        logger.info(f"[translate] Integrity check PASSED for {model_name}")
        return True

    def _delete_hf_cache(self, hf_name: str):
        """Delete the HuggingFace cache directory for a model.

        Converts 'facebook/nllb-200-distilled-600M' to the cache path
        '~/.cache/huggingface/hub/models--facebook--nllb-200-distilled-600M'
        and removes it entirely so a fresh download can succeed.
        """
        import shutil
        from pathlib import Path

        cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'
        # HF cache uses 'models--org--name' format
        folder_name = 'models--' + hf_name.replace('/', '--')
        model_cache = cache_dir / folder_name

        if model_cache.exists():
            try:
                shutil.rmtree(model_cache)
                logger.info(f"[translate] Deleted corrupt cache: {model_cache}")
            except Exception as e:
                logger.warning(f"[translate] Failed to delete cache {model_cache}: {e}")
        else:
            logger.debug(f"[translate] No cache to delete at {model_cache}")

    def unload_model(self):
        """Unload the current model."""
        self.model = None
        self.tokenizer = None
        self.model_name = None
        logger.info("Translation model unloaded")

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        max_length: int = 256
    ) -> str:
        """Translate text between languages.

        Args:
            text: Text to translate
            source_lang: Source language code (e.g., 'eng_Latn' or 'en')
            target_lang: Target language code (e.g., 'jpn_Jpan' or 'ja')
            max_length: Maximum output length

        Returns:
            Translated text
        """
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not loaded")

        # Convert short codes to NLLB codes if needed
        if source_lang in LANGUAGE_CODES:
            source_lang = LANGUAGE_CODES[source_lang]
        if target_lang in LANGUAGE_CODES:
            target_lang = LANGUAGE_CODES[target_lang]

        try:
            import torch

            # Set source language
            self.tokenizer.src_lang = source_lang

            # Tokenize input
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate translation
            with torch.no_grad():
                generated_tokens = self.model.generate(
                    **inputs,
                    forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(target_lang),
                    max_length=max_length,
                    num_beams=4,
                    early_stopping=True
                )

            # Decode output
            translated = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

            logger.debug(f"Translated: '{text[:50]}...' -> '{translated[:50]}...'")
            return translated

        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        max_length: int = 256
    ) -> List[str]:
        """Translate multiple texts.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code
            max_length: Maximum output length per text

        Returns:
            List of translated texts
        """
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not loaded")

        # Convert short codes to NLLB codes if needed
        if source_lang in LANGUAGE_CODES:
            source_lang = LANGUAGE_CODES[source_lang]
        if target_lang in LANGUAGE_CODES:
            target_lang = LANGUAGE_CODES[target_lang]

        try:
            import torch

            # Set source language
            self.tokenizer.src_lang = source_lang

            # Tokenize inputs
            inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate translations
            with torch.no_grad():
                generated_tokens = self.model.generate(
                    **inputs,
                    forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(target_lang),
                    max_length=max_length,
                    num_beams=4,
                    early_stopping=True
                )

            # Decode outputs
            translated = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)

            return translated

        except Exception as e:
            logger.error(f"Batch translation error: {e}")
            raise

    @staticmethod
    def get_supported_languages() -> List[Dict[str, str]]:
        """Get list of supported languages.

        Returns:
            List of dicts with 'code' and 'name' keys
        """
        return [
            {'code': code, 'name': name}
            for code, name in sorted(LANGUAGE_NAMES.items(), key=lambda x: x[1])
        ]

    @staticmethod
    def get_language_name(code: str) -> str:
        """Get display name for a language code.

        Args:
            code: NLLB language code or short code

        Returns:
            Human-readable language name
        """
        # Convert short code if needed
        if code in LANGUAGE_CODES:
            code = LANGUAGE_CODES[code]

        return LANGUAGE_NAMES.get(code, code)

    @staticmethod
    def normalize_language_code(code: str) -> str:
        """Convert short language code to NLLB code.

        Args:
            code: Short code (e.g., 'en') or NLLB code

        Returns:
            NLLB language code
        """
        if code in LANGUAGE_CODES:
            return LANGUAGE_CODES[code]
        return code

    @property
    def is_loaded(self) -> bool:
        """Check if a model is loaded."""
        return self.model is not None

    @property
    def current_model(self) -> Optional[str]:
        """Get the name of the currently loaded model."""
        return self.model_name
