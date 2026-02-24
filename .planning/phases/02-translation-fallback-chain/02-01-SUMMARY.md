---
phase: 02-translation-fallback-chain
plan: 01
subsystem: translation
tags: [python, urllib, mymemory, libretranslate, lingva, nllb, fallback-chain, websocket-events]

requires:
  - phase: 01-stability-pass
    provides: engine.py patterns (failure counting, provider switching, broadcast helpers)

provides:
  - FreeTranslationManager with MyMemory, LibreTranslate, Lingva providers
  - 3-tier translation fallback chain: paid cloud -> free -> local NLLB
  - TRANSLATION_PROVIDER_SWITCHED WebSocket event type
  - VRChat/overlay guarded by translation success (no untranslated text sent on failure)
  - Per-provider rate limit tracking with automatic cooldowns

affects:
  - 02-02 (frontend provider status UI)
  - 03-ai-provider-fallback (same pattern: provider state, cooldowns, event broadcasting)

tech-stack:
  added: []
  patterns:
    - FreeTranslationProvider state machine (enabled, rate_limited_until, consecutive_failures)
    - NLLB_TO_FREE_API dict for per-provider language code mapping
    - 5s timeout on all HTTP calls to prevent hanging on slow/dead providers
    - HTML-response detection for Lingva (scraper blocked signal)
    - Instance rotation pattern for multi-instance providers (LibreTranslate, Lingva)
    - _notify_provider_if_changed() suppresses duplicate broadcast events

key-files:
  created:
    - python/ai/translator_free.py
  modified:
    - python/core/events.py
    - python/core/engine.py
    - python/ai/__init__.py

key-decisions:
  - "FreeTranslationManager is always initialized regardless of selected provider (lightweight, no model download)"
  - "5s timeout per HTTP request (plan specifies this explicitly — prevents hanging)"
  - "Mark provider unavailable for 5 minutes after 3 consecutive failures"
  - "MyMemory daily limit cooldown is 86400s (full day reset); transient errors use 300s"
  - "VRChat/overlay only receive text when translation succeeds — when enabled and failed, send nothing"
  - "'free' and 'local' providers are not passed to CloudTranslationManager.set_provider() to avoid warning"

patterns-established:
  - "Provider guard pattern: if not translation_enabled or translated — gates VRChat/overlay sends"
  - "has_free = self._free_translator is not None added alongside has_cloud/has_local in all 3 callers"

requirements-completed: [TRAN-01, TRAN-02, TRAN-03]

duration: 5min
completed: 2026-02-24
---

# Phase 2 Plan 01: Translation Fallback Chain — Python Backend Summary

**3-tier translation fallback chain (paid cloud -> MyMemory/LibreTranslate/Lingva -> local NLLB) with rate-limit tracking, VRChat failure fix, and provider-switch event broadcasting using only Python stdlib**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-24T~20:12Z
- **Completed:** 2026-02-24T~20:17Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Created `python/ai/translator_free.py` with FreeTranslationManager, provider state tracking, and per-provider rate limit/cooldown logic
- Wired 3-tier fallback chain into `engine.py`'s `_translate_text()`: paid cloud providers -> free chain -> local NLLB
- Fixed VRChat/overlay send-on-failure bug: untranslated text no longer sent when translation is enabled but fails
- Added `TRANSLATION_PROVIDER_SWITCHED` WebSocket event type with suppression for duplicate broadcasts
- `mymemory_email` credential accepted at runtime to upgrade from 5K/day anonymous to 50K/day limit

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FreeTranslationManager with MyMemory, LibreTranslate, Lingva providers** - `3e91566` (feat)
2. **Task 2: Wire fallback chain into engine.py and fix VRChat send-on-failure bug** - `cdc9908` (feat)

## Files Created/Modified

- `python/ai/translator_free.py` - FreeTranslationManager class with 3 providers, NLLB code mapping, rate limit tracking
- `python/core/events.py` - Added TRANSLATION_PROVIDER_SWITCHED event type after TRANSLATION_FAILED
- `python/core/engine.py` - 3-tier _translate_text(), _notify_provider_if_changed(), VRChat guard fix, 'free' provider handling, status extension
- `python/ai/__init__.py` - Exports FreeTranslationManager

## Decisions Made

- FreeTranslationManager is always initialized in `initialize()` regardless of selected provider — it's lightweight (no model downloads) and must always be available as middle-tier fallback
- 5-second HTTP timeout per request (plan requirement) — prevents the engine from hanging on unresponsive providers
- After 3 consecutive failures, provider enters 5-minute cooldown via the same `mark_rate_limited(300)` mechanism as rate limiting
- MyMemory daily limit uses 86400s cooldown; transient errors use 300s
- VRChat/overlay guard pattern: `if not translation_enabled or translated` — when translation is enabled and fails, sends nothing; when translation is disabled, sends the original text normally
- `'free'` provider value is not forwarded to `CloudTranslationManager.set_provider()` (would log "Unknown cloud translation provider: free" warning)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Extended translation availability check in all 3 callers**
- **Found during:** Task 2 (engine.py modification)
- **Issue:** `_process_transcript`, `process_text_input`, and `_process_speaker_transcript` all checked `if has_cloud or has_local` before attempting translation. This would skip translation even when free providers are available.
- **Fix:** Added `has_free = self._free_translator is not None` to all three callers and changed condition to `if has_cloud or has_free or has_local`
- **Files modified:** python/core/engine.py
- **Verification:** All three translation code paths now include free provider availability check
- **Committed in:** cdc9908 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical)
**Impact on plan:** Essential fix — without it, free providers would never be tried when no paid key is configured and no local model is loaded. No scope creep.

## Issues Encountered

None - plan executed without blocking issues.

## Next Phase Readiness

- Python backend fallback chain is complete and importable
- Frontend status display for free provider availability can now consume `get_status()['translation']['free_providers']`
- `TRANSLATION_PROVIDER_SWITCHED` event is available for frontend to display active provider name
- No blockers for Phase 2 Plan 02 (frontend UI changes)

---
*Phase: 02-translation-fallback-chain*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: python/ai/translator_free.py
- FOUND: python/core/events.py
- FOUND: python/core/engine.py
- FOUND: python/ai/__init__.py
- FOUND: .planning/phases/02-translation-fallback-chain/02-01-SUMMARY.md
- COMMIT 3e91566: feat(02-01): create FreeTranslationManager with MyMemory, LibreTranslate, Lingva providers
- COMMIT cdc9908: feat(02-01): wire fallback chain into engine.py and fix VRChat send-on-failure bug
