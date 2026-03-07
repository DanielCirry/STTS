import { create } from 'zustand'

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

  // Install/uninstall event state (replaces lastMessage pattern)
  installProgress: FeatureInstallProgress | null
  installResult: FeatureInstallResult | null
  uninstallResult: FeatureUninstallResult | null
  setInstallProgress: (progress: FeatureInstallProgress) => void
  setInstallResult: (result: FeatureInstallResult) => void
  setUninstallResult: (result: FeatureUninstallResult) => void
}

export const useFeaturesStore = create<FeaturesStore>()((set) => ({
  status: null,
  setStatus: (status) => set({ status }),

  installProgress: null,
  installResult: null,
  uninstallResult: null,
  setInstallProgress: (progress) => set({ installProgress: progress }),
  setInstallResult: (result) => set({ installResult: result }),
  setUninstallResult: (result) => set({ uninstallResult: result }),
}))
