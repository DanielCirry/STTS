"""
AI Assistant Base Interface
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger('stts.assistant.base')


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # 'user', 'assistant', or 'system'
    content: str


@dataclass
class AssistantConfig:
    """Configuration for AI assistant."""
    system_prompt: str = "You are a helpful AI assistant integrated into a VRChat companion app. Keep responses concise and friendly."
    max_response_length: int = 140  # VRChat chatbox limit
    temperature: float = 0.7
    max_tokens: int = 150
    context_messages: int = 10  # Number of previous messages to include


@dataclass
class AssistantResponse:
    """Response from the AI assistant."""
    content: str
    tokens_used: int = 0
    model: Optional[str] = None
    truncated: bool = False


class AIProvider(ABC):
    """Base class for AI providers."""

    def __init__(self):
        self.name: str = "base"
        self.is_online: bool = False
        self.is_loaded: bool = False
        self._config = AssistantConfig()
        self._conversation: List[Message] = []
        self._on_token: Optional[Callable[[str], None]] = None

    @property
    def config(self) -> AssistantConfig:
        """Get current configuration."""
        return self._config

    @config.setter
    def config(self, value: AssistantConfig):
        """Set configuration."""
        self._config = value

    def set_token_callback(self, callback: Callable[[str], None]):
        """Set callback for streaming token updates."""
        self._on_token = callback

    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self._conversation.append(Message(role=role, content=content))

        # Trim to max context
        max_messages = self._config.context_messages
        if len(self._conversation) > max_messages:
            self._conversation = self._conversation[-max_messages:]

    def clear_conversation(self):
        """Clear the conversation history."""
        self._conversation = []

    def get_conversation(self) -> List[Message]:
        """Get the conversation history."""
        return self._conversation.copy()

    @abstractmethod
    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response to the given prompt.

        Args:
            prompt: User input

        Returns:
            AssistantResponse with the generated content
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and ready to use.

        Returns:
            True if available
        """
        pass

    def cleanup(self):
        """Clean up provider resources."""
        pass


def truncate_response(text: str, max_length: int = 140) -> tuple[str, bool]:
    """Truncate response to fit VRChat chatbox limit.

    Args:
        text: Response text
        max_length: Maximum length

    Returns:
        Tuple of (truncated text, was truncated)
    """
    if len(text) <= max_length:
        return text, False

    # Try to truncate at sentence boundary
    truncated = text[:max_length]

    # Find last sentence end
    for end_char in ['. ', '! ', '? ']:
        pos = truncated.rfind(end_char)
        if pos > max_length // 2:
            return truncated[:pos + 1].strip(), True

    # Fall back to word boundary
    space_pos = truncated.rfind(' ')
    if space_pos > max_length // 2:
        return truncated[:space_pos].strip() + '...', True

    # Hard truncate
    return truncated[:max_length - 3] + '...', True
