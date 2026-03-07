"""
Free AI Provider using Pollinations.ai (OpenAI-compatible, no API key needed).
"""

import logging
import aiohttp
from typing import Optional

from ai.assistant.base import AIProvider, AssistantResponse, truncate_response

logger = logging.getLogger('stts.assistant.free')

POLLINATIONS_URL = "https://text.pollinations.ai/openai/chat/completions"

# Models available on Pollinations (free, no key)
FREE_MODELS = {
    "openai": "openai",
    "gpt-4o-mini": "openai",
    "mistral": "mistral",
    "llama": "llama",
    "deepseek": "deepseek",
    "qwen": "qwen",
}


class FreeProvider(AIProvider):
    """Free AI provider via Pollinations.ai (no API key needed)."""

    def __init__(self):
        super().__init__()
        self.name = "free"
        self.is_online = True
        self._model = "openai"

    def set_model(self, model: str):
        self._model = model

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response using Pollinations.ai."""
        self.add_message('user', prompt)

        try:
            messages = [{'role': 'system', 'content': self._config.system_prompt}]
            for msg in self._conversation:
                messages.append({'role': msg.role, 'content': msg.content})

            model_id = FREE_MODELS.get(self._model, self._model)

            payload = {
                "model": model_id,
                "messages": messages,
                "max_tokens": self._config.max_tokens,
                "temperature": self._config.temperature,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    POLLINATIONS_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(f"Pollinations API error {resp.status}: {body[:200]}")

                    data = await resp.json()

            content = data["choices"][0]["message"]["content"]
            if not content:
                raise RuntimeError("Empty response from free AI provider")

            content = content.strip()
            content, truncated = truncate_response(content, self._config.max_response_length)

            self.add_message('assistant', content)

            return AssistantResponse(
                content=content,
                tokens_used=0,
                model=f"free:{data.get('model', self._model)}",
                truncated=truncated
            )

        except Exception as e:
            # Remove the user message we added since we failed
            if self._conversation and self._conversation[-1].role == 'user':
                self._conversation.pop()
            logger.error(f"Free provider error: {e}")
            raise

    def is_available(self) -> bool:
        return True
