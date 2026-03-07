import { Mic, Keyboard, User, Bot, AlertTriangle } from 'lucide-react'
import type { ChatMessage } from '@/stores'

interface MessageBubbleProps {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.type === 'user'
  const isAI = message.type === 'ai'
  const isSpeaker = message.type === 'speaker'
  const isError = isAI && message.originalText.startsWith('Error:')

  // Parse error message for helpful hints
  const getErrorHint = (errorText: string): string | null => {
    if (errorText.includes('Model not loaded')) {
      return 'Go to Settings → AI Assistant and load a local model, or switch to a cloud provider.'
    }
    if (errorText.includes('not available')) {
      return 'This provider requires an API key. Go to Settings → API Credentials to add your key.'
    }
    if (errorText.includes('API key')) {
      return 'Go to Settings → API Credentials to configure your API key.'
    }
    return null
  }

  const errorHint = isError ? getErrorHint(message.originalText) : null

  return (
    <div className={`flex ${isUser || isAI ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`rounded-lg px-4 py-2 max-w-[70%] ${
          isError
            ? 'bg-destructive/20 text-destructive border border-destructive/30'
            : isUser
            ? 'bg-primary text-primary-foreground'
            : isAI
            ? 'bg-accent text-accent-foreground'
            : 'bg-secondary text-secondary-foreground'
        }`}
      >
        {/* Speaker indicator */}
        <div className="flex items-center gap-2 mb-1">
          {isSpeaker && <User className="w-3 h-3" />}
          {isUser && message.inputSource === 'text' && <Keyboard className="w-3 h-3" />}
          {isUser && message.inputSource !== 'text' && <Mic className="w-3 h-3" />}
          {isError && <AlertTriangle className="w-3 h-3" />}
          {isAI && !isError && <Bot className="w-3 h-3" />}
          <span className="text-xs opacity-70">
            {isSpeaker
              ? message.speakerName || 'Speaker'
              : isUser
              ? 'You'
              : isError
              ? 'Error'
              : 'AI'}
          </span>
        </div>

        {/* Text content */}
        {message.translatedText ? (
          <>
            <p className="text-xs opacity-60">{message.originalText}</p>
            <p className="text-sm mt-1">{message.translatedText}</p>
          </>
        ) : (
          <p className="text-sm">
            {message.originalText}
            {message.translationFailed && (
              <span className="text-xs text-yellow-500 italic ml-1">[translation failed]</span>
            )}
          </p>
        )}

        {/* Error hint */}
        {errorHint && (
          <p className="text-xs mt-2 opacity-80">{errorHint}</p>
        )}
      </div>
    </div>
  )
}
