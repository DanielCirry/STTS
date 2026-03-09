"""
AI Assistant Manager
Unified interface for managing AI providers and keyword detection
"""

import logging
import re
from typing import Callable, Dict, List, Optional

from ai.assistant.base import AIProvider, AssistantConfig, AssistantResponse
from ai.assistant.local_llm import LocalLLMProvider
from ai.assistant.cloud_providers import (
    OpenAIProvider,
    AnthropicProvider,
    GroqProvider,
    GoogleProvider,
    get_api_key,
    set_api_key,
    delete_api_key
)
from ai.assistant.free_provider import FreeProvider

logger = logging.getLogger('stts.assistant.manager')


class AIAssistantManager:
    """Manages AI providers and handles keyword-triggered queries."""

    def __init__(self):
        self._providers: Dict[str, AIProvider] = {}
        self._current_provider: Optional[str] = None
        self._keyword: str = "jarvis"
        self._keyword_pattern: Optional[re.Pattern] = None
        self._config = AssistantConfig()

        # Callbacks
        self.on_response: Optional[Callable[[AssistantResponse], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Initialize available providers
        self._init_providers()
        self._compile_keyword_pattern()

    def _init_providers(self):
        """Initialize all available AI providers."""
        # Local LLM
        try:
            local = LocalLLMProvider()
            self._providers['local'] = local
            if local.is_available():
                logger.debug("Local LLM provider available")
            else:
                logger.debug("Local LLM provider registered (llama-cpp-python not installed)")
        except Exception as e:
            logger.warning(f"Local LLM provider failed to initialize: {e}")

        # OpenAI
        try:
            openai = OpenAIProvider()
            self._providers['openai'] = openai
            if openai.is_available():
                logger.debug("OpenAI provider available (key configured)")
            else:
                logger.debug("OpenAI provider registered (key not configured)")
        except Exception as e:
            logger.warning(f"OpenAI provider error: {e}")

        # Anthropic
        try:
            anthropic = AnthropicProvider()
            self._providers['anthropic'] = anthropic
            if anthropic.is_available():
                logger.debug("Anthropic provider available (key configured)")
            else:
                logger.debug("Anthropic provider registered (key not configured)")
        except Exception as e:
            logger.warning(f"Anthropic provider error: {e}")

        # Groq
        try:
            groq = GroqProvider()
            self._providers['groq'] = groq
            if groq.is_available():
                logger.debug("Groq provider available (key configured)")
            else:
                logger.debug("Groq provider registered (key not configured)")
        except Exception as e:
            logger.warning(f"Groq provider error: {e}")

        # Google
        try:
            google = GoogleProvider()
            self._providers['google'] = google
            if google.is_available():
                logger.debug("Google provider available (key configured)")
            else:
                logger.debug("Google provider registered (key not configured)")
        except Exception as e:
            logger.warning(f"Google provider error: {e}")

        # Free provider (DuckDuckGo AI Chat - no API key needed)
        try:
            free = FreeProvider()
            self._providers['free'] = free
            logger.debug("Free AI provider available (no API key needed)")
        except Exception as e:
            logger.warning(f"Free provider error: {e}")

        # Set default provider - prefer free (no setup), then local, then cloud
        if 'free' in self._providers:
            self._current_provider = 'free'
        elif 'local' in self._providers:
            self._current_provider = 'local'
        elif 'groq' in self._providers and self._providers['groq'].is_available():
            self._current_provider = 'groq'
        elif 'openai' in self._providers and self._providers['openai'].is_available():
            self._current_provider = 'openai'

    def _compile_keyword_pattern(self):
        """Compile regex pattern for keyword detection."""
        # Match keyword at start of sentence or after punctuation
        # Case-insensitive, allows for variations
        keyword = re.escape(self._keyword)
        self._keyword_pattern = re.compile(
            rf'(?:^|[.!?]\s*){keyword}[,:]?\s*(.*)',
            re.IGNORECASE | re.DOTALL
        )

    def set_keyword(self, keyword: str):
        """Set the trigger keyword.

        Args:
            keyword: Keyword to trigger AI assistant
        """
        self._keyword = keyword.lower()
        self._compile_keyword_pattern()
        logger.debug(f"AI keyword set to: {keyword}")

    def check_keyword(self, text: str) -> Optional[str]:
        """Check if text contains the trigger keyword.

        Args:
            text: Text to check

        Returns:
            Query text if keyword found, None otherwise
        """
        if not self._keyword_pattern:
            return None

        # Check for keyword
        match = self._keyword_pattern.search(text)
        if match:
            query = match.group(1).strip()
            if query:
                return query

            # Also check simple keyword presence
            text_lower = text.lower()
            if self._keyword in text_lower:
                # Extract everything after keyword
                idx = text_lower.find(self._keyword)
                query = text[idx + len(self._keyword):].strip(' ,.:')
                if query:
                    return query

        return None

    def get_available_providers(self) -> List[Dict[str, str]]:
        """Get list of available AI providers.

        Returns:
            List of provider info dicts
        """
        providers = []
        for name, provider in self._providers.items():
            providers.append({
                'id': name,
                'name': provider.name,
                'is_online': provider.is_online,
                'is_available': provider.is_available(),
                'is_loaded': getattr(provider, 'is_loaded', provider.is_available())
            })
        return providers

    def get_current_provider(self) -> Optional[str]:
        """Get current provider ID."""
        return self._current_provider

    def set_provider(self, provider_id: str) -> bool:
        """Set the current AI provider.

        Args:
            provider_id: Provider ID

        Returns:
            True if successful
        """
        if provider_id not in self._providers:
            logger.error(f"Unknown provider: {provider_id}")
            return False

        self._current_provider = provider_id
        logger.info(f"AI provider set to: {provider_id}")
        return True

    def set_api_key(self, provider_id: str, api_key: str) -> bool:
        """Set API key for a provider.

        Args:
            provider_id: Provider ID
            api_key: API key

        Returns:
            True if successful
        """
        if provider_id not in self._providers:
            return False

        provider = self._providers[provider_id]
        if hasattr(provider, 'set_api_key'):
            provider.set_api_key(api_key, save=True)
            return True
        return False

    def has_api_key(self, provider_id: str) -> bool:
        """Check if provider has API key configured.

        Args:
            provider_id: Provider ID

        Returns:
            True if API key is configured
        """
        return get_api_key(provider_id) is not None

    def delete_api_key(self, provider_id: str) -> bool:
        """Delete API key for a provider.

        Args:
            provider_id: Provider ID

        Returns:
            True if successful
        """
        return delete_api_key(provider_id)

    def set_config(self, config: AssistantConfig):
        """Set configuration for all providers.

        Args:
            config: Assistant configuration
        """
        self._config = config
        for provider in self._providers.values():
            provider.config = config

    def update_config(self, **kwargs):
        """Update specific config values.

        Args:
            **kwargs: Config fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

        for provider in self._providers.values():
            provider.config = self._config

    async def load_local_model(self, model_path: str) -> bool:
        """Load a local LLM model.

        Args:
            model_path: Path to GGUF model file

        Returns:
            True if successful
        """
        if 'local' not in self._providers:
            return False

        provider = self._providers['local']
        if isinstance(provider, LocalLLMProvider):
            # Let exceptions propagate so error messages reach the frontend
            return provider.load_model(model_path)
        return False

    async def generate(self, prompt: str, provider_id: Optional[str] = None) -> AssistantResponse:
        """Generate an AI response.

        Args:
            prompt: User prompt
            provider_id: Provider to use (or None for current)

        Returns:
            AssistantResponse with the generated content
        """
        if provider_id is None:
            provider_id = self._current_provider

        if provider_id is None or provider_id not in self._providers:
            raise RuntimeError("No AI provider available")

        provider = self._providers[provider_id]

        if not provider.is_available():
            raise RuntimeError(f"Provider {provider_id} is not available")

        try:
            response = await provider.generate(prompt)

            if self.on_response:
                self.on_response(response)

            return response

        except Exception as e:
            error_msg = str(e)
            logger.error(f"AI generation error: {error_msg}")

            if self.on_error:
                self.on_error(error_msg)

            raise

    def clear_conversation(self, provider_id: Optional[str] = None):
        """Clear conversation history.

        Args:
            provider_id: Provider to clear (or None for all)
        """
        if provider_id:
            if provider_id in self._providers:
                self._providers[provider_id].clear_conversation()
        else:
            for provider in self._providers.values():
                provider.clear_conversation()

    def get_local_models(self) -> List[Dict]:
        """Get list of available local models.

        Returns:
            List of model info dicts
        """
        if 'local' not in self._providers:
            return []

        provider = self._providers['local']
        if isinstance(provider, LocalLLMProvider):
            return provider.get_available_models()
        return []

    def set_local_models_directory(self, path: str) -> bool:
        """Set the local models directory.

        Args:
            path: Path to the models directory

        Returns:
            True if successful
        """
        if 'local' not in self._providers:
            return False

        provider = self._providers['local']
        if isinstance(provider, LocalLLMProvider):
            return provider.set_models_directory(path)
        return False

    def get_llm_status(self) -> Dict:
        """Get current local LLM status."""
        if 'local' not in self._providers:
            return {'loaded': False, 'model': None, 'model_path': None}
        provider = self._providers['local']
        if isinstance(provider, LocalLLMProvider):
            return {
                'loaded': provider.is_loaded,
                'model': provider.current_model,
                'model_path': str(provider._current_model_path) if getattr(provider, '_current_model_path', None) else None,
            }
        return {'loaded': False, 'model': None, 'model_path': None}

    def get_local_models_directory(self) -> str:
        """Get the current local models directory.

        Returns:
            Path to models directory
        """
        if 'local' not in self._providers:
            return ""

        provider = self._providers['local']
        if isinstance(provider, LocalLLMProvider):
            return str(provider._models_dir)
        return ""

    def cleanup(self):
        """Clean up resources."""
        for provider in self._providers.values():
            provider.cleanup()
        self._providers.clear()
