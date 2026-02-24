---
phase: 02-translation-fallback-chain
plan: 02
subsystem: ui
tags: [zustand, react, websocket, translation, toast, settings]

# Dependency graph
requires:
  - phase: 01-stability-pass
    provides: notification store with addToast, useBackend WebSocket event handler pattern, StatusBar component
provides:
  - TranslationProvider type extended with 'free' option and Zustand v2 migration
  - chatStore activeTranslationProvider runtime state field
  - translation_provider_switched WebSocket event handler with toast notifications
  - StatusBar provider pill showing active translation provider
  - 'Free (No API Key)' option in settings translation provider dropdown
  - MyMemory email field in API Credentials settings
affects: [03-ai-provider-fallback, 04-rvc, settings, status-bar]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - PROVIDER_LABELS map pattern for human-readable backend provider names (used in both useBackend and StatusBar)
    - Zustand migrate with version parameter for sequential migrations
    - Runtime state (not persisted) in chatStore for transient backend state

key-files:
  created: []
  modified:
    - src/stores/settingsStore.ts
    - src/stores/chatStore.ts
    - src/hooks/useBackend.ts
    - src/components/chat/StatusBar.tsx
    - src/components/settings/SettingsView.tsx

key-decisions:
  - "MyMemory email stored in localStorage credentials (stts_api_credentials) not Zustand, consistent with existing API keys pattern"
  - "activeTranslationProvider is runtime state in chatStore (not persisted) — reflects current backend state"
  - "Recovery toast uses 'warning' severity (auto-dismisses 5s) not 'info' — notificationStore only has warning and error severities"
  - "Free provider treated as cloud (isCloud=true) in TranslationSettings — no local model selection shown"

patterns-established:
  - "PROVIDER_LABELS: Record<string, string> — define at module level for mapping backend provider IDs to display names"
  - "Zustand persist version migrations: use version parameter and if (version < N) blocks for sequential migration"

requirements-completed: [TRAN-04, TRAN-05]

# Metrics
duration: 20min
completed: 2026-02-24
---

# Phase 02 Plan 02: Frontend Translation Provider Integration Summary

**Translation provider visibility and configuration: 'free' type with Zustand migration, activeTranslationProvider in chatStore, provider-switch toasts via WebSocket, StatusBar pill, and Free/MyMemory settings UI**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-02-24T00:00:00Z
- **Completed:** 2026-02-24T00:20:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Extended `TranslationProvider` type with `'free'` as the new default, with Zustand v2 migration migrating existing `'local'` users to `'free'`
- Added `activeTranslationProvider: string | null` runtime state to chatStore with setter, enabling StatusBar to display which provider the backend is currently using
- Implemented `translation_provider_switched` WebSocket event handler in useBackend.ts with three toast cases: warning on switch, warning on recovery, sticky error when all exhausted
- StatusBar now shows "Trans: {ProviderName}" pill whenever a provider is active
- Settings UI gains "Free (No API Key)" as first/default provider option and MyMemory email field in Credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: Add free TranslationProvider, chatStore activeTranslationProvider, Zustand migration** - `47fef5b` (feat)
2. **Task 2: Handle translation_provider_switched event and StatusBar provider pill** - `df4f25e` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `src/stores/settingsStore.ts` - Extended TranslationProvider type ('free'), changed default to 'free', bumped persist to v2 with local->free migration
- `src/stores/chatStore.ts` - Added activeTranslationProvider field and setActiveTranslationProvider action
- `src/hooks/useBackend.ts` - Added PROVIDER_LABELS constant, translation_provider_switched case with toast logic, added to known types list
- `src/components/chat/StatusBar.tsx` - Added PROVIDER_LABELS, reads activeTranslationProvider from chatStore, renders "Trans: X" pill
- `src/components/settings/SettingsView.tsx` - Added 'Free (No API Key)' to TRANSLATION_PROVIDERS, fixed handleProviderChange type cast, updated provider description text and info box, added Free Translation section with MyMemory email field in CredentialsSettings

## Decisions Made

- **MyMemory email in localStorage**: The existing CredentialsSettings uses localStorage (`stts_api_credentials`) not Zustand for API keys. Added `mymemoryEmail` to the same localStorage object and sends it to backend as `mymemory_email` via `updateSettings`. Consistent with existing pattern.
- **activeTranslationProvider not persisted**: This is transient runtime state reflecting what the backend says it's using. Not persisted — resets to null on reload (backend will re-emit on connect).
- **Recovery toast as 'warning'**: notificationStore only has `'warning' | 'error'` severities. Used 'warning' for recovery toast (auto-dismisses 5s), which is acceptable.
- **Free provider as cloud**: `isCloud = translation.provider !== 'local'` — 'free' is correctly treated as cloud (uses internet APIs, no local model needed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated TranslationSettings handleProviderChange type cast**
- **Found during:** Task 1 (TranslationProvider type extension)
- **Issue:** `handleProviderChange` had `value as 'local' | 'deepl' | 'google'` — would cause TypeScript error after adding 'free' to the union
- **Fix:** Updated cast to include 'free': `value as 'local' | 'free' | 'deepl' | 'google'`
- **Files modified:** src/components/settings/SettingsView.tsx
- **Verification:** TypeScript compiles clean
- **Committed in:** 47fef5b (Task 1 commit)

**2. [Rule 1 - Bug] Updated TranslationSettings info box and description for 'free' provider**
- **Found during:** Task 1 (adding 'free' provider option to dropdown)
- **Issue:** Info box and description text only handled `isCloud` vs local — 'free' would show "Using local NLLB model" which is incorrect
- **Fix:** Added 'free'-specific branches in description text and info box with correct messaging about MyMemory/free APIs
- **Files modified:** src/components/settings/SettingsView.tsx
- **Verification:** TypeScript compiles clean, description text correct for each provider
- **Committed in:** 47fef5b (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bug fixes in adjacent code)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

None - implementation proceeded smoothly following existing patterns.

## User Setup Required

None - no external service configuration required. MyMemory email is optional and improves rate limits.

## Next Phase Readiness

- Frontend is fully wired for translation provider state and notifications
- Backend needs to emit `translation_provider_switched` events with `{provider, previous}` payload for the UI to respond
- Phase 02-01 (backend fallback chain) provides the Python implementation that emits these events
- All frontend artifacts in place: chatStore field, WebSocket handler, StatusBar pill, settings UI

---
*Phase: 02-translation-fallback-chain*
*Completed: 2026-02-24*
