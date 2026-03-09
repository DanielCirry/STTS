import { useEffect, useRef, useCallback, useState } from 'react'
import { useChatStore, useModelStore, useNotificationStore, useSettingsStore, type TTSEngine } from '@/stores'
import { useFeaturesStore } from '@/stores/featuresStore'

const WS_URL = 'ws://127.0.0.1:9876'

const PROVIDER_LABELS: Record<string, string> = {
  MyMemory: 'Online (Free)',
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

export interface BackendMessage {
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
            inputSource: 'mic',
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
        ...(payload.translated ? { translatedText: payload.translated as string } : {}),
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

    case 'tts_started':
      chatStore.setSpeaking(true)
      break

    case 'tts_finished':
      chatStore.setSpeaking(false)
      break

    case 'model_loading': {
      modelStore.updateModelStatus(
        payload.id as string,
        'loading'
      )
      // Show friendly name (strip path, keep just filename without extension)
      const loadingName = (payload.id as string).replace(/\\/g, '/').split('/').pop()?.replace(/\.gguf$/i, '') || payload.id as string
      chatStore.addMessage({
        type: 'system',
        originalText: `Loading ${payload.type} model: ${loadingName}...`,
      })
      break
    }

    case 'model_loaded': {
      modelStore.updateModelStatus(
        payload.id as string,
        'loaded'
      )
      const loadedName = (payload.id as string).replace(/\\/g, '/').split('/').pop()?.replace(/\.gguf$/i, '') || payload.id as string
      chatStore.addMessage({
        type: 'system',
        originalText: `${payload.type} model loaded: ${loadedName}`,
      })
      break
    }

    case 'model_error': {
      const notificationStore = useNotificationStore.getState()
      modelStore.updateModelStatus(
        payload.id as string,
        'error',
        undefined,
        payload.error as string
      )
      const errorName = (payload.id as string).replace(/\\/g, '/').split('/').pop()?.replace(/\.gguf$/i, '') || payload.id as string
      chatStore.addMessage({
        type: 'system',
        originalText: `Error loading ${payload.type} model: ${payload.error || errorName}`,
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

    // RVC Voice Conversion events
    case 'rvc_model_loaded':
      useChatStore.getState().setRvcModelLoaded(true)
      // Backend auto-enables RVC on model load, but frontend may have it off.
      // Sync the frontend's enabled state back to backend.
      if (globalWs?.readyState === WebSocket.OPEN) {
        globalWs.send(JSON.stringify({ type: 'rvc_enable', payload: { enabled: useSettingsStore.getState().rvc.enabled } }))
      }
      break

    case 'rvc_unloaded':
      useChatStore.getState().setRvcModelLoaded(false)
      break

    case 'rvc_status': {
      const rvcLoaded = payload.loaded as boolean | undefined
      if (rvcLoaded !== undefined) {
        useChatStore.getState().setRvcModelLoaded(rvcLoaded)
      }
      // Don't override frontend device from rvc_status — the frontend's saved
      // setting is the source of truth (sent to backend on connect).
      // Just log for diagnostics.
      const rvcDevice = payload.device as string | undefined
      if (rvcDevice) {
        console.log('[useBackend] rvc_status reports device:', rvcDevice, '(frontend has:', useSettingsStore.getState().rvc.rvcDevice, ')')
      }
      break
    }

    case 'rvc_model_error':
      useChatStore.getState().setRvcModelLoaded(false)
      // Clear saved model path so it doesn't retry on every reconnect
      useSettingsStore.getState().updateRVC({ modelPath: null, indexPath: null })
      useNotificationStore.getState().addToast(
        `RVC model failed: ${payload.error || 'Unknown error'}`,
        'error'
      )
      break

    case 'rvc_mic_started':
      useChatStore.getState().setMicRvcActive(true)
      break

    case 'rvc_mic_stopped':
      useChatStore.getState().setMicRvcActive(false)
      break

    case 'rvc_available_devices': {
      const devices = (payload as { devices?: string[] }).devices
      if (devices) {
        useSettingsStore.getState().updateRVC({ rvcAvailableDevices: devices })
      }
      break
    }

    case 'rvc_mic_error':
      useChatStore.getState().setMicRvcActive(false)
      useNotificationStore.getState().addToast(
        `Mic RVC error: ${(payload.error as string) || 'Unknown error'}`,
        'error'
      )
      break

    case 'rvc_conversion_failed':
      useNotificationStore.getState().addToast(
        (payload.message as string) || 'Voice conversion failed \u2014 playing original audio.',
        'warning'
      )
      break

    case 'rvc_base_models_needed':
      useChatStore.getState().setRvcBaseModelsNeeded(true, payload.size_mb as number | undefined)
      break

    case 'rvc_download_progress': {
      const file = payload.file as string || ''
      const progress = payload.progress as number || 0
      useChatStore.getState().setRvcDownloadProgress({ file, progress })
      // Auto-dismiss base models dialog when download completes
      if (progress >= 1.0) {
        useChatStore.getState().setRvcBaseModelsNeeded(false)
        useChatStore.getState().setRvcDownloadProgress(null)
      }
      break
    }

    case 'rvc_test_voice_error':
      useNotificationStore.getState().addToast(
        `Test voice failed: ${payload.error || 'Unknown error'}`,
        'warning'
      )
      break

    case 'settings_updated': {
      // If backend reports a different TTS engine (e.g. piper unavailable → edge),
      // update frontend to match so voice list shows the correct engine's voices
      const actualEngine = payload.tts_engine as string | undefined
      if (actualEngine) {
        const settings = useSettingsStore.getState()
        if (settings.tts.engine !== actualEngine) {
          settings.updateTTS({ engine: actualEngine as TTSEngine })
        }
      }
      break
    }

    case 'error':
      console.error('Backend error:', payload.message)
      break

    case 'features_status':
      useFeaturesStore.getState().setStatus(payload as any)
      break

    case 'feature_install_progress':
      useFeaturesStore.getState().setInstallProgress({
        detail: (payload.detail as string) || '',
        timestamp: Date.now(),
      })
      break

    case 'feature_install_result':
      console.log('[useBackend] feature_install_result:', JSON.stringify(payload))
      useFeaturesStore.getState().setInstallResult({
        success: payload.success as boolean,
        feature: payload.feature as string | undefined,
        error: payload.error as string | undefined,
        timestamp: Date.now(),
        restart_needed: payload.restart_needed as boolean | undefined,
      })
      break

    case 'feature_uninstall_result':
      useFeaturesStore.getState().setUninstallResult({
        success: payload.success as boolean,
        feature: payload.feature as string,
        error: payload.error as string | undefined,
        timestamp: Date.now(),
      })
      break

    case 'voicevox_setup_status':
      useFeaturesStore.getState().setVoicevoxInstalled(payload.installed as boolean)
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
      globalConnecting = false
      globalWs = null
    }

    if (globalConnecting) {
      return
    }

    globalConnecting = true

    try {
      const ws = new WebSocket(WS_URL)
      globalWs = ws

      ws.onopen = () => {
        globalConnecting = false
        setGlobalConnected(true)
        setReconnectAttempt(0)  // Reset backoff on successful connection

        // Request initial status
        ws.send(JSON.stringify({ type: 'get_status' }))
        ws.send(JSON.stringify({ type: 'rvc_get_status' }))
        ws.send(JSON.stringify({ type: 'get_features_status' }))
        // Check VOICEVOX install status (fast local check, no network/icon fetch)
        ws.send(JSON.stringify({ type: 'voicevox_check_install' }))

        // Resync frontend settings to backend (critical after backend restart)
        // Must use nested keys matching backend's settings dict structure
        const settings = useSettingsStore.getState()
        ws.send(JSON.stringify({
          type: 'update_settings',
          payload: {
            stt: {
              model: settings.stt.model,
              language: settings.stt.language,
              device: settings.stt.device,
            },
            tts: {
              engine: settings.tts.engine,
              voice: settings.tts.voice,
              enabled: settings.tts.enabled,
              device: settings.tts.device,
            },
            translation: {
              enabled: settings.translation.enabled,
              provider: settings.translation.provider,
              device: settings.translation.device,
              language_pairs: settings.translation.languagePairs.map((p) => ({
                source: p.sourceLanguage,
                target: p.targetLanguage,
              })),
              active_pair_index: settings.translation.activePairIndex,
            },
            ai: {
              enabled: settings.ai.enabled,
              keyword: settings.ai.keyword,
              provider: settings.ai.provider,
              emoji_mode: settings.ai.emojiMode,
              device: settings.ai.device,
            },
            audio: {
              input_device: settings.audio.microphoneDeviceId ? parseInt(settings.audio.microphoneDeviceId) : null,
              speaker_capture_device: settings.audio.speakerCaptureDeviceId ? parseInt(settings.audio.speakerCaptureDeviceId) : null,
              vad_enabled: settings.audio.enableVAD,
              vad_sensitivity: settings.audio.vadSensitivity,
            },
          }
        }))
        // Also resync RVC device after restart
        ws.send(JSON.stringify({
          type: 'rvc_set_device',
          payload: { device: settings.rvc.rvcDevice }
        }))
      }

      ws.onclose = (event) => {
        globalConnecting = false
        globalWs = null
        setGlobalConnected(false)
        // 1001 = "going away" (normal close, e.g. page unload) — don't log as error
        if (event.code !== 1001) {
          console.debug('WebSocket closed:', event.code, event.reason)
        }
        // Reset runtime state that depends on backend
        useChatStore.getState().setMicRvcActive(false)
        useChatStore.getState().setRvcModelLoaded(false)
        useChatStore.getState().setListening(false)
        useChatStore.getState().setSpeakerListening(false)
        // Reset persisted RVC toggle so it doesn't show stale "on" state
        useSettingsStore.getState().updateRVC({ enabled: false })

        const delay = getReconnectDelay()
        setReconnectAttempt(reconnectAttempt + 1)
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
          if (message.type !== 'audio_level') {
            console.log('[WS] RECV', message.type, message.payload)
          }

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

      case 'tts_voices':
      case 'voicevox_voices':
        if (payload.voices) {
          useChatStore.getState().setTtsVoices(
            (payload.voices as { id: string; name: string; icon?: string }[]).slice(0, 50)
          )
        }
        break

      case 'app_restarting':
        console.log('[WS] App is restarting:', payload.reason)
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
              'cache_cleared', 'cache_info',
              'rvc_models_list', 'rvc_model_loading', 'rvc_model_loaded', 'rvc_model_error',
              'rvc_status', 'rvc_unloaded', 'rvc_params_updated', 'rvc_conversion_failed',
              'rvc_download_progress', 'rvc_base_models_needed',
              'llm_unloaded',
              'rvc_test_voice_ready', 'rvc_test_voice_error', 'rvc_model_browsed',
              'rvc_mic_started', 'rvc_mic_stopped', 'rvc_mic_error', 'rvc_available_devices',
              'voicevox_setup_status', 'voicevox_setup_progress', 'voicevox_engine_status',
              'vrchat_sent', 'vrchat_status', 'tts_started', 'tts_finished',
              'tts_voices', 'tts_output_devices', 'audio_devices', 'loopback_test_result',
              'features_status', 'feature_install_progress', 'feature_install_result', 'feature_uninstall_result',
              'test_osc_result'].includes(type)) {
          console.warn('Unknown message type:', type)
        }
        break
    }
  }, [])

  const send = useCallback((message: { type: string; payload?: Record<string, unknown> }) => {
    console.log('[WS] SEND', message)
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

  const browseLLMFolder = useCallback(() => {
    send({ type: 'browse_llm_folder' })
  }, [send])

  const browseLLMModel = useCallback(() => {
    send({ type: 'browse_llm_model' })
  }, [send])

  const unloadLLM = useCallback(() => {
    send({ type: 'unload_llm' })
  }, [send])

  const getLLMStatus = useCallback(() => {
    send({ type: 'get_llm_status' })
  }, [send])

  // Register message handler
  useEffect(() => {
    messageHandlers.add(handleMessage)
    return () => {
      messageHandlers.delete(handleMessage)
    }
  }, [handleMessage])

  useEffect(() => {
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
    browseLLMFolder,
    browseLLMModel,
    getLLMStatus,
    unloadLLM,
  }
}
