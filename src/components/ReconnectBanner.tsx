interface ReconnectBannerProps {
  connected: boolean
  reconnectAttempt: number
}

export function ReconnectBanner({ connected, reconnectAttempt }: ReconnectBannerProps) {
  if (connected) return null

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] bg-yellow-900/95 border-b border-yellow-700 px-4 py-2 text-sm text-yellow-100 flex items-center gap-2">
      <span className="inline-block w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
      <span>
        Disconnected from backend.
        {reconnectAttempt > 0
          ? ` Reconnecting... (attempt ${reconnectAttempt})`
          : ' Reconnecting...'}
      </span>
    </div>
  )
}
