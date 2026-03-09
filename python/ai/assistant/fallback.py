"""
FallbackAIManager — Automatic provider fallback for AI assistant.

Wraps AIAssistantManager with priority-based provider selection,
rate limit handling, network error detection, and conversation
continuity across provider switches.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from ai.assistant.base import AssistantResponse, Message

logger = logging.getLogger('stts.assistant.fallback')

AI_PROVIDER_LABELS = {
    'free': 'Free',
    'local': 'local',
    'groq': 'Groq',
    'google': 'Gemini',
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
}

# Per-provider context window (number of messages to inject).
# Local LLM: 4 messages (2 turns) — small context, slow inference.
# Cloud providers: 10 messages (full context_messages default).
PROVIDER_CONTEXT_LIMITS = {
    'free': 6,
    'local': 4,
    'groq': 10,
    'google': 10,
    'openai': 10,
    'anthropic': 10,
}


class ProviderHealth(Enum):
    HEALTHY = "healthy"
    COOLING = "cooling"       # Temporary RPM limit — retry after cooldown_until
    EXHAUSTED = "exhausted"   # Daily limit — skip for rest of session


@dataclass
class ProviderState:
    health: ProviderHealth = ProviderHealth.HEALTHY
    cooldown_until: float = 0.0
    failure_count: int = 0
    last_error: Optional[str] = None

    def is_available(self) -> bool:
        if self.health == ProviderHealth.EXHAUSTED:
            return False
        if self.health == ProviderHealth.COOLING:
            if time.monotonic() >= self.cooldown_until:
                self.health = ProviderHealth.HEALTHY
                self.failure_count = 0
            else:
                return False
        return True

    def mark_rate_limited(self, retry_after: float, daily: bool = False):
        if daily:
            self.health = ProviderHealth.EXHAUSTED
        else:
            self.health = ProviderHealth.COOLING
            self.cooldown_until = time.monotonic() + max(retry_after, 5.0)
        self.failure_count += 1

    def mark_failure(self, retry_after: float = 30.0):
        self.health = ProviderHealth.COOLING
        self.cooldown_until = time.monotonic() + retry_after
        self.failure_count += 1

    def mark_healthy(self):
        self.health = ProviderHealth.HEALTHY
        self.failure_count = 0
        self.last_error = None


class FallbackAIManager:
    """Wraps AIAssistantManager with automatic provider fallback."""

    DEFAULT_PRIORITY = ['free', 'local', 'groq', 'google', 'openai', 'anthropic']
    CLOUD_TIMEOUT = 30.0            # Seconds per cloud provider attempt
    NETWORK_RETRY_INTERVAL = 60.0   # Seconds before retrying cloud after network loss

    FALLBACK_MESSAGES = [
        "[AI unavailable] Try again in a moment.",
        "[AI unavailable] All providers are busy.",
        "[AI unavailable] Cannot reach AI service right now.",
    ]

    def __init__(self, manager, notify_callback: Optional[Callable] = None):
        """Initialize FallbackAIManager.

        Args:
            manager: AIAssistantManager instance (holds _providers dict).
            notify_callback: Async callable(event_type: str, data: dict)
                             for broadcasting AI events to frontend.
        """
        self._manager = manager
        self._notify = notify_callback  # async callable(event_type, data)
        self._health: Dict[str, ProviderState] = {}
        self._priority: List[str] = list(self.DEFAULT_PRIORITY)
        self._active_provider: Optional[str] = None
        self._shared_conversation: List[Message] = []
        self._network_down: bool = False
        self._network_retry_at: float = 0.0

    def clear_conversation(self):
        """Clear shared conversation. Health states are NOT reset (per CONTEXT.md)."""
        self._shared_conversation.clear()

    def get_active_provider(self) -> Optional[str]:
        """Return the ID of the last successfully used provider."""
        return self._active_provider

    def _state(self, provider_id: str) -> ProviderState:
        """Lazy-init and return ProviderState for a given provider."""
        if provider_id not in self._health:
            self._health[provider_id] = ProviderState()
        return self._health[provider_id]

    def _get_candidates(self) -> List[str]:
        """Return priority-ordered list of healthy, available providers."""
        provider_info = {p['id']: p for p in self._manager.get_available_providers()}
        skip_cloud = self._network_down and time.monotonic() < self._network_retry_at

        candidates = []
        for pid in self._priority:
            info = provider_info.get(pid)
            if not info:
                continue
            # For local: check is_loaded (library installed != model loaded)
            if pid == 'local' and not info.get('is_loaded', False):
                continue
            # For cloud: check is_available (has API key)
            if pid != 'local' and not info.get('is_available'):
                continue
            # Skip cloud providers when network is known down
            if pid != 'local' and skip_cloud:
                continue
            if self._state(pid).is_available():
                candidates.append(pid)
        return candidates

    async def _emit(self, event_type: str, data: dict):
        """Safely emit an event via the notify callback."""
        if self._notify:
            try:
                await self._notify(event_type, data)
            except Exception as e:
                logger.warning(f"Notify error: {e}")

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response with automatic provider fallback.

        Tries providers in priority order. Rate limits, timeouts, and
        network errors trigger fallback to the next candidate.
        Application errors (bad prompt, model not found) are re-raised.

        Returns:
            AssistantResponse — model='fallback' when all providers fail.
        """
        candidates = self._get_candidates()

        # Sticky: prefer last successful provider
        if self._active_provider in candidates:
            candidates = [self._active_provider] + [
                p for p in candidates if p != self._active_provider
            ]

        if not candidates:
            msg = random.choice(self.FALLBACK_MESSAGES)
            await self._emit('ai_offline_mode', {
                'reason': 'all_providers_unavailable',
                'retry_in': self.NETWORK_RETRY_INTERVAL,
            })
            return AssistantResponse(
                content=msg, tokens_used=0, model='fallback', truncated=False
            )

        network_fail_count = 0

        for provider_id in candidates:
            provider_obj = self._manager._providers.get(provider_id)
            if not provider_obj:
                continue

            # Inject conversation history (with per-provider context limit)
            limit = PROVIDER_CONTEXT_LIMITS.get(provider_id, 10)
            provider_obj._conversation = list(self._shared_conversation[-limit:])

            try:
                # Apply timeout to cloud providers only
                if provider_id != 'local':
                    response = await asyncio.wait_for(
                        provider_obj.generate(prompt),
                        timeout=self.CLOUD_TIMEOUT
                    )
                else:
                    response = await provider_obj.generate(prompt)

                # --- SUCCESS ---
                self._shared_conversation = list(provider_obj._conversation)
                self._state(provider_id).mark_healthy()

                prev = self._active_provider
                self._active_provider = provider_id

                if prev and prev != provider_id:
                    prev_state = self._state(prev)
                    reason = (
                        f'{AI_PROVIDER_LABELS.get(prev, prev)} rate limited'
                        if prev_state.health == ProviderHealth.COOLING
                        else 'restored'
                    )
                    await self._emit('ai_provider_switched', {
                        'from': prev,
                        'to': provider_id,
                        'reason': reason,
                    })
                elif not prev:
                    # First successful call — tell StatusBar the initial provider
                    await self._emit('ai_provider_switched', {
                        'from': None,
                        'to': provider_id,
                        'reason': 'initial',
                    })

                if self._network_down:
                    self._network_down = False
                    await self._emit('ai_online_restored', {
                        'provider': provider_id,
                    })

                return response

            except asyncio.TimeoutError:
                # MUST catch BEFORE Exception (Python 3.11+ subclass issue)
                self._state(provider_id).mark_failure(retry_after=60.0)
                logger.warning(
                    f"{provider_id}: timeout after {self.CLOUD_TIMEOUT}s"
                )
                next_pids = [
                    p for p in candidates[candidates.index(provider_id) + 1:]
                ]
                if next_pids:
                    await self._emit('ai_provider_switched', {
                        'from': provider_id,
                        'to': next_pids[0],
                        'reason': f'{AI_PROVIDER_LABELS.get(provider_id, provider_id)} timed out',
                    })
                continue

            except Exception as exc:
                state = self._state(provider_id)

                if _is_rate_limit(exc):
                    retry_after = _get_retry_after(exc, default=60.0)
                    daily = _is_daily_limit(exc)
                    state.mark_rate_limited(retry_after, daily=daily)
                    reason = (
                        f'{AI_PROVIDER_LABELS.get(provider_id, provider_id)} daily limit reached'
                        if daily else
                        f'{AI_PROVIDER_LABELS.get(provider_id, provider_id)} rate limited'
                    )
                    logger.warning(f"{provider_id}: {reason}")
                    next_pids = [
                        p for p in candidates[candidates.index(provider_id) + 1:]
                    ]
                    if next_pids:
                        await self._emit('ai_provider_switched', {
                            'from': provider_id,
                            'to': next_pids[0],
                            'reason': reason,
                        })
                    continue

                elif _is_network_error(exc):
                    state.mark_failure(retry_after=30.0)
                    network_fail_count += 1
                    logger.warning(f"{provider_id}: network error: {exc}")
                    if network_fail_count >= 2 and not self._network_down:
                        self._network_down = True
                        self._network_retry_at = (
                            time.monotonic() + self.NETWORK_RETRY_INTERVAL
                        )
                        await self._emit('ai_offline_mode', {
                            'reason': 'network_unavailable',
                            'retry_in': self.NETWORK_RETRY_INTERVAL,
                        })
                    continue

                else:
                    # Application error — do NOT fallback, surface to caller
                    logger.error(f"{provider_id}: application error: {exc}")
                    raise

        # All providers exhausted
        msg = random.choice(self.FALLBACK_MESSAGES)
        return AssistantResponse(
            content=msg, tokens_used=0, model='fallback', truncated=False
        )


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------

def _is_rate_limit(exc: Exception) -> bool:
    """Check whether an exception indicates a rate-limit response."""
    status = getattr(exc, 'status_code', None)
    if status in (429, 529):
        return True
    try:
        import google.api_core.exceptions as gexc
        if isinstance(exc, gexc.ResourceExhausted):
            return True
    except ImportError:
        pass
    try:
        import anthropic
        if isinstance(exc, anthropic.OverloadedError):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return '429' in msg or 'rate limit' in msg or 'resource_exhausted' in msg


def _is_network_error(exc: Exception) -> bool:
    """Check whether an exception indicates a network / connectivity issue."""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    try:
        import google.api_core.exceptions as gexc
        if isinstance(exc, (gexc.ServiceUnavailable, gexc.DeadlineExceeded)):
            return True
    except ImportError:
        pass
    type_name = type(exc).__name__
    return any(t in type_name for t in [
        'ConnectionError', 'Timeout', 'NetworkError',
        'ServiceUnavailable', 'ConnectError',
    ])


def _is_daily_limit(exc: Exception) -> bool:
    """Check whether a rate-limit exception is a daily / quota limit."""
    msg = str(exc).lower()
    return 'per day' in msg or 'daily' in msg or 'quota' in msg


def _get_retry_after(exc: Exception, default: float = 60.0) -> float:
    """Extract retry-after seconds from an exception's HTTP response headers."""
    if hasattr(exc, 'response') and exc.response is not None:
        headers = getattr(exc.response, 'headers', {})
        for h in ('retry-after', 'x-ratelimit-reset-requests', 'x-ratelimit-reset-tokens'):
            val = headers.get(h)
            if val:
                try:
                    return float(val)
                except ValueError:
                    pass
    return default
