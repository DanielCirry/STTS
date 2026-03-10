import { useState, useEffect, useRef, useCallback } from 'react'
import { useBackend } from '@/hooks/useBackend'
import { useFeaturesStore } from '@/stores/featuresStore'

const INSTALL_ORDER = [
  { id: 'torch_cuda', label: 'PyTorch (GPU)', triggerRestart: true },
  { id: 'stt', label: 'Speech Recognition' },
  { id: 'translation', label: 'Translation' },
  { id: 'local_llm', label: 'Local AI' },
  { id: 'rvc', label: 'Voice Conversion' },
  { id: 'piper_tts', label: 'Text-to-Speech' },
  { id: 'ocr', label: 'OCR / VR Translation' },
  { id: 'voicevox', label: 'VOICEVOX Engine' },
]

function estimateProgress(detail: string): number {
  if (!detail) return 0.05
  const d = detail.toLowerCase()
  // Try to extract real percentage from pip output (e.g., "45%", "Downloading 67%")
  const pctMatch = detail.match(/(\d{1,3})%/)
  if (pctMatch) {
    const pct = parseInt(pctMatch[1]) / 100
    if (pct > 0 && pct <= 1) return pct
  }
  if (d.includes('collecting')) return 0.1
  if (d.includes('downloading')) return 0.3
  if (d.includes('installing') || d.includes('building')) return 0.6
  if (d.includes('verifying') || d.includes('satisfied')) return 0.85
  if (d.includes('successfully') || d.includes('complete') || d.includes('already installed')) return 1
  return 0.2
}

export default function FeaturesManager({ onComplete }: { onComplete?: () => void }) {
  const { sendMessage, connected, lastMessage } = useBackend()
  const featuresStatus = useFeaturesStore(s => s.status)
  const statusReceived = useFeaturesStore(s => s.statusReceived)
  const installProgress = useFeaturesStore(s => s.installProgress)
  const installResult = useFeaturesStore(s => s.installResult)
  const cachedResults = useFeaturesStore(s => s.cachedResults)

  const [currentFeature, setCurrentFeature] = useState<string | null>(null)
  const [currentProgress, setCurrentProgress] = useState(0)
  const [completedCount, setCompletedCount] = useState(0)
  const [queue, setQueue] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [allDone, setAllDone] = useState(false)
  const [restartPending, setRestartPending] = useState(false)

  const currentRef = useRef(currentFeature)
  const queueRef = useRef(queue)
  const startedRef = useRef(false)
  const completedRef = useRef(completedCount)

  useEffect(() => { currentRef.current = currentFeature }, [currentFeature])
  useEffect(() => { queueRef.current = queue }, [queue])
  useEffect(() => { completedRef.current = completedCount }, [completedCount])

  // Request feature status on mount — also clear stale cached results
  useEffect(() => {
    if (!connected) return
    console.log('[Setup] Connected, requesting features_status')
    // Clear restart state on reconnect (app has restarted, we're back)
    if (restartPending) {
      console.log('[Setup] Clearing restart state on reconnect')
      setRestartPending(false)
      startedRef.current = false
    }
    // Clear stale cached results from previous installs so we only trust backend status
    useFeaturesStore.setState({ cachedResults: {} })
    useFeaturesStore.getState().setStatusReceived(false)
    sendMessage({ type: 'get_features_status' })
    // Also check VOICEVOX status
    sendMessage({ type: 'voicevox_check_install' })
  }, [connected, sendMessage])

  // Check if all installed, or auto-start install
  useEffect(() => {
    if (!featuresStatus?.features || startedRef.current) return

    const voicevoxInstalled = useFeaturesStore.getState().voicevoxInstalled

    const missing: string[] = []
    let installed = 0
    for (const step of INSTALL_ORDER) {
      const fid = step.id
      if (fid === 'voicevox') {
        // VOICEVOX uses separate install mechanism
        if (voicevoxInstalled) {
          installed++
        } else {
          missing.push(fid)
        }
        continue
      }
      // torch_cuda / torch_cpu are interchangeable — ONLY trust backend status, not cachedResults
      const isInstalled = featuresStatus.features[fid]?.installed
        || (fid === 'torch_cuda' && featuresStatus.features['torch_cpu']?.installed)
      if (isInstalled) {
        installed++
      } else {
        missing.push(fid)
      }
    }

    console.log('[Setup] Status check: installed=%d, missing=%o', installed, missing)
    setCompletedCount(installed)

    if (missing.length === 0) {
      console.log('[Setup] All features already installed')
      setAllDone(true)
      return
    }

    // Resume pending queue from restart
    const pendingQueue = useFeaturesStore.getState().pendingInstallQueue
    if (pendingQueue.length > 0) {
      const remaining = pendingQueue.filter(fid => {
        if (fid === 'voicevox') return !voicevoxInstalled
        const inst = featuresStatus.features[fid]?.installed
          || (fid === 'torch_cpu' && featuresStatus.features['torch_cuda']?.installed)
          || (fid === 'torch_cuda' && featuresStatus.features['torch_cpu']?.installed)
        return !inst
      })
      useFeaturesStore.getState().clearPendingInstallQueue()
      if (remaining.length > 0) {
        console.log('[Setup] Resuming pending queue after restart:', remaining)
        startedRef.current = true
        const [first, ...rest] = remaining
        setCurrentFeature(first)
        setCurrentProgress(0.05)
        setQueue(rest)
        installFeature(first)
        return
      }
    }

    // Auto-start installing missing features
    console.log('[Setup] Auto-installing missing features:', missing)
    startedRef.current = true

    // If torch is needed, install only torch first (requires restart)
    const torchIdx = missing.findIndex(id => id === 'torch_cpu' || id === 'torch_cuda')
    if (torchIdx >= 0) {
      const torchId = missing[torchIdx]
      const remaining = missing.filter((_, i) => i !== torchIdx)
      console.log('[Setup] Torch needs restart — installing torch first, saving remaining:', remaining)
      useFeaturesStore.getState().setPendingInstallQueue(remaining)
      setCurrentFeature(torchId)
      setCurrentProgress(0.05)
      installFeature(torchId)
      return
    }

    // No torch needed — install all sequentially
    const [first, ...rest] = missing
    setCurrentFeature(first)
    setCurrentProgress(0.05)
    setQueue(rest)
    installFeature(first)
  }, [featuresStatus, connected, sendMessage])

  // Send the right install message depending on feature type
  function installFeature(fid: string) {
    if (fid === 'voicevox') {
      console.log('[Setup] Installing VOICEVOX engine (directml)')
      sendMessage({ type: 'voicevox_download_engine', payload: { build_type: 'directml' } })
    } else {
      console.log('[Setup] Installing feature:', fid)
      sendMessage({ type: 'install_feature', payload: { feature_id: fid } })
    }
  }

  // Track install progress (pip features)
  useEffect(() => {
    if (!installProgress || !currentRef.current) return
    if (currentRef.current === 'voicevox') return // VOICEVOX has its own progress
    const est = estimateProgress(installProgress.detail)
    setCurrentProgress(prev => Math.max(prev, est))
  }, [installProgress])

  // Track VOICEVOX install progress
  useEffect(() => {
    if (!lastMessage || currentRef.current !== 'voicevox') return
    if (lastMessage.type === 'voicevox_setup_progress') {
      const p = lastMessage.payload as { progress?: number; stage?: string; detail?: string }
      console.log('[Setup] VOICEVOX progress:', p)
      if (p.progress !== undefined) {
        setCurrentProgress(Math.min(p.progress / 100, 0.99))
      }
      // Check if download complete (stage = 'complete' or 'ready')
      if (p.stage === 'complete' || p.stage === 'ready') {
        handleFeatureComplete('voicevox')
      }
    }
    if (lastMessage.type === 'voicevox_setup_status') {
      const p = lastMessage.payload as { installed?: boolean; error?: string }
      console.log('[Setup] VOICEVOX status:', p)
      if (p.installed) {
        handleFeatureComplete('voicevox')
      } else if (p.error) {
        setError(`Failed to install VOICEVOX: ${p.error}`)
      }
    }
  }, [lastMessage])

  function handleFeatureComplete(fid: string) {
    console.log('[Setup] Feature complete:', fid)
    setCompletedCount(c => c + 1)
    setCurrentProgress(1)
    useFeaturesStore.getState().updateCachedResult(fid, 'success')
    setCurrentFeature(null)
    const pending = [...queueRef.current]
    if (pending.length > 0) {
      setTimeout(() => startNext(pending), 300)
    } else {
      setAllDone(true)
    }
  }

  // Handle install result (pip features)
  const startNext = useCallback((nextQueue: string[]) => {
    if (nextQueue.length === 0) {
      setAllDone(true)
      return
    }
    const next = nextQueue[0]
    setCurrentFeature(next)
    setCurrentProgress(0.05)
    setQueue(nextQueue.slice(1))
    installFeature(next)
  }, [sendMessage])

  useEffect(() => {
    if (!installResult) return
    const fid = currentRef.current
    if (!fid || fid === 'voicevox') return // VOICEVOX handled separately
    console.log('[Setup] Install result:', JSON.stringify(installResult), 'active:', fid)

    if (installResult.success) {
      setCompletedCount(c => c + 1)
      setCurrentProgress(1)
      useFeaturesStore.getState().updateCachedResult(fid, 'success')

      if (installResult.restart_needed) {
        console.log('[Setup] Restart needed after torch install')
        setRestartPending(true)
        setCurrentFeature(null)
        sendMessage({ type: 'restart_app' })
        return
      }
    } else {
      setError(`Failed to install ${getLabel(fid)}: ${installResult.error || 'Unknown error'}`)
      useFeaturesStore.getState().updateCachedResult(fid, 'error')
    }

    setCurrentFeature(null)
    const pending = [...queueRef.current]
    if (pending.length > 0) {
      setTimeout(() => startNext(pending), 300)
    } else if (!error && installResult.success) {
      setAllDone(true)
    }
  }, [installResult, startNext])

  function getLabel(fid: string): string {
    return INSTALL_ORDER.find(s => s.id === fid)?.label || fid
  }

  // All done — auto-dismiss after 1.5s
  useEffect(() => {
    if (allDone && onComplete) {
      const timer = setTimeout(() => onComplete(), 1500)
      return () => clearTimeout(timer)
    }
  }, [allDone, onComplete])

  const total = INSTALL_ORDER.length
  const overallProgress = allDone ? 1 : (completedCount + currentProgress) / total

  // Check if feature is installed — only trust backend status for pip features
  function isFeatureInstalled(fid: string): boolean {
    if (fid === 'voicevox') {
      return useFeaturesStore.getState().voicevoxInstalled === true || cachedResults[fid] === 'success'
    }
    return !!(featuresStatus?.features?.[fid]?.installed
      || (fid === 'torch_cuda' && featuresStatus?.features?.['torch_cpu']?.installed)
      || cachedResults[fid] === 'success')
  }

  // Waiting for backend
  if (!statusReceived) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 16 }}>
        <div style={{ fontSize: 16, fontWeight: 500 }}>Checking installed features...</div>
        <div style={{ width: 200, height: 4, background: '#333', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ width: '30%', height: '100%', background: '#4a8', borderRadius: 4, animation: 'shimmer 1.5s ease-in-out infinite' }} />
        </div>
        <style>{`@keyframes shimmer { 0%,100% { opacity: 0.3 } 50% { opacity: 1 } }`}</style>
      </div>
    )
  }

  if (allDone) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 16 }}>
        <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'rgba(40,120,60,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 24, color: '#4a8' }}>&#10003;</span>
        </div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>All features installed</div>
        <div style={{ fontSize: 13, opacity: 0.5, textAlign: 'center' }}>
          Everything is set up and ready to use.
        </div>
      </div>
    )
  }

  // Restarting
  if (restartPending) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 16 }}>
        <div style={{ fontSize: 16, fontWeight: 500 }}>Restarting...</div>
        <div style={{ fontSize: 13, opacity: 0.5, textAlign: 'center' }}>
          Restarting to apply changes.<br />
          Remaining features will continue installing automatically.
        </div>
      </div>
    )
  }

  // Installing
  const currentLabel = currentFeature ? getLabel(currentFeature) : ''
  const statusText = error
    ? error
    : currentFeature
      ? `Installing ${currentLabel}... (${completedCount + 1} of ${total})`
      : `Preparing...`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', padding: 24, gap: 20 }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Setting up STTS</div>
        <div style={{ fontSize: 13, opacity: 0.5 }}>
          Installing required features. This may take a few minutes.
        </div>
      </div>

      {/* Single progress bar */}
      <div style={{ position: 'relative', width: '100%', height: 32, background: '#1e1e2e', borderRadius: 8, border: '1px solid #333', overflow: 'hidden' }}>
        {/* Green fill */}
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${Math.max(overallProgress * 100, 2)}%`,
          background: error ? 'rgba(180,60,60,0.4)' : 'rgba(40,120,60,0.4)',
          transition: 'width 0.6s ease-out',
          borderRadius: 8,
        }} />
        {/* Shimmer when active */}
        {currentFeature && !error && (
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, right: 0,
            background: 'linear-gradient(90deg, transparent 0%, rgba(80,180,100,0.1) 50%, transparent 100%)',
            animation: 'progressShimmer 2s ease-in-out infinite',
            borderRadius: 8,
          }} />
        )}
        {/* Percentage text */}
        <div style={{
          position: 'absolute', left: 0, top: 0, right: 0, bottom: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 500, color: '#ddd', zIndex: 1,
        }}>
          {Math.round(overallProgress * 100)}%
        </div>
      </div>

      {/* Status text */}
      <div style={{ textAlign: 'center', fontSize: 13, color: error ? '#e88' : '#aaa' }}>
        {statusText}
      </div>

      {/* Feature checklist */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '0 8px' }}>
        {INSTALL_ORDER.map((step) => {
          const fid = step.id
          const installed = isFeatureInstalled(fid)
          const isCurrent = currentFeature === fid
          const hasError = cachedResults[fid] === 'error'
          return (
            <div key={fid} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              fontSize: 13, padding: '3px 0',
              opacity: installed || isCurrent ? 1 : 0.4,
            }}>
              <span style={{ width: 16, textAlign: 'center', fontSize: 12 }}>
                {installed ? <span style={{ color: '#4a8' }}>&#10003;</span>
                  : hasError ? <span style={{ color: '#e66' }}>&#10007;</span>
                  : isCurrent ? <span style={{ color: '#aa8833' }}>&#9679;</span>
                  : <span style={{ color: '#555' }}>&#9675;</span>}
              </span>
              <span style={{ color: isCurrent ? '#ddd' : installed ? '#8a8' : '#777' }}>
                {step.label}
              </span>
              {isCurrent && (
                <span style={{ fontSize: 11, color: '#aa8833', marginLeft: 'auto' }}>
                  {Math.round(currentProgress * 100)}%
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Error retry */}
      {error && (
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <button
            onClick={() => {
              console.log('[Setup] Retry after error')
              setError(null)
              startedRef.current = false
              // Re-request status to re-evaluate what's missing
              useFeaturesStore.getState().setStatusReceived(false)
              sendMessage({ type: 'get_features_status' })
              sendMessage({ type: 'voicevox_check_install' })
            }}
            style={{
              padding: '6px 20px', background: '#335', border: '1px solid #557',
              borderRadius: 6, color: '#ddd', cursor: 'pointer', fontSize: 13,
            }}
          >
            Retry
          </button>
        </div>
      )}

      <style>{`
        @keyframes progressShimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
    </div>
  )
}
