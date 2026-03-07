import { useState, useEffect, useRef, useCallback } from 'react'
import { useBackend } from '@/hooks/useBackend'
import { useFeaturesStore } from '@/stores/featuresStore'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FeatureInstallProgress, FeatureInstallResult, FeatureUninstallResult } from '@/stores/featuresStore'

const FEATURES = [
  { id: 'stt', name: 'Speech-to-Text (Whisper)', description: 'Local speech recognition (~300 MB)' },
  { id: 'torch_cpu', name: 'PyTorch', description: 'Required for Translation & RVC', torchPick: true },
  { id: 'translation', name: 'Translation (NLLB)', description: 'Offline translation for 200+ languages (~50 MB)' },
  { id: 'local_llm', name: 'Local LLM (llama.cpp)', description: 'Run AI models locally (~50 MB)' },
  { id: 'rvc', name: 'RVC Voice Conversion', description: 'Real-time voice conversion (~100 MB)' },
  { id: 'piper_tts', name: 'Piper TTS (Offline)', description: 'Offline text-to-speech engine (~150 MB)' },
]

// Estimate progress from pip output keywords
function estimateProgress(detail: string): number {
  if (!detail) return 0.05
  const d = detail.toLowerCase()
  if (d.includes('installing dependency') || d.includes('pytorch')) return 0.1
  if (d.includes('collecting')) return 0.2
  if (d.includes('downloading')) return 0.5
  if (d.includes('installing')) return 0.75
  if (d.includes('successfully')) return 1
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
  const activeRef = useRef(active)
  const queueRef = useRef(queue)
  const checkedRef = useRef(false)

  // VOICEVOX Engine state
  const [vvInstalled, setVvInstalled] = useState<boolean | null>(vvSession.installed)
  const [vvEngineRunning, setVvEngineRunning] = useState(vvSession.engineRunning)
  const [vvInstallPath, setVvInstallPath] = useState(vvSession.installPath)
  const [vvSetupProgress, setVvSetupProgress] = useState<{ stage: string; progress: number; detail: string } | null>(vvSession.setupProgress)
  const [vvBuildType, setVvBuildType] = useState<'directml' | 'cpu'>(vvSession.buildType)

  // Sync VOICEVOX session state
  useEffect(() => { vvSession.installed = vvInstalled }, [vvInstalled])
  useEffect(() => { vvSession.engineRunning = vvEngineRunning }, [vvEngineRunning])
  useEffect(() => { vvSession.installPath = vvInstallPath }, [vvInstallPath])
  useEffect(() => { vvSession.setupProgress = vvSetupProgress }, [vvSetupProgress])
  useEffect(() => { vvSession.buildType = vvBuildType }, [vvBuildType])

  // Check installed status on mount and when connection establishes
  useEffect(() => {
    if (!connected) return
    sendMessage({ type: 'get_features_status' })
    // If we had an active install but navigated away, re-check
    if (session.active) {
      const timer = setTimeout(() => {
        if (activeRef.current && !queueRef.current.length) {
          setActive(null)
          session.active = null
        }
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [connected, sendMessage])

  // Check VOICEVOX install status on mount
  useEffect(() => {
    if (!connected) return
    sendMessage({ type: 'voicevox_check_install' })
  }, [connected, sendMessage])

  // Handle VOICEVOX backend messages
  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'voicevox_setup_status') {
      const p = lastMessage.payload as { installed?: boolean; install_path?: string; engine_running?: boolean }
      setVvInstalled(p.installed ?? false)
      setVvEngineRunning(p.engine_running ?? false)
      if (p.install_path) setVvInstallPath(p.install_path)
    } else if (lastMessage.type === 'voicevox_setup_progress') {
      const p = lastMessage.payload as { stage?: string; progress?: number; detail?: string }
      if (p.stage === 'complete') {
        setVvSetupProgress(null)
        setVvInstalled(true)
        sendMessage({ type: 'voicevox_check_install' })
      } else if (p.stage === 'error') {
        setVvSetupProgress(null)
      } else {
        setVvSetupProgress({
          stage: p.stage || '',
          progress: p.progress || 0,
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
    const newResults: Record<string, 'success' | 'error'> = { ...results }
    for (const [fid, info] of Object.entries(featuresStatus.features)) {
      if (info.installed && !newResults[fid]) {
        newResults[fid] = 'success'
      }
    }
    setResults(newResults)
    // If the previously-active feature is now installed, clear active state
    const act = activeRef.current
    if (act && featuresStatus.features[act]?.installed) {
      setActive(null)
      setProgress(p => ({ ...p, [act]: 1 }))
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
    if (fid) {
      if (installResult.success) {
        setProgress(p => ({ ...p, [fid]: 1 }))
        setResults(r => ({ ...r, [fid]: 'success' }))
      } else {
        setProgress(p => ({ ...p, [fid]: 0 }))
        setResults(r => ({ ...r, [fid]: 'error' }))
        setErrorMsg(installResult.error || 'Installation failed')
      }
    }
    setActive(null)
    // Start next in queue
    setTimeout(() => {
      const q = queueRef.current
      if (q.length > 0) startNext(q)
    }, 300)
  }, [installResult, startNext])

  // Handle uninstall result from store
  useEffect(() => {
    if (!uninstallResult) return
    const fid = uninstallResult.feature
    if (fid) {
      if (uninstallResult.success) {
        setResults(r => { const copy = { ...r }; delete copy[fid]; return copy })
        setProgress(p => { const copy = { ...p }; delete copy[fid]; return copy })
      } else {
        setErrorMsg(uninstallResult.error || 'Uninstall failed')
      }
    }
    setActive(null)
  }, [uninstallResult])

  const install = (featureId: string) => {
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

  const uninstall = (featureId: string) => {
    if (active) return
    setActive(featureId)
    sendMessage({ type: 'uninstall_feature', payload: { feature_id: featureId } })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16 }}>
      <div style={{ fontSize: 12, opacity: 0.5, padding: '0 2px' }}>
        Click to install optional features.
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
                      style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', opacity: 0.7 }}>
                      Switch to {results['torch_cuda'] ? 'CPU' : 'CUDA'}
                    </button>
                    <button
                      onClick={() => uninstall(results['torch_cuda'] ? 'torch_cuda' : 'torch_cpu')}
                      disabled={!!active}
                      title="Uninstall"
                      style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', background: '#433', borderColor: '#644', color: '#c88' }}>
                      ✕
                    </button>
                  </>
                ) : (
                  <>
                    <span style={{ color: '#4a8', fontSize: 13 }}>Installed</span>
                    <button
                      onClick={() => uninstall(fid)}
                      disabled={!!active}
                      title="Uninstall"
                      style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', background: '#433', borderColor: '#644', color: '#c88' }}>
                      ✕
                    </button>
                  </>
                )
              ) : result === 'error' ? (
                <button onClick={() => install(feature.torchPick ? 'torch_cpu' : fid)}
                  disabled={!!active} style={{ ...btnStyle, borderColor: '#733' }}>Retry</button>
              ) : isActive ? (
                <span style={{ color: '#aa8833', fontSize: 13 }}>Installing...</span>
              ) : isQueued ? (
                <span style={{ color: '#888', fontSize: 13 }}>Queued</span>
              ) : feature.torchPick ? (
                <>
                  <button onClick={() => install('torch_cpu')} disabled={!!active && !isActive}
                    style={btnStyle}>CPU</button>
                  <button onClick={() => install('torch_cuda')} disabled={!!active && !isActive}
                    style={btnStyle}>CUDA</button>
                </>
              ) : (
                <button onClick={() => install(fid)} disabled={!!active && !isActive}
                  style={btnStyle}>Install</button>
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
        display: 'flex', flexDirection: 'column', gap: 8,
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

          <div style={{ marginLeft: 12, display: 'flex', gap: 6, flexShrink: 0 }}>
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
                  Installed{vvEngineRunning ? ' & Running' : ''}
                </span>
              </>
            ) : (
              <span style={{ color: '#888', fontSize: 13 }}>Not installed</span>
            )}
          </div>
        </div>

        {/* Progress bar during download/extract */}
        {vvSetupProgress && vvSetupProgress.stage !== 'starting' && (
          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{
              width: '100%', height: 6, background: '#333', borderRadius: 3, overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', borderRadius: 3,
                background: '#4a8',
                width: `${Math.min(vvSetupProgress.progress, 100)}%`,
                transition: 'width 0.4s ease-out',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 11, opacity: 0.6 }}>{vvSetupProgress.detail}</span>
              <button
                onClick={() => sendMessage({ type: 'voicevox_cancel_download' })}
                style={{ ...btnStyle, fontSize: 11, padding: '1px 8px', background: '#433', borderColor: '#644', color: '#c88' }}
              >Cancel</button>
            </div>
          </div>
        )}

        {/* Starting spinner */}
        {vvSetupProgress && vvSetupProgress.stage === 'starting' && (
          <div style={{ position: 'relative', zIndex: 1, fontSize: 12, opacity: 0.6 }}>
            {vvSetupProgress.detail}
          </div>
        )}

        {/* Action buttons */}
        {!vvSetupProgress && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
            {vvInstalled === null ? null : vvInstalled ? (
              <>
                {!vvEngineRunning ? (
                  <button
                    onClick={() => sendMessage({ type: 'voicevox_start_engine' })}
                    style={btnStyle}
                  >Start Engine</button>
                ) : (
                  <button
                    onClick={() => sendMessage({ type: 'voicevox_stop_engine' })}
                    style={{ ...btnStyle, opacity: 0.7 }}
                  >Stop Engine</button>
                )}
                <button
                  onClick={() => {
                    if (confirm('Uninstall VOICEVOX Engine? You can reinstall later with a different build.')) {
                      sendMessage({ type: 'voicevox_stop_engine' })
                      sendMessage({ type: 'voicevox_uninstall_engine' })
                      setVvInstalled(false)
                      setVvEngineRunning(false)
                    }
                  }}
                  style={{ ...btnStyle, fontSize: 11, padding: '2px 8px', background: '#433', borderColor: '#644', color: '#c88' }}
                >Uninstall</button>
                {vvInstallPath && (
                  <span style={{ fontSize: 11, opacity: 0.4, alignSelf: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
                    {vvInstallPath}
                  </span>
                )}
              </>
            ) : (
              <>
                <select
                  value={vvBuildType}
                  onChange={(e) => {
                    const bt = e.target.value as 'directml' | 'cpu'
                    setVvBuildType(bt)
                    updateTTS({ voicevoxBuildType: bt })
                  }}
                  style={{
                    background: '#2a2a3a', border: '1px solid #444', borderRadius: 6,
                    color: '#ddd', fontSize: 12, padding: '3px 8px', cursor: 'pointer',
                  }}
                >
                  <option value="directml">DirectML / GPU (~1.75 GB)</option>
                  <option value="cpu">CPU only (~1.74 GB)</option>
                </select>
                <button
                  onClick={() => sendMessage({
                    type: 'voicevox_download_engine',
                    payload: { build_type: vvBuildType }
                  })}
                  style={btnStyle}
                >Install</button>
              </>
            )}
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

const btnStyle: React.CSSProperties = {
  padding: '4px 12px',
  background: '#335',
  border: '1px solid #557',
  borderRadius: 6,
  color: '#ddd',
  cursor: 'pointer',
  fontSize: 13,
}
