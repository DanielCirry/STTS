import { useNotificationStore } from '@/stores'
import { useBackend } from '@/hooks/useBackend'
import { AlertTriangle, RefreshCw, SkipForward, Settings } from 'lucide-react'

interface ModelErrorDialogProps {
  onNavigateToSettings: () => void
}

export function ModelErrorDialog({ onNavigateToSettings }: ModelErrorDialogProps) {
  const modelError = useNotificationStore((s) => s.modelError)
  const dismissModelError = useNotificationStore((s) => s.dismissModelError)
  const { loadModel } = useBackend()

  if (!modelError) return null

  const handleRetry = () => {
    loadModel(modelError.modelType, modelError.modelId)
    dismissModelError()
  }

  const handleSkip = () => {
    // Dismiss — app continues in degraded mode (STT disabled, everything else works)
    dismissModelError()
  }

  const handlePickDifferent = () => {
    dismissModelError()
    onNavigateToSettings()
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-background border border-border rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-full bg-red-900/50">
            <AlertTriangle className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold">Model Load Failed</h3>
            <p className="text-sm text-muted-foreground">
              {modelError.modelType.toUpperCase()} model: {modelError.modelId}
            </p>
          </div>
        </div>

        <p className="text-sm text-red-300 bg-red-950/50 border border-red-900/50 rounded-lg p-3 mb-5 break-words">
          {modelError.error}
        </p>

        <div className="flex flex-col gap-2">
          <button
            onClick={handleRetry}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-sm font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
          <button
            onClick={handleSkip}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors text-sm font-medium"
          >
            <SkipForward className="w-4 h-4" />
            Skip (continue without {modelError.modelType.toUpperCase()})
          </button>
          <button
            onClick={handlePickDifferent}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors text-sm font-medium"
          >
            <Settings className="w-4 h-4" />
            Pick Different Model
          </button>
        </div>
      </div>
    </div>
  )
}
