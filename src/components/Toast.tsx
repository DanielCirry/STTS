import { useNotificationStore } from '@/stores'
import { X } from 'lucide-react'

export function ToastContainer() {
  const toasts = useNotificationStore((s) => s.toasts)
  const dismiss = useNotificationStore((s) => s.dismissToast)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-start gap-2 px-4 py-3 rounded-lg shadow-lg text-sm max-w-sm transition-opacity duration-300 ${
            toast.severity === 'error'
              ? 'bg-red-900/95 border border-red-700 text-red-100'
              : toast.severity === 'info'
                ? 'bg-blue-900/95 border border-blue-700 text-blue-100'
                : 'bg-yellow-900/95 border border-yellow-700 text-yellow-100'
          }`}
        >
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => dismiss(toast.id)}
            className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
