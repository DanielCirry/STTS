import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type MessageType = 'user' | 'speaker' | 'ai' | 'system'

export interface ChatMessage {
  id: string
  type: MessageType
  originalText: string
  translatedText?: string
  translationFailed?: boolean
  timestamp: Date
  speakerName?: string
  inputSource?: 'mic' | 'text'
}

interface ChatStore {
  messages: ChatMessage[]
  isListening: boolean
  isSpeakerListening: boolean
  isMicRvcActive: boolean
  isRvcModelLoaded: boolean
  isProcessing: boolean
  currentTranscript: string
  showEmojiPicker: boolean
  detectedLanguage: string | null
  activeTranslationProvider: string | null
  activeAIProvider: string | null
  aiOfflineMode: boolean
  ttsVoices: { id: string; name: string; icon?: string }[]
  rvcBaseModelsNeeded: boolean
  rvcBaseModelsSizeMb: number
  isSpeaking: boolean
  rvcDownloadProgress: { file: string; progress: number } | null
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  updateMessageTranslation: (originalText: string, translatedText: string) => void
  clearMessages: () => void
  setListening: (listening: boolean) => void
  setSpeakerListening: (listening: boolean) => void
  setMicRvcActive: (active: boolean) => void
  setRvcModelLoaded: (loaded: boolean) => void
  setProcessing: (processing: boolean) => void
  setCurrentTranscript: (transcript: string) => void
  setShowEmojiPicker: (show: boolean) => void
  toggleEmojiPicker: () => void
  setDetectedLanguage: (lang: string | null) => void
  setActiveTranslationProvider: (provider: string | null) => void
  setActiveAIProvider: (provider: string | null) => void
  setAIOfflineMode: (offline: boolean) => void
  setTtsVoices: (voices: { id: string; name: string; icon?: string }[]) => void
  setRvcBaseModelsNeeded: (needed: boolean, sizeMb?: number) => void
  setSpeaking: (speaking: boolean) => void
  setRvcDownloadProgress: (progress: { file: string; progress: number } | null) => void
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      messages: [],
      isListening: false,
      isSpeakerListening: false,
      isMicRvcActive: false,
      isRvcModelLoaded: false,
      isProcessing: false,
      currentTranscript: '',
      showEmojiPicker: false,
      detectedLanguage: null,
      activeTranslationProvider: null,
      activeAIProvider: null,
      aiOfflineMode: false,
      ttsVoices: [],
      rvcBaseModelsNeeded: false,
      rvcBaseModelsSizeMb: 400,
      isSpeaking: false,
      rvcDownloadProgress: null,
      addMessage: (message) =>
        set((state) => {
          const MAX_MESSAGES = 500
          const newMessages = [
            ...state.messages,
            {
              ...message,
              id: crypto.randomUUID(),
              timestamp: new Date(),
            },
          ]
          // Trim oldest messages when over limit
          if (newMessages.length > MAX_MESSAGES) {
            return { messages: newMessages.slice(newMessages.length - MAX_MESSAGES) }
          }
          return { messages: newMessages }
        }),
      updateMessageTranslation: (originalText, translatedText) =>
        set((state) => {
          const messages = [...state.messages]
          for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].originalText === originalText && !messages[i].translatedText) {
              messages[i] = { ...messages[i], translatedText }
              break
            }
          }
          return { messages }
        }),
      clearMessages: () => set({ messages: [] }),
      setListening: (listening) => set({ isListening: listening }),
      setSpeakerListening: (listening) => set({ isSpeakerListening: listening }),
      setMicRvcActive: (active) => set({ isMicRvcActive: active }),
      setRvcModelLoaded: (loaded) => set({ isRvcModelLoaded: loaded }),
      setProcessing: (processing) => set({ isProcessing: processing }),
      setCurrentTranscript: (transcript) => set({ currentTranscript: transcript }),
      setShowEmojiPicker: (show) => set({ showEmojiPicker: show }),
      toggleEmojiPicker: () => set((state) => ({ showEmojiPicker: !state.showEmojiPicker })),
      setDetectedLanguage: (lang) => set({ detectedLanguage: lang }),
      setActiveTranslationProvider: (provider) => set({ activeTranslationProvider: provider }),
      setActiveAIProvider: (provider) => set({ activeAIProvider: provider }),
      setAIOfflineMode: (offline) => set({ aiOfflineMode: offline }),
      setTtsVoices: (voices) => set({ ttsVoices: voices }),
      setRvcBaseModelsNeeded: (needed, sizeMb) => set({ rvcBaseModelsNeeded: needed, ...(sizeMb !== undefined ? { rvcBaseModelsSizeMb: sizeMb } : {}) }),
      setSpeaking: (speaking) => set({ isSpeaking: speaking }),
      setRvcDownloadProgress: (progress) => set({ rvcDownloadProgress: progress }),
    }),
    {
      name: 'stts-chat',
      // Only persist messages — transient state (isListening, etc.) resets on reload
      partialize: (state) => ({ messages: state.messages }),
    }
  )
)
