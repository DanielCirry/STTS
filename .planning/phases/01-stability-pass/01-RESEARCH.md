# Phase 1: Stability Pass - Research

**Researched:** 2026-02-24
**Domain:** Python error handling, WebSocket reconnection, React error UI, PyInstaller freeze_support
**Confidence:** HIGH (all findings based on direct codebase inspection)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Error Feedback
- **Desktop:** Toast notifications, 5 seconds, auto-dismiss
- **VR:** Errors shown in VR overlay so headset users don't miss them
- **Persistent:** Status bar badge (red dot/counter) + system messages in chat for important errors — nothing gets lost
- **Severity levels:** Two — Warning (yellow, auto-dismiss, recoverable) and Error (red, sticky, needs attention)

#### Reconnection Behavior
- **Visual:** Yellow/red banner across top of app + disable mic/TTS controls until reconnected
- **Strategy:** Never give up — exponential backoff (1s, 2s, 4s, 8s... capped at 30s)
- **Restore:** Full state restore on reconnect — re-send settings, reload active models, resume STT/TTS if they were running
- **VR:** Show "Reconnecting..." in VR overlay

#### Translation Failure Handling
- **Message display:** Show original untranslated text with "[translation failed]" tag — user still sees what was said
- **VRChat:** Do NOT send untranslated text to VRChat OSC — only send successfully translated messages
- **Provider switching:** Auto-switch to next provider after 3 consecutive failures
- **Manual override:** User can pin a preferred translation provider in settings — fallback still activates if pinned provider fails

#### Model Loading UX
- **Failure options:** Three buttons — Retry, Skip, Pick Different Model
- **Degraded mode:** App launches and works even if STT model fails to load — STT disabled, everything else works, warning shown
- **Auto-load:** Load last-used STT, TTS, and translation models automatically on startup
- **Non-blocking:** Downloads run in background with progress in status bar — user can use the app while models download

### Claude's Discretion
- Exact toast component implementation
- Banner animation/transition style
- Status bar badge positioning
- Exponential backoff jitter strategy
- Model auto-load ordering/priority

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STAB-01 | Full pipeline (mic → STT → translate → TTS → audio out) works end-to-end without errors | Manual pipeline walkthrough; engine.py has all hooks in place; verification steps identified |
| STAB-02 | Translation errors are caught and fall back gracefully (no crashes or silent failures) | engine.py _process_transcript already catches exceptions but does not apply "[translation failed]" tag or provider switching logic; research shows exact lines to fix |
| STAB-03 | WebSocket reconnection with exponential backoff when backend disconnects | useBackend.ts currently uses fixed 3000ms RECONNECT_INTERVAL; exponential backoff + state restore pattern documented |
| STAB-04 | All model loading errors surface clearly to the user with recovery options | model_error event is broadcast; frontend useBackend.ts handleGlobalMessage 'model_error' only adds a system message; no retry/skip UI exists yet |
| STAB-05 | multiprocessing.freeze_support() added to all entry points for frozen builds | main.py, standalone.py, stts_launcher.py all confirmed missing freeze_support(); EXE_PACKAGING.md confirms this is required |
</phase_requirements>

---

## Summary

STTS is a React + Python WebSocket app. The frontend (Vite/React/Zustand/Tailwind) talks to a Python asyncio WebSocket server (`python/main.py`) via `useBackend.ts`. The engine (`core/engine.py`) coordinates STT (faster-whisper), translation (NLLB local or DeepL/Google cloud), TTS (Edge/Piper/SAPI/VOICEVOX), and VRChat OSC output.

Phase 1 is a surgical error-handling pass with six discrete fix areas. All the backend plumbing (event types, engine callbacks, broadcast) already exists. Most fixes are additions — wrapping existing code in try/except, adding missing UI state, adding backoff logic to the reconnect loop. No architectural changes are needed.

The most impactful changes are: (1) exponential backoff in `useBackend.ts` (replaces fixed 3s reconnect), (2) translation failure handling in `engine.py` (show original + tag, suppress VRChat send), (3) model error UI with Retry/Skip/Pick Different Model buttons (currently only a system chat message), and (4) `freeze_support()` in three entry points (one-liner fix, critical for frozen builds).

**Primary recommendation:** Implement fixes in order — freeze_support first (Python, safest), then translation error handling (Python), then WebSocket reconnection (TypeScript), then error notification UI (TypeScript/React), then model loading UX (React), then E2E pipeline test.

---

## Standard Stack

### Core (already in project — no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React 19 | 19.2.0 | Frontend UI | Already installed |
| Zustand 5 | 5.0.10 | State management | Already installed |
| Tailwind CSS 4 | 4.1.18 | Styling | Already installed |
| Lucide React | 0.563.0 | Icons | Already installed |
| Python asyncio | stdlib | Async backend | Already used |
| websockets | installed in venv | WebSocket server | Already used |

### New Patterns (no new dependencies needed)

No new npm packages or pip packages are required for Phase 1. All fixes use existing libraries and stdlib patterns.

The toast notification system will be built as a small React component using Tailwind (already in project). There is no need to add react-hot-toast, sonner, or any other toast library — the design is simple enough (two severity levels, auto-dismiss, positioning) that hand-rolled is appropriate and keeps the bundle lean.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled toast | react-hot-toast or sonner | External libs add bundle weight and limit VR overlay integration; hand-rolled is ~40 lines and fits existing Tailwind/Zustand patterns |
| Custom reconnect loop | reconnecting-websocket npm package | Package adds complexity; the reconnect logic is ~20 lines and needs tight integration with settings restore |

**Installation:** No new installs required.

---

## Architecture Patterns

### Recommended Project Structure (what changes)

```
python/
├── main.py                  # ADD multiprocessing.freeze_support()
├── standalone.py            # ADD multiprocessing.freeze_support()
├── stts_launcher.py         # ADD multiprocessing.freeze_support()
└── core/
    └── engine.py            # FIX _process_transcript translation error handling
                             # FIX _translate_text consecutive failure counting

src/
├── hooks/
│   └── useBackend.ts        # FIX: exponential backoff reconnect + state restore
├── stores/
│   ├── chatStore.ts         # ADD: error state (toasts, badge counter)
│   └── modelStore.ts        # No changes needed
├── components/
│   ├── Toast.tsx            # NEW: toast notification component
│   ├── ReconnectBanner.tsx  # NEW: top-of-app reconnect status banner
│   └── chat/
│       ├── ChatView.tsx     # ADD: model error dialog (Retry/Skip/Pick Different)
│       └── StatusBar.tsx    # ADD: error badge (red dot + count)
└── App.tsx                  # ADD: Toast/Banner rendering, disable controls on disconnect
```

### Pattern 1: Exponential Backoff WebSocket Reconnect

**What:** Replace fixed-interval reconnect (currently `RECONNECT_INTERVAL = 3000`) with exponential backoff.
**When to use:** Any WebSocket/network connection that should keep trying indefinitely.

Current code in `useBackend.ts` (line 250):
```typescript
reconnectTimeoutRef.current = window.setTimeout(() => {
  connect()
}, RECONNECT_INTERVAL)  // Always 3000ms
```

Replace with:
```typescript
// Module-level reconnect state
let reconnectAttempt = 0
const MIN_RECONNECT_MS = 1000
const MAX_RECONNECT_MS = 30000

function getReconnectDelay(): number {
  // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped)
  // Add small jitter (+/- 200ms) to prevent thundering herd if multiple tabs
  const base = Math.min(MIN_RECONNECT_MS * Math.pow(2, reconnectAttempt), MAX_RECONNECT_MS)
  const jitter = (Math.random() - 0.5) * 400
  return Math.round(base + jitter)
}

// In ws.onclose:
ws.onclose = () => {
  globalConnecting = false
  globalWs = null
  setGlobalConnected(false)
  const delay = getReconnectDelay()
  reconnectAttempt++
  reconnectTimeoutRef.current = window.setTimeout(() => connect(), delay)
}

// On successful connect, reset attempt counter:
ws.onopen = () => {
  reconnectAttempt = 0
  // ... rest of onopen
}
```

### Pattern 2: State Restore After Reconnect

**What:** On reconnect, re-send current settings and reload active models.
**When to use:** After WebSocket re-connects in `ws.onopen`.

```typescript
ws.onopen = () => {
  reconnectAttempt = 0
  globalConnecting = false
  setGlobalConnected(true)
  ws.send(JSON.stringify({ type: 'get_status' }))

  // Re-send settings so backend is in sync
  const settings = useSettingsStore.getState()
  ws.send(JSON.stringify({
    type: 'update_settings',
    payload: buildSettingsPayload(settings)  // same as App.tsx useEffect
  }))

  // Reload active models
  const modelStore = useModelStore.getState()
  if (modelStore.activeModels.stt) {
    ws.send(JSON.stringify({ type: 'load_model', payload: { type: 'stt', id: modelStore.activeModels.stt } }))
  }
  if (modelStore.activeModels.translation) {
    ws.send(JSON.stringify({ type: 'load_model', payload: { type: 'translation', id: modelStore.activeModels.translation } }))
  }
}
```

### Pattern 3: Translation Error Handling with Consecutive Failure Counting

**What:** Track consecutive failures per provider; after 3, switch to next provider. Show "[translation failed]" tag in UI but do NOT send to VRChat.
**When to use:** In `engine.py`'s `_process_transcript` and `process_text_input`.

Current code in `engine.py` (line 526):
```python
except Exception as e:
    logger.error(f"Translation error: {e}")
    translated = None
```

This silently drops the error. The new pattern:

```python
# Add to engine __init__:
self._translation_failure_count = 0
TRANSLATION_FAILURE_THRESHOLD = 3

# In _process_transcript, replace the except block:
except Exception as e:
    logger.error(f"Translation error: {e}")
    translated = None
    self._translation_failure_count += 1
    # Broadcast to frontend: show "[translation failed]" tag
    await self.broadcast(create_event(EventType.TRANSLATION_FAILED, {
        'original': text,
        'error': str(e),
    }))
    # Auto-switch provider after 3 consecutive failures
    if self._translation_failure_count >= TRANSLATION_FAILURE_THRESHOLD:
        self._translation_failure_count = 0
        self._switch_translation_provider()

# On success, reset counter:
translated = self._translate_text(text, source_lang, target_lang)
self._translation_failure_count = 0  # Reset on success

# VRChat send: only if translated is not None
# Current code at line 554 already checks `if translated`, so this is correct.
# VERIFY: send_translations logic only sends `text_to_send = f"{text} - {translated}"` when translated exists
```

Note: A `TRANSLATION_FAILED` event type needs to be added to `core/events.py`.

### Pattern 4: freeze_support in Entry Points

**What:** Add `multiprocessing.freeze_support()` immediately inside `if __name__ == '__main__':` blocks.
**When to use:** Required for any PyInstaller-frozen Python app that uses multiprocessing (PyTorch uses it internally).

```python
# main.py, standalone.py, stts_launcher.py — add at top of if __name__ == '__main__':
if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    # ... rest of existing code
```

This must be the FIRST thing executed before any other imports or logic.

### Pattern 5: Toast Notification System

**What:** Zustand-backed toast queue + React component. Two severity levels.
**When to use:** All error feedback to the user.

```typescript
// Add to chatStore.ts or a new notificationStore.ts
interface Toast {
  id: string
  message: string
  severity: 'warning' | 'error'  // warning = yellow/auto-dismiss, error = red/sticky
  autoDismissMs?: number  // undefined = sticky
}

interface NotificationState {
  toasts: Toast[]
  errorCount: number  // for status bar badge
  addToast: (message: string, severity: 'warning' | 'error') => void
  dismissToast: (id: string) => void
  clearAll: () => void
}
```

Auto-dismiss logic: warnings auto-dismiss after 5000ms (per user decision). Errors are sticky until dismissed by user.

### Pattern 6: Model Error Dialog

**What:** When `model_error` event arrives, show a modal/dialog with three buttons: Retry, Skip, Pick Different Model.
**When to use:** STT, translation, TTS, LLM model load failures.

Currently `handleGlobalMessage` case `'model_error'` only calls `chatStore.addMessage(...)`. Add:
```typescript
case 'model_error':
  modelStore.updateModelStatus(payload.id as string, 'error', undefined, payload.error as string)
  // NEW: trigger error dialog
  notificationStore.showModelError({
    modelType: payload.type as string,
    modelId: payload.id as string,
    error: payload.error as string,
  })
  break
```

The dialog component renders conditionally from the notification store. "Pick Different Model" navigates to the model settings page.

### Anti-Patterns to Avoid

- **Showing untranslated text in VRChat on failure:** CONTEXT.md explicitly forbids this. The current code at engine.py line 554 already gates VRChat send on `if translated`, so the logic is correct — just verify it stays that way.
- **Fixed reconnect interval:** The existing 3000ms constant must be removed. Do not leave it as a fallback.
- **Swallowing model errors silently:** The current `handleGlobalMessage` only adds a system chat message on `model_error`; this is insufficient — a dismissable dialog is required.
- **Calling freeze_support() after other imports:** It must be inside `if __name__ == '__main__':` before anything else runs.
- **Making the toast system require a new npm dependency:** The existing Tailwind + Zustand stack is sufficient.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff formula | Custom complex retry scheduler | Simple `Math.min(base * 2^attempt, cap)` | One-liner, sufficient for this use case |
| Toast animation | CSS transition library | Tailwind `transition-all` + `opacity-0` → `opacity-100` | Already available; no extra dep |
| UUID for toast IDs | UUID library | `crypto.randomUUID()` (already used in chatStore.ts) | Built-in browser API |

**Key insight:** This phase is plumbing, not infrastructure. Every problem here has a 5-30 line solution. Resist the urge to build a "proper notification system" — STTS needs working error handling, not a framework.

---

## Common Pitfalls

### Pitfall 1: freeze_support() Outside `if __name__ == '__main__':`

**What goes wrong:** Calling `multiprocessing.freeze_support()` at module level causes it to run in subprocess workers too, which can create infinite spawning.
**Why it happens:** Developers add it as a top-level call thinking that's "earlier".
**How to avoid:** Always place it as the FIRST line inside `if __name__ == '__main__':`.
**Warning signs:** App starts spawning identical child processes on launch.

### Pitfall 2: State Restore Race Condition on Reconnect

**What goes wrong:** Reconnect sends `update_settings` before the backend engine has re-initialized, so settings are applied to a half-ready engine.
**Why it happens:** `ws.onopen` fires as soon as the TCP connection is established; the backend's `handler()` sends the initial status immediately.
**How to avoid:** Wait for the `status` message (backend sends it immediately on connection) before re-sending settings. The `ws.onmessage` handler already processes the `status` event — trigger the restore there if `status.initialized === true`.

### Pitfall 3: Translation Failure Count Not Resetting on Provider Switch

**What goes wrong:** The failure counter keeps incrementing even after switching providers, causing the new provider to be dropped after 3 failures total rather than 3 failures of the NEW provider.
**Why it happens:** Counter is incremented before the switch check.
**How to avoid:** Reset `_translation_failure_count = 0` immediately when switching providers.

### Pitfall 4: Reconnect Banner Disabling Controls Before Connection is Truly Lost

**What goes wrong:** WebSocket `onerror` fires before `onclose`; disabling controls on `onerror` leaves them disabled even if the connection recovers.
**Why it happens:** Developers react to both `onerror` and `onclose` by setting `connected = false`.
**How to avoid:** Only update `connected` state in `onopen` and `onclose`. The `onerror` is informational; `onclose` always fires after it.

### Pitfall 5: toast/banner z-index Conflicts with Existing UI

**What goes wrong:** The reconnect banner renders behind the right sidebar or the language picker popup.
**Why it happens:** Existing elements use `z-50` (language picker in App.tsx).
**How to avoid:** Use `z-[60]` or higher for the banner/toasts. The banner should be a fixed-position element outside the flex layout.

### Pitfall 6: Model Error Dialog Shown for Non-Critical Model Types

**What goes wrong:** A TTS or LLM model load failure shows a blocking dialog when the user hasn't even enabled that feature.
**Why it happens:** The `model_error` event fires for all model types.
**How to avoid:** Only show the blocking retry/skip dialog for STT model errors (STT is the primary feature). For translation/TTS/LLM model errors, show a toast notification instead.

### Pitfall 7: VRChat Send Logic Already Correct — Don't Break It

**What goes wrong:** In fixing translation error handling, a developer wraps or restructures the VRChat send block and accidentally removes the `if translated` guard.
**Why it happens:** engine.py `_process_transcript` already correctly gates VRChat send at line 554.
**How to avoid:** When editing `_process_transcript`, preserve the existing `if translated and vrchat_settings.get('send_translations', True)` guard. Only add to the except block.

---

## Code Examples

### freeze_support — Exact Pattern for All Three Entry Points

```python
# python/main.py  (line 395-402 currently)
if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()  # ADD THIS — must be first
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

# python/standalone.py  (line 118-119 currently)
if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()  # ADD THIS — must be first
    main()

# python/stts_launcher.py  (line 250-251 currently)
if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()  # ADD THIS — must be first
    main()
```

### Translation Failure Event Type

```python
# python/core/events.py — add to EventType enum
class EventType(str, Enum):
    # ... existing types ...
    TRANSLATION_FAILED = 'translation_failed'  # ADD
```

### Frontend: Handling translation_failed Event

```typescript
// In useBackend.ts handleGlobalMessage:
case 'translation_failed':
  // Show original text with [translation failed] tag in chat
  chatStore.addMessage({
    type: 'user',
    originalText: payload.original as string,
    translationFailed: true,  // chatStore needs this field for display
  })
  // Show warning toast
  notificationStore.addToast('Translation failed — showing original text', 'warning')
  break
```

### Exponential Backoff Full Implementation

```typescript
// useBackend.ts — module level (outside useBackend function)
let reconnectAttempt = 0
const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000

function getReconnectDelay(): number {
  const base = Math.min(RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt), RECONNECT_MAX_MS)
  // Jitter: +/- 200ms to avoid thundering herd
  const jitter = Math.floor((Math.random() - 0.5) * 400)
  return Math.max(RECONNECT_BASE_MS, base + jitter)
}

// In ws.onopen:
ws.onopen = () => {
  reconnectAttempt = 0  // Reset on success
  globalConnecting = false
  setGlobalConnected(true)
  ws.send(JSON.stringify({ type: 'get_status' }))
}

// In ws.onclose:
ws.onclose = () => {
  globalConnecting = false
  globalWs = null
  setGlobalConnected(false)
  const delay = getReconnectDelay()
  reconnectAttempt++
  console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempt})`)
  reconnectTimeoutRef.current = window.setTimeout(() => connect(), delay)
}
```

### Reconnect Banner Component

```tsx
// src/components/ReconnectBanner.tsx
interface ReconnectBannerProps {
  connected: boolean
  reconnectAttempt?: number  // expose for display
}

export function ReconnectBanner({ connected, reconnectAttempt = 0 }: ReconnectBannerProps) {
  if (connected) return null
  return (
    <div className="fixed top-0 left-0 right-0 z-[60] bg-yellow-900/95 border-b border-yellow-700 px-4 py-2 text-sm text-yellow-100 flex items-center gap-2">
      <span className="animate-pulse">●</span>
      <span>
        Disconnected from backend.
        {reconnectAttempt > 0 ? ` Reconnecting... (attempt ${reconnectAttempt})` : ' Reconnecting...'}
      </span>
    </div>
  )
}
```

### Toast Component

```tsx
// src/components/Toast.tsx
export function ToastContainer() {
  const toasts = useNotificationStore(s => s.toasts)
  const dismiss = useNotificationStore(s => s.dismissToast)

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`flex items-start gap-2 px-4 py-3 rounded-lg shadow-lg text-sm max-w-sm
            ${toast.severity === 'error'
              ? 'bg-red-900/95 border border-red-700 text-red-100'
              : 'bg-yellow-900/95 border border-yellow-700 text-yellow-100'
            }`}
        >
          <span className="flex-1">{toast.message}</span>
          <button onClick={() => dismiss(toast.id)} className="shrink-0 opacity-60 hover:opacity-100">
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed reconnect interval | Exponential backoff with jitter | Standard practice since ~2015 | Prevents hammering a restarting backend; avoids thundering herd |
| Silent translation exception | Explicit TRANSLATION_FAILED event | Phase 1 change | User sees what failed, no silent data loss |
| System chat message for model errors | Blocking retry dialog for STT | Phase 1 change | User can recover without restarting the app |

**No deprecated patterns in this phase.** All changes are additions or modifications to existing code.

---

## Open Questions

1. **ChatMessage.translationFailed field**
   - What we know: ChatStore.ChatMessage currently has `originalText`, `translatedText`, `type`, `id`, `timestamp`, `speakerName`
   - What's unclear: Does adding `translationFailed?: boolean` to the interface require updating any serialization/persistence?
   - Recommendation: The chatStore uses no persistence (messages are in-memory only — Zustand without persist middleware for chat). Safe to add the field without migration concerns.

2. **VR overlay error display**
   - What we know: VROverlay (`python/integrations/vr_overlay.py`) has a `show_text()` method. The engine calls it for transcripts and AI responses.
   - What's unclear: Whether errors should be shown via a new `show_error()` method or by passing `message_type='error'` to the existing `show_text()`.
   - Recommendation: Use `show_text(message, message_type='system')` for errors — it's already implemented. Reserve a new `show_error()` for Phase 2 if overlay visual differentiation becomes needed.

3. **Translation provider auto-switch: what providers exist at Phase 1?**
   - What we know: Phase 2 adds the full free translation chain (MyMemory, LibreTranslate, Lingva). Phase 1 only has DeepL and Google (paid, require API keys) plus local NLLB.
   - What's unclear: Should the auto-switch logic in Phase 1 switch between DeepL → Google → local, or only between cloud → local?
   - Recommendation: In Phase 1, implement a simpler two-level fallback: configured cloud provider → local NLLB. The full provider chain is Phase 2's job. Track failure count per cloud provider only; fall back to local after 3 failures.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `C:/repos/STTS/python/main.py`, `standalone.py`, `stts_launcher.py` (confirmed missing freeze_support)
- Direct codebase inspection — `C:/repos/STTS/python/core/engine.py` (confirmed translation exception handling, VRChat send guard)
- Direct codebase inspection — `C:/repos/STTS/src/hooks/useBackend.ts` (confirmed fixed 3000ms reconnect interval)
- Direct codebase inspection — `C:/repos/STTS/src/stores/chatStore.ts`, `modelStore.ts`, `settingsStore.ts`
- Direct codebase inspection — `C:/repos/STTS/src/App.tsx`, `StatusBar.tsx`
- `.planning/research/EXE_PACKAGING.md` — freeze_support analysis and PyInstaller requirements
- `.planning/phases/01-stability-pass/01-CONTEXT.md` — user decisions

### Secondary (MEDIUM confidence)
- Python docs on `multiprocessing.freeze_support()` — requirement is well-established for PyInstaller + multiprocessing
- MDN WebSocket API docs — onclose/onerror behavior is stable across browsers

### Tertiary (LOW confidence)
- None — all findings are directly from codebase inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; confirmed all existing libraries in package.json and venv
- Architecture: HIGH — all patterns derived directly from reading the actual source files
- Pitfalls: HIGH — pitfalls identified from reading the actual code paths that would be modified

**Research date:** 2026-02-24
**Valid until:** This phase is against stable, in-repo code. Research is valid indefinitely until the codebase changes.
