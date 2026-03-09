import { useState, useEffect, useCallback, useRef } from 'react'
import { ArrowLeft, Home, Cpu, Volume2, Bot, Monitor, Headphones, Key, Languages, Check, Loader2, Play, Square, Wifi, WifiOff, Mic, MicOff, RefreshCw, Activity, AlertCircle, Eye, RotateCcw, Trash2, AudioLines, Download, FolderOpen, X, Plus, Send, ScanText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Select } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { useSettingsStore, useChatStore, type ComputeDevice, type TTSEngine, type AIProvider, type OutputProfile } from '@/stores'
import { useModelStore } from '@/stores/modelStore'
import { useFeaturesStore } from '@/stores/featuresStore'
import { useBackend } from '@/hooks/useBackend'
import FeaturesManager from './FeaturesManager'

type SettingsPage = 'main' | 'models' | 'translation' | 'tts' | 'ai' | 'voiceConversion' | 'overlay' | 'audio' | 'vrchat' | 'credentials' | 'features'

interface SettingsViewProps {
  onBack: () => void
  initialPage?: SettingsPage
}

const settingsPages = [
  { id: 'models' as const, label: 'Speech Recognition', icon: Cpu },
  { id: 'translation' as const, label: 'Translation', icon: Languages },
  { id: 'tts' as const, label: 'Text-to-Speech', icon: Volume2 },
  { id: 'ai' as const, label: 'AI Assistant', icon: Bot },
  { id: 'voiceConversion' as const, label: 'Voice Conversion', icon: AudioLines },
  { id: 'overlay' as const, label: 'VR Overlay', icon: Monitor },
  { id: 'audio' as const, label: 'Audio', icon: Headphones },
  { id: 'vrchat' as const, label: 'OSC', icon: Send },
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
      case 'vrchat':
        return <VRChatSettings />
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
          onClick={currentPage === 'main' ? onBack : () => { console.log('[Settings] Navigate back to main'); setCurrentPage('main') }}
          title={currentPage === 'main' ? 'Back to chat' : 'Back to settings'}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          title="Back to chat"
        >
          <Home className="w-4 h-4" />
        </Button>
        <span className="font-semibold">
          {currentPage === 'main'
            ? 'Settings'
            : settingsPages.find((p) => p.id === currentPage)?.label || 'Settings'}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto">{renderContent()}</div>
      </div>
    </div>
  )
}

const TTS_ENGINE_OPTIONS_ALL = [
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
        onClick={() => { console.log('[Settings] Device toggle → CPU'); onChange('cpu') }}
        className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
          !isGpu
            ? 'bg-primary text-primary-foreground'
            : 'hover:bg-secondary/80 text-muted-foreground'
        }`}
      >
        CPU
      </button>
      <button
        onClick={() => { console.log('[Settings] Device toggle → GPU'); onChange('cuda') }}
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
  const voicevoxInstalled = useFeaturesStore((s) => s.voicevoxInstalled)

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

  /** Trigger app restart after device change (models need reloading on new device) */
  const restartForDevice = (delay = 800) => {
    console.log('[Settings] Device changed — scheduling app restart')
    setTimeout(() => {
      console.log('[Settings] Sending restart_app for device change')
      sendMessage({ type: 'restart_app' })
    }, delay)
  }

  /** Global device change: sets ALL component devices at once */
  const setGlobalDevice = (d: 'cpu' | 'cuda') => {
    console.log('[Settings] Global device change', d)
    settings.updateSTT({ device: d })
    settings.updateTTS({ device: d })
    settings.updateTranslation({ device: d })
    settings.updateAI({ device: d })
    settings.updateRVC({ rvcDevice: d })
    sendMessage({ type: 'update_settings', payload: { stt: { device: d }, tts: { device: d }, translation: { device: d }, ai: { device: d } } })
    sendMessage({ type: 'rvc_set_device', payload: { device: d } })
    restartForDevice()
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
          <span className="text-sm">All Models</span>
          <span className="text-[10px] text-muted-foreground">(sets all at once)</span>
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
            console.log('[Settings] STT device change', d)
            settings.updateSTT({ device: d })
            sendMessage({ type: 'update_settings', payload: { stt: { device: d } } })
            restartForDevice()
          }}
        />
      </div>

      {/* Row 3: TTS — device + engine */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">TTS</span>
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.tts.device}
            onChange={(d) => {
              console.log('[Settings] TTS device change', d)
              settings.updateTTS({ device: d })
              sendMessage({ type: 'update_settings', payload: { tts: { device: d } } })
              restartForDevice()
            }}
          />
          <select
            value={settings.tts.engine}
            onChange={(e) => {
              const engine = e.target.value as TTSEngine
              console.log('[Settings] TTS engine change', engine)
              // Save current voice for the old engine before switching
              const voicePerEngine = { ...(settings.tts.voicePerEngine ?? {}), [settings.tts.engine]: settings.tts.voice }
              settings.updateTTS({ engine, voicePerEngine })
              sendMessage({ type: 'update_settings', payload: { tts: { engine } } })
            }}
            className="bg-secondary border border-border rounded px-2 py-1 text-xs w-24"
          >
            {TTS_ENGINE_OPTIONS_ALL
              .filter(o => o.value !== 'voicevox' || voicevoxInstalled)
              .map(o => (
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
            console.log('[Settings] TTS voice change', voice)
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

      {/* Row 5: Translation — device + provider */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Languages className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">Translate</span>
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.translation.device}
            onChange={(d) => {
              console.log('[Settings] Translation device change', d)
              settings.updateTranslation({ device: d })
              sendMessage({ type: 'update_settings', payload: { translation: { device: d } } })
              restartForDevice()
            }}
          />
          <select
            value={settings.translation.provider}
            onChange={(e) => {
              const provider = e.target.value
              console.log('[Settings] Translation provider change (quick)', provider)
              settings.updateTranslation({ provider: provider as 'local' | 'free' | 'deepl' | 'google' })
              sendMessage({ type: 'update_settings', payload: { translation: { provider } } })
            }}
            className="bg-secondary border border-border rounded px-2 py-1 text-xs w-24"
          >
            <option value="free">Free</option>
            <option value="local">Local</option>
            <option value="deepl">DeepL</option>
            <option value="google">Google</option>
          </select>
        </div>
      </div>

      {/* Row 6: AI Assistant */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">AI</span>
          {settings.ai.provider === 'local' && settings.ai.localModel ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">loaded</span>
          ) : settings.ai.provider === 'local' && !settings.ai.localModel ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">no model</span>
          ) : settings.ai.provider !== 'local' && settings.ai.enabled ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">{settings.ai.provider}</span>
          ) : (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">off</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.ai.device}
            onChange={(d) => {
              console.log('[Settings] AI device change', d)
              settings.updateAI({ device: d })
              sendMessage({ type: 'update_settings', payload: { ai: { device: d } } })
              restartForDevice()
            }}
          />
          <select
            value={settings.ai.provider}
            onChange={(e) => {
              const provider = e.target.value as AIProvider
              console.log('[Settings] AI provider change', provider)
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

      {/* Row 6b: AI Model — submenu for cloud model or local model name */}
      {settings.ai.provider !== 'local' && CLOUD_MODELS[settings.ai.provider] && (
        <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/20 ml-4 min-h-[40px]">
          <span className="text-xs text-muted-foreground">Model</span>
          <select
            value={settings.ai.cloudModels?.[settings.ai.provider] || CLOUD_MODELS[settings.ai.provider][0]?.value}
            onChange={(e) => {
              const model = e.target.value
              console.log('[Settings] AI cloud model change (quick)', model)
              settings.updateAI({ cloudModels: { ...settings.ai.cloudModels, [settings.ai.provider]: model } })
              sendMessage({ type: 'update_settings', payload: { ai: { cloud_model: model, provider: settings.ai.provider } } })
            }}
            className="bg-secondary border border-border rounded px-2 py-1 text-xs max-w-[200px]"
          >
            {CLOUD_MODELS[settings.ai.provider].map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>
      )}
      {settings.ai.provider === 'local' && (
        <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/20 ml-4 min-h-[40px]">
          <span className="text-xs text-muted-foreground">Model</span>
          <div className="flex items-center gap-1.5">
            <span className="text-xs truncate max-w-[160px]">
              {settings.ai.localModel
                ? settings.ai.localModel.replace(/\\/g, '/').split('/').pop()?.replace(/\.gguf$/i, '') || settings.ai.localModel
                : 'None loaded'}
            </span>
            {settings.ai.localModel && (
              <button
                onClick={() => {
                  console.log('[Settings] Quick unload LLM')
                  sendMessage({ type: 'unload_llm' })
                }}
                className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-secondary hover:bg-destructive/20 hover:text-destructive transition-colors border border-border shrink-0"
                title="Unload model"
              >
                Unload
              </button>
            )}
          </div>
        </div>
      )}

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
              console.log('[Settings] RVC device change', d)
              settings.updateRVC({ rvcDevice: d })
              sendMessage({ type: 'rvc_set_device', payload: { device: d } })
              restartForDevice()
            }}
          />
          <button
            onClick={() => {
              console.log('[Settings] RVC Mic button clicked', { isRvcModelLoaded, isMicRvcActive })
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
              console.log('[Settings] RVC TTS button clicked', { isRvcModelLoaded, wasEnabled: settings.rvc.enabled })
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

      {/* Row 8: VR Translation */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/30">
        <div className="flex items-center gap-2">
          <ScanText className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm">VRT</span>
          <Switch
            checked={settings.ocr.enabled}
            onCheckedChange={(v) => {
              console.log('[Settings] VRT quick toggle', v)
              settings.updateOCR({ enabled: v })
              sendMessage({ type: 'update_settings', payload: { ocr: { enabled: v } } })
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <DeviceToggle
            device={settings.ocr.device}
            onChange={(d) => {
              console.log('[Settings] VRT device change', d)
              settings.updateOCR({ device: d })
              sendMessage({ type: 'update_settings', payload: { ocr: { device: d } } })
            }}
          />
          <div className="flex items-center gap-0.5 bg-secondary/60 rounded p-0.5">
            <button
              onClick={() => {
                console.log('[Settings] VRT mode → Manual')
                settings.updateOCR({ mode: 'manual' })
                sendMessage({ type: 'update_settings', payload: { ocr: { mode: 'manual' } } })
              }}
              className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
                settings.ocr.mode === 'manual'
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-secondary/80 text-muted-foreground'
              }`}
            >
              Manual
            </button>
            <button
              onClick={() => {
                console.log('[Settings] VRT mode → Auto')
                settings.updateOCR({ mode: 'automatic' })
                sendMessage({ type: 'update_settings', payload: { ocr: { mode: 'automatic' } } })
              }}
              className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
                settings.ocr.mode === 'automatic'
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-secondary/80 text-muted-foreground'
              }`}
            >
              Auto
            </button>
          </div>
        </div>
      </div>
      {/* VRT Interval */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/20 ml-4">
        <span className="text-xs text-muted-foreground">Interval</span>
        <div className="flex items-center gap-1">
          {[1, 2, 3, 5, 10].map(s => (
            <button
              key={s}
              disabled={settings.ocr.mode !== 'automatic'}
              onClick={() => {
                console.log('[Settings] VRT interval change', s)
                settings.updateOCR({ interval: s })
                sendMessage({ type: 'update_settings', payload: { ocr: { interval: s } } })
              }}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                settings.ocr.mode !== 'automatic'
                  ? 'opacity-40 cursor-not-allowed bg-secondary text-muted-foreground'
                  : settings.ocr.interval === s
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary hover:bg-secondary/80 text-muted-foreground'
              }`}
            >
              {s}s
            </button>
          ))}
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
    console.log('[Settings] Clear cache clicked')
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
            onClick={() => { console.log('[Settings] Navigate to page', id); onNavigate(id) }}
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
                  console.log('[Settings] Menu position change', order[(idx + 1) % order.length])
                  settings.setMenuPosition(order[(idx + 1) % order.length])
                }}
                className="text-xs font-medium px-2 py-1 rounded bg-secondary hover:bg-secondary/80 transition-colors"
              >
                {settings.menuPosition.charAt(0).toUpperCase() + settings.menuPosition.slice(1)}
              </button>
              <button
                onClick={() => { const v = settings.menuAlignment === 'center' ? 'start' : 'center'; console.log('[Settings] Menu alignment change', v); settings.setMenuAlignment(v) }}
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
  { id: 'whisper-tiny', name: 'Tiny', size: '75 MB', description: 'Fastest, lowest accuracy' },
  { id: 'whisper-base', name: 'Base', size: '145 MB', description: 'Good balance of speed and accuracy' },
  { id: 'whisper-small', name: 'Small', size: '488 MB', description: 'Better accuracy, moderate speed' },
  { id: 'whisper-medium', name: 'Medium', size: '1.5 GB', description: 'High accuracy, slower on CPU' },
  { id: 'whisper-large-v2', name: 'Large v2', size: '3.1 GB', description: 'Very high accuracy, needs GPU' },
  { id: 'whisper-large-v3', name: 'Large v3', size: '3.1 GB', description: 'Latest large model, best accuracy' },
  { id: 'whisper-large-v3-turbo', name: 'Large v3 Turbo', size: '1.6 GB', description: 'Near-large accuracy, much faster' },
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
      className={`w-full text-left p-3 rounded-lg border transition-all relative overflow-hidden ${
        isCurrent
          ? isLoaded
            ? 'border-green-600/50'
            : 'border-primary/50'
          : 'bg-secondary border-border hover:border-primary/30'
      } ${isLoading ? 'opacity-70' : ''}`}
    >
      <div className="flex items-center justify-between relative z-10">
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
      {/* Download/loading progress — green background fill like Features page */}
      {(isCurrent && (isLoading || isLoaded)) && (
        <div
          className="absolute inset-0 rounded-lg transition-all duration-500"
          style={{
            background: isLoaded
              ? 'rgba(40, 120, 60, 0.3)'
              : 'rgba(40, 120, 60, 0.2)',
            width: isLoaded
              ? '100%'
              : isDownloading
              ? `${downloadProgress}%`
              : '100%',
          }}
        />
      )}
      {isCurrent && isLoading && !isDownloading && (
        <div
          className="absolute inset-0 rounded-lg animate-pulse"
          style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(80,180,100,0.08) 50%, transparent 100%)' }}
        />
      )}
    </button>
  )
}

function ModelsSettings() {
  const { stt, updateSTT } = useSettingsStore()
  const { loadModel, updateSettings, status, sendMessage, lastMessage } = useBackend()
  const modelStore = useModelStore()
  const [loadingModelId, setLoadingModelId] = useState<string | null>(null)
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
  }, [modelStore.models])

  const handleSelectSTTModel = (modelId: string) => {
    console.log('[Settings] Select STT model', modelId)
    updateSTT({ model: modelId })
    setLoadingModelId(modelId)
    loadModel('stt', modelId)
  }

  const handleDeviceChange = (device: ComputeDevice) => {
    console.log('[Settings] STT device change', device)
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

  // GPU status from backend status
  const backendGpu = (status as unknown as Record<string, unknown>)?.gpu as GpuInfo | undefined
  const gpu = gpuInfo || backendGpu

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Speech Recognition</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Manage Whisper speech recognition models. Larger models are more accurate but slower.
          Models download automatically on first use.
        </p>
      </div>

      {/* Enable/Disable Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable Speech Recognition</Label>
          <p className="text-xs text-muted-foreground">
            Transcribe your voice to text
          </p>
        </div>
        <Switch
          checked={stt.enabled}
          onCheckedChange={(checked) => {
            console.log('[Settings] STT enabled toggle', checked)
            updateSTT({ enabled: checked })
            updateSettings({ stt: { enabled: checked } })
          }}
        />
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
      {gpu && !gpu.available && gpu.name === undefined && (
        <div className="rounded-lg bg-secondary/50 border border-border p-3">
          <p className="text-xs text-muted-foreground">
            GPU info loading... Models will use the selected compute device.
          </p>
        </div>
      )}
      {gpu && !gpu.available && gpu.name !== undefined && (
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

      {/* Device Selection */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>STT Compute Device</Label>
          <DeviceToggle device={stt.device} onChange={handleDeviceChange} />
        </div>
        <p className="text-xs text-muted-foreground">
          Controls whether Whisper runs on CPU or GPU.
        </p>
      </div>

      {/* Info Box */}
      <div className="rounded-lg bg-secondary p-4 text-sm">
        <p className="font-medium mb-2">About Whisper Models</p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
          <li>Models download automatically on first use (~1-5 min)</li>
          <li>Larger models need more RAM/VRAM but give better accuracy</li>
          <li><strong>Tiny/Base:</strong> Best for real-time, low latency</li>
          <li><strong>Small/Medium:</strong> Good accuracy for most use cases</li>
          <li><strong>Large v3 Turbo:</strong> Near-large accuracy at half the size</li>
          <li><strong>Large v3:</strong> Best accuracy, needs GPU for real-time</li>
        </ul>
      </div>
    </div>
  )
}

const TRANSLATION_PROVIDERS = [
  { value: 'free', label: 'Free Translation', description: 'MyMemory & other free APIs, no API key required', online: true, badge: 'Free' },
  { value: 'local', label: 'Local NLLB', description: 'Fully offline, downloads a local model', online: false, badge: 'Local' },
  { value: 'deepl', label: 'DeepL', description: 'High-quality cloud translation, API key required', online: true, badge: 'Cloud' },
  { value: 'google', label: 'Google Cloud', description: 'Google Cloud Translation, API key required', online: true, badge: 'Cloud' },
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
    console.log('[Settings] Toggle translation', checked)
    updateTranslation({ enabled: checked })
    if (checked && !isCloud) {
      setLoadingModel(true)
      loadModel('translation', translation.model)
    }
  }

  const handleProviderChange = (value: string) => {
    console.log('[Settings] Translation provider change', value)
    updateTranslation({ provider: value as 'local' | 'free' | 'deepl' | 'google' })
    updateSettings({ translation: { provider: value } })
    // If switching to local and translation is enabled, load the model
    if (value === 'local' && translation.enabled) {
      setLoadingModel(true)
      loadModel('translation', translation.model)
    }
  }

  const handleModelChange = (value: string) => {
    console.log('[Settings] Translation model change', value)
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
        <div className="space-y-2">
          {TRANSLATION_PROVIDERS.map((provider) => {
            const isSelected = translation.provider === provider.value
            return (
              <button
                key={provider.value}
                onClick={() => handleProviderChange(provider.value)}
                disabled={!translation.enabled}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isSelected
                    ? 'bg-primary/10 border-primary'
                    : 'bg-secondary border-border hover:border-primary/30'
                } ${!translation.enabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{provider.label}</p>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        provider.online
                          ? 'bg-blue-500/10 text-blue-500'
                          : 'bg-green-500/10 text-green-500'
                      }`}>
                        {provider.badge}
                      </span>
                      {isSelected && (
                        <span className="flex items-center gap-1 text-xs text-green-500">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{provider.description}</p>
                  </div>
                  {provider.online ? (
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

      {/* Model Selection - only for local provider, shown as cards */}
      {!isCloud && (
        <div className="space-y-2">
          <Label>Translation Model (NLLB)</Label>
          <div className="space-y-2">
            {TRANSLATION_MODELS.map((model) => {
              const isActive = translation.model === model.value
              return (
                <button
                  key={model.value}
                  onClick={() => {
                    console.log('[Settings] Translation model card click', model.value)
                    handleModelChange(model.value)
                  }}
                  disabled={!translation.enabled || loadingModel}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    isActive
                      ? 'bg-primary/10 border-primary'
                      : 'bg-secondary border-border hover:border-primary/30'
                  } ${(!translation.enabled || loadingModel) ? 'opacity-70' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{model.label}</span>
                    {isActive && !loadingModel && (
                      <span className="flex items-center gap-1 text-xs text-green-500">
                        <Check className="w-3 h-3" /> Active
                      </span>
                    )}
                    {isActive && loadingModel && (
                      <span className="flex items-center gap-1 text-xs text-primary">
                        <Loader2 className="w-3 h-3 animate-spin" /> Loading...
                      </span>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
          {loadingModel && (
            <div className="flex items-center gap-2 text-xs text-primary">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Loading model... (first time may download ~1-3 GB)</span>
            </div>
          )}
        </div>
      )}

      {/* Translation Compute Device */}
      {!isCloud && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Translation Compute Device</Label>
            <DeviceToggle
              device={translation.device}
              onChange={(d) => {
                console.log('[Settings] Translation device change', d)
                updateTranslation({ device: d })
                updateSettings({ translation: { device: d } })
              }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Controls whether NLLB runs on CPU or GPU.
          </p>
        </div>
      )}

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
  const voicevoxInstalled = useFeaturesStore((s) => s.voicevoxInstalled)

  const [voices, setVoices] = useState<TTSVoice[]>([])
  const [outputDevices, setOutputDevices] = useState<TTSOutputDevice[]>([])
  const isSpeaking = useChatStore((s) => s.isSpeaking)
  const [testText, setTestText] = useState('Hello, this is a test of the text to speech voice.')
  const [voicevoxUrl, setVoicevoxUrl] = useState(tts.voicevoxUrl || 'http://localhost:50021')
  const [voicevoxConnected, setVoicevoxConnected] = useState<boolean | null>(null)
  const [voicevoxTesting, setVoicevoxTesting] = useState(false)
  const [voicevoxFetchingVoices, setVoicevoxFetchingVoices] = useState(false)

  // VOICEVOX Engine setup state
  const setVoicevoxInstalled = useFeaturesStore((s) => s.setVoicevoxInstalled)
  const [voicevoxEngineRunning, setVoicevoxEngineRunning] = useState(false)
  const [voicevoxSetupProgress, setVoicevoxSetupProgress] = useState<{
    stage: string; progress: number; detail: string
  } | null>(null)
  const [voicevoxInstallPath, setVoicevoxInstallPath] = useState('')

  // Fetch voices when engine changes or WebSocket (re)connects
  useEffect(() => {
    if (!connected) return
    if (tts.engine === 'voicevox') {
      // Use VOICEVOX-specific endpoint that includes icons
      sendMessage({ type: 'fetch_voicevox_voices' })
    } else {
      getTTSVoices(tts.engine)
    }
    getTTSOutputDevices()
  }, [tts.engine, connected, getTTSVoices, getTTSOutputDevices, sendMessage])

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
    console.log('[Settings] TTS engine change', engineId)
    // Save current voice for the old engine before switching
    const voicePerEngine = { ...(tts.voicePerEngine ?? {}), [tts.engine]: tts.voice }
    updateTTS({ engine: engineId as typeof tts.engine, voicePerEngine })
    updateSettings({ tts: { engine: engineId } })
  }

  const handleVoiceChange = (voiceId: string) => {
    console.log('[Settings] TTS voice change', voiceId)
    const voicePerEngine = { ...(tts.voicePerEngine ?? {}), [tts.engine]: voiceId }
    updateTTS({ voice: voiceId, voicePerEngine })
    updateSettings({ tts: { voice: voiceId } })
  }

  const handleSpeedChange = (speed: number) => {
    console.log('[Settings] TTS speed change', speed)
    updateTTS({ speed })
    updateSettings({ tts: { speed } })
  }

  const handlePitchChange = (pitch: number) => {
    console.log('[Settings] TTS pitch change', pitch)
    updateTTS({ pitch })
    updateSettings({ tts: { pitch } })
  }

  const handleVolumeChange = (volume: number) => {
    console.log('[Settings] TTS volume change', volume)
    updateTTS({ volume })
    updateSettings({ tts: { volume } })
  }

  const handleTestVoice = () => {
    console.log('[Settings] Test voice clicked', { isSpeaking })
    if (isSpeaking) {
      stopSpeaking()
    } else {
      speak(testText)
    }
  }

  // Deduplicate voices by id
  const uniqueVoices = voices.filter((v, i, arr) => arr.findIndex(x => x.id === v.id) === i)

  // Build voice options grouped by language
  const voiceGroups = uniqueVoices.reduce<Record<string, TTSVoice[]>>((groups, voice) => {
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
  const voiceOptions = uniqueVoices.map(v => ({
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
            console.log('[Settings] TTS page enabled toggle', checked)
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
            const isVoicevoxUnavailable = engine.id === 'voicevox' && !voicevoxInstalled
            const isDisabled = !tts.enabled || isVoicevoxUnavailable
            return (
              <button
                key={engine.id}
                onClick={() => !isVoicevoxUnavailable && handleEngineChange(engine.id)}
                disabled={isDisabled}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isSelected
                    ? 'bg-primary/10 border-primary'
                    : 'bg-secondary border-border hover:border-primary/30'
                } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
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
                      {isSelected && !isVoicevoxUnavailable && (
                        <span className="flex items-center gap-1 text-xs text-green-500">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      )}
                      {isVoicevoxUnavailable && (
                        <span className="text-xs text-yellow-500/70">Install in Features settings</span>
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
                  console.log('[Settings] Test VOICEVOX connection', voicevoxUrl)
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
                console.log('[Settings] VOICEVOX English phonetic toggle', enabled)
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
        {tts.engine === 'voicevox' && uniqueVoices.length > 0 && uniqueVoices.some(v => v.icon) ? (
          <div className="space-y-2">
            <div className="grid grid-cols-4 gap-2 max-h-[320px] overflow-y-auto pr-1">
              {uniqueVoices.map((voice) => {
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
            <p className="text-xs text-muted-foreground">{uniqueVoices.length} voices available</p>
          </div>
        ) : uniqueVoices.length > 0 ? (
          /* Standard dropdown for non-VOICEVOX engines or when no icons available */
          <div>
            <Select
              value={tts.voice}
              onValueChange={handleVoiceChange}
              options={voiceOptions}
              groups={voiceSelectGroups.length > 1 ? voiceSelectGroups : undefined}
              disabled={!tts.enabled}
            />
            <p className="text-xs text-muted-foreground mt-1">{uniqueVoices.length} voices available</p>
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
            variant="outline"
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

      {/* Output Device is configured in Audio settings page */}

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
  { value: 'free', label: 'Free (Pollinations)', description: 'No API key needed, works out of the box', online: true, badge: 'Free' },
  { value: 'local', label: 'Local LLM', description: 'Run AI models on your machine, fully offline', online: false, badge: 'Local' },
  { value: 'groq', label: 'Groq', description: 'Fast cloud inference, free tier available', online: true, badge: 'Cloud' },
  { value: 'openai', label: 'OpenAI', description: 'GPT-4o, GPT-3.5 Turbo', online: true, badge: 'Cloud' },
  { value: 'anthropic', label: 'Anthropic', description: 'Claude models', online: true, badge: 'Cloud' },
  { value: 'google', label: 'Google', description: 'Gemini models', online: true, badge: 'Cloud' },
]

const CLOUD_MODELS: Record<string, { value: string; label: string; badge?: string }[]> = {
  openai: [
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', badge: 'Fast' },
    { value: 'gpt-4o', label: 'GPT-4o', badge: 'Quality' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', badge: 'Fastest' },
  ],
  anthropic: [
    { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4', badge: 'Quality' },
    { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku', badge: 'Fast' },
  ],
  google: [
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash', badge: 'Fast' },
    { value: 'gemini-2.0-pro', label: 'Gemini 2.0 Pro', badge: 'Quality' },
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  ],
  groq: [
    { value: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B', badge: 'Fast' },
    { value: 'llama-3.1-70b-versatile', label: 'Llama 3.1 70B', badge: 'Quality' },
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
  const { updateSettings, getLocalModels, loadLocalModel, lastMessage, setModelsDirectory, getModelsDirectory, browseLLMFolder, browseLLMModel, getLLMStatus, unloadLLM } = useBackend()
  const [localModels, setLocalModels] = useState<LocalModel[]>([])
  const [loadingModel, setLoadingModel] = useState<string | null>(null)
  const [modelError, setModelError] = useState<string | null>(null)
  const [modelsDir, setModelsDir] = useState<string>('')
  const [customDir, setCustomDir] = useState<string>(ai.modelsDirectory || '')

  // Loaded model from persisted store (survives page nav + restart)
  const loadedModel = ai.localModel || null

  // Fetch local models, directory, and LLM status on mount + rescan periodically
  useEffect(() => {
    if (ai.provider === 'local') {
      console.log('[Settings] AI local provider active — fetching models, directory, and LLM status')
      getLocalModels()
      getModelsDirectory()
      getLLMStatus()
      // Rescan every 5 seconds so newly added models show up quickly
      const interval = setInterval(() => {
        getLocalModels()
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [ai.provider, getLocalModels, getModelsDirectory, getLLMStatus])

  // Handle backend messages
  useEffect(() => {
    if (lastMessage?.type === 'local_models') {
      setLocalModels(lastMessage.payload.models as LocalModel[])
    } else if (lastMessage?.type === 'model_loaded') {
      const payload = lastMessage.payload as { type?: string; id?: string }
      if (payload.type === 'llm') {
        console.log('[Settings] LLM model loaded:', payload.id)
        setLoadingModel(null)
        setModelError(null)
        // Persist loaded model path in store (survives page nav + restart)
        updateAI({ localModel: payload.id || '' })
      }
    } else if (lastMessage?.type === 'model_error') {
      const payload = lastMessage.payload as { type?: string; error?: string }
      if (payload.type === 'llm') {
        console.log('[Settings] LLM model error:', payload.error)
        setLoadingModel(null)
        setModelError(payload.error || 'Failed to load model')
      }
    } else if (lastMessage?.type === 'llm_status') {
      const payload = lastMessage.payload as { loaded?: boolean; model?: string; model_path?: string }
      console.log('[Settings] LLM status:', payload)
      if (payload.loaded && payload.model_path) {
        updateAI({ localModel: payload.model_path })
        setLoadingModel(null)
        setModelError(null)
      } else if (!payload.loaded && ai.localModel && !loadingModel) {
        // Backend says not loaded but we have a saved model — auto-reload it (only if not already loading)
        console.log('[Settings] LLM not loaded on backend, auto-reloading:', ai.localModel)
        setLoadingModel(ai.localModel)
        loadLocalModel(ai.localModel)
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
        console.log('[Settings] Models directory set to', payload.path, 'found', payload.models?.length, 'models')
        setModelsDir(payload.path || '')
        setCustomDir(payload.path || '')
        setLocalModels(payload.models || [])
        updateAI({ modelsDirectory: payload.path || '' })
      }
    } else if (lastMessage?.type === 'llm_unloaded') {
      const payload = lastMessage.payload as { success?: boolean }
      if (payload.success) {
        console.log('[Settings] LLM unloaded successfully')
        updateAI({ localModel: '' })
        setLoadingModel(null)
        setModelError(null)
      }
    } else if (lastMessage?.type === 'llm_model_browsed') {
      const payload = lastMessage.payload as { path?: string; directory?: string; models?: LocalModel[] }
      console.log('[Settings] LLM model browsed:', payload.path, 'in dir:', payload.directory)
      if (payload.directory) {
        setModelsDir(payload.directory)
        setCustomDir(payload.directory)
        updateAI({ modelsDirectory: payload.directory })
      }
      if (payload.models) {
        setLocalModels(payload.models)
      }
    }
  }, [lastMessage, customDir, updateAI, ai.localModel, loadLocalModel])

  // Sync provider change to backend
  const handleProviderChange = (provider: typeof ai.provider) => {
    console.log('[Settings] AI provider change', provider)
    updateAI({ provider })
    updateSettings({ ai: { provider } })
  }

  const handleLoadModel = (model: LocalModel) => {
    console.log('[Settings] Load local model', model.name)
    if (!model.downloaded || !model.path) return
    setLoadingModel(model.path)
    setModelError(null)
    loadLocalModel(model.path)
  }

  const handleSetModelsDirectory = () => {
    console.log('[Settings] Set models directory', customDir.trim())
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
          onCheckedChange={(checked) => { console.log('[Settings] AI enabled toggle', checked); updateAI({ enabled: checked }) }}
        />
      </div>

      {/* Everything below toggle is disabled when AI is off */}
      <div className={!ai.enabled ? 'opacity-50 pointer-events-none' : ''}>

      {/* Keyword */}
      <div className="space-y-2">
        <Label>Activation Keyword</Label>
        <input
          type="text"
          value={ai.keyword}
          onChange={(e) => { console.log('[Settings] AI keyword change', e.target.value); updateAI({ keyword: e.target.value }); updateSettings({ ai: { keyword: e.target.value } }) }}
          placeholder="Jarvis"
          className="w-full bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
        <p className="text-xs text-muted-foreground">
          Say this word before your question (e.g., &quot;{ai.keyword}, what&apos;s the weather?&quot;)
        </p>
      </div>

      {/* Provider Selection */}
      <div className="space-y-2">
        <Label>AI Provider</Label>
        <div className="space-y-2">
          {AI_PROVIDERS.map((provider) => {
            const isSelected = ai.provider === provider.value
            return (
              <button
                key={provider.value}
                onClick={() => handleProviderChange(provider.value as typeof ai.provider)}
                disabled={!ai.enabled}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isSelected
                    ? 'bg-primary/10 border-primary'
                    : 'bg-secondary border-border hover:border-primary/30'
                } ${!ai.enabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{provider.label}</p>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        provider.online
                          ? 'bg-blue-500/10 text-blue-500'
                          : 'bg-green-500/10 text-green-500'
                      }`}>
                        {provider.badge}
                      </span>
                      {isSelected && (
                        <span className="flex items-center gap-1 text-xs text-green-500">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{provider.description}</p>
                  </div>
                  {provider.online ? (
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
            <div className="flex items-center justify-between">
              <Label>Available Models</Label>
              <button
                onClick={() => { console.log('[Settings] Browse LLM model file'); browseLLMModel() }}
                className="flex items-center gap-1.5 h-7 px-2.5 rounded-md bg-secondary text-secondary-foreground text-xs font-medium hover:bg-secondary/80 transition-colors"
                title="Browse for a .gguf model file"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                Browse .gguf
              </button>
            </div>
            <div className="space-y-2">
              {/* No models warning / loading state */}
              {localModels.filter(m => m.downloaded).length === 0 && (
                ai.localModel ? (
                  <div className="rounded-lg bg-secondary/50 border border-border p-4 text-sm">
                    <p className="font-medium text-muted-foreground mb-1">Loading model list...</p>
                    <p className="text-muted-foreground text-xs">
                      Loading a local LLM can take 10-30 seconds depending on model size.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/30 p-4 text-sm">
                    <p className="font-medium text-yellow-500 mb-1">No Models Found</p>
                    <p className="text-muted-foreground text-xs">
                      Download a .gguf model from the links below, or use Browse to select one from your computer.
                    </p>
                  </div>
                )
              )}

              {/* Downloaded model cards — same style as RVC cards */}
              {localModels.filter(m => m.downloaded).map((model) => {
                const isLoaded = loadedModel === model.path
                const isThisLoading = loadingModel === model.path
                return (
                  <div
                    key={model.name}
                    className={`relative overflow-hidden rounded-lg border transition-colors ${
                      isLoaded
                        ? 'border-green-500/50'
                        : 'bg-secondary/30 border-transparent hover:bg-secondary/50'
                    }`}
                  >
                    {isLoaded && (
                      <div className="absolute inset-0 rounded-lg" style={{ background: 'rgba(40, 180, 80, 0.08)' }} />
                    )}
                    <div className="relative flex items-center justify-between p-2.5">
                      <button
                        onClick={() => !isLoaded && !isThisLoading && handleLoadModel(model)}
                        disabled={isLoaded || loadingModel !== null}
                        className="flex-1 text-left min-w-0"
                      >
                        <div className="flex items-center gap-2">
                          {isThisLoading && <Loader2 className="w-3.5 h-3.5 text-primary animate-spin shrink-0" />}
                          <span className={`text-sm truncate ${isLoaded ? 'text-foreground' : 'text-muted-foreground'}`}>{model.name}</span>
                          <span className="text-[10px] text-muted-foreground shrink-0">{formatSize(model.size)}</span>
                          {isThisLoading && (
                            <span className="text-[10px] text-muted-foreground">Loading...</span>
                          )}
                        </div>
                      </button>
                      {isLoaded && (
                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                          <Check className="w-4 h-4 text-green-500" />
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              console.log('[Settings] Unload LLM model')
                              unloadLLM()
                            }}
                            className="px-2 py-0.5 rounded text-[10px] font-medium bg-secondary hover:bg-destructive/20 hover:text-destructive transition-colors border border-border"
                            title="Unload model"
                          >
                            Unload
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}

              {/* Model error message */}
              {modelError && (
                <div className="flex items-center gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/30">
                  <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
                  <span className="text-sm text-red-400">{modelError}</span>
                </div>
              )}

              {/* Recommended models to download — hide ones already downloaded */}
              {localModels.filter(m => !m.downloaded).length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-muted-foreground mb-2">Recommended models to download:</p>
                  {localModels.filter(m => !m.downloaded).map((model) => (
                    <a
                      key={model.name}
                      href={model.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 border border-border/50 mb-2 hover:border-primary/30 transition-colors cursor-pointer"
                    >
                      <div>
                        <p className="font-medium text-sm">{model.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {model.size} {model.description && `- ${model.description}`}
                        </p>
                      </div>
                      <span className="flex items-center gap-1 text-xs text-primary">
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Cloud Model Selection - show when non-local provider is selected */}
      {ai.provider !== 'local' && CLOUD_MODELS[ai.provider] && (
        <div className="space-y-2">
          <Label>Model</Label>
          <div className="grid grid-cols-2 gap-2">
            {CLOUD_MODELS[ai.provider].map((model) => {
              const selected = (ai.cloudModels?.[ai.provider] || CLOUD_MODELS[ai.provider][0].value) === model.value
              return (
                <button
                  key={model.value}
                  onClick={() => {
                    console.log('[Settings] AI cloud model change', model.value)
                    updateAI({ cloudModels: { ...ai.cloudModels, [ai.provider]: model.value } })
                    updateSettings({ ai: { cloud_model: model.value, provider: ai.provider } })
                  }}
                  disabled={!ai.enabled}
                  className={`p-3 rounded-lg border text-left transition-colors ${
                    selected
                      ? 'bg-green-500/10 border-green-500/50'
                      : 'bg-secondary border-border hover:border-primary/50'
                  } ${!ai.enabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{model.label}</p>
                    <div className="flex items-center gap-1.5">
                      {selected && (
                        <span className="flex items-center gap-1 text-xs text-green-500">
                          <Check className="w-3 h-3" />
                        </span>
                      )}
                      {model.badge && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          selected ? 'bg-green-500/20 text-green-400' : 'bg-muted text-muted-foreground'
                        }`}>
                          {model.badge}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
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
          onCheckedChange={(checked) => { console.log('[Settings] AI speak responses toggle', checked); updateAI({ speakResponses: checked }) }}
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

      {/* Max Response Length end */}

      </div>{/* End disabled wrapper */}

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
  const { vrOverlay, updateVROverlay, ocr, updateOCR, translation } = useSettingsStore()
  const { updateSettings, sendMessage, status } = useBackend()
  const canvasRef = useRef<HTMLDivElement>(null)
  const [interaction, setInteraction] = useState<{
    type: 'drag' | 'resize'
    element: 'notification' | 'log' | 'ocrButton' | 'ocrRegion'
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

        if (interaction.element === 'ocrButton') {
          // OCR button: update ocr settings
          const ocrTracking = tracking
          const updated = { ocrButton: { ...ocr.ocrButton, x: Math.round(newX * 100) / 100, y: Math.round(newY * 100) / 100, tracking: ocrTracking } }
          console.log('[Settings] OCR button drag', updated)
          updateOCR(updated)
          updateSettings({ ocr: updated })
        } else if (interaction.element === 'ocrRegion') {
          const updated = { captureRegion: { ...ocr.captureRegion, x: Math.round(newX * 100) / 100, y: Math.round(newY * 100) / 100 } }
          console.log('[Settings] OCR region drag', updated)
          updateOCR(updated)
          updateSettings({ ocr: updated })
        } else {
          const trackingKey = interaction.element === 'notification' ? 'notificationTracking' : 'messageLogTracking'
          if (interaction.element === 'notification') {
            handleUpdate({ notificationX: Math.round(newX * 100) / 100, notificationY: Math.round(newY * 100) / 100, [trackingKey]: tracking })
          } else {
            handleUpdate({ messageLogX: Math.round(newX * 100) / 100, messageLogY: Math.round(newY * 100) / 100, [trackingKey]: tracking })
          }
        }
      } else {
        // Resize
        if (interaction.element === 'ocrButton') {
          // OCR button resize: only width
          const dw = (interaction.corner === 'tl' || interaction.corner === 'bl') ? -dx : dx
          const newW = Math.max(0.03, Math.min(0.15, interaction.startW + dw))
          const updated = { ocrButton: { ...ocr.ocrButton, width: Math.round(newW * 100) / 100 } }
          updateOCR(updated)
          updateSettings({ ocr: updated })
        } else if (interaction.element === 'ocrRegion') {
          const c = interaction.corner || 'br'
          const dw = (c === 'tl' || c === 'bl') ? -dx : dx
          const dh = (c === 'tl' || c === 'tr') ? dy : -dy
          const newW = Math.max(0.1, Math.min(1.5, interaction.startW + dw))
          const newH = Math.max(0.05, Math.min(1.0, interaction.startH + dh))
          const wDelta = newW - interaction.startW
          const hDelta = newH - interaction.startH
          const xShift = (c === 'tl' || c === 'bl') ? -wDelta / 2 : wDelta / 2
          const yShift = (c === 'tl' || c === 'tr') ? hDelta / 2 : -hDelta / 2
          const newX = Math.round((interaction.startX + xShift) * 100) / 100
          const newY = Math.round((interaction.startY + yShift) * 100) / 100
          const updated = { captureRegion: { ...ocr.captureRegion, x: newX, y: newY, width: Math.round(newW * 100) / 100, height: Math.round(newH * 100) / 100 } }
          updateOCR(updated)
          updateSettings({ ocr: updated })
        } else {
          const isNotif = interaction.element === 'notification'
          const maxW = isNotif ? NOTIF_MAX_W : LOG_MAX_W
          const maxH = isNotif ? NOTIF_MAX_H : LOG_MAX_H
          const minW = isNotif ? NOTIF_MIN_W : LOG_MIN_W
          const minH = isNotif ? NOTIF_MIN_H : LOG_MIN_H
          const c = interaction.corner || 'br'
          const dw = (c === 'tl' || c === 'bl') ? -dx : dx
          const dh = (c === 'tl' || c === 'tr') ? dy : -dy
          const newW = Math.max(minW, Math.min(maxW, interaction.startW + dw))
          const newH = Math.max(minH, Math.min(maxH, interaction.startH + dh))
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
    }

    const handleMouseUp = () => setInteraction(null)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [interaction, handleUpdate, ocr, updateOCR, updateSettings])

  const startDrag = (element: 'notification' | 'log' | 'ocrButton' | 'ocrRegion', e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    let startX = 0, startY = 0
    if (element === 'notification') { startX = vrOverlay.notificationX; startY = vrOverlay.notificationY }
    else if (element === 'log') { startX = vrOverlay.messageLogX; startY = vrOverlay.messageLogY }
    else if (element === 'ocrButton') { startX = ocr.ocrButton.x; startY = ocr.ocrButton.y }
    else if (element === 'ocrRegion') { startX = ocr.captureRegion.x; startY = ocr.captureRegion.y }
    setInteraction({
      type: 'drag', element,
      startMouseX: e.clientX, startMouseY: e.clientY,
      startX, startY, startW: 0, startH: 0,
    })
  }

  const startResize = (element: 'notification' | 'log' | 'ocrButton' | 'ocrRegion', corner: 'tl' | 'tr' | 'bl' | 'br', e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    let startX = 0, startY = 0, startW = 0, startH = 0
    if (element === 'notification') {
      startX = vrOverlay.notificationX; startY = vrOverlay.notificationY
      startW = vrOverlay.notificationWidth; startH = vrOverlay.notificationHeight
    } else if (element === 'log') {
      startX = vrOverlay.messageLogX; startY = vrOverlay.messageLogY
      startW = vrOverlay.messageLogWidth; startH = vrOverlay.messageLogHeight
    } else if (element === 'ocrButton') {
      startX = ocr.ocrButton.x; startY = ocr.ocrButton.y
      startW = ocr.ocrButton.width; startH = ocr.ocrButton.width // Square
    } else if (element === 'ocrRegion') {
      startX = ocr.captureRegion.x; startY = ocr.captureRegion.y
      startW = ocr.captureRegion.width; startH = ocr.captureRegion.height
    }
    setInteraction({
      type: 'resize', element, corner,
      startMouseX: e.clientX, startMouseY: e.clientY,
      startX, startY, startW, startH,
    })
  }

  const handleResetDefaults = () => {
    console.log('[Settings] VR Overlay reset defaults')
    const defaults: Record<string, unknown> = {
      showOriginalText: true, showTranslatedText: true,
      showAIResponses: true, showListenText: true, showOCRText: true,
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
  const anyOnLeftHand = vrOverlay.notificationTracking === 'left_hand' || vrOverlay.messageLogTracking === 'left_hand' || ocr.ocrButton.tracking === 'left_hand'
  const anyOnRightHand = vrOverlay.notificationTracking === 'right_hand' || vrOverlay.messageLogTracking === 'right_hand' || ocr.ocrButton.tracking === 'right_hand'

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

          {/* OCR Capture Region (white/light gray) */}
          {ocr.enabled && (
            <div
              className="absolute border-2 border-white/30 bg-white/10 cursor-move flex items-center justify-center"
              style={{
                left: `${toCanvasX(ocr.captureRegion.x) - toCanvasW(ocr.captureRegion.width) / 2}%`,
                top: `${toCanvasY(ocr.captureRegion.y) - toCanvasH(ocr.captureRegion.height) / 2}%`,
                width: `${toCanvasW(ocr.captureRegion.width)}%`,
                height: `${toCanvasH(ocr.captureRegion.height)}%`,
              }}
              onMouseDown={(e) => startDrag('ocrRegion', e)}
            >
              <span className="text-[9px] text-white/40 pointer-events-none">VRT Region</span>
              <div className="absolute left-0 top-0 w-2.5 h-2.5 cursor-nw-resize bg-cyan-400/60" onMouseDown={(e) => startResize('ocrRegion', 'tl', e)} />
              <div className="absolute right-0 top-0 w-2.5 h-2.5 cursor-ne-resize bg-cyan-400/60" onMouseDown={(e) => startResize('ocrRegion', 'tr', e)} />
              <div className="absolute left-0 bottom-0 w-2.5 h-2.5 cursor-sw-resize bg-cyan-400/60" onMouseDown={(e) => startResize('ocrRegion', 'bl', e)} />
              <div className="absolute right-0 bottom-0 w-2.5 h-2.5 cursor-se-resize bg-cyan-400/60" onMouseDown={(e) => startResize('ocrRegion', 'br', e)} />
            </div>
          )}

          {/* OCR Toggle Button (cyan) */}
          {ocr.enabled && (() => {
            const onHand = ocr.ocrButton.tracking !== 'none'
            return (
              <div
                className={`absolute border-2 cursor-move flex items-center justify-center rounded ${
                  onHand ? 'border-yellow-400 bg-yellow-500/20' : 'border-cyan-400 bg-cyan-500/20'
                }`}
                style={{
                  left: `${toCanvasX(ocr.ocrButton.x) - toCanvasW(ocr.ocrButton.width) / 2}%`,
                  top: `${toCanvasY(ocr.ocrButton.y) - toCanvasW(ocr.ocrButton.width) / 2}%`,
                  width: `${toCanvasW(ocr.ocrButton.width)}%`,
                  height: `${toCanvasW(ocr.ocrButton.width)}%`,
                }}
                onMouseDown={(e) => startDrag('ocrButton', e)}
              >
                <ScanText className="w-3 h-3 text-cyan-300 pointer-events-none" />
                <div className="absolute right-0 bottom-0 w-2.5 h-2.5 cursor-se-resize bg-cyan-400/60" onMouseDown={(e) => startResize('ocrButton', 'br', e)} />
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

        {/* VR Translation */}
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="flex items-center justify-between p-2 bg-secondary/20">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-sm bg-cyan-400" />
              <span className="text-xs font-medium">VR Translation</span>
            </div>
            <Switch checked={ocr.enabled}
              onCheckedChange={(v) => {
                console.log('[Settings] VRT overlay toggle', v)
                updateOCR({ enabled: v })
                sendMessage({ type: 'update_settings', payload: { ocr: { enabled: v } } })
              }} />
          </div>
          {ocr.enabled && (
            <div className="p-2.5 space-y-2.5 border-t border-border">
              {/* Device & Mode */}
              <div className="flex items-center justify-between">
                <Label className="text-xs">Device</Label>
                <DeviceToggle
                  device={ocr.device}
                  onChange={(d) => {
                    console.log('[Settings] VRT device', d)
                    updateOCR({ device: d })
                    sendMessage({ type: 'update_settings', payload: { ocr: { device: d } } })
                  }}
                />
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-xs">Mode</Label>
                <div className="flex items-center gap-0.5 bg-secondary/60 rounded p-0.5">
                  <button
                    onClick={() => {
                      console.log('[Settings] VRT mode → Manual')
                      updateOCR({ mode: 'manual' })
                      sendMessage({ type: 'update_settings', payload: { ocr: { mode: 'manual' } } })
                    }}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
                      ocr.mode === 'manual'
                        ? 'bg-primary text-primary-foreground'
                        : 'hover:bg-secondary/80 text-muted-foreground'
                    }`}
                  >
                    Manual
                  </button>
                  <button
                    onClick={() => {
                      console.log('[Settings] VRT mode → Auto')
                      updateOCR({ mode: 'automatic' })
                      sendMessage({ type: 'update_settings', payload: { ocr: { mode: 'automatic' } } })
                    }}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
                      ocr.mode === 'automatic'
                        ? 'bg-primary text-primary-foreground'
                        : 'hover:bg-secondary/80 text-muted-foreground'
                    }`}
                  >
                    Auto
                  </button>
                </div>
              </div>
              {/* Interval */}
              <div className="flex items-center justify-between">
                <Label className="text-xs">Interval</Label>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 5, 10].map(s => (
                    <button
                      key={s}
                      disabled={ocr.mode !== 'automatic'}
                      onClick={() => {
                        console.log('[Settings] VRT interval', s)
                        updateOCR({ interval: s })
                        sendMessage({ type: 'update_settings', payload: { ocr: { interval: s } } })
                      }}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
                        ocr.mode !== 'automatic'
                          ? 'opacity-40 cursor-not-allowed bg-secondary text-muted-foreground'
                          : ocr.interval === s
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-secondary hover:bg-secondary/80 text-muted-foreground'
                      }`}
                    >
                      {s}s
                    </button>
                  ))}
                </div>
              </div>
              {/* Confidence */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Confidence</Label>
                  <span className="text-[10px] text-muted-foreground font-mono">{ocr.confidence.toFixed(1)}</span>
                </div>
                <input type="range" min={0.1} max={0.9} step={0.1}
                  value={ocr.confidence}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value)
                    updateOCR({ confidence: v })
                    sendMessage({ type: 'update_settings', payload: { ocr: { confidence: v } } })
                  }}
                  className="w-full accent-primary" />
              </div>
              {/* Manual capture button — always visible, greyed when auto */}
              <button
                disabled={ocr.mode !== 'manual'}
                onClick={() => {
                  console.log('[Settings] VRT manual capture')
                  sendMessage({ type: 'ocr_capture' })
                }}
                className={`w-full flex items-center justify-center gap-1.5 p-1.5 rounded text-xs font-medium transition-colors border border-border ${
                  ocr.mode !== 'manual' ? 'opacity-40 cursor-not-allowed bg-secondary text-muted-foreground' : 'bg-secondary hover:bg-secondary/80'
                }`}
              >
                <ScanText className="w-3.5 h-3.5" />
                Capture Now
              </button>
              {/* Languages info */}
              <div className="text-[10px] text-muted-foreground bg-secondary/30 rounded p-2">
                {translation.languagePairs.length > 0
                  ? (() => {
                      const langs = new Set<string>()
                      translation.languagePairs.forEach(p => {
                        const src = LANGUAGES.find(l => l.value === p.sourceLanguage)?.label
                        const tgt = LANGUAGES.find(l => l.value === p.targetLanguage)?.label
                        if (src) langs.add(src)
                        if (tgt) langs.add(tgt)
                      })
                      return Array.from(langs).join(', ')
                    })()
                  : 'No languages configured'}
              </div>
              {/* Controller Bindings */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Controller Bindings</Label>
                  <Switch checked={ocr.controllerBindingEnabled}
                    onCheckedChange={(v) => {
                      console.log('[Settings] VRT controller bindings', v)
                      updateOCR({ controllerBindingEnabled: v })
                      sendMessage({ type: 'update_settings', payload: { ocr: { controllerBindingEnabled: v } } })
                    }} />
                </div>
                <div className={`space-y-1.5 ${!ocr.controllerBindingEnabled ? 'opacity-40 pointer-events-none' : ''}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground">Capture</span>
                      <div className="flex items-center gap-1">
                        {ocr.captureBinding.map((btn, i) => (
                          <select key={i} value={btn}
                            onChange={(e) => {
                              const newBinding = [...ocr.captureBinding]
                              newBinding[i] = e.target.value
                              console.log('[Settings] VRT capture binding', newBinding)
                              updateOCR({ captureBinding: newBinding })
                              sendMessage({ type: 'update_settings', payload: { ocr: { captureBinding: newBinding } } })
                            }}
                            className="bg-secondary border border-border rounded px-1 py-0.5 text-[10px]"
                          >
                            {['left_grip', 'left_trigger', 'left_a', 'left_b', 'left_trackpad',
                              'right_grip', 'right_trigger', 'right_a', 'right_b', 'right_trackpad'].map(v => (
                              <option key={v} value={v}>{v.replace('_', ' ')}</option>
                            ))}
                          </select>
                        ))}
                        <button
                          onClick={() => {
                            if (ocr.captureBinding.length < 3) {
                              const newBinding = [...ocr.captureBinding, 'right_trigger']
                              updateOCR({ captureBinding: newBinding })
                              sendMessage({ type: 'update_settings', payload: { ocr: { captureBinding: newBinding } } })
                            }
                          }}
                          className="px-1 py-0.5 rounded text-[10px] bg-secondary hover:bg-secondary/80 border border-border"
                          title="Add button to combo"
                        >+</button>
                        {ocr.captureBinding.length > 1 && (
                          <button
                            onClick={() => {
                              const newBinding = ocr.captureBinding.slice(0, -1)
                              updateOCR({ captureBinding: newBinding })
                              sendMessage({ type: 'update_settings', payload: { ocr: { captureBinding: newBinding } } })
                            }}
                            className="px-1 py-0.5 rounded text-[10px] bg-secondary hover:bg-secondary/80 border border-border"
                            title="Remove last button"
                          >-</button>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground">Toggle</span>
                      <div className="flex items-center gap-1">
                        {ocr.toggleBinding.map((btn, i) => (
                          <select key={i} value={btn}
                            onChange={(e) => {
                              const newBinding = [...ocr.toggleBinding]
                              newBinding[i] = e.target.value
                              console.log('[Settings] VRT toggle binding', newBinding)
                              updateOCR({ toggleBinding: newBinding })
                              sendMessage({ type: 'update_settings', payload: { ocr: { toggleBinding: newBinding } } })
                            }}
                            className="bg-secondary border border-border rounded px-1 py-0.5 text-[10px]"
                          >
                            {['left_grip', 'left_trigger', 'left_a', 'left_b', 'left_trackpad',
                              'right_grip', 'right_trigger', 'right_a', 'right_b', 'right_trackpad'].map(v => (
                              <option key={v} value={v}>{v.replace('_', ' ')}</option>
                            ))}
                          </select>
                        ))}
                        <button
                          onClick={() => {
                            if (ocr.toggleBinding.length < 3) {
                              const newBinding = [...ocr.toggleBinding, 'left_trigger']
                              updateOCR({ toggleBinding: newBinding })
                              sendMessage({ type: 'update_settings', payload: { ocr: { toggleBinding: newBinding } } })
                            }
                          }}
                          className="px-1 py-0.5 rounded text-[10px] bg-secondary hover:bg-secondary/80 border border-border"
                          title="Add button to combo"
                        >+</button>
                        {ocr.toggleBinding.length > 1 && (
                          <button
                            onClick={() => {
                              const newBinding = ocr.toggleBinding.slice(0, -1)
                              updateOCR({ toggleBinding: newBinding })
                              sendMessage({ type: 'update_settings', payload: { ocr: { toggleBinding: newBinding } } })
                            }}
                            className="px-1 py-0.5 rounded text-[10px] bg-secondary hover:bg-secondary/80 border border-border"
                            title="Remove last button"
                          >-</button>
                        )}
                      </div>
                    </div>
                  </div>
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
            { key: 'showOCRText', label: 'VR Translation', Icon: ScanText },
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
  const { audio, updateAudio, outputProfiles, updateOutputProfile, addOutputProfile, removeOutputProfile } = useSettingsStore()
  const { audioLevel, testMicrophone, stopTestMicrophone, getAudioDevices, updateSettings, lastMessage, sendMessage, connected } = useBackend()

  const [inputDevices, setInputDevices] = useState<AudioDevice[]>([])
  const [outputDevices, setOutputDevices] = useState<AudioDevice[]>([])
  const [isTesting, setIsTesting] = useState(false)
  const [isTestingSpeaker, setIsTestingSpeaker] = useState(false)
  const [isTestingLoopback, setIsTestingLoopback] = useState(false)
  const [loopbackResult, setLoopbackResult] = useState<{ success: boolean; message: string } | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const defaultProfile = outputProfiles.find(p => p.id === 'default') || outputProfiles[0]

  // Fetch audio devices on mount and when connected
  useEffect(() => {
    console.log('[Audio] Requesting audio devices (connected:', connected, ')')
    getAudioDevices()
  }, [getAudioDevices, connected])

  // Listen for audio device responses
  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'audio_devices') {
      const payload = lastMessage.payload as { inputs?: AudioDevice[]; outputs?: AudioDevice[] }
      console.log('[Audio] Received devices:', payload.inputs?.length, 'inputs,', payload.outputs?.length, 'outputs')
      setInputDevices(payload.inputs || [])
      setOutputDevices(payload.outputs || [])
      setIsRefreshing(false)
    } else if (lastMessage.type === 'speaker_test_done') {
      setIsTestingSpeaker(false)
    } else if (lastMessage.type === 'loopback_test_result') {
      const result = lastMessage.payload as { success: boolean; message: string }
      console.log('[Audio] Loopback test result:', result)
      setIsTestingLoopback(false)
      setLoopbackResult(result)
      setTimeout(() => setLoopbackResult(null), 5000)
    }
  }, [lastMessage])

  const handleRefreshDevices = () => {
    console.log('[Settings] Refresh audio devices')
    setIsRefreshing(true)
    getAudioDevices()
    setTimeout(() => setIsRefreshing(false), 3000)
  }

  const handleTestMicrophone = () => {
    console.log('[Settings] Test microphone clicked', { wasTesting: isTesting })
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
    console.log('[Audio] Mic device changed:', value || 'default')
    updateAudio({ microphoneDeviceId: value || null })
    // Backend expects 'input_device' as int or null
    const deviceInt = value ? parseInt(value) : null
    updateSettings({ audio: { input_device: deviceInt } })
  }

  const handleSpeakerCaptureDeviceChange = (value: string) => {
    console.log('[Audio] Speaker capture device changed:', value || 'default')
    updateAudio({ speakerCaptureDeviceId: value || null })
    const deviceInt = value ? parseInt(value) : null
    updateSettings({ audio: { speaker_capture_device: deviceInt } })
  }

  const handleNoiseSuppressionToggle = (enabled: boolean) => {
    console.log('[Settings] Noise suppression toggle', enabled)
    updateAudio({ enableNoiseSuppression: enabled })
    updateSettings({ audio: { enableNoiseSuppression: enabled } })
  }

  const handleVADToggle = (enabled: boolean) => {
    console.log('[Settings] VAD toggle', enabled)
    updateAudio({ enableVAD: enabled })
    updateSettings({ audio: { vad_enabled: enabled } })
  }

  const handleVADSensitivity = (value: number) => {
    console.log('[Settings] VAD sensitivity change', value)
    updateAudio({ vadSensitivity: value })
    updateSettings({ audio: { vad_sensitivity: value } })
  }

  // Output profile helpers — sync to backend after every change
  const syncProfiles = () => {
    const profiles = useSettingsStore.getState().outputProfiles
    updateSettings({ output_profiles: profiles })
  }

  const handleMasterOutputChange = (value: string) => {
    updateOutputProfile('default', { audioOutputDeviceId: value || null })
    syncProfiles()
  }

  const handleDefaultProfileUpdate = (settings: Partial<OutputProfile>) => {
    updateOutputProfile('default', settings)
    syncProfiles()
  }

  // Build device options
  const inputDeviceOptions = inputDevices.map(d => ({
    value: String(d.id),
    label: `${d.name}${d.is_default ? ' (Default)' : ''}`,
  }))

  const outputDeviceOptions = outputDevices.map(d => ({
    value: String(d.id),
    label: `${d.name}${d.is_default ? ' (Default)' : ''}`,
  }))

  const levelPercent = Math.min(100, Math.max(0, (audioLevel || 0) * 100))
  const levelColor = levelPercent > 80 ? 'bg-red-500' : levelPercent > 50 ? 'bg-yellow-500' : 'bg-green-500'

  // RVC Mic Output state
  const rvcSettings = useSettingsStore((s) => s.rvc)
  const updateRVC = useSettingsStore((s) => s.updateRVC)
  const isMicRvcActive = useChatStore((s) => s.isMicRvcActive)

  const handleMicRvcOutputDevice = (deviceId: string) => {
    console.log('[Audio] RVC mic output device change', deviceId)
    const id = parseInt(deviceId)
    updateRVC({ micRvcOutputDeviceId: id })
    if (isMicRvcActive) {
      sendMessage({ type: 'rvc_mic_set_output_device', payload: { device_id: id } })
    }
  }

  return (
    <div className="p-4 space-y-4">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Audio</h3>
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

      {/* ─── MICROPHONE CARD ─── */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary/40 border-b border-border">
          <Mic className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Microphone</span>
        </div>
        <div className="p-4 space-y-4">
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
              <p className="text-xs text-muted-foreground">Reduce background noise</p>
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
                <p className="text-sm font-medium">Voice Activity Detection</p>
                <p className="text-xs text-muted-foreground">Auto-detect when you speak</p>
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
      </div>

      {/* ─── SPEAKER CAPTURE CARD ─── */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary/40 border-b border-border">
          <Headphones className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Speaker Capture (Loopback)</span>
        </div>
        <div className="p-4 space-y-3">
          <div className="space-y-2">
            <Label>Capture Device</Label>
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
          <Button
            variant="outline"
            size="sm"
            disabled={isTestingLoopback}
            onClick={() => {
              console.log('[Audio] Test Loopback clicked, device:', audio.speakerCaptureDeviceId || 'default')
              const deviceId = audio.speakerCaptureDeviceId
                ? parseInt(audio.speakerCaptureDeviceId) : undefined
              setIsTestingLoopback(true)
              setLoopbackResult(null)
              sendMessage({ type: 'test_loopback', payload: { device_id: deviceId ?? null } })
              // Timeout fallback in case backend doesn't respond
              setTimeout(() => setIsTestingLoopback(false), 5000)
            }}
          >
            {isTestingLoopback ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            {isTestingLoopback ? 'Testing...' : 'Test Loopback'}
          </Button>
        </div>
        {loopbackResult && (
          <p className={`text-xs flex items-center gap-1 px-4 pb-2 ${loopbackResult.success ? 'text-green-400' : 'text-red-400'}`}>
            {loopbackResult.success ? <Check className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
            {loopbackResult.message}
          </p>
        )}
      </div>

      {/* ─── TTS OUTPUT CARD ─── */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary/40 border-b border-border">
          <Volume2 className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">TTS Output</span>
        </div>
        <div className="p-4 space-y-3">
          <div className="space-y-2">
            <Label>Output Device</Label>
            <Select
              value={defaultProfile?.audioOutputDeviceId || ''}
              onValueChange={handleMasterOutputChange}
              options={[
                { value: '', label: 'System Default' },
                ...outputDeviceOptions,
              ]}
              placeholder="Select output device..."
            />
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                console.log('[Settings] Test speaker clicked')
                setIsTestingSpeaker(true)
                const deviceId = defaultProfile?.audioOutputDeviceId
                  ? parseInt(defaultProfile.audioOutputDeviceId) : undefined
                sendMessage({ type: 'test_speaker', payload: { device_id: deviceId ?? null } })
                setTimeout(() => setIsTestingSpeaker(false), 3000)
              }}
              disabled={isTestingSpeaker}
            >
              {isTestingSpeaker ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              Test Speaker
            </Button>
          </div>
        </div>
      </div>

      {/* ─── RVC MIC OUTPUT CARD ─── */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary/40 border-b border-border">
          <AudioLines className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">RVC Mic Output</span>
        </div>
        <div className="p-4 space-y-3">
          <div className="space-y-2">
            <Label>Output Device</Label>
            <Select
              value={String(rvcSettings.micRvcOutputDeviceId ?? '')}
              onValueChange={handleMicRvcOutputDevice}
              options={[
                { value: '', label: 'System Default' },
                ...outputDeviceOptions,
              ]}
              placeholder="Select output device..."
            />
            <p className="text-xs text-muted-foreground">
              Where real-time voice conversion audio plays.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                console.log('[Audio] Test RVC mic output')
                const deviceId = rvcSettings.micRvcOutputDeviceId
                sendMessage({ type: 'test_speaker', payload: { device_id: deviceId ?? null } })
              }}
            >
              <Play className="w-4 h-4 mr-2" />
              Test Output
            </Button>
          </div>
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <p className="text-xs text-blue-400">
              <strong>Tip:</strong> For VRChat or Discord, use a virtual audio cable (e.g., VB-CABLE) as the output device,
              then set it as your microphone in the target app.
            </p>
          </div>
        </div>
      </div>

    </div>
  )
}

function VRChatSettings() {
  const { outputProfiles, updateOutputProfile, addOutputProfile, removeOutputProfile } = useSettingsStore()
  const { updateSettings, getAudioDevices, lastMessage, sendMessage } = useBackend()
  const [outputDevices, setOutputDevices] = useState<AudioDevice[]>([])
  const [oscTestResult, setOscTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [oscTesting, setOscTesting] = useState(false)

  useEffect(() => {
    getAudioDevices()
  }, [getAudioDevices])

  useEffect(() => {
    if (lastMessage?.type === 'audio_devices') {
      const payload = lastMessage.payload as { outputs?: AudioDevice[] }
      setOutputDevices(payload.outputs || [])
    } else if (lastMessage?.type === 'test_osc_result') {
      const payload = lastMessage.payload as { success?: boolean; error?: string; ip?: string; port?: number }
      console.log('[Settings] OSC test result:', payload)
      setOscTesting(false)
      if (payload.success) {
        setOscTestResult({ success: true, message: `Test message sent to ${payload.ip}:${payload.port}` })
      } else {
        setOscTestResult({ success: false, message: payload.error || 'Failed to send test message' })
      }
    }
  }, [lastMessage])

  const defaultProfile = outputProfiles.find(p => p.id === 'default') || outputProfiles[0]

  const syncProfiles = () => {
    const profiles = useSettingsStore.getState().outputProfiles
    updateSettings({ output_profiles: profiles })
  }

  const handleUpdate = (settings: Partial<OutputProfile>) => {
    updateOutputProfile('default', settings)
    syncProfiles()
  }

  const additionalProfiles = outputProfiles.filter(p => p.id !== 'default')

  const handleProfileUpdate = (id: string, settings: Partial<OutputProfile>) => {
    updateOutputProfile(id, settings)
    syncProfiles()
  }

  const handleAddProfile = () => {
    console.log('[Settings] Add output profile')
    addOutputProfile()
    syncProfiles()
  }

  const handleRemoveProfile = (id: string) => {
    console.log('[Settings] Remove output profile', id)
    removeOutputProfile(id)
    syncProfiles()
  }

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium">OSC</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Send transcribed and translated text to VRChat's chatbox via OSC. This controls text display, not audio.
        </p>
      </div>

      <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
        <div>
          <p className="text-sm font-medium">Enable OSC</p>
          <p className="text-xs text-muted-foreground">Send text to VRChat chatbox</p>
        </div>
        <Switch
          checked={defaultProfile?.oscEnabled ?? true}
          onCheckedChange={(v) => handleUpdate({ oscEnabled: v })}
        />
      </div>

      {defaultProfile?.oscEnabled && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">OSC IP</Label>
              <input
                type="text"
                value={defaultProfile.oscIP}
                onChange={(e) => handleUpdate({ oscIP: e.target.value })}
                className="w-full bg-secondary px-2 py-1.5 rounded text-sm font-mono"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">OSC Port</Label>
              <input
                type="number"
                value={defaultProfile.oscPort}
                onChange={(e) => handleUpdate({ oscPort: parseInt(e.target.value) || 9000 })}
                className="w-full bg-secondary px-2 py-1.5 rounded text-sm font-mono"
              />
            </div>
          </div>

          {/* Test OSC Connection */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={oscTesting}
              onClick={() => {
                console.log('[Settings] Test OSC clicked', defaultProfile.oscIP, defaultProfile.oscPort)
                setOscTesting(true)
                setOscTestResult(null)
                sendMessage({ type: 'test_osc', payload: { ip: defaultProfile.oscIP, port: defaultProfile.oscPort } })
                setTimeout(() => setOscTesting(false), 5000)
              }}
            >
              {oscTesting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              Test OSC
            </Button>
            {oscTestResult && (
              <span className={`text-xs flex items-center gap-1 ${oscTestResult.success ? 'text-green-400' : 'text-red-400'}`}>
                {oscTestResult.success ? <Check className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                {oscTestResult.message}
              </span>
            )}
          </div>

          {/* Text routing toggles */}
          <div>
            <Label className="text-xs text-muted-foreground">What to send</Label>
            <div className="grid grid-cols-2 gap-2 mt-1">
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">Original Text</span>
                <Switch
                  checked={defaultProfile.sendOriginalText}
                  onCheckedChange={(v) => handleUpdate({ sendOriginalText: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">Translated Text</span>
                <Switch
                  checked={defaultProfile.sendTranslatedText}
                  onCheckedChange={(v) => handleUpdate({ sendTranslatedText: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">AI Responses</span>
                <Switch
                  checked={defaultProfile.sendAiResponses}
                  onCheckedChange={(v) => handleUpdate({ sendAiResponses: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">Listen Text</span>
                <Switch
                  checked={defaultProfile.sendListenText}
                  onCheckedChange={(v) => handleUpdate({ sendListenText: v })}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Divider */}
      <div className="border-t border-border" />

      {/* ─── ADDITIONAL OSC DESTINATIONS ─── */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
          <Send className="w-4 h-4" />
          Additional Output Destinations
          {additionalProfiles.length > 0 && (
            <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded normal-case tracking-normal">
              {additionalProfiles.length}
            </span>
          )}
        </div>

        {additionalProfiles.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Add extra destinations to route audio and text to multiple OSC targets or virtual cables.
          </p>
        )}

        {additionalProfiles.map((profile) => (
          <OutputProfileCard
            key={profile.id}
            profile={profile}
            outputDevices={outputDevices}
            isDefault={false}
            onUpdate={(settings) => handleProfileUpdate(profile.id, settings)}
            onRemove={() => handleRemoveProfile(profile.id)}
          />
        ))}

        {outputProfiles.length < 5 && (
          <Button variant="outline" size="sm" onClick={handleAddProfile} className="w-full">
            <Plus className="w-4 h-4 mr-2" />
            Add Output Destination
          </Button>
        )}

        {outputProfiles.length >= 5 && (
          <p className="text-xs text-muted-foreground text-center">
            Maximum of 5 output destinations reached.
          </p>
        )}
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

      {/* OSC Enable */}
      <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
        <div>
          <p className="text-sm font-medium">Enable OSC</p>
          <p className="text-xs text-muted-foreground">Send text to VRChat chatbox</p>
        </div>
        <Switch
          checked={profile.oscEnabled}
          onCheckedChange={(v) => onUpdate({ oscEnabled: v })}
        />
      </div>

      {profile.oscEnabled && (
        <div className="space-y-4">
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

          {/* Text routing toggles */}
          <div>
            <Label className="text-xs text-muted-foreground">What to send</Label>
            <div className="grid grid-cols-2 gap-2 mt-1">
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">Original Text</span>
                <Switch
                  checked={profile.sendOriginalText}
                  onCheckedChange={(v) => onUpdate({ sendOriginalText: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">Translated Text</span>
                <Switch
                  checked={profile.sendTranslatedText}
                  onCheckedChange={(v) => onUpdate({ sendTranslatedText: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">AI Responses</span>
                <Switch
                  checked={profile.sendAiResponses}
                  onCheckedChange={(v) => onUpdate({ sendAiResponses: v })}
                />
              </div>
              <div className="flex items-center justify-between p-2 bg-secondary/50 rounded">
                <span className="text-xs">Listen Text</span>
                <Switch
                  checked={profile.sendListenText}
                  onCheckedChange={(v) => onUpdate({ sendListenText: v })}
                />
              </div>
            </div>
          </div>
        </div>
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
    console.log('[Settings] Save credentials')
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
                  className="w-16"
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
                  className="w-16"
                  onClick={() => setShowKeys({ ...showKeys, [key]: !showKeys[key] })}
                >
                  {showKeys[key] ? 'Hide' : 'Show'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Button onClick={handleSave} size="sm" className="gap-1.5">
        {saved ? <><Check className="w-3.5 h-3.5" /> Saved!</> : 'Save Credentials'}
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
  // Base models are now auto-downloaded during model load — no modal needed

  // Local state for runtime RVC data (not persisted)
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; path: string; index_path: string | null; size_mb: number }>>([])
  const [isModelLoaded, setIsModelLoaded] = useState(globalRvcLoaded)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState('')
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [memoryUsageMb, setMemoryUsageMb] = useState(0)
  const [modelName, setModelName] = useState<string | null>(null)
  const [isTestingVoice, setIsTestingVoice] = useState(false)

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
        // Restart mic RVC if it was enabled before model switch
        if (settings.rvc.micRvcEnabled) {
          console.log('[Settings] RVC model loaded — restarting mic RVC')
          sendMessage({
            type: 'rvc_mic_start',
            payload: { output_device_id: settings.rvc.micRvcOutputDeviceId }
          })
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
          enabled?: boolean; loaded?: boolean; model_name?: string | null; memory_mb?: number; device?: string
        }
        if (payload.loaded !== undefined) setIsModelLoaded(payload.loaded)
        if (payload.model_name) setModelName(payload.model_name)
        if (payload.memory_mb) setMemoryUsageMb(payload.memory_mb)
        // Log backend device for diagnostics (don't override user's saved device —
        // the resync on connect already sends the correct device to backend)
        if (payload.device) {
          console.log('[Settings] RVC backend reports device:', payload.device, '(frontend has:', settings.rvc.rvcDevice, ')')
        }
        break
      }
      case 'rvc_base_models_needed': {
        // No longer shows modal — backend auto-downloads base models
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
      case 'tts_output_devices':
        // Handled in Audio page now
        break
    }
  }, [lastMessage])

  const handleEnableToggle = (checked: boolean) => {
    console.log('[Settings] RVC enable toggle', checked)
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
    console.log('[Settings] RVC load model', path)
    if (isLoading) return
    // Stop mic RVC before loading a new model to avoid stream errors
    if (isMicRvcActive) {
      console.log('[Settings] RVC stopping mic before model switch')
      sendMessage({ type: 'rvc_mic_stop' })
    }
    settings.updateRVC({ modelPath: path, indexPath: indexPath || null })
    setIsLoading(true)
    setLoadingStage('Loading voice model...')
    setLoadingProgress(0)
    sendMessage({ type: 'rvc_load_model', payload: { model_path: path, ...(indexPath ? { index_path: indexPath } : {}) } })
  }

  const handleLoadFromPath = () => {
    console.log('[Settings] RVC load from path', browsePath)
    const path = browsePath.trim().replace(/^["']+|["']+$/g, '').replace(/\//g, '\\')
    if (!path) return
    loadModel(path)
    setBrowsePath('')
  }

  const handleBrowse = () => {
    console.log('[Settings] RVC browse model')
    if (isLoading) return
    sendMessage({ type: 'rvc_browse_model' })
  }

  const handleUnloadModel = () => {
    console.log('[Settings] RVC unload model')
    sendMessage({ type: 'rvc_unload' })
    setIsModelLoaded(false)
    setMemoryUsageMb(0)
    setModelName(null)
    settings.updateRVC({ modelPath: null, indexPath: null })
  }

  const handleParamChange = (param: string, value: number) => {
    console.log('[Settings] RVC param change', param, value)
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
    console.log('[Settings] RVC test voice')
    setIsTestingVoice(true)
    sendMessage({ type: 'rvc_test_voice' })
  }

  // Base models auto-download removed — handled by backend during model load

  const handleMicRvcToggle = (checked: boolean) => {
    console.log('[Settings] RVC mic toggle', checked)
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

  const handleDeviceChange = (device: string) => {
    console.log('[Settings] RVC device change', device)
    settings.updateRVC({ rvcDevice: device as 'cpu' | 'cuda' | 'directml' })
    sendMessage({ type: 'rvc_set_device', payload: { device } })
    // Restart app for clean device switch
    console.log('[Settings] RVC device changed — scheduling app restart')
    setTimeout(() => sendMessage({ type: 'restart_app' }), 800)
  }

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Voice Conversion</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Apply RVC voice models to transform TTS output into a different voice. Load a .pth voice model and adjust conversion parameters.
        </p>
      </div>

      {/* ─── Conversion Options — Mic first, then TTS ─── */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Conversion Options</h4>

        {/* Real-Time Mic Conversion */}
        <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Real-Time Mic Conversion</p>
            <p className="text-xs text-muted-foreground">
              Convert your mic audio through the voice model live
            </p>
          </div>
          <Switch
            checked={isMicRvcActive}
            onCheckedChange={handleMicRvcToggle}
            disabled={!isModelLoaded}
          />
        </div>

        {/* Apply to TTS Toggle */}
        <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Apply to TTS Output</p>
            <p className="text-xs text-muted-foreground">
              Post-process TTS audio through the voice model
            </p>
          </div>
          <Switch
            checked={settings.rvc.enabled}
            onCheckedChange={handleEnableToggle}
            disabled={!isModelLoaded}
          />
        </div>
      </div>

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

        {/* Recent Models as cards — with loading progress as background fill */}
        {(settings.rvc.recentModels || []).length > 0 && (
          <div className="space-y-1.5">
            {(settings.rvc.recentModels || []).map((model) => {
              const isActive = isModelLoaded && settings.rvc.modelPath === model.path
              const isThisLoading = isLoading && settings.rvc.modelPath === model.path
              return (
                <div
                  key={model.path}
                  className={`relative overflow-hidden rounded-lg border transition-colors ${
                    isActive
                      ? 'border-green-500/50'
                      : isThisLoading
                      ? 'border-primary/50'
                      : 'bg-secondary/30 border-transparent hover:bg-secondary/50'
                  }`}
                >
                  {/* Background fill for loading progress */}
                  {isThisLoading && loadingProgress > 0 && (
                    <div
                      className="absolute inset-0 transition-all duration-300 rounded-lg"
                      style={{
                        width: `${loadingProgress}%`,
                        background: 'rgba(40, 180, 80, 0.15)',
                      }}
                    />
                  )}
                  {/* Green background for loaded state */}
                  {isActive && !isThisLoading && (
                    <div className="absolute inset-0 rounded-lg" style={{ background: 'rgba(40, 180, 80, 0.08)' }} />
                  )}
                  <div className="relative flex items-center justify-between p-2.5">
                    <button
                      onClick={() => !isActive && !isLoading && loadModel(model.path, model.indexPath)}
                      disabled={isActive || isLoading}
                      className="flex-1 text-left min-w-0"
                    >
                      <div className="flex items-center gap-2">
                        {isThisLoading && <Loader2 className="w-3.5 h-3.5 text-primary animate-spin shrink-0" />}
                        <span className={`text-sm truncate ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>{model.name}</span>
                        {model.sizeMb > 0 && (
                          <span className="text-[10px] text-muted-foreground shrink-0">{model.sizeMb} MB</span>
                        )}
                        {isThisLoading && (
                          <span className="text-[10px] text-muted-foreground">{loadingStage || 'Loading...'} {loadingProgress > 0 ? `${Math.round(loadingProgress)}%` : ''}</span>
                        )}
                      </div>
                    </button>
                    {isActive ? (
                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        <Check className="w-4 h-4 text-green-500" />
                        <Button variant="ghost" size="sm" onClick={handleUnloadModel} className="text-xs h-7">
                          Unload
                        </Button>
                      </div>
                    ) : isThisLoading ? (
                      <button
                        onClick={() => {
                          console.log('[Settings] RVC cancel model load')
                          sendMessage({ type: 'rvc_unload' })
                          setIsLoading(false)
                          setLoadingStage('')
                          setLoadingProgress(0)
                          settings.updateRVC({ modelPath: null, indexPath: null })
                        }}
                        className="px-2 py-0.5 rounded text-[10px] bg-destructive/20 text-destructive hover:bg-destructive/30 transition-colors shrink-0 ml-2"
                      >
                        Cancel
                      </button>
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
                </div>
              )
            })}
          </div>
        )}

        {/* Loading state for models not yet in recent list */}
        {isLoading && !(settings.rvc.recentModels || []).some(m => m.path === settings.rvc.modelPath) && (
          <div className="relative overflow-hidden rounded-lg border border-primary/50">
            {loadingProgress > 0 && (
              <div
                className="absolute inset-0 transition-all duration-300 rounded-lg"
                style={{ width: `${loadingProgress}%`, background: 'rgba(40, 180, 80, 0.15)' }}
              />
            )}
            <div className="relative flex items-center gap-2 p-2.5 text-xs text-primary">
              <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
              <span className="flex-1">{loadingStage || 'Loading model...'} {loadingProgress > 0 ? `${Math.round(loadingProgress)}%` : ''}</span>
              <button
                onClick={() => {
                  console.log('[Settings] RVC cancel model load')
                  sendMessage({ type: 'rvc_unload' })
                  setIsLoading(false)
                  setLoadingStage('')
                  setLoadingProgress(0)
                  settings.updateRVC({ modelPath: null, indexPath: null })
                }}
                className="px-2 py-0.5 rounded text-[10px] bg-destructive/20 text-destructive hover:bg-destructive/30 transition-colors"
              >
                Cancel
              </button>
            </div>
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
            <p className="text-xs text-muted-foreground">GPU provides lower latency. Changing will restart the app.</p>
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

      {/* Base models are now auto-downloaded during model load - no modal needed */}

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

