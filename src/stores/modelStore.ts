import { create } from 'zustand'

export type ModelCategory = 'stt' | 'translation' | 'tts' | 'llm'
export type ModelStatus = 'not_installed' | 'downloading' | 'installed' | 'loading' | 'loaded' | 'error'

export interface ModelInfo {
  id: string
  name: string
  category: ModelCategory
  size: string
  sizeBytes: number
  description: string
  status: ModelStatus
  downloadProgress?: number
  error?: string
}

interface ModelStore {
  models: ModelInfo[]
  activeModels: {
    stt: string | null
    translation: string | null
    tts: string | null
    llm: string | null
  }
  setModels: (models: ModelInfo[]) => void
  updateModelStatus: (modelId: string, status: ModelStatus, progress?: number, error?: string) => void
  setActiveModel: (category: ModelCategory, modelId: string | null) => void
  getModelsByCategory: (category: ModelCategory) => ModelInfo[]
}

const defaultModels: ModelInfo[] = [
  // STT Models
  {
    id: 'whisper-tiny',
    name: 'Whisper Tiny',
    category: 'stt',
    size: '75 MB',
    sizeBytes: 75 * 1024 * 1024,
    description: 'Fast speech recognition, good for real-time',
    status: 'not_installed',
  },
  {
    id: 'whisper-base',
    name: 'Whisper Base',
    category: 'stt',
    size: '145 MB',
    sizeBytes: 145 * 1024 * 1024,
    description: 'Better accuracy than tiny',
    status: 'not_installed',
  },
  {
    id: 'whisper-small',
    name: 'Whisper Small',
    category: 'stt',
    size: '488 MB',
    sizeBytes: 488 * 1024 * 1024,
    description: 'Good balance of speed and accuracy',
    status: 'not_installed',
  },
  {
    id: 'whisper-medium',
    name: 'Whisper Medium',
    category: 'stt',
    size: '1.5 GB',
    sizeBytes: 1.5 * 1024 * 1024 * 1024,
    description: 'High accuracy, slower',
    status: 'not_installed',
  },
  {
    id: 'whisper-large-v3-turbo',
    name: 'Whisper Large v3 Turbo',
    category: 'stt',
    size: '1.5 GB',
    sizeBytes: 1.5 * 1024 * 1024 * 1024,
    description: 'Best accuracy, optimized for speed',
    status: 'not_installed',
  },
  // Translation Models — IDs must match backend model names
  {
    id: 'nllb-200-distilled-600M',
    name: 'NLLB 600M',
    category: 'translation',
    size: '1.2 GB',
    sizeBytes: 1.2 * 1024 * 1024 * 1024,
    description: '200+ languages, good quality',
    status: 'not_installed',
  },
  {
    id: 'nllb-200-distilled-1.3B',
    name: 'NLLB 1.3B',
    category: 'translation',
    size: '2.6 GB',
    sizeBytes: 2.6 * 1024 * 1024 * 1024,
    description: 'Better translation quality',
    status: 'not_installed',
  },
  {
    id: 'nllb-200-3.3B',
    name: 'NLLB 3.3B',
    category: 'translation',
    size: '6.6 GB',
    sizeBytes: 6.6 * 1024 * 1024 * 1024,
    description: 'Best translation quality',
    status: 'not_installed',
  },
  // TTS Voices
  {
    id: 'piper-en_US-amy-medium',
    name: 'Amy (English US)',
    category: 'tts',
    size: '65 MB',
    sizeBytes: 65 * 1024 * 1024,
    description: 'Female American English voice',
    status: 'not_installed',
  },
  {
    id: 'piper-en_US-ryan-high',
    name: 'Ryan (English US)',
    category: 'tts',
    size: '70 MB',
    sizeBytes: 70 * 1024 * 1024,
    description: 'Male American English voice',
    status: 'not_installed',
  },
  {
    id: 'piper-en_GB-alba-medium',
    name: 'Alba (English UK)',
    category: 'tts',
    size: '60 MB',
    sizeBytes: 60 * 1024 * 1024,
    description: 'Female British English voice',
    status: 'not_installed',
  },
  // LLM Models
  {
    id: 'phi-3-mini-q4',
    name: 'Phi-3 Mini (Q4)',
    category: 'llm',
    size: '2.1 GB',
    sizeBytes: 2.1 * 1024 * 1024 * 1024,
    description: 'Microsoft Phi-3, good for assistants',
    status: 'not_installed',
  },
  {
    id: 'llama-3.2-3b-q4',
    name: 'Llama 3.2 3B (Q4)',
    category: 'llm',
    size: '2 GB',
    sizeBytes: 2 * 1024 * 1024 * 1024,
    description: 'Meta Llama 3.2, versatile',
    status: 'not_installed',
  },
  {
    id: 'qwen2.5-3b-q4',
    name: 'Qwen 2.5 3B (Q4)',
    category: 'llm',
    size: '2 GB',
    sizeBytes: 2 * 1024 * 1024 * 1024,
    description: 'Alibaba Qwen 2.5, multilingual',
    status: 'not_installed',
  },
]

export const useModelStore = create<ModelStore>((set, get) => ({
  models: defaultModels,
  activeModels: {
    stt: null,
    translation: null,
    tts: null,
    llm: null,
  },
  setModels: (models) => set({ models }),
  updateModelStatus: (modelId, status, progress, error) =>
    set((state) => ({
      models: state.models.map((m) =>
        m.id === modelId
          ? { ...m, status, downloadProgress: progress, error }
          : m
      ),
    })),
  setActiveModel: (category, modelId) =>
    set((state) => ({
      activeModels: { ...state.activeModels, [category]: modelId },
    })),
  getModelsByCategory: (category) =>
    get().models.filter((m) => m.category === category),
}))
