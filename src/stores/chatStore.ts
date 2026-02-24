import { create } from 'zustand'

export type MessageType = 'user' | 'speaker' | 'ai' | 'system'

export interface ChatMessage {
  id: string
  type: MessageType
  originalText: string
  translatedText?: string
  translationFailed?: boolean
  timestamp: Date
  speakerName?: string
}

interface ChatStore {
  messages: ChatMessage[]
  isListening: boolean
  isSpeakerListening: boolean
  isProcessing: boolean
  currentTranscript: string
  showEmojiPicker: boolean
  detectedLanguage: string | null
  activeTranslationProvider: string | null
  activeAIProvider: string | null
  aiOfflineMode: boolean
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  updateMessageTranslation: (originalText: string, translatedText: string) => void
  clearMessages: () => void
  setListening: (listening: boolean) => void
  setSpeakerListening: (listening: boolean) => void
  setProcessing: (processing: boolean) => void
  setCurrentTranscript: (transcript: string) => void
  setShowEmojiPicker: (show: boolean) => void
  toggleEmojiPicker: () => void
  setDetectedLanguage: (lang: string | null) => void
  setActiveTranslationProvider: (provider: string | null) => void
  setActiveAIProvider: (provider: string | null) => void
  setAIOfflineMode: (offline: boolean) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isListening: false,
  isSpeakerListening: false,
  isProcessing: false,
  currentTranscript: '',
  showEmojiPicker: false,
  detectedLanguage: null,
  activeTranslationProvider: null,
  activeAIProvider: null,
  aiOfflineMode: false,
  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: crypto.randomUUID(),
          timestamp: new Date(),
        },
      ],
    })),
  updateMessageTranslation: (originalText, translatedText) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.originalText === originalText
          ? { ...msg, translatedText }
          : msg
      ),
    })),
  clearMessages: () => set({ messages: [] }),
  setListening: (listening) => set({ isListening: listening }),
  setSpeakerListening: (listening) => set({ isSpeakerListening: listening }),
  setProcessing: (processing) => set({ isProcessing: processing }),
  setCurrentTranscript: (transcript) => set({ currentTranscript: transcript }),
  setShowEmojiPicker: (show) => set({ showEmojiPicker: show }),
  toggleEmojiPicker: () => set((state) => ({ showEmojiPicker: !state.showEmojiPicker })),
  setDetectedLanguage: (lang) => set({ detectedLanguage: lang }),
  setActiveTranslationProvider: (provider) => set({ activeTranslationProvider: provider }),
  setActiveAIProvider: (provider) => set({ activeAIProvider: provider }),
  setAIOfflineMode: (offline) => set({ aiOfflineMode: offline }),
}))
