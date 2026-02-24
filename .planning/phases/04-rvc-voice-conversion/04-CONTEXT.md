# Phase 4: RVC Voice Conversion - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can apply their own RVC voice models to TTS output as a post-processing step. Load .pth voice models, adjust conversion parameters, and hear TTS audio transformed to the selected voice. RVC is optional — disabling it returns to normal TTS output.

</domain>

<decisions>
## Implementation Decisions

### Model loading & memory management
- Model selection: Folder scan + browse. Scan a default models folder and show up to 5 most recent .pth files in a dropdown. "Browse..." option at the bottom for files elsewhere on disk
- .index files: Optional. Auto-detect by matching filename in the same folder as .pth. If not found, RVC still works (less accurate timbre) — no error, no requirement
- Load timing: Model loads immediately on selection in settings. Show loading progress in the settings UI. Model is warm and ready for first TTS call
- Base model download (HuBERT + RMVPE, ~400MB): Prompt the user with a confirmation dialog before downloading. "RVC needs to download ~400MB of base models. Download now?" One-time setup
- Memory: Show memory usage indicator (e.g., "RVC: 1.5 GB") only when a model is actively loaded. "Unload Model" button frees memory immediately. Disabling the RVC toggle also unloads the model

### Voice conversion quality controls
- Full control panel exposed: Pitch shift (-12 to +12 semitones), Index Rate (0-1), Filter Radius, Resample Rate, Volume Envelope, Protect Consonants
- All sliders have sensible defaults so users don't need to touch them unless they want to
- "Test Voice" button: Records 3 seconds from user's microphone, converts through current RVC model, plays back. User hears THEIR voice transformed
- A/B comparison: No special feature — the enable/disable toggle is the A/B test

### Integration into TTS pipeline
- Hook point: After TTS engine produces audio bytes, before playback + VRChat/overlay send. RVC is a transparent post-processor
- Acceptable latency: Up to 5 seconds on CPU. Users are already waiting for STT + AI + TTS — a few more seconds is tolerable
- Failure behavior: Fall back to original (unconverted) TTS audio + warning toast "Voice conversion failed — playing original audio." Pipeline never breaks
- Audio scope: Configurable per source. User can control which audio sources go through RVC (e.g., TTS yes, system sounds no). Default: TTS output only

### Settings UI layout
- Separate top-level settings section (same level as STT, Translation, TTS, AI). Not nested inside TTS
- Empty state: Show enable toggle (disabled state), model selector (empty dropdown), and message: "Select a voice model to enable voice conversion"
- Model dropdown: Shows up to 5 most recently used .pth models from the scanned folder. "Browse..." at the bottom for other files
- Memory indicator: Only shown when a model is loaded
- All quality sliders visible when model is loaded. Disabled/grayed when no model selected

### Claude's Discretion
- Default models folder location (reasonable default like `models/rvc/` or user's home directory)
- Exact slider ranges and step values for each RVC parameter
- Loading progress UI implementation (progress bar vs. spinner vs. percentage text)
- How to handle the 3-second mic recording for "Test Voice" (reuse existing mic infrastructure or separate)
- Internal RVC wrapper architecture (direct port vs. rvc-python vs. custom)
- Exact audio format conversions between TTS output and RVC input
- Per-source toggle UI design for the configurable audio scope

</decisions>

<specifics>
## Specific Ideas

- User has a local RVC project at `C:\repos\RVC\RVC1006AMD_Intel\` — this is the AMD/Intel-optimized variant targeting CPU and DirectML (not CUDA)
- Research in `.planning/research/RVC_INTEGRATION.md` covers the direct port approach, rvc-python, HuBERT/RMVPE pipeline, and memory estimates
- The full control panel (Pitch, Index Rate, Filter Radius, Resample Rate, Volume Envelope, Protect Consonants) follows standard RVC parameter names
- "Test Voice" records live from the user's microphone — this is different from typical "play a sample" buttons. It lets users hear their OWN voice transformed

</specifics>

<deferred>
## Deferred Ideas

- GPU/CUDA acceleration for faster conversion — could be a v2 optimization
- Voice model training within the app — entirely separate feature
- Real-time streaming RVC (convert audio as it's being generated) — requires fundamental architecture change
- Voice model marketplace or sharing — out of scope

</deferred>

---

*Phase: 04-rvc-voice-conversion*
*Context gathered: 2026-02-24*
