import { create } from 'zustand'
import { getBaseUrl, setBaseUrl } from '../lib/api'

interface AppState {
  server: string
  setServer: (url: string) => void
  defaultProviderId: string
  defaultModelName: string
  setDefaults: (providerId: string, modelName: string) => void
  toast: string | null
  showToast: (msg: string) => void
}

export const useApp = create<AppState>((set) => ({
  server: getBaseUrl(),
  setServer: (url) => {
    setBaseUrl(url)
    set({ server: getBaseUrl() })
  },
  defaultProviderId: localStorage.getItem('bilinote.provider') || '',
  defaultModelName: localStorage.getItem('bilinote.model') || '',
  setDefaults: (providerId, modelName) => {
    localStorage.setItem('bilinote.provider', providerId)
    localStorage.setItem('bilinote.model', modelName)
    set({ defaultProviderId: providerId, defaultModelName: modelName })
  },
  toast: null,
  showToast: (msg) => {
    set({ toast: msg })
    setTimeout(() => set({ toast: null }), 2600)
  },
}))
