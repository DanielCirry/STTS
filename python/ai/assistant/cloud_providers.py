"""
Cloud AI Providers
OpenAI, Anthropic, Groq, and Google Gemini integrations
"""

import logging
from typing import Optional

import keyring

from ai.assistant.base import AIProvider, AssistantResponse, truncate_response

logger = logging.getLogger('stts.assistant.cloud')

# Service name for keyring
KEYRING_SERVICE = "STTS"


def get_api_key(provider: str) -> Optional[str]:
    """Get API key from secure storage.

    Args:
        provider: Provider name (openai, anthropic, groq, google)

    Returns:
        API key or None if not found
    """
    try:
        return keyring.get_password(KEYRING_SERVICE, f"{provider}_api_key")
    except Exception as e:
        logger.error(f"Error getting API key for {provider}: {e}")
        return None


def set_api_key(provider: str, api_key: str) -> bool:
    """Store API key in secure storage.

    Args:
        provider: Provider name
        api_key: API key to store

    Returns:
        True if successful
    """
    try:
        keyring.set_password(KEYRING_SERVICE, f"{provider}_api_key", api_key)
        return True
    except Exception as e:
        logger.error(f"Error storing API key for {provider}: {e}")
        return False


def delete_api_key(provider: str) -> bool:
    """Delete API key from secure storage.

    Args:
        provider: Provider name

    Returns:
        True if successful
    """
    try:
        keyring.delete_password(KEYRING_SERVICE, f"{provider}_api_key")
        return True
    except Exception as e:
        logger.error(f"Error deleting API key for {provider}: {e}")
        return False


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.name = "openai"
        self.is_online = True
        self._api_key = api_key or get_api_key("openai")
        self._client = None
        self._model = "gpt-4o-mini"

    def set_api_key(self, api_key: str, save: bool = True):
        """Set the API key.

        Args:
            api_key: OpenAI API key
            save: If True, save to secure storage
        """
        self._api_key = api_key
        self._client = None  # Reset client
        if save:
            set_api_key("openai", api_key)

    def set_model(self, model: str):
        """Set the model to use.

        Args:
            model: Model name (e.g., 'gpt-4o-mini', 'gpt-4o')
        """
        self._model = model

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("OpenAI API key not set")

            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)

        return self._client

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response using OpenAI API.

        Args:
            prompt: User input

        Returns:
            AssistantResponse with the generated content
        """
        client = self._get_client()

        # Add user message to conversation
        self.add_message('user', prompt)

        try:
            # Build messages
            messages = [{'role': 'system', 'content': self._config.system_prompt}]
            for msg in self._conversation:
                messages.append({'role': msg.role, 'content': msg.content})

            # Make API request
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature
            )

            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Truncate for VRChat
            content, truncated = truncate_response(content, self._config.max_response_length)

            # Add assistant response to conversation
            self.add_message('assistant', content)

            return AssistantResponse(
                content=content,
                tokens_used=tokens_used,
                model=self._model,
                truncated=truncated
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        try:
            from openai import AsyncOpenAI
            return self._api_key is not None
        except ImportError:
            return False


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.name = "anthropic"
        self.is_online = True
        self._api_key = api_key or get_api_key("anthropic")
        self._client = None
        self._model = "claude-3-haiku-20240307"

    def set_api_key(self, api_key: str, save: bool = True):
        """Set the API key."""
        self._api_key = api_key
        self._client = None
        if save:
            set_api_key("anthropic", api_key)

    def set_model(self, model: str):
        """Set the model to use."""
        self._model = model

    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("Anthropic API key not set")

            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self._api_key)

        return self._client

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response using Anthropic API."""
        client = self._get_client()

        # Add user message to conversation
        self.add_message('user', prompt)

        try:
            # Build messages (Anthropic doesn't use system in messages)
            messages = []
            for msg in self._conversation:
                messages.append({'role': msg.role, 'content': msg.content})

            # Make API request
            response = await client.messages.create(
                model=self._model,
                system=self._config.system_prompt,
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature
            )

            content = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Truncate for VRChat
            content, truncated = truncate_response(content, self._config.max_response_length)

            # Add assistant response to conversation
            self.add_message('assistant', content)

            return AssistantResponse(
                content=content,
                tokens_used=tokens_used,
                model=self._model,
                truncated=truncated
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        try:
            from anthropic import AsyncAnthropic
            return self._api_key is not None
        except ImportError:
            return False


class GroqProvider(AIProvider):
    """Groq API provider (fast inference)."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.name = "groq"
        self.is_online = True
        self._api_key = api_key or get_api_key("groq")
        self._client = None
        self._model = "llama-3.1-8b-instant"

    def set_api_key(self, api_key: str, save: bool = True):
        """Set the API key."""
        self._api_key = api_key
        self._client = None
        if save:
            set_api_key("groq", api_key)

    def set_model(self, model: str):
        """Set the model to use."""
        self._model = model

    def _get_client(self):
        """Get or create Groq client."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("Groq API key not set")

            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=self._api_key)

        return self._client

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response using Groq API."""
        client = self._get_client()

        # Add user message to conversation
        self.add_message('user', prompt)

        try:
            # Build messages
            messages = [{'role': 'system', 'content': self._config.system_prompt}]
            for msg in self._conversation:
                messages.append({'role': msg.role, 'content': msg.content})

            # Make API request
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature
            )

            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Truncate for VRChat
            content, truncated = truncate_response(content, self._config.max_response_length)

            # Add assistant response to conversation
            self.add_message('assistant', content)

            return AssistantResponse(
                content=content,
                tokens_used=tokens_used,
                model=self._model,
                truncated=truncated
            )

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Groq is available."""
        try:
            from groq import AsyncGroq
            return self._api_key is not None
        except ImportError:
            return False


class GoogleProvider(AIProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.name = "google"
        self.is_online = True
        self._api_key = api_key or get_api_key("google")
        self._client = None
        self._model = "gemini-1.5-flash"

    def set_api_key(self, api_key: str, save: bool = True):
        """Set the API key."""
        self._api_key = api_key
        self._client = None
        if save:
            set_api_key("google", api_key)

    def set_model(self, model: str):
        """Set the model to use."""
        self._model = model

    def _get_client(self):
        """Get or create Google Generative AI client."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("Google API key not set")

            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(
                self._model,
                system_instruction=self._config.system_prompt
            )

        return self._client

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response using Google Gemini API."""
        client = self._get_client()

        # Add user message to conversation
        self.add_message('user', prompt)

        try:
            # Build conversation history
            history = []
            for msg in self._conversation[:-1]:  # Exclude last (current) message
                role = 'user' if msg.role == 'user' else 'model'
                history.append({'role': role, 'parts': [msg.content]})

            # Start chat with history
            chat = client.start_chat(history=history)

            # Generate response
            response = await chat.send_message_async(
                prompt,
                generation_config={
                    'max_output_tokens': self._config.max_tokens,
                    'temperature': self._config.temperature
                }
            )

            content = response.text.strip()

            # Truncate for VRChat
            content, truncated = truncate_response(content, self._config.max_response_length)

            # Add assistant response to conversation
            self.add_message('assistant', content)

            return AssistantResponse(
                content=content,
                tokens_used=0,  # Gemini doesn't always report tokens
                model=self._model,
                truncated=truncated
            )

        except Exception as e:
            logger.error(f"Google Gemini API error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Google Gemini is available."""
        try:
            import google.generativeai
            return self._api_key is not None
        except ImportError:
            return False
