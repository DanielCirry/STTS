# Phase 3: AI Provider Fallback Chain - Research

**Researched:** 2026-02-24
**Domain:** Python async AI provider management, WebSocket events, React state management
**Confidence:** HIGH — Based on direct reading of all relevant source files plus existing project-level research.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Provider switching notification UX**
- On ANY provider switch: Warning toast (auto-dismiss 5s). Example: "AI switched to Gemini (Groq rate limited)"
- Always show toast — even for short RPM cooldowns. Consistent visibility, unlike translation which is silent for minor switches
- StatusBar: Always show active AI provider pill ("AI: groq", "AI: local") next to the translation pill. Visible whenever AI assistant is enabled
- Offline mode: StatusBar indicator only ("AI: local (offline)"). NO sticky toast for offline — just the StatusBar change
- Recovery from offline/failure: Warning toast (auto-dismiss 5s). Example: "AI restored via Groq". Same pattern as translation recovery

**Conversation continuity behavior**
- Shared conversation history across provider switches — inject history into new provider before generating
- Copy conversation list (not reference) to avoid aliasing bugs
- Manual provider change in settings: Keep conversation history (don't clear)
- Per-provider context limits: Local LLM gets smaller context window, cloud providers get full context window. Claude decides the specific numbers based on model capabilities
- Clearing chat: Resets conversation history only. Provider health states (cooldowns, failure counts) are NOT reset. Health persists for the full app session

**Fallback chain order and triggers**
- Default chain: local LLM -> Groq free -> Gemini free -> OpenAI (paid, if key) -> Anthropic (paid, if key)
- Local-first by default — always available offline, zero latency, no API key needed
- Providers without configured API keys are automatically skipped
- Sticky provider preference: Once a provider succeeds, prefer it for subsequent calls. Only move to next on failure
- Switch triggers: Rate limit (HTTP 429/529, ResourceExhausted), 15-second timeout, network/connection error
- Do NOT switch on application errors (bad prompt, model not found) — those surface to the user as errors
- Cooldowns: Parse retry-after header from rate limit responses. Default 60s for RPM limits. Daily limit = skip provider for rest of session (until app restart)
- Fixed chain order, not user-configurable priority. User can select a preferred provider in settings, but fallback order is fixed

**Offline / total failure behavior**
- When AI fails: User's original text still flows through the normal pipeline (STT -> translate -> TTS -> VRChat). AI is silently skipped for that message
- Show subtle "[AI unavailable]" note in chat UI only — do NOT speak it via TTS or send to VRChat
- Offline detection: One explicit connectivity check at app startup. During runtime, use reactive detection (2+ cloud providers hit network errors in the same generate() call = infer network is down)
- When network down: Skip all cloud providers for 60 seconds, use local LLM only
- Recovery: After 60s, try the highest-priority cloud provider on the next AI request. If it succeeds, clear offline mode and resume normal fallback chain
- Each AI message is independent — no queueing or retry of failed messages. Skip and continue

### Claude's Discretion
- Exact per-provider context window sizes for the per-provider limit feature
- FallbackAIManager internal architecture details (dataclasses, enums, helper functions)
- Network connectivity check implementation at startup (ping approach vs. DNS lookup)
- Exact fallback message wording for the [AI unavailable] chat note
- Whether to wrap existing generate() or create parallel path

### Deferred Ideas (OUT OF SCOPE)
- OpenRouter as user-optional provider (POL-08) — already in v2 requirements, not part of automatic fallback chain
- Groq model validation at startup (query available models API) — nice optimization but not essential for v1
- Context window auto-truncation safety valve — only needed if context_messages is increased substantially
- Per-provider quality scoring/preference learning — out of scope, would be v2+ feature
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-01 | Fallback chain: local LLM → Groq free → Gemini free → paid providers (OpenAI/Anthropic if keys configured) | FallbackAIManager wraps AIAssistantManager._providers dict; `get_available_providers()` returns is_available per provider; priority list filters by key presence |
| AI-02 | Rate limit detection per provider (429 for Groq/OpenAI, ResourceExhausted for Google, 529 for Anthropic) | Per-SDK exception mapping fully documented; `_is_rate_limit()` helper covers all providers; Anthropic 529 is `anthropic.OverloadedError` |
| AI-03 | Seamless provider switching — conversation continues without interruption | `_process_transcript()` and `process_text_input()` currently call `self._ai_assistant.generate(query)` — replace with `self._fallback_manager.generate(query)`; two call sites identified |
| AI-04 | Shared conversation history maintained across provider switches | `provider._conversation` is a `List[Message]` on `AIProvider` base class; inject `list(self._shared_conversation)` before each provider call, read back after success |
| AI-05 | User notification on provider switch (status bar pill showing active AI provider) | Three new WebSocket event types: `ai_provider_switched`, `ai_offline_mode`, `ai_online_restored`; `chatStore` needs `activeAIProvider` field; `StatusBar.tsx` needs AI pill after Trans pill |
| AI-06 | 15-second timeout on all cloud AI calls to prevent hanging | `asyncio.wait_for(..., timeout=15.0)` wraps each provider's `generate()` call inside the fallback loop |
| AI-07 | Local LLM works as ultimate fallback when no internet available | `LocalLLMProvider.is_available()` returns True if llama_cpp installed (library check), `is_loaded` is the actual readiness flag; fallback must check `is_loaded` not `is_available` |
</phase_requirements>

---

## Summary

Phase 3 adds automatic provider fallback to the AI assistant. The entire AI stack already exists (`AIAssistantManager`, `LocalLLMProvider`, `OpenAIProvider`, `GroqProvider`, `GoogleProvider`, `AnthropicProvider`) — no provider code needs rewriting. What does not exist is orchestration: nothing currently selects a different provider when the active one fails. When `generate()` raises, the exception propagates to engine.py where it is caught and logged as an error.

The implementation creates one new file (`python/ai/assistant/fallback.py`) containing `FallbackAIManager`, and makes surgical edits to `engine.py` (two call sites, one initialization block), `events.py` (three new event type constants), `chatStore.ts` (one new field + three new state setters), `useBackend.ts` (three new case handlers in `handleGlobalMessage`), and `StatusBar.tsx` (one new pill element). The extensive project-level research in `.planning/research/AI_PROVIDER_FALLBACK.md` already contains a production-ready `FallbackAIManager` skeleton — the planner should treat that as the primary implementation reference, verified against the actual source here.

The key integration finding from reading the source: `AIAssistantManager._providers` is a `Dict[str, AIProvider]` with keys `'local'`, `'openai'`, `'anthropic'`, `'groq'`, `'google'`. `FallbackAIManager` accesses this dict directly to inject conversation history and call providers individually, bypassing `AIAssistantManager.generate()` which does not accept a provider ID — it uses `_current_provider` instead. The research-provided skeleton already uses `provider_obj = self._manager._providers.get(provider_id)` which is exactly correct for the actual code.

**Primary recommendation:** Use the production-ready `FallbackAIManager` skeleton from `.planning/research/AI_PROVIDER_FALLBACK.md` (section 7.5) directly, adjusting toast behavior per CONTEXT.md decisions (always toast on any switch, offline = StatusBar only).

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `groq` (Python SDK) | Already in project | Groq API client; raises `groq.RateLimitError` on 429 | Already used by GroqProvider |
| `google-generativeai` | Already in project | Gemini API; raises `google.api_core.exceptions.ResourceExhausted` on 429 | Already used by GoogleProvider |
| `anthropic` | Already in project | Anthropic API; raises `anthropic.RateLimitError` (429) and `anthropic.OverloadedError` (529) | Already used by AnthropicProvider |
| `openai` | Already in project | OpenAI API; raises `openai.RateLimitError` on 429 | Already used by OpenAIProvider |
| `asyncio` (stdlib) | Python 3.x | `asyncio.wait_for()` for 15s timeout; `asyncio.run_coroutine_threadsafe()` for broadcasting from sync context | Already used throughout engine.py |
| `zustand` | Already in project | Frontend state management; `useChatStore` for `activeAIProvider` | Already used for `activeTranslationProvider` |

### No New Installations Required

All SDKs and frontend libraries are already present. Phase 3 is pure orchestration — new files and edits only.

---

## Architecture Patterns

### Recommended File Structure

```
python/ai/assistant/
  base.py               (unchanged — Message, AssistantConfig, AssistantResponse, AIProvider)
  local_llm.py          (unchanged)
  cloud_providers.py    (unchanged)
  manager.py            (unchanged — AIAssistantManager still used by FallbackAIManager)
  fallback.py           (NEW — FallbackAIManager + ProviderState + ProviderHealth + helpers)
  __init__.py           (add FallbackAIManager to exports)

python/core/
  engine.py             (edit: initialize FallbackAIManager, replace 2 generate() call sites)
  events.py             (edit: add 3 new AI event type constants)

src/stores/
  chatStore.ts          (edit: add activeAIProvider field + setters)

src/hooks/
  useBackend.ts         (edit: handle 3 new AI event types in handleGlobalMessage)

src/components/chat/
  StatusBar.tsx         (edit: add AI provider pill)
```

### Pattern 1: FallbackAIManager Wraps AIAssistantManager

**What:** `FallbackAIManager` holds a reference to the existing `AIAssistantManager` instance, accesses `_providers` dict directly to call individual providers, and maintains shared conversation history.

**When to use:** Always. The wrapper pattern preserves all existing manager functionality (keyword detection, config management, API key management) while adding fallback logic.

**Key insight from source reading:** `AIAssistantManager.generate()` does NOT accept a `provider_id` parameter in its current signature — it uses `_current_provider`. The fallback manager must bypass `manager.generate()` and call `provider_obj.generate(prompt)` directly on the provider instance.

```python
# Source: python/ai/assistant/manager.py line 275
async def generate(self, prompt: str, provider_id: Optional[str] = None) -> AssistantResponse:
    # NOTE: provider_id IS supported via optional param — it overrides _current_provider
    # FallbackAIManager can use this OR call provider_obj.generate() directly
    # Direct call is safer as it bypasses on_response/on_error callbacks (FallbackAIManager handles those)
```

Actually, `manager.generate()` does accept `provider_id`. But using `provider_obj.generate()` directly is better because `manager.generate()` calls `self.on_response` and `self.on_error` callbacks — which would fire multiple times during fallback attempts. Call `provider_obj.generate(prompt)` directly and handle callbacks only on final success.

### Pattern 2: Conversation History Injection

**What:** Before calling each provider, copy `self._shared_conversation` into `provider._conversation`. After success, copy back.

**When to use:** Every `generate()` call in `FallbackAIManager`.

**Source verification:** `AIProvider._conversation` is `List[Message]` (base.py line 47). `provider.add_message()` appends to `_conversation` and trims to `context_messages` limit. The fallback manager reads back `provider._conversation` after the provider's `generate()` call, which has already appended both user and assistant messages.

```python
# Source: python/ai/assistant/base.py line 64-71
def add_message(self, role: str, content: str):
    self._conversation.append(Message(role=role, content=content))
    max_messages = self._config.context_messages
    if len(self._conversation) > max_messages:
        self._conversation = self._conversation[-max_messages:]
```

Critical: Each provider's `generate()` calls `self.add_message('user', prompt)` at the start (before any API call). If the API call fails, the user message is already in `_conversation`. When injecting history into the next provider, DO NOT include this failed partial message. The pattern from the research skeleton handles this correctly by injecting BEFORE calling generate (provider adds user message itself), then reading back AFTER success.

**Per-provider context limits (Claude's discretion):**
- Local LLM: inject last 4 messages (2 turns). Local models have small context windows and are slow; keeping it tight minimizes latency.
- Cloud providers: inject last 10 messages (full `context_messages` value). Cloud models handle larger contexts efficiently.

### Pattern 3: Event Broadcasting from FallbackAIManager

**What:** `FallbackAIManager` receives an async `notify_callback` and calls it with event type + data dict. `engine.py` wires this to broadcast via `asyncio.run_coroutine_threadsafe`.

**When to use:** All three AI event types: `ai_provider_switched`, `ai_offline_mode`, `ai_online_restored`.

**Source verification — how translation events are currently broadcast (engine.py line 283):**
```python
# Source: python/core/engine.py line 283-289
asyncio.run_coroutine_threadsafe(
    self.broadcast(create_event(EventType.TRANSLATION_PROVIDER_SWITCHED, {
        'provider': new_provider,
        'previous': old,
    })),
    self._loop
)
```

**For AI events**, the `FallbackAIManager.generate()` is called from within an `async` context (it is `await`ed in `_process_transcript` and `ai_query`). The notify callback should also be `async`, called with `await` directly — no `run_coroutine_threadsafe` needed inside `FallbackAIManager` itself. The engine passes an async function as the callback.

```python
# In engine.py initialize():
async def _on_ai_provider_event(self, event_type: str, data: dict):
    event_map = {
        'ai_provider_switched': EventType.AI_PROVIDER_SWITCHED,
        'ai_offline_mode': EventType.AI_OFFLINE_MODE,
        'ai_online_restored': EventType.AI_ONLINE_RESTORED,
    }
    if event_type in event_map:
        await self.broadcast(create_event(event_map[event_type], data))

self._fallback_manager = FallbackAIManager(
    self._ai_assistant,
    notify_callback=self._on_ai_provider_event
)
```

### Pattern 4: engine.py Call Sites to Replace

There are exactly TWO places in `engine.py` that call AI generate, both currently using `self._ai_assistant.generate(query)`:

1. **`_process_transcript()` line 623:** `await self._ai_assistant.generate(query)` — change to `await self._fallback_manager.generate(query)`
2. **`process_text_input()` line 720:** `await self._ai_assistant.generate(query)` — change to `await self._fallback_manager.generate(query)`
3. **`ai_query()` line 1486:** `response = await self._ai_assistant.generate(query)` — change to `await self._fallback_manager.generate(query)`

That is THREE call sites. All three wrap with try/except. The current behavior on exception is to log and either return an error string (ai_query) or continue pipeline (process_transcript). With FallbackAIManager, exceptions only propagate for application-level errors; rate limits and network errors are handled internally.

**Important:** When all providers fail in FallbackAIManager, return a soft-failure `AssistantResponse` (content = fallback message, model='fallback') instead of raising. This way the existing `try/except` blocks in engine.py remain but the fallback message still flows through the pipeline. The "[AI unavailable]" note goes into chat; do NOT send it to TTS or VRChat. Handle this in engine.py by checking `response.model == 'fallback'` and skipping TTS/VRChat dispatch.

### Pattern 5: StatusBar AI Provider Pill

**What:** Add an "AI: {provider}" pill to StatusBar.tsx, conditionally shown when AI is enabled. Follows identical pattern to the existing "Trans: {provider}" pill.

**Source verification — existing Trans pill (StatusBar.tsx line 130-138):**
```tsx
{activeTranslationProvider && (
  <>
    <div className="h-3 w-px bg-border shrink-0" />
    <span className="shrink-0 text-muted-foreground text-xs">
      Trans: {PROVIDER_LABELS[activeTranslationProvider] || activeTranslationProvider}
    </span>
  </>
)}
```

**AI pill (new, same pattern):**
```tsx
{settings.ai.enabled && activeAIProvider && (
  <>
    <div className="h-3 w-px bg-border shrink-0" />
    <span className="shrink-0 text-muted-foreground text-xs">
      AI: {AI_PROVIDER_LABELS[activeAIProvider] || activeAIProvider}
    </span>
  </>
)}
```

`StatusBar` already imports `useChatStore` — destructure `activeAIProvider` from there.

### Pattern 6: chatStore.ts Extensions

**What:** Add `activeAIProvider` and `aiOfflineMode` fields to track runtime AI provider state.

**Source verification — existing activeTranslationProvider (chatStore.ts line 23-24, 34, 46, 73):**
```typescript
// Source: src/stores/chatStore.ts
activeTranslationProvider: string | null
setActiveTranslationProvider: (provider: string | null) => void
// initialized as null, updated via setActiveTranslationProvider
```

**New fields (same pattern):**
```typescript
activeAIProvider: string | null         // 'local', 'groq', 'google', etc.
aiOfflineMode: boolean                  // true when in offline-degraded state
setActiveAIProvider: (provider: string | null) => void
setAIOfflineMode: (offline: boolean) => void
```

### Pattern 7: useBackend.ts Event Handling

**What:** Add three new cases to `handleGlobalMessage` switch. Follow identical pattern to `translation_provider_switched` handling (lines 144-176).

**Source verification — translation_provider_switched handler (useBackend.ts line 144-176):**
The handler updates chatStore AND fires toasts. Three AI event types follow the same pattern:

```typescript
case 'ai_provider_switched': {
  const to = payload.to as string
  const from = payload.from as string | null
  const reason = payload.reason as string

  useChatStore.getState().setActiveAIProvider(to)

  // Always toast on any switch (locked decision — differs from translation which is silent for minor switches)
  const toLabel = AI_PROVIDER_LABELS[to] || to
  useNotificationStore.getState().addToast(
    `AI switched to ${toLabel} (${reason})`,
    'warning'
  )
  break
}

case 'ai_offline_mode': {
  // StatusBar only (no toast) — locked decision
  useChatStore.getState().setAIOfflineMode(true)
  // Update active provider to show offline state
  const currentProvider = useChatStore.getState().activeAIProvider
  // Keep current provider shown in StatusBar, component shows "(offline)" suffix
  break
}

case 'ai_online_restored': {
  const provider = payload.provider as string
  useChatStore.getState().setAIOfflineMode(false)
  useChatStore.getState().setActiveAIProvider(provider)
  const providerLabel = AI_PROVIDER_LABELS[provider] || provider
  useNotificationStore.getState().addToast(
    `AI restored via ${providerLabel}`,
    'warning'
  )
  break
}
```

Also add these event types to the ignore list in the `default` case so they don't log "Unknown message type".

### Anti-Patterns to Avoid

- **Calling `manager.generate()` inside FallbackAIManager:** This triggers `on_response`/`on_error` callbacks prematurely during fallback attempts. Call `provider_obj.generate(prompt)` directly.
- **Aliasing conversation lists:** Always `list(self._shared_conversation)` when injecting. Never assign the reference directly. Verified bug risk from base.py: providers trim `_conversation` in-place.
- **Raising on all-providers-fail:** Return a soft-failure `AssistantResponse(model='fallback')` instead. Avoids breaking the transcript processing pipeline.
- **Treating `LocalLLMProvider.is_available()` as "ready":** It returns `True` if `llama_cpp` is installed, regardless of whether a model is loaded. Always check `provider_info.get('is_loaded')` from `get_available_providers()` for the local provider.
- **Applying timeout to local LLM:** The 15s timeout is for CLOUD providers only. Local LLM may take longer on slow CPUs. Apply `asyncio.wait_for` only when `provider_id != 'local'`.
- **Running `_on_ai_provider_event` with `run_coroutine_threadsafe`:** The `generate()` call is already in an async context (it is `await`ed), so the callback is also async and can be `await`ed directly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limit exception detection | Custom HTTP status parsing | SDK exception classes (`groq.RateLimitError`, `google.api_core.exceptions.ResourceExhausted`, `anthropic.OverloadedError`) + `_is_rate_limit()` helper | SDKs wrap all HTTP status codes; string parsing misses edge cases |
| Async timeout | Manual timer or threading.Timer | `asyncio.wait_for(coro, timeout=15.0)` | Stdlib, zero-cost, integrates with async cancel semantics |
| State management | Custom dict + threading.Lock | `ProviderState` dataclass with `time.monotonic()` for cooldowns | Monotonic clock doesn't drift; dataclass is simpler than dict + lock |
| Broadcast from async context | `asyncio.run_coroutine_threadsafe` inside FallbackAIManager | Async callback passed from engine.py | FallbackAIManager is always called from async context; no thread-crossing needed |
| Daily vs. RPM limit detection | Parse HTTP headers only | Message text parsing (`"per day" in msg.lower()`) | Both are HTTP 429; only message text distinguishes them |

**Key insight:** The heavy lifting (SDK integration, async patterns, state management) is either already in the codebase or covered by stdlib. FallbackAIManager is ~150 lines of pure orchestration logic.

---

## Common Pitfalls

### Pitfall 1: User Message Added Before API Call Fails

**What goes wrong:** Each provider's `generate()` calls `self.add_message('user', prompt)` at the very start (before the API request). If the API fails, the user message is already appended to `_conversation`. When FallbackAIManager reads back `provider._conversation` after a failure, it contains an extra dangling user message.

**Why it happens:** `AIProvider.add_message()` is called unconditionally in `generate()` (cloud_providers.py line 122, 207, 291, 379). The provider does not roll back on exception.

**How to avoid:** Always inject `list(self._shared_conversation)` into `provider._conversation` BEFORE calling `provider.generate(prompt)`. The provider will add the user message. On success, read back. On failure, the injected copy is discarded (provider's `_conversation` is overwritten on the next attempt). Never update `self._shared_conversation` from a failed provider.

**Warning signs:** Conversation history growing unexpectedly; duplicate user messages appearing in AI context.

### Pitfall 2: `on_response` Callback Fires During Failed Attempts

**What goes wrong:** If `FallbackAIManager` calls `self._manager.generate(prompt, provider_id=provider_id)`, the manager's `on_response` callback fires on success. But `on_response` is `self._on_ai_response` in engine.py which broadcasts `AI_RESPONSE` to the frontend and triggers TTS/VRChat dispatch. This should only happen ONCE on final success, not on intermediate attempts.

**Why it happens:** `AIAssistantManager.generate()` calls `if self.on_response: self.on_response(response)` unconditionally on success.

**How to avoid:** Call `provider_obj.generate(prompt)` directly, bypassing the manager's `generate()`. After final successful response, call `engine._on_ai_response(response)` exactly once. The FallbackAIManager should return the `AssistantResponse` to the engine, which calls `_handle_ai_response` as usual.

**Warning signs:** Multiple AI responses appearing in chat for a single query; TTS fires multiple times.

### Pitfall 3: asyncio.TimeoutError Not Caught as General Exception

**What goes wrong:** `asyncio.TimeoutError` is raised by `asyncio.wait_for()` when the provider hangs. If the fallback loop's `except Exception` catches it before the explicit `except asyncio.TimeoutError` clause, behavior is wrong.

**Why it happens:** In Python 3.11+, `asyncio.TimeoutError` is a subclass of `TimeoutError` which is a subclass of `Exception`. In Python 3.10 and earlier, `asyncio.TimeoutError` is a subclass of `concurrent.futures.TimeoutError`. The catch ordering matters.

**How to avoid:** Always catch `asyncio.TimeoutError` BEFORE `Exception` in the try/except block:
```python
except asyncio.TimeoutError:
    state.mark_failure(retry_after=60.0)
    continue
except Exception as exc:
    # rate limit and network error handling
```

**Warning signs:** 15s timeouts not triggering fallback; provider stays stuck.

### Pitfall 4: Anthropic 529 Not Detected as Rate Limit

**What goes wrong:** Anthropic uses HTTP 529 (Overloaded) for capacity issues. This is NOT a standard HTTP status code and is not caught by generic 429-checking. If 529 falls through to the "application error — do not fallback" branch, the user sees an error instead of a graceful fallback.

**Why it happens:** `_is_rate_limit()` checks `exc.status_code == 429`. Anthropic's `OverloadedError` has `status_code == 529`.

**How to avoid:** Add explicit check in `_is_rate_limit()`:
```python
try:
    import anthropic
    if isinstance(exc, anthropic.OverloadedError):
        return True
except ImportError:
    pass
```
Or check `getattr(exc, 'status_code', None) in (429, 529)`.

**Warning signs:** Anthropic failures surfacing as errors instead of triggering fallback.

### Pitfall 5: Local LLM is_available vs. is_loaded Confusion

**What goes wrong:** `LocalLLMProvider.is_available()` returns `True` whenever `llama_cpp` is installed — even if no model is loaded. `FallbackAIManager` includes 'local' in candidates, tries to call it, and gets `RuntimeError("Model not loaded")` which is an application error and causes the fallback to re-raise.

**Why it happens:** `get_available_providers()` returns `is_loaded` via `getattr(provider, 'is_loaded', provider.is_available())` (manager.py line 169). But the `is_available` field in the dict refers to `provider.is_available()` (library check), while `is_loaded` is separate.

**How to avoid:** In `_get_candidates()`, for 'local' specifically, check both `is_available` AND `is_loaded`:
```python
info = provider_info.get(pid)
if pid == 'local' and not info.get('is_loaded', False):
    continue  # local library installed but no model loaded
if not info.get('is_available'):
    continue
```

**Warning signs:** RuntimeError("Model not loaded") appearing when local LLM is listed as a candidate.

### Pitfall 6: `_on_ai_response` Double-Fire

**What goes wrong:** `AIAssistantManager` has `self.on_response = self._on_ai_response` set in engine.py `initialize()`. If `FallbackAIManager` returns a response and engine.py also has a direct `_handle_ai_response` call, the AI message appears twice in chat.

**Why it happens:** Current pattern for `_process_transcript` is `await self._ai_assistant.generate(query)` which triggers the `on_response` callback. `ai_query()` does `response = await self._ai_assistant.generate(query); return response.content` — the callback fires AND the caller gets the response.

**How to avoid:** After switching to FallbackAIManager, the `on_response` callback on `AIAssistantManager` is no longer triggered (since `FallbackAIManager` calls `provider_obj.generate()` directly). The engine must call `await self._handle_ai_response(response)` explicitly after `response = await self._fallback_manager.generate(query)`.

Current code in `_process_transcript` (line 621-626):
```python
await self._ai_assistant.generate(query)  # on_response fires internally
return
```
Must become:
```python
response = await self._fallback_manager.generate(query)
await self._handle_ai_response(response)
return
```

---

## Code Examples

### FallbackAIManager — Complete Integration Skeleton

```python
# Source: .planning/research/AI_PROVIDER_FALLBACK.md section 7.5 (verified against actual code)
# python/ai/assistant/fallback.py

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from ai.assistant.base import AssistantResponse, Message

logger = logging.getLogger('stts.assistant.fallback')

AI_PROVIDER_LABELS = {
    'local': 'local',
    'groq': 'Groq',
    'google': 'Gemini',
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
}

# Per-provider context window (number of messages to inject)
PROVIDER_CONTEXT_LIMITS = {
    'local': 4,    # 2 conversation turns — local LLM is slow, keep context tight
    'groq': 10,    # full context_messages default
    'google': 10,
    'openai': 10,
    'anthropic': 10,
}


class ProviderHealth(Enum):
    HEALTHY   = "healthy"
    COOLING   = "cooling"    # temporary (RPM), retry after cooldown_until
    EXHAUSTED = "exhausted"  # daily limit — skip for rest of session


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

    DEFAULT_PRIORITY = ['local', 'groq', 'google', 'openai', 'anthropic']
    CLOUD_TIMEOUT = 15.0          # seconds per cloud provider attempt
    NETWORK_RETRY_INTERVAL = 60.0 # seconds before retrying cloud after network loss

    FALLBACK_MESSAGES = [
        "[AI unavailable] Try again in a moment.",
        "[AI unavailable] All providers are busy.",
        "[AI unavailable] Cannot reach AI service right now.",
    ]

    def __init__(self, manager, notify_callback: Optional[Callable] = None):
        self._manager = manager
        self._notify = notify_callback  # async callable(event_type: str, data: dict)
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
        return self._active_provider

    def _state(self, provider_id: str) -> ProviderState:
        if provider_id not in self._health:
            self._health[provider_id] = ProviderState()
        return self._health[provider_id]

    def _get_candidates(self) -> List[str]:
        """Priority-ordered list of healthy, available providers."""
        provider_info = {p['id']: p for p in self._manager.get_available_providers()}
        skip_cloud = (self._network_down and time.monotonic() < self._network_retry_at)

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
        if self._notify:
            try:
                await self._notify(event_type, data)
            except Exception as e:
                logger.warning(f"Notify error: {e}")

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate with automatic provider fallback. Never raises on provider failures."""
        candidates = self._get_candidates()

        # Sticky: prefer last successful provider
        if self._active_provider in candidates:
            candidates = [self._active_provider] + [
                p for p in candidates if p != self._active_provider
            ]

        if not candidates:
            import random
            msg = random.choice(self.FALLBACK_MESSAGES)
            await self._emit('ai_offline_mode', {
                'reason': 'all_providers_unavailable',
                'retry_in': self.NETWORK_RETRY_INTERVAL,
            })
            return AssistantResponse(content=msg, tokens_used=0, model='fallback', truncated=False)

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

                # Success
                self._shared_conversation = list(provider_obj._conversation)
                self._state(provider_id).mark_healthy()

                prev = self._active_provider
                self._active_provider = provider_id

                if prev and prev != provider_id:
                    await self._emit('ai_provider_switched', {
                        'from': prev,
                        'to': provider_id,
                        'reason': f'{AI_PROVIDER_LABELS.get(prev, prev)} rate limited'
                        if self._state(prev).health == ProviderHealth.COOLING
                        else 'restored',
                    })
                elif not prev:
                    # First successful call — emit initial provider so StatusBar shows it
                    await self._emit('ai_provider_switched', {
                        'from': None,
                        'to': provider_id,
                        'reason': 'initial',
                    })

                if self._network_down:
                    self._network_down = False
                    await self._emit('ai_online_restored', {'provider': provider_id})

                return response

            except asyncio.TimeoutError:
                self._state(provider_id).mark_failure(retry_after=60.0)
                logger.warning(f"{provider_id}: timeout after {self.CLOUD_TIMEOUT}s")
                next_pids = [p for p in candidates[candidates.index(provider_id)+1:]]
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
                    next_pids = [p for p in candidates[candidates.index(provider_id)+1:]]
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
                    logger.warning(f"{provider_id}: network error")
                    if network_fail_count >= 2 and not self._network_down:
                        self._network_down = True
                        self._network_retry_at = time.monotonic() + self.NETWORK_RETRY_INTERVAL
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
        import random
        msg = random.choice(self.FALLBACK_MESSAGES)
        return AssistantResponse(content=msg, tokens_used=0, model='fallback', truncated=False)


def _is_rate_limit(exc: Exception) -> bool:
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
    msg = str(exc).lower()
    return 'per day' in msg or 'daily' in msg or 'quota' in msg


def _get_retry_after(exc: Exception, default: float = 60.0) -> float:
    if hasattr(exc, 'response') and exc.response is not None:
        headers = exc.response.headers
        for h in ('retry-after', 'x-ratelimit-reset-requests', 'x-ratelimit-reset-tokens'):
            val = headers.get(h)
            if val:
                try:
                    return float(val)
                except ValueError:
                    pass
    return default
```

### engine.py — Three Call Site Changes

```python
# Source: python/core/engine.py — lines to change

# In initialize() — AFTER self._ai_assistant = AIAssistantManager():
from ai.assistant.fallback import FallbackAIManager

self._ai_assistant = AIAssistantManager()
self._ai_assistant.on_error = self._on_ai_error
# NOTE: do NOT set on_response here — FallbackAIManager handles response dispatching
self._fallback_manager = FallbackAIManager(
    self._ai_assistant,
    notify_callback=self._on_ai_provider_event
)

# New method to add to engine.py:
async def _on_ai_provider_event(self, event_type: str, data: dict):
    """Bridge FallbackAIManager events to WebSocket broadcast."""
    event_map = {
        'ai_provider_switched': EventType.AI_PROVIDER_SWITCHED,
        'ai_offline_mode': EventType.AI_OFFLINE_MODE,
        'ai_online_restored': EventType.AI_ONLINE_RESTORED,
    }
    if event_type in event_map:
        await self.broadcast(create_event(event_map[event_type], data))

# In _process_transcript() — replace lines 621-626:
# BEFORE:
#   await self._ai_assistant.generate(query)
#   return
# AFTER:
response = await self._fallback_manager.generate(query)
if response.model != 'fallback':
    await self._handle_ai_response(response)
else:
    # AI unavailable — show [AI unavailable] in chat only, not TTS/VRChat
    await self.broadcast(create_event(EventType.AI_RESPONSE, {
        'response': response.content,
        'model': 'fallback',
        'truncated': False,
    }))
return

# In process_text_input() — same pattern (line 720 area)

# In ai_query() — replace lines 1486:
# BEFORE:
#   response = await self._ai_assistant.generate(query)
#   return response.content
# AFTER:
response = await self._fallback_manager.generate(query)
return response.content

# In clear_ai_conversation() — replace lines 1651-1653:
def clear_ai_conversation(self):
    if self._fallback_manager:
        self._fallback_manager.clear_conversation()
    elif self._ai_assistant:
        self._ai_assistant.clear_conversation()
```

### events.py — New Event Types

```python
# Source: python/core/events.py — add to EventType enum

# AI Fallback Events
AI_PROVIDER_SWITCHED = 'ai_provider_switched'
AI_OFFLINE_MODE = 'ai_offline_mode'
AI_ONLINE_RESTORED = 'ai_online_restored'
```

### chatStore.ts — New Fields

```typescript
// Source: src/stores/chatStore.ts — add to ChatStore interface and create():

// In interface:
activeAIProvider: string | null
aiOfflineMode: boolean
setActiveAIProvider: (provider: string | null) => void
setAIOfflineMode: (offline: boolean) => void

// In create():
activeAIProvider: null,
aiOfflineMode: false,
setActiveAIProvider: (provider) => set({ activeAIProvider: provider }),
setAIOfflineMode: (offline) => set({ aiOfflineMode: offline }),
```

### StatusBar.tsx — AI Provider Pill

```tsx
// Source: src/components/chat/StatusBar.tsx — add after activeTranslationProvider block

const AI_PROVIDER_LABELS: Record<string, string> = {
  local: 'local',
  groq: 'Groq',
  google: 'Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
}

// In component:
const { isListening, isProcessing, activeTranslationProvider, activeAIProvider, aiOfflineMode } = useChatStore()

// In JSX, after Trans pill:
{settings.ai.enabled && activeAIProvider && (
  <>
    <div className="h-3 w-px bg-border shrink-0" />
    <span className="shrink-0 text-muted-foreground text-xs">
      AI: {AI_PROVIDER_LABELS[activeAIProvider] || activeAIProvider}
      {aiOfflineMode && ' (offline)'}
    </span>
  </>
)}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single provider, exception on failure | FallbackAIManager with health tracking | Phase 3 | Transparent to user; conversation continues |
| `on_response` callback triggers response dispatch | FallbackAIManager returns response, engine dispatches | Phase 3 | Enables soft-failure responses; prevents double-fire |
| `ai.provider` setting directly controls which provider | `ai.provider` = user preference, FallbackAIManager = runtime decision | Phase 3 | Setting preserved; runtime adapts to availability |

---

## Open Questions

1. **`ai_query()` endpoint — soft failure behavior**
   - What we know: `ai_query()` returns a string content, no `_handle_ai_response()` dispatch. It is used for direct AI queries from the UI (not from voice transcripts).
   - What's unclear: If `response.model == 'fallback'`, should `ai_query()` return the fallback message string? The caller (WebSocket handler) may do different things with it.
   - Recommendation: Return `response.content` regardless of `model`. The fallback message is already suitable as a user-facing response.

2. **Initial provider event on first generate() call**
   - What we know: StatusBar needs to show "AI: local" from the first transcript. But `ai_provider_switched` is only emitted when the provider changes or on first success.
   - What's unclear: Should we emit an initial event in `initialize()` to set the expected default provider?
   - Recommendation: Emit `ai_provider_switched` with `from=None` on the first successful generate() call. This is already in the code example above. Alternatively, initialize `activeAIProvider` from the status endpoint response.

3. **`get_status()` AI field — should it include fallback provider?**
   - What we know: `get_status()` in engine.py returns `ai.provider = self._ai_assistant.get_current_provider()` — this is the manually set provider, not the fallback's active provider.
   - What's unclear: Should `get_status()` also return the fallback's active provider?
   - Recommendation: Add `'fallback_provider': self._fallback_manager.get_active_provider() if self._fallback_manager else None` to the status response. Frontend uses this for initial StatusBar state on reconnect.

---

## Sources

### Primary (HIGH confidence)

- Direct reading of `python/ai/assistant/manager.py` — confirmed `_providers` dict structure, `generate()` signature, `get_available_providers()` return format
- Direct reading of `python/ai/assistant/base.py` — confirmed `AIProvider._conversation: List[Message]`, `add_message()` behavior, `AssistantResponse` fields
- Direct reading of `python/ai/assistant/cloud_providers.py` — confirmed per-provider `generate()` patterns, `add_message()` call placement
- Direct reading of `python/ai/assistant/local_llm.py` — confirmed `is_available()` = library check, `is_loaded` = model loaded flag
- Direct reading of `python/core/engine.py` — confirmed three call sites, `_on_ai_response` callback pattern, `_notify_provider_if_changed` broadcast pattern
- Direct reading of `python/core/events.py` — confirmed EventType enum structure
- Direct reading of `src/hooks/useBackend.ts` — confirmed `handleGlobalMessage` switch structure, `translation_provider_switched` handler pattern
- Direct reading of `src/stores/chatStore.ts` — confirmed `activeTranslationProvider` field pattern
- Direct reading of `src/components/chat/StatusBar.tsx` — confirmed Trans pill JSX pattern

### Secondary (MEDIUM confidence)

- `.planning/research/AI_PROVIDER_FALLBACK.md` — Rate limit formats, SDK exception classes, `FallbackAIManager` skeleton design. MEDIUM because rate limit numbers may have drifted since August 2025.

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all libraries are already installed; verified from imports in existing provider files
- Architecture: HIGH — all integration points verified by reading actual source code
- Pitfalls: HIGH — identified from direct code reading (add_message placement, on_response callback, is_available vs is_loaded)
- Toast/UX behavior: HIGH — locked decisions from CONTEXT.md

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (rate limit numbers in provider research are MEDIUM confidence, may change; code patterns are stable)
