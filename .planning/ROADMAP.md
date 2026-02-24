# STTS Roadmap — v1

**Created:** 2026-02-24
**Milestone:** v1.0 — Stable, distributable STTS with fallback chains and RVC

## Phase Overview

| Phase | Name | Requirements | Goal |
|-------|------|-------------|------|
| 1 | Stability Pass | STAB-01 to STAB-05 | End-to-end pipeline works reliably, errors handled gracefully |
| 2 | Translation Fallback Chain | TRAN-01 to TRAN-05 | Free + paid + local translation with seamless switching |
| 3 | AI Provider Fallback Chain | AI-01 to AI-07 | Local-first AI with seamless cloud fallback |
| 4 | RVC Voice Conversion | RVC-01 to RVC-10 | Custom voice models as TTS post-processor |
| 5 | Packaging & Distribution | PKG-01 to PKG-08 | Portable EXE + NSIS installer for any Windows PC |

---

## Phase 1: Stability Pass

**Goal:** Verify the full pipeline works end-to-end and add error handling where it's missing.

**Requirements:** STAB-01, STAB-02, STAB-03, STAB-04, STAB-05

**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Python backend fixes: freeze_support + translation error handling
- [x] 01-02-PLAN.md — Frontend notification system + exponential backoff reconnection
- [x] 01-03-PLAN.md — Error UI wiring: model error dialog, status bar badge, control disabling, E2E verification

**What to build:**
- Manual end-to-end test of: mic → STT → translate → TTS → audio output → VRChat OSC
- Fix translation error handling (from prior chat context — crashes on translation failures)
- Add WebSocket reconnection with exponential backoff (currently reconnects at fixed 3s interval)
- Surface model loading errors clearly in the UI with retry/skip options
- Add `multiprocessing.freeze_support()` to `main.py`, `standalone.py`, `stts_launcher.py`
- Fix `soundcard` missing from PyInstaller builds (from packaging research)

**Success criteria:**
- [ ] Speak in English → see transcription → see Japanese translation → hear TTS → see VRChat chatbox *(human test pending)*
- [x] Kill backend → frontend shows disconnection → backend restarts → frontend reconnects automatically *(code verified)*
- [x] Translation provider fails → error shown to user → fallback works → no crash *(code verified)*
- [x] Model load fails → error message shown → user can retry or skip *(code verified)*

**Dependencies:** None (first phase)

---

## Phase 2: Translation Fallback Chain

**Goal:** Translation works for free without API keys, with paid APIs as optional upgrade, and local NLLB as ultimate fallback.

**Requirements:** TRAN-01, TRAN-02, TRAN-03, TRAN-04, TRAN-05

**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — Python backend: FreeTranslationManager + engine fallback chain + VRChat fix
- [x] 02-02-PLAN.md — Frontend: provider type/stores, event handling, StatusBar pill, settings UI

**What to build:**
- `FreeTranslationManager` class (MyMemory → LibreTranslate → Lingva) matching existing `CloudTranslationManager` pattern
- Rate limit detection per free provider (HTTP 429, daily char limits)
- Automatic fallback chain: free cloud → paid (DeepL/Google if keys set) → local NLLB
- Status bar indicator showing active translation provider
- Optional MyMemory email field in Credentials page (upgrades from 5K to 50K chars/day)
- Update `engine.py` `_translate_text()` to route through fallback chain

**Success criteria:**
- [ ] Translation works with zero API keys configured (MyMemory free tier)
- [ ] Hit MyMemory limit → automatically switches to LibreTranslate → user sees notification
- [ ] All free providers exhausted → falls back to local NLLB
- [ ] If DeepL/Google keys configured → used between free and local tiers
- [ ] StatusBar shows which translation provider is currently active

**Dependencies:** Phase 1 (stability pass — error handling patterns established)

---

## Phase 3: AI Provider Fallback Chain

**Goal:** AI assistant works for free with local LLM, with cloud free tiers as upgrade, and paid APIs only if configured.

**Requirements:** AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, AI-07

**Plans:** 2 plans

Plans:
- [x] 03-01-PLAN.md — Python backend: FallbackAIManager with provider health tracking, fallback chain, engine.py wiring
- [x] 03-02-PLAN.md — Frontend: chatStore AI state, useBackend event handlers, StatusBar AI provider pill

**What to build:**
- `FallbackAIManager` class with provider health tracking and priority chain
- Rate limit detection per provider (429/ResourceExhausted/529 error types)
- Shared conversation history across provider switches
- 15-second timeout wrapper on all cloud AI calls
- Status bar AI provider pill (shows "AI: local", "AI: groq", etc.)
- WebSocket events: `ai_provider_switched`, `ai_offline_mode`, `ai_online_restored`
- Frontend handling of provider switch events (subtle notification, not interruptive)

**Success criteria:**
- [ ] Say "jarvis" → local LLM responds (no API keys needed)
- [ ] Local LLM not loaded → auto-tries Groq free → gets response
- [ ] Groq rate limited → switches to Gemini free → conversation continues seamlessly
- [ ] All cloud providers down → falls back to local LLM → user notified
- [ ] Conversation history preserved when switching providers
- [ ] StatusBar shows current AI provider

**Dependencies:** Phase 1 (error handling), Phase 2 (same fallback pattern — reuse the approach)

---

## Phase 4: RVC Voice Conversion

**Goal:** Users can apply their own RVC voice models to any TTS engine output.

**Requirements:** RVC-01 to RVC-10

**Plans:** 4 plans

Plans:
- [ ] 04-01-PLAN.md — Port RVC inference code + RVCPostProcessor wrapper class
- [ ] 04-02-PLAN.md — Backend integration: TTSManager hook + engine.py WebSocket handlers
- [ ] 04-03-PLAN.md — Frontend: RVC settings store + Voice Conversion settings UI
- [ ] 04-04-PLAN.md — End-to-end wiring: frontend event handlers + Test Voice + verification

**What to build:**
- `python/ai/rvc/` — Ported RVC inference package (pipeline, RMVPE, synthesizer models)
- `python/ai/tts/rvc_postprocess.py` — RVC inference wrapper with async interface
- HuBERT feature extraction + RMVPE pitch extraction pipeline
- Integration into `TTSManager.speak()` as optional post-processing step
- Model file scanner for .pth and .index files with folder browse
- Frontend: "Voice Conversion" as separate top-level settings section with enable toggle, model selector, full quality control panel (pitch, index rate, filter radius, resample rate, volume envelope, protect consonants)
- Model warm-loading on selection (not on first TTS call)
- Explicit unload button (RVC adds ~1.5GB memory)
- Base model (HuBERT + RMVPE) download with user confirmation dialog
- "Test Voice" records 3 seconds from microphone, converts through RVC, plays back

**Success criteria:**
- [ ] Enable RVC → select .pth model → TTS output sounds like the selected voice
- [ ] Pitch shift slider changes output pitch in real-time
- [ ] Works on CPU (1.5-5s added latency is acceptable)
- [ ] HuBERT + RMVPE models auto-download on first use with progress
- [ ] "Test Voice" plays sample through RVC pipeline
- [ ] Disable RVC → TTS output returns to normal
- [ ] Memory usage stays reasonable (unload button works)

**Dependencies:** Phase 1 (stability), no dependency on Phases 2-3

---

## Phase 5: Packaging & Distribution

**Goal:** STTS can be distributed as a working Windows application to any PC.

**Requirements:** PKG-01 to PKG-08

**What to build:**
- Fix PyInstaller spec (COLLECT pattern instead of current broken approach)
- Resolve all hidden imports (soundcard, torch submodules, transformers, etc.)
- CPU-only build variant (~800MB) — exclude CUDA dependencies
- Bundle React frontend into distribution (static files served by Python HTTP server)
- Portable folder distribution (extract and run)
- NSIS installer script for one-click setup
- Test on clean Windows machine (no Python/Node installed)

**Success criteria:**
- [ ] `STTS.exe` launches from portable folder on clean Windows 10/11 PC
- [ ] Full pipeline works in packaged build (STT → translate → TTS → VRChat)
- [ ] NSIS installer installs cleanly, creates start menu shortcut, uninstaller works
- [ ] Bundle size ≤ 800MB for CPU-only build
- [ ] No "DLL not found" or "module not found" errors on target machines

**Dependencies:** All prior phases (package the final working product)

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Free translation APIs change limits | TRAN chain breaks | NLLB local fallback always available |
| Groq/Gemini change free tier | AI chain breaks | Local LLM always available |
| RVC port is complex | Phase 4 delayed | Try rvc-python first; manual port as fallback |
| PyInstaller + PyTorch is fragile | Build breaks | Use --onedir, extensive hidden import list, test on clean VM |
| Bundle size too large | User friction | CPU-only default, CUDA as optional download |
| RVC memory pressure | OOM on 8GB machines | Explicit unload, don't load RVC by default |

---
*Roadmap created: 2026-02-24*
*Last updated: 2026-02-25 after Phase 4 planning (RVC Voice Conversion)*
