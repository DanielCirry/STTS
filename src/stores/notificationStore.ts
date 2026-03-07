import { create } from 'zustand'

export type ToastSeverity = 'info' | 'warning' | 'error'

export interface Toast {
  id: string
  message: string
  severity: ToastSeverity
  timestamp: Date
}

export interface ModelErrorInfo {
  modelType: string
  modelId: string
  error: string
}

interface NotificationStore {
  toasts: Toast[]
  errorCount: number
  modelError: ModelErrorInfo | null
  addToast: (message: string, severity: ToastSeverity) => void
  dismissToast: (id: string) => void
  clearAll: () => void
  showModelError: (info: ModelErrorInfo) => void
  dismissModelError: () => void
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  toasts: [],
  errorCount: 0,
  modelError: null,

  addToast: (message, severity) => {
    const id = crypto.randomUUID()
    const toast: Toast = { id, message, severity, timestamp: new Date() }

    set((state) => ({
      toasts: [...state.toasts, toast],
      errorCount: severity === 'error' ? state.errorCount + 1 : state.errorCount,
    }))

    // Auto-dismiss: info 4s, warnings 5s, errors 8s
    const delays: Record<ToastSeverity, number> = { info: 4000, warning: 5000, error: 8000 }
    setTimeout(() => {
      get().dismissToast(id)
    }, delays[severity])
  },

  dismissToast: (id) =>
    set((state) => {
      const toast = state.toasts.find((t) => t.id === id)
      return {
        toasts: state.toasts.filter((t) => t.id !== id),
        errorCount: toast?.severity === 'error' ? Math.max(0, state.errorCount - 1) : state.errorCount,
      }
    }),

  clearAll: () => set({ toasts: [], errorCount: 0 }),

  showModelError: (info) => set({ modelError: info }),

  dismissModelError: () => set({ modelError: null }),
}))
