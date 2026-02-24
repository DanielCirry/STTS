import { useState, useEffect, useCallback } from 'react'
import { ArrowLeft, Cpu, Volume2, Bot, Monitor, Headphones, Key, Languages, Check, Loader2, Play, Square, Wifi, WifiOff, ExternalLink, Mic, MicOff, RefreshCw, Activity, AlertCircle, Eye, EyeOff, RotateCcw, Move, Palette, Trash2, AudioLines } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Select } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { useSettingsStore, type ComputeDevice } from '@/stores'
import { useModelStore } from '@/stores/modelStore'
import { useBackend } from '@/hooks/useBackend'

type SettingsPage = 'main' | 'models' | 'translation' | 'tts' | 'ai' | 'voiceConversion' | 'overlay' | 'audio' | 'credentials'

interface SettingsViewProps {
  onBack: () => void
}

const settingsPages = [
  { id: 'models' as const, label: 'AI Models', icon: Cpu },
  { id: 'translation' as const, label: 'Translation', icon: Languages },
  { id: 'tts' as const, label: 'Text-to-Speech', icon: Volume2 },
  { id: 'ai' as const, label: 'AI Assistant', icon: Bot },
  { id: 'voiceConversion' as const, label: 'Voice Conversion', icon: AudioLines },
  { id: 'overlay' as const, label: 'VR Overlay', icon: Monitor },
  { id: 'audio' as const, label: 'Audio Devices', icon: Headphones },
  { id: 'credentials' as const, label: 'API Credentials', icon: Key },
]

// Common languages for the translation settings
const LANGUAGES = [
  { value: 'eng_Latn', label: 'English' },
  { value: 'jpn_Jpan', label: 'Japanese' },
  { value: 'zho_Hans', label: 'Chinese (Simplified)' },
  { value: 'zho_Hant', label: 'Chinese (Traditional)' },
  { value: 'kor_Hang', label: 'Korean' },
  { value: 'spa_Latn', label: 'Spanish' },
  { value: 'fra_Latn', label: 'French' },
  { value: 'deu_Latn', label: 'German' },
  { value: 'ita_Latn', label: 'Italian' },
  { value: 'por_Latn', label: 'Portuguese' },
  { value: 'rus_Cyrl', label: 'Russian' },
  { value: 'arb_Arab', label: 'Arabic' },
  { value: 'hin_Deva', label: 'Hindi' },
  { value: 'tha_Thai', label: 'Thai' },
  { value: 'vie_Latn', label: 'Vietnamese' },
  { value: 'ind_Latn', label: 'Indonesian' },
  { value: 'nld_Latn', label: 'Dutch' },
  { value: 'pol_Latn', label: 'Polish' },
  { value: 'tur_Latn', label: 'Turkish' },
  { value: 'ukr_Cyrl', label: 'Ukrainian' },
]

const TRANSLATION_MODELS = [
  { value: 'nllb-200-distilled-600M', label: 'NLLB 600M (1.2 GB) - Good' },
  { value: 'nllb-200-distilled-1.3B', label: 'NLLB 1.3B (2.6 GB) - Better' },
  { value: 'nllb-200-3.3B', label: 'NLLB 3.3B (6.6 GB) - Best' },
]

export function SettingsView({ onBack }: SettingsViewProps) {
  const [currentPage, setCurrentPage] = useState<SettingsPage>('main')

  const renderContent = () => {
    switch (currentPage) {
      case 'models':
        return <ModelsSettings />
      case 'translation':
        return <TranslationSettings />
      case 'tts':
        return <TTSSettings />
      case 'ai':
        return <AISettings />
      case 'voiceConversion':
        return <VoiceConversionSettings />
      case 'overlay':
        return <OverlaySettings />
      case 'audio':
        return <AudioSettings />
      case 'credentials':
        return <CredentialsSettings />
      default:
        return <MainSettingsPage onNavigate={setCurrentPage} />
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="h-10 flex items-center px-4 border-b border-border gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={currentPage === 'main' ? onBack : () => setCurrentPage('main')}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <span className="font-semibold">
          {currentPage === 'main'
            ? 'Settings'
            : settingsPages.find((p) => p.id === currentPage)?.label || 'Settings'}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">{renderContent()}</div>
    </div>
  )
}

function MainSettingsPage({ onNavigate }: { onNavigate: (page: SettingsPage) => void }) {
  const { sendMessage, lastMessage } = useBackend()
  const [clearingCache, setClearingCache] = useState(false)
  const [cacheCleared, setCacheCleared] = useState<{ files: number; bytes: number } | null>(null)

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'cache_cleared') {
      const payload = lastMessage.payload as { files_deleted?: number; bytes_freed?: number; error?: string }
      setClearingCache(false)
      if (!payload.error) {
        setCacheCleared({ files: payload.files_deleted ?? 0, bytes: payload.bytes_freed ?? 0 })
        setTimeout(() => setCacheCleared(null), 3000)
      }
    }
  }, [lastMessage])

  const handleClearCache = () => {
    setClearingCache(true)
    setCacheCleared(null)
    sendMessage({ type: 'clear_cache' })
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="p-4 space-y-6">
      <div className="grid grid-cols-2 gap-4">
        {settingsPages.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className="flex items-center gap-3 p-4 rounded-lg bg-secondary hover:bg-secondary/80 transition-colors text-left"
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* General — Cache Management */}
      <div className="border-t border-border pt-4 space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">General</h4>
        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <p className="text-sm font-medium">Clear Cache</p>
            <p className="text-xs text-muted-foreground">Remove cached VOICEVOX icons and other data</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleClearCache}
            disabled={clearingCache}
            className="gap-1.5"
          >
            {clearingCache ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Trash2 className="w-3.5 h-3.5" />
            )}
            Clear
          </Button>
        </div>
        {cacheCleared && (
          <p className="text-xs text-green-400 flex items-center gap-1">
            <Check className="w-3 h-3" /> Cleared {cacheCleared.files} files ({formatBytes(cacheCleared.bytes)})
          </p>
        )}
      </div>
    </div>
  )
}

const STT_MODELS = [
  { id: 'whisper-base', name: 'Base', size: '145 MB', description: 'Good balance of speed and accuracy' },
  { id: 'whisper-small', name: 'Small', size: '488 MB', description: 'Better accuracy, moderate speed' },
  { id: 'whisper-medium', name: 'Medium', size: '1.5 GB', description: 'High accuracy, slower on CPU' },
]

const TRANSLATION_MODEL_CARDS = [
  { id: 'nllb-200-distilled-600M', name: 'NLLB 600M', size: '1.2 GB', description: 'Good quality, fast' },
  { id: 'nllb-200-distilled-1.3B', name: 'NLLB 1.3B', size: '2.6 GB', description: 'Better quality, moderate speed' },
  { id: 'nllb-200-3.3B', name: 'NLLB 3.3B', size: '6.6 GB', description: 'Best quality, needs more memory' },
]

interface GpuInfo {
  available: boolean
  name: string | null
  vram_total_mb: number
  vram_used_mb: number
  vram_free_mb: number
}

function ModelCard({
  model,
  isCurrent,
  isLoading,
  isLoaded,
  downloadProgress,
  onClick,
}: {
  model: { id: string; name: string; size: string; description: string }
  isCurrent: boolean
  isLoading: boolean
  isLoaded: boolean
  downloadProgress?: number
  onClick: () => void
}) {
  const isDownloading = downloadProgress !== undefined && downloadProgress > 0 && downloadProgress < 100

  return (
    <button
      onClick={() => !isLoading && onClick()}
      disabled={isLoading}
      className={`w-full text-left p-3 rounded-lg border transition-all ${
        isCurrent
          ? isLoaded
            ? 'bg-primary/10 border-primary'
            : 'bg-primary/5 border-primary/50'
          : 'bg-secondary border-border hover:border-primary/30'
      } ${isLoading ? 'opacity-70' : ''}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm">{model.name}</p>
            <span className="text-xs text-muted-foreground">{model.size}</span>
            {isCurrent && isLoaded && (
              <span className="flex items-center gap-1 text-xs text-green-500">
                <Check className="w-3 h-3" /> Active
              </span>
            )}
            {isCurrent && isLoading && !isDownloading && (
              <span className="flex items-center gap-1 text-xs text-primary">
                <Loader2 className="w-3 h-3 animate-spin" /> Loading...
              </span>
            )}
            {isDownloading && (
              <span className="flex items-center gap-1 text-xs text-primary">
                <Loader2 className="w-3 h-3 animate-spin" /> Downloading {Math.round(downloadProgress || 0)}%
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{model.description}</p>
        </div>
      </div>
      {/* Download/loading progress bar */}
      {(isCurrent && isLoading) && (
        <div className="mt-2 h-1.5 bg-secondary rounded-full overflow-hidden">
          {isDownloading ? (
            <div
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${downloadProgress}%` }}
            />
          ) : (
            <div className="h-full bg-primary rounded-full animate-pulse" style={{ width: '100%' }} />
          )}
        </div>
      )}
    </button>
  )
}

function ModelsSettings() {
  const { stt, translation, updateSTT, updateTranslation } = useSettingsStore()
  const { loadModel, updateSettings, status, sendMessage, lastMessage } = useBackend()
  const modelStore = useModelStore()
  const [loadingModelId, setLoadingModelId] = useState<string | null>(null)
  const [loadingTranslationId, setLoadingTranslationId] = useState<string | null>(null)
  const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null)

  // Request GPU info on mount
  useEffect(() => {
    sendMessage({ type: 'get_gpu_info' })
  }, [sendMessage])

  // Handle GPU info response
  useEffect(() => {
    if (lastMessage?.type === 'gpu_info') {
      setGpuInfo(lastMessage.payload as unknown as GpuInfo)
    }
  }, [lastMessage])

  // Track model loading state from modelStore
  useEffect(() => {
    const sttModels = modelStore.models.filter(m => m.category === 'stt')
    const loading = sttModels.find(m => m.status === 'loading' || m.status === 'downloading')
    const loaded = sttModels.find(m => m.status === 'loaded')
    if (loading) {
      setLoadingModelId(loading.id)
    } else if (loaded) {
      setLoadingModelId(null)
    }

    const transModels = modelStore.models.filter(m => m.category === 'translation')
    const transLoading = transModels.find(m => m.status === 'loading' || m.status === 'downloading')
    const transLoaded = transModels.find(m => m.status === 'loaded')
    if (transLoading) {
      setLoadingTranslationId(transLoading.id)
    } else if (transLoaded) {
      setLoadingTranslationId(null)
    }
  }, [modelStore.models])

  const handleSelectSTTModel = (modelId: string) => {
    updateSTT({ model: modelId })
    setLoadingModelId(modelId)
    loadModel('stt', modelId)
  }

  const handleSelectTranslationModel = (modelId: string) => {
    updateTranslation({ model: modelId })
    setLoadingTranslationId(modelId)
    loadModel('translation', modelId)
  }

  const handleDeviceChange = (device: ComputeDevice) => {
    updateSTT({ device })
    updateSettings({ stt: { device } })
  }

  const getModelStatus = (modelId: string) => {
    const model = modelStore.models.find(m => m.id === modelId)
    return model?.status || 'not_installed'
  }

  const getDownloadProgress = (modelId: string) => {
    const model = modelStore.models.find(m => m.id === modelId)
    return model?.downloadProgress
  }

  // STT helpers
  const isCurrentSTT = (modelId: string) => stt.model === modelId
  const isSTTLoading = (modelId: string) => loadingModelId === modelId
  const isSTTLoaded = (modelId: string) => getModelStatus(modelId) === 'loaded'

  // Translation helpers
  const isCurrentTrans = (modelId: string) => translation.model === modelId
  const isTransLoading = (modelId: string) => loadingTranslationId === modelId
  const isTransLoaded = (modelId: string) => getModelStatus(modelId) === 'loaded'

  // GPU status from backend status
  const backendGpu = (status as unknown as Record<string, unknown>)?.gpu as GpuInfo | undefined
  const gpu = gpuInfo || backendGpu

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">AI Models</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Manage speech recognition and translation models. Larger models are more accurate but slower.
          Models download automatically on first use.
        </p>
      </div>

      {/* GPU Info Display */}
      {gpu && gpu.available && (
        <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-green-400">{gpu.name || 'GPU'}</span>
            </div>
            {gpu.vram_total_mb > 0 && (
              <span className="text-xs text-muted-foreground">
                {Math.round(gpu.vram_used_mb)}MB / {Math.round(gpu.vram_total_mb)}MB VRAM
              </span>
            )}
          </div>
          {gpu.vram_total_mb > 0 && (
            <div className="mt-2 h-1.5 bg-green-500/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${Math.min(100, (gpu.vram_used_mb / gpu.vram_total_mb) * 100)}%` }}
              />
            </div>
          )}
        </div>
      )}
      {gpu && !gpu.available && (
        <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/20 p-3">
          <p className="text-xs text-yellow-400">
            No NVIDIA GPU detected. Models will run on CPU (slower but works everywhere).
          </p>
        </div>
      )}

      {/* STT Model Selection */}
      <div className="space-y-2">
        <Label>Speech Recognition (Whisper)</Label>
        <div className="space-y-2">
          {STT_MODELS.map((model) => (
            <ModelCard
              key={model.id}
              model={model}
              isCurrent={isCurrentSTT(model.id)}
              isLoading={isSTTLoading(model.id)}
              isLoaded={isSTTLoaded(model.id)}
              downloadProgress={getDownloadProgress(model.id)}
              onClick={() => handleSelectSTTModel(model.id)}
            />
          ))}
        </div>
      </div>

      {/* Translation Model Selection */}
      <div className="space-y-2">
        <Label>Translation (NLLB)</Label>
        <div className="space-y-2">
          {TRANSLATION_MODEL_CARDS.map((model) => (
            <ModelCard
              key={model.id}
              model={model}
              isCurrent={isCurrentTrans(model.id)}
              isLoading={isTransLoading(model.id)}
              isLoaded={isTransLoaded(model.id)}
              downloadProgress={getDownloadProgress(model.id)}
              onClick={() => handleSelectTranslationModel(model.id)}
            />
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          NLLB (No Language Left Behind) supports 200+ languages. Larger models give better translations.
        </p>
      </div>

      {/* Device Selection */}
      <div className="space-y-2">
        <Label>Compute Device</Label>
        <div className="flex gap-2">
          {(['cpu', 'cuda'] as const).map((device) => (
            <button
              key={device}
              onClick={() => handleDeviceChange(device)}
              className={`flex-1 p-3 rounded-lg border text-center transition-colors ${
                stt.device === device
                  ? 'bg-primary/10 border-primary text-foreground'
                  : 'bg-secondary border-border text-muted-foreground hover:border-primary/30'
              }`}
            >
              <p className="font-medium text-sm">{device === 'cpu' ? 'CPU' : 'GPU (CUDA)'}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {device === 'cpu' ? 'Works on all devices' : 'Faster, requires NVIDIA GPU'}
              </p>
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          GPU acceleration requires an NVIDIA GPU with CUDA support. Falls back to CPU if unavailable.
        </p>
      </div>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">About Models</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li>Models download automatically on first use (~1-5 min)</li>
          <li>Larger models need more RAM/VRAM but give better accuracy</li>
          <li><strong>STT Base:</strong> Best for real-time, low latency</li>
          <li><strong>STT Medium:</strong> Best accuracy, needs GPU for real-time</li>
          <li><strong>NLLB 600M:</strong> Good quality, works well on CPU</li>
          <li><strong>NLLB 1.3B:</strong> Better translations, recommended with GPU</li>
        </ul>
      </div>
    </div>
  )
}

const TRANSLATION_PROVIDERS = [
  { value: 'free', label: 'Free (No API Key)' },
  { value: 'local', label: 'Local NLLB (Offline)' },
  { value: 'deepl', label: 'DeepL (Cloud)' },
  { value: 'google', label: 'Google Cloud Translation' },
]

function TranslationSettings() {
  const { translation, updateTranslation, updatePairLanguage } = useSettingsStore()
  const { loadModel, updateSettings } = useBackend()
  const modelStore = useModelStore()
  const [loadingModel, setLoadingModel] = useState(false)

  // Track translation model loading
  useEffect(() => {
    const translationModels = modelStore.models.filter(m => m.category === 'translation')
    const loading = translationModels.some(m => m.status === 'loading')
    const loaded = translationModels.some(m => m.status === 'loaded')
    if (loading) setLoadingModel(true)
    else if (loaded) setLoadingModel(false)
  }, [modelStore.models])

  const activePair = translation.languagePairs[translation.activePairIndex] || translation.languagePairs[0]
  const isCloud = translation.provider !== 'local'

  const handleToggleTranslation = (checked: boolean) => {
    updateTranslation({ enabled: checked })
    if (checked && !isCloud) {
      setLoadingModel(true)
      loadModel('translation', translation.model)
    }
  }

  const handleProviderChange = (value: string) => {
    updateTranslation({ provider: value as 'local' | 'free' | 'deepl' | 'google' })
    updateSettings({ translation: { provider: value } })
    // If switching to local and translation is enabled, load the model
    if (value === 'local' && translation.enabled) {
      setLoadingModel(true)
      loadModel('translation', translation.model)
    }
  }

  const handleModelChange = (value: string) => {
    updateTranslation({ model: value })
    if (translation.enabled && !isCloud) {
      setLoadingModel(true)
      loadModel('translation', value)
    }
  }

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Translation</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Translate your speech in real-time. Choose between local NLLB models or cloud services like DeepL and Google Cloud Translation.
        </p>
      </div>

      {/* Enable/Disable Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable Translation</Label>
          <p className="text-xs text-muted-foreground">
            Automatically translate transcribed text
          </p>
        </div>
        <Switch
          checked={translation.enabled}
          onCheckedChange={handleToggleTranslation}
        />
      </div>

      {/* Translation Provider */}
      <div className="space-y-2">
        <Label>Translation Provider</Label>
        <Select
          value={translation.provider}
          onValueChange={handleProviderChange}
          options={TRANSLATION_PROVIDERS}
          disabled={!translation.enabled}
        />
        <p className="text-xs text-muted-foreground">
          {translation.provider === 'free'
            ? 'Uses MyMemory and other free APIs. No API key required. Set optional email in API Credentials for higher limits.'
            : isCloud
            ? `Using ${translation.provider === 'deepl' ? 'DeepL' : 'Google Cloud'} API. Set your API key in API Credentials.`
            : 'Using local NLLB model. No internet required.'}
        </p>
      </div>

      {/* Model Selection - only for local provider */}
      {!isCloud && (
        <div className="space-y-2">
          <Label>Translation Model</Label>
          <Select
            value={translation.model}
            onValueChange={handleModelChange}
            options={TRANSLATION_MODELS}
            disabled={!translation.enabled || loadingModel}
          />
          {loadingModel && (
            <div className="flex items-center gap-2 text-xs text-primary">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Loading model... (first time may download ~1-3 GB)</span>
            </div>
          )}
          {!loadingModel && (
            <p className="text-xs text-muted-foreground">
              Larger models provide better quality but require more memory. Model will download on first use.
            </p>
          )}
        </div>
      )}

      {/* Source Language */}
      <div className="space-y-2">
        <Label>Source Language (Your Speech)</Label>
        <Select
          value={activePair?.sourceLanguage || 'eng_Latn'}
          onValueChange={(value) => {
            if (activePair) updatePairLanguage(activePair.id, 'sourceLanguage', value)
          }}
          options={LANGUAGES}
          disabled={!translation.enabled}
        />
      </div>

      {/* Target Language */}
      <div className="space-y-2">
        <Label>Target Language (Translation Output)</Label>
        <Select
          value={activePair?.targetLanguage || 'jpn_Jpan'}
          onValueChange={(value) => {
            if (activePair) updatePairLanguage(activePair.id, 'targetLanguage', value)
          }}
          options={LANGUAGES}
          disabled={!translation.enabled}
        />
      </div>

      {/* Quick Swap Button */}
      <Button
        variant="outline"
        onClick={() => {
          if (activePair) {
            updatePairLanguage(activePair.id, 'sourceLanguage', activePair.targetLanguage)
          }
        }}
        disabled={!translation.enabled}
        className="w-full"
      >
        Swap Languages
      </Button>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        {translation.provider === 'free' ? (
          <>
            <p className="font-medium mb-2">About Free Translation</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
              <li>Uses MyMemory, LibreTranslate, and other free APIs</li>
              <li>No API key required — works out of the box</li>
              <li>MyMemory: 5,000 chars/day free; 50,000/day with email</li>
              <li>Automatically falls back to next provider if one fails</li>
              <li>Set optional email in Settings &gt; API Credentials</li>
            </ul>
          </>
        ) : isCloud ? (
          <>
            <p className="font-medium mb-2">About Cloud Translation</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
              <li>Requires internet connection and API key</li>
              <li>Higher quality translations for common languages</li>
              <li>{translation.provider === 'deepl' ? 'DeepL offers 500K characters/month on free tier' : 'Google Cloud Translation is pay-per-use'}</li>
              <li>Set your API key in Settings &gt; API Credentials</li>
              <li>Falls back to local NLLB if cloud provider fails</li>
            </ul>
          </>
        ) : (
          <>
            <p className="font-medium mb-2">About NLLB Translation</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
              <li>Runs locally on your device - no internet required</li>
              <li>First use will download the selected model</li>
              <li>GPU acceleration available with CUDA</li>
              <li>Supports 200+ languages including rare languages</li>
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

interface TTSVoice {
  id: string
  name: string
  language: string
  gender?: string
  description?: string
  icon?: string | null  // base64-encoded PNG icon (VOICEVOX)
}

interface TTSOutputDevice {
  id: number
  name: string
  channels: number
  sample_rate: number
}

const TTS_ENGINES = [
  {
    id: 'piper' as const,
    name: 'Piper TTS',
    description: 'Fast, natural, fully offline',
    online: false,
    badge: 'Local',
  },
  {
    id: 'edge' as const,
    name: 'Edge TTS',
    description: 'Microsoft neural voices, requires internet',
    online: true,
    badge: 'Online',
  },
  {
    id: 'sapi' as const,
    name: 'Windows SAPI',
    description: 'Built-in Windows voices, no setup needed',
    online: false,
    badge: 'System',
  },
  {
    id: 'voicevox' as const,
    name: 'VOICEVOX',
    description: 'Japanese anime voices (requires VOICEVOX engine)',
    online: false,
    badge: 'External',
  },
]

function TTSSettings() {
  const { tts, updateTTS } = useSettingsStore()
  const { updateSettings, speak, stopSpeaking, getTTSVoices, getTTSOutputDevices, lastMessage, sendMessage } = useBackend()

  const [voices, setVoices] = useState<TTSVoice[]>([])
  const [outputDevices, setOutputDevices] = useState<TTSOutputDevice[]>([])
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [testText, setTestText] = useState('Hello, this is a test of the text to speech voice.')
  const [voicevoxUrl, setVoicevoxUrl] = useState(tts.voicevoxUrl || 'http://localhost:50021')
  const [voicevoxConnected, setVoicevoxConnected] = useState<boolean | null>(null)
  const [voicevoxTesting, setVoicevoxTesting] = useState(false)
  const [voicevoxFetchingVoices, setVoicevoxFetchingVoices] = useState(false)

  // Fetch voices when engine changes
  useEffect(() => {
    getTTSVoices(tts.engine)
    getTTSOutputDevices()
  }, [tts.engine, getTTSVoices, getTTSOutputDevices])

  // Auto-fetch VOICEVOX voices with icons when engine is selected
  const fetchVoicevoxVoices = useCallback(() => {
    setVoicevoxFetchingVoices(true)
    sendMessage({ type: 'fetch_voicevox_voices' })
  }, [sendMessage])

  useEffect(() => {
    if (tts.engine === 'voicevox' && tts.enabled) {
      fetchVoicevoxVoices()
    }
  }, [tts.engine, tts.enabled, fetchVoicevoxVoices])

  // Handle backend responses
  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'tts_voices') {
      setVoices((lastMessage.payload.voices as TTSVoice[]) || [])
    } else if (lastMessage.type === 'tts_output_devices') {
      setOutputDevices((lastMessage.payload.devices as TTSOutputDevice[]) || [])
    } else if (lastMessage.type === 'tts_started') {
      setIsSpeaking(true)
    } else if (lastMessage.type === 'tts_finished') {
      setIsSpeaking(false)
    } else if (lastMessage.type === 'voicevox_connection_result') {
      const result = lastMessage.payload as { connected?: boolean; voices?: TTSVoice[] }
      setVoicevoxConnected(result.connected ?? false)
      setVoicevoxTesting(false)
      if (result.connected && result.voices) {
        setVoices(result.voices)
        setVoicevoxFetchingVoices(false)
      }
    } else if (lastMessage.type === 'voicevox_voices') {
      const result = lastMessage.payload as { voices?: TTSVoice[] }
      if (result.voices && result.voices.length > 0) {
        setVoices(result.voices)
      }
      setVoicevoxFetchingVoices(false)
    }
  }, [lastMessage])

  const handleEngineChange = (engineId: string) => {
    updateTTS({ engine: engineId as typeof tts.engine })
    updateSettings({ tts: { engine: engineId } })
  }

  const handleVoiceChange = (voiceId: string) => {
    updateTTS({ voice: voiceId })
    updateSettings({ tts: { voice: voiceId } })
  }

  const handleSpeedChange = (speed: number) => {
    updateTTS({ speed })
    updateSettings({ tts: { speed } })
  }

  const handlePitchChange = (pitch: number) => {
    updateTTS({ pitch })
    updateSettings({ tts: { pitch } })
  }

  const handleVolumeChange = (volume: number) => {
    updateTTS({ volume })
    updateSettings({ tts: { volume } })
  }

  const handleTestVoice = () => {
    if (isSpeaking) {
      stopSpeaking()
    } else {
      speak(testText)
    }
  }

  // Build voice options grouped by language
  const voiceGroups = voices.reduce<Record<string, TTSVoice[]>>((groups, voice) => {
    const lang = voice.language || 'Unknown'
    if (!groups[lang]) groups[lang] = []
    groups[lang].push(voice)
    return groups
  }, {})

  const voiceSelectGroups = Object.entries(voiceGroups).map(([lang, langVoices]) => ({
    label: lang,
    options: langVoices.map(v => ({
      value: v.id,
      label: `${v.name}${v.gender ? ` (${v.gender})` : ''}`,
    })),
  }))

  // Flat voice options as fallback
  const voiceOptions = voices.map(v => ({
    value: v.id,
    label: `${v.name}${v.gender ? ` (${v.gender})` : ''} — ${v.language}`,
  }))

  const outputDeviceOptions = [
    { value: '', label: 'System Default' },
    ...outputDevices.map(d => ({ value: String(d.id), label: d.name })),
  ]

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Text-to-Speech</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Choose a TTS engine to read your translated text aloud. Different engines offer different voice quality, speed, and language support.
        </p>
      </div>

      {/* Enable / Disable Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable Text-to-Speech</Label>
          <p className="text-xs text-muted-foreground">Speak translated text and AI responses aloud</p>
        </div>
        <Switch
          checked={tts.enabled}
          onCheckedChange={(checked) => {
            updateTTS({ enabled: checked })
            updateSettings({ tts: { enabled: checked } })
          }}
        />
      </div>

      {/* Engine Selection Cards */}
      <div className="space-y-2">
        <Label>TTS Engine</Label>
        <div className="space-y-2">
          {TTS_ENGINES.map((engine) => {
            const isSelected = tts.engine === engine.id
            return (
              <button
                key={engine.id}
                onClick={() => handleEngineChange(engine.id)}
                disabled={!tts.enabled}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isSelected
                    ? 'bg-primary/10 border-primary'
                    : 'bg-secondary border-border hover:border-primary/30'
                } ${!tts.enabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{engine.name}</p>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        engine.online
                          ? 'bg-blue-500/10 text-blue-500'
                          : 'bg-green-500/10 text-green-500'
                      }`}>
                        {engine.badge}
                      </span>
                      {isSelected && (
                        <span className="flex items-center gap-1 text-xs text-green-500">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{engine.description}</p>
                  </div>
                  {engine.online ? (
                    <Wifi className="w-4 h-4 text-muted-foreground shrink-0" />
                  ) : (
                    <WifiOff className="w-4 h-4 text-muted-foreground shrink-0" />
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Engine-specific warning */}
      {tts.engine === 'edge' && tts.enabled && (
        <div className="rounded-lg bg-blue-500/10 border border-blue-500/20 p-3 text-sm">
          <div className="flex items-center gap-2 text-blue-400">
            <Wifi className="w-4 h-4 shrink-0" />
            <p>Edge TTS requires an internet connection. Voices may have slight latency.</p>
          </div>
        </div>
      )}
      {tts.engine === 'voicevox' && tts.enabled && (
        <div className="space-y-3 p-3 bg-secondary/30 rounded-lg">
          <p className="text-sm font-medium">VOICEVOX Engine Settings</p>

          {/* Engine URL */}
          <div className="space-y-2">
            <Label className="text-sm">Engine URL</Label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={voicevoxUrl}
                onChange={(e) => setVoicevoxUrl(e.target.value)}
                placeholder="http://localhost:50021"
                className="flex-1 bg-secondary/50 border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
              <Button
                variant="outline"
                size="sm"
                disabled={voicevoxTesting}
                onClick={() => {
                  setVoicevoxTesting(true)
                  setVoicevoxConnected(null)
                  updateTTS({ voicevoxUrl: voicevoxUrl })
                  sendMessage({ type: 'test_voicevox_connection', payload: { url: voicevoxUrl } })
                }}
              >
                {voicevoxTesting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Test'
                )}
              </Button>
            </div>
            {voicevoxConnected === true && (
              <p className="text-xs text-green-400 flex items-center gap-1">
                <Check className="w-3 h-3" /> Connected to VOICEVOX
              </p>
            )}
            {voicevoxConnected === false && (
              <p className="text-xs text-red-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Cannot connect. Make sure VOICEVOX is running.
              </p>
            )}
          </div>

          {/* English Phonetic Toggle */}
          <div className="flex items-center justify-between pt-2 border-t border-border/50">
            <div>
              <p className="text-sm">English Phonetic Mode</p>
              <p className="text-xs text-muted-foreground">
                Convert English text to katakana for Japanese pronunciation
              </p>
            </div>
            <Switch
              checked={tts.voicevoxEnglishPhonetic}
              onCheckedChange={(enabled) => {
                updateTTS({ voicevoxEnglishPhonetic: enabled })
                updateSettings({ tts: { voicevox_english_phonetic: enabled } })
              }}
            />
          </div>

          {/* Download Link */}
          <div className="pt-2 border-t border-border/50">
            <a
              href="https://voicevox.hiroshiba.jp/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <ExternalLink className="w-3 h-3" />
              Download VOICEVOX Engine
            </a>
          </div>
        </div>
      )}

      {/* Voice Selection */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Voice</Label>
          {tts.engine === 'voicevox' && voices.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchVoicevoxVoices}
              disabled={voicevoxFetchingVoices || !tts.enabled}
              className="h-6 px-2 text-xs gap-1"
            >
              <RefreshCw className={`w-3 h-3 ${voicevoxFetchingVoices ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          )}
        </div>

        {/* VOICEVOX Icon Grid Picker */}
        {tts.engine === 'voicevox' && voices.length > 0 && voices.some(v => v.icon) ? (
          <div className="space-y-2">
            <div className="grid grid-cols-4 gap-2 max-h-[320px] overflow-y-auto pr-1">
              {voices.map((voice) => {
                const isSelected = tts.voice === voice.id
                return (
                  <button
                    key={voice.id}
                    onClick={() => handleVoiceChange(voice.id)}
                    disabled={!tts.enabled}
                    className={`flex flex-col items-center gap-1 p-2 rounded-lg border transition-all ${
                      isSelected
                        ? 'bg-primary/15 border-primary ring-1 ring-primary/30'
                        : 'bg-secondary/50 border-border hover:border-primary/30 hover:bg-secondary'
                    } ${!tts.enabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    title={voice.name}
                  >
                    {voice.icon ? (
                      <img
                        src={`data:image/png;base64,${voice.icon}`}
                        alt={voice.name}
                        className="w-12 h-12 rounded-md object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-md bg-secondary flex items-center justify-center text-lg">
                        🎤
                      </div>
                    )}
                    <span className="text-[10px] leading-tight text-center line-clamp-2 w-full">
                      {voice.name}
                    </span>
                    {isSelected && (
                      <Check className="w-3 h-3 text-primary" />
                    )}
                  </button>
                )
              })}
            </div>
            <p className="text-xs text-muted-foreground">{voices.length} voices available</p>
          </div>
        ) : voices.length > 0 ? (
          /* Standard dropdown for non-VOICEVOX engines or when no icons available */
          <div>
            <Select
              value={tts.voice}
              onValueChange={handleVoiceChange}
              options={voiceOptions}
              groups={voiceSelectGroups.length > 1 ? voiceSelectGroups : undefined}
              disabled={!tts.enabled}
            />
            <p className="text-xs text-muted-foreground mt-1">{voices.length} voices available</p>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>{tts.engine === 'voicevox' ? 'Fetching VOICEVOX voices...' : 'Loading voices...'}</span>
          </div>
        )}
      </div>

      {/* Speed Slider */}
      <div className="space-y-2">
        <Label>Speed</Label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={tts.speed}
            onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
            className="flex-1"
            disabled={!tts.enabled}
          />
          <span className="text-sm w-12 text-right">{tts.speed.toFixed(1)}x</span>
        </div>
      </div>

      {/* Pitch Slider */}
      <div className="space-y-2">
        <Label>Pitch</Label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={tts.pitch}
            onChange={(e) => handlePitchChange(parseFloat(e.target.value))}
            className="flex-1"
            disabled={!tts.enabled}
          />
          <span className="text-sm w-12 text-right">
            {tts.pitch === 1.0 ? 'Normal' : tts.pitch < 1.0 ? 'Low' : 'High'}
          </span>
        </div>
      </div>

      {/* Volume Slider */}
      <div className="space-y-2">
        <Label>Volume</Label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={tts.volume}
            onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
            className="flex-1"
            disabled={!tts.enabled}
          />
          <span className="text-sm w-12 text-right">{Math.round(tts.volume * 100)}%</span>
        </div>
      </div>

      {/* Test Voice */}
      <div className="space-y-2">
        <Label>Test Voice</Label>
        <div className="flex gap-2">
          <input
            type="text"
            value={testText}
            onChange={(e) => setTestText(e.target.value)}
            placeholder="Type text to test..."
            className="flex-1 bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={!tts.enabled}
          />
          <Button
            size="sm"
            onClick={handleTestVoice}
            disabled={!tts.enabled || !testText.trim()}
            className="shrink-0 gap-1.5"
          >
            {isSpeaking ? (
              <>
                <Square className="w-3 h-3" /> Stop
              </>
            ) : (
              <>
                <Play className="w-3 h-3" /> Test
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Output Device */}
      <div className="space-y-2">
        <Label>Output Device</Label>
        <Select
          value={tts.voice ? '' : ''}
          onValueChange={(value) => {
            const deviceId = value ? parseInt(value) : null
            updateSettings({ tts: { output_device: deviceId } })
          }}
          options={outputDeviceOptions}
          disabled={!tts.enabled}
        />
        <p className="text-xs text-muted-foreground">
          Route TTS audio to a virtual cable, then set that as your VRChat/Discord microphone input.
        </p>
      </div>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">About TTS Engines</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li><strong>Piper:</strong> Fastest, runs locally, best for real-time use</li>
          <li><strong>Edge TTS:</strong> Best voice quality, 100+ voices, needs internet</li>
          <li><strong>SAPI:</strong> Uses built-in Windows voices, no download needed</li>
          <li><strong>VOICEVOX:</strong> High-quality Japanese anime voices, needs separate engine</li>
        </ul>
      </div>
    </div>
  )
}

const AI_PROVIDERS = [
  { value: 'local', label: 'Local LLM (No API key needed)' },
  { value: 'groq', label: 'Groq (Fast, Free tier available)' },
  { value: 'openai', label: 'OpenAI (GPT-4, GPT-3.5)' },
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'google', label: 'Google (Gemini)' },
]

const CLOUD_MODELS: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini (Fast, cheap)' },
    { value: 'gpt-4o', label: 'GPT-4o (Best quality)' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo (Fastest)' },
  ],
  anthropic: [
    { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4 (Best)' },
    { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku (Fast)' },
  ],
  google: [
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Fast)' },
    { value: 'gemini-2.0-pro', label: 'Gemini 2.0 Pro (Quality)' },
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  ],
  groq: [
    { value: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B (Fast)' },
    { value: 'llama-3.1-70b-versatile', label: 'Llama 3.1 70B (Quality)' },
    { value: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B' },
    { value: 'gemma2-9b-it', label: 'Gemma 2 9B' },
  ],
}

interface LocalModel {
  name: string
  path?: string
  size: string | number
  description?: string
  downloaded: boolean
  url?: string
  filename?: string
}

function AISettings() {
  const { ai, updateAI } = useSettingsStore()
  const { updateSettings, getLocalModels, loadLocalModel, lastMessage, setModelsDirectory, getModelsDirectory } = useBackend()
  const [localModels, setLocalModels] = useState<LocalModel[]>([])
  const [loadingModel, setLoadingModel] = useState<string | null>(null)
  const [loadedModel, setLoadedModel] = useState<string | null>(null)
  const [modelsDir, setModelsDir] = useState<string>('')
  const [customDir, setCustomDir] = useState<string>(ai.modelsDirectory || '')

  // Fetch local models and directory when provider changes to local
  useEffect(() => {
    if (ai.provider === 'local') {
      getLocalModels()
      getModelsDirectory()
    }
  }, [ai.provider, getLocalModels, getModelsDirectory])

  // Handle backend messages
  useEffect(() => {
    if (lastMessage?.type === 'local_models') {
      setLocalModels(lastMessage.payload.models as LocalModel[])
    } else if (lastMessage?.type === 'model_loaded') {
      const payload = lastMessage.payload as { type?: string; id?: string }
      if (payload.type === 'llm') {
        setLoadingModel(null)
        setLoadedModel(payload.id || null)
      }
    } else if (lastMessage?.type === 'model_error') {
      const payload = lastMessage.payload as { type?: string }
      if (payload.type === 'llm') {
        setLoadingModel(null)
      }
    } else if (lastMessage?.type === 'models_directory') {
      const payload = lastMessage.payload as { path?: string }
      setModelsDir(payload.path || '')
      if (!customDir) {
        setCustomDir(payload.path || '')
      }
    } else if (lastMessage?.type === 'models_directory_set') {
      const payload = lastMessage.payload as { success?: boolean; path?: string; models?: LocalModel[] }
      if (payload.success) {
        setModelsDir(payload.path || '')
        setLocalModels(payload.models || [])
        updateAI({ modelsDirectory: payload.path || '' })
      }
    }
  }, [lastMessage, customDir, updateAI])

  // Sync provider change to backend
  const handleProviderChange = (provider: typeof ai.provider) => {
    updateAI({ provider })
    updateSettings({ ai: { provider } })
  }

  const handleLoadModel = (model: LocalModel) => {
    if (!model.downloaded || !model.path) return
    setLoadingModel(model.name)
    loadLocalModel(model.path)
  }

  const handleSetModelsDirectory = () => {
    if (customDir.trim()) {
      setModelsDirectory(customDir.trim())
    }
  }

  const formatSize = (size: string | number) => {
    if (typeof size === 'string') return size
    const gb = size / (1024 * 1024 * 1024)
    return `${gb.toFixed(2)} GB`
  }

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">AI Assistant</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Configure your AI assistant. Say the keyword followed by your question to get a response.
        </p>
      </div>

      {/* Enable/Disable Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable AI Assistant</Label>
          <p className="text-xs text-muted-foreground">
            Respond to voice commands starting with the keyword
          </p>
        </div>
        <Switch
          checked={ai.enabled}
          onCheckedChange={(checked) => updateAI({ enabled: checked })}
        />
      </div>

      {/* Keyword */}
      <div className="space-y-2">
        <Label>Activation Keyword</Label>
        <input
          type="text"
          value={ai.keyword}
          onChange={(e) => updateAI({ keyword: e.target.value })}
          placeholder="Jarvis"
          className="w-full bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          disabled={!ai.enabled}
        />
        <p className="text-xs text-muted-foreground">
          Say this word before your question (e.g., &quot;{ai.keyword}, what&apos;s the weather?&quot;)
        </p>
      </div>

      {/* Provider Selection */}
      <div className="space-y-2">
        <Label>AI Provider</Label>
        <Select
          value={ai.provider}
          onValueChange={(value) => handleProviderChange(value as typeof ai.provider)}
          options={AI_PROVIDERS}
          disabled={!ai.enabled}
        />
        <p className="text-xs text-muted-foreground">
          {ai.provider === 'local'
            ? 'Uses a local model - no internet or API key required'
            : 'Requires an API key configured in Credentials settings'}
        </p>
      </div>

      {/* Local Model Selection - show when local provider selected (even if disabled, so users can set up first) */}
      {ai.provider === 'local' && (
        <div className="space-y-4">
          {/* Models Directory */}
          <div className="space-y-2">
            <Label>Models Directory</Label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customDir}
                onChange={(e) => setCustomDir(e.target.value)}
                placeholder={modelsDir || 'Enter path to models folder...'}
                className="flex-1 bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 font-mono text-xs"
              />
              <Button
                size="sm"
                onClick={handleSetModelsDirectory}
                disabled={!customDir.trim() || customDir.trim() === modelsDir}
              >
                Set
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Current: {modelsDir || 'Loading...'}
            </p>
          </div>

          {/* Local Models List */}
          <div className="space-y-2">
            <Label>Available Models</Label>
            {localModels.filter(m => m.downloaded).length === 0 ? (
              <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/30 p-4 text-sm">
                <p className="font-medium text-yellow-500 mb-2">No Models Found</p>
                <p className="text-muted-foreground text-xs mb-2">
                  Download a GGUF model file to your models directory:
                </p>
                <code className="text-xs bg-secondary px-2 py-1 rounded block mb-2">
                  {modelsDir || '%APPDATA%\\STTS\\models\\llm\\'}
                </code>
                <p className="text-muted-foreground text-xs">
                  Recommended models from Hugging Face:
                </p>
                <ul className="list-disc list-inside text-xs text-muted-foreground mt-1">
                  <li>Llama-3.2-1B-Instruct-Q4_K_M.gguf (~0.8GB)</li>
                  <li>Llama-3.2-3B-Instruct-Q4_K_M.gguf (~2GB)</li>
                  <li>Phi-3-mini-4k-instruct-q4.gguf (~2.3GB)</li>
                </ul>
              </div>
            ) : (
              <div className="space-y-2">
                {localModels.filter(m => m.downloaded).map((model) => (
                  <div
                    key={model.name}
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      loadedModel === model.path
                        ? 'bg-primary/10 border-primary'
                        : 'bg-secondary border-border'
                    }`}
                  >
                    <div>
                      <p className="font-medium text-sm">{model.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatSize(model.size)}
                        {model.description && ` - ${model.description}`}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant={loadedModel === model.path ? 'default' : 'outline'}
                      onClick={() => handleLoadModel(model)}
                      disabled={loadingModel !== null}
                    >
                      {loadingModel === model.name
                        ? 'Loading...'
                        : loadedModel === model.path
                        ? 'Loaded'
                        : 'Load'}
                    </Button>
                  </div>
                ))}

              {/* Show recommended models to download */}
              {localModels.filter(m => !m.downloaded).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs text-muted-foreground mb-2">Recommended models to download:</p>
                  {localModels.filter(m => !m.downloaded).map((model) => (
                    <div
                      key={model.name}
                      className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 border border-border/50 mb-2"
                    >
                      <div>
                        <p className="font-medium text-sm text-muted-foreground">{model.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {model.size} {model.description && `- ${model.description}`}
                        </p>
                      </div>
                      {model.url && (
                        <a
                          href={model.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline"
                        >
                          Download
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Cloud Model Selection - show when non-local provider is selected */}
      {ai.provider !== 'local' && CLOUD_MODELS[ai.provider] && (
        <div className="space-y-2">
          <Label>Cloud Model</Label>
          <Select
            value={ai.cloudModels?.[ai.provider] || CLOUD_MODELS[ai.provider][0].value}
            onValueChange={(value) => {
              updateAI({
                cloudModels: { ...ai.cloudModels, [ai.provider]: value },
              })
              updateSettings({ ai: { cloud_model: value, provider: ai.provider } })
            }}
            options={CLOUD_MODELS[ai.provider]}
            disabled={!ai.enabled}
          />
          <p className="text-xs text-muted-foreground">
            Select which model to use for {AI_PROVIDERS.find(p => p.value === ai.provider)?.label.split(' (')[0] || ai.provider}
          </p>
        </div>
      )}

      {/* GPU Layers - show when local provider is selected */}
      {ai.provider === 'local' && (
        <div className="space-y-2">
          <Label>GPU Layers (n_gpu_layers)</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={ai.gpuLayers}
              onChange={(e) => {
                const val = parseInt(e.target.value)
                updateAI({ gpuLayers: val })
                updateSettings({ ai: { gpu_layers: val } })
              }}
              className="flex-1"
              disabled={!ai.enabled}
            />
            <span className="text-sm w-12 text-right">{ai.gpuLayers}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {ai.gpuLayers === 0
              ? 'All layers on CPU (default, safe for any system)'
              : `Offload ${ai.gpuLayers} layers to GPU for faster inference. Requires CUDA GPU.`}
          </p>
        </div>
      )}

      {/* Speak Responses */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Speak Responses</Label>
          <p className="text-xs text-muted-foreground">
            Use TTS to speak AI responses aloud
          </p>
        </div>
        <Switch
          checked={ai.speakResponses}
          onCheckedChange={(checked) => updateAI({ speakResponses: checked })}
          disabled={!ai.enabled}
        />
      </div>

      {/* Max Response Length */}
      <div className="space-y-2">
        <Label>Max Response Length</Label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="50"
            max="500"
            step="10"
            value={ai.maxResponseLength}
            onChange={(e) => updateAI({ maxResponseLength: parseInt(e.target.value) })}
            className="flex-1"
            disabled={!ai.enabled}
          />
          <span className="text-sm w-16 text-right">{ai.maxResponseLength} chars</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Shorter responses are faster to speak
        </p>
      </div>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">About AI Providers</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li><strong>Local LLM:</strong> Runs on your device, slower but private</li>
          <li><strong>Groq:</strong> Very fast, generous free tier</li>
          <li><strong>OpenAI:</strong> GPT models, requires paid API key</li>
          <li><strong>Anthropic:</strong> Claude models, requires paid API key</li>
          <li><strong>Google:</strong> Gemini models, free tier available</li>
        </ul>
      </div>
    </div>
  )
}

function OverlaySettings() {
  const { vrOverlay, updateVROverlay } = useSettingsStore()
  const { updateSettings, status } = useBackend()

  const overlayStatus = status?.vrOverlay as {
    available?: boolean
    initialized?: boolean
    steamvr_installed?: boolean
    hmd_present?: boolean
  } | undefined

  const handleUpdate = (updates: Record<string, unknown>) => {
    updateVROverlay(updates)
    updateSettings({ vrOverlay: updates })
  }

  const handleResetDefaults = () => {
    const defaults = {
      distance: 1.5,
      verticalOffset: 0.2,
      horizontalOffset: 0,
      width: 0.4,
      height: 0.15,
      fontSize: 24,
      fontColor: '#FFFFFF',
      backgroundColor: '#000000',
      backgroundOpacity: 0.7,
      autoHideSeconds: 5,
      followHead: true,
    }
    updateVROverlay(defaults)
    updateSettings({ vrOverlay: defaults })
  }

  const steamVRInstalled = overlayStatus?.steamvr_installed ?? false
  const hmdPresent = overlayStatus?.hmd_present ?? false
  const isInitialized = overlayStatus?.initialized ?? false

  return (
    <div className="p-4 space-y-6">
      <h3 className="text-lg font-medium">VR Overlay</h3>

      {/* Status Banner */}
      {!steamVRInstalled ? (
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <p className="text-xs text-yellow-400">
            <strong>SteamVR not detected.</strong> Install SteamVR to use the VR overlay.
            The overlay will display subtitles and translations in your VR headset.
          </p>
        </div>
      ) : !hmdPresent ? (
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <p className="text-xs text-yellow-400">
            <strong>No VR headset detected.</strong> Connect and power on your headset, then start SteamVR.
          </p>
        </div>
      ) : isInitialized ? (
        <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
          <p className="text-xs text-green-400">
            <strong>VR Overlay Active</strong> — Overlay is running in SteamVR.
          </p>
        </div>
      ) : null}

      {/* Enable/Disable */}
      <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
        <div>
          <p className="text-sm font-medium">Enable VR Overlay</p>
          <p className="text-xs text-muted-foreground">
            Show text overlay in your VR headset
          </p>
        </div>
        <Switch
          checked={vrOverlay.enabled}
          onCheckedChange={(enabled) => handleUpdate({ enabled })}
        />
      </div>

      {/* What to Display */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Eye className="w-4 h-4" />
          Display Content
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between p-2 bg-secondary/20 rounded">
            <div className="flex items-center gap-2">
              <Mic className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm">Your speech (own text)</span>
            </div>
            <Switch
              checked={vrOverlay.showOwnText}
              onCheckedChange={(show) => handleUpdate({ showOwnText: show })}
            />
          </div>

          <div className="flex items-center justify-between p-2 bg-secondary/20 rounded">
            <div className="flex items-center gap-2">
              <Headphones className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm">Incoming speech (others)</span>
            </div>
            <Switch
              checked={vrOverlay.showIncomingText}
              onCheckedChange={(show) => handleUpdate({ showIncomingText: show })}
            />
          </div>

          <div className="flex items-center justify-between p-2 bg-secondary/20 rounded">
            <div className="flex items-center gap-2">
              <Bot className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm">AI responses</span>
            </div>
            <Switch
              checked={vrOverlay.showAIResponses}
              onCheckedChange={(show) => handleUpdate({ showAIResponses: show })}
            />
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Position */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Move className="w-4 h-4" />
          Position
        </div>

        {/* Distance */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Distance</Label>
            <span className="text-xs text-muted-foreground font-mono">{vrOverlay.distance.toFixed(1)}m</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="5.0"
            step="0.1"
            value={vrOverlay.distance}
            onChange={(e) => handleUpdate({ distance: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>0.5m (close)</span>
            <span>5.0m (far)</span>
          </div>
        </div>

        {/* Vertical Offset */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Vertical Offset</Label>
            <span className="text-xs text-muted-foreground font-mono">
              {vrOverlay.verticalOffset > 0 ? '+' : ''}{vrOverlay.verticalOffset.toFixed(2)}m
            </span>
          </div>
          <input
            type="range"
            min="-1.0"
            max="1.0"
            step="0.05"
            value={vrOverlay.verticalOffset}
            onChange={(e) => handleUpdate({ verticalOffset: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Below</span>
            <span>Above</span>
          </div>
        </div>

        {/* Horizontal Offset */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Horizontal Offset</Label>
            <span className="text-xs text-muted-foreground font-mono">
              {vrOverlay.horizontalOffset > 0 ? '+' : ''}{vrOverlay.horizontalOffset.toFixed(2)}m
            </span>
          </div>
          <input
            type="range"
            min="-1.0"
            max="1.0"
            step="0.05"
            value={vrOverlay.horizontalOffset}
            onChange={(e) => handleUpdate({ horizontalOffset: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Left</span>
            <span>Right</span>
          </div>
        </div>

        {/* Follow Head */}
        <div className="flex items-center justify-between p-2 bg-secondary/20 rounded">
          <div>
            <span className="text-sm">Follow Head</span>
            <p className="text-xs text-muted-foreground">
              Overlay follows your head movement (billboard mode)
            </p>
          </div>
          <Switch
            checked={vrOverlay.followHead}
            onCheckedChange={(follow) => handleUpdate({ followHead: follow })}
          />
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Size */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Monitor className="w-4 h-4" />
          Size
        </div>

        {/* Width */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Width</Label>
            <span className="text-xs text-muted-foreground font-mono">{vrOverlay.width.toFixed(2)}m</span>
          </div>
          <input
            type="range"
            min="0.1"
            max="1.5"
            step="0.05"
            value={vrOverlay.width}
            onChange={(e) => handleUpdate({ width: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
        </div>

        {/* Height */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Height</Label>
            <span className="text-xs text-muted-foreground font-mono">{vrOverlay.height.toFixed(2)}m</span>
          </div>
          <input
            type="range"
            min="0.05"
            max="0.5"
            step="0.01"
            value={vrOverlay.height}
            onChange={(e) => handleUpdate({ height: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Appearance */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Palette className="w-4 h-4" />
          Appearance
        </div>

        {/* Font Size */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Font Size</Label>
            <span className="text-xs text-muted-foreground font-mono">{vrOverlay.fontSize}px</span>
          </div>
          <input
            type="range"
            min="12"
            max="64"
            step="2"
            value={vrOverlay.fontSize}
            onChange={(e) => handleUpdate({ fontSize: parseInt(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Small</span>
            <span>Large</span>
          </div>
        </div>

        {/* Font Color */}
        <div className="flex items-center justify-between">
          <Label className="text-sm">Font Color</Label>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-mono">{vrOverlay.fontColor}</span>
            <input
              type="color"
              value={vrOverlay.fontColor}
              onChange={(e) => handleUpdate({ fontColor: e.target.value })}
              className="w-8 h-8 rounded cursor-pointer border border-border bg-transparent"
            />
          </div>
        </div>

        {/* Background Color */}
        <div className="flex items-center justify-between">
          <Label className="text-sm">Background Color</Label>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-mono">{vrOverlay.backgroundColor}</span>
            <input
              type="color"
              value={vrOverlay.backgroundColor}
              onChange={(e) => handleUpdate({ backgroundColor: e.target.value })}
              className="w-8 h-8 rounded cursor-pointer border border-border bg-transparent"
            />
          </div>
        </div>

        {/* Background Opacity */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Background Opacity</Label>
            <span className="text-xs text-muted-foreground font-mono">{Math.round(vrOverlay.backgroundOpacity * 100)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={vrOverlay.backgroundOpacity}
            onChange={(e) => handleUpdate({ backgroundOpacity: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Transparent</span>
            <span>Opaque</span>
          </div>
        </div>

        {/* Overlay Preview */}
        <div className="space-y-2">
          <Label className="text-sm">Preview</Label>
          <div
            className="rounded-lg p-4 text-center"
            style={{
              backgroundColor: `${vrOverlay.backgroundColor}${Math.round(vrOverlay.backgroundOpacity * 255).toString(16).padStart(2, '0')}`,
              color: vrOverlay.fontColor,
              fontSize: `${Math.min(vrOverlay.fontSize, 32)}px`,
            }}
          >
            Hello! This is a preview.
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Behavior */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <EyeOff className="w-4 h-4" />
          Behavior
        </div>

        {/* Auto-hide */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Auto-hide After</Label>
            <span className="text-xs text-muted-foreground font-mono">
              {vrOverlay.autoHideSeconds === 0 ? 'Never' : `${vrOverlay.autoHideSeconds}s`}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="30"
            step="1"
            value={vrOverlay.autoHideSeconds}
            onChange={(e) => handleUpdate({ autoHideSeconds: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Never</span>
            <span>30 seconds</span>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Reset to Defaults */}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={handleResetDefaults}>
          <RotateCcw className="w-4 h-4 mr-2" />
          Reset to Defaults
        </Button>
      </div>
    </div>
  )
}

interface AudioDevice {
  id: number
  name: string
  raw_name: string
  sample_rate: number
  channels: number
  is_default: boolean
  is_active: boolean
  is_hardware: boolean
  host_api: string
}

function AudioSettings() {
  const { audio, updateAudio } = useSettingsStore()
  const { audioLevel, testMicrophone, stopTestMicrophone, getAudioDevices, updateSettings, lastMessage } = useBackend()

  const [inputDevices, setInputDevices] = useState<AudioDevice[]>([])
  const [outputDevices, setOutputDevices] = useState<AudioDevice[]>([])
  const [isTesting, setIsTesting] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Fetch audio devices on mount
  useEffect(() => {
    getAudioDevices()
  }, [getAudioDevices])

  // Listen for audio device responses
  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'audio_devices') {
      const payload = lastMessage.payload as { inputs?: AudioDevice[]; outputs?: AudioDevice[] }
      setInputDevices(payload.inputs || [])
      setOutputDevices(payload.outputs || [])
      setIsRefreshing(false)
    }
  }, [lastMessage])

  const handleRefreshDevices = () => {
    setIsRefreshing(true)
    getAudioDevices()
    // Safety timeout
    setTimeout(() => setIsRefreshing(false), 3000)
  }

  const handleTestMicrophone = () => {
    if (isTesting) {
      stopTestMicrophone()
      setIsTesting(false)
    } else {
      const deviceId = audio.microphoneDeviceId ? parseInt(audio.microphoneDeviceId) : undefined
      testMicrophone(deviceId)
      setIsTesting(true)
    }
  }

  const handleMicChange = (value: string) => {
    updateAudio({ microphoneDeviceId: value || null })
    updateSettings({ audio: { microphoneDeviceId: value || null } })
  }

  const handleSpeakerCaptureDeviceChange = (value: string) => {
    updateAudio({ speakerCaptureDeviceId: value || null })
    updateSettings({ audio: { speakerCaptureDeviceId: value || null } })
  }

  const handleTTSOutputChange = (value: string) => {
    updateAudio({ ttsOutputDeviceId: value || null })
    updateSettings({ audio: { ttsOutputDeviceId: value || null } })
  }

  const handleNoiseSuppressionToggle = (enabled: boolean) => {
    updateAudio({ enableNoiseSuppression: enabled })
    updateSettings({ audio: { enableNoiseSuppression: enabled } })
  }

  const handleVADToggle = (enabled: boolean) => {
    updateAudio({ enableVAD: enabled })
    updateSettings({ audio: { vad_enabled: enabled } })
  }

  const handleVADSensitivity = (value: number) => {
    updateAudio({ vadSensitivity: value })
    updateSettings({ audio: { vad_sensitivity: value } })
  }

  // Build input device options
  const inputDeviceOptions = inputDevices.map(d => ({
    value: String(d.id),
    label: `${d.name}${d.is_default ? ' (Default)' : ''}`,
  }))

  // Build output device options
  const outputDeviceOptions = outputDevices.map(d => ({
    value: String(d.id),
    label: `${d.name}${d.is_default ? ' (Default)' : ''}`,
  }))

  // Calculate audio level bar width (0-100)
  const levelPercent = Math.min(100, Math.max(0, (audioLevel || 0) * 100))
  const levelColor = levelPercent > 80 ? 'bg-red-500' : levelPercent > 50 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className="p-4 space-y-6">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Audio Devices</h3>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefreshDevices}
          disabled={isRefreshing}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh Devices
        </Button>
      </div>

      {/* Microphone Input Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Mic className="w-4 h-4" />
          Microphone Input
        </div>

        {/* Microphone device selector */}
        <div className="space-y-2">
          <Label>Input Device</Label>
          <Select
            value={audio.microphoneDeviceId || ''}
            onValueChange={handleMicChange}
            options={[
              { value: '', label: 'System Default' },
              ...inputDeviceOptions,
            ]}
            placeholder="Select microphone..."
          />
          {inputDevices.length === 0 && (
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              No input devices found. Connect a microphone and click Refresh.
            </p>
          )}
        </div>

        {/* Audio Level Meter */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Input Level</Label>
            <span className="text-xs text-muted-foreground font-mono">
              {isTesting ? `${Math.round(levelPercent)}%` : 'Not testing'}
            </span>
          </div>
          <div className="h-3 bg-secondary rounded-full overflow-hidden">
            <div
              className={`h-full ${isTesting ? levelColor : 'bg-muted-foreground/20'} transition-all duration-75 rounded-full`}
              style={{ width: `${isTesting ? levelPercent : 0}%` }}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={isTesting ? 'destructive' : 'outline'}
              size="sm"
              onClick={handleTestMicrophone}
            >
              {isTesting ? (
                <>
                  <MicOff className="w-4 h-4 mr-2" />
                  Stop Test
                </>
              ) : (
                <>
                  <Activity className="w-4 h-4 mr-2" />
                  Test Microphone
                </>
              )}
            </Button>
            {isTesting && (
              <span className="text-xs text-muted-foreground animate-pulse">
                Speak into your microphone...
              </span>
            )}
          </div>
        </div>

        {/* Noise Suppression */}
        <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
          <div>
            <p className="text-sm font-medium">Noise Suppression</p>
            <p className="text-xs text-muted-foreground">
              Reduce background noise from your microphone
            </p>
          </div>
          <Switch
            checked={audio.enableNoiseSuppression}
            onCheckedChange={handleNoiseSuppressionToggle}
          />
        </div>

        {/* VAD Settings */}
        <div className="space-y-3 p-3 bg-secondary/30 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Voice Activity Detection (VAD)</p>
              <p className="text-xs text-muted-foreground">
                Automatically detect when you start and stop talking
              </p>
            </div>
            <Switch
              checked={audio.enableVAD}
              onCheckedChange={handleVADToggle}
            />
          </div>

          {audio.enableVAD && (
            <div className="space-y-2 pt-2 border-t border-border/50">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Sensitivity</Label>
                <span className="text-xs text-muted-foreground font-mono">
                  {audio.vadSensitivity < 0.33 ? 'Low' : audio.vadSensitivity < 0.66 ? 'Medium' : 'High'}
                  {' '}({Math.round(audio.vadSensitivity * 100)}%)
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={audio.vadSensitivity}
                onChange={(e) => handleVADSensitivity(parseFloat(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Less sensitive</span>
                <span>More sensitive</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Speaker Capture Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Headphones className="w-4 h-4" />
          Speaker Capture (Loopback)
        </div>

        <div className="space-y-2">
          <Label>Speaker Capture Device</Label>
          <Select
            value={audio.speakerCaptureDeviceId || ''}
            onValueChange={handleSpeakerCaptureDeviceChange}
            options={[
              { value: '', label: 'System Default' },
              ...outputDeviceOptions,
            ]}
            placeholder="Select speaker device..."
          />
          <p className="text-xs text-muted-foreground">
            Used to listen to other speakers (e.g., Discord/VRChat audio). Uses WASAPI loopback capture.
          </p>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* TTS Output Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Volume2 className="w-4 h-4" />
          TTS Audio Output
        </div>

        <div className="space-y-2">
          <Label>Output Device</Label>
          <Select
            value={audio.ttsOutputDeviceId || ''}
            onValueChange={handleTTSOutputChange}
            options={[
              { value: '', label: 'System Default' },
              ...outputDeviceOptions,
            ]}
            placeholder="Select output device..."
          />
          <p className="text-xs text-muted-foreground">
            Where TTS audio will be played. Use a virtual audio cable to route TTS to VRChat or Discord.
          </p>
        </div>
      </div>

      {/* Info Box */}
      <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
        <p className="text-xs text-blue-400">
          <strong>Tip:</strong> For VRChat, use a virtual audio cable (e.g., VB-CABLE) as the TTS output device,
          then set it as your microphone in VRChat. This lets your AI-generated speech play directly into the game.
        </p>
      </div>
    </div>
  )
}

function CredentialsSettings() {
  const [credentials, setCredentials] = useState({
    groq: '',
    openai: '',
    anthropic: '',
    google: '',
    deepl: '',
    googleTranslate: '',
    mymemoryEmail: '',
  })
  const [showKeys, setShowKeys] = useState({
    groq: false,
    openai: false,
    anthropic: false,
    google: false,
    deepl: false,
    googleTranslate: false,
  })
  const [saved, setSaved] = useState(false)

  const { updateSettings } = useBackend()

  // Load saved credentials from localStorage on mount
  useEffect(() => {
    const savedCreds = localStorage.getItem('stts_api_credentials')
    if (savedCreds) {
      try {
        const parsed = JSON.parse(savedCreds)
        setCredentials(prev => ({ ...prev, ...parsed }))
      } catch {
        // Ignore parse errors
      }
    }
  }, [])

  const handleSave = () => {
    localStorage.setItem('stts_api_credentials', JSON.stringify(credentials))
    // Send credentials to backend
    updateSettings({
      credentials: {
        groq_api_key: credentials.groq || null,
        openai_api_key: credentials.openai || null,
        anthropic_api_key: credentials.anthropic || null,
        google_api_key: credentials.google || null,
        deepl_api_key: credentials.deepl || null,
        google_translate_api_key: credentials.googleTranslate || null,
        mymemory_email: credentials.mymemoryEmail || null,
      }
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const aiProviders = [
    { key: 'groq' as const, name: 'Groq', url: 'https://console.groq.com/keys' },
    { key: 'openai' as const, name: 'OpenAI', url: 'https://platform.openai.com/api-keys' },
    { key: 'anthropic' as const, name: 'Anthropic', url: 'https://console.anthropic.com/settings/keys' },
    { key: 'google' as const, name: 'Google AI', url: 'https://aistudio.google.com/app/apikey' },
  ]

  const translationProviders = [
    { key: 'deepl' as const, name: 'DeepL', url: 'https://www.deepl.com/pro-api' },
    { key: 'googleTranslate' as const, name: 'Google Cloud Translation', url: 'https://console.cloud.google.com/apis/credentials' },
  ]

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">API Credentials</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Enter your API keys for cloud providers. Keys are stored locally and never sent anywhere except the respective API.
        </p>
      </div>

      {/* AI Provider Keys */}
      <div>
        <h4 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wider">AI Providers</h4>
        <div className="space-y-4">
          {aiProviders.map(({ key, name, url }) => (
            <div key={key} className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{name} API Key</Label>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  Get API Key
                </a>
              </div>
              <div className="flex gap-2">
                <input
                  type={showKeys[key] ? 'text' : 'password'}
                  value={credentials[key]}
                  onChange={(e) => setCredentials({ ...credentials, [key]: e.target.value })}
                  placeholder={`Enter your ${name} API key`}
                  className="flex-1 bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 font-mono"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowKeys({ ...showKeys, [key]: !showKeys[key] })}
                >
                  {showKeys[key] ? 'Hide' : 'Show'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Free Translation section */}
      <div>
        <h4 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wider">Free Translation</h4>
        <div className="space-y-2">
          <div>
            <label className="block text-sm font-medium mb-1">
              MyMemory Email (optional)
            </label>
            <p className="text-xs text-muted-foreground mb-1">
              Increases daily limit from 5,000 to 50,000 characters. No account required.
            </p>
            <input
              type="email"
              placeholder="your@email.com"
              value={credentials.mymemoryEmail}
              onChange={(e) => setCredentials({ ...credentials, mymemoryEmail: e.target.value })}
              className="w-full bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>
      </div>

      {/* Translation Provider Keys */}
      <div>
        <h4 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wider">Translation Providers</h4>
        <div className="space-y-4">
          {translationProviders.map(({ key, name, url }) => (
            <div key={key} className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{name} API Key</Label>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  Get API Key
                </a>
              </div>
              <div className="flex gap-2">
                <input
                  type={showKeys[key] ? 'text' : 'password'}
                  value={credentials[key]}
                  onChange={(e) => setCredentials({ ...credentials, [key]: e.target.value })}
                  placeholder={`Enter your ${name} API key`}
                  className="flex-1 bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 font-mono"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowKeys({ ...showKeys, [key]: !showKeys[key] })}
                >
                  {showKeys[key] ? 'Hide' : 'Show'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Button onClick={handleSave} className="w-full">
        {saved ? 'Saved!' : 'Save Credentials'}
      </Button>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">Security Note</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li>API keys are stored locally in your browser</li>
          <li>Keys are only sent to their respective APIs</li>
          <li>For maximum security, use environment variables instead</li>
          <li>You can also set keys via GROQ_API_KEY, OPENAI_API_KEY, DEEPL_API_KEY, etc.</li>
        </ul>
      </div>
    </div>
  )
}

const RESAMPLE_RATE_OPTIONS = [
  { value: '0', label: 'Disabled (No Resample)' },
  { value: '16000', label: '16000 Hz' },
  { value: '22050', label: '22050 Hz' },
  { value: '24000', label: '24000 Hz' },
  { value: '32000', label: '32000 Hz' },
  { value: '40000', label: '40000 Hz' },
  { value: '44100', label: '44100 Hz' },
  { value: '48000', label: '48000 Hz' },
]

function VoiceConversionSettings() {
  const settings = useSettingsStore()
  const { sendMessage, lastMessage } = useBackend()

  // Local state for runtime RVC data (not persisted)
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; path: string; index_path: string | null; size_mb: number }>>([])
  const [isModelLoaded, setIsModelLoaded] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState('')
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [memoryUsageMb, setMemoryUsageMb] = useState(0)
  const [modelName, setModelName] = useState<string | null>(null)

  // Request model list and status on mount
  useEffect(() => {
    sendMessage({ type: 'rvc_scan_models' })
    sendMessage({ type: 'rvc_get_status' })
  }, [sendMessage])

  // Handle backend messages for RVC
  useEffect(() => {
    if (!lastMessage) return
    switch (lastMessage.type) {
      case 'rvc_models_list': {
        const payload = lastMessage.payload as { models?: Array<{ name: string; path: string; model_path?: string; index_path: string | null; size_mb: number }> }
        if (payload.models) {
          setAvailableModels(payload.models.map(m => ({
            name: m.name,
            path: m.model_path || m.path,
            index_path: m.index_path || null,
            size_mb: m.size_mb,
          })))
        }
        break
      }
      case 'rvc_model_loaded': {
        const payload = lastMessage.payload as { model_path?: string; memory_mb?: number }
        setIsLoading(false)
        setIsModelLoaded(true)
        setLoadingProgress(100)
        setLoadingStage('')
        if (payload.memory_mb) setMemoryUsageMb(payload.memory_mb)
        // Extract model name from path
        if (payload.model_path) {
          const parts = payload.model_path.replace(/\\/g, '/').split('/')
          const filename = parts[parts.length - 1]
          setModelName(filename.replace(/\.pth$/i, ''))
        }
        break
      }
      case 'rvc_model_error': {
        setIsLoading(false)
        setLoadingStage('')
        setLoadingProgress(0)
        break
      }
      case 'rvc_loading': {
        const payload = lastMessage.payload as { stage?: string; progress?: number }
        setIsLoading(true)
        if (payload.stage) setLoadingStage(payload.stage)
        if (payload.progress !== undefined) setLoadingProgress(payload.progress)
        break
      }
      case 'rvc_unloaded': {
        setIsModelLoaded(false)
        setMemoryUsageMb(0)
        setModelName(null)
        settings.updateRVC({ modelPath: null, indexPath: null })
        break
      }
      case 'rvc_status': {
        const payload = lastMessage.payload as {
          enabled?: boolean; model_loaded?: boolean; model_name?: string; memory_mb?: number
        }
        if (payload.model_loaded !== undefined) setIsModelLoaded(payload.model_loaded)
        if (payload.model_name) setModelName(payload.model_name)
        if (payload.memory_mb) setMemoryUsageMb(payload.memory_mb)
        break
      }
    }
  }, [lastMessage, settings])

  const handleEnableToggle = (checked: boolean) => {
    settings.updateRVC({ enabled: checked })
    sendMessage({ type: 'rvc_enable', payload: { enabled: checked } })
    // Disabling RVC also unloads the model (per CONTEXT.md)
    if (!checked && isModelLoaded) {
      sendMessage({ type: 'rvc_unload' })
      setIsModelLoaded(false)
      setMemoryUsageMb(0)
      setModelName(null)
    }
  }

  const handleModelSelect = (value: string) => {
    if (value === '__browse__') {
      sendMessage({ type: 'rvc_browse_model' })
      return
    }
    const model = availableModels.find(m => m.path === value)
    if (model) {
      settings.updateRVC({ modelPath: model.path, indexPath: model.index_path })
      setIsLoading(true)
      setLoadingStage('Loading voice model...')
      setLoadingProgress(0)
      sendMessage({ type: 'rvc_load_model', payload: { model_path: model.path, index_path: model.index_path } })
    }
  }

  const handleUnloadModel = () => {
    sendMessage({ type: 'rvc_unload' })
    setIsModelLoaded(false)
    setMemoryUsageMb(0)
    setModelName(null)
    settings.updateRVC({ modelPath: null, indexPath: null })
  }

  const handleParamChange = (param: string, value: number) => {
    settings.updateRVC({ [param]: value } as Partial<typeof settings.rvc>)
    // Map camelCase to snake_case for backend
    const paramMap: Record<string, string> = {
      f0UpKey: 'f0_up_key',
      indexRate: 'index_rate',
      filterRadius: 'filter_radius',
      rmsMixRate: 'rms_mix_rate',
      protect: 'protect',
      resampleSr: 'resample_sr',
      volumeEnvelope: 'volume_envelope',
    }
    const backendParam = paramMap[param] || param
    sendMessage({ type: 'rvc_set_params', payload: { [backendParam]: value } })
  }

  const handleTestVoice = () => {
    sendMessage({ type: 'rvc_test_voice' })
  }

  const modelOptions = [
    ...availableModels.map(m => ({
      value: m.path,
      label: `${m.name} (${m.size_mb.toFixed(1)} MB)`,
    })),
    { value: '__browse__', label: 'Browse...' },
  ]

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Voice Conversion</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Apply RVC voice models to transform TTS output into a different voice. Load a .pth voice model and adjust conversion parameters.
        </p>
      </div>

      {/* Enable/Disable Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable Voice Conversion</Label>
          <p className="text-xs text-muted-foreground">
            Post-process TTS audio through the selected voice model
          </p>
        </div>
        <Switch
          checked={settings.rvc.enabled}
          onCheckedChange={handleEnableToggle}
        />
      </div>

      {/* Model Selector */}
      <div className="space-y-2">
        <Label>Voice Model</Label>
        {availableModels.length > 0 || isModelLoaded ? (
          <Select
            value={settings.rvc.modelPath || ''}
            onValueChange={handleModelSelect}
            options={modelOptions}
            placeholder="Select a voice model..."
          />
        ) : (
          <div>
            <Select
              value=""
              onValueChange={handleModelSelect}
              options={[{ value: '__browse__', label: 'Browse...' }]}
              placeholder="No models found"
            />
          </div>
        )}
        {/* Empty state message */}
        {!isModelLoaded && !isLoading && (
          <p className="text-sm text-muted-foreground">
            Select a voice model to enable voice conversion
          </p>
        )}
        {/* Loading state */}
        {isLoading && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-primary">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>{loadingStage || 'Loading model...'}</span>
            </div>
            {loadingProgress > 0 && loadingProgress < 100 && (
              <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${loadingProgress}%` }}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Memory Indicator + Unload — only when model loaded */}
      {isModelLoaded && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-green-400" />
            <span className="text-sm text-muted-foreground">
              RVC: {modelName || 'Model loaded'}{memoryUsageMb > 0 ? ` — ${memoryUsageMb} MB` : ''}
            </span>
          </div>
          <Button variant="ghost" size="sm" onClick={handleUnloadModel}>
            Unload Model
          </Button>
        </div>
      )}

      {/* Quality Control Sliders */}
      <div className={`space-y-4 ${!isModelLoaded ? 'opacity-50 pointer-events-none' : ''}`}>
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Quality Controls</h4>

        {/* Pitch Shift */}
        <div className="space-y-2">
          <Label>Pitch Shift: {settings.rvc.f0UpKey} semitones</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={-12}
              max={12}
              step={1}
              value={settings.rvc.f0UpKey}
              onChange={(e) => handleParamChange('f0UpKey', parseInt(e.target.value))}
              className="flex-1"
              disabled={!isModelLoaded}
            />
            <span className="text-sm w-12 text-right">{settings.rvc.f0UpKey > 0 ? '+' : ''}{settings.rvc.f0UpKey}</span>
          </div>
          <p className="text-xs text-muted-foreground">Shift pitch up or down. 0 = no change, +12 = one octave up.</p>
        </div>

        {/* Index Rate */}
        <div className="space-y-2">
          <Label>Index Rate: {settings.rvc.indexRate.toFixed(2)}</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={settings.rvc.indexRate}
              onChange={(e) => handleParamChange('indexRate', parseFloat(e.target.value))}
              className="flex-1"
              disabled={!isModelLoaded}
            />
            <span className="text-sm w-12 text-right">{settings.rvc.indexRate.toFixed(2)}</span>
          </div>
          <p className="text-xs text-muted-foreground">FAISS index influence on timbre. Higher = more timbre from the voice model.</p>
        </div>

        {/* Filter Radius */}
        <div className="space-y-2">
          <Label>Filter Radius: {settings.rvc.filterRadius}</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={7}
              step={1}
              value={settings.rvc.filterRadius}
              onChange={(e) => handleParamChange('filterRadius', parseInt(e.target.value))}
              className="flex-1"
              disabled={!isModelLoaded}
            />
            <span className="text-sm w-12 text-right">{settings.rvc.filterRadius}</span>
          </div>
          <p className="text-xs text-muted-foreground">Pitch smoothing. Higher values reduce pitch jitter.</p>
        </div>

        {/* Resample Rate */}
        <div className="space-y-2">
          <Label>Resample Rate</Label>
          <Select
            value={String(settings.rvc.resampleSr)}
            onValueChange={(value) => handleParamChange('resampleSr', parseInt(value))}
            options={RESAMPLE_RATE_OPTIONS}
            disabled={!isModelLoaded}
          />
          <p className="text-xs text-muted-foreground">Output audio resample rate. 0 = use model default.</p>
        </div>

        {/* Volume Envelope */}
        <div className="space-y-2">
          <Label>Volume Envelope: {settings.rvc.volumeEnvelope.toFixed(2)}</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={settings.rvc.volumeEnvelope}
              onChange={(e) => handleParamChange('volumeEnvelope', parseFloat(e.target.value))}
              className="flex-1"
              disabled={!isModelLoaded}
            />
            <span className="text-sm w-12 text-right">{settings.rvc.volumeEnvelope.toFixed(2)}</span>
          </div>
          <p className="text-xs text-muted-foreground">Volume envelope mixing. 0 = use original envelope.</p>
        </div>

        {/* Protect Consonants */}
        <div className="space-y-2">
          <Label>Protect Consonants: {settings.rvc.protect.toFixed(2)}</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={0.5}
              step={0.01}
              value={settings.rvc.protect}
              onChange={(e) => handleParamChange('protect', parseFloat(e.target.value))}
              className="flex-1"
              disabled={!isModelLoaded}
            />
            <span className="text-sm w-12 text-right">{settings.rvc.protect.toFixed(2)}</span>
          </div>
          <p className="text-xs text-muted-foreground">Protect voiceless consonants from artifacts. Higher = more protection.</p>
        </div>

        {/* RMS Mix Rate */}
        <div className="space-y-2">
          <Label>RMS Mix Rate: {settings.rvc.rmsMixRate.toFixed(2)}</Label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={settings.rvc.rmsMixRate}
              onChange={(e) => handleParamChange('rmsMixRate', parseFloat(e.target.value))}
              className="flex-1"
              disabled={!isModelLoaded}
            />
            <span className="text-sm w-12 text-right">{settings.rvc.rmsMixRate.toFixed(2)}</span>
          </div>
          <p className="text-xs text-muted-foreground">Loudness matching with original audio. Higher = closer to model loudness.</p>
        </div>
      </div>

      {/* Test Voice Button */}
      <div className="space-y-2">
        <Button
          disabled={!isModelLoaded}
          onClick={handleTestVoice}
          className="w-full gap-2"
        >
          <Mic className="w-4 h-4" />
          Test Voice (3s recording)
        </Button>
        <p className="text-xs text-muted-foreground">
          Records 3 seconds from your microphone, converts through the loaded voice model, and plays back.
        </p>
      </div>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">About Voice Conversion</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li>RVC (Retrieval-based Voice Conversion) transforms TTS audio into a selected voice</li>
          <li>Place .pth model files in the models/rvc/voices folder, or use Browse to select from anywhere</li>
          <li>.index files are optional but improve timbre accuracy when placed alongside the .pth file</li>
          <li>CPU processing adds 1-5 seconds of latency depending on audio length</li>
          <li>Disabling the toggle also unloads the model to free memory</li>
        </ul>
      </div>
    </div>
  )
}
