import { useEffect, useRef, useCallback, useState } from 'react'
import { useChatStore, useModelStore, useNotificationStore } from '@/stores'

const WS_URL = 'ws://127.0.0.1:9876'

const PROVIDER_LABELS: Record<string, string> = {
  MyMemory: 'MyMemory',
  LibreTranslate: 'LibreTranslate',
  Lingva: 'Lingva',
  deepl: 'DeepL',
  google: 'Google',
  nllb: 'NLLB (Local)',
}

const AI_PROVIDER_LABELS: Record<string, string> = {
  local: 'Local LLM',
  groq: 'Groq',
  google: 'Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
}

// Module-level singleton WebSocket to prevent React StrictMode double-connections
let globalWs: WebSocket | null = null
let globalConnecting = false
let globalConnected = false
// Store message handlers from all hook instances so they all receive messages
const messageHandlers = new Set<(message: BackendMessage) => void>()
// Store connection state change handlers
const connectionHandlers = new Set<(connected: boolean) => void>()

// Reconnection with exponential backoff
let reconnectAttempt = 0
const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000

function getReconnectDelay(): number {
  const base = Math.min(RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt), RECONNECT_MAX_MS)
  // Jitter: +/- 200ms to prevent thundering herd
  const jitter = Math.floor((Math.random() - 0.5) * 400)
  return Math.max(RECONNECT_BASE_MS, base + jitter)
}

const reconnectAttemptHandlers = new Set<(attempt: number) => void>()

function setReconnectAttempt(attempt: number) {
  reconnectAttempt = attempt
  reconnectAttemptHandlers.forEach(handler => handler(attempt))
}

interface BackendMessage {
  type: string
  payload: Record<string, unknown>
  timestamp: number
}

interface BackendStatus {
  initialized: boolean
  listening: boolean
  cuda_available: boolean
  device: string
  models: {
    stt: boolean
    translator: boolean
    tts: boolean
    ai: boolean
  }
  tts?: {
    available: boolean
    engine: string | null
    engines: string[]
    speaking: boolean
  }
  vrchat?: {
    connected: boolean
    queue_size: number
    processing: boolean
  }
  vrOverlay?: {
    available: boolean
    initialized: boolean
    steamvr_installed: boolean
    hmd_present: boolean
  }
  speakerCapture?: {
    available: boolean
    capturing: boolean
    device: string | null
  }
}

// Module-level function to handle global state updates (only called once per message)
function handleGlobalMessage(message: BackendMessage) {
  const { type, payload } = message
  const chatStore = useChatStore.getState()
  const modelStore = useModelStore.getState()

  switch (type) {
    case 'transcript_partial':
      chatStore.setCurrentTranscript(payload.text as string)
      break

    case 'transcript_final': {
      const source = payload.source as string | undefined
      // Track detected language for StatusBar display
      const detLang = payload.detected_language as string | null | undefined
      if (detLang && source !== 'speaker') {
        chatStore.setDetectedLanguage(detLang)
      }
      if (source === 'speaker') {
        // Speaker capture transcript — show as incoming speaker message
        chatStore.addMessage({
          type: 'speaker',
          originalText: payload.text as string,
        })
      } else {
        chatStore.setCurrentTranscript('')
        // Skip if this text was already added locally (typed input)
        const msgs = chatStore.messages
        const last = msgs[msgs.length - 1]
        if (!last || last.originalText !== (payload.text as string)) {
          chatStore.addMessage({
            type: 'user',
            originalText: payload.text as string,
          })
        }
      }
      break
    }

    case 'translation_complete':
      chatStore.updateMessageTranslation(
        payload.original as string,
        payload.translated as string
      )
      break

    case 'translation_failed':
      // Show original text with translationFailed tag in chat
      chatStore.addMessage({
        type: 'user',
        originalText: payload.original as string,
        translationFailed: true,
      })
      // Warning toast — auto-dismisses after 5s per user decision
      useNotificationStore.getState().addToast(
        'Translation failed \u2014 showing original text',
        'warning'
      )
      break

    case 'translation_provider_switched': {
      const provider = payload.provider as string | null
      const previous = payload.previous as string | null

      // Update chatStore with active provider
      useChatStore.getState().setActiveTranslationProvider(provider)

      if (provider && previous) {
        // Provider switched — warning toast (auto-dismiss 5s per existing behavior)
        const providerLabel = PROVIDER_LABELS[provider] || provider
        const previousLabel = PROVIDER_LABELS[previous] || previous
        useNotificationStore.getState().addToast(
          `Translation switched to ${providerLabel} (${previousLabel} unavailable)`,
          'warning'
        )
      } else if (provider && !previous) {
        // Recovery from total failure — previous was null (all failed), now one is back
        // On initial startup, previous is also null — show nothing to avoid toast spam
        // The backend sets previous=null only on recovery, so show a recovery toast
        const providerLabel = PROVIDER_LABELS[provider] || provider
        useNotificationStore.getState().addToast(
          `Translation restored via ${providerLabel}`,
          'warning'
        )
      } else if (!provider) {
        // All providers exhausted — sticky error toast
        useNotificationStore.getState().addToast(
          'All translation providers unavailable. Check your internet connection or configure API keys.',
          'error'
        )
      }
      break
    }

    case 'ai_provider_switched': {
      const to = payload.to as string
      const from = payload.from as string | null
      const reason = payload.reason as string

      useChatStore.getState().setActiveAIProvider(to)

      // Always toast on ANY provider switch (LOCKED DECISION -- differs from translation which is silent for minor switches)
      // Only toast when there was a previous provider (not initial assignment)
      if (from !== null && reason !== 'initial') {
        const toLabel = AI_PROVIDER_LABELS[to] || to
        useNotificationStore.getState().addToast(
          `AI switched to ${toLabel} (${reason})`,
          'warning'
        )
      }
      break
    }

    case 'ai_offline_mode': {
      // StatusBar indicator only -- NO toast (LOCKED DECISION)
      useChatStore.getState().setAIOfflineMode(true)
      break
    }

    case 'ai_online_restored': {
      const provider = payload.provider as string
      useChatStore.getState().setAIOfflineMode(false)
      useChatStore.getState().setActiveAIProvider(provider)
      const providerLabel = AI_PROVIDER_LABELS[provider] || provider
      useNotificationStore.getState().addToast(
        `AI restored via ${providerLabel}`,
        'warning'
      )
      break
    }

    case 'ai_response':
      chatStore.addMessage({
        type: 'ai',
        originalText: payload.response as string,
      })
      break

    case 'listening_started':
      if ((payload as Record<string, unknown>).source === 'speaker') {
        chatStore.setSpeakerListening(true)
      } else {
        chatStore.setListening(true)
      }
      break

    case 'listening_stopped':
      if ((payload as Record<string, unknown>).source === 'speaker') {
        chatStore.setSpeakerListening(false)
      } else {
        chatStore.setListening(false)
      }
      break

    case 'model_loading':
      modelStore.updateModelStatus(
        payload.id as string,
        'loading'
      )
      chatStore.addMessage({
        type: 'system',
        originalText: `Loading ${payload.type} model: ${payload.id}...`,
      })
      break

    case 'model_loaded':
      modelStore.updateModelStatus(
        payload.id as string,
        'loaded'
      )
      chatStore.addMessage({
        type: 'system',
        originalText: `${payload.type} model loaded: ${payload.id}`,
      })
      break

    case 'model_error': {
      const notificationStore = useNotificationStore.getState()
      modelStore.updateModelStatus(
        payload.id as string,
        'error',
        undefined,
        payload.error as string
      )
      chatStore.addMessage({
        type: 'system',
        originalText: `Error loading ${payload.type} model: ${payload.error || payload.id}`,
      })

      // Only show blocking dialog for STT errors (per RESEARCH pitfall 6)
      // TTS/translation/LLM errors get toast notification
      if (payload.type === 'stt') {
        notificationStore.showModelError({
          modelType: payload.type as string,
          modelId: payload.id as string,
          error: (payload.error as string) || 'Unknown error',
        })
      } else {
        notificationStore.addToast(
          `Failed to load ${payload.type} model: ${payload.error || payload.id}`,
          'error'
        )
      }
      break
    }

    case 'model_download_progress':
      modelStore.updateModelStatus(
        payload.id as string,
        'downloading',
        payload.progress as number
      )
      break

    case 'error':
      console.error('Backend error:', payload.message)
      break

    default:
      // Other messages are handled by individual hook instances
      break
  }
}

// Notify all hook instances of connection state change
function setGlobalConnected(connected: boolean) {
  globalConnected = connected
  connectionHandlers.forEach(handler => handler(connected))
}

export function useBackend() {
  const reconnectTimeoutRef = useRef<number | null>(null)
  const [connected, setConnected] = useState(globalConnected)
  const [status, setStatus] = useState<BackendStatus | null>(null)
  const [audioLevel, setAudioLevel] = useState(0)
  const [lastMessage, setLastMessage] = useState<BackendMessage | null>(null)
  const [reconnectAttemptState, setReconnectAttemptState] = useState(reconnectAttempt)

  // Register for connection state changes
  useEffect(() => {
    const handler = (isConnected: boolean) => setConnected(isConnected)
    connectionHandlers.add(handler)
    // Sync current state
    setConnected(globalConnected)
    return () => {
      connectionHandlers.delete(handler)
    }
  }, [])

  // Register for reconnect attempt changes
  useEffect(() => {
    const handler = (attempt: number) => setReconnectAttemptState(attempt)
    reconnectAttemptHandlers.add(handler)
    setReconnectAttemptState(reconnectAttempt)
    return () => {
      reconnectAttemptHandlers.delete(handler)
    }
  }, [])

  const connect = useCallback(() => {
    // Check if already connected
    if (globalWs?.readyState === WebSocket.OPEN) {
      setGlobalConnected(true)
      return
    }

    // Check if currently connecting
    if (globalWs?.readyState === WebSocket.CONNECTING) {
      return
    }

    // Reset stale connecting state (can happen after hot reload)
    if (globalConnecting && (!globalWs || globalWs.readyState === WebSocket.CLOSED)) {
      console.log('Resetting stale connection state')
      globalConnecting = false
      globalWs = null
    }

    if (globalConnecting) {
      return
    }

    globalConnecting = true
    console.log('Creating new WebSocket connection to', WS_URL)
    console.log('globalWs:', globalWs, 'globalConnecting:', globalConnecting)

    try {
      const ws = new WebSocket(WS_URL)
      globalWs = ws

      ws.onopen = () => {
        console.log('Connected to backend')
        globalConnecting = false
        setGlobalConnected(true)
        setReconnectAttempt(0)  // Reset backoff on successful connection

        // Request initial status
        ws.send(JSON.stringify({ type: 'get_status' }))
      }

      ws.onclose = () => {
        console.log('Disconnected from backend')
        globalConnecting = false
        globalWs = null
        setGlobalConnected(false)

        const delay = getReconnectDelay()
        setReconnectAttempt(reconnectAttempt + 1)
        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempt})`)
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, delay)
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        globalConnecting = false
      }

      ws.onmessage = (event) => {
        try {
          const message: BackendMessage = JSON.parse(event.data)

          // Handle global state updates ONCE at module level
          // (Zustand stores are singletons, so getState() always works)
          handleGlobalMessage(message)

          // Notify all registered handlers for local state updates
          messageHandlers.forEach(handler => handler(message))
        } catch (e) {
          console.error('Error parsing message:', e)
        }
      }
    } catch (e) {
      console.error('Failed to create WebSocket:', e)
      globalConnecting = false
      globalWs = null
    }
  }, [])

  // Handler for local state updates only (no store updates)
  const handleMessage = useCallback((message: BackendMessage) => {
    const { type, payload } = message

    // Store last message for components that need raw access
    setLastMessage(message)

    switch (type) {
      case 'status':
        setStatus(payload as unknown as BackendStatus)
        break

      case 'audio_level':
        setAudioLevel(payload.level as number)
        break

      case 'vrchat_sent':
        console.log('VRChat message sent:', payload.text)
        break

      case 'vrchat_status':
        console.log('VRChat status:', payload)
        break

      case 'tts_started':
        console.log('TTS started')
        break

      case 'tts_finished':
        console.log('TTS finished')
        break

      case 'tts_voices':
        console.log('TTS voices:', payload.voices)
        break

      case 'tts_output_devices':
        console.log('TTS output devices:', payload.devices)
        break

      case 'audio_devices':
        console.log('Audio devices received:', payload)
        break

      default:
        // Log unknown messages only if they're not handled globally
        if (!['transcript_partial', 'transcript_final', 'translation_complete', 'translation_failed',
              'translation_provider_switched',
              'ai_response', 'ai_provider_switched', 'ai_offline_mode', 'ai_online_restored',
              'listening_started', 'listening_stopped',
              'model_loading', 'model_loaded', 'model_error', 'model_download_progress',
              'error', 'local_models', 'models_directory', 'models_directory_set',
              'settings_updated', 'voicevox_connection_result', 'voicevox_voices',
              'cache_cleared', 'cache_info'].includes(type)) {
          console.log('Unknown message type:', type, payload)
        }
        break
    }
  }, [])

  const send = useCallback((message: { type: string; payload?: Record<string, unknown> }) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket not connected')
    }
  }, [])

  const startListening = useCallback(() => {
    send({ type: 'start_listening' })
  }, [send])

  const stopListening = useCallback(() => {
    send({ type: 'stop_listening' })
  }, [send])

  const testMicrophone = useCallback((deviceId?: number) => {
    send({ type: 'test_microphone', payload: deviceId !== undefined ? { device_id: deviceId } : {} })
  }, [send])

  const stopTestMicrophone = useCallback(() => {
    send({ type: 'stop_test_microphone' })
  }, [send])

  const loadModel = useCallback((modelType: string, modelId: string) => {
    send({ type: 'load_model', payload: { type: modelType, id: modelId } })
  }, [send])

  const speak = useCallback((text: string) => {
    send({ type: 'speak', payload: { text } })
  }, [send])

  const aiQuery = useCallback((query: string) => {
    send({ type: 'ai_query', payload: { query } })
  }, [send])

  // Send text input to be processed like voice (with keyword detection, translation, etc.)
  const sendTextInput = useCallback((text: string) => {
    send({ type: 'text_input', payload: { text } })
  }, [send])

  const requestTranslation = useCallback((text: string, source: string, target: string) => {
    send({ type: 'translate', payload: { text, source, target } })
  }, [send])

  const updateSettings = useCallback((settings: Record<string, unknown>) => {
    send({ type: 'update_settings', payload: settings })
  }, [send])

  const getAudioDevices = useCallback(() => {
    send({ type: 'get_audio_devices' })
  }, [send])

  const sendToVRChat = useCallback((text: string, useQueue: boolean = true) => {
    send({ type: 'vrchat_send', payload: { text, use_queue: useQueue } })
  }, [send])

  const clearVRChatChatbox = useCallback(() => {
    send({ type: 'vrchat_clear' })
  }, [send])

  const stopSpeaking = useCallback(() => {
    send({ type: 'stop_speaking' })
  }, [send])

  const startSpeakerCapture = useCallback(() => {
    send({ type: 'start_speaker_capture' })
  }, [send])

  const stopSpeakerCapture = useCallback(() => {
    send({ type: 'stop_speaker_capture' })
  }, [send])

  const getTTSVoices = useCallback((engine?: string) => {
    send({ type: 'get_tts_voices', payload: engine ? { engine } : {} })
  }, [send])

  const getTTSOutputDevices = useCallback(() => {
    send({ type: 'get_tts_output_devices' })
  }, [send])

  const getLocalModels = useCallback(() => {
    send({ type: 'get_local_models' })
  }, [send])

  const loadLocalModel = useCallback((modelPath: string) => {
    send({ type: 'load_model', payload: { type: 'llm', id: modelPath } })
  }, [send])

  const getAIProviders = useCallback(() => {
    send({ type: 'get_ai_providers' })
  }, [send])

  const setModelsDirectory = useCallback((path: string) => {
    send({ type: 'set_models_directory', payload: { path } })
  }, [send])

  const getModelsDirectory = useCallback(() => {
    send({ type: 'get_models_directory' })
  }, [send])

  // Register message handler
  useEffect(() => {
    messageHandlers.add(handleMessage)
    return () => {
      messageHandlers.delete(handleMessage)
    }
  }, [handleMessage])

  useEffect(() => {
    console.log('useBackend: useEffect called, calling connect()')
    connect()

    return () => {
      // Only clear the reconnect timeout, don't close the connection
      // (connection is managed at module level to survive StrictMode remounts)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  return {
    connected,
    reconnectAttempt: reconnectAttemptState,
    status,
    audioLevel,
    lastMessage,
    sendMessage: send,
    startListening,
    stopListening,
    testMicrophone,
    stopTestMicrophone,
    loadModel,
    speak,
    stopSpeaking,
    startSpeakerCapture,
    stopSpeakerCapture,
    aiQuery,
    sendTextInput,
    requestTranslation,
    updateSettings,
    getAudioDevices,
    getTTSVoices,
    getTTSOutputDevices,
    sendToVRChat,
    clearVRChatChatbox,
    getLocalModels,
    loadLocalModel,
    getAIProviders,
    setModelsDirectory,
    getModelsDirectory,
  }
}
