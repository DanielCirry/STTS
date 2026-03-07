"""STTS AI Assistant module - Local and Cloud LLM providers."""

from ai.assistant.base import AIProvider, AssistantConfig, AssistantResponse, Message, truncate_response
from ai.assistant.local_llm import LocalLLMProvider, RECOMMENDED_MODELS
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
from ai.assistant.manager import AIAssistantManager
from ai.assistant.fallback import FallbackAIManager

__all__ = [
    'AIProvider',
    'AssistantConfig',
    'AssistantResponse',
    'Message',
    'truncate_response',
    'LocalLLMProvider',
    'FreeProvider',
    'RECOMMENDED_MODELS',
    'OpenAIProvider',
    'AnthropicProvider',
    'GroqProvider',
    'GoogleProvider',
    'get_api_key',
    'set_api_key',
    'delete_api_key',
    'AIAssistantManager',
    'FallbackAIManager',
]
