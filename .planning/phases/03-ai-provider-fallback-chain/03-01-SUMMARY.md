---
phase: 03-ai-provider-fallback-chain
plan: 01
subsystem: ai
tags: [fallback, provider-chain, rate-limit, asyncio, timeout, websocket-events]

# Dependency graph
requires:
  - phase: 01-stability-pass
    provides: Error handling patterns, WebSocket event infrastructure
provides:
  - FallbackAIManager with priority-based provider fallback (local -> groq -> google -> openai -> anthropic)
  - ProviderState health tracking with HEALTHY/COOLING/EXHAUSTED states
  - Rate limit detection for all provider SDKs (429, 529, ResourceExhausted, OverloadedError)
  - 15-second cloud timeout via asyncio.wait_for
  - Shared conversation history injection across provider switches
  - Three new AI WebSocket event types for frontend consumption
  - Soft-failure response (model='fallback') for graceful degradation
affects: [03-02-frontend-ai-provider-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FallbackAIManager wraps AIAssistantManager, calls provider.generate() directly"
    - "ProviderState dataclass with monotonic-time cooldowns"
    - "Conversation history injection with per-provider context limits"
    - "Soft-failure AssistantResponse(model='fallback') instead of raising"

key-files:
  created:
    - python/ai/assistant/fallback.py
  modified:
    - python/ai/assistant/__init__.py
    - python/core/events.py
    - python/core/engine.py

key-decisions:
  - "Call provider_obj.generate() directly instead of manager.generate() to avoid premature on_response/on_error callback firing during fallback attempts"
  - "Local LLM context limit = 4 messages (2 turns), cloud = 10 messages (full default)"
  - "Soft-failure AssistantResponse(model='fallback') returned when all providers fail, shown in chat only (not TTS/VRChat)"
  - "Application errors (bad prompt, model not found) are re-raised and not swallowed by fallback"
  - "Health states persist across conversation clears (only conversation history is reset)"

patterns-established:
  - "FallbackAIManager wrapper pattern: wraps existing manager, accesses _providers dict directly"
  - "AI event bridge: async _on_ai_provider_event in engine.py maps string events to EventType enum and broadcasts"
  - "Fallback response routing: model='fallback' goes to chat-only broadcast, skipping TTS/VRChat/VR overlay"

requirements-completed: [AI-01, AI-02, AI-03, AI-04, AI-06, AI-07]

# Metrics
duration: 12min
completed: 2026-02-24
---

# Phase 3 Plan 1: AI Provider Fallback Chain Backend Summary

**FallbackAIManager with priority chain (local -> groq -> google -> openai -> anthropic), per-provider health tracking, 15s cloud timeout, and rate limit/network error detection wired into engine.py**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-02-24
- **Completed:** 2026-02-24
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created FallbackAIManager class with complete provider fallback orchestration
- Added ProviderState/ProviderHealth for health tracking with monotonic-time cooldowns
- Added rate limit detection covering all provider SDKs (429, 529, ResourceExhausted, OverloadedError)
- Added 15-second cloud timeout (local LLM excluded)
- Added conversation history injection with per-provider context limits
- Wired all 3 engine.py call sites to use FallbackAIManager
- Added 3 new WebSocket event types for frontend AI provider notifications
- Added soft-failure response (model='fallback') that shows in chat without triggering TTS/VRChat

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FallbackAIManager with provider health tracking and fallback logic** - `8afb7b3` (feat)
2. **Task 2: Wire FallbackAIManager into engine.py and add event types** - `a89b7ee` (feat)

## Files Created/Modified
- `python/ai/assistant/fallback.py` - FallbackAIManager class with ProviderState, ProviderHealth, and helper functions for rate limit/network error detection
- `python/ai/assistant/__init__.py` - Added FallbackAIManager to module exports
- `python/core/events.py` - Added AI_PROVIDER_SWITCHED, AI_OFFLINE_MODE, AI_ONLINE_RESTORED event types
- `python/core/engine.py` - Initialized FallbackAIManager, replaced all 3 generate() call sites, added event bridge, updated clear_conversation and get_status

## Decisions Made
- Call `provider_obj.generate()` directly instead of `manager.generate()` to prevent premature on_response/on_error callback firing during fallback attempts
- Local LLM gets 4 messages context (2 turns) due to small context windows and slow inference; cloud providers get full 10 messages
- Soft-failure AssistantResponse with `model='fallback'` returned when all providers fail -- shown in chat UI only, never sent to TTS, VRChat, or VR overlay
- Application errors (bad prompt, model not found) are re-raised to the caller -- only rate limits, timeouts, and network errors trigger fallback
- Health states (cooldowns, failure counts) persist across conversation clears -- only `_shared_conversation` is reset

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend fallback chain is complete and ready for frontend integration (Plan 03-02)
- Three WebSocket event types ready for useBackend.ts handling
- chatStore.ts needs activeAIProvider and aiOfflineMode fields
- StatusBar.tsx needs AI provider pill

## Self-Check: PASSED

- All 5 files verified present on disk
- Both commits verified in git log: `8afb7b3`, `a89b7ee`
- FallbackAIManager imports successfully
- EventType.AI_PROVIDER_SWITCHED accessible
- No old `await self._ai_assistant.generate()` calls remain in engine.py
- `_fallback_manager` referenced 9 times in engine.py

---
*Phase: 03-ai-provider-fallback-chain*
*Completed: 2026-02-24*
