import { useState, useEffect, useRef, useCallback } from 'react'
import { useBackend } from '@/hooks/useBackend'
import { useFeaturesStore } from '@/stores/featuresStore'
import { useSettingsStore } from '@/stores/settingsStore'

const FEATURES = [
  { id: 'torch_cpu', name: 'PyTorch', description: 'Required for STT, Translation & RVC. Switching CPU/CUDA will restart the app.', torchPick: true },
  { id: 'stt', name: 'Speech-to-Text (Whisper)', description: 'Local speech recognition (~300 MB)' },
  { id: 'translation', name: 'Translation (NLLB)', description: 'Offline translation for 200+ languages (~50 MB)' },
  { id: 'local_llm', name: 'Local LLM (llama.cpp)', description: 'Run AI models locally (~50 MB)' },
  { id: 'rvc', name: 'RVC Voice Conversion', description: 'Real-time voice conversion + base models (~550 MB)' },
  { id: 'piper_tts', name: 'Piper TTS (Offline)', description: 'Offline text-to-speech engine (~150 MB)' },
]

// Estimate progress from pip output keywords — parse real percentages when available
function estimateProgress(detail: string): number {
  if (!detail) return 0.05
  const d = detail.toLowerCase()
  // Try to parse real pip download percentage (e.g., "Downloading foo 45%", "45%|████")
  const pctMatch = detail.match(/(\d{1,3})%/)
  if (pctMatch) {
    const pct = parseInt(pctMatch[1]) / 100
    if (pct > 0 && pct <= 1) return pct
  }
  if (d.includes('installing dependency') || d.includes('pytorch')) return 0.1
  if (d.includes('collecting')) return 0.15
  if (d.includes('downloading')) return 0.4
  if (d.includes('installing')) return 0.7
  if (d.includes('successfully') || d.includes('complete')) return 1
  if (d.includes('verifying')) return 0.9
  return 0.3
}

// VOICEVOX session state (persists across page navigations)
const vvSession = {
  installed: null as boolean | null,
  engineRunning: false,
  installPath: '',
  setupProgress: null as { stage: string; progress: number; detail: string } | null,
  buildType: 'directml' as 'directml' | 'cpu',
}

// Persist across page navigations within session
const session = {
  queue: [] as string[],
  active: null as string | null,
  progress: {} as Record<string, number>, // 0-1
  results: {} as Record<string, 'success' | 'error'>,
  errorMsg: null as string | null,
}

export default function FeaturesManager() {
  const { sendMessage, lastMessage, connected } = useBackend()
  const featuresStatus = useFeaturesStore(s => s.status)
  const installProgress = useFeaturesStore(s => s.installProgress)
  const installResult = useFeaturesStore(s => s.installResult)
  const uninstallResult = useFeaturesStore(s => s.uninstallResult)
  const updateTTS = useSettingsStore(s => s.updateTTS)
  const [queue, setQueue] = useState<string[]>(session.queue)
  const [active, setActive] = useState<string | null>(session.active)
  const [progress, setProgress] = useState<Record<string, number>>(session.progress)
  const [results, setResults] = useState<Record<string, 'success' | 'error'>>(session.results)
  const [errorMsg, setErrorMsg] = useState<string | null>(session.errorMsg)
  const [restartNeeded, setRestartNeeded] = useState(false)
  const activeRef = useRef(active)
  const queueRef = useRef(queue)
  const checkedRef = useRef(false)

  // VOICEVOX Engine state
  const [vvInstalled, setVvInstalled] = useState<boolean | null>(vvSession.installed)
  const [vvEngineRunning, setVvEngineRunning] = useState(vvSession.engineRunning)
  const [vvInstallPath, setVvInstallPath] = useState(vvSession.installPath)
  const [vvSetupProgress, setVvSetupProgress] = useState<{ stage: string; progress: number; detail: string } | null>(vvSession.setupProgress)
  const [vvBuildType, setVvBuildType] = useState<'directml' | 'cpu'>(vvSession.buildType)

  // Sync VOICEVOX session state + global store
  useEffect(() => {
    vvSession.installed = vvInstalled
    useFeaturesStore.getState().setVoicevoxInstalled(vvInstalled)
  }, [vvInstalled])
  useEffect(() => { vvSession.engineRunning = vvEngineRunning }, [vvEngineRunning])
  useEffect(() => { vvSession.installPath = vvInstallPath }, [vvInstallPath])
  useEffect(() => { vvSession.setupProgress = vvSetupProgress }, [vvSetupProgress])
  useEffect(() => { vvSession.buildType = vvBuildType }, [vvBuildType])

  // Check installed status on mount and when connection establishes
  useEffect(() => {
    if (!connected) return
    sendMessage({ type: 'get_features_status' })
    // If we had an active install but navigated away, clear stale state
    // The features_status response will set correct results
    if (session.active) {
      console.log('[Features] Clearing stale active state:', session.active)
      setActive(null)
      session.active = null
      setQueue([])
      session.queue = []
    }
  }, [connected, sendMessage])

  // Check VOICEVOX install status on mount — also reset stale progress
  useEffect(() => {
    if (!connected) return
    // Clear stale extracting/downloading progress on re-mount
    // (backend will send fresh status via voicevox_setup_status)
    if (vvSetupProgress && !vvSetupProgress.stage) {
      setVvSetupProgress(null)
    }
    sendMessage({ type: 'voicevox_check_install' })
    // Timeout: if still null (checking) after 10s, assume not installed
    const timeout = setTimeout(() => {
      if (vvSession.installed === null) {
        console.log('[Features] VOICEVOX check timed out, assuming not installed')
        setVvInstalled(false)
      }
    }, 10000)
    return () => clearTimeout(timeout)
  }, [connected, sendMessage])

  // Handle VOICEVOX backend messages
  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'voicevox_setup_status') {
      const p = lastMessage.payload as { installed?: boolean; install_path?: string; engine_running?: boolean }
      setVvInstalled(p.installed ?? false)
      setVvEngineRunning(p.engine_running ?? false)
      if (p.install_path) setVvInstallPath(p.install_path)
      // Clear stale progress if backend says installed (navigated away during install)
      if (p.installed) setVvSetupProgress(null)
    } else if (lastMessage.type === 'voicevox_setup_progress') {
      const p = lastMessage.payload as { stage?: string; progress?: number; detail?: string }
      if (p.stage === 'complete') {
        setVvSetupProgress(null)
        setVvInstalled(true)
        sendMessage({ type: 'voicevox_check_install' })
      } else if (p.stage === 'error') {
        setVvSetupProgress(null)
      } else {
        // Map download (0-80%) + extract (80-100%) for continuous progress bar
        const raw = p.progress || 0
        const overall = p.stage === 'downloading' ? raw * 0.8
          : p.stage === 'extracting' ? 80 + raw * 0.2
          : raw
        setVvSetupProgress({
          stage: p.stage || '',
          progress: overall,
          detail: p.detail || '',
        })
      }
    } else if (lastMessage.type === 'voicevox_engine_status') {
      const p = lastMessage.payload as { running?: boolean }
      setVvEngineRunning(p.running ?? false)
    }
  }, [lastMessage, sendMessage])

  // React to featuresStatus from Zustand store (set by handleGlobalMessage)
  useEffect(() => {
    if (!featuresStatus?.features) return
    const newResults: Record<string, 'success' | 'error'> = {}
    // Sync results with backend truth — only mark 'success' if backend says installed
    for (const [fid, info] of Object.entries(featuresStatus.features)) {
      if (info.installed) {
        newResults[fid] = 'success'
      }
    }
    // Preserve any in-progress results (active installs)
    for (const [fid, res] of Object.entries(results)) {
      if (res === 'error' || (active === fid)) {
        newResults[fid] = res
      }
    }
    setResults(newResults)
    // Clear stale active state — if no recent progress, nothing is really installing
    const act = activeRef.current
    if (act) {
      const recentProgress = installProgress && (Date.now() - installProgress.timestamp < 30000)
      if (featuresStatus.features[act]?.installed || !recentProgress) {
        setActive(null)
        if (featuresStatus.features[act]?.installed) {
          setProgress(p => ({ ...p, [act]: 1 }))
        }
      }
    }
  }, [featuresStatus])

  // Sync refs and session
  useEffect(() => { activeRef.current = active; session.active = active }, [active])
  useEffect(() => { queueRef.current = queue; session.queue = queue }, [queue])
  useEffect(() => { session.progress = progress }, [progress])
  useEffect(() => { session.results = results }, [results])
  useEffect(() => { session.errorMsg = errorMsg }, [errorMsg])

  const startNext = useCallback((currentQueue: string[]) => {
    if (currentQueue.length === 0) return
    const next = currentQueue[0]
    setActive(next)
    setQueue(currentQueue.slice(1))
    setProgress(p => ({ ...p, [next]: 0.05 }))
    sendMessage({ type: 'install_feature', payload: { feature_id: next } })
  }, [sendMessage])

  // Handle install progress from store
  useEffect(() => {
    if (!installProgress) return
    const fid = activeRef.current
    if (fid) {
      const est = estimateProgress(installProgress.detail)
      setProgress(p => ({ ...p, [fid]: Math.max(p[fid] || 0, est) }))
    }
  }, [installProgress])

  // Handle install result from store
  useEffect(() => {
    if (!installResult) return
    const fid = activeRef.current
    console.log('[Features] Install result received:', JSON.stringify(installResult), 'active:', fid, 'queue:', queueRef.current)
    if (fid) {
      if (installResult.success) {
        setProgress(p => ({ ...p, [fid]: 1 }))
        setResults(r => ({ ...r, [fid]: 'success' }))
        if (installResult.restart_needed) {
          console.log('[Features] Restart needed after installing:', fid)
          setRestartNeeded(true)
        }
      } else {
        setProgress(p => ({ ...p, [fid]: 0 }))
        setResults(r => ({ ...r, [fid]: 'error' }))
        setErrorMsg(installResult.error || 'Installation failed')
      }
    }
    setActive(null)
    // Start next in queue, or restart if queue is done and restart was requested
    const pendingQueue = [...queueRef.current]
    console.log('[Features] Will start next from queue:', pendingQueue)
    if (pendingQueue.length > 0) {
      setTimeout(() => {
        console.log('[Features] Starting next feature from queue:', pendingQueue[0])
        startNext(pendingQueue)
      }, 300)
    }
  }, [installResult, startNext])

  // Auto-restart when queue empties and restart was requested (torch installed)
  useEffect(() => {
    if (restartNeeded && !active && queue.length === 0) {
      console.log('[Features] All installs done, triggering restart for GPU support')
      sendMessage({ type: 'restart_app' })
    }
  }, [restartNeeded, active, queue, sendMessage])

  // Handle uninstall result from store
  useEffect(() => {
    if (!uninstallResult) return
    console.log('[Features] Uninstall result received:', JSON.stringify(uninstallResult))
    const fid = uninstallResult.feature
    if (fid) {
      if (uninstallResult.success) {
        console.log('[Features] Uninstall success:', fid)
        setResults(r => { const copy = { ...r }; delete copy[fid]; return copy })
        setProgress(p => { const copy = { ...p }; delete copy[fid]; return copy })
        // Clear persisted settings for uninstalled features
        if (fid === 'rvc') {
          useSettingsStore.getState().updateRVC({ modelPath: null, indexPath: null, enabled: false, recentModels: [] })
        }
        // Uninstalling torch breaks RVC and STT — clear RVC model path
        if (fid === 'torch_cpu' || fid === 'torch_cuda') {
          useSettingsStore.getState().updateRVC({ modelPath: null, indexPath: null, enabled: false })
        }
        // Refresh features status so UI shows correct installed state
        sendMessage({ type: 'get_features_status' })
      } else {
        setErrorMsg(uninstallResult.error || 'Uninstall failed')
      }
    }
    setUninstalling(null)
    if (uninstallTimerRef.current) { clearTimeout(uninstallTimerRef.current); uninstallTimerRef.current = null }
  }, [uninstallResult, sendMessage])

  const install = (featureId: string) => {
    console.log('[Features] Install clicked', featureId)
    // Don't re-queue if already queued or active
    if (active === featureId || queue.includes(featureId)) return
    // Clear previous result and progress for this feature
    // For torch switching, also clear the other variant
    setResults(r => {
      const copy = { ...r }
      delete copy[featureId]
      if (featureId === 'torch_cpu') delete copy['torch_cuda']
      if (featureId === 'torch_cuda') delete copy['torch_cpu']
      return copy
    })
    setProgress(p => {
      const copy = { ...p }
      delete copy[featureId]
      if (featureId === 'torch_cpu') delete copy['torch_cuda']
      if (featureId === 'torch_cuda') delete copy['torch_cpu']
      return copy
    })

    if (!active) {
      // Nothing installing, start immediately
      setActive(featureId)
      setProgress(p => ({ ...p, [featureId]: 0.05 }))
      sendMessage({ type: 'install_feature', payload: { feature_id: featureId } })
    } else {
      // Queue it
      setQueue(q => [...q, featureId])
      setProgress(p => ({ ...p, [featureId]: 0 }))
    }
  }

  const [uninstalling, setUninstalling] = useState<string | null>(null)
  const uninstallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const uninstall = (featureId: string) => {
    console.log('[Features] Uninstall clicked:', featureId, 'currently uninstalling:', uninstalling, 'active:', active)
    if (uninstalling) {
      console.log('[Features] Uninstall BLOCKED — already uninstalling:', uninstalling)
      return
    }
    setUninstalling(featureId)
    // Clear stale uninstall result so new result triggers the effect
    useFeaturesStore.getState().setUninstallResult(null as any)
    console.log('[Features] Sending uninstall_feature:', featureId)
    sendMessage({ type: 'uninstall_feature', payload: { feature_id: featureId } })
    // Safety timeout — clear stuck state after 30s
    if (uninstallTimerRef.current) clearTimeout(uninstallTimerRef.current)
    uninstallTimerRef.current = setTimeout(() => {
      console.log('[Features] Uninstall safety timeout triggered for:', featureId)
      setUninstalling(null)
      sendMessage({ type: 'get_features_status' })
    }, 30000)
  }

  const installAll = () => {
    console.log('[Features] Install All clicked')
    // Queue all uninstalled features (skip torch — default to CPU)
    const toInstall: string[] = []
    for (const feature of FEATURES) {
      const fid = feature.id
      const effectiveId = feature.torchPick ? 'torch_cpu' : fid
      const result = results[fid] || (feature.torchPick ? (results['torch_cpu'] || results['torch_cuda']) : undefined)
      if (result !== 'success' && !queue.includes(effectiveId) && active !== effectiveId) {
        toInstall.push(effectiveId)
      }
    }
    if (toInstall.length === 0) return
    // Start first, queue rest
    if (!active) {
      const [first, ...rest] = toInstall
      setActive(first)
      setProgress(p => ({ ...p, [first]: 0.05 }))
      sendMessage({ type: 'install_feature', payload: { feature_id: first } })
      if (rest.length > 0) {
        setQueue(q => [...q, ...rest])
        for (const r of rest) setProgress(p => ({ ...p, [r]: 0 }))
      }
    } else {
      setQueue(q => [...q, ...toInstall])
      for (const r of toInstall) setProgress(p => ({ ...p, [r]: 0 }))
    }
  }

  const allInstalled = FEATURES.every(f => {
    const r = results[f.id] || (f.torchPick ? (results['torch_cpu'] || results['torch_cuda']) : undefined)
    return r === 'success'
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 2px' }}>
        <div style={{ fontSize: 12, opacity: 0.5 }}>
          Click to install optional features.
        </div>
        {!allInstalled && (
          <button
            onClick={installAll}
            disabled={!!active}
            style={{
              ...btnStyle,
              fontSize: 12,
              padding: '4px 14px',
              opacity: active ? 0.5 : 1,
            }}
          >
            Install All
          </button>
        )}
      </div>

      {errorMsg && (
        <div style={{
          padding: '10px 14px', background: '#3a1010', borderRadius: 8,
          border: '1px solid #663333', fontSize: 13, whiteSpace: 'pre-wrap',
        }}>
          {errorMsg}
          <button onClick={() => setErrorMsg(null)} style={{
            marginLeft: 10, background: 'none', border: 'none',
            color: '#999', cursor: 'pointer', fontSize: 13,
          }}>dismiss</button>
        </div>
      )}

      {FEATURES.map(feature => {
        const fid = feature.id
        const torchId = feature.torchPick ? (results['torch_cuda'] ? 'torch_cuda' : 'torch_cpu') : null
        const effectiveId = torchId || fid
        const isActive = active === effectiveId || (feature.torchPick && (active === 'torch_cpu' || active === 'torch_cuda'))
        const isQueued = queue.includes(effectiveId) || (feature.torchPick && (queue.includes('torch_cpu') || queue.includes('torch_cuda')))
        const result = results[fid] || (feature.torchPick ? (results['torch_cpu'] || results['torch_cuda']) : undefined)
        const prog = progress[effectiveId] || (feature.torchPick ? (progress['torch_cpu'] || progress['torch_cuda']) : 0) || 0
        const showBar = isActive || isQueued || (result === 'success' && prog > 0)

        return (
          <div key={fid} style={{
            position: 'relative',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 14px',
            background: '#1e1e2e',
            borderRadius: 8,
            border: `1px solid ${result === 'success' ? '#2a4a2a' : result === 'error' ? '#4a2a2a' : '#333'}`,
            overflow: 'hidden',
          }}>
            {/* Progress bar background */}
            {(showBar || result === 'success') && (
              <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0,
                width: `${(result === 'success' ? 1 : prog) * 100}%`,
                background: result === 'success'
                  ? 'rgba(40, 120, 60, 0.3)'
                  : 'rgba(40, 120, 60, 0.2)',
                transition: 'width 0.6s ease-out',
                borderRadius: 8,
              }} />
            )}
            {/* Shimmer animation when actively installing */}
            {isActive && (
              <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0, right: 0,
                background: 'linear-gradient(90deg, transparent 0%, rgba(80,180,100,0.08) 50%, transparent 100%)',
                animation: 'shimmer 2s ease-in-out infinite',
                borderRadius: 8,
              }} />
            )}

            <div style={{ flex: 1, minWidth: 0, position: 'relative', zIndex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{feature.name}</div>
              <div style={{
                fontSize: 12, opacity: 0.6, marginTop: 2,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {feature.description}
              </div>
            </div>
            <div style={{ marginLeft: 12, display: 'flex', gap: 6, flexShrink: 0, position: 'relative', zIndex: 1 }}>
              {result === 'success' ? (
                feature.torchPick ? (
                  // Allow switching torch variant even after install
                  <>
                    <span style={{ color: '#4a8', fontSize: 13, marginRight: 4 }}>
                      {results['torch_cuda'] ? 'CUDA' : 'CPU'}
                    </span>
                    <button
                      onClick={() => install(results['torch_cuda'] ? 'torch_cpu' : 'torch_cuda')}
                      disabled={!!active}
                      style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', opacity: active ? 0.3 : 0.7, cursor: active ? 'not-allowed' : 'pointer' }}>
                      Switch to {results['torch_cuda'] ? 'CPU' : 'CUDA'}
                    </button>
                    <button
                      onClick={() => { console.log('[Features] Uninstall X clicked for torch'); uninstall(results['torch_cuda'] ? 'torch_cuda' : 'torch_cpu') }}
                      disabled={!!uninstalling}
                      title="Uninstall"
                      style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', background: '#433', borderColor: '#644', color: uninstalling === (results['torch_cuda'] ? 'torch_cuda' : 'torch_cpu') ? '#aa8833' : '#c88' }}>
                      {uninstalling === (results['torch_cuda'] ? 'torch_cuda' : 'torch_cpu') ? '...' : '✕'}
                    </button>
                  </>
                ) : (
                  <>
                    <span style={{ color: '#4a8', fontSize: 13 }}>
                      {uninstalling === fid ? 'Removing...' : 'Installed'}
                    </span>
                    <button
                      onClick={() => { console.log('[Features] Uninstall X clicked for', fid); uninstall(fid) }}
                      disabled={!!uninstalling}
                      title="Uninstall"
                      style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', background: '#433', borderColor: '#644', color: uninstalling === fid ? '#aa8833' : '#c88' }}>
                      {uninstalling === fid ? '...' : '✕'}
                    </button>
                  </>
                )
              ) : result === 'error' ? (
                feature.torchPick ? (
                  <>
                    <button onClick={() => install('torch_cpu')} disabled={!!active}
                      style={{ ...btnStyle, borderColor: '#733' }}>Retry CPU</button>
                    <button onClick={() => install('torch_cuda')} disabled={!!active}
                      style={{ ...btnStyle, borderColor: '#733' }}>Retry CUDA</button>
                  </>
                ) : (
                  <button onClick={() => install(fid)}
                    disabled={!!active} style={{ ...btnStyle, borderColor: '#733' }}>Retry</button>
                )
              ) : isActive ? (
                <span style={{ color: '#aa8833', fontSize: 13 }}>Installing...</span>
              ) : isQueued ? (
                <span style={{ color: '#888', fontSize: 13 }}>Queued</span>
              ) : feature.torchPick ? (
                <>
                  <button onClick={() => install('torch_cpu')} disabled={!!active && !isActive}
                    style={!!active && !isActive ? btnDisabledStyle : btnStyle}>CPU</button>
                  <button onClick={() => install('torch_cuda')} disabled={!!active && !isActive}
                    style={!!active && !isActive ? btnDisabledStyle : btnStyle}>CUDA</button>
                </>
              ) : (
                <button onClick={() => install(fid)} disabled={!!active && !isActive}
                  style={!!active && !isActive ? btnDisabledStyle : btnStyle}>Install</button>
              )}
            </div>
          </div>
        )
      })}

      {/* External Engines separator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '12px 0 4px' }}>
        <div style={{ flex: 1, height: 1, background: '#444' }} />
        <span style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: 1 }}>External Engines</span>
        <div style={{ flex: 1, height: 1, background: '#444' }} />
      </div>

      {/* VOICEVOX Engine */}
      <div style={{
        position: 'relative',
        display: 'flex', flexDirection: 'column',
        padding: '10px 14px',
        background: '#1e1e2e',
        borderRadius: 8,
        border: `1px solid ${vvInstalled ? '#2a4a2a' : '#333'}`,
        overflow: 'hidden',
      }}>
        {/* Installed background fill */}
        {vvInstalled && (
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, width: '100%',
            background: 'rgba(40, 120, 60, 0.3)',
            borderRadius: 8,
          }} />
        )}
        {/* Download progress background fill */}
        {vvSetupProgress && vvSetupProgress.stage !== 'starting' && (
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${Math.min(vvSetupProgress.progress, 100)}%`,
            background: 'rgba(40, 120, 60, 0.2)',
            transition: 'width 0.6s ease-out',
            borderRadius: 8,
          }} />
        )}
        {/* Shimmer when downloading/extracting */}
        {vvSetupProgress && (
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, right: 0,
            background: 'linear-gradient(90deg, transparent 0%, rgba(80,180,100,0.08) 50%, transparent 100%)',
            animation: 'shimmer 2s ease-in-out infinite',
            borderRadius: 8,
          }} />
        )}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative', zIndex: 1 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>VOICEVOX Engine</div>
            <div style={{ fontSize: 12, opacity: 0.6, marginTop: 2 }}>
              Japanese text-to-speech engine (~1.75 GB)
            </div>
          </div>

          <div style={{ marginLeft: 12, display: 'flex', gap: 6, flexShrink: 0, alignItems: 'center', position: 'relative', zIndex: 1 }}>
            {vvInstalled === null ? (
              <span style={{ color: '#888', fontSize: 13 }}>Checking...</span>
            ) : vvSetupProgress ? (
              <span style={{ color: '#aa8833', fontSize: 13 }}>
                {vvSetupProgress.stage === 'downloading' ? 'Downloading...'
                  : vvSetupProgress.stage === 'starting' ? 'Starting...'
                  : 'Extracting...'}
              </span>
            ) : vvInstalled ? (
              <>
                <span style={{ color: '#4a8', fontSize: 13 }}>
                  {vvEngineRunning ? 'Running' : 'Installed'}
                </span>
                {!vvEngineRunning ? (
                  <button
                    onClick={() => { console.log('[Features] VOICEVOX Start Engine'); sendMessage({ type: 'voicevox_start_engine' }) }}
                    style={{ ...btnStyle, fontSize: 11, padding: '2px 8px' }}
                  >Start</button>
                ) : (
                  <button
                    onClick={() => { console.log('[Features] VOICEVOX Stop Engine'); sendMessage({ type: 'voicevox_stop_engine' }) }}
                    style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', opacity: 0.7 }}
                  >Stop</button>
                )}
                <button
                  onClick={() => {
                    console.log('[Features] VOICEVOX Uninstall')
                    sendMessage({ type: 'voicevox_stop_engine' })
                    sendMessage({ type: 'voicevox_uninstall_engine' })
                    setVvInstalled(false)
                    setVvEngineRunning(false)
                  }}
                  title="Uninstall"
                  style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', background: '#433', borderColor: '#644', color: '#c88' }}
                >✕</button>
              </>
            ) : (
              <>
                <select
                  value={vvBuildType}
                  onChange={(e) => {
                    const bt = e.target.value as 'directml' | 'cpu'
                    console.log('[Features] VOICEVOX Build Type changed', bt)
                    setVvBuildType(bt)
                    updateTTS({ voicevoxBuildType: bt })
                  }}
                  style={{
                    background: '#2a2a3a', border: '1px solid #444', borderRadius: 6,
                    color: '#ddd', fontSize: 12, padding: '3px 8px', cursor: 'pointer',
                  }}
                >
                  <option value="directml">DirectML / GPU</option>
                  <option value="cpu">CPU only</option>
                </select>
                <button
                  onClick={() => { console.log('[Features] VOICEVOX Install clicked', vvBuildType); sendMessage({
                    type: 'voicevox_download_engine',
                    payload: { build_type: vvBuildType }
                  }) }}
                  style={btnStyle}
                >Install</button>
              </>
            )}
          </div>
        </div>

        {/* Cancel button during download */}
        {vvSetupProgress && vvSetupProgress.stage !== 'starting' && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', position: 'relative', zIndex: 1, marginTop: 4 }}>
            <button
              onClick={() => { console.log('[Features] VOICEVOX Cancel Download'); sendMessage({ type: 'voicevox_cancel_download' }) }}
              style={{ ...btnStyle, fontSize: 11, padding: '1px 8px', background: '#433', borderColor: '#644', color: '#c88' }}
            >Cancel</button>
          </div>
        )}
      </div>

      {/* Shimmer keyframes */}
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
    </div>
  )
}

const btnBase: React.CSSProperties = {
  padding: '4px 12px',
  background: '#335',
  border: '1px solid #557',
  borderRadius: 6,
  color: '#ddd',
  cursor: 'pointer',
  fontSize: 13,
}

const btnStyle: React.CSSProperties = btnBase

const btnDisabledStyle: React.CSSProperties = {
  ...btnBase,
  opacity: 0.4,
  cursor: 'not-allowed',
  pointerEvents: 'none' as const,
}
