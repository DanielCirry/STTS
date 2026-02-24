---
phase: 03-ai-provider-fallback-chain
plan: 02
subsystem: ui
tags: [zustand, react, websocket, ai-provider, toast, statusbar, fallback]

# Dependency graph
requires:
  - phase: 03-ai-provider-fallback-chain
    provides: FallbackAIManager backend with ai_provider_switched, ai_offline_mode, ai_online_restored WebSocket events
  - phase: 01-stability-pass
    provides: notification store with addToast, useBackend WebSocket event handler pattern, StatusBar component
  - phase: 02-translation-fallback-chain
    provides: PROVIDER_LABELS pattern, activeTranslationProvider runtime state in chatStore, StatusBar pill pattern
provides:
  - chatStore activeAIProvider (string|null) and aiOfflineMode (boolean) runtime state fields
  - AI_PROVIDER_LABELS constant mapping provider IDs to display names (useBackend and StatusBar)
  - Three AI event handlers in useBackend handleGlobalMessage switch (ai_provider_switched, ai_offline_mode, ai_online_restored)
  - StatusBar "AI: {provider}" pill with "(offline)" suffix support
  - Toast notifications on provider switch (warning, auto-dismiss 5s) and online restoration
affects: [04-rvc, settings, status-bar]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AI_PROVIDER_LABELS: Record<string, string> for mapping AI provider IDs to display names"
    - "Runtime state pattern (not persisted) for transient backend AI provider state"
    - "Three-event AI notification pattern: switch (toast), offline (StatusBar only), restore (toast)"

key-files:
  created: []
  modified:
    - src/stores/chatStore.ts
    - src/hooks/useBackend.ts
    - src/components/chat/StatusBar.tsx

key-decisions:
  - "activeAIProvider and aiOfflineMode are runtime state (not persisted) -- reset to null/false on reload, backend re-emits on next generate()"
  - "AI provider switch always shows toast (differs from translation which is silent for minor switches) per CONTEXT.md locked decision"
  - "Offline mode shows StatusBar indicator only (no toast) per CONTEXT.md locked decision"
  - "Initial provider assignment (from=null, reason=initial) does not trigger toast -- only subsequent switches"

patterns-established:
  - "AI_PROVIDER_LABELS constant: defined at module level in both useBackend.ts and StatusBar.tsx for mapping backend IDs to user-facing names"
  - "AI event handling pattern: three complementary events (switch/offline/restore) with differentiated UX responses"

requirements-completed: [AI-03, AI-05]

# Metrics
duration: 8min
completed: 2026-02-24
---

# Phase 3 Plan 2: Frontend AI Provider Integration Summary

**AI provider StatusBar pill, WebSocket event handlers for provider switch/offline/restore notifications, and chatStore runtime state for active AI provider tracking**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-02-24T23:13:53Z
- **Completed:** 2026-02-24T23:22:00Z
- **Tasks:** 2 auto + 1 human-verify checkpoint (noted, not blocked)
- **Files modified:** 3

## Accomplishments
- Added activeAIProvider (string|null) and aiOfflineMode (boolean) runtime state to chatStore with setters
- Added AI_PROVIDER_LABELS constant and three AI event handlers to useBackend.ts handleGlobalMessage switch
- Added "AI: {provider}" pill to StatusBar with "(offline)" suffix, conditionally shown when AI is enabled
- Toast notifications fire on provider switch (warning, auto-dismiss 5s) and online restoration
- Offline mode only updates StatusBar indicator (no toast) per locked decision

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AI provider state to chatStore and wire event handlers in useBackend** - `408496a` (feat)
2. **Task 2: Add AI provider pill to StatusBar** - `8e9930f` (feat)
3. **Task 3: Verify AI fallback chain end-to-end** - checkpoint:human-verify (noted, not blocked per execution instructions)

## Files Created/Modified
- `src/stores/chatStore.ts` - Added activeAIProvider (string|null), aiOfflineMode (boolean), and their setters as runtime state
- `src/hooks/useBackend.ts` - Added AI_PROVIDER_LABELS constant, three AI event cases (ai_provider_switched, ai_offline_mode, ai_online_restored) in handleGlobalMessage, and added event types to known message list
- `src/components/chat/StatusBar.tsx` - Added AI_PROVIDER_LABELS constant, destructured activeAIProvider/aiOfflineMode from chatStore, added conditional "AI: {provider}" pill with offline suffix

## Decisions Made
- **Runtime state not persisted**: activeAIProvider and aiOfflineMode are transient runtime state in chatStore, reset to null/false on reload. Backend re-emits active provider on the next successful generate() call.
- **Toast on all non-initial switches**: Per CONTEXT.md locked decision, every provider switch gets a warning toast (auto-dismiss 5s), even for short RPM cooldowns. This differs from translation which is silent for minor switches.
- **No toast for offline mode**: Per CONTEXT.md locked decision, offline mode only updates the StatusBar pill to show "(offline)" suffix. No toast to avoid alarm.
- **Initial provider assignment silent**: When from=null and reason='initial' (first ever generate() call), no toast fires. Only subsequent switches produce toasts.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Human Verification Pending

Task 3 is a checkpoint:human-verify for end-to-end testing of the complete AI provider fallback chain. Verification steps:
1. Start the application and enable AI assistant in settings
2. Check StatusBar shows "AI: {provider}" pill
3. Say "jarvis" or trigger AI and verify response
4. If multiple providers are configured, verify toast appears on provider switch
5. Verify "(offline)" suffix appears during offline mode
6. Verify "[AI unavailable]" message appears in chat (not spoken via TTS)

## Next Phase Readiness
- Frontend AI provider integration is complete
- Phase 3 (AI Provider Fallback Chain) is fully wired: backend FallbackAIManager (Plan 01) + frontend state/events/UI (Plan 02)
- Ready for Phase 4 (RVC Voice Conversion)

## Self-Check: PASSED

- All 3 modified source files verified present on disk
- SUMMARY.md verified present on disk
- Both commits verified in git log: `408496a`, `8e9930f`
- activeAIProvider and aiOfflineMode fields present in chatStore.ts (6 references)
- ai_provider_switched, ai_offline_mode, ai_online_restored handlers present in useBackend.ts
- AI_PROVIDER_LABELS and AI pill JSX present in StatusBar.tsx
- TypeScript compiles clean (npx tsc --noEmit passes)

---
*Phase: 03-ai-provider-fallback-chain*
*Completed: 2026-02-24*
