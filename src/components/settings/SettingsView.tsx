import { useState, useEffect, useCallback, useRef } from 'react'
import { ArrowLeft, Home, Cpu, Volume2, Bot, Monitor, Headphones, Key, Languages, Check, Loader2, Play, Square, Wifi, WifiOff, Mic, MicOff, RefreshCw, Activity, AlertCircle, Eye, RotateCcw, Move, Trash2, AudioLines, Download, FolderOpen, X, Plus, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Select } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { useSettingsStore, useChatStore, type ComputeDevice, type TTSEngine, type AIProvider, type OutputProfile } from '@/stores'
import { useModelStore } from '@/stores/modelStore'
import { useBackend } from '@/hooks/useBackend'
import FeaturesManager from './FeaturesManager'

type SettingsPage = 'main' | 'models' | 'translation' | 'tts' | 'ai' | 'voiceConversion' | 'overlay' | 'audio' | 'outputProfiles' | 'credentials' | 'features'

interface SettingsViewProps {
  onBack: () => void
  initialPage?: SettingsPage
}

const settingsPages = [
  { id: 'models' as const, label: 'AI Models', icon: Cpu },
  { id: 'translation' as const, label: 'Translation', icon: Languages },
  { id: 'tts' as const, label: 'Text-to-Speech', icon: Volume2 },
  { id: 'ai' as const, label: 'AI Assistant', icon: Bot },
  { id: 'voiceConversion' as const, label: 'Voice Conversion', icon: AudioLines },
  { id: 'overlay' as const, label: 'VR Overlay', icon: Monitor },
  { id: 'audio' as const, label: 'Audio Devices', icon: Headphones },
  { id: 'outputProfiles' as const, label: 'Output Routing', icon: Send },
  { id: 'credentials' as const, label: 'API Credentials', icon: Key },
  { id: 'features' as const, label: 'Install Features', icon: Download },
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

export function SettingsView({ onBack, initialPage }: SettingsViewProps) {
  const [currentPage, setCurrentPage] = useState<SettingsPage>(initialPage ?? 'main')
  const { sendMessage, lastMessage } = useBackend()

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
      case 'outputProfiles':
        return <OutputProfilesSettings />
      case 'credentials':
        return <CredentialsSettings />
      case 'features':
        return <FeaturesManager />
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
          title={currentPage === 'main' ? 'Back to chat' : 'Back to settings'}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        {currentPage !== 'main' && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onBack}
            title="Back to chat"
          >
            <Home className="w-4 h-4" />
          </Button>
        )}
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

const TTS_ENGINE_OPTIONS = [
  { value: 'piper', label: 'Piper' },
  { value: 'edge', label: 'Edge' },
  { value: 'sapi', label: 'SAPI' },
  { value: 'voicevox', label: 'VOICEVOX' },
]

const AI_PROVIDER_OPTIONS = [
  { value: 'local', label: 'Local LLM' },
  { value: 'groq', label: 'Groq' },
  { value: 'google', label: 'Gemini' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
]

const QUICK_LANG_OPTIONS = [
  { value: 'eng_Latn', label: 'English' },
  { value: 'jpn_Jpan', label: 'Japanese' },
  { value: 'zho_Hans', label: 'Chinese' },
  { value: 'kor_Hang', label: 'Korean' },
  { value: 'spa_Latn', label: 'Spanish' },
  { value: 'fra_Latn', label: 'French' },
  { value: 'deu_Latn', label: 'German' },
  { value: 'rus_Cyrl', label: 'Russian' },
]

/** Reusable CPU/GPU toggle chip */
function DeviceToggle({
  device,
  onChange,
}: {
  device: 'cpu' | 'cuda' | 'directml'
  onChange: (d: 'cpu' | 'cuda') => void
}) {
  const isGpu = device === 'cuda' || device === 'directml'
  return (
    <div className="flex items-center gap-0.5 bg-secondary/60 rounded p-0.5">
      <button
        onClick={() => onChange('cpu')}
        className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
          !isGpu
            ? 'bg-primary text-primary-foreground'
            : 'hover:bg-secondary/80 text-muted-foreground'
        }`}
      >
        CPU
      </button>
      <button
        onClick={() => onChange('cuda')}
        className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
          isGpu
            ? 'bg-primary text-primary-foreground'
            : 'hover:bg-secondary/80 text-muted-foreground'
        }`}
      >
        GPU
      </button>
    </div>
  )
}

function QuickSettingsSection({ onNavigate }: { onNavigate: (page: SettingsPage) => void }) {
  const settings = useSettingsStore()
  const { sendMessage, connected } = useBackend()
  const isRvcModelLoaded = useChatStore((s) => s.isRvcModelLoaded)
  const isMicRvcActive = useChatStore((s) => s.isMicRvcActive)
  const quickVoices = useChatStore((s) => s.ttsVoices)

  // Fetch voices when engine changes or connection comes up
  useEffect(() => {
    if (!connected) return
    useChatStore.getState().setTtsVoices([]) // Clear old voices immediately on engine change
    if (settings.tts.engine === 'voicevox') {
      sendMessage({ type: 'fetch_voicevox_voices' })
    } else {
      sendMessage({ type: 'get_tts_voices', payload: { engine: settings.tts.engine } })
    }
  }, [settings.tts.engine, connected, sendMessage])

  // Auto-select voice when voice list changes
  useEffect(() => {
    if (quickVoices.length === 0) return
    const currentVoice = settings.tts.voice
    const currentEngine = settings.tts.engine
    const voiceInList = quickVoices.some(v => v.id === currentVoice)
    if (!voiceInList) {
      const savedVoice = (settings.tts.voicePerEngine ?? {})[currentEngine]
      const newVoice = (savedVoice && quickVoices.some(v => v.id === savedVoice))
        ? savedVoice
        : quickVoices[0].id
      settings.updateTTS({ voice: newVoice })
      sendMessage({ type: 'update_settings', payload: { tts: { voice: newVoice } } })
    }
  }, [quickVoices]) // eslint-disable-line react-hooks/exhaustive-deps

  const activePair = settings.translation.languagePairs[settings.translation.activePairIndex]

  /** Global device change: sets ALL component devices at once */
  const setGlobalDevice = (d: 'cpu' | 'cuda') => {
    settings.updateSTT({ device: d })
    settings.updateTTS({ device: d })
    settings.updateTranslation({ device: d })
    settings.updateAI({ device: d })
    settings.updateRVC({ rvcDevice: d })
    sendMessage({ type: 'update_settings', payload: { stt: { device: d }, tts: { device: d }, translation: { device: d }, ai: { device: d } } })
    sendMessage({ type: 'rvc_set_device', payload: { device: d } })
  }

  // Global shows GPU only when ALL components are on GPU
  const allGpu = settings.stt.device === 'cuda' && settings.tts.device === 'cuda' &&
    settings.translation.device === 'cuda' && settings.ai.device === 'cuda' && settings.rvc.rvcDevice === 'cuda'
  const globalDevice = allGpu ? 'cuda' : 'cpu'

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Quick Settings</h4>

      {/* Row 1: Global Compute — sets all components at once */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">Compute</span>
        </div>
        <DeviceToggle device={globalDevice} onChange={setGlobalDevice} />
      </div>

      {/* Row 2: STT */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Mic className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">STT</span>
        </div>
        <DeviceToggle
          device={settings.stt.device}
          onChange={(d) => {
            settings.updateSTT({ device: d })
            sendMessage({ type: 'update_settings', payload: { stt: { device: d } } })
          }}
        />
      </div>

      {/* Row 3: TTS — device + on/off + engine + voice */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">TTS</span>
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.tts.device}
            onChange={(d) => {
              settings.updateTTS({ device: d })
              sendMessage({ type: 'update_settings', payload: { tts: { device: d } } })
            }}
          />
          <Switch
            checked={settings.tts.enabled}
            onCheckedChange={(checked) => {
              settings.updateTTS({ enabled: checked })
              sendMessage({ type: 'update_settings', payload: { tts: { enabled: checked } } })
            }}
            className="scale-75"
          />
          <select
            value={settings.tts.engine}
            onChange={(e) => {
              const engine = e.target.value as TTSEngine
              // Save current voice for the old engine before switching
              const voicePerEngine = { ...(settings.tts.voicePerEngine ?? {}), [settings.tts.engine]: settings.tts.voice }
              settings.updateTTS({ engine, voicePerEngine })
              sendMessage({ type: 'update_settings', payload: { tts: { engine } } })
            }}
            className="bg-secondary border border-border rounded px-2 py-1 text-xs w-24"
          >
            {TTS_ENGINE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 3b: TTS Voice — dropdown for quick selection */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/20 ml-4">
        <span className="text-xs text-muted-foreground">Voice</span>
        <select
          value={settings.tts.voice}
          onChange={(e) => {
            const voice = e.target.value
            const voicePerEngine = { ...(settings.tts.voicePerEngine ?? {}), [settings.tts.engine]: voice }
            settings.updateTTS({ voice, voicePerEngine })
            sendMessage({ type: 'update_settings', payload: { tts: { voice } } })
          }}
          disabled={quickVoices.length === 0}
          className="bg-secondary border border-border rounded px-2 py-1 text-xs max-w-[200px]"
        >
          {quickVoices.length === 0 ? (
            <option value={settings.tts.voice}>Loading voices...</option>
          ) : (
            quickVoices.map(v => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))
          )}
        </select>
      </div>

      {/* Row 4: Translation */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Languages className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">Translate</span>
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.translation.device}
            onChange={(d) => {
              settings.updateTranslation({ device: d })
              sendMessage({ type: 'update_settings', payload: { translation: { device: d } } })
            }}
          />
          <Switch
            checked={settings.translation.enabled}
            onCheckedChange={(checked) => {
              settings.updateTranslation({ enabled: checked })
              sendMessage({ type: 'update_settings', payload: { translation: { enabled: checked } } })
            }}
            className="scale-75"
          />
          {settings.translation.enabled && activePair && (
            <div className="flex items-center gap-1 text-xs">
              <select
                value={activePair.sourceLanguage}
                onChange={(e) => {
                  const pairs = [...settings.translation.languagePairs]
                  pairs[settings.translation.activePairIndex] = { ...pairs[settings.translation.activePairIndex], sourceLanguage: e.target.value }
                  settings.updateTranslation({ languagePairs: pairs })
                  sendMessage({ type: 'update_settings', payload: { translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: settings.translation.activePairIndex } } })
                }}
                className="bg-secondary border border-border rounded px-1.5 py-1 text-xs w-20"
              >
                {QUICK_LANG_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <span className="text-muted-foreground">→</span>
              <select
                value={activePair.targetLanguage}
                onChange={(e) => {
                  const pairs = [...settings.translation.languagePairs]
                  pairs[settings.translation.activePairIndex] = { ...pairs[settings.translation.activePairIndex], targetLanguage: e.target.value }
                  settings.updateTranslation({ languagePairs: pairs })
                  sendMessage({ type: 'update_settings', payload: { translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: settings.translation.activePairIndex } } })
                }}
                className="bg-secondary border border-border rounded px-1.5 py-1 text-xs w-20"
              >
                {QUICK_LANG_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Row 5: AI Assistant */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">AI</span>
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.ai.device}
            onChange={(d) => {
              settings.updateAI({ device: d })
              sendMessage({ type: 'update_settings', payload: { ai: { device: d } } })
            }}
          />
          <Switch
            checked={settings.ai.enabled}
            onCheckedChange={(checked) => {
              settings.updateAI({ enabled: checked })
              sendMessage({ type: 'update_settings', payload: { ai: { enabled: checked } } })
            }}
            className="scale-75"
          />
          <select
            value={settings.ai.provider}
            onChange={(e) => {
              const provider = e.target.value as AIProvider
              settings.updateAI({ provider })
              sendMessage({ type: 'update_settings', payload: { ai: { provider } } })
            }}
            className="bg-secondary border border-border rounded px-2 py-1 text-xs w-24"
          >
            {AI_PROVIDER_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 6: RVC — device + Mic/TTS buttons */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <AudioLines className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">RVC</span>
          {isRvcModelLoaded ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">loaded</span>
          ) : (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">no model</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.rvc.rvcDevice}
            onChange={(d) => {
              settings.updateRVC({ rvcDevice: d })
              sendMessage({ type: 'rvc_set_device', payload: { device: d } })
            }}
          />
          <button
            onClick={() => {
              if (!isRvcModelLoaded) { onNavigate('voiceConversion'); return }
              if (isMicRvcActive) {
                useChatStore.getState().setMicRvcActive(false)  // Optimistic update
                sendMessage({ type: 'rvc_mic_stop' })
              } else {
                useChatStore.getState().setMicRvcActive(true)   // Optimistic update
                sendMessage({ type: 'rvc_mic_start', payload: { output_device_id: settings.rvc.micRvcOutputDeviceId } })
              }
            }}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              isMicRvcActive
                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                : isRvcModelLoaded
                ? 'bg-secondary hover:bg-secondary/80 text-muted-foreground border border-border'
                : 'bg-secondary/50 text-muted-foreground/50 border border-border/50 cursor-default'
            }`}
            title={!isRvcModelLoaded ? 'Load a model first' : isMicRvcActive ? 'Stop mic RVC' : 'Start mic RVC'}
          >
            Mic
          </button>
          <button
            onClick={() => {
              if (!isRvcModelLoaded) { onNavigate('voiceConversion'); return }
              const newEnabled = !settings.rvc.enabled
              settings.updateRVC({ enabled: newEnabled })
              sendMessage({ type: 'rvc_enable', payload: { enabled: newEnabled } })
            }}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              settings.rvc.enabled && isRvcModelLoaded
                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                : isRvcModelLoaded
                ? 'bg-secondary hover:bg-secondary/80 text-muted-foreground border border-border'
                : 'bg-secondary/50 text-muted-foreground/50 border border-border/50 cursor-default'
            }`}
            title={!isRvcModelLoaded ? 'Load a model first' : settings.rvc.enabled ? 'Disable TTS RVC' : 'Enable TTS RVC'}
          >
            TTS
          </button>
        </div>
      </div>
    </div>
  )
}

function MainSettingsPage({ onNavigate }: { onNavigate: (page: SettingsPage) => void }) {
  const settings = useSettingsStore()
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
      {/* Quick Settings */}
      <QuickSettingsSection onNavigate={onNavigate} />

      {/* Separator */}
      <div className="border-t border-border" />

      {/* Full Settings Pages Grid */}
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

      {/* General */}
      <div className="border-t border-border pt-4 space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">General</h4>
        <div className="grid grid-cols-2 gap-3">
          {/* Clear Cache */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
            <div>
              <p className="text-sm font-medium">Clear Cache</p>
              <p className="text-xs text-muted-foreground">Remove cached data</p>
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

          {/* Menu Layout */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 gap-2">
            <p className="text-sm font-medium shrink-0">Menu</p>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  const order: Array<'right' | 'top' | 'left' | 'bottom'> = ['right', 'top', 'left', 'bottom']
                  const idx = order.indexOf(settings.menuPosition)
                  settings.setMenuPosition(order[(idx + 1) % order.length])
                }}
                className="text-xs font-medium px-2 py-1 rounded bg-secondary hover:bg-secondary/80 transition-colors"
              >
                {settings.menuPosition.charAt(0).toUpperCase() + settings.menuPosition.slice(1)}
              </button>
              <button
                onClick={() => settings.setMenuAlignment(settings.menuAlignment === 'center' ? 'start' : 'center')}
                className="text-xs font-medium px-2 py-1 rounded bg-secondary hover:bg-secondary/80 transition-colors"
              >
                {settings.menuAlignment === 'center' ? 'Center' : 'Start'}
              </button>
            </div>
          </div>
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
            if (activePair) {
              updatePairLanguage(activePair.id, 'sourceLanguage', value)
              const pairs = useSettingsStore.getState().translation.languagePairs
              updateSettings({ translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: translation.activePairIndex } })
            }
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
            if (activePair) {
              updatePairLanguage(activePair.id, 'targetLanguage', value)
              const pairs = useSettingsStore.getState().translation.languagePairs
              updateSettings({ translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: translation.activePairIndex } })
            }
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
            // Need to read updated state after the swap
            const pairs = useSettingsStore.getState().translation.languagePairs
            updateSettings({ translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: translation.activePairIndex } })
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
  const { connected, updateSettings, speak, stopSpeaking, getTTSVoices, getTTSOutputDevices, lastMessage, sendMessage } = useBackend()

  const [voices, setVoices] = useState<TTSVoice[]>([])
  const [outputDevices, setOutputDevices] = useState<TTSOutputDevice[]>([])
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [testText, setTestText] = useState('Hello, this is a test of the text to speech voice.')
  const [voicevoxUrl, setVoicevoxUrl] = useState(tts.voicevoxUrl || 'http://localhost:50021')
  const [voicevoxConnected, setVoicevoxConnected] = useState<boolean | null>(null)
  const [voicevoxTesting, setVoicevoxTesting] = useState(false)
  const [voicevoxFetchingVoices, setVoicevoxFetchingVoices] = useState(false)

  // VOICEVOX Engine setup state
  const [voicevoxInstalled, setVoicevoxInstalled] = useState<boolean | null>(null)
  const [voicevoxEngineRunning, setVoicevoxEngineRunning] = useState(false)
  const [voicevoxSetupProgress, setVoicevoxSetupProgress] = useState<{
    stage: string; progress: number; detail: string
  } | null>(null)
  const [voicevoxInstallPath, setVoicevoxInstallPath] = useState('')

  // Fetch voices when engine changes or WebSocket (re)connects
  useEffect(() => {
    if (!connected) return
    getTTSVoices(tts.engine)
    getTTSOutputDevices()
  }, [tts.engine, connected, getTTSVoices, getTTSOutputDevices])

  // Auto-fetch VOICEVOX voices with icons when engine is running
  const fetchVoicevoxVoices = useCallback(() => {
    setVoicevoxFetchingVoices(true)
    sendMessage({ type: 'fetch_voicevox_voices' })
  }, [sendMessage])

  // Only fetch voices after backend confirms engine is running
  // (voicevoxEngineRunning is set by voicevox_engine_status or voicevox_setup_status from backend)

  // Check VOICEVOX Engine install status when engine is selected
  useEffect(() => {
    if (tts.engine === 'voicevox' && connected) {
      sendMessage({ type: 'voicevox_check_install' })
    }
  }, [tts.engine, connected, sendMessage])

  // Auto-connect when managed engine starts running
  useEffect(() => {
    if (voicevoxEngineRunning && tts.engine === 'voicevox') {
      const localUrl = 'http://localhost:50021'
      setVoicevoxUrl(localUrl)
      updateTTS({ voicevoxUrl: localUrl })
      sendMessage({ type: 'test_voicevox_connection', payload: { url: localUrl } })
    }
  }, [voicevoxEngineRunning, tts.engine, sendMessage, updateTTS])

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
    } else if (lastMessage.type === 'voicevox_setup_status') {
      const p = lastMessage.payload as {
        installed?: boolean; install_path?: string; engine_running?: boolean
      }
      setVoicevoxInstalled(p.installed ?? false)
      const running = p.engine_running ?? false
      setVoicevoxEngineRunning(running)
      if (!running) setVoicevoxFetchingVoices(false)
      if (p.install_path) setVoicevoxInstallPath(p.install_path)
    } else if (lastMessage.type === 'voicevox_setup_progress') {
      const p = lastMessage.payload as { stage?: string; progress?: number; detail?: string }
      if (p.stage === 'complete') {
        setVoicevoxSetupProgress(null)
        setVoicevoxInstalled(true)
        sendMessage({ type: 'voicevox_check_install' })
      } else if (p.stage === 'error') {
        setVoicevoxSetupProgress(null)
      } else {
        setVoicevoxSetupProgress({
          stage: p.stage || '',
          progress: p.progress || 0,
          detail: p.detail || '',
        })
      }
    } else if (lastMessage.type === 'voicevox_engine_status') {
      const p = lastMessage.payload as { running?: boolean }
      const running = p.running ?? false
      setVoicevoxEngineRunning(running)
      if (running) {
        setVoicevoxConnected(true)
        fetchVoicevoxVoices()
      } else {
        setVoicevoxFetchingVoices(false)
      }
    }
  }, [lastMessage, sendMessage, fetchVoicevoxVoices])

  const handleEngineChange = (engineId: string) => {
    // Save current voice for the old engine before switching
    const voicePerEngine = { ...(tts.voicePerEngine ?? {}), [tts.engine]: tts.voice }
    updateTTS({ engine: engineId as typeof tts.engine, voicePerEngine })
    updateSettings({ tts: { engine: engineId } })
  }

  const handleVoiceChange = (voiceId: string) => {
    const voicePerEngine = { ...(tts.voicePerEngine ?? {}), [tts.engine]: voiceId }
    updateTTS({ voice: voiceId, voicePerEngine })
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

          {/* Engine status indicator */}
          <div className="pt-2 border-t border-border/50">
            <p className="text-xs text-muted-foreground">
              Install or manage the VOICEVOX engine from the <strong>Install Features</strong> page.
              {voicevoxEngineRunning && (
                <span className="text-green-400 ml-1">Engine is running.</span>
              )}
            </p>
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
        ) : tts.engine === 'voicevox' && !voicevoxEngineRunning ? (
          <div className="text-sm text-muted-foreground py-2">
            Start the VOICEVOX engine to load voices.
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
  const canvasRef = useRef<HTMLDivElement>(null)
  const [interaction, setInteraction] = useState<{
    type: 'drag' | 'resize'
    element: 'notification' | 'log'
    corner?: 'tl' | 'tr' | 'bl' | 'br'
    startMouseX: number
    startMouseY: number
    startX: number
    startY: number
    startW: number
    startH: number
  } | null>(null)

  const overlayStatus = status?.vrOverlay as {
    available?: boolean
    initialized?: boolean
    steamvr_installed?: boolean
    hmd_present?: boolean
  } | undefined

  const handleUpdate = useCallback((updates: Record<string, unknown>) => {
    updateVROverlay(updates)
    updateSettings({ vrOverlay: updates })
  }, [updateVROverlay, updateSettings])

  // Canvas coordinate system: 3.0m wide (-1.5 to 1.5), 2.0m tall (-1.0 to 1.0)
  const H_RANGE = 3.0
  const V_RANGE = 2.0
  const toCanvasX = (m: number) => ((m + H_RANGE / 2) / H_RANGE) * 100
  const toCanvasY = (m: number) => ((V_RANGE / 2 - m) / V_RANGE) * 100
  const toCanvasW = (m: number) => (m / H_RANGE) * 100
  const toCanvasH = (m: number) => (m / V_RANGE) * 100

  // Size limits (meters)
  const NOTIF_MAX_W = 1.2, NOTIF_MAX_H = 0.8, NOTIF_MIN_W = 0.1, NOTIF_MIN_H = 0.05
  const LOG_MAX_W = 1.8, LOG_MAX_H = 1.2, LOG_MIN_W = 0.2, LOG_MIN_H = 0.1

  // Snap zone: bottom 20% of canvas, left/right 30%
  const SNAP_Y_THRESHOLD = 0.7  // canvas % from top (bottom 30%)
  const SNAP_X_LEFT = 0.3       // left 30%
  const SNAP_X_RIGHT = 0.7      // right 30%

  const getSnapTracking = (canvasXPct: number, canvasYPct: number): 'none' | 'left_hand' | 'right_hand' => {
    if (canvasYPct < SNAP_Y_THRESHOLD) return 'none'
    if (canvasXPct < SNAP_X_LEFT) return 'left_hand'
    if (canvasXPct > SNAP_X_RIGHT) return 'right_hand'
    return 'none'
  }

  // Drag/resize handler
  useEffect(() => {
    if (!interaction) return
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const pxToH = H_RANGE / rect.width
    const pxToV = V_RANGE / rect.height

    const handleMouseMove = (e: MouseEvent) => {
      const dx = (e.clientX - interaction.startMouseX) * pxToH
      const dy = -(e.clientY - interaction.startMouseY) * pxToV

      if (interaction.type === 'drag') {
        const newX = Math.max(-1.0, Math.min(1.0, interaction.startX + dx))
        const newY = Math.max(-1.0, Math.min(1.0, interaction.startY + dy))
        const canvasXPct = (e.clientX - rect.left) / rect.width
        const canvasYPct = (e.clientY - rect.top) / rect.height
        const tracking = getSnapTracking(canvasXPct, canvasYPct)
        const trackingKey = interaction.element === 'notification' ? 'notificationTracking' : 'messageLogTracking'
        if (interaction.element === 'notification') {
          handleUpdate({ notificationX: Math.round(newX * 100) / 100, notificationY: Math.round(newY * 100) / 100, [trackingKey]: tracking })
        } else {
          handleUpdate({ messageLogX: Math.round(newX * 100) / 100, messageLogY: Math.round(newY * 100) / 100, [trackingKey]: tracking })
        }
      } else {
        const isNotif = interaction.element === 'notification'
        const maxW = isNotif ? NOTIF_MAX_W : LOG_MAX_W
        const maxH = isNotif ? NOTIF_MAX_H : LOG_MAX_H
        const minW = isNotif ? NOTIF_MIN_W : LOG_MIN_W
        const minH = isNotif ? NOTIF_MIN_H : LOG_MIN_H
        const c = interaction.corner || 'br'
        // Sign of dx/dy contribution depends on which corner is being dragged
        const dw = (c === 'tl' || c === 'bl') ? -dx : dx
        const dh = (c === 'tl' || c === 'tr') ? dy : -dy
        const newW = Math.max(minW, Math.min(maxW, interaction.startW + dw))
        const newH = Math.max(minH, Math.min(maxH, interaction.startH + dh))
        // Shift position to keep opposite corner fixed
        const wDelta = newW - interaction.startW
        const hDelta = newH - interaction.startH
        const xShift = (c === 'tl' || c === 'bl') ? -wDelta / 2 : wDelta / 2
        const yShift = (c === 'tl' || c === 'tr') ? hDelta / 2 : -hDelta / 2
        const newX = Math.round((interaction.startX + xShift) * 100) / 100
        const newY = Math.round((interaction.startY + yShift) * 100) / 100
        const prefix = isNotif ? 'notification' : 'messageLog'
        handleUpdate({
          [`${prefix}Width`]: Math.round(newW * 100) / 100,
          [`${prefix}Height`]: Math.round(newH * 100) / 100,
          [`${prefix}X`]: newX,
          [`${prefix}Y`]: newY,
        })
      }
    }

    const handleMouseUp = () => setInteraction(null)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [interaction, handleUpdate])

  const startDrag = (element: 'notification' | 'log', e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const isNotif = element === 'notification'
    setInteraction({
      type: 'drag', element,
      startMouseX: e.clientX, startMouseY: e.clientY,
      startX: isNotif ? vrOverlay.notificationX : vrOverlay.messageLogX,
      startY: isNotif ? vrOverlay.notificationY : vrOverlay.messageLogY,
      startW: 0, startH: 0,
    })
  }

  const startResize = (element: 'notification' | 'log', corner: 'tl' | 'tr' | 'bl' | 'br', e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const isNotif = element === 'notification'
    setInteraction({
      type: 'resize', element, corner,
      startMouseX: e.clientX, startMouseY: e.clientY,
      startX: isNotif ? vrOverlay.notificationX : vrOverlay.messageLogX,
      startY: isNotif ? vrOverlay.notificationY : vrOverlay.messageLogY,
      startW: isNotif ? vrOverlay.notificationWidth : vrOverlay.messageLogWidth,
      startH: isNotif ? vrOverlay.notificationHeight : vrOverlay.messageLogHeight,
    })
  }

  const handleResetDefaults = () => {
    const defaults: Record<string, unknown> = {
      showOriginalText: true, showTranslatedText: true,
      showAIResponses: true, showListenText: true,
      notificationEnabled: true, notificationTracking: 'none',
      notificationX: 0, notificationY: -0.3,
      notificationWidth: 0.4, notificationHeight: 0.15,
      notificationDistance: 1.5,
      notificationFontSize: 24, notificationFontColor: '#FFFFFF',
      notificationBgColor: '#000000', notificationBgOpacity: 0.7,
      notificationFadeIn: 0.3, notificationFadeOut: 0.5,
      notificationAutoHide: 5, notificationAdaptiveHeight: true,
      messageLogEnabled: false, messageLogTracking: 'none',
      messageLogX: 0, messageLogY: 0,
      messageLogWidth: 0.5, messageLogHeight: 0.4,
      messageLogDistance: 1.8,
      messageLogFontSize: 20, messageLogFontColor: '#FFFFFF',
      messageLogBgColor: '#000000', messageLogBgOpacity: 0.6,
      messageLogMax: 20,
    }
    updateVROverlay(defaults)
    updateSettings({ vrOverlay: defaults })
  }

  const steamVRInstalled = overlayStatus?.steamvr_installed ?? false
  const hmdPresent = overlayStatus?.hmd_present ?? false
  const isInitialized = overlayStatus?.initialized ?? false

  // Helper for per-element settings section
  const renderSlider = (label: string, value: number, min: number, max: number, step: number,
    format: (v: number) => string, key: string) => (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{label}</Label>
        <span className="text-xs text-muted-foreground font-mono">{format(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => handleUpdate({ [key]: parseFloat(e.target.value) })}
        className="w-full accent-primary" />
    </div>
  )

  const renderColorPicker = (label: string, value: string, key: string) => (
    <div className="flex items-center justify-between">
      <Label className="text-xs">{label}</Label>
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground font-mono">{value}</span>
        <input type="color" value={value}
          onChange={(e) => handleUpdate({ [key]: e.target.value })}
          className="w-6 h-6 rounded cursor-pointer border border-border bg-transparent" />
      </div>
    </div>
  )

  const renderTrackingToggle = (tracking: string, trackingKey: string) => (
    <div className="space-y-1">
      <Label className="text-xs">Attach To</Label>
      <div className="grid grid-cols-3 gap-1">
        {[
          { value: 'none', label: 'Head (HMD)' },
          { value: 'left_hand', label: 'Left Hand' },
          { value: 'right_hand', label: 'Right Hand' },
        ].map((opt) => (
          <button key={opt.value}
            onClick={() => handleUpdate({ [trackingKey]: opt.value })}
            className={`p-1 text-[10px] rounded border transition-colors ${
              tracking === opt.value
                ? 'border-primary bg-primary/20 text-primary'
                : 'border-border bg-secondary/20 text-muted-foreground hover:bg-secondary/40'
            }`}>{opt.label}</button>
        ))}
      </div>
    </div>
  )

  // Any item on a hand?
  const anyOnLeftHand = vrOverlay.notificationTracking === 'left_hand' || vrOverlay.messageLogTracking === 'left_hand'
  const anyOnRightHand = vrOverlay.notificationTracking === 'right_hand' || vrOverlay.messageLogTracking === 'right_hand'

  return (
    <div className="p-4 space-y-6">
      <h3 className="text-lg font-medium">VR Overlay</h3>

      {/* Status Banner */}
      {!steamVRInstalled ? (
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <p className="text-xs text-yellow-400">
            <strong>SteamVR not detected.</strong> Install SteamVR to use the VR overlay.
          </p>
        </div>
      ) : !hmdPresent ? (
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <p className="text-xs text-yellow-400">
            <strong>No VR headset detected.</strong> Connect and power on your headset.
          </p>
        </div>
      ) : isInitialized ? (
        <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
          <p className="text-xs text-green-400">
            <strong>VR Overlay Active</strong> — Running in SteamVR.
          </p>
        </div>
      ) : null}

      {/* Enable */}
      <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
        <div>
          <p className="text-sm font-medium">Enable VR Overlay</p>
          <p className="text-xs text-muted-foreground">Show text overlay in your VR headset</p>
        </div>
        <Switch checked={vrOverlay.enabled} onCheckedChange={(enabled) => handleUpdate({ enabled })} />
      </div>

      {/* ========== CANVAS EDITOR ========== */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Layout</Label>
        <p className="text-xs text-muted-foreground">Drag to move, corner handle to resize. Drag to bottom corners to attach to hand.</p>

        <div
          ref={canvasRef}
          className="relative border border-border bg-black/60 select-none overflow-hidden mx-auto"
          style={{ aspectRatio: '16/9', borderRadius: '0.75rem', width: '100%', maxWidth: '1000px' }}
        >
          {/* Center crosshair */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/10" />
          <div className="absolute top-1/2 left-0 right-0 h-px bg-white/10" />
          <span className="absolute top-1 left-2 text-[9px] text-white/20">VR Field of View</span>

          {/* Hand snap zones */}
          <div className={`absolute bottom-0 left-0 w-[30%] h-[30%] border-t border-r border-dashed flex items-center justify-center ${anyOnLeftHand ? 'border-yellow-400/40 bg-yellow-400/5' : 'border-white/15'}`}>
            <span className={`text-xs font-medium ${anyOnLeftHand ? 'text-yellow-400' : 'text-white/25'}`}>Left Hand</span>
          </div>
          <div className={`absolute bottom-0 right-0 w-[30%] h-[30%] border-t border-l border-dashed flex items-center justify-center ${anyOnRightHand ? 'border-yellow-400/40 bg-yellow-400/5' : 'border-white/15'}`}>
            <span className={`text-xs font-medium ${anyOnRightHand ? 'text-yellow-400' : 'text-white/25'}`}>Right Hand</span>
          </div>

          {/* Notification rectangle */}
          {vrOverlay.notificationEnabled && (() => {
            const onHand = vrOverlay.notificationTracking !== 'none'
            const handleColor = onHand ? 'bg-yellow-400/60' : 'bg-blue-400/60'
            return (
              <div
                className={`absolute border-2 cursor-move flex items-center justify-center ${
                  onHand ? 'border-yellow-400 bg-yellow-500/15' : 'border-blue-400 bg-blue-500/15'
                }`}
                style={{
                  left: `${toCanvasX(vrOverlay.notificationX) - toCanvasW(vrOverlay.notificationWidth) / 2}%`,
                  top: `${toCanvasY(vrOverlay.notificationY) - toCanvasH(vrOverlay.notificationHeight) / 2}%`,
                  width: `${toCanvasW(vrOverlay.notificationWidth)}%`,
                  height: `${toCanvasH(vrOverlay.notificationHeight)}%`,
                }}
                onMouseDown={(e) => startDrag('notification', e)}
              >
                <span className={`text-[10px] pointer-events-none ${onHand ? 'text-yellow-300' : 'text-blue-300'}`}>
                  Notification{onHand ? ` (${vrOverlay.notificationTracking === 'left_hand' ? 'L' : 'R'})` : ''}
                </span>
                <div className={`absolute left-0 top-0 w-2.5 h-2.5 cursor-nw-resize ${handleColor}`} onMouseDown={(e) => startResize('notification', 'tl', e)} />
                <div className={`absolute right-0 top-0 w-2.5 h-2.5 cursor-ne-resize ${handleColor}`} onMouseDown={(e) => startResize('notification', 'tr', e)} />
                <div className={`absolute left-0 bottom-0 w-2.5 h-2.5 cursor-sw-resize ${handleColor}`} onMouseDown={(e) => startResize('notification', 'bl', e)} />
                <div className={`absolute right-0 bottom-0 w-2.5 h-2.5 cursor-se-resize ${handleColor}`} onMouseDown={(e) => startResize('notification', 'br', e)} />
              </div>
            )
          })()}

          {/* Log rectangle */}
          {vrOverlay.messageLogEnabled && (() => {
            const onHand = vrOverlay.messageLogTracking !== 'none'
            const handleColor = onHand ? 'bg-yellow-400/60' : 'bg-green-400/60'
            return (
              <div
                className={`absolute border-2 cursor-move flex items-center justify-center ${
                  onHand ? 'border-yellow-400 bg-yellow-500/15' : 'border-green-400 bg-green-500/15'
                }`}
                style={{
                  left: `${toCanvasX(vrOverlay.messageLogX) - toCanvasW(vrOverlay.messageLogWidth) / 2}%`,
                  top: `${toCanvasY(vrOverlay.messageLogY) - toCanvasH(vrOverlay.messageLogHeight) / 2}%`,
                  width: `${toCanvasW(vrOverlay.messageLogWidth)}%`,
                  height: `${toCanvasH(vrOverlay.messageLogHeight)}%`,
                }}
                onMouseDown={(e) => startDrag('log', e)}
              >
                <span className={`text-[10px] pointer-events-none ${onHand ? 'text-yellow-300' : 'text-green-300'}`}>
                  Message Log{onHand ? ` (${vrOverlay.messageLogTracking === 'left_hand' ? 'L' : 'R'})` : ''}
                </span>
                <div className={`absolute left-0 top-0 w-2.5 h-2.5 cursor-nw-resize ${handleColor}`} onMouseDown={(e) => startResize('log', 'tl', e)} />
                <div className={`absolute right-0 top-0 w-2.5 h-2.5 cursor-ne-resize ${handleColor}`} onMouseDown={(e) => startResize('log', 'tr', e)} />
                <div className={`absolute left-0 bottom-0 w-2.5 h-2.5 cursor-sw-resize ${handleColor}`} onMouseDown={(e) => startResize('log', 'bl', e)} />
                <div className={`absolute right-0 bottom-0 w-2.5 h-2.5 cursor-se-resize ${handleColor}`} onMouseDown={(e) => startResize('log', 'br', e)} />
              </div>
            )
          })()}
        </div>
      </div>

      {/* ========== PANEL SETTINGS — SIDE BY SIDE ========== */}
      <div className="grid grid-cols-2 gap-3">
        {/* Notification */}
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="flex items-center justify-between p-2 bg-secondary/20">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-sm bg-blue-400" />
              <span className="text-xs font-medium">Notification</span>
            </div>
            <Switch checked={vrOverlay.notificationEnabled}
              onCheckedChange={(v) => handleUpdate({ notificationEnabled: v })} />
          </div>
          {vrOverlay.notificationEnabled && (
            <div className="p-2.5 space-y-2.5 border-t border-border">
              {renderTrackingToggle(vrOverlay.notificationTracking, 'notificationTracking')}
              {renderSlider('Depth from you (meters)', vrOverlay.notificationDistance, 0.05, 5, 0.05, v => `${v.toFixed(2)}m`, 'notificationDistance')}
              {renderSlider('Font Size (in VR)', vrOverlay.notificationFontSize, 12, 64, 2, v => `${v}px`, 'notificationFontSize')}
              {renderColorPicker('Font Color', vrOverlay.notificationFontColor, 'notificationFontColor')}
              {renderColorPicker('Background', vrOverlay.notificationBgColor, 'notificationBgColor')}
              {renderSlider('BG Opacity', vrOverlay.notificationBgOpacity, 0, 1, 0.05, v => `${Math.round(v * 100)}%`, 'notificationBgOpacity')}
              {renderSlider('Auto-hide', vrOverlay.notificationAutoHide, 0, 30, 1, v => v === 0 ? 'Never' : `${v}s`, 'notificationAutoHide')}
              {renderSlider('Fade In', vrOverlay.notificationFadeIn, 0, 2, 0.1, v => v === 0 ? 'Instant' : `${v.toFixed(1)}s`, 'notificationFadeIn')}
              {renderSlider('Fade Out', vrOverlay.notificationFadeOut, 0, 2, 0.1, v => v === 0 ? 'Instant' : `${v.toFixed(1)}s`, 'notificationFadeOut')}
              <div className="flex items-center justify-between">
                <Label className="text-xs">Adaptive Height</Label>
                <Switch checked={vrOverlay.notificationAdaptiveHeight}
                  onCheckedChange={(v) => handleUpdate({ notificationAdaptiveHeight: v })} />
              </div>
              {/* Live Preview */}
              <div className="rounded p-2 text-center transition-all overflow-hidden" style={{
                backgroundColor: vrOverlay.notificationBgColor + Math.round(vrOverlay.notificationBgOpacity * 255).toString(16).padStart(2, '0'),
                color: vrOverlay.notificationFontColor,
                fontSize: `${Math.round(10 + (vrOverlay.notificationFontSize - 12) * 0.3)}px`,
              }}>Hello! Preview text.</div>
            </div>
          )}
        </div>

        {/* Message Log */}
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="flex items-center justify-between p-2 bg-secondary/20">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-sm bg-green-400" />
              <span className="text-xs font-medium">Message Log</span>
            </div>
            <Switch checked={vrOverlay.messageLogEnabled}
              onCheckedChange={(v) => handleUpdate({ messageLogEnabled: v })} />
          </div>
          {vrOverlay.messageLogEnabled && (
            <div className="p-2.5 space-y-2.5 border-t border-border">
              {renderTrackingToggle(vrOverlay.messageLogTracking, 'messageLogTracking')}
              {renderSlider('Depth from you (meters)', vrOverlay.messageLogDistance, 0.05, 5, 0.05, v => `${v.toFixed(2)}m`, 'messageLogDistance')}
              {renderSlider('Font Size (in VR)', vrOverlay.messageLogFontSize, 12, 48, 2, v => `${v}px`, 'messageLogFontSize')}
              {renderColorPicker('Font Color', vrOverlay.messageLogFontColor, 'messageLogFontColor')}
              {renderColorPicker('Background', vrOverlay.messageLogBgColor, 'messageLogBgColor')}
              {renderSlider('BG Opacity', vrOverlay.messageLogBgOpacity, 0, 1, 0.05, v => `${Math.round(v * 100)}%`, 'messageLogBgOpacity')}
              {renderSlider('Max Messages', vrOverlay.messageLogMax, 5, 50, 5, v => `${v}`, 'messageLogMax')}
              {/* Live Preview */}
              <div className="rounded p-2 space-y-0.5 transition-all overflow-hidden" style={{
                backgroundColor: vrOverlay.messageLogBgColor + Math.round(vrOverlay.messageLogBgOpacity * 255).toString(16).padStart(2, '0'),
                color: vrOverlay.messageLogFontColor,
                fontSize: `${Math.round(9 + (vrOverlay.messageLogFontSize - 12) * 0.25)}px`,
              }}>
                <div style={{ color: '#64c8ff' }}>[You] Hello!</div>
                <div style={{ color: '#c8ff64' }}>[Other] Hi there</div>
                <div style={{ color: '#ffb464' }}>[AI] How can I help?</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* ========== DISPLAY CONTENT ========== */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Eye className="w-4 h-4" />
          Display Content
        </div>
        <div className="grid grid-cols-2 gap-2">
          {[
            { key: 'showOriginalText', label: 'Original text', Icon: Mic },
            { key: 'showTranslatedText', label: 'Translated text', Icon: Languages },
            { key: 'showAIResponses', label: 'AI responses', Icon: Bot },
            { key: 'showListenText', label: 'Listen text', Icon: Headphones },
          ].map(({ key, label, Icon }) => (
            <div key={key} className="flex items-center justify-between p-2 bg-secondary/20 rounded">
              <div className="flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs">{label}</span>
              </div>
              <Switch checked={vrOverlay[key as keyof typeof vrOverlay] as boolean}
                onCheckedChange={(show) => handleUpdate({ [key]: show })} />
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-border" />

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

function OutputProfileCard({ profile, outputDevices, isDefault, onUpdate, onRemove }: {
  profile: OutputProfile
  outputDevices: AudioDevice[]
  isDefault: boolean
  onUpdate: (settings: Partial<OutputProfile>) => void
  onRemove: () => void
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(profile.name)

  const outputDeviceOptions = outputDevices.map(d => ({
    value: String(d.id),
    label: `${d.name}${d.is_default ? ' (Default)' : ''}`,
  }))

  const handleNameSave = () => {
    if (editName.trim()) {
      onUpdate({ name: editName.trim() })
    }
    setIsEditing(false)
  }

  return (
    <div className="border border-border rounded-lg p-4 space-y-4">
      {/* Profile header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isEditing ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onBlur={handleNameSave}
                onKeyDown={(e) => e.key === 'Enter' && handleNameSave()}
                className="bg-secondary px-2 py-1 rounded text-sm font-medium w-40"
                autoFocus
              />
            </div>
          ) : (
            <button
              onClick={() => { setEditName(profile.name); setIsEditing(true) }}
              className="text-sm font-medium hover:text-primary transition-colors"
              title="Click to rename"
            >
              {profile.name}
            </button>
          )}
          {isDefault && (
            <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded">
              DEFAULT
            </span>
          )}
        </div>
        {!isDefault && (
          <Button variant="ghost" size="icon" onClick={onRemove} title="Remove profile">
            <Trash2 className="w-4 h-4 text-muted-foreground hover:text-destructive" />
          </Button>
        )}
      </div>

      {/* Audio Output */}
      <div className="space-y-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <Volume2 className="w-3 h-3" /> Audio Output
        </div>

        <div className="space-y-2">
          <Label className="text-sm">Output Device</Label>
          <Select
            value={profile.audioOutputDeviceId || ''}
            onValueChange={(v) => onUpdate({ audioOutputDeviceId: v || null })}
            options={[
              { value: '', label: 'System Default' },
              ...outputDeviceOptions,
            ]}
            placeholder="Select output device..."
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
            <span className="text-xs">TTS Audio</span>
            <Switch
              checked={profile.sendTtsAudio}
              onCheckedChange={(v) => onUpdate({ sendTtsAudio: v })}
            />
          </div>
          <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
            <span className="text-xs">RVC Audio</span>
            <Switch
              checked={profile.sendRvcAudio}
              onCheckedChange={(v) => onUpdate({ sendRvcAudio: v })}
            />
          </div>
        </div>
      </div>

      {/* OSC / Text Output */}
      <div className="space-y-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <Send className="w-3 h-3" /> OSC / Text Output
        </div>

        <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
          <span className="text-xs">OSC Enabled</span>
          <Switch
            checked={profile.oscEnabled}
            onCheckedChange={(v) => onUpdate({ oscEnabled: v })}
          />
        </div>

        {profile.oscEnabled && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">OSC IP</Label>
                <input
                  type="text"
                  value={profile.oscIP}
                  onChange={(e) => onUpdate({ oscIP: e.target.value })}
                  className="w-full bg-secondary px-2 py-1.5 rounded text-sm font-mono"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">OSC Port</Label>
                <input
                  type="number"
                  value={profile.oscPort}
                  onChange={(e) => onUpdate({ oscPort: parseInt(e.target.value) || 9000 })}
                  className="w-full bg-secondary px-2 py-1.5 rounded text-sm font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
                <span className="text-xs">Original Text</span>
                <Switch
                  checked={profile.sendOriginalText}
                  onCheckedChange={(v) => onUpdate({ sendOriginalText: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
                <span className="text-xs">Translated Text</span>
                <Switch
                  checked={profile.sendTranslatedText}
                  onCheckedChange={(v) => onUpdate({ sendTranslatedText: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
                <span className="text-xs">AI Responses</span>
                <Switch
                  checked={profile.sendAiResponses}
                  onCheckedChange={(v) => onUpdate({ sendAiResponses: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
                <span className="text-xs">Listen Text</span>
                <Switch
                  checked={profile.sendListenText}
                  onCheckedChange={(v) => onUpdate({ sendListenText: v })}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function OutputProfilesSettings() {
  const { outputProfiles, addOutputProfile, removeOutputProfile, updateOutputProfile } = useSettingsStore()
  const { getAudioDevices, lastMessage, updateSettings } = useBackend()
  const [outputDevices, setOutputDevices] = useState<AudioDevice[]>([])

  useEffect(() => {
    getAudioDevices()
  }, [getAudioDevices])

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'audio_devices') {
      const payload = lastMessage.payload as { outputs?: AudioDevice[] }
      setOutputDevices(payload.outputs || [])
    }
  }, [lastMessage])

  const handleUpdate = (id: string, settings: Partial<OutputProfile>) => {
    updateOutputProfile(id, settings)
    // Sync to backend
    const profiles = useSettingsStore.getState().outputProfiles
    updateSettings({ output_profiles: profiles })
  }

  const handleAdd = () => {
    addOutputProfile()
    const profiles = useSettingsStore.getState().outputProfiles
    updateSettings({ output_profiles: profiles })
  }

  const handleRemove = (id: string) => {
    removeOutputProfile(id)
    const profiles = useSettingsStore.getState().outputProfiles
    updateSettings({ output_profiles: profiles })
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">Output Routing</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Route audio and text to different speakers and OSC destinations.
          </p>
        </div>
        {outputProfiles.length < 5 && (
          <Button variant="outline" size="sm" onClick={handleAdd}>
            <Plus className="w-4 h-4 mr-2" />
            Add Profile
          </Button>
        )}
      </div>

      {/* Info box */}
      <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
        <p className="text-xs text-blue-400">
          <strong>Profile 1</strong> is your default output and cannot be removed.
          Additional profiles let you send different content to different destinations
          (e.g., your language to one VRChat instance, translations to another).
        </p>
      </div>

      {/* Profile cards */}
      <div className="space-y-4">
        {outputProfiles.map((profile) => (
          <OutputProfileCard
            key={profile.id}
            profile={profile}
            outputDevices={outputDevices}
            isDefault={profile.id === 'default'}
            onUpdate={(settings) => handleUpdate(profile.id, settings)}
            onRemove={() => handleRemove(profile.id)}
          />
        ))}
      </div>

      {outputProfiles.length >= 5 && (
        <p className="text-xs text-muted-foreground text-center">
          Maximum of 5 profiles reached.
        </p>
      )}
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
  const globalRvcLoaded = useChatStore((s) => s.isRvcModelLoaded)
  const isMicRvcActive = useChatStore((s) => s.isMicRvcActive)
  const showDownloadDialog = useChatStore((s) => s.rvcBaseModelsNeeded)
  const downloadSizeMb = useChatStore((s) => s.rvcBaseModelsSizeMb)
  const storeDownloadProgress = useChatStore((s) => s.rvcDownloadProgress)

  // Local state for runtime RVC data (not persisted)
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; path: string; index_path: string | null; size_mb: number }>>([])
  const [isModelLoaded, setIsModelLoaded] = useState(globalRvcLoaded)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState('')
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [memoryUsageMb, setMemoryUsageMb] = useState(0)
  const [modelName, setModelName] = useState<string | null>(null)
  const [isTestingVoice, setIsTestingVoice] = useState(false)
  const [outputDevices, setOutputDevices] = useState<Array<{ id: number; name: string }>>([])

  // Derive download progress from store
  const downloadProgress = storeDownloadProgress?.progress ?? 0
  const downloadFile = storeDownloadProgress?.file ?? ''
  const [browsePath, setBrowsePath] = useState('')

  // Sync local loaded state with global store (for auto-load on connect)
  useEffect(() => {
    setIsModelLoaded(globalRvcLoaded)
  }, [globalRvcLoaded])

  // Request model list, status, and available devices on mount
  useEffect(() => {
    sendMessage({ type: 'rvc_scan_models' })
    sendMessage({ type: 'rvc_get_status' })
    sendMessage({ type: 'rvc_get_available_devices' })
    sendMessage({ type: 'get_tts_output_devices' })
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
        const payload = lastMessage.payload as { model_name?: string; memory_mb?: number; has_index?: boolean }
        setIsLoading(false)
        setIsModelLoaded(true)
        setLoadingProgress(0)
        setLoadingStage('')
        if (payload.memory_mb) setMemoryUsageMb(payload.memory_mb)
        if (payload.model_name) setModelName(payload.model_name)
        // Save to recent models
        const currentPath = useSettingsStore.getState().rvc.modelPath
        if (currentPath && payload.model_name) {
          addRecentModel(payload.model_name, currentPath, useSettingsStore.getState().rvc.indexPath, payload.memory_mb || 0)
        }
        break
      }
      case 'rvc_model_error': {
        setIsLoading(false)
        setLoadingStage('')
        setLoadingProgress(0)
        break
      }
      case 'rvc_model_loading': {
        const payload = lastMessage.payload as { stage?: string; progress?: number }
        setIsLoading(true)
        if (payload.stage) setLoadingStage(payload.stage)
        if (payload.progress !== undefined) setLoadingProgress(payload.progress * 100)
        break
      }
      case 'rvc_unloaded': {
        setIsModelLoaded(false)
        setMemoryUsageMb(0)
        setModelName(null)
        useSettingsStore.getState().updateRVC({ modelPath: null, indexPath: null })
        break
      }
      case 'rvc_status': {
        const payload = lastMessage.payload as {
          enabled?: boolean; loaded?: boolean; model_name?: string | null; memory_mb?: number
        }
        if (payload.loaded !== undefined) setIsModelLoaded(payload.loaded)
        if (payload.model_name) setModelName(payload.model_name)
        if (payload.memory_mb) setMemoryUsageMb(payload.memory_mb)
        break
      }
      case 'rvc_base_models_needed': {
        // Handled by chatStore via handleGlobalMessage
        setIsLoading(false)
        break
      }
      case 'rvc_download_progress': {
        // Handled by chatStore via handleGlobalMessage
        break
      }
      case 'rvc_test_voice_ready': {
        const payload = lastMessage.payload as { audio_base64?: string; sample_rate?: number }
        setIsTestingVoice(false)
        if (payload.audio_base64) {
          const audioBytes = Uint8Array.from(atob(payload.audio_base64), c => c.charCodeAt(0))
          const blob = new Blob([audioBytes], { type: 'audio/wav' })
          const url = URL.createObjectURL(blob)
          const audio = new Audio(url)
          audio.onended = () => URL.revokeObjectURL(url)
          audio.play()
        }
        break
      }
      case 'rvc_test_voice_error': {
        setIsTestingVoice(false)
        break
      }
      case 'rvc_model_browsed': {
        const payload = lastMessage.payload as { path?: string; index_path?: string | null }
        if (payload.path) {
          loadModel(payload.path, payload.index_path)
        }
        break
      }
      case 'rvc_mic_started':
      case 'rvc_mic_stopped':
        // Handled globally by useBackend → chatStore.setMicRvcActive
        break
      case 'rvc_available_devices': {
        const payload = lastMessage.payload as { devices?: string[] }
        if (payload.devices) settings.updateRVC({ rvcAvailableDevices: payload.devices })
        break
      }
      case 'tts_output_devices': {
        const payload = lastMessage.payload as { devices?: Array<{ id: number; name: string }> }
        if (payload.devices) setOutputDevices(payload.devices)
        break
      }
    }
  }, [lastMessage])

  const handleEnableToggle = (checked: boolean) => {
    settings.updateRVC({ enabled: checked })
    sendMessage({ type: 'rvc_enable', payload: { enabled: checked } })
    // Note: disabling TTS→RVC does NOT unload the model.
    // The model stays loaded so mic→RVC can still work independently.
    // Use the explicit "Unload" button to free model memory.
  }

  const addRecentModel = (name: string, path: string, indexPath: string | null, sizeMb: number) => {
    const recent = (settings.rvc.recentModels || []).filter(m => m.path !== path)
    recent.unshift({ name, path, indexPath, sizeMb })
    settings.updateRVC({ recentModels: recent.slice(0, 5) })
  }

  const removeRecentModel = (path: string) => {
    settings.updateRVC({ recentModels: (settings.rvc.recentModels || []).filter(m => m.path !== path) })
  }

  const loadModel = (path: string, indexPath?: string | null) => {
    if (isLoading) return
    settings.updateRVC({ modelPath: path, indexPath: indexPath || null })
    setIsLoading(true)
    setLoadingStage('Loading voice model...')
    setLoadingProgress(0)
    sendMessage({ type: 'rvc_load_model', payload: { model_path: path, ...(indexPath ? { index_path: indexPath } : {}) } })
  }

  const handleLoadFromPath = () => {
    const path = browsePath.trim().replace(/^["']+|["']+$/g, '').replace(/\//g, '\\')
    if (!path) return
    loadModel(path)
    setBrowsePath('')
  }

  const handleBrowse = () => {
    if (isLoading) return
    sendMessage({ type: 'rvc_browse_model' })
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
    setIsTestingVoice(true)
    sendMessage({ type: 'rvc_test_voice' })
  }

  const handleDownloadBaseModels = () => {
    useChatStore.getState().setRvcDownloadProgress({ file: '', progress: 0 })
    sendMessage({ type: 'rvc_download_base_models' })
  }

  const handleMicRvcToggle = (checked: boolean) => {
    settings.updateRVC({ micRvcEnabled: checked })
    useChatStore.getState().setMicRvcActive(checked)  // Optimistic UI update
    if (checked) {
      sendMessage({
        type: 'rvc_mic_start',
        payload: { output_device_id: settings.rvc.micRvcOutputDeviceId }
      })
    } else {
      sendMessage({ type: 'rvc_mic_stop' })
    }
  }

  const handleMicRvcOutputDevice = (deviceId: string) => {
    const id = parseInt(deviceId)
    settings.updateRVC({ micRvcOutputDeviceId: id })
    if (isMicRvcActive) {
      sendMessage({ type: 'rvc_mic_set_output_device', payload: { device_id: id } })
    }
  }

  const handleDeviceChange = (device: string) => {
    settings.updateRVC({ rvcDevice: device as 'cpu' | 'cuda' | 'directml' })
    sendMessage({ type: 'rvc_set_device', payload: { device } })
  }

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Voice Conversion</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Apply RVC voice models to transform TTS output into a different voice. Load a .pth voice model and adjust conversion parameters.
        </p>
      </div>

      {/* Apply to TTS Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Apply to TTS Output</Label>
          <p className="text-xs text-muted-foreground">
            Post-process TTS audio through the selected voice model
          </p>
        </div>
        <Switch
          checked={settings.rvc.enabled}
          onCheckedChange={handleEnableToggle}
        />
      </div>

      {/* Real-Time Mic Conversion */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Real-Time Mic Conversion</Label>
          <p className="text-xs text-muted-foreground">
            Convert your microphone audio through the voice model in real-time
          </p>
        </div>
        <Switch
          checked={isMicRvcActive}
          onCheckedChange={handleMicRvcToggle}
          disabled={!isModelLoaded}
        />
      </div>

      {/* Mic RVC Output Device */}
      {isMicRvcActive && (
        <div className="space-y-2">
          <Label>Conversion Output Device</Label>
          <Select
            value={String(settings.rvc.micRvcOutputDeviceId ?? '')}
            onValueChange={handleMicRvcOutputDevice}
            options={outputDevices.map(d => ({ value: String(d.id), label: d.name }))}
            placeholder="Select output device..."
          />
          <p className="text-xs text-muted-foreground">
            Where converted audio plays. Use a virtual audio cable for Discord/VRChat.
          </p>
        </div>
      )}

      {/* Voice Model */}
      <div className="space-y-3">
        <Label>Voice Model</Label>

        {/* Warning: RVC enabled but no model */}
        {settings.rvc.enabled && !isModelLoaded && !isLoading && (
          <div className="flex items-center gap-2 p-2.5 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
            <AlertCircle className="w-4 h-4 text-yellow-500 shrink-0" />
            <span className="text-sm text-yellow-200">Voice conversion is enabled but no model is loaded</span>
          </div>
        )}

        {/* Load input + buttons */}
        {!isLoading && (
          <div className="flex gap-2">
            <input
              type="text"
              value={browsePath}
              onChange={(e) => setBrowsePath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLoadFromPath()}
              placeholder="Path to .pth file..."
              className="flex-1 h-9 px-3 rounded-md border border-input bg-background text-sm"
            />
            <button
              onClick={handleLoadFromPath}
              disabled={!browsePath.trim()}
              className="h-9 px-3 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
              title="Load model"
            >
              Load
            </button>
            <button
              onClick={handleBrowse}
              className="h-9 px-3 rounded-md bg-secondary text-secondary-foreground text-sm font-medium hover:bg-secondary/80 transition-colors"
              title="Browse for model file"
            >
              <FolderOpen className="w-4 h-4" />
            </button>
          </div>
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

        {/* Recent Models as cards */}
        {(settings.rvc.recentModels || []).length > 0 && (
          <div className="space-y-1.5">
            {(settings.rvc.recentModels || []).map((model) => {
              const isActive = isModelLoaded && settings.rvc.modelPath === model.path
              return (
                <div
                  key={model.path}
                  className={`flex items-center justify-between p-2.5 rounded-lg border transition-colors ${
                    isActive
                      ? 'bg-primary/10 border-primary'
                      : 'bg-secondary/30 border-transparent hover:bg-secondary/50'
                  }`}
                >
                  <button
                    onClick={() => !isActive && !isLoading && loadModel(model.path, model.indexPath)}
                    disabled={isActive || isLoading}
                    className="flex-1 text-left min-w-0"
                  >
                    <div className="flex items-center gap-2">
                      {isActive && <Activity className="w-3.5 h-3.5 text-green-400 shrink-0" />}
                      <span className={`text-sm truncate ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>{model.name}</span>
                      {model.sizeMb > 0 && (
                        <span className="text-[10px] text-muted-foreground shrink-0">{model.sizeMb} MB</span>
                      )}
                    </div>
                  </button>
                  {isActive ? (
                    <Button variant="ghost" size="sm" onClick={handleUnloadModel} className="shrink-0 ml-2 text-xs h-7">
                      Unload
                    </Button>
                  ) : (
                    <button
                      onClick={() => removeRecentModel(model.path)}
                      className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors shrink-0 ml-2"
                      title="Remove from recent"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Quality Control Sliders */}
      <div className={`space-y-4 ${!isModelLoaded ? 'opacity-50 pointer-events-none' : ''}`}>
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Quality Controls</h4>

        {/* Compute Device */}
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Compute Device</Label>
            <p className="text-xs text-muted-foreground">GPU provides lower latency</p>
          </div>
          <DeviceToggle
            device={settings.rvc.rvcDevice}
            onChange={(d) => handleDeviceChange(d)}
          />
        </div>

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
          disabled={!isModelLoaded || isTestingVoice}
          onClick={handleTestVoice}
          className="w-full gap-2"
        >
          {isTestingVoice ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Recording & Converting...
            </>
          ) : (
            <>
              <Mic className="w-4 h-4" />
              Test Voice (3s recording)
            </>
          )}
        </Button>
        <p className="text-xs text-muted-foreground">
          Records 3 seconds from your microphone, converts through the loaded voice model, and plays back.
        </p>
      </div>

      {/* Base Model Download Dialog */}
      {showDownloadDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background border rounded-lg p-6 max-w-md mx-4">
            <h3 className="text-lg font-semibold mb-2">Download Required</h3>
            <p className="text-sm text-muted-foreground mb-4">
              RVC needs to download ~{downloadSizeMb} MB of base models (HuBERT + RMVPE).
              This is a one-time setup.
            </p>
            {downloadProgress > 0 ? (
              <div className="space-y-2">
                <p className="text-sm">Downloading {downloadFile}...</p>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${downloadProgress * 100}%` }}
                  />
                </div>
                {downloadProgress >= 1 && (
                  <p className="text-xs text-green-400">Download complete! Loading model...</p>
                )}
              </div>
            ) : (
              <div className="flex gap-2 justify-end">
                <Button variant="ghost" onClick={() => useChatStore.getState().setRvcBaseModelsNeeded(false)}>Cancel</Button>
                <Button onClick={handleDownloadBaseModels}>Download Now</Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">About Voice Conversion</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li>RVC (Retrieval-based Voice Conversion) transforms TTS audio into a selected voice</li>
          <li>Place .pth model files in the models/rvc/voices folder, or use Browse to select from anywhere</li>
          <li>.index files are optional but improve timbre accuracy when placed alongside the .pth file</li>
          <li>CPU processing adds 1-5 seconds of latency depending on audio length</li>
          <li>Use the Unload button to free model memory when done</li>
        </ul>
      </div>
    </div>
  )
}
