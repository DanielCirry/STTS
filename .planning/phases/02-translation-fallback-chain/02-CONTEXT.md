# Phase 2: Translation Fallback Chain - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Translation works for free without API keys, with paid APIs as optional upgrade, and local NLLB as ultimate fallback. Seamless provider switching with user notification. Fixed fallback chain, no user-configurable priority.

</domain>

<decisions>
## Implementation Decisions

### Fallback chain order & triggers
- Default mode (no API keys): Free APIs first (MyMemory -> LibreTranslate -> Lingva -> local NLLB)
- When paid keys configured: Paid first (DeepL/Google) -> Free chain -> local NLLB
- Failure trigger: Any error OR slow response (>5s timeout) triggers immediate switch to next provider
- Cooldown: MyMemory daily limit = retry next day (UTC midnight reset). Transient errors = 5-minute cooldown after 3 consecutive failures
- Fixed chain order, not user-configurable

### Provider switching notification
- On switch: Warning toast (yellow, auto-dismiss 5s). Example: "Translation switched to LibreTranslate (MyMemory daily limit reached)"
- StatusBar: Always show active translation provider (e.g., "Trans: MyMemory" or "Trans: NLLB") next to the language pair
- Total failure (all providers exhausted): Sticky error toast with guidance + original text in chat with [no translation available] tag
- Recovery: Subtle info toast when a provider comes back online (e.g., "Translation restored via MyMemory"), auto-dismiss

### Settings & configuration
- Add "Free (No API Key)" as a new translation provider dropdown option — make it the default for new users
- MyMemory email field goes in Credentials/API section, near other API keys. Label: "MyMemory Email (optional) — increases daily limit from 5K to 50K chars"
- No drag-to-reorder. Fixed chain: paid (if keys) -> free (MyMemory -> LibreTranslate -> Lingva) -> local NLLB
- No per-provider toggles. Keep it simple — the chain handles failures automatically

### VRChat behavior on translation failure
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

</decisions>

<specifics>
## Specific Ideas

- Research from new-project phase already includes a complete `FreeTranslationManager` class with all 3 providers, rate limit detection, cooldown tracking, and language code mapping in `.planning/research/FREE_TRANSLATION_APIS.md`
- The existing `CloudTranslationManager` pattern should be extended, not replaced
- `'free'` should be added as a valid `TranslationProvider` value alongside `'local'`, `'deepl'`, `'google'`
- No new Python dependencies — use stdlib urllib like existing cloud translator
- Phase 1's `_switch_translation_provider()` in engine.py needs to be updated to work with the new fallback chain instead of the simple cloud->local switch

</specifics>

<deferred>
## Deferred Ideas

- Azure Translator as additional keyed provider (2M chars/month free tier) — noted in research, deferred to v2 as POL-07
- User-configurable LibreTranslate instance list — nice-to-have but not essential for v1
- Per-provider quality comparison/benchmarking — out of scope

</deferred>

---

*Phase: 02-translation-fallback-chain*
*Context gathered: 2026-02-24*
