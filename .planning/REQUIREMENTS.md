# Requirements: STTS v1

**Defined:** 2026-02-24
**Core Value:** Real-time voice pipeline that just works — speak, transcribe, translate, speak back — with zero interruptions from rate limits, model failures, or missing dependencies.

## v1 Requirements

### Stability

- [ ] **STAB-01**: Full pipeline (mic → STT → translate → TTS → audio out) works end-to-end without errors
- [ ] **STAB-02**: Translation errors are caught and fall back gracefully (no crashes or silent failures)
- [ ] **STAB-03**: WebSocket reconnection with exponential backoff when backend disconnects
- [ ] **STAB-04**: All model loading errors surface clearly to the user with recovery options
- [ ] **STAB-05**: `multiprocessing.freeze_support()` added to all entry points for frozen builds

### Translation Fallback

- [x] **TRAN-01**: Free translation APIs integrated (MyMemory primary, LibreTranslate secondary, Lingva tertiary)
- [x] **TRAN-02**: Automatic fallback chain: free cloud → paid APIs (DeepL/Google if keys configured) → local NLLB
- [x] **TRAN-03**: Rate limit detection and seamless provider switching without user action
- [x] **TRAN-04**: User notification when provider switches (subtle status bar indicator, not interruptive)
- [x] **TRAN-05**: Translation provider status visible in StatusBar (which provider is active)

### AI Provider Fallback

- [x] **AI-01**: Fallback chain: local LLM → Groq free → Gemini free → paid providers (OpenAI/Anthropic if keys configured)
- [x] **AI-02**: Rate limit detection per provider (429 for Groq/OpenAI, ResourceExhausted for Google, 529 for Anthropic)
- [x] **AI-03**: Seamless provider switching — conversation continues without interruption
- [x] **AI-04**: Shared conversation history maintained across provider switches
- [ ] **AI-05**: User notification on provider switch (status bar pill showing active AI provider)
- [x] **AI-06**: 15-second timeout on all cloud AI calls to prevent hanging
- [x] **AI-07**: Local LLM works as ultimate fallback when no internet available

### RVC Voice Conversion

- [ ] **RVC-01**: RVC post-processor integrated into TTS pipeline (any TTS engine → RVC → output)
- [ ] **RVC-02**: User can select .pth voice model file via file browser
- [ ] **RVC-03**: User can select .index FAISS file (optional)
- [ ] **RVC-04**: Pitch shift configurable (-12 to +12 semitones)
- [ ] **RVC-05**: Index rate configurable (0.0 - 1.0)
- [ ] **RVC-06**: Enable/disable RVC toggle in TTS settings
- [ ] **RVC-07**: RVC works on CPU (GPU optional for faster processing)
- [ ] **RVC-08**: Pre-trained models (HuBERT, RMVPE) auto-download on first use
- [ ] **RVC-09**: "Test Voice" button plays sample with RVC applied
- [ ] **RVC-10**: Models load on selection (not on first TTS call) to avoid latency spike

### Packaging & Distribution

- [ ] **PKG-01**: PyInstaller spec fixed (COLLECT pattern, not --onefile behavior)
- [ ] **PKG-02**: All hidden imports resolved (soundcard, torch, transformers, etc.)
- [ ] **PKG-03**: CPU-only build option (~800MB) without CUDA dependencies
- [ ] **PKG-04**: Portable folder distribution (copy anywhere, run exe)
- [ ] **PKG-05**: NSIS installer for one-click setup
- [ ] **PKG-06**: Works on any Windows 10/11 PC without Python installed
- [ ] **PKG-07**: React frontend bundled into distribution (not separate static server)
- [ ] **PKG-08**: No antivirus false positive blocking (code signing if feasible)

## v2 Requirements

### Polish & Extras

- **POL-01**: Auto-queue long AI responses into multiple VRChat chatbox messages
- **POL-02**: Quantization selector (INT8/FP16/FP32) for models
- **POL-03**: DirectML GPU support for AMD/Intel GPUs
- **POL-04**: Backend settings persistence to disk (survive restart)
- **POL-05**: Connection test buttons per API key in Credentials page
- **POL-06**: CUDA build variant (~3.5GB) for users with NVIDIA GPUs
- **POL-07**: Azure Translator as additional translation provider (2M chars/month free)
- **POL-08**: OpenRouter as user-configurable AI provider option

## Out of Scope

| Feature | Reason |
|---------|--------|
| Tauri wrapper | Current PyInstaller + bundled frontend approach works fine |
| Linux / macOS | Windows-first, can revisit later |
| RVC model training | Users bring their own trained models |
| Multi-user / server | Desktop-only application |
| Mobile / web version | Desktop target only |
| Test suite | No existing tests — adding test coverage is a separate effort |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STAB-01 | Phase 1 | Pending |
| STAB-02 | Phase 1 | Pending |
| STAB-03 | Phase 1 | Pending |
| STAB-04 | Phase 1 | Pending |
| STAB-05 | Phase 1 | Pending |
| TRAN-01 | Phase 2 | Pending |
| TRAN-02 | Phase 2 | Pending |
| TRAN-03 | Phase 2 | Pending |
| TRAN-04 | Phase 2 | Complete (02-02) |
| TRAN-05 | Phase 2 | Complete (02-02) |
| AI-01 | Phase 3 | Complete |
| AI-02 | Phase 3 | Complete |
| AI-03 | Phase 3 | Complete |
| AI-04 | Phase 3 | Complete |
| AI-05 | Phase 3 | Pending |
| AI-06 | Phase 3 | Complete |
| AI-07 | Phase 3 | Complete |
| RVC-01 | Phase 4 | Pending |
| RVC-02 | Phase 4 | Pending |
| RVC-03 | Phase 4 | Pending |
| RVC-04 | Phase 4 | Pending |
| RVC-05 | Phase 4 | Pending |
| RVC-06 | Phase 4 | Pending |
| RVC-07 | Phase 4 | Pending |
| RVC-08 | Phase 4 | Pending |
| RVC-09 | Phase 4 | Pending |
| RVC-10 | Phase 4 | Pending |
| PKG-01 | Phase 5 | Pending |
| PKG-02 | Phase 5 | Pending |
| PKG-03 | Phase 5 | Pending |
| PKG-04 | Phase 5 | Pending |
| PKG-05 | Phase 5 | Pending |
| PKG-06 | Phase 5 | Pending |
| PKG-07 | Phase 5 | Pending |
| PKG-08 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after Phase 2 Plan 02 (TRAN-04, TRAN-05 complete)*
