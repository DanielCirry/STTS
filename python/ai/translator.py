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

        # Step 4: Load tokenizer
        try:
            logger.debug(f"[translate] Step 4: Loading tokenizer for {hf_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(hf_name)
            logger.debug(f"[translate] Step 4: Tokenizer loaded. Vocab size: {self.tokenizer.vocab_size}")
        except Exception as e:
            self.last_error = f"Failed to load tokenizer: {type(e).__name__}: {e}"
            logger.error(f"[translate] {self.last_error}")
            logger.error(f"[translate] Tokenizer traceback:\n{traceback.format_exc()}")
            self.tokenizer = None
            self.model = None
            return False

        # Step 5: Load model (use safetensors to avoid torch.load CVE-2025-32434)
        try:
            logger.debug(f"[translate] Step 5: Loading model {hf_name} on {device} (safetensors)...")
            kwargs = {'use_safetensors': True}
            if device == 'cuda':
                kwargs['dtype'] = torch.float16
            self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name, **kwargs)
            self.model = self.model.to(device)

            self.model_name = model_name
            param_count = sum(p.numel() for p in self.model.parameters())
            logger.info(f"[translate] Step 5: Model loaded! {model_name} ({param_count:,} params) on {device}")
            return True

        except Exception as e:
            self.last_error = f"Failed to load model weights: {type(e).__name__}: {e}"
            logger.error(f"[translate] {self.last_error}")
            logger.error(f"[translate] Model load traceback:\n{traceback.format_exc()}")
            self.model = None
            self.tokenizer = None
            return False

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
