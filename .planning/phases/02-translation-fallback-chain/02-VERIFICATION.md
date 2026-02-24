---
phase: 02-translation-fallback-chain
verified: 2026-02-24T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 2: Translation Fallback Chain Verification Report

**Phase Goal:** Translation works for free without API keys, with paid APIs as optional upgrade, and local NLLB as ultimate fallback.
**Verified:** 2026-02-24
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Translation works with zero API keys via MyMemory free tier | VERIFIED | FreeTranslationManager initialized unconditionally in engine.py `initialize()`; MyMemory is first provider in `_setup_providers()` |
| 2 | When MyMemory rate-limits, LibreTranslate is tried next, then Lingva | VERIFIED | `translate()` in translator_free.py iterates providers in order; `mark_rate_limited(86400)` on `RateLimitError` skips provider for 24h |
| 3 | When all free providers fail, local NLLB is used as final fallback | VERIFIED | Tier 3 in `_translate_text()`: `if self._translator and self._translator.is_loaded:` triggers NLLB |
| 4 | When paid API keys are configured, paid providers are tried before free chain | VERIFIED | Tier 1 in `_translate_text()` checks `self._cloud_translator.active_provider` before attempting free tier |
| 5 | 5-second timeout per HTTP request prevents hanging on slow providers | VERIFIED | `timeout=5` present in all three provider methods (lines 231, 278, 329 of translator_free.py) |
| 6 | VRChat chatbox and VR overlay receive nothing when translation fails | VERIFIED | Guard `if not translation_enabled or translated:` wraps all VRChat/overlay sends in both `_process_transcript()` and `process_text_input()`; comment confirms intent |
| 7 | Backend broadcasts translation_provider_switched event when provider changes | VERIFIED | `_notify_provider_if_changed()` in engine.py broadcasts `EventType.TRANSLATION_PROVIDER_SWITCHED` only on actual change |
| 8 | StatusBar shows which translation provider is currently active | VERIFIED | StatusBar.tsx reads `activeTranslationProvider` from chatStore and renders `Trans: {PROVIDER_LABELS[...]}` pill |
| 9 | Warning toast appears when translation provider switches | VERIFIED | useBackend.ts `translation_provider_switched` handler calls `addToast(..., 'warning')` when `provider && previous` |
| 10 | 'Free (No API Key)' appears as a translation provider option in settings and is the default for new users | VERIFIED | settingsStore.ts: `provider: 'free'` as default; SettingsView.tsx: `TRANSLATION_PROVIDERS` includes `{ value: 'free', label: 'Free (No API Key)' }` as first entry |
| 11 | Existing users with 'local' provider are migrated to 'free' via Zustand persist migration | VERIFIED | settingsStore.ts v1->v2 migration at line 284: `if (t.provider === 'local') { t.provider = 'free' }` with `version: 2` persist config |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `python/ai/translator_free.py` | FreeTranslationManager with MyMemory, LibreTranslate, Lingva providers | VERIFIED | 369 lines; contains `class FreeTranslationManager`, `class FreeTranslationProvider`, `NLLB_TO_FREE_API` (20 languages), all three provider methods |
| `python/core/events.py` | TRANSLATION_PROVIDER_SWITCHED event type | VERIFIED | `TRANSLATION_PROVIDER_SWITCHED = 'translation_provider_switched'` present at line 31, after TRANSLATION_FAILED |
| `python/core/engine.py` | Full fallback chain in `_translate_text()` and VRChat failure fix | VERIFIED | 3-tier chain at lines 225-273; `_free_translator` field initialized; VRChat guard at lines 629-648 |
| `python/ai/__init__.py` | Exports FreeTranslationManager | VERIFIED | `from ai.translator_free import FreeTranslationManager` — single export, correct |
| `src/stores/settingsStore.ts` | TranslationProvider type with 'free' option, version 2 migration | VERIFIED | `TranslationProvider = 'local' \| 'free' \| 'deepl' \| 'google'`; `version: 2`; migration block present |
| `src/stores/chatStore.ts` | activeTranslationProvider state field | VERIFIED | Field declared in interface, initialized to `null`, setter `setActiveTranslationProvider` implemented |
| `src/hooks/useBackend.ts` | translation_provider_switched event handler | VERIFIED | Case at line 144 in `handleGlobalMessage()` switch; PROVIDER_LABELS map at module level; three toast branches present |
| `src/components/chat/StatusBar.tsx` | Translation provider pill display | VERIFIED | `PROVIDER_LABELS` defined; `activeTranslationProvider` read from `useChatStore()`; conditional `Trans:` pill in JSX at lines 131-138 |
| `src/components/settings/SettingsView.tsx` | MyMemory email field and Free provider option | VERIFIED | `TRANSLATION_PROVIDERS` array with 'free' first (line 478); `mymemoryEmail` in credentials state (line 2296); MyMemory email input in "Free Translation" section (lines 2400-2420); sent to backend as `mymemory_email` (line 2334) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `python/core/engine.py` | `python/ai/translator_free.py` | `self._free_translator` instance | WIRED | `FreeTranslationManager` imported (line 22); instantiated in `initialize()` (line 330); used in `_translate_text()` (line 258) |
| `python/core/engine.py` | `python/core/events.py` | `TRANSLATION_PROVIDER_SWITCHED` event broadcast | WIRED | `EventType.TRANSLATION_PROVIDER_SWITCHED` used in `_notify_provider_if_changed()` (line 284) |
| `python/ai/translator_free.py` | `urllib.request` | HTTP calls with 5s timeout | WIRED | `urllib.request.urlopen(..., timeout=5)` present in all three provider methods |
| `src/hooks/useBackend.ts` | `src/stores/chatStore.ts` | `setActiveTranslationProvider` call on event | WIRED | `useChatStore.getState().setActiveTranslationProvider(provider)` called at start of `translation_provider_switched` case |
| `src/hooks/useBackend.ts` | `src/stores/notificationStore.ts` | `addToast` on provider switch | WIRED | `useNotificationStore.getState().addToast(...)` called in all three toast branches |
| `src/components/chat/StatusBar.tsx` | `src/stores/chatStore.ts` | reads `activeTranslationProvider` for display | WIRED | `const { isListening, isProcessing, activeTranslationProvider } = useChatStore()` destructured; used in JSX |
| `src/components/settings/SettingsView.tsx` | `src/stores/settingsStore.ts` | `mymemory_email` credential and 'free' provider option | WIRED | 'free' option in TRANSLATION_PROVIDERS wired to `updateTranslation({ provider: value as ... })`; mymemoryEmail sent via `updateSettings()` in `handleSave()` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TRAN-01 | 02-01-PLAN | Free translation APIs integrated (MyMemory primary, LibreTranslate secondary, Lingva tertiary) | SATISFIED | `FreeTranslationManager` in translator_free.py with all three providers in correct fallback order |
| TRAN-02 | 02-01-PLAN | Automatic fallback chain: free cloud → paid APIs (DeepL/Google if keys configured) → local NLLB | SATISFIED | `_translate_text()` implements 3-tier chain: paid (if active_provider) → free → NLLB; chain runs automatically |
| TRAN-03 | 02-01-PLAN | Rate limit detection and seamless provider switching without user action | SATISFIED | `mark_rate_limited(86400)` on MyMemory daily limit; `mark_failure()` after 3 consecutive failures triggers 5-minute cooldown; `translate()` skips unavailable providers transparently |
| TRAN-04 | 02-02-PLAN | User notification when provider switches (subtle status bar indicator, not interruptive) | SATISFIED | Warning toast on switch (auto-dismiss 5s); sticky error toast when all exhausted; recovery toast on restore |
| TRAN-05 | 02-02-PLAN | Translation provider status visible in StatusBar (which provider is active) | SATISFIED | StatusBar renders "Trans: {provider}" pill when `activeTranslationProvider` is non-null |

All 5 requirements (TRAN-01 through TRAN-05) are satisfied. No orphaned requirements found.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `python/core/engine.py` | 291-306 | `_switch_translation_provider()` is Phase 1 legacy that sets `provider = 'local'` and notifies via SETTINGS_UPDATED — superseded by the new chain | Info | Not a blocker: the old method is still wired to the `_translation_failure_count >= 3` path, but `_translate_text()` already handles all fallbacks internally. The legacy switch fires AFTER the chain has already exhausted all tiers and raised RuntimeError. Redundant but harmless. |
| `python/core/engine.py` | 262-263 | After free chain succeeds, `get_active_provider()` is called to determine which provider was active — but this is called AFTER `translate()` returns, so the "active" provider shown is the first available one, not necessarily the one that succeeded (if it changed internally) | Info | Edge case: if a provider fails mid-chain and another succeeds, the event will correctly show the name of the provider that is currently first-available, which is the one that just succeeded. Behavior is correct in practice. |

No blocker or warning-level anti-patterns found.

---

### Human Verification Required

#### 1. End-to-End Translation Without API Keys

**Test:** With no API keys configured, speak in English with translation target set to Japanese. Observe chatbox.
**Expected:** MyMemory translates the speech; "Trans: MyMemory" appears in StatusBar.
**Why human:** Cannot verify live HTTP call to MyMemory succeeds in the test environment.

#### 2. Rate Limit Fallback Toast

**Test:** Manually trigger a MyMemory rate limit (or mock it) and observe the UI notification.
**Expected:** Warning toast "Translation switched to LibreTranslate (MyMemory unavailable)" appears and auto-dismisses after 5 seconds.
**Why human:** Rate limit behavior requires live API interaction or mock injection.

#### 3. All Providers Exhausted Sticky Error

**Test:** Mark all three free providers as rate-limited (or disconnect internet) with no NLLB model loaded.
**Expected:** Sticky error toast "All translation providers unavailable. Check your internet connection or configure API keys."
**Why human:** Requires live failure condition to trigger.

#### 4. VRChat Silence on Translation Failure

**Test:** Enable translation, kill internet connectivity, speak a sentence.
**Expected:** Chat UI shows "[translation failed]" tag; VRChat chatbox receives nothing.
**Why human:** Requires runtime VRChat connection and controlled network failure.

---

### Observations

**Chain order note:** The ROADMAP "What to build" description says "free cloud -> paid -> local NLLB" but the CONTEXT document (the authoritative design decision) explicitly states "When paid keys configured: Paid first (DeepL/Google) -> Free chain -> local NLLB". The code implements the CONTEXT order (paid first). The ROADMAP success criteria "If DeepL/Google keys configured → used between free and local tiers" is slightly imprecise but the intent is correct — paid is used when keys are present, free is used otherwise. This is not a gap.

**mymemory_email storage pattern:** Consistent with the existing credential pattern — stored in `localStorage` under `stts_api_credentials` key, sent to backend on save via `updateSettings({ credentials: { mymemory_email: ... } })`. Not in Zustand persist (correct — API keys should not be persisted in Zustand state).

**FreeTranslationManager always initialized:** The manager is created in `initialize()` regardless of the selected translation provider. This is correct — it ensures the free tier is always available as a fallback even when the user has selected a paid provider.

---

## Gap Summary

No gaps found. All 11 observable truths verified, all 9 artifacts substantive and wired, all 7 key links confirmed, all 5 requirements satisfied.

---

_Verified: 2026-02-24_
_Verifier: Claude (gsd-verifier)_
