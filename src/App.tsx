import { useState, useEffect, useRef } from 'react'
import { Settings, Mic, Languages, Volume2, Bot, Headphones, SmilePlus, ArrowLeftRight, Plus, X, AudioLines, Music, Speech, Trash2, Power, ScanText } from 'lucide-react'
import { ChatView } from '@/components/chat/ChatView'
import { SettingsView } from '@/components/settings/SettingsView'
import { ToastContainer } from '@/components/Toast'
import { ReconnectBanner } from '@/components/ReconnectBanner'
import { ModelErrorDialog } from '@/components/ModelErrorDialog'
import { StatusBar } from '@/components/chat/StatusBar'
import { useSettingsStore, useChatStore } from '@/stores'
import { useNotificationStore } from '@/stores/notificationStore'
import { useFeaturesStore } from '@/stores/featuresStore'
import { useBackend } from '@/hooks/useBackend'

type View = 'chat' | 'settings'

const LANGUAGES = [
  { value: 'eng_Latn', label: 'English', short: 'ENG' },
  { value: 'jpn_Jpan', label: 'Japanese', short: 'JPN' },
  { value: 'zho_Hans', label: 'Chinese (Simplified)', short: 'ZHO' },
  { value: 'zho_Hant', label: 'Chinese (Traditional)', short: 'ZHT' },
  { value: 'kor_Hang', label: 'Korean', short: 'KOR' },
  { value: 'spa_Latn', label: 'Spanish', short: 'SPA' },
  { value: 'fra_Latn', label: 'French', short: 'FRA' },
  { value: 'deu_Latn', label: 'German', short: 'DEU' },
  { value: 'ita_Latn', label: 'Italian', short: 'ITA' },
  { value: 'por_Latn', label: 'Portuguese', short: 'POR' },
  { value: 'rus_Cyrl', label: 'Russian', short: 'RUS' },
  { value: 'arb_Arab', label: 'Arabic', short: 'ARA' },
  { value: 'hin_Deva', label: 'Hindi', short: 'HIN' },
  { value: 'tha_Thai', label: 'Thai', short: 'THA' },
  { value: 'vie_Latn', label: 'Vietnamese', short: 'VIE' },
  { value: 'ind_Latn', label: 'Indonesian', short: 'IND' },
  { value: 'nld_Latn', label: 'Dutch', short: 'NLD' },
  { value: 'pol_Latn', label: 'Polish', short: 'POL' },
  { value: 'tur_Latn', label: 'Turkish', short: 'TUR' },
  { value: 'ukr_Cyrl', label: 'Ukrainian', short: 'UKR' },
]

function getLangShort(nllbCode: string) {
  return LANGUAGES.find(l => l.value === nllbCode)?.short || nllbCode.slice(0, 3).toUpperCase()
}

function getLangLabel(nllbCode: string) {
  return LANGUAGES.find(l => l.value === nllbCode)?.label || nllbCode
}

interface MenuBarProps {
  settings: ReturnType<typeof useSettingsStore>
  menuPosition: 'right' | 'top' | 'left' | 'bottom'
  menuAlignment: 'center' | 'start'
  isListening: boolean
  isSpeakerListening: boolean
  isMicRvcActive: boolean
  isRvcModelLoaded: boolean
  connected: boolean
  startListening: () => void
  stopListening: () => void
  startSpeakerCapture: () => void
  stopSpeakerCapture: () => void
  updateSettings: (s: Record<string, unknown>) => void
  sendMessage: (msg: Record<string, unknown>) => void
  navigateToSettings: (page?: string) => void
  setCurrentView: (view: View) => void
}

function MenuBar({ settings, menuPosition, menuAlignment, isListening, isSpeakerListening, isMicRvcActive, isRvcModelLoaded, connected, startListening, stopListening, startSpeakerCapture, stopSpeakerCapture, updateSettings, sendMessage, navigateToSettings, setCurrentView }: MenuBarProps) {
  const isHorizontal = menuPosition === 'top' || menuPosition === 'bottom'
  const border = menuPosition === 'top' ? 'border-b' : menuPosition === 'bottom' ? 'border-t' : menuPosition === 'left' ? 'border-r' : 'border-l'
  const hAlign = menuAlignment === 'center' ? 'justify-center' : 'justify-start'
  const vAlign = menuAlignment === 'center' ? 'justify-center' : 'justify-start'
  const containerClass = isHorizontal
    ? `${border} border-border flex flex-row ${hAlign} items-center px-4 py-2 gap-3 flex-wrap shrink-0`
    : `w-20 shrink-0 ${border} border-border flex flex-col items-center ${vAlign} py-4 gap-2`
  const separatorClass = isHorizontal ? 'w-px h-8 bg-border mx-1' : 'w-12 h-px bg-border my-1'

  return (
    <div className={containerClass}>
      <ToggleControl icon={<Mic className="w-4 h-4" />} label="STT" enabled={isListening} disabled={!connected}
        onClick={() => { console.log('[App] Toggle STT', { wasListening: isListening }); if (isListening) stopListening(); else startListening() }} />
      <ToggleControl icon={<Volume2 className="w-4 h-4" />} label="TTS" enabled={settings.tts.enabled} disabled={!connected}
        onClick={() => { const v = !settings.tts.enabled; console.log('[App] Toggle TTS', v); settings.updateTTS({ enabled: v }); updateSettings({ tts: { enabled: v } }) }} />

      <div className={separatorClass} />

      <ToggleControl icon={<Languages className="w-4 h-4" />} label="Trans" enabled={settings.translation.enabled} disabled={!connected}
        onClick={() => { const v = !settings.translation.enabled; console.log('[App] Toggle Translation', v); settings.updateTranslation({ enabled: v }); updateSettings({ translation: { enabled: v } }) }} />
      <ToggleControl icon={<ScanText className="w-4 h-4" />} label="VRT" enabled={settings.ocr.enabled} disabled={!connected}
        onClick={() => { const v = !settings.ocr.enabled; console.log('[App] Toggle VRT', v); settings.updateOCR({ enabled: v }); updateSettings({ ocr: { enabled: v } }) }} />
      <ToggleControl icon={<Headphones className="w-4 h-4" />} label="Listen" enabled={isSpeakerListening} disabled={!connected}
        onClick={() => { console.log('[App] Toggle Speaker Capture', { wasSpeakerListening: isSpeakerListening }); if (isSpeakerListening) stopSpeakerCapture(); else startSpeakerCapture() }} />

      <div className={separatorClass} />

      <ToggleControl icon={<Bot className="w-4 h-4" />} label="AI" enabled={settings.ai.enabled} disabled={!connected}
        onClick={() => {
          console.log('[App] Toggle AI', { wasEnabled: settings.ai.enabled, provider: settings.ai.provider })
          if (!settings.ai.enabled && settings.ai.provider === 'local' && !settings.ai.localModel) {
            useNotificationStore.getState().addToast('Configure your AI provider in Settings → AI Assistant', 'info')
            navigateToSettings('ai'); return
          }
          const v = !settings.ai.enabled; settings.updateAI({ enabled: v }); updateSettings({ ai: { enabled: v } })
        }}
        onDisabledClick={() => { useNotificationStore.getState().addToast('Connect to the backend first', 'info') }}
      />
      <ToggleControl icon={<Speech className="w-4 h-4" />} label="Speak" enabled={settings.ai.speakResponses} disabled={!connected}
        onClick={() => { const v = !settings.ai.speakResponses; console.log('[App] Toggle Speak Responses', v); settings.updateAI({ speakResponses: v }); updateSettings({ ai: { speak_responses: v } }) }} />
      <ToggleControl icon={<SmilePlus className="w-4 h-4" />} label="Emoji" enabled={settings.ai.emojiMode} disabled={!connected}
        onClick={() => { const v = !settings.ai.emojiMode; console.log('[App] Toggle Emoji Mode', v); settings.updateAI({ emojiMode: v }); updateSettings({ ai: { emoji_mode: v } }) }} />

      <div className={separatorClass} />

      <ToggleControl icon={<AudioLines className="w-4 h-4" />} label="Mic→RVC" enabled={isMicRvcActive} disabled={!connected || !isRvcModelLoaded}
        onClick={() => {
          console.log('[App] Toggle Mic→RVC', { wasActive: isMicRvcActive })
          if (isMicRvcActive) { useChatStore.getState().setMicRvcActive(false); sendMessage({ type: 'rvc_mic_stop' }) }
          else { useChatStore.getState().setMicRvcActive(true); sendMessage({ type: 'rvc_mic_start', payload: { output_device_id: settings.rvc.micRvcOutputDeviceId } }) }
        }} />
      <ToggleControl icon={<Music className="w-4 h-4" />} label="TTS→RVC" enabled={settings.rvc.enabled} disabled={!connected || !isRvcModelLoaded}
        onClick={() => { const v = !settings.rvc.enabled; console.log('[App] Toggle TTS→RVC', v); settings.updateRVC({ enabled: v }); sendMessage({ type: 'rvc_enable', payload: { enabled: v } }) }} />

      <div className={separatorClass} />

      <button onClick={() => { console.log('[App] Open Settings'); setCurrentView('settings') }} className="p-3 rounded-lg hover:bg-secondary transition-colors" title="Settings">
        <Settings className="w-5 h-5" />
      </button>
      <button onClick={() => { console.log('[App] Quit STTS'); sendMessage({ type: 'shutdown' }); setTimeout(() => window.close(), 500) }} className="p-3 rounded-lg hover:bg-red-500/20 transition-colors text-muted-foreground hover:text-red-400" title="Quit STTS">
        <Power className="w-5 h-5" />
      </button>
    </div>
  )
}

function App() {
  const [currentView, setCurrentView] = useState<View>('chat')
  const [settingsPage, setSettingsPage] = useState<string | undefined>(undefined)
  const [editingPairId, setEditingPairId] = useState<string | 'new' | null>(null)
  const langPickerRef = useRef<HTMLDivElement>(null)
  const settings = useSettingsStore()
  const { updateSettings, connected, reconnectAttempt, loadModel, startListening, stopListening, startSpeakerCapture, stopSpeakerCapture, sendMessage, audioLevel, status } = useBackend()
  const isListening = useChatStore((s) => s.isListening)
  const isSpeakerListening = useChatStore((s) => s.isSpeakerListening)
  const detectedLanguage = useChatStore((s) => s.detectedLanguage)
  const isMicRvcActive = useChatStore((s) => s.isMicRvcActive)
  const isRvcModelLoaded = useChatStore((s) => s.isRvcModelLoaded)
  // showEmojiPicker/toggleEmojiPicker removed - emoji mode is now a setting in settingsStore.ai.emojiMode

  const navigateToSettings = (page?: string) => {
    console.log('[App] Navigate to settings', page || 'main')
    setSettingsPage(page)
    setCurrentView('settings')
  }

  // Close language picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (langPickerRef.current && !langPickerRef.current.contains(e.target as Node)) {
        setEditingPairId(null)
      }
    }
    if (editingPairId) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [editingPairId])

  // On first run (no features installed), go to Features page
  const featuresStatus = useFeaturesStore(s => s.status)
  const firstRunChecked = useRef(false)
  useEffect(() => {
    if (firstRunChecked.current) return
    if (!featuresStatus?.features) return
    firstRunChecked.current = true
    const anyInstalled = Object.values(featuresStatus.features).some(f => f.installed)
    if (!anyInstalled) {
      navigateToSettings('features')
    }
  }, [featuresStatus])

  // Sync frontend settings to backend on initial connect only.
  // Individual setting controls send their own update_settings messages,
  // so this should NOT re-fire on every settings change (causes infinite loops
  // when backend responds with settings_updated → store update → re-sync).
  useEffect(() => {
    if (connected) {
      const s = useSettingsStore.getState()
      updateSettings({
        ai: {
          enabled: s.ai.enabled,
          provider: s.ai.provider,
          keyword: s.ai.keyword,
          speak_responses: s.ai.speakResponses,
          emoji_mode: s.ai.emojiMode,
        },
        translation: {
          enabled: s.translation.enabled,
          provider: s.translation.provider,
          language_pairs: s.translation.languagePairs.map((p) => ({
            source: p.sourceLanguage,
            target: p.targetLanguage,
          })),
          active_pair_index: s.translation.activePairIndex,
        },
        stt: {
          model: s.stt.model,
        },
        tts: {
          enabled: s.tts.enabled,
          engine: s.tts.engine,
        },
      })
    }
  }, [connected, updateSettings]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-load translator model when translation is enabled (only for local provider)
  useEffect(() => {
    if (connected && settings.translation.enabled && settings.translation.provider === 'local') {
      // Fix stale default model name from older settings
      const validModels = ['nllb-200-distilled-600M', 'nllb-200-distilled-1.3B', 'nllb-200-3.3B']
      const modelId = validModels.includes(settings.translation.model)
        ? settings.translation.model
        : 'nllb-200-distilled-600M'
      loadModel('translation', modelId)
    }
  }, [connected, settings.translation.enabled, settings.translation.provider, settings.translation.model, loadModel])

  // Auto-load RVC model when connected and a model path is saved
  // Only if RVC feature is actually installed (torch + rvc packages present)
  useEffect(() => {
    if (connected && settings.rvc.modelPath && !isRvcModelLoaded) {
      const features = useFeaturesStore.getState().status?.features
      const torchInstalled = features?.['torch_cpu']?.installed || features?.['torch_cuda']?.installed
      const rvcInstalled = features?.['rvc']?.installed
      if (!torchInstalled || !rvcInstalled) {
        console.log('[App] Skipping RVC auto-load: torch=%s rvc=%s', torchInstalled, rvcInstalled)
        // Clear stale model path since features aren't installed
        settings.updateRVC({ modelPath: null, indexPath: null })
        return
      }
      sendMessage({
        type: 'rvc_load_model',
        payload: {
          model_path: settings.rvc.modelPath,
          index_path: settings.rvc.indexPath || undefined,
        },
      })
    }
  }, [connected]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
    <ReconnectBanner connected={connected} reconnectAttempt={reconnectAttempt} />
    <ToastContainer />
    <ModelErrorDialog onNavigateToSettings={() => navigateToSettings('models')} />
    <div className="flex flex-col h-screen bg-background text-foreground">
      <div className="flex flex-row flex-1 min-h-0">

      {/* Menu — left position: full height */}
      {currentView === 'chat' && settings.menuPosition === 'left' && (
        <MenuBar settings={settings} menuPosition={settings.menuPosition} menuAlignment={settings.menuAlignment}
          isListening={isListening} isSpeakerListening={isSpeakerListening} isMicRvcActive={isMicRvcActive}
          isRvcModelLoaded={isRvcModelLoaded} connected={connected}
          startListening={startListening} stopListening={stopListening}
          startSpeakerCapture={startSpeakerCapture} stopSpeakerCapture={stopSpeakerCapture}
          updateSettings={updateSettings} sendMessage={sendMessage}
          navigateToSettings={navigateToSettings} setCurrentView={setCurrentView}
        />
      )}

      {/* Center column: header + menu(top) + content + menu(bottom) */}
      <div className="flex-1 flex flex-col min-h-0">

        {/* Header — always at top of content area */}
        {currentView === 'chat' && (
          <div className="h-14 flex items-center justify-between px-4 border-b border-border shrink-0 overflow-visible">
            <div className="flex items-center gap-2">
              <img src="/stts-icon.png" alt="STTS" className="w-6 h-6" />
              <span className="text-lg font-bold">STTS</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative flex items-center gap-1" ref={langPickerRef}>
                {[...settings.translation.languagePairs]
                  .map((pair, idx) => ({ pair, idx }))
                  .sort((a, b) => {
                    const aActive = a.idx === settings.translation.activePairIndex ? 0 : 1
                    const bActive = b.idx === settings.translation.activePairIndex ? 0 : 1
                    return aActive - bActive
                  })
                  .map(({ pair, idx }) => {
                  const isActive = idx === settings.translation.activePairIndex
                  return (
                    <div key={pair.id} className="relative group">
                      <button
                        onClick={() => {
                          if (isActive) {
                            console.log('[App] Toggle language pair editor', pair.id)
                            setEditingPairId(editingPairId === pair.id ? null : pair.id)
                          } else {
                            console.log('[App] Switch active language pair', idx)
                            settings.setActivePair(idx)
                            const pairs = useSettingsStore.getState().translation.languagePairs
                            updateSettings({ translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: idx } })
                          }
                        }}
                        className={`text-xs font-medium px-2 py-1 rounded transition-colors ${
                          isActive
                            ? 'bg-white text-black'
                            : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700'
                        }`}
                        title={`${getLangLabel(pair.sourceLanguage)} → ${getLangLabel(pair.targetLanguage)}${isActive ? ' (active - click to edit)' : ' (click to activate)'}`}
                      >
                        {getLangShort(pair.sourceLanguage)}→{getLangShort(pair.targetLanguage)}
                      </button>
                      {settings.translation.languagePairs.length > 1 && !isActive && (
                        <span
                          onMouseDown={(e) => {
                            e.stopPropagation()
                            e.preventDefault()
                            settings.removeLanguagePair(pair.id)
                          }}
                          className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-destructive/80 text-destructive-foreground text-[8px] leading-none flex items-center justify-center cursor-pointer z-10 opacity-0 transition-opacity [.group:hover_&]:opacity-100"
                          title="Remove pair"
                        >
                          <X className="w-2 h-2" />
                        </span>
                      )}
                    </div>
                  )
                })}
                <button
                  onClick={() => { console.log('[App] Add language pair clicked'); if (settings.translation.languagePairs.length < 5) setEditingPairId('new') }}
                  className={`p-1 rounded transition-colors ${settings.translation.languagePairs.length < 5 ? 'text-zinc-500 hover:text-zinc-300 hover:bg-secondary cursor-pointer' : 'text-zinc-700 cursor-not-allowed'}`}
                  title={settings.translation.languagePairs.length < 5 ? 'Add language pair' : 'Maximum 5 pairs'}
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>

                {editingPairId && (
                  <LanguagePicker
                    pairId={editingPairId}
                    pairs={settings.translation.languagePairs}
                    onUpdatePair={(id, field, lang) => {
                      settings.updatePairLanguage(id, field, lang)
                      const pairs = useSettingsStore.getState().translation.languagePairs
                      updateSettings({ translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: settings.translation.activePairIndex } })
                    }}
                    onAddPair={(source, target) => {
                      settings.addLanguagePair(source, target)
                      setEditingPairId(null)
                    }}
                    onSwap={(id) => {
                      const pair = settings.translation.languagePairs.find((p) => p.id === id)
                      if (pair) {
                        settings.updatePairLanguage(id, 'sourceLanguage', pair.targetLanguage)
                        const pairs = useSettingsStore.getState().translation.languagePairs
                        updateSettings({ translation: { language_pairs: pairs.map(p => ({ source: p.sourceLanguage, target: p.targetLanguage })), active_pair_index: settings.translation.activePairIndex } })
                      }
                    }}
                    onClose={() => setEditingPairId(null)}
                  />
                )}
              </div>
              {useChatStore.getState().messages.length > 0 && (
                <button
                  onClick={() => { console.log('[App] Clear chat'); useChatStore.getState().clearMessages() }}
                  className="p-1.5 rounded text-muted-foreground hover:text-destructive transition-colors"
                  title="Clear chat"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Menu — top position */}
        {currentView === 'chat' && settings.menuPosition === 'top' && (
          <MenuBar settings={settings} menuPosition={settings.menuPosition} menuAlignment={settings.menuAlignment}
            isListening={isListening} isSpeakerListening={isSpeakerListening} isMicRvcActive={isMicRvcActive}
            isRvcModelLoaded={isRvcModelLoaded} connected={connected}
            startListening={startListening} stopListening={stopListening}
            startSpeakerCapture={startSpeakerCapture} stopSpeakerCapture={stopSpeakerCapture}
            updateSettings={updateSettings} sendMessage={sendMessage}
            navigateToSettings={navigateToSettings} setCurrentView={setCurrentView}
          />
        )}

        {/* Main Content */}
        <div className="flex-1 flex flex-col min-h-0">
          {currentView === 'chat' ? (
            <ChatView />
          ) : (
            <SettingsView onBack={() => { console.log('[App] Back to chat from settings'); setSettingsPage(undefined); setCurrentView('chat') }} initialPage={settingsPage as any} />
          )}
        </div>

        {/* Menu — bottom position */}
        {currentView === 'chat' && settings.menuPosition === 'bottom' && (
          <MenuBar settings={settings} menuPosition={settings.menuPosition} menuAlignment={settings.menuAlignment}
            isListening={isListening} isSpeakerListening={isSpeakerListening} isMicRvcActive={isMicRvcActive}
            isRvcModelLoaded={isRvcModelLoaded} connected={connected}
            startListening={startListening} stopListening={stopListening}
            startSpeakerCapture={startSpeakerCapture} stopSpeakerCapture={stopSpeakerCapture}
            updateSettings={updateSettings} sendMessage={sendMessage}
            navigateToSettings={navigateToSettings} setCurrentView={setCurrentView}
          />
        )}

      </div>

      {/* Menu — right position: full height */}
      {currentView === 'chat' && settings.menuPosition === 'right' && (
        <MenuBar settings={settings} menuPosition={settings.menuPosition} menuAlignment={settings.menuAlignment}
          isListening={isListening} isSpeakerListening={isSpeakerListening} isMicRvcActive={isMicRvcActive}
          isRvcModelLoaded={isRvcModelLoaded} connected={connected}
          startListening={startListening} stopListening={stopListening}
          startSpeakerCapture={startSpeakerCapture} stopSpeakerCapture={stopSpeakerCapture}
          updateSettings={updateSettings} sendMessage={sendMessage}
          navigateToSettings={navigateToSettings} setCurrentView={setCurrentView}
        />
      )}

      </div>
      <StatusBar
        connected={connected}
        audioLevel={audioLevel}
        detectedLanguage={detectedLanguage}
        speakerCapturing={isSpeakerListening}
        ttsEngine={status?.tts?.engine as string | undefined}
      />
    </div>
    </>
  )
}

interface LanguagePickerProps {
  pairId: string | 'new'
  pairs: import('@/stores/settingsStore').LanguagePair[]
  onUpdatePair: (id: string, field: 'sourceLanguage' | 'targetLanguage', language: string) => void
  onAddPair: (source: string, target: string) => void
  onSwap: (id: string) => void
  onClose: () => void
}

function LanguagePicker({ pairId, pairs, onUpdatePair, onAddPair, onSwap }: LanguagePickerProps) {
  const [editingField, setEditingField] = useState<'source' | 'target' | null>(null)
  const [newSource, setNewSource] = useState('eng_Latn')
  const [newTarget, setNewTarget] = useState('jpn_Jpan')

  const isNew = pairId === 'new'
  const existingPair = !isNew ? pairs.find((p) => p.id === pairId) : null
  const sourceLanguage = isNew ? newSource : (existingPair?.sourceLanguage || 'eng_Latn')
  const targetLanguage = isNew ? newTarget : (existingPair?.targetLanguage || 'jpn_Jpan')

  if (editingField) {
    return (
      <div className="absolute right-full mr-2 top-0 bg-background border border-border rounded-lg shadow-lg p-2 w-48 max-h-80 overflow-y-auto z-50">
        <p className="text-xs text-muted-foreground px-2 py-1 font-medium">
          {editingField === 'source' ? 'You speak:' : 'Translate to:'}
        </p>
        {LANGUAGES.map((lang) => (
          <button
            key={lang.value}
            onClick={() => {
              if (isNew) {
                if (editingField === 'source') setNewSource(lang.value)
                else setNewTarget(lang.value)
              } else if (existingPair) {
                onUpdatePair(existingPair.id, editingField === 'source' ? 'sourceLanguage' : 'targetLanguage', lang.value)
              }
              setEditingField(null)
            }}
            className={`w-full text-left px-2 py-1.5 text-sm rounded hover:bg-secondary transition-colors ${
              (editingField === 'source' ? sourceLanguage : targetLanguage) === lang.value
                ? 'bg-primary/10 text-primary font-medium'
                : ''
            }`}
          >
            {lang.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="absolute right-full mr-2 top-0 bg-background border border-border rounded-lg shadow-lg p-3 w-52 z-50">
      <button
        onClick={() => setEditingField('source')}
        className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-secondary transition-colors text-left"
      >
        <div>
          <p className="text-xs text-muted-foreground">You speak</p>
          <p className="text-sm font-medium">{getLangLabel(sourceLanguage)}</p>
        </div>
        <span className="text-xs text-muted-foreground">{getLangShort(sourceLanguage)}</span>
      </button>

      <div className="flex items-center justify-center my-1">
        <button
          onClick={() => {
            if (isNew) {
              setNewSource(newTarget)
              setNewTarget(newSource)
            } else if (existingPair) {
              onSwap(existingPair.id)
            }
          }}
          className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
          title="Swap languages"
        >
          <ArrowLeftRight className="w-3.5 h-3.5 text-muted-foreground rotate-90" />
        </button>
      </div>

      <button
        onClick={() => setEditingField('target')}
        className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-secondary transition-colors text-left"
      >
        <div>
          <p className="text-xs text-muted-foreground">Translate to</p>
          <p className="text-sm font-medium">{getLangLabel(targetLanguage)}</p>
        </div>
        <span className="text-xs text-muted-foreground">{getLangShort(targetLanguage)}</span>
      </button>

      {isNew && (
        <button
          onClick={() => onAddPair(newSource, newTarget)}
          className="w-full mt-2 py-1.5 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Add Pair
        </button>
      )}
    </div>
  )
}

interface ToggleControlProps {
  icon: React.ReactNode
  label: string
  enabled: boolean
  onClick?: () => void
  disabled?: boolean
  onDisabledClick?: () => void
}

function ToggleControl({ icon, label, enabled, onClick, disabled, onDisabledClick }: ToggleControlProps) {
  const isDisabled = disabled && !onDisabledClick
  return (
    <button
      className={`flex flex-col items-center gap-1 ${isDisabled ? 'opacity-50' : ''}`}
      onClick={() => {
        if (disabled && onDisabledClick) {
          onDisabledClick()
        } else if (!disabled && onClick) {
          onClick()
        }
      }}
      disabled={isDisabled}
    >
      <div
        className={`p-2 rounded-lg transition-colors ${
          enabled ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground'
        } ${(onClick && !disabled) || onDisabledClick ? 'hover:bg-primary/80 cursor-pointer' : ''}`}
      >
        {icon}
      </div>
      <span className="text-xs text-muted-foreground">{label}</span>
    </button>
  )
}

export default App
