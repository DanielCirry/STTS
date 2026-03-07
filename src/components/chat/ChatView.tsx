import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { useChatStore } from '@/stores'
import { useBackend } from '@/hooks'
import { MessageBubble } from './MessageBubble'
import { Button } from '@/components/ui/button'

export function ChatView() {
  const { messages, currentTranscript, addMessage } = useChatStore()
  const { connected, sendTextInput } = useBackend()
  const [inputText, setInputText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const mountedRef = useRef(false)

  // Auto-scroll: instant on mount, smooth on updates
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true
      messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, currentTranscript])

  // Focus the chat input on mount and when connection is established
  useEffect(() => {
    if (connected) {
      // Small delay to ensure DOM is ready
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [connected])

  const handleSend = () => {
    const text = inputText.trim()
    if (!text) return

    // Add message to chat immediately
    addMessage({ type: 'user', originalText: text, inputSource: 'text' })
    setInputText('')

    // Send to backend for translation, AI keyword detection, VRChat, etc.
    if (connected) {
      sendTextInput(text)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-lg">Welcome to STTS</p>
              <p className="text-sm mt-2">
                {connected
                  ? 'Start speaking to see your transcription here'
                  : 'Connecting to backend...'}
              </p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))
        )}

        {/* Current transcript (while speaking) */}
        {currentTranscript && (
          <div className="flex justify-end">
            <div className="bg-secondary/50 rounded-lg px-4 py-2 max-w-[70%] opacity-70">
              <p className="text-sm italic">{currentTranscript}...</p>
            </div>
          </div>
        )}

        {/* Auto-scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Text Input */}
      <div className="border-t border-border p-2">
        <div className="relative flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="flex-1 bg-secondary/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={!connected}
          />
          <Button
            variant="default"
            size="icon"
            onClick={handleSend}
            disabled={!connected || !inputText.trim()}
            className="h-9 w-9 shrink-0"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>

    </div>
  )
}
