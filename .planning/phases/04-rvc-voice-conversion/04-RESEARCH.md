# Phase 4: RVC Voice Conversion - Research

**Researched:** 2026-02-24
**Domain:** RVC (Retrieval-based Voice Conversion) — Python inference pipeline, TTS post-processing, audio format handling, React settings UI
**Confidence:** HIGH (based on direct codebase reading + existing project-level RVC_INTEGRATION.md research)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Model loading & memory management**
- Model selection: Folder scan + browse. Scan a default models folder and show up to 5 most recent .pth files in a dropdown. "Browse..." option at the bottom for files elsewhere on disk
- .index files: Optional. Auto-detect by matching filename in the same folder as .pth. If not found, RVC still works (less accurate timbre) — no error, no requirement
- Load timing: Model loads immediately on selection in settings. Show loading progress in the settings UI. Model is warm and ready for first TTS call
- Base model download (HuBERT + RMVPE, ~400MB): Prompt the user with a confirmation dialog before downloading. "RVC needs to download ~400MB of base models. Download now?" One-time setup
- Memory: Show memory usage indicator (e.g., "RVC: 1.5 GB") only when a model is actively loaded. "Unload Model" button frees memory immediately. Disabling the RVC toggle also unloads the model

**Voice conversion quality controls**
- Full control panel exposed: Pitch shift (-12 to +12 semitones), Index Rate (0-1), Filter Radius, Resample Rate, Volume Envelope, Protect Consonants
- All sliders have sensible defaults so users don't need to touch them unless they want to
- "Test Voice" button: Records 3 seconds from user's microphone, converts through current RVC model, plays back. User hears THEIR voice transformed
- A/B comparison: No special feature — the enable/disable toggle is the A/B test

**Integration into TTS pipeline**
- Hook point: After TTS engine produces audio bytes, before playback + VRChat/overlay send. RVC is a transparent post-processor
- Acceptable latency: Up to 5 seconds on CPU. Users are already waiting for STT + AI + TTS — a few more seconds is tolerable
- Failure behavior: Fall back to original (unconverted) TTS audio + warning toast "Voice conversion failed — playing original audio." Pipeline never breaks
- Audio scope: Configurable per source. User can control which audio sources go through RVC (e.g., TTS yes, system sounds no). Default: TTS output only

**Settings UI layout**
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

### Deferred Ideas (OUT OF SCOPE)
- GPU/CUDA acceleration for faster conversion — could be a v2 optimization
- Voice model training within the app — entirely separate feature
- Real-time streaming RVC (convert audio as it's being generated) — requires fundamental architecture change
- Voice model marketplace or sharing — out of scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RVC-01 | RVC post-processor integrated into TTS pipeline (any TTS engine → RVC → output) | Integration point identified in TTSManager.speak() between synthesis and _play_audio(); RVCPostProcessor class design documented |
| RVC-02 | User can select .pth voice model file via file browser | File scan pattern documented; WebSocket handler `rvc_browse_model` + `rvc_scan_models`; OS file dialog via tkinter or os.listdir |
| RVC-03 | User can select .index FAISS file (optional) | Auto-detect pattern documented: same dir as .pth, same stem, .index extension; graceful skip when missing |
| RVC-04 | Pitch shift configurable (-12 to +12 semitones) | f0_up_key parameter in RVCPostProcessor; range and step documented |
| RVC-05 | Index rate configurable (0.0 - 1.0) | index_rate parameter; skip FAISS entirely when 0.0 for performance |
| RVC-06 | Enable/disable RVC toggle in TTS settings | TTSManager._rvc guard; settings['rvc']['enabled']; disabling also unloads model |
| RVC-07 | RVC works on CPU (GPU optional for faster processing) | CPU-only inference documented; DirectML optional; torch.set_num_threads() tuning |
| RVC-08 | Pre-trained models (HuBERT, RMVPE) auto-download on first use | Download via huggingface_hub; confirmation dialog before ~400MB download; path resolution order documented |
| RVC-09 | "Test Voice" button plays sample with RVC applied | 3-second mic capture → RVC → playback; reuse AudioManager infrastructure |
| RVC-10 | Models load on selection (not on first TTS call) to avoid latency spike | load_models() called on model selection in settings; run in executor thread |
</phase_requirements>

---

## Summary

Phase 4 implements RVC (Retrieval-based Voice Conversion) as an optional post-processing step in the existing TTS pipeline. The integration point is clean and well-defined: in `TTSManager.speak()`, between `engine.synthesize(text)` returning a `TTSResult` and `_play_audio(result)` consuming it. A single conditional call to `RVCPostProcessor.process(result)` transparently converts the audio without touching any TTS engine code.

The technical approach is a direct port of the inference code from the user's local AMD/Intel RVC repository (`C:\repos\RVC\`). This is preferred over pip packages (`rvc-python`, `rvc-infer`) because it preserves DirectML device paths for AMD/Intel GPU acceleration, guarantees model compatibility with the user's trained `.pth` files, and avoids dependency conflicts. The ported inference code goes into `python/ai/rvc/` as a package, with a clean async wrapper class `RVCPostProcessor` in `python/ai/tts/rvc_postprocess.py`.

The frontend adds a new top-level settings section "Voice Conversion" following the exact same pattern used by existing settings pages (TTS, AI, Translation). Backend communication uses the existing `update_settings` + new dedicated WebSocket message types for model scanning, browsing, and loading status. Memory management is explicit: model loads on selection, unloads on toggle-off or "Unload Model" button, with a RAM indicator shown only when active.

**Primary recommendation:** Port inference code from local RVC repo into `python/ai/rvc/`, wrap with `RVCPostProcessor`, integrate as a single optional post-processing step in `TTSManager.speak()`, and add a new "Voice Conversion" settings page following the `SettingsView.tsx` page pattern.

---

## Standard Stack

### Core (Python backend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `torch` | >=2.0.0 (already in requirements.txt) | Neural network inference for HuBERT, RMVPE, VITS synthesizer | Already a project dependency (used by Whisper, NLLB) |
| `faiss-cpu` | >=1.7.3 (new dependency) | FAISS index retrieval for timbre matching | Required by RVC pipeline; CPU variant avoids CUDA dependency |
| `librosa` | >=0.9.2,<0.11.0 (new dependency) | Audio resampling to 16kHz for HuBERT input | Standard for audio ML; safer than scipy for complex resampling |
| `soundfile` | latest (likely already present) | Audio I/O: decode WAV bytes to numpy | Already likely installed via piper-tts chain |

### Supporting (Python backend)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `torch-directml` | latest (optional) | AMD/Intel GPU acceleration | Auto-detected at startup; graceful CPU fallback if absent |
| `asyncio.run_in_executor` | stdlib | Run blocking RVC inference without freezing event loop | Required — all RVC CPU steps are blocking |

### Core (Frontend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Zustand `persist` middleware | already in project | RVC settings persistence across sessions | Same pattern as all other settings in `settingsStore.ts` |
| Lucide React icons | already in project | Icons for RVC settings panel | Same icon library used across all settings pages |
| Tailwind CSS | already in project | Slider, toggle, and panel styling | Same styling system as rest of UI |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct port from local RVC repo | `rvc-python` pip package | rvc-python: zero port work, but loses DirectML paths, possible stale code, pins old torch |
| Direct port from local RVC repo | `rvc-infer` pip package | rvc-infer: even less adoption, no compensating benefits |
| `faiss-cpu` | Skip FAISS entirely | Viable if user sets index_rate=0; but removes timbre retrieval quality |
| `librosa` resampling | `scipy.signal.resample_poly` | scipy is already a dep; acceptable fallback if librosa conflicts |

**Installation (new deps only):**
```bash
# Add to python/requirements.txt:
faiss-cpu>=1.7.3
librosa>=0.9.2,<0.11.0
```

---

## Architecture Patterns

### Recommended Project Structure (new files)

```
python/ai/rvc/                     # Ported RVC inference code (from local repo)
    __init__.py
    pipeline.py                    # Core voice conversion logic (from infer/modules/vc/pipeline.py)
    modules.py                     # VC orchestrator — model load + inference (from infer/modules/vc/modules.py)
    rmvpe.py                       # RMVPE pitch extraction (from infer/lib/rmvpe.py)
    audio.py                       # Audio loading utilities (from infer/lib/audio.py)
    config.py                      # GPU/device detection (from configs/config.py)
    models/
        __init__.py
        synthesizer.py             # VITS synthesizer (from infer/lib/infer_pack/models.py)
        attentions.py              # Attention modules (from infer/lib/infer_pack/attentions.py)
        commons.py                 # Shared utilities (from infer/lib/infer_pack/commons.py)
        transforms.py              # Transform utilities (from infer/lib/infer_pack/transforms.py)

python/ai/tts/rvc_postprocess.py   # Clean async wrapper (NEW — the main integration class)

src/components/settings/VoiceConversionSettings.tsx   # New settings panel (NEW)
src/stores/settingsStore.ts        # Add RVCSettings interface + updateRVC() (MODIFY)
src/hooks/useBackend.ts            # Add RVC-specific WebSocket calls (MODIFY)
python/core/events.py              # Add RVC_MODEL_LOADING, RVC_MODEL_LOADED, RVC_STATUS events (MODIFY)
python/core/engine.py              # Add _rvc field, rvc settings handling in update_settings() (MODIFY)
python/ai/tts/manager.py           # Add RVC post-processing step in speak() (MODIFY)
python/main.py                     # Add WebSocket handlers: rvc_scan_models, rvc_load_model, rvc_unload, rvc_test_voice (MODIFY)
```

### Pattern 1: TTS Post-Processing Hook

**What:** Insert optional RVC conversion between synthesis and playback in `TTSManager.speak()`.

**When to use:** Always — this is the single integration point.

```python
# Source: python/ai/tts/manager.py (to be modified)
async def speak(self, text: str) -> bool:
    # ... (existing setup code) ...
    result = await engine.synthesize(text)       # → TTSResult (bytes + sample_rate)

    if self._stop_requested:
        return False

    # RVC post-processing (new)
    if self._rvc and self._rvc.is_enabled():
        try:
            result = await self._rvc.process(result)   # → TTSResult (converted audio)
        except Exception as e:
            logger.warning(f"RVC conversion failed, using original audio: {e}")
            if self.on_rvc_failed:
                self.on_rvc_failed(str(e))
            # result unchanged — fall back to original TTS audio

    await self._play_audio(result)
    return True
```

### Pattern 2: RVCPostProcessor Class Design

**What:** Async wrapper around ported RVC inference code. Keeps all models warm between calls.

**When to use:** Instantiated by TTSManager; controlled via engine.py settings calls.

```python
# Source: python/ai/tts/rvc_postprocess.py (new file)
import asyncio
import logging
from typing import Optional
import numpy as np
import torch
from ai.tts.base import TTSResult

logger = logging.getLogger('stts.rvc')

class RVCPostProcessor:
    """RVC voice conversion post-processor for TTS output."""

    def __init__(self):
        self._enabled: bool = False
        self._model_path: Optional[str] = None
        self._index_path: Optional[str] = None
        self._device: torch.device = torch.device('cpu')

        # Loaded models (kept warm in memory)
        self._hubert: Optional[object] = None
        self._rmvpe: Optional[object] = None
        self._synthesizer: Optional[object] = None
        self._index: Optional[object] = None  # faiss.Index or None

        # Conversion parameters (sensible defaults)
        self.f0_up_key: int = 0           # Pitch shift in semitones (-12 to +12)
        self.index_rate: float = 0.75     # FAISS influence (0.0-1.0); 0 skips FAISS
        self.filter_radius: int = 3       # Pitch smoothing (1-7)
        self.rms_mix_rate: float = 0.25   # Volume envelope matching (0.0-1.0)
        self.protect: float = 0.33        # Consonant protection (0.0-0.5)
        self.resample_sr: int = 0         # Output resample rate (0 = no resample)

    def is_enabled(self) -> bool:
        return self._enabled and self._synthesizer is not None

    def enable(self, enabled: bool):
        """Enable or disable RVC. Disabling does NOT unload models."""
        self._enabled = enabled

    async def load_models(
        self,
        model_path: str,
        index_path: Optional[str],
        hubert_path: str,
        rmvpe_path: str,
        on_progress: Optional[callable] = None
    ) -> bool:
        """Load voice model and base models. Runs in thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._load_models_sync,
            model_path, index_path, hubert_path, rmvpe_path, on_progress
        )

    def _load_models_sync(self, model_path, index_path, hubert_path, rmvpe_path, on_progress):
        """Synchronous model loading — called in thread pool."""
        try:
            # Load HuBERT (if not already loaded)
            if self._hubert is None:
                from ai.rvc.modules import load_hubert
                self._hubert = load_hubert(hubert_path, self._device)
                if on_progress: on_progress(33)

            # Load RMVPE (if not already loaded)
            if self._rmvpe is None:
                from ai.rvc.rmvpe import RMVPE
                self._rmvpe = RMVPE(rmvpe_path, self._device)
                if on_progress: on_progress(66)

            # Load voice synthesizer
            from ai.rvc.modules import load_synthesizer
            self._synthesizer = load_synthesizer(model_path, self._device)
            self._model_path = model_path

            # Load FAISS index (optional)
            if index_path:
                try:
                    import faiss
                    self._index = faiss.read_index(index_path)
                    self._index_path = index_path
                except Exception as e:
                    logger.warning(f"FAISS index load failed (continuing without): {e}")
                    self._index = None

            if on_progress: on_progress(100)
            return True
        except Exception as e:
            logger.error(f"RVC model load failed: {e}")
            return False

    async def process(self, result: TTSResult) -> TTSResult:
        """Convert TTSResult audio through RVC. Runs in thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._process_sync, result)

    def _process_sync(self, result: TTSResult) -> TTSResult:
        """Synchronous RVC inference — called in thread pool."""
        with torch.no_grad():
            # Decode TTSResult bytes to float32 numpy array
            audio_array, sr = _decode_tts_result(result)

            # Run RVC pipeline (pipeline.py VC class)
            from ai.rvc.pipeline import VC
            vc = VC(self._synthesizer, self._hubert, self._rmvpe, self._device)
            converted = vc.pipeline(
                audio=audio_array,
                f0_up_key=self.f0_up_key,
                index=self._index,
                index_rate=self.index_rate if self._index else 0,
                filter_radius=self.filter_radius,
                rms_mix_rate=self.rms_mix_rate,
                protect=self.protect,
                resample_sr=self.resample_sr,
            )

            # Encode back to WAV bytes
            import io, wave
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self._synthesizer.target_sr)
                pcm = (converted * 32767).astype(np.int16)
                wf.writeframes(pcm.tobytes())
            return TTSResult(
                audio_data=buf.getvalue(),
                sample_rate=self._synthesizer.target_sr,
                channels=1,
                sample_width=2
            )

    def unload(self):
        """Free all model memory."""
        self._synthesizer = None
        self._index = None
        # HuBERT and RMVPE are base models — keep them loaded unless explicitly asked
        # (they don't change when switching voice models)
        self._model_path = None
        self._index_path = None

    def unload_all(self):
        """Free ALL model memory including HuBERT and RMVPE."""
        self._hubert = None
        self._rmvpe = None
        self.unload()

    def get_memory_estimate_mb(self) -> int:
        """Rough RAM usage estimate when models are loaded."""
        if self._synthesizer is None:
            return 0
        # HuBERT ~700MB + RMVPE ~300MB + voice model ~100-400MB + FAISS ~50-200MB
        return 1200  # Conservative estimate; actual varies by model
```

### Pattern 3: Audio Format Conversion

**What:** TTS engines return different formats — RVC needs 16kHz mono float32 for HuBERT input.

**When to use:** Inside `_process_sync()` before HuBERT feature extraction.

```python
# Source: python/ai/tts/rvc_postprocess.py (helper function)
import io, wave
import numpy as np
import librosa

def _decode_tts_result(result: 'TTSResult') -> tuple[np.ndarray, int]:
    """Decode TTSResult bytes to (float32 ndarray, sample_rate).

    Handles WAV, MP3 (Edge TTS), and raw PCM.
    Returns mono float32 array in range [-1.0, 1.0].
    """
    data = result.audio_data

    if data[:4] == b'RIFF':
        # WAV format (Piper, SAPI, VOICEVOX)
        with wave.open(io.BytesIO(data), 'rb') as wf:
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    elif data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
        # MP3 format (Edge TTS)
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(io.BytesIO(data))
        audio = audio.set_channels(1)
        arr = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0
        sr = audio.frame_rate

    else:
        # Raw PCM fallback
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        sr = result.sample_rate

    return arr, sr
```

### Pattern 4: Backend Settings Integration

**What:** RVC settings flow through the same `update_settings` WebSocket message, plus dedicated messages for model operations.

**When to use:** All RVC settings go through `engine.update_settings({'rvc': {...}})`. Model loading/unloading uses dedicated messages.

```python
# In python/core/engine.py — add to __init__ settings dict:
'rvc': {
    'enabled': False,
    'model_path': None,
    'index_path': None,
    'models_dir': 'models/rvc',      # default scan dir
    'f0_up_key': 0,
    'index_rate': 0.75,
    'filter_radius': 3,
    'rms_mix_rate': 0.25,
    'protect': 0.33,
    'resample_sr': 0,
}

# In python/core/engine.py — add to update_settings():
if self._tts and 'rvc' in settings:
    rvc_settings = settings['rvc']
    if 'enabled' in rvc_settings:
        enabled = rvc_settings['enabled']
        self._tts.set_rvc_enabled(enabled)
        if not enabled and self._tts._rvc:
            self._tts._rvc.unload_all()
    # Apply parameter changes if RVC is loaded
    if self._tts._rvc:
        for param in ('f0_up_key', 'index_rate', 'filter_radius', 'rms_mix_rate', 'protect', 'resample_sr'):
            if param in rvc_settings:
                setattr(self._tts._rvc, param, rvc_settings[param])
```

**New WebSocket message types (add to `python/main.py`):**

```python
elif msg_type == 'rvc_scan_models':
    # Scan models/rvc/ dir for .pth files; return up to 5 most recent
    models_dir = payload.get('dir', engine.settings['rvc']['models_dir'])
    models = engine.scan_rvc_models(models_dir)
    await websocket.send(json.dumps({'type': 'rvc_models_list', 'payload': {'models': models}}))

elif msg_type == 'rvc_load_model':
    # Load voice model (immediate, shows progress via rvc_loading events)
    model_path = payload.get('model_path')
    index_path = payload.get('index_path')  # may be None
    success = await engine.load_rvc_model(model_path, index_path)
    await websocket.send(json.dumps({'type': 'rvc_model_loaded' if success else 'rvc_model_error',
                                     'payload': {'model_path': model_path, 'success': success}}))

elif msg_type == 'rvc_unload':
    # Free all RVC model memory
    if engine._tts and engine._tts._rvc:
        engine._tts._rvc.unload_all()
    await websocket.send(json.dumps({'type': 'rvc_unloaded', 'payload': {}}))

elif msg_type == 'rvc_test_voice':
    # Record 3 sec from mic, run RVC, play back
    success = await engine.rvc_test_voice()
    await websocket.send(json.dumps({'type': 'rvc_test_complete', 'payload': {'success': success}}))

elif msg_type == 'rvc_check_base_models':
    # Check if HuBERT and RMVPE are available locally
    status = engine.check_rvc_base_models()
    await websocket.send(json.dumps({'type': 'rvc_base_models_status', 'payload': status}))

elif msg_type == 'rvc_download_base_models':
    # Download HuBERT + RMVPE from HuggingFace (user confirmed dialog)
    asyncio.create_task(engine.download_rvc_base_models())
```

### Pattern 5: Frontend Settings Page Addition

**What:** New "Voice Conversion" entry in `settingsPages` array + `VoiceConversionSettings` component.

**When to use:** Add to `SettingsView.tsx` following exact same page pattern as existing settings.

```typescript
// In src/components/settings/SettingsView.tsx

// 1. Add to SettingsPage type:
type SettingsPage = 'main' | 'models' | 'translation' | 'tts' | 'ai' | 'overlay' | 'audio' | 'credentials' | 'voiceConversion'

// 2. Add to settingsPages array (import Wand2 or Mic2 from lucide-react):
{ id: 'voiceConversion' as const, label: 'Voice Conversion', icon: Mic2 }

// 3. Add case to renderContent():
case 'voiceConversion':
  return <VoiceConversionSettings />

// 4. Import from new file:
import { VoiceConversionSettings } from './VoiceConversionSettings'
```

**RVC settings in Zustand store (add to `settingsStore.ts`):**

```typescript
interface RVCSettings {
  enabled: boolean
  modelPath: string | null
  indexPath: string | null
  modelsDir: string
  f0UpKey: number          // -12 to +12
  indexRate: number        // 0.0 to 1.0
  filterRadius: number     // 1 to 7
  rmsMixRate: number       // 0.0 to 1.0
  protect: number          // 0.0 to 0.5
  resampleSr: number       // 0 = no resample
}

// Default values:
rvc: {
  enabled: false,
  modelPath: null,
  indexPath: null,
  modelsDir: 'models/rvc',
  f0UpKey: 0,
  indexRate: 0.75,
  filterRadius: 3,
  rmsMixRate: 0.25,
  protect: 0.33,
  resampleSr: 0,
}
```

### Pattern 6: New Event Types

**What:** Add RVC-specific events to `core/events.py` EventType enum.

```python
# In python/core/events.py — add to EventType:
RVC_MODEL_LOADING = 'rvc_model_loading'
RVC_MODEL_LOADED = 'rvc_model_loaded'
RVC_MODEL_ERROR = 'rvc_model_error'
RVC_UNLOADED = 'rvc_unloaded'
RVC_STATUS = 'rvc_status'
```

### Anti-Patterns to Avoid

- **Calling RVC synchronously in the event loop:** All `_load_models_sync()` and `_process_sync()` calls MUST go through `run_in_executor`. STTS is fully async — blocking the event loop for 1-5 seconds freezes WebSocket handling, mic capture, and OSC output.
- **Lazy model loading on first TTS call:** HuBERT + RMVPE + voice model cold load takes 15-30 seconds. Must load on model selection in settings, not on first use. See pitfall 1.
- **Rewriting imports using sys.path manipulation:** Adding the RVC project root to sys.path creates namespace collisions with STTS modules. Rewrite all imports to use `from ai.rvc.xxx import yyy` paths.
- **Assuming FAISS is available:** `faiss-cpu` on Windows can fail to install. Build graceful degradation: if FAISS import fails, set `index_rate = 0` automatically and warn the user.
- **Re-encoding/decoding audio unnecessarily:** The `_play_audio()` method already decodes audio from `TTSResult`. Let RVC operate on the decoded numpy array and return a WAV-encoded `TTSResult` to avoid triple encode/decode cycles.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio decoding (MP3/WAV → numpy) | Custom byte parser | pydub (MP3) / wave stdlib (WAV) — already in codebase | Already implemented in `_decode_mp3()` and `_decode_wav()` in manager.py |
| Audio resampling to 16kHz | Custom interpolation | `librosa.resample()` | Handles all edge cases (non-integer ratios, mono/stereo, float32) |
| HuBERT feature extraction | Custom transformer | Copy from local RVC repo's `infer/modules/vc/modules.py` | Already solved; battle-tested with the user's exact model files |
| RMVPE pitch extraction | Custom F0 estimator | Copy from local RVC repo's `infer/lib/rmvpe.py` | RMVPE is a neural model; hand-rolling F0 extraction produces poor results |
| FAISS index retrieval | Custom vector search | faiss-cpu library | FAISS handles L2/IP search at scale; custom KNN would be 100x slower |
| Download progress tracking | Custom HTTP progress | `utils/download.py` `patch_transformers_download_progress` | Already implemented for HuggingFace downloads; reuse for HuBERT/RMVPE download |
| WebSocket settings propagation | Custom settings bus | `update_settings` message (existing pattern) | Engine already handles deep merge of settings dicts in `update_settings()` |

**Key insight:** The entire RVC inference stack is already solved in the user's local RVC repository. The work is porting, wrapping, and integrating — not building from scratch.

---

## Common Pitfalls

### Pitfall 1: Cold Load Latency on First TTS Call
**What goes wrong:** If HuBERT + RMVPE + voice model are loaded lazily on first `speak()` call, the user experiences a 15-30 second freeze on the first TTS after enabling RVC. This makes the feature appear broken.
**Why it happens:** Model loading is synchronous and CPU-bound.
**How to avoid:** Load models immediately when the user selects a voice model in the settings UI (`rvc_load_model` WebSocket message). Show loading progress (spinner/bar) in the settings panel. Model is warm before first TTS call.
**Warning signs:** If `load_models()` is called inside `speak()` or `process()` rather than in the settings handler.

### Pitfall 2: Audio Format Assumption Causing Silent/Garbled Output
**What goes wrong:** RVC HuBERT requires 16kHz mono float32. Different TTS engines return different formats (Piper: WAV 22050Hz, Edge TTS: MP3 24000Hz, VOICEVOX: WAV 24000Hz). Feeding unconverted audio produces garbled output or silent conversion with no obvious error.
**Why it happens:** The RVC pipeline.py assumes pre-processed input format.
**How to avoid:** Always call `_decode_tts_result()` first to get float32 array + sample rate, then resample to 16kHz before passing to HuBERT. The `_play_audio()` in manager.py already shows the decoding pattern to copy.
**Warning signs:** Output audio is much shorter than input, is static noise, or is silent.

### Pitfall 3: Blocking the Async Event Loop
**What goes wrong:** CPU inference for 4-second TTS takes ~3 seconds on CPU. Calling `rvc.process()` without `run_in_executor` freezes WebSocket message handling, microphone input, and OSC output for the entire duration.
**Why it happens:** asyncio is single-threaded — any blocking call blocks everything.
**How to avoid:** Wrap ALL synchronous RVC operations (`_load_models_sync`, `_process_sync`) in `await loop.run_in_executor(None, sync_fn, *args)`. Never call torch inference directly in an `async def` without executor.
**Warning signs:** UI becomes unresponsive during TTS; WebSocket pings time out; mic stops responding mid-speech.

### Pitfall 4: RVC Import Path Collisions
**What goes wrong:** The local RVC repo uses imports like `from infer.lib.infer_pack.models import ...` and `from configs.config import ...`. If you add the RVC project root to `sys.path`, these collide with STTS's own `config.py` or other modules.
**Why it happens:** Python resolves imports by searching sys.path in order; adding a foreign project's root is dangerous.
**How to avoid:** Copy files to `python/ai/rvc/` and rewrite ALL imports to use the new package path: `from ai.rvc.models.synthesizer import ...`, `from ai.rvc.config import ...`. Do not modify sys.path.
**Warning signs:** `ImportError: cannot import name 'X' from 'config'` or mysterious `AttributeError` from the wrong module.

### Pitfall 5: Memory Pressure with Other Models Loaded
**What goes wrong:** On 8 GB RAM: Whisper medium (~1.5 GB) + NLLB 600M (~2.5 GB) + RVC (~1.5 GB) + system = ~7 GB, nearly at limit. Windows may start swapping, causing severe performance degradation or OOM errors.
**Why it happens:** RVC adds 3 significant neural models (HuBERT, RMVPE, VITS) to an already memory-heavy process.
**How to avoid:** Implement `unload_all()` that frees HuBERT, RMVPE, and voice model. Show memory indicator in settings so user is aware. "Unload Model" button is a required feature (RVC-06 via toggle). Disabling the RVC toggle triggers `unload_all()`.
**Warning signs:** Whisper or NLLB inference becomes unusually slow after RVC is loaded; Python process memory in Task Manager > 6 GB.

### Pitfall 6: FAISS Install Failure on Windows
**What goes wrong:** `faiss-cpu` wheel may not be available for Python 3.12+ on Windows, causing `pip install faiss-cpu` to fail with a build error.
**Why it happens:** faiss-cpu wheel coverage varies by Python version.
**How to avoid:** Wrap all `import faiss` calls in try/except. If FAISS is unavailable, force `index_rate = 0` and show a warning in the UI ("FAISS not available — index retrieval disabled"). RVC still works, just with lower timbre accuracy. Test `pip install faiss-cpu` early in the build.
**Warning signs:** `ModuleNotFoundError: No module named 'faiss'` on startup.

### Pitfall 7: HuBERT/RMVPE Path Resolution
**What goes wrong:** HuBERT and RMVPE must be downloaded (~400MB + ~150MB). If the user already has them in the local RVC repo assets, downloading again wastes time and disk.
**Why it happens:** Two separate locations: local RVC repo's `assets/` and STTS's `models/rvc/pretrained/`.
**How to avoid:** Check paths in this order: (1) `models/rvc/pretrained/hubert_base.pt`, (2) `C:\repos\RVC\RVC1006AMD_Intel\RVC1006AMD_Intel1\assets\hubert\hubert_base.pt`. Only prompt for download if neither exists. For download, use `huggingface_hub.hf_hub_download()` with `lj1995/VoiceConversionWebUI` repo.
**Warning signs:** 400MB download triggered even though user already has the files.

### Pitfall 8: Test Voice Recording Race Condition
**What goes wrong:** "Test Voice" records 3 seconds from mic, but AudioManager may already be capturing for STT. Starting a second capture session causes device conflict or captures STT audio instead of a clean test.
**Why it happens:** sounddevice allows only one input stream per device on some configurations.
**How to avoid:** Check `engine.listening` state. If STT is active, temporarily pause mic capture during test recording (stop AudioManager, record 3 sec, restart AudioManager). Or use a separate sounddevice `InputStream` instance on the same device (sounddevice does support multiple readers on some backends). Simpler path: show a "Stop listening before testing voice" message if STT is active.
**Warning signs:** Error from sounddevice about device in use; test recording captures STT processing artifacts.

---

## Code Examples

### Exact Integration Point in TTSManager.speak()

```python
# Source: Reading python/ai/tts/manager.py lines 210-257 (confirmed)
# Current speak() — insert RVC block between synthesize and _play_audio:

async def speak(self, text: str) -> bool:
    if not text.strip():
        return False
    if self._current_engine is None:
        return False

    engine = self._engines[self._current_engine]

    try:
        self._is_speaking = True
        self._stop_requested = False

        if self.on_speaking_started:
            self.on_speaking_started()

        # Synthesize audio (unchanged)
        result = await engine.synthesize(text)

        if self._stop_requested:
            return False

        # === NEW: RVC post-processing ===
        if self._rvc and self._rvc.is_enabled():
            try:
                result = await self._rvc.process(result)
            except Exception as e:
                logger.warning(f"RVC failed, using original TTS audio: {e}")
                if self.on_rvc_failed:
                    self.on_rvc_failed(str(e))
                # Fall through with original result

        # Play audio (unchanged)
        await self._play_audio(result)
        return True

    except Exception as e:
        logger.error(f"TTS error: {e}")
        if self.on_error:
            self.on_error(str(e))
        return False

    finally:
        self._is_speaking = False
        if self.on_speaking_finished:
            self.on_speaking_finished()
```

### TTSManager RVC Control Methods (add to manager.py)

```python
# Source: Pattern from existing set_engine(), set_voice() methods in manager.py
def set_rvc_enabled(self, enabled: bool):
    if self._rvc:
        self._rvc.enable(enabled)
        if not enabled:
            self._rvc.unload_all()

async def load_rvc_model(self, model_path: str, index_path: Optional[str] = None,
                          hubert_path: str = '', rmvpe_path: str = '',
                          on_progress=None) -> bool:
    if self._rvc is None:
        from ai.tts.rvc_postprocess import RVCPostProcessor
        self._rvc = RVCPostProcessor()
    return await self._rvc.load_models(model_path, index_path, hubert_path, rmvpe_path, on_progress)

def set_rvc_params(self, **kwargs):
    if self._rvc:
        for k, v in kwargs.items():
            if hasattr(self._rvc, k):
                setattr(self._rvc, k, v)
```

### RVC Model File Scanning

```python
# Source: Derived from pattern in ai/assistant modules; adapted for .pth files
import os
from pathlib import Path

def scan_rvc_models(self, models_dir: str, max_results: int = 5) -> list[dict]:
    """Scan directory for .pth voice model files.
    Returns up to max_results most recent files.
    """
    results = []
    base = Path(models_dir)
    if not base.exists():
        return results

    pth_files = list(base.glob('**/*.pth'))  # Recursive scan
    # Sort by modification time, newest first
    pth_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for pth in pth_files[:max_results]:
        # Auto-detect .index file (same stem, same dir)
        index_path = pth.with_suffix('.index')
        result = {
            'name': pth.stem,
            'model_path': str(pth),
            'index_path': str(index_path) if index_path.exists() else None,
            'size_mb': round(pth.stat().st_size / (1024 * 1024), 1),
        }
        results.append(result)

    return results
```

### HuBERT/RMVPE Base Model Path Resolution

```python
# Source: python/utils/download.py pattern + RVC_INTEGRATION.md section 8
import os
from pathlib import Path

def get_rvc_base_model_paths(self) -> dict:
    """Resolve paths for HuBERT and RMVPE base models.

    Priority order:
    1. STTS local: models/rvc/pretrained/
    2. Local RVC repo: C:/repos/RVC/.../assets/
    3. Not found (needs download)
    """
    stts_pretrained = Path('models/rvc/pretrained')
    rvc_assets = Path(r'C:/repos/RVC/RVC1006AMD_Intel/RVC1006AMD_Intel1/assets')

    def find_model(filename: str, asset_subdir: str) -> Optional[str]:
        # Check STTS local
        local = stts_pretrained / filename
        if local.exists():
            return str(local)
        # Check user's local RVC repo
        rvc_path = rvc_assets / asset_subdir / filename
        if rvc_path.exists():
            return str(rvc_path)
        return None

    hubert = find_model('hubert_base.pt', 'hubert')
    rmvpe = find_model('rmvpe.pt', 'rmvpe')

    return {
        'hubert': hubert,
        'rmvpe': rmvpe,
        'hubert_found': hubert is not None,
        'rmvpe_found': rmvpe is not None,
        'needs_download': hubert is None or rmvpe is None,
    }
```

### Frontend Toast Pattern for RVC Failure (existing notification system)

```typescript
// Source: Reading src/hooks/useBackend.ts — existing handleGlobalMessage pattern
// Add to handleGlobalMessage() switch in useBackend.ts:

case 'rvc_conversion_failed':
  useNotificationStore.getState().addToast(
    'Voice conversion failed \u2014 playing original audio',
    'warning'  // auto-dismisses after 5s per existing behavior
  )
  break

case 'rvc_model_error':
  useNotificationStore.getState().addToast(
    `Voice model failed to load: ${payload.error as string}`,
    'error'  // sticky — requires user dismiss
  )
  break
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Harvest/Dio pitch extraction (signal processing) | RMVPE (neural network pitch) | 2023 | Significantly better pitch accuracy on speech, faster than Crepe on CPU |
| Single-model voice cloning | RVC v2 (768-dim FAISS index) | 2023 | Better timbre matching; v1 models use 256-dim, v2 uses 768-dim |
| rvc-python pip package | Direct port of inference code | Project decision | Better AMD/Intel GPU support; guaranteed model compatibility |
| CUDA-only RVC | DirectML + CPU fallback | AMD/Intel RVC fork | Works on AMD/Intel GPUs via torch-directml |

**Confirmed current best practices (HIGH confidence — from project's own RVC_INTEGRATION.md research):**
- Use RMVPE pitch method exclusively (best CPU/GPU balance)
- Keep all models warm in memory (HuBERT, RMVPE, voice model, FAISS)
- Skip FAISS retrieval when `index_rate = 0` (performance optimization)
- Run all inference in thread pool executors
- Default `torch.set_num_threads(4)` for CPU inference to leave headroom for other STTS components

---

## Files: What to Create vs. Modify

### Files to CREATE (new)
| File | Type | Description |
|------|------|-------------|
| `python/ai/rvc/__init__.py` | Python package | RVC inference code package init |
| `python/ai/rvc/pipeline.py` | Port from RVC repo | Core VC pipeline (infer/modules/vc/pipeline.py) |
| `python/ai/rvc/modules.py` | Port from RVC repo | VC orchestrator — model loading (infer/modules/vc/modules.py) |
| `python/ai/rvc/rmvpe.py` | Port from RVC repo | RMVPE pitch extraction (infer/lib/rmvpe.py) |
| `python/ai/rvc/audio.py` | Port from RVC repo | Audio utilities (infer/lib/audio.py) |
| `python/ai/rvc/config.py` | Port from RVC repo | Device detection (configs/config.py) |
| `python/ai/rvc/models/__init__.py` | Python package | Synthesizer models package init |
| `python/ai/rvc/models/synthesizer.py` | Port from RVC repo | VITS synthesizer (infer/lib/infer_pack/models.py) |
| `python/ai/rvc/models/attentions.py` | Port from RVC repo | Attention layers (infer/lib/infer_pack/attentions.py) |
| `python/ai/rvc/models/commons.py` | Port from RVC repo | Shared utilities (infer/lib/infer_pack/commons.py) |
| `python/ai/rvc/models/transforms.py` | Port from RVC repo | Transform functions (infer/lib/infer_pack/transforms.py) |
| `python/ai/tts/rvc_postprocess.py` | New Python module | `RVCPostProcessor` async wrapper class |
| `src/components/settings/VoiceConversionSettings.tsx` | New React component | Full Voice Conversion settings panel |

### Files to MODIFY (existing)
| File | Change Summary |
|------|---------------|
| `python/ai/tts/manager.py` | Add `_rvc: Optional[RVCPostProcessor]` field; insert RVC post-processing in `speak()`; add `set_rvc_enabled()`, `load_rvc_model()`, `set_rvc_params()` |
| `python/core/engine.py` | Add `'rvc'` key to `settings` dict; handle `'rvc'` in `update_settings()`; add `scan_rvc_models()`, `load_rvc_model()`, `rvc_test_voice()`, `check_rvc_base_models()`, `download_rvc_base_models()` methods; add to `get_status()` response |
| `python/core/events.py` | Add `RVC_MODEL_LOADING`, `RVC_MODEL_LOADED`, `RVC_MODEL_ERROR`, `RVC_UNLOADED`, `RVC_STATUS` to `EventType` enum |
| `python/main.py` | Add handlers for `rvc_scan_models`, `rvc_load_model`, `rvc_unload`, `rvc_test_voice`, `rvc_check_base_models`, `rvc_download_base_models` message types |
| `python/requirements.txt` | Add `faiss-cpu>=1.7.3` and `librosa>=0.9.2,<0.11.0` |
| `src/stores/settingsStore.ts` | Add `RVCSettings` interface, `rvc` field to `Settings` and defaults, `updateRVC()` action, `persist` key includes rvc |
| `src/hooks/useBackend.ts` | Add cases for `rvc_models_list`, `rvc_model_loaded`, `rvc_model_error`, `rvc_unloaded`, `rvc_status`, `rvc_test_complete`, `rvc_base_models_status`, `rvc_conversion_failed` in message handler; add `scanRVCModels()`, `loadRVCModel()`, `unloadRVC()`, `testRVCVoice()`, `checkRVCBaseModels()`, `downloadRVCBaseModels()` functions to return object |
| `src/components/settings/SettingsView.tsx` | Add `'voiceConversion'` to `SettingsPage` type and `settingsPages` array; import and render `VoiceConversionSettings` |

---

## Open Questions

1. **Local RVC repo availability at runtime**
   - What we know: The CONTEXT.md specifies user has local RVC at `C:\repos\RVC\RVC1006AMD_Intel\`. The HuBERT and RMVPE models are at `assets/hubert/hubert_base.pt` and `assets/rmvpe/rmvpe.pt`.
   - What's unclear: Can we reliably hardcode that fallback path? Will this path exist on other user machines? Is it safe to use as a permanent fallback or only for initial dev convenience?
   - Recommendation: Use the local path as a secondary fallback for development convenience. The production path should be `models/rvc/pretrained/`. Include a one-time "copy from local RVC" action in the UI if files are found there (saves 400MB re-download).

2. **Test Voice mic recording approach**
   - What we know: AudioManager drives mic capture; STT may or may not be active when "Test Voice" is pressed.
   - What's unclear: Whether sounddevice supports simultaneous readers on the same device on Windows; whether we should pause STT or use a separate stream.
   - Recommendation: Simplest approach — if STT is listening, show "Pause listening to test voice" message. If not listening, open a fresh `sounddevice.InputStream` for exactly 3 seconds, then close it. This avoids any interaction with AudioManager.

3. **Slider ranges and step values for Claude's Discretion parameters**
   - What we know: Standard RVC parameter names and their purposes.
   - Recommendation:
     | Parameter | Range | Step | Default |
     |-----------|-------|------|---------|
     | Pitch Shift (f0_up_key) | -12 to +12 | 1 semitone | 0 |
     | Index Rate | 0.0 to 1.0 | 0.05 | 0.75 |
     | Filter Radius | 1 to 7 | 1 | 3 |
     | Volume Envelope (rms_mix_rate) | 0.0 to 1.0 | 0.05 | 0.25 |
     | Protect Consonants | 0.0 to 0.5 | 0.01 | 0.33 |
     | Resample Rate | [0, 16000, 22050, 44100] | discrete | 0 (off) |

4. **Default models folder location**
   - Recommendation: Use `models/rvc/` relative to the application working directory (same level as other model dirs). On frozen PyInstaller builds this resolves relative to the executable directory, which is consistent with how other models are stored. Add a "Browse" option so users can point elsewhere.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase reading: `python/ai/tts/manager.py` — confirmed `TTSResult` dataclass, `speak()` flow, `_play_audio()` format handling
- Direct codebase reading: `python/ai/tts/base.py` — confirmed `TTSResult(audio_data: bytes, sample_rate: int, channels: int, sample_width: int)` exact signature
- Direct codebase reading: `python/core/engine.py` — confirmed `STTSEngine.settings` dict structure, `update_settings()` pattern, `load_model()` broadcast pattern
- Direct codebase reading: `python/core/events.py` — confirmed `EventType` enum members to extend
- Direct codebase reading: `python/main.py` — confirmed WebSocket message handler pattern (elif chain, payload extraction, broadcast)
- Direct codebase reading: `src/components/settings/SettingsView.tsx` — confirmed `settingsPages` array structure, `SettingsPage` type, component pattern for new pages
- Direct codebase reading: `src/hooks/useBackend.ts` — confirmed `handleGlobalMessage()` switch structure, WebSocket send pattern
- Direct codebase reading: `src/stores/settingsStore.ts` — confirmed interface/defaults/Zustand pattern for new settings slice
- Direct codebase reading: `python/utils/download.py` — confirmed `patch_transformers_download_progress()` pattern reusable for RVC downloads
- Project research: `.planning/research/RVC_INTEGRATION.md` — comprehensive RVC approach analysis, pipeline steps, memory estimates, pitfalls

### Secondary (MEDIUM confidence)
- `python/requirements.txt` — confirmed `torch>=2.0.0` already present; `soundfile`, `librosa` NOT currently listed (new deps required)
- RVC_INTEGRATION.md CPU performance estimates: MEDIUM confidence (stated as community benchmarks, actual varies by hardware)
- faiss-cpu Windows compatibility: MEDIUM confidence (noted as potentially problematic for Python 3.12+; test early)

### Tertiary (LOW confidence)
- DirectML acceleration path: LOW confidence (not tested; documented in RVC_INTEGRATION.md based on AMD/Intel RVC fork knowledge; verify actual torch-directml API before implementing)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed by direct codebase reading; existing deps verified in requirements.txt
- Architecture patterns: HIGH — derived from reading actual source files, not assumptions
- Integration point: HIGH — exact code location confirmed (manager.py lines 210-257)
- Pitfalls: HIGH — 5 of 8 are directly confirmed by code reading (async loop, audio formats, import paths); 3 are from existing research
- RVC inference internals: MEDIUM — from RVC_INTEGRATION.md project research; dependent on local RVC repo structure matching assumptions

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (RVC inference API is stable; STTS codebase is rapidly evolving — re-read source files before executing tasks if > 1 week gap)
