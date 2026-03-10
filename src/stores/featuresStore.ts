import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface FeatureInfo {
  id: string
  name: string
  description: string
  installed: boolean
  requires_torch: boolean
  torch_installed: boolean
  version?: string
}

export interface FeaturesStatus {
  features: Record<string, FeatureInfo>
  python_available: boolean
  is_frozen: boolean
  error?: string
}

export interface FeatureInstallProgress {
  detail: string
  timestamp: number
}

export interface FeatureInstallResult {
  success: boolean
  feature?: string
  error?: string
  timestamp: number
  restart_needed?: boolean
}

export interface FeatureUninstallResult {
  success: boolean
  feature: string
  error?: string
  timestamp: number
}

interface FeaturesStore {
  status: FeaturesStatus | null
  setStatus: (status: FeaturesStatus) => void

  // Persisted cache of feature install results (survives page refresh)
  cachedResults: Record<string, 'success' | 'error'>
  setCachedResults: (results: Record<string, 'success' | 'error'>) => void
  updateCachedResult: (featureId: string, result: 'success' | 'error') => void
  removeCachedResult: (featureId: string) => void

  // Track recently uninstalled features so setStatus doesn't re-mark them
  recentlyUninstalled: Set<string>

  // VOICEVOX engine install state (shared across components, persisted)
  voicevoxInstalled: boolean | null
  setVoicevoxInstalled: (installed: boolean | null) => void

  // Whether we've received features_status from backend at least once this session
  statusReceived: boolean
  setStatusReceived: (received: boolean) => void

  // Install/uninstall event state (replaces lastMessage pattern)
  installProgress: FeatureInstallProgress | null
  installResult: FeatureInstallResult | null
  uninstallResult: FeatureUninstallResult | null
  setInstallProgress: (progress: FeatureInstallProgress) => void
  setInstallResult: (result: FeatureInstallResult) => void
  setUninstallResult: (result: FeatureUninstallResult) => void

  // Persisted queue for resuming installs after torch restart
  pendingInstallQueue: string[]
  setPendingInstallQueue: (queue: string[]) => void
  clearPendingInstallQueue: () => void
}

export const useFeaturesStore = create<FeaturesStore>()(
  persist(
    (set) => ({
      status: null,
      recentlyUninstalled: new Set(),
      setStatus: (status) => {
        console.log('[featuresStore] setStatus called, features:', Object.keys(status?.features || {}))
        const recentlyUninstalled = useFeaturesStore.getState().recentlyUninstalled
        // Also update cachedResults from backend truth
        const newCached: Record<string, 'success' | 'error'> = {}
        if (status?.features) {
          for (const [fid, info] of Object.entries(status.features)) {
            if (info.installed) {
              // Don't re-mark features that were just uninstalled
              if (recentlyUninstalled.has(fid)) {
                console.log('[featuresStore] Skipping recently uninstalled feature:', fid)
                continue
              }
              newCached[fid] = 'success'
            }
          }
        }
        console.log('[featuresStore] Updating cachedResults from backend:', JSON.stringify(newCached))
        set({ status, cachedResults: newCached, statusReceived: true })
      },

      cachedResults: {},
      setCachedResults: (results) => {
        console.log('[featuresStore] setCachedResults:', JSON.stringify(results))
        set({ cachedResults: results })
      },
      updateCachedResult: (featureId, result) => {
        console.log('[featuresStore] updateCachedResult:', featureId, result)
        set((state) => ({
          cachedResults: { ...state.cachedResults, [featureId]: result },
        }))
      },
      removeCachedResult: (featureId) => {
        console.log('[featuresStore] removeCachedResult:', featureId)
        set((state) => {
          const copy = { ...state.cachedResults }
          delete copy[featureId]
          // Track as recently uninstalled so setStatus doesn't re-mark it
          const newRecent = new Set(state.recentlyUninstalled)
          newRecent.add(featureId)
          return { cachedResults: copy, recentlyUninstalled: newRecent }
        })
        // Auto-clear after 10s so future status checks work normally
        setTimeout(() => {
          const store = useFeaturesStore.getState()
          if (store.recentlyUninstalled.has(featureId)) {
            console.log('[featuresStore] Clearing recentlyUninstalled:', featureId)
            const newRecent = new Set(store.recentlyUninstalled)
            newRecent.delete(featureId)
            useFeaturesStore.setState({ recentlyUninstalled: newRecent })
          }
        }, 10000)
      },

      voicevoxInstalled: null,
      setVoicevoxInstalled: (installed) => {
        console.log('[featuresStore] setVoicevoxInstalled:', installed)
        set({ voicevoxInstalled: installed })
      },

      statusReceived: false,
      setStatusReceived: (received) => set({ statusReceived: received }),

      installProgress: null,
      installResult: null,
      uninstallResult: null,
      setInstallProgress: (progress) => set({ installProgress: progress }),
      setInstallResult: (result) => set({ installResult: result }),
      setUninstallResult: (result) => set({ uninstallResult: result }),

      pendingInstallQueue: [],
      setPendingInstallQueue: (queue) => {
        console.log('[featuresStore] setPendingInstallQueue:', queue)
        set({ pendingInstallQueue: queue })
      },
      clearPendingInstallQueue: () => {
        console.log('[featuresStore] clearPendingInstallQueue')
        set({ pendingInstallQueue: [] })
      },
    }),
    {
      name: 'stts-features',
      version: 2,
      // Persist cachedResults, voicevoxInstalled, and pendingInstallQueue (survives restart)
      partialize: (state) => ({
        cachedResults: state.cachedResults,
        voicevoxInstalled: state.voicevoxInstalled,
        pendingInstallQueue: state.pendingInstallQueue,
      }),
    }
  )
)
