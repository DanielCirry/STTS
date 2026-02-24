# STTS — Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-02-24)

**Core value:** Real-time voice pipeline that just works — zero interruptions from rate limits, model failures, or missing dependencies.
**Current focus:** Phase 3 complete — ready for Phase 4 (RVC Voice Conversion)

## Current Milestone

**v1.0** — Stable, distributable STTS with fallback chains and RVC

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Stability Pass | COMPLETE (verified 2026-02-24, 7/7 must-haves, human testing pending) |
| 2 | Translation Fallback Chain | COMPLETE |
| 3 | AI Provider Fallback Chain | COMPLETE |
| 4 | RVC Voice Conversion | NOT STARTED |
| 5 | Packaging & Distribution | NOT STARTED |

## Current Position

**Phase:** 03-ai-provider-fallback-chain (COMPLETE)
**Last completed plan:** 03-02 (Frontend AI Provider Integration)
**Summary:** `.planning/phases/03-ai-provider-fallback-chain/03-02-SUMMARY.md`

## Decisions Log

- **2026-02-24 (01-02):** Warning toasts auto-dismiss after 5s; error toasts are sticky
- **2026-02-24 (01-02):** ReconnectBanner takes props instead of store dependency
- **2026-02-24 (01-02):** Jitter of +/-200ms added to exponential backoff to prevent thundering herd
- **2026-02-24 (01-02):** tailwindcss-animate not installed; using transition-opacity instead of animate-in
- **2026-02-24 (01-03):** STT model errors get blocking dialog; non-STT errors get toast
- **2026-02-24 (01-03):** ModelErrorDialog z-[70] renders above toasts (z-[60]) and banner
- **2026-02-24 (02-01):** FreeTranslationManager always initialized regardless of selected provider (lightweight, no model download)
- **2026-02-24 (02-01):** 5s HTTP timeout per provider request (prevents hanging on slow/dead providers)
- **2026-02-24 (02-01):** VRChat/overlay only receive text when translation succeeds — when enabled and failed, send nothing
- **2026-02-24 (02-01):** 'free' provider value not forwarded to CloudTranslationManager.set_provider() to avoid warning
- **2026-02-24 (02-02):** MyMemory email stored in localStorage credentials not Zustand, consistent with existing API keys pattern
- **2026-02-24 (02-02):** activeTranslationProvider is runtime state in chatStore (not persisted) — reflects current backend state
- **2026-02-24 (02-02):** Recovery toast uses 'warning' severity (auto-dismisses 5s) — notificationStore only has warning and error
- **2026-02-24 (02-02):** 'free' provider treated as cloud in TranslationSettings (isCloud=true) — no local model selection shown
- **2026-02-24 (03-01):** Call provider_obj.generate() directly in FallbackAIManager to avoid premature on_response/on_error callback firing
- **2026-02-24 (03-01):** Local LLM context limit = 4 messages (2 turns), cloud = 10 messages (full default)
- **2026-02-24 (03-01):** Soft-failure AssistantResponse(model='fallback') shown in chat only (not TTS/VRChat)
- **2026-02-24 (03-01):** Application errors re-raised from fallback; only rate limits/timeouts/network errors trigger fallback
- **2026-02-24 (03-01):** Health states persist across conversation clears (only _shared_conversation is reset)
- **2026-02-24 (03-02):** activeAIProvider and aiOfflineMode are runtime state (not persisted) -- reset on reload, backend re-emits on next generate()
- **2026-02-24 (03-02):** AI provider switch always shows toast (differs from translation); offline mode is StatusBar-only per CONTEXT.md locked decisions
- **2026-02-24 (03-02):** Initial provider assignment (from=null, reason=initial) does not trigger toast

## Key Documents

| Document | Path |
|----------|------|
| Project context | `.planning/PROJECT.md` |
| Requirements | `.planning/REQUIREMENTS.md` |
| Roadmap | `.planning/ROADMAP.md` |
| Config | `.planning/config.json` |
| Codebase map | `.planning/codebase/` (7 docs) |
| Research | `.planning/research/` (4 docs) |
| Phase 1 verification | `.planning/phases/01-stability-pass/01-VERIFICATION.md` |

## Research Completed

- `FREE_TRANSLATION_APIS.md` — MyMemory primary, LibreTranslate/Lingva secondary
- `AI_PROVIDER_FALLBACK.md` — local → Groq → Gemini → paid; circuit breaker pattern
- `RVC_INTEGRATION.md` — Direct port recommended; ~1.5GB memory; CPU viable at 1.5-5s latency
- `EXE_PACKAGING.md` — Critical bugs found in current specs; CPU-only ~800MB; NSIS recommended

## Notes

- No auto-commits — user manages git manually
- No test suite exists — all verification is manual
- Architecture: PyInstaller + static server (not Tauri)
- VRChat send-on-failure bug FIXED in 02-01 — untranslated text no longer sent when translation fails

---
*Last updated: 2026-02-24 after Phase 3 Plan 02 (Frontend AI Provider Integration)*
