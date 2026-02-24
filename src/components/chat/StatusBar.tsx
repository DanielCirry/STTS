import { Circle, Wifi, WifiOff, Globe, Volume2, Headphones } from 'lucide-react'
import { useChatStore, useSettingsStore, useNotificationStore } from '@/stores'

interface StatusBarProps {
  connected: boolean
  audioLevel?: number
  detectedLanguage?: string | null
  speakerCapturing?: boolean
  ttsEngine?: string | null
}

// Map Whisper ISO 639-1 codes to short labels
const LANG_LABELS: Record<string, string> = {
  en: 'EN', ja: 'JA', zh: 'ZH', ko: 'KO', es: 'ES', fr: 'FR',
  de: 'DE', it: 'IT', pt: 'PT', ru: 'RU', ar: 'AR', hi: 'HI',
  th: 'TH', vi: 'VI', id: 'ID', nl: 'NL', pl: 'PL', tr: 'TR', uk: 'UK',
}

// Map NLLB codes to short display labels
const NLLB_SHORT: Record<string, string> = {
  eng_Latn: 'EN', jpn_Jpan: 'JA', zho_Hans: 'ZH', zho_Hant: 'ZH-TW',
  kor_Hang: 'KO', spa_Latn: 'ES', fra_Latn: 'FR', deu_Latn: 'DE',
  ita_Latn: 'IT', por_Latn: 'PT', rus_Cyrl: 'RU', arb_Arab: 'AR',
  hin_Deva: 'HI', tha_Thai: 'TH', vie_Latn: 'VI', ind_Latn: 'ID',
  nld_Latn: 'NL', pol_Latn: 'PL', tur_Latn: 'TR', ukr_Cyrl: 'UK',
}

const TTS_ENGINE_LABELS: Record<string, string> = {
  piper: 'Piper',
  edge: 'Edge',
  sapi: 'SAPI',
  voicevox: 'VOICEVOX',
}

const PROVIDER_LABELS: Record<string, string> = {
  MyMemory: 'MyMemory',
  LibreTranslate: 'LibreTranslate',
  Lingva: 'Lingva',
  deepl: 'DeepL',
  google: 'Google',
  nllb: 'NLLB',
}

const AI_PROVIDER_LABELS: Record<string, string> = {
  local: 'Local LLM',
  groq: 'Groq',
  google: 'Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
}

export function StatusBar({ connected, audioLevel = 0, detectedLanguage, speakerCapturing, ttsEngine }: StatusBarProps) {
  const { isListening, isProcessing, activeTranslationProvider, activeAIProvider, aiOfflineMode } = useChatStore()
  const settings = useSettingsStore()
  const errorCount = useNotificationStore((s) => s.errorCount)

  const status = !connected
    ? 'Disconnected'
    : isProcessing
    ? 'Processing'
    : isListening
    ? 'Listening'
    : 'Ready'

  const statusColor = !connected
    ? 'text-red-500'
    : isProcessing
    ? 'text-yellow-500'
    : isListening
    ? 'text-green-500'
    : 'text-muted-foreground'

  // Build active translation pair label
  const activePair = settings.translation.languagePairs[settings.translation.activePairIndex]
  const pairLabel = activePair
    ? `${NLLB_SHORT[activePair.sourceLanguage] || activePair.sourceLanguage.split('_')[0].toUpperCase()}→${NLLB_SHORT[activePair.targetLanguage] || activePair.targetLanguage.split('_')[0].toUpperCase()}`
    : null

  const detectedLabel = detectedLanguage ? (LANG_LABELS[detectedLanguage] || detectedLanguage.toUpperCase()) : null

  return (
    <div className="h-8 flex items-center px-4 border-t border-border text-xs text-muted-foreground gap-3 overflow-x-auto">
      {/* Connection status */}
      <div className="flex items-center gap-1.5 shrink-0">
        {connected ? (
          <Wifi className="w-3 h-3 text-green-500" />
        ) : (
          <WifiOff className="w-3 h-3 text-red-500" />
        )}
      </div>

      {/* Status indicator */}
      <div className="flex items-center gap-1.5 shrink-0">
        <Circle className={`w-2 h-2 fill-current ${statusColor}`} />
        <span>{status}</span>
      </div>

      {/* Audio level meter */}
      {isListening && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <div className="flex items-center gap-1.5 shrink-0">
            <div className="w-16 h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 transition-all duration-75"
                style={{ width: `${audioLevel * 100}%` }}
              />
            </div>
          </div>
        </>
      )}

      <div className="h-3 w-px bg-border shrink-0" />

      {/* STT Model + Detected Language */}
      <span className="shrink-0">
        STT: {settings.stt.model.replace('whisper-', '')}
        {detectedLabel && (
          <span className="ml-1 text-primary font-medium">[{detectedLabel}]</span>
        )}
      </span>

      <div className="h-3 w-px bg-border shrink-0" />

      <span className="shrink-0">Device: {settings.stt.device.toUpperCase()}</span>

      {/* Translation pair */}
      {settings.translation.enabled && pairLabel && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <span className="shrink-0 flex items-center gap-1">
            <Globe className="w-3 h-3" />
            {pairLabel}
          </span>
        </>
      )}

      {/* Active translation provider */}
      {activeTranslationProvider && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <span className="shrink-0 text-muted-foreground text-xs">
            Trans: {PROVIDER_LABELS[activeTranslationProvider] || activeTranslationProvider}
          </span>
        </>
      )}

      {/* Active AI provider */}
      {settings.ai.enabled && activeAIProvider && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <span className="shrink-0 text-muted-foreground text-xs">
            AI: {AI_PROVIDER_LABELS[activeAIProvider] || activeAIProvider}
            {aiOfflineMode && ' (offline)'}
          </span>
        </>
      )}

      {/* TTS engine */}
      {settings.tts.enabled && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <span className="shrink-0 flex items-center gap-1">
            <Volume2 className="w-3 h-3" />
            {TTS_ENGINE_LABELS[ttsEngine || settings.tts.engine] || settings.tts.engine}
          </span>
        </>
      )}

      {/* Speaker capture status */}
      {speakerCapturing && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <span className="shrink-0 flex items-center gap-1 text-blue-400">
            <Headphones className="w-3 h-3" />
            Listening
          </span>
        </>
      )}

      {/* Error badge */}
      {errorCount > 0 && (
        <>
          <div className="h-3 w-px bg-border shrink-0" />
          <span className="shrink-0 flex items-center gap-1 text-red-400 font-medium">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
            {errorCount} {errorCount === 1 ? 'error' : 'errors'}
          </span>
        </>
      )}

      <div className="h-3 w-px bg-border shrink-0" />

      <span className="shrink-0">VRC: {settings.vrchat.oscEnabled ? '✓' : '✗'}</span>
    </div>
  )
}
