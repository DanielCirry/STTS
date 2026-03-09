import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type TTSEngine = 'piper' | 'voicevox' | 'edge' | 'sapi'
export type AIProvider = 'free' | 'local' | 'openai' | 'anthropic' | 'google' | 'groq'
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
  enabled: boolean
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
  device: ComputeDevice
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
  device: ComputeDevice
  voicevoxUrl: string
  voicevoxEnglishPhonetic: boolean
  voicevoxBuildType: 'directml' | 'cpu'
  voicePerEngine: Record<string, string>  // remembers last voice per engine
}

interface AIAssistantSettings {
  enabled: boolean
  keyword: string
  provider: AIProvider
  device: ComputeDevice
  localModel: string
  cloudModel: string
  modelsDirectory: string
  maxResponseLength: number
  speakResponses: boolean
  showInOverlay: boolean
  gpuLayers: number
  cloudModels: Record<string, string>  // per-provider model selection
  emojiMode: boolean  // AI adds unicode emojis to responses when enabled
}

interface VROverlaySettings {
  enabled: boolean
  showOriginalText: boolean
  showTranslatedText: boolean
  showAIResponses: boolean
  showListenText: boolean
  // Notification panel
  notificationEnabled: boolean
  notificationTracking: 'none' | 'left_hand' | 'right_hand'  // hand attachment
  notificationX: number          // horizontal offset (meters, -1.0 to 1.0)
  notificationY: number          // vertical offset (meters, -1.0 to 1.0)
  notificationWidth: number      // meters (0.1 to 1.2)
  notificationHeight: number     // meters (0.05 to 0.8)
  notificationDistance: number   // depth from tracking target (meters)
  notificationFontSize: number
  notificationFontColor: string
  notificationBgColor: string
  notificationBgOpacity: number
  notificationFadeIn: number
  notificationFadeOut: number
  notificationAutoHide: number
  notificationAdaptiveHeight: boolean
  // Message log panel
  messageLogEnabled: boolean
  messageLogTracking: 'none' | 'left_hand' | 'right_hand'  // hand attachment
  messageLogX: number
  messageLogY: number
  messageLogWidth: number        // meters (0.2 to 1.8)
  messageLogHeight: number       // meters (0.1 to 1.2)
  messageLogDistance: number
  messageLogFontSize: number
  messageLogFontColor: string
  messageLogBgColor: string
  messageLogBgOpacity: number
  messageLogMax: number
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
  micRvcEnabled: boolean   // Real-time mic conversion
  micRvcOutputDeviceId: number | null
  rvcDevice: 'cpu' | 'cuda' | 'directml'
  rvcAvailableDevices: string[]
  recentModels: Array<{ name: string; path: string; indexPath: string | null; sizeMb: number }>
}

interface VRChatSettings {
  oscEnabled: boolean
  oscIP: string
  oscPort: number
  typingIndicator: boolean
}

export interface OutputProfile {
  id: string
  name: string
  // Audio output
  audioOutputDeviceId: string | null
  sendTtsAudio: boolean
  sendRvcAudio: boolean
  // OSC/Text output
  oscEnabled: boolean
  oscIP: string
  oscPort: number
  sendOriginalText: boolean
  sendTranslatedText: boolean
  sendAiResponses: boolean
  sendListenText: boolean  // speaker capture text
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
  outputProfiles: OutputProfile[]
  menuPosition: 'right' | 'top' | 'left' | 'bottom'
  menuAlignment: 'center' | 'start'
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
  addOutputProfile: () => void
  removeOutputProfile: (id: string) => void
  updateOutputProfile: (id: string, settings: Partial<OutputProfile>) => void
  renameOutputProfile: (id: string, name: string) => void
  setMenuPosition: (position: 'right' | 'top' | 'left' | 'bottom') => void
  setMenuAlignment: (alignment: 'center' | 'start') => void
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
    enabled: true,
    model: 'whisper-base',
    language: 'en',
    device: 'cpu',
  },
  translation: {
    enabled: true,
    model: 'nllb-200-distilled-600M',
    provider: 'free',
    device: 'cpu' as ComputeDevice,
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
    device: 'cpu' as ComputeDevice,
    voicevoxUrl: 'http://localhost:50021',
    voicevoxEnglishPhonetic: true,
    voicevoxBuildType: 'directml',
    voicePerEngine: {},
  },
  ai: {
    enabled: false,
    keyword: 'Jarvis',
    provider: 'free',
    device: 'cpu' as ComputeDevice,
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
    emojiMode: false,
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
    micRvcEnabled: false,
    micRvcOutputDeviceId: null,
    rvcDevice: 'cpu' as const,
    rvcAvailableDevices: ['cpu'],
    recentModels: [],
  },
  vrOverlay: {
    enabled: false,
    showOriginalText: true,
    showTranslatedText: true,
    showAIResponses: true,
    showListenText: true,
    // Notification panel
    notificationEnabled: true,
    notificationTracking: 'none',
    notificationX: 0,
    notificationY: -0.3,
    notificationWidth: 0.4,
    notificationHeight: 0.15,
    notificationDistance: 1.5,
    notificationFontSize: 24,
    notificationFontColor: '#FFFFFF',
    notificationBgColor: '#000000',
    notificationBgOpacity: 0.7,
    notificationFadeIn: 0.3,
    notificationFadeOut: 0.5,
    notificationAutoHide: 5,
    notificationAdaptiveHeight: true,
    // Message log panel
    messageLogEnabled: false,
    messageLogTracking: 'none',
    messageLogX: 0,
    messageLogY: 0,
    messageLogWidth: 0.5,
    messageLogHeight: 0.4,
    messageLogDistance: 1.8,
    messageLogFontSize: 20,
    messageLogFontColor: '#FFFFFF',
    messageLogBgColor: '#000000',
    messageLogBgOpacity: 0.6,
    messageLogMax: 20,
  },
  vrchat: {
    oscEnabled: true,
    oscIP: '127.0.0.1',
    oscPort: 9000,
    typingIndicator: true,
  },
  menuPosition: 'right',
  menuAlignment: 'center',
  outputProfiles: [
    {
      id: 'default',
      name: 'Profile 1',
      audioOutputDeviceId: null,
      sendTtsAudio: true,
      sendRvcAudio: true,
      oscEnabled: true,
      oscIP: '127.0.0.1',
      oscPort: 9000,
      sendOriginalText: true,
      sendTranslatedText: true,
      sendAiResponses: true,
      sendListenText: true,
    },
  ],
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
          // Prevent same language pair
          if (sourceLanguage === targetLanguage) return state
          // Prevent duplicate pairs (same source+target combo)
          const duplicate = state.translation.languagePairs.some(
            (p) => p.sourceLanguage === sourceLanguage && p.targetLanguage === targetLanguage
          )
          if (duplicate) return state
          // If reverse pair exists (e.g. adding JP→EN when EN→JP exists), swap it and activate
          const reverseIdx = state.translation.languagePairs.findIndex(
            (p) => p.sourceLanguage === targetLanguage && p.targetLanguage === sourceLanguage
          )
          if (reverseIdx !== -1) {
            const pair = state.translation.languagePairs[reverseIdx]
            return {
              translation: {
                ...state.translation,
                languagePairs: state.translation.languagePairs.map((p) =>
                  p.id === pair.id ? { ...p, sourceLanguage, targetLanguage } : p
                ),
                activePairIndex: reverseIdx,
              },
            }
          }
          const newPairs = [
            ...state.translation.languagePairs,
            { id: crypto.randomUUID(), sourceLanguage, targetLanguage },
          ]
          return {
            translation: {
              ...state.translation,
              languagePairs: newPairs,
              activePairIndex: newPairs.length - 1,
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
      addOutputProfile: () =>
        set((state) => {
          if (state.outputProfiles.length >= 5) return state
          const num = state.outputProfiles.length + 1
          return {
            outputProfiles: [
              ...state.outputProfiles,
              {
                id: crypto.randomUUID(),
                name: `Profile ${num}`,
                audioOutputDeviceId: null,
                sendTtsAudio: false,
                sendRvcAudio: false,
                oscEnabled: true,
                oscIP: '127.0.0.1',
                oscPort: 9000,
                sendOriginalText: true,
                sendTranslatedText: true,
                sendAiResponses: false,
                sendListenText: false,
              },
            ],
          }
        }),
      removeOutputProfile: (id) =>
        set((state) => {
          // Can't remove the default profile
          if (id === 'default') return state
          return {
            outputProfiles: state.outputProfiles.filter((p) => p.id !== id),
          }
        }),
      updateOutputProfile: (id, settings) =>
        set((state) => ({
          outputProfiles: state.outputProfiles.map((p) =>
            p.id === id ? { ...p, ...settings } : p
          ),
        })),
      renameOutputProfile: (id, name) =>
        set((state) => ({
          outputProfiles: state.outputProfiles.map((p) =>
            p.id === id ? { ...p, name } : p
          ),
        })),
      setMenuPosition: (position) => set({ menuPosition: position }),
      setMenuAlignment: (alignment) => set({ menuAlignment: alignment }),
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

        // v3 -> v4: Reset all devices to CPU (backend always starts on CPU) + add recentModels
        if (version < 4) {
          const stt = (state?.stt as Record<string, unknown>) || {}
          const tts = (state?.tts as Record<string, unknown>) || {}
          const translation = (state?.translation as Record<string, unknown>) || {}
          const ai = (state?.ai as Record<string, unknown>) || {}
          const rvc = (state?.rvc as Record<string, unknown>) || {}
          stt.device = 'cpu'
          tts.device = 'cpu'
          translation.device = 'cpu'
          ai.device = 'cpu'
          rvc.rvcDevice = 'cpu'
          if (!rvc.recentModels) rvc.recentModels = []
        }

        // v4 -> v5: Add output profiles — migrate existing VRChat OSC + TTS output into Profile 1
        if (version < 5) {
          const vrchat = (state?.vrchat as Record<string, unknown>) || {}
          const audio = (state?.audio as Record<string, unknown>) || {}
          state.outputProfiles = [
            {
              id: 'default',
              name: 'Profile 1',
              audioOutputDeviceId: audio.ttsOutputDeviceId ?? null,
              sendTtsAudio: true,
              sendRvcAudio: true,
              oscEnabled: vrchat.oscEnabled ?? true,
              oscIP: vrchat.oscIP ?? '127.0.0.1',
              oscPort: vrchat.oscPort ?? 9000,
              sendOriginalText: true,
              sendTranslatedText: true,
              sendAiResponses: true,
              sendListenText: true,
            },
          ]
        }

        // v5 -> v6: Restructure VR overlay — per-element settings, canvas positioning
        if (version < 6) {
          const vr = (state?.vrOverlay as Record<string, unknown>) || {}
          // Migrate old toggle names
          if (vr.showOriginalText === undefined) vr.showOriginalText = vr.showOwnText ?? true
          if (vr.showTranslatedText === undefined) vr.showTranslatedText = true
          if (vr.showListenText === undefined) vr.showListenText = vr.showIncomingText ?? true
          if (vr.showAIResponses === undefined) vr.showAIResponses = true
          delete vr.showOwnText
          delete vr.showIncomingText
          // Tracking & rotation
          if (vr.trackingTarget === undefined) vr.trackingTarget = 'hmd'
          if (vr.rotationX === undefined) vr.rotationX = 0
          if (vr.rotationY === undefined) vr.rotationY = 0
          if (vr.rotationZ === undefined) vr.rotationZ = 0
          // Migrate notification from old flat fields
          if (vr.notificationEnabled === undefined) vr.notificationEnabled = true
          if (vr.notificationX === undefined) vr.notificationX = (vr.horizontalOffset as number) ?? 0
          if (vr.notificationY === undefined) vr.notificationY = (vr.verticalOffset as number) ?? -0.3
          if (vr.notificationWidth === undefined) vr.notificationWidth = (vr.width as number) ?? 0.4
          if (vr.notificationHeight === undefined) vr.notificationHeight = (vr.height as number) ?? 0.15
          if (vr.notificationDistance === undefined) vr.notificationDistance = (vr.distance as number) ?? 1.5
          if (vr.notificationFontSize === undefined) vr.notificationFontSize = (vr.fontSize as number) ?? 24
          if (vr.notificationFontColor === undefined) vr.notificationFontColor = (vr.fontColor as string) ?? '#FFFFFF'
          if (vr.notificationBgColor === undefined) vr.notificationBgColor = (vr.backgroundColor as string) ?? '#000000'
          if (vr.notificationBgOpacity === undefined) vr.notificationBgOpacity = (vr.backgroundOpacity as number) ?? 0.7
          if (vr.notificationFadeIn === undefined) vr.notificationFadeIn = (vr.fadeInDuration as number) ?? 0.3
          if (vr.notificationFadeOut === undefined) vr.notificationFadeOut = (vr.fadeOutDuration as number) ?? 0.5
          if (vr.notificationAutoHide === undefined) vr.notificationAutoHide = (vr.autoHideSeconds as number) ?? 5
          if (vr.notificationAdaptiveHeight === undefined) vr.notificationAdaptiveHeight = (vr.adaptiveHeight as boolean) ?? true
          // Clean up old flat fields
          delete vr.horizontalOffset; delete vr.verticalOffset; delete vr.width; delete vr.height
          delete vr.distance; delete vr.fontSize; delete vr.fontColor; delete vr.backgroundColor
          delete vr.backgroundOpacity; delete vr.fadeInDuration; delete vr.fadeOutDuration
          delete vr.autoHideSeconds; delete vr.adaptiveHeight; delete vr.followHead
          // Message log
          if (vr.messageLogEnabled === undefined) vr.messageLogEnabled = false
          if (vr.messageLogX === undefined) vr.messageLogX = (vr.messageLogHorizontalOffset as number) ?? 0
          if (vr.messageLogY === undefined) vr.messageLogY = (vr.messageLogVerticalOffset as number) ?? 0
          if (vr.messageLogWidth === undefined) vr.messageLogWidth = 0.5
          if (vr.messageLogHeight === undefined) vr.messageLogHeight = 0.4
          if (vr.messageLogDistance === undefined) vr.messageLogDistance = 1.8
          if (vr.messageLogFontSize === undefined) vr.messageLogFontSize = 20
          if (vr.messageLogFontColor === undefined) vr.messageLogFontColor = '#FFFFFF'
          if (vr.messageLogBgColor === undefined) vr.messageLogBgColor = '#000000'
          if (vr.messageLogBgOpacity === undefined) vr.messageLogBgOpacity = 0.6
          if (vr.messageLogMax === undefined) vr.messageLogMax = 20
          delete vr.messageLogHorizontalOffset; delete vr.messageLogVerticalOffset
          state.vrOverlay = vr
        }

        // v6 -> v7: Per-element tracking, remove global rotation/trackingTarget
        if (version < 7) {
          const vr = (state?.vrOverlay as Record<string, unknown>) || {}
          const oldTarget = vr.trackingTarget as string
          // Migrate global tracking to per-element
          if (vr.notificationTracking === undefined) {
            vr.notificationTracking = (oldTarget === 'left_hand' || oldTarget === 'right_hand') ? oldTarget : 'none'
          }
          if (vr.messageLogTracking === undefined) {
            vr.messageLogTracking = (oldTarget === 'left_hand' || oldTarget === 'right_hand') ? oldTarget : 'none'
          }
          delete vr.trackingTarget
          delete vr.rotationX
          delete vr.rotationY
          delete vr.rotationZ
          state.vrOverlay = vr
        }

        // v7 -> v8: Add menu layout settings
        if (version < 8) {
          if ((state as Record<string, unknown>).menuPosition === undefined) {
            (state as Record<string, unknown>).menuPosition = 'right'
          }
          if ((state as Record<string, unknown>).menuAlignment === undefined) {
            (state as Record<string, unknown>).menuAlignment = 'center'
          }
        }

        return state
      },
      version: 8,
    }
  )
)
