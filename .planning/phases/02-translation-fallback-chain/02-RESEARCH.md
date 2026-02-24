# Phase 2: Translation Fallback Chain - Research

**Researched:** 2026-02-24
**Domain:** Python fallback chain architecture, free REST translation APIs, React/Zustand frontend integration
**Confidence:** HIGH (existing pre-research in FREE_TRANSLATION_APIS.md is detailed and directly applicable; codebase fully read)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Fallback chain order & triggers:**
- Default mode (no API keys): Free APIs first (MyMemory -> LibreTranslate -> Lingva -> local NLLB)
- When paid keys configured: Paid first (DeepL/Google) -> Free chain -> local NLLB
- Failure trigger: Any error OR slow response (>5s timeout) triggers immediate switch to next provider
- Cooldown: MyMemory daily limit = retry next day (UTC midnight reset). Transient errors = 5-minute cooldown after 3 consecutive failures
- Fixed chain order, not user-configurable

**Provider switching notification:**
- On switch: Warning toast (yellow, auto-dismiss 5s). Example: "Translation switched to LibreTranslate (MyMemory daily limit reached)"
- StatusBar: Always show active translation provider (e.g., "Trans: MyMemory" or "Trans: NLLB") next to the language pair
- Total failure (all providers exhausted): Sticky error toast with guidance + original text in chat with [no translation available] tag
- Recovery: Subtle info toast when a provider comes back online (e.g., "Translation restored via MyMemory"), auto-dismiss

**Settings & configuration:**
- Add "Free (No API Key)" as a new translation provider dropdown option — make it the default for new users
- MyMemory email field goes in Credentials/API section, near other API keys. Label: "MyMemory Email (optional) — increases daily limit from 5K to 50K chars"
- No drag-to-reorder. Fixed chain: paid (if keys) -> free (MyMemory -> LibreTranslate -> Lingva) -> local NLLB
- No per-provider toggles. Keep it simple — the chain handles failures automatically

**VRChat behavior on translation failure:**
- Block untranslated text from VRChat chatbox (don't send original when translation fails)
- Nothing in VRChat chatbox on failure — stays empty. The chat UI shows [translation failed] tag
- Skip failed messages, continue when restored — each message independent, no pausing
- Block VR overlay too when translation fails — consistent behavior, nothing shows anywhere except chat UI
- This fixes the Phase 1 verifier flag: engine.py currently sends original text to VRChat on translation failure and needs to be updated

### Claude's Discretion
- Language code mapping implementation details (NLLB -> free API codes)
- HTTP request implementation (urllib vs requests, retry logic)
- Instance rotation strategy for LibreTranslate and Lingva
- Exact toast wording and timing

### Deferred Ideas (OUT OF SCOPE)
- Azure Translator as additional keyed provider (2M chars/month free tier) — noted in research, deferred to v2 as POL-07
- User-configurable LibreTranslate instance list — nice-to-have but not essential for v1
- Per-provider quality comparison/benchmarking — out of scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRAN-01 | Free translation APIs integrated (MyMemory primary, LibreTranslate secondary, Lingva tertiary) | `FreeTranslationManager` class pattern fully documented in FREE_TRANSLATION_APIS.md; API formats verified |
| TRAN-02 | Automatic fallback chain: free cloud → paid APIs (DeepL/Google if keys configured) → local NLLB | Fallback logic integrates into existing `_translate_text()` in engine.py; `CloudTranslationManager` extended |
| TRAN-03 | Rate limit detection and seamless provider switching without user action | Rate limit signals documented per provider (HTTP 429, responseStatus 429, HTML body); cooldown tracking pattern defined |
| TRAN-04 | User notification when provider switches (subtle status bar indicator, not interruptive) | notificationStore.addToast() (warning severity = auto-dismiss 5s) already supports this; new `translation_provider_switched` WebSocket event needed |
| TRAN-05 | Translation provider status visible in StatusBar (which provider is active) | StatusBar.tsx already renders dynamic items from props; needs `activeTranslationProvider` prop and backend status field |
</phase_requirements>

---

## Summary

Phase 2 adds a free translation fallback chain to STTS so it works without any API keys configured. The pre-existing research document (`FREE_TRANSLATION_APIS.md`) already contains a complete, vetted `FreeTranslationManager` class implementation — this research phase primarily validates that implementation against the actual codebase and identifies all integration points.

The Python backend needs three changes: (1) a new `python/ai/translator_free.py` file containing `FreeTranslationManager`, (2) extension of `CloudTranslationManager` in `translator_cloud.py` to route through free providers, and (3) updates to `engine.py`'s `_translate_text()` and `_switch_translation_provider()` to implement the new chain. The VRChat failure behavior also needs a fix: engine.py currently sends original text to VRChat when translation fails, which contradicts the user's decision to send nothing on failure.

The frontend needs four changes: (1) add `'free'` to the `TranslationProvider` type union, (2) add a MyMemory email field in `CredentialsSettings`, (3) add a translation provider pill to `StatusBar`, and (4) handle the new `translation_provider_switched` WebSocket event in `useBackend.ts` to trigger toasts. No new Python packages are needed — all free API calls use stdlib `urllib` matching the existing `translator_cloud.py` pattern.

**Primary recommendation:** Port the complete `FreeTranslationManager` from `FREE_TRANSLATION_APIS.md` into `python/ai/translator_free.py` as-is, then wire it into the existing `_translate_text()` fallback chain in `engine.py`.

---

## Standard Stack

### Core (no new dependencies)
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Python `urllib.request` | stdlib | HTTP requests to free APIs | Already used in `translator_cloud.py`; no new deps |
| Python `urllib.parse` | stdlib | URL encoding for MyMemory/Lingva GET requests | stdlib, consistent with existing code |
| Python `json` | stdlib | Parse API responses | stdlib |
| React + Zustand | existing | Frontend state for provider status | Already in use; `notificationStore`, `settingsStore` |
| WebSocket events | existing | Backend→frontend notifications | `EventType` enum in `core/events.py` |

### No New Packages Required
The entire `FreeTranslationManager` uses only Python stdlib. Do NOT add `requests`, `deep-translator`, `googletrans`, or any other HTTP library.

---

## Architecture Patterns

### Recommended File Structure

New file to create:
```
python/ai/
├── translator.py           # Local NLLB (existing)
├── translator_cloud.py     # DeepL + Google (existing, extend)
└── translator_free.py      # FreeTranslationManager (NEW — create this file)
```

Frontend changes (modify existing files only, no new files):
```
src/
├── stores/settingsStore.ts      # Add 'free' to TranslationProvider type
├── hooks/useBackend.ts          # Handle translation_provider_switched event
├── components/chat/StatusBar.tsx  # Add active translation provider pill
└── components/settings/SettingsView.tsx  # Add MyMemory email in CredentialsSettings
```

### Pattern 1: FreeTranslationManager (new `translator_free.py`)

The complete implementation from `FREE_TRANSLATION_APIS.md` should be ported verbatim. Key design:

```python
# Source: .planning/research/FREE_TRANSLATION_APIS.md (fully vetted)

class RateLimitError(Exception):
    """Provider has hit its daily/hourly limit."""
    pass

class ProviderUnavailableError(Exception):
    """Provider is down, network error, or unreachable."""
    pass

class FreeTranslationProvider:
    """State tracker for one free translation provider."""
    def __init__(self, name: str, translate_fn: Callable):
        self.name = name
        self._translate = translate_fn
        self.enabled = True
        self.rate_limited_until: Optional[datetime] = None
        self.consecutive_failures: int = 0

    @property
    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if self.rate_limited_until and datetime.utcnow() < self.rate_limited_until:
            return False
        return True

    def mark_rate_limited(self, duration_seconds: int = 86400):
        """MyMemory: 86400s (next UTC day). Transient: 300s."""
        from datetime import timedelta
        self.rate_limited_until = datetime.utcnow() + timedelta(seconds=duration_seconds)

    def mark_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            from datetime import timedelta
            self.rate_limited_until = datetime.utcnow() + timedelta(minutes=5)

    def mark_success(self):
        self.consecutive_failures = 0
        self.rate_limited_until = None


class FreeTranslationManager:
    """Fallback chain: MyMemory -> LibreTranslate -> Lingva."""

    def __init__(self, mymemory_email: str = ""):
        self._email = mymemory_email
        self._providers: List[FreeTranslationProvider] = []
        self._libretranslate_instances = [
            "https://translate.argosopentech.com",
            "https://translate.terraprint.co",
            "https://lt.vern.cc",
        ]
        self._lingva_instances = [
            "https://lingva.ml",
            "https://translate.plausibility.cloud",
            "https://lingva.tiekoetter.com",
        ]
        self._setup_providers()

    def translate(self, text: str, source_nllb: str, target_nllb: str) -> Optional[str]:
        """Try each provider. Returns None if all fail (caller falls to NLLB)."""
        ...

    def get_active_provider(self) -> Optional[str]:
        """Return name of first available provider, or None if all rate-limited."""
        for p in self._providers:
            if p.is_available:
                return p.name
        return None
```

### Pattern 2: Extended `_translate_text()` in `engine.py`

Current code (Phase 1) only knows about cloud (DeepL/Google) and local NLLB. Phase 2 replaces this with the full chain:

```python
# Current (Phase 1) — REPLACE THIS:
def _translate_text(self, text, source_lang, target_lang) -> str:
    # Try cloud translation first
    if self._cloud_translator:
        cloud_result = self._cloud_translator.translate(...)
        if cloud_result: return cloud_result
    # Fall back to local NLLB
    if self._translator and self._translator.is_loaded:
        return self._translator.translate(...)
    raise RuntimeError("No translation provider available")

# Phase 2 — NEW CHAIN:
def _translate_text(self, text, source_lang, target_lang) -> str:
    # 1. Paid cloud (DeepL/Google) — if keys configured AND active_provider is paid
    if self._cloud_translator and self._cloud_translator.active_provider in ('deepl', 'google'):
        try:
            result = self._cloud_translator.translate(text, source_lang, target_lang)
            if result:
                self._notify_provider_if_changed(self._cloud_translator.active_provider)
                return result
        except Exception as e:
            logger.warning(f"Paid cloud translation failed: {e}")

    # 2. Free chain (MyMemory -> LibreTranslate -> Lingva)
    if self._free_translator:
        try:
            result = self._free_translator.translate(text, source_lang, target_lang)
            if result:
                self._notify_provider_if_changed(self._free_translator.get_active_provider())
                return result
        except Exception as e:
            logger.warning(f"Free translation failed: {e}")

    # 3. Local NLLB fallback
    if self._translator and self._translator.is_loaded:
        self._notify_provider_if_changed('nllb')
        return self._translator.translate(text, source_lang, target_lang)

    raise RuntimeError("No translation provider available")
```

### Pattern 3: Provider Switch Notification (Python → Frontend)

Add a new EventType and broadcast it when the active provider changes:

```python
# In core/events.py — add:
TRANSLATION_PROVIDER_SWITCHED = 'translation_provider_switched'

# In engine.py — add field and notification method:
self._active_translation_provider: Optional[str] = None  # track to detect changes

def _notify_provider_if_changed(self, new_provider: Optional[str]):
    if new_provider == self._active_translation_provider:
        return  # No change, no notification
    old = self._active_translation_provider
    self._active_translation_provider = new_provider
    if self._loop:
        asyncio.run_coroutine_threadsafe(
            self.broadcast(create_event(EventType.TRANSLATION_PROVIDER_SWITCHED, {
                'provider': new_provider,
                'previous': old,
            })),
            self._loop
        )
```

### Pattern 4: StatusBar Provider Pill (Frontend)

StatusBar.tsx already renders dynamic items using the props pattern. Add `activeTranslationProvider` as a prop:

```typescript
// StatusBar.tsx additions
interface StatusBarProps {
  // ... existing props
  activeTranslationProvider?: string | null  // 'MyMemory', 'LibreTranslate', 'Lingva', 'DeepL', 'Google', 'NLLB', null
}

const PROVIDER_LABELS: Record<string, string> = {
  MyMemory: 'MyMemory',
  LibreTranslate: 'LibreTranslate',
  Lingva: 'Lingva',
  deepl: 'DeepL',
  google: 'Google',
  nllb: 'NLLB',
}

// In StatusBar render — insert after the Globe/pair label section:
{settings.translation.enabled && activeTranslationProvider && (
  <>
    <div className="h-3 w-px bg-border shrink-0" />
    <span className="shrink-0 text-muted-foreground">
      Trans: {PROVIDER_LABELS[activeTranslationProvider] || activeTranslationProvider}
    </span>
  </>
)}
```

### Pattern 5: useBackend.ts Event Handler

Handle `translation_provider_switched` in the global message handler in `useBackend.ts`:

```typescript
// In handleGlobalMessage() switch statement — add case:
case 'translation_provider_switched': {
  const provider = payload.provider as string | null
  const previous = payload.previous as string | null

  if (provider && previous) {
    // Provider switched — warning toast
    const providerLabel = PROVIDER_LABELS[provider] || provider
    useNotificationStore.getState().addToast(
      `Translation switched to ${providerLabel}`,
      'warning'  // auto-dismisses 5s per existing notificationStore behavior
    )
  } else if (!provider) {
    // All providers exhausted
    useNotificationStore.getState().addToast(
      'All translation providers unavailable — check connection',
      'error'  // sticky
    )
  }
  // Update active provider state — store it in chatStore or as module-level state
  // (chatStore or a new activeTranslationProvider field in chatStore)
  break
}
```

The `activeTranslationProvider` state needs to live somewhere accessible to StatusBar. The cleanest approach is to add it to `chatStore.ts` (it's runtime state, not user settings):

```typescript
// chatStore.ts additions:
interface ChatStore {
  // ... existing fields
  activeTranslationProvider: string | null
  setActiveTranslationProvider: (provider: string | null) => void
}
```

### Pattern 6: CredentialsSettings — MyMemory Email Field

The `CredentialsSettings` component in `SettingsView.tsx` already has a pattern for optional API key fields. Add the email field in the same style:

```typescript
// In CredentialsSettings component (SettingsView.tsx)
// Look for the pattern used for deepl_api_key and google_translate_api_key inputs
// Add a "Free Translation" section above them:
<div className="space-y-4">
  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
    Free Translation
  </h3>
  <div>
    <Label>MyMemory Email (optional)</Label>
    <p className="text-xs text-muted-foreground mb-1">
      Increases daily limit from 5,000 to 50,000 characters. No account required.
    </p>
    <input
      type="email"
      placeholder="your@email.com"
      value={mymemoryEmail}
      onChange={handleEmailChange}
      className="..."  // match existing input styles
    />
  </div>
</div>
```

The email value needs to flow through: settingsStore (as `credentials.mymemory_email`) → updateSettings WebSocket → engine.py → FreeTranslationManager.set_mymemory_email().

### Pattern 7: TranslationProvider Type Extension

```typescript
// settingsStore.ts — change:
export type TranslationProvider = 'local' | 'deepl' | 'google'

// To:
export type TranslationProvider = 'local' | 'free' | 'deepl' | 'google'
```

Change default provider from `'local'` to `'free'`:
```typescript
translation: {
  enabled: true,
  model: 'nllb-200-distilled-600M',
  provider: 'free',  // changed from 'local'
  ...
}
```

Also update settings store version (currently `version: 1`) to `version: 2` with migration that converts any stored `'local'` provider to `'free'` for existing users who had no API keys.

### Pattern 8: VRChat Failure Fix

Current `engine.py` line ~588-594 sends `text_to_send = text` (original) when translation fails. Phase 2 must change this so VRChat and VR overlay receive nothing when translation fails:

```python
# Current (BROKEN — sends original on failure):
if translated and vrchat_settings.get('send_translations', True):
    text_to_send = f"{text} - {translated}"
else:
    text_to_send = text  # BUG: sends original even when translation failed
await self._vrchat.send_text(text_to_send)

# Fixed (Phase 2):
if translated:
    text_to_send = f"{text} - {translated}"
    await self._vrchat.send_text(text_to_send)
# If no translation, send nothing to VRChat (block untranslated text)
```

This same fix applies to the VR overlay display: only show text when `translated` is not None.

### Anti-Patterns to Avoid

- **Do not instantiate FreeTranslationManager in CloudTranslationManager**: Keep them as siblings in engine.py. The engine coordinates the chain, not the translators themselves.
- **Do not add `'free'` provider routing inside CloudTranslationManager.set_provider()**: The engine handles routing; `CloudTranslationManager` only wraps DeepL and Google.
- **Do not use threading.Lock for rate limit state**: Rate limit tracking is only mutated from the translation thread; no lock needed.
- **Do not block on timeout inside _translate_text()**: The 5s timeout must be per HTTP request (urllib timeout parameter), not a wrapper around the whole chain.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry with backoff | Custom retry wrapper | Provider-level instance rotation (try next instance on failure) | Simpler, already in FreeTranslationManager pattern |
| Rate limit state machine | Complex state machine | Simple `rate_limited_until: datetime` field | Sufficient for this use case; no complex FSM needed |
| Language code mapping | Ad-hoc string manipulation | `NLLB_TO_FREE_API` dict (from FREE_TRANSLATION_APIS.md) | Already has all 20 languages; verified correct |
| Toast notifications | Custom notification UI | `notificationStore.addToast()` | Already implemented in Phase 1; `'warning'` severity auto-dismisses 5s |

**Key insight:** The free API implementations in `FREE_TRANSLATION_APIS.md` are already written and correct. Don't re-derive them — port them.

---

## Common Pitfalls

### Pitfall 1: 5-Second Timeout Not Enforced Per Request
**What goes wrong:** `urllib.request.urlopen(url, timeout=10)` is set to 10s per request. Phase 2 requires 5s timeout. If a provider hangs for 10s and there are 3 instances, the whole LibreTranslate tier takes 30s.
**Why it happens:** Default timeout in existing code is 10s.
**How to avoid:** Use `timeout=5` in all `urlopen()` calls inside FreeTranslationManager.
**Warning signs:** Translation seems to hang before switching to next provider.

### Pitfall 2: MyMemory Rate Limit Signal Is in Response Body (Not HTTP Status)
**What goes wrong:** MyMemory returns HTTP 200 with `responseStatus: 429` inside the JSON body. If you only check the HTTP status code, you'll miss the rate limit signal and keep calling a limited provider.
**Why it happens:** MyMemory's API design uses `responseStatus` inside JSON for all error types.
**How to avoid:** Always parse the JSON response and check both `data["responseStatus"]` and `data["responseDetails"]` for `"QUERY LENGTH LIMIT"`.
**Warning signs:** MyMemory seems to return results but they're garbled or empty when limit is hit.

### Pitfall 3: Lingva HTML Response When Scraper Blocked
**What goes wrong:** When Google blocks a Lingva instance's server IP, Lingva returns an HTML error page instead of JSON. `json.loads()` throws, which gets caught as a generic error. You might misinterpret this as a network error and apply a 5-minute cooldown instead of trying the next Lingva instance.
**Why it happens:** Lingva returns `Content-Type: text/html` or HTML body when blocked.
**How to avoid:** Check Content-Type header AND check if raw response starts with `<!DOCTYPE`. If HTML detected, try next Lingva instance, don't raise RateLimitError.
**Warning signs:** All Lingva instances fail with json.JSONDecodeError on the same request.

### Pitfall 4: Provider Notification on Every Translation (Not Just on Switch)
**What goes wrong:** Broadcasting `translation_provider_switched` on every call creates WebSocket spam and confusing toasts that flash every few seconds.
**Why it happens:** Checking provider without tracking previous state.
**How to avoid:** Track `self._active_translation_provider` in engine and only broadcast when it changes from the previous value.
**Warning signs:** StatusBar flickers; toast appears every utterance.

### Pitfall 5: Zustand Migration Version Not Incremented
**What goes wrong:** Changing `TranslationProvider` default from `'local'` to `'free'` without bumping the Zustand persist version means existing users keep `'local'` from localStorage. New users get `'free'` (correct), but existing users are stuck on `'local'` unless they clear storage.
**Why it happens:** Zustand's persist middleware only runs migration when version changes.
**How to avoid:** Increment `version: 1` to `version: 2` in `useSettingsStore` persist config, and add migration that converts stored `'local'` (no API keys) to `'free'`.
**Warning signs:** Translation settings work on fresh installs but not for users who ran STTS before.

### Pitfall 6: VRChat Send-on-Failure Bug (Phase 1 Verifier Flag)
**What goes wrong:** The Phase 1 verifier flagged that `engine.py` sends the original text to VRChat when translation fails. The current code at line ~589-594 has this bug: `text_to_send = text` runs even when `translated` is None.
**Why it happens:** The conditional for VRChat send uses `else: text_to_send = text` without checking if translation was attempted and failed vs. translation was disabled.
**How to avoid:** Phase 2 must fix this — only send to VRChat when `translated is not None`. When translation fails, send nothing.
**Warning signs:** VRChat shows untranslated English when translation is enabled but failing.

### Pitfall 7: `'free'` Provider Not Handled in `engine.py` update_settings()
**What goes wrong:** `update_settings()` currently calls `self._cloud_translator.set_provider(provider if provider != 'local' else None)`. When `provider == 'free'`, it will pass `'free'` to `CloudTranslationManager.set_provider()`, which doesn't recognize it and logs a warning.
**Why it happens:** `set_provider()` currently only accepts `None`, `'deepl'`, `'google'`, or `'local'`.
**How to avoid:** In `update_settings()`, check: `if provider in ('local', 'free'): cloud_provider = None else: cloud_provider = provider`. The free chain is always active; only paid cloud providers need to be set on CloudTranslationManager.
**Warning signs:** Warning log "Unknown cloud translation provider: free" on startup.

### Pitfall 8: FreeTranslationManager Not Initialized When Provider Is Not 'free'
**What goes wrong:** If provider is `'deepl'`, users might assume free chain is inactive. But the free chain should ALWAYS be the fallback even when paid providers are configured. If `_free_translator` is only created when `provider == 'free'`, it won't be available when DeepL fails.
**Why it happens:** Trying to lazily init based on selected provider.
**How to avoid:** Always instantiate `FreeTranslationManager` in `engine.initialize()` regardless of selected provider. It's lightweight (no models to load) and must always be available as fallback.

---

## Code Examples

### Language Code Mapping (complete, from FREE_TRANSLATION_APIS.md — HIGH confidence)

```python
# Source: .planning/research/FREE_TRANSLATION_APIS.md (verified)
NLLB_TO_FREE_API: Dict[str, Dict[str, str]] = {
    'eng_Latn': {'mymemory': 'en',    'libretranslate': 'en', 'lingva': 'en'},
    'jpn_Jpan': {'mymemory': 'ja',    'libretranslate': 'ja', 'lingva': 'ja'},
    'zho_Hans': {'mymemory': 'zh-CN', 'libretranslate': 'zh', 'lingva': 'zh'},
    'zho_Hant': {'mymemory': 'zh-TW', 'libretranslate': 'zh', 'lingva': 'zh-TW'},
    'kor_Hang': {'mymemory': 'ko',    'libretranslate': 'ko', 'lingva': 'ko'},
    'spa_Latn': {'mymemory': 'es',    'libretranslate': 'es', 'lingva': 'es'},
    'fra_Latn': {'mymemory': 'fr',    'libretranslate': 'fr', 'lingva': 'fr'},
    'deu_Latn': {'mymemory': 'de',    'libretranslate': 'de', 'lingva': 'de'},
    # ... (20 languages total in FREE_TRANSLATION_APIS.md)
}
```

### MyMemory API Call (HIGH confidence — official API)

```python
# Source: https://api.mymemory.translated.net/
def _mymemory_translate(self, text: str, source: str, target: str) -> str:
    import urllib.request, urllib.parse, json
    params = {"q": text, "langpair": f"{source}|{target}"}
    if self._email:
        params["de"] = self._email
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ProviderUnavailableError(f"MyMemory network error: {e}")

    status = data.get("responseStatus", 0)
    # CRITICAL: Rate limit is in response body, not HTTP status
    if status == 429 or "QUERY LENGTH LIMIT" in data.get("responseDetails", ""):
        raise RateLimitError("MyMemory daily limit reached")
    if status not in (200, "200"):
        raise ProviderUnavailableError(f"MyMemory status {status}")

    translated = data.get("responseData", {}).get("translatedText", "")
    if not translated:
        raise ProviderUnavailableError("MyMemory returned empty translation")
    return translated
```

### get_status() Extension for Backend

The existing `get_status()` in `engine.py` returns `cloudTranslation` info. Extend to include free provider state:

```python
# In get_status() — extend the return dict:
'translation': {
    'active_provider': self._active_translation_provider,  # 'MyMemory', 'LibreTranslate', 'Lingva', 'deepl', 'google', 'nllb', None
    'free_providers': self._free_translator.get_status() if self._free_translator else [],
    'cloud_provider': self._cloud_translator.active_provider if self._cloud_translator else None,
}
```

### Zustand Migration for 'free' Default

```typescript
// In settingsStore.ts persist config — update version and migration:
{
  name: 'stts-settings',
  version: 2,  // bumped from 1
  migrate: (persisted: unknown, version: number) => {
    const state = persisted as Record<string, unknown>
    // Existing v0->v1 migration (languagePairs)
    if (version < 1) {
      // ... existing migration code
    }
    // New v1->v2 migration: default 'local' -> 'free' for zero-config users
    if (version < 2) {
      const t = (state?.translation as Record<string, unknown>) || {}
      if (t.provider === 'local') {
        t.provider = 'free'
      }
    }
    return state
  },
}
```

---

## Integration Points (all files that need changes)

### Python Backend

| File | Change Type | What Changes |
|------|-------------|-------------|
| `python/ai/translator_free.py` | CREATE | Port `FreeTranslationManager` from FREE_TRANSLATION_APIS.md |
| `python/ai/__init__.py` | MODIFY | Export `FreeTranslationManager` |
| `python/core/events.py` | MODIFY | Add `TRANSLATION_PROVIDER_SWITCHED = 'translation_provider_switched'` |
| `python/core/engine.py` | MODIFY | (1) Add `_free_translator` field, (2) rewrite `_translate_text()` chain, (3) add `_active_translation_provider` tracking, (4) fix VRChat/overlay send-on-failure bug, (5) handle `'free'` in `update_settings()`, (6) handle `mymemory_email` in credentials |
| `python/ai/translator_cloud.py` | MODIFY | Accept `'free'` without warning in `set_provider()` (or handle in engine only) |

### Frontend

| File | Change Type | What Changes |
|------|-------------|-------------|
| `src/stores/settingsStore.ts` | MODIFY | Add `'free'` to `TranslationProvider` type; change default; bump persist version; add migration |
| `src/stores/chatStore.ts` | MODIFY | Add `activeTranslationProvider: string | null` field and setter |
| `src/hooks/useBackend.ts` | MODIFY | Handle `translation_provider_switched` event: update chatStore, trigger toast |
| `src/components/chat/StatusBar.tsx` | MODIFY | Add `activeTranslationProvider` prop; render provider pill |
| `src/components/chat/ChatView.tsx` | MODIFY | Pass `activeTranslationProvider` from chatStore to StatusBar |
| `src/components/settings/SettingsView.tsx` | MODIFY | Add MyMemory email field in `CredentialsSettings`; add `'free'` option to provider dropdown in `TranslationSettings` |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| Single provider: local or cloud | Full fallback chain: free → paid → local | Zero-config users now have translation |
| Send original to VRChat on failure | Send nothing on failure | Prevents untranslated text in VRChat |
| `'local'` as default provider | `'free'` as default provider | Better first-run experience |
| No provider visibility in StatusBar | Provider pill shows active translator | User knows what's working |

---

## Open Questions

1. **Lingva instance availability (2026-02-24)**
   - What we know: `lingva.ml` was the primary instance as of Aug 2025, community instances are volatile
   - What's unclear: Current uptime status of lingva.ml and alternatives
   - Recommendation: Include 3 instances hardcoded; executor should verify one is responsive before shipping. If all fail, graceful degradation to NLLB is already handled.

2. **LibreTranslate instance key requirements**
   - What we know: `translate.argosopentech.com`, `translate.terraprint.co`, `lt.vern.cc` were keyless as of Aug 2025
   - What's unclear: Current key requirements on these instances
   - Recommendation: The code already handles 403 (key required) by skipping to next instance — this is self-healing. No special handling needed.

3. **MyMemory JA/ZH quality for casual VRChat speech**
   - What we know: MyMemory uses Google MT under the hood for JA/ZH; quality is GOOD for formal text
   - What's unclear: Quality for casual/informal Japanese (VRChat slang, short utterances)
   - Recommendation: Accept this limitation for Phase 2; users with quality concerns can configure a paid API key. Quality is still better than no translation.

4. **`activeTranslationProvider` state on app startup**
   - What we know: Backend starts with no active provider until first translation succeeds
   - What's unclear: What to show in StatusBar before any translation has happened
   - Recommendation: Show nothing (null state → don't render the pill) until first `translation_provider_switched` event arrives. Or show the configured provider from settings as "expected" state.

---

## Sources

### Primary (HIGH confidence)
- `.planning/research/FREE_TRANSLATION_APIS.md` — Complete FreeTranslationManager implementation, all API formats, rate limit signals, language code mappings
- `python/core/engine.py` — Full source read; all integration points identified
- `python/ai/translator_cloud.py` — CloudTranslationManager pattern to follow
- `python/core/events.py` — EventType enum; where to add new event
- `src/stores/settingsStore.ts` — TranslationProvider type; persist/migrate pattern
- `src/stores/notificationStore.ts` — Toast system; addToast() API
- `src/hooks/useBackend.ts` — WebSocket event handler pattern; where to add new case
- `src/components/chat/StatusBar.tsx` — Existing StatusBar structure and props pattern
- `src/components/settings/SettingsView.tsx` — CredentialsSettings pattern to follow

### Secondary (MEDIUM confidence)
- MyMemory official API (`https://api.mymemory.translated.net/`) — Documented API format, rate limit behavior confirmed via FREE_TRANSLATION_APIS.md research

### Tertiary (LOW confidence — needs verification at implementation time)
- LibreTranslate public instances (`translate.argosopentech.com`, etc.) — Instance availability as of Feb 2026 unverified; code handles 403/timeout gracefully
- Lingva instances (`lingva.ml`, etc.) — Community-operated; may be offline

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all existing stdlib/libraries verified in codebase
- Architecture patterns: HIGH — complete codebase read; all integration points identified; pre-existing FreeTranslationManager already written
- API behavior: HIGH for MyMemory (10+ years stable), MEDIUM for LibreTranslate instances, LOW-MEDIUM for Lingva instances
- Pitfalls: HIGH — identified from codebase review + Phase 1 verifier flags

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (MyMemory/DeepL/Google APIs stable; Lingva/LibreTranslate instance list should be re-verified before ship)
