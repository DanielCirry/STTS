import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type TTSEngine = 'piper' | 'voicevox' | 'edge' | 'sapi'
export type AIProvider = 'local' | 'openai' | 'anthropic' | 'google' | 'groq'
export type TranslationProvider = 'local' | 'free' | 'deepl' | 'google'
export type ComputeDevice = 'cpu' | 'cuda'

interface AudioSettings {
  microphoneDeviceId: string | null
  speakerCaptureDeviceId: string | null
  ttsOutputDeviceId: string | null
  enableNoiseSuppression: boolean
  enableVAD: boolean
  vadSensitivity: number
}

interface STTSettings {
  model: string
  language: string
  device: ComputeDevice
}

export interface LanguagePair {
  id: string
  sourceLanguage: string
  targetLanguage: string
}

interface TranslationSettings {
  enabled: boolean
  model: string
  provider: TranslationProvider
  languagePairs: LanguagePair[]
  activePairIndex: number
}

interface TTSSettings {
  enabled: boolean
  engine: TTSEngine
  voice: string
  speed: number
  pitch: number
  volume: number
  voicevoxUrl: string
  voicevoxEnglishPhonetic: boolean
}

interface AIAssistantSettings {
  enabled: boolean
  keyword: string
  provider: AIProvider
  localModel: string
  cloudModel: string
  modelsDirectory: string
  maxResponseLength: number
  speakResponses: boolean
  showInOverlay: boolean
  gpuLayers: number
  cloudModels: Record<string, string>  // per-provider model selection
}

interface VROverlaySettings {
  enabled: boolean
  showIncomingText: boolean
  showOwnText: boolean
  showAIResponses: boolean
  distance: number
  verticalOffset: number
  horizontalOffset: number
  width: number
  height: number
  fontSize: number
  fontColor: string
  backgroundColor: string
  backgroundOpacity: number
  autoHideSeconds: number
  followHead: boolean
}

export interface RVCSettings {
  enabled: boolean
  modelPath: string | null
  indexPath: string | null
  modelsDirectory: string
  f0UpKey: number          // Pitch shift: -12 to +12 semitones
  indexRate: number         // FAISS influence: 0.0 to 1.0
  filterRadius: number     // Pitch smoothing: 1 to 7
  rmsMixRate: number       // Loudness matching: 0.0 to 1.0
  protect: number          // Consonant protection: 0.0 to 0.5
  resampleSr: number       // Resample rate: 0 = disabled
  volumeEnvelope: number   // Volume envelope mix: 0.0 to 1.0
}

interface VRChatSettings {
  oscEnabled: boolean
  oscIP: string
  oscPort: number
  typingIndicator: boolean
}

export interface Settings {
  audio: AudioSettings
  stt: STTSettings
  translation: TranslationSettings
  tts: TTSSettings
  ai: AIAssistantSettings
  rvc: RVCSettings
  vrOverlay: VROverlaySettings
  vrchat: VRChatSettings
  firstRunComplete: boolean
}

interface SettingsStore extends Settings {
  updateAudio: (settings: Partial<AudioSettings>) => void
  updateSTT: (settings: Partial<STTSettings>) => void
  updateTranslation: (settings: Partial<TranslationSettings>) => void
  updateTTS: (settings: Partial<TTSSettings>) => void
  updateAI: (settings: Partial<AIAssistantSettings>) => void
  updateRVC: (settings: Partial<RVCSettings>) => void
  updateVROverlay: (settings: Partial<VROverlaySettings>) => void
  updateVRChat: (settings: Partial<VRChatSettings>) => void
  addLanguagePair: (sourceLanguage: string, targetLanguage: string) => void
  removeLanguagePair: (id: string) => void
  setActivePair: (index: number) => void
  updatePairLanguage: (id: string, field: 'sourceLanguage' | 'targetLanguage', language: string) => void
  setFirstRunComplete: () => void
  resetToDefaults: () => void
}

const defaultSettings: Settings = {
  audio: {
    microphoneDeviceId: null,
    speakerCaptureDeviceId: null,
    ttsOutputDeviceId: null,
    enableNoiseSuppression: true,
    enableVAD: true,
    vadSensitivity: 0.5,
  },
  stt: {
    model: 'whisper-base',
    language: 'en',
    device: 'cpu',
  },
  translation: {
    enabled: true,
    model: 'nllb-200-distilled-600M',
    provider: 'free',
    languagePairs: [
      { id: 'default-pair', sourceLanguage: 'eng_Latn', targetLanguage: 'jpn_Jpan' },
    ],
    activePairIndex: 0,
  },
  tts: {
    enabled: true,
    engine: 'piper',
    voice: 'en_US-amy-medium',
    speed: 1.0,
    pitch: 1.0,
    volume: 0.8,
    voicevoxUrl: 'http://localhost:50021',
    voicevoxEnglishPhonetic: true,
  },
  ai: {
    enabled: false,
    keyword: 'Jarvis',
    provider: 'local',
    localModel: '',
    cloudModel: 'gpt-4o-mini',
    modelsDirectory: '',
    maxResponseLength: 140,
    speakResponses: true,
    showInOverlay: true,
    gpuLayers: 0,
    cloudModels: {
      openai: 'gpt-4o-mini',
      anthropic: 'claude-sonnet-4-20250514',
      google: 'gemini-2.0-flash',
      groq: 'llama-3.1-8b-instant',
    },
  },
  rvc: {
    enabled: false,
    modelPath: null,
    indexPath: null,
    modelsDirectory: 'models/rvc/voices',
    f0UpKey: 0,
    indexRate: 0.75,
    filterRadius: 3,
    rmsMixRate: 0.25,
    protect: 0.33,
    resampleSr: 0,
    volumeEnvelope: 0.0,
  },
  vrOverlay: {
    enabled: false,
    showIncomingText: true,
    showOwnText: true,
    showAIResponses: true,
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
  },
  vrchat: {
    oscEnabled: true,
    oscIP: '127.0.0.1',
    oscPort: 9000,
    typingIndicator: true,
  },
  firstRunComplete: false,
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      ...defaultSettings,
      updateAudio: (settings) =>
        set((state) => ({ audio: { ...state.audio, ...settings } })),
      updateSTT: (settings) =>
        set((state) => ({ stt: { ...state.stt, ...settings } })),
      updateTranslation: (settings) =>
        set((state) => ({ translation: { ...state.translation, ...settings } })),
      updateTTS: (settings) =>
        set((state) => ({ tts: { ...state.tts, ...settings } })),
      updateAI: (settings) =>
        set((state) => ({ ai: { ...state.ai, ...settings } })),
      updateRVC: (settings) =>
        set((state) => ({ rvc: { ...state.rvc, ...settings } })),
      updateVROverlay: (settings) =>
        set((state) => ({ vrOverlay: { ...state.vrOverlay, ...settings } })),
      updateVRChat: (settings) =>
        set((state) => ({ vrchat: { ...state.vrchat, ...settings } })),
      addLanguagePair: (sourceLanguage, targetLanguage) =>
        set((state) => {
          if (state.translation.languagePairs.length >= 5) return state
          // Prevent duplicate pairs (same source+target combo)
          const duplicate = state.translation.languagePairs.some(
            (p) => p.sourceLanguage === sourceLanguage && p.targetLanguage === targetLanguage
          )
          if (duplicate) return state
          return {
            translation: {
              ...state.translation,
              languagePairs: [
                ...state.translation.languagePairs,
                { id: crypto.randomUUID(), sourceLanguage, targetLanguage },
              ],
            },
          }
        }),
      removeLanguagePair: (id) =>
        set((state) => {
          const pairs = state.translation.languagePairs.filter((p) => p.id !== id)
          if (pairs.length === 0) return state
          const activeIdx = Math.min(state.translation.activePairIndex, pairs.length - 1)
          return {
            translation: { ...state.translation, languagePairs: pairs, activePairIndex: activeIdx },
          }
        }),
      setActivePair: (index) =>
        set((state) => ({
          translation: { ...state.translation, activePairIndex: index },
        })),
      updatePairLanguage: (id, field, language) =>
        set((state) => ({
          translation: {
            ...state.translation,
            languagePairs: state.translation.languagePairs.map((p) => {
              if (p.id !== id) return p
              // If picking the other side's language, swap them
              if (field === 'sourceLanguage' && language === p.targetLanguage) {
                return { ...p, sourceLanguage: p.targetLanguage, targetLanguage: p.sourceLanguage }
              }
              if (field === 'targetLanguage' && language === p.sourceLanguage) {
                return { ...p, sourceLanguage: p.targetLanguage, targetLanguage: p.sourceLanguage }
              }
              return { ...p, [field]: language }
            }),
          },
        })),
      setFirstRunComplete: () => set({ firstRunComplete: true }),
      resetToDefaults: () => set(defaultSettings),
    }),
    {
      name: 'stts-settings',
      // Migrate old formats to new schema
      migrate: (persisted: unknown, version: number) => {
        const state = persisted as Record<string, unknown>

        // v0 -> v1: Migrate old single-pair format to new array format
        if (version < 1) {
          if (state?.translation) {
            const t = state.translation as Record<string, unknown>
            // Old format had sourceLanguage/targetLanguage at top level, no languagePairs
            if (t.sourceLanguage && t.targetLanguage && !t.languagePairs) {
              t.languagePairs = [
                { id: 'migrated-pair', sourceLanguage: t.sourceLanguage, targetLanguage: t.targetLanguage },
              ]
              t.activePairIndex = 0
              delete t.sourceLanguage
              delete t.targetLanguage
            }
          }
        }

        // v1 -> v2: Migrate 'local' provider to 'free' for users who had no API keys
        if (version < 2) {
          const t = (state?.translation as Record<string, unknown>) || {}
          if (t.provider === 'local') {
            t.provider = 'free'
          }
        }

        // v2 -> v3: Add RVC settings for users upgrading from older versions
        if (version < 3) {
          if (!state?.rvc) {
            state.rvc = defaultSettings.rvc
          }
        }

        return state
      },
      version: 3,
    }
  )
)
