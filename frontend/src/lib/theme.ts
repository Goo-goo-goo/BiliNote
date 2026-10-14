// 主题：跟随系统 / 浅色 / 深色，持久化到 localStorage。
// data-theme 由 index.html 的内联脚本在首帧设置（防闪烁），这里负责切换与跟随系统。
export type ThemeMode = 'system' | 'light' | 'dark'

const KEY = 'bilinote.theme'

export function getThemeMode(): ThemeMode {
  const v = localStorage.getItem(KEY)
  return v === 'light' || v === 'dark' ? v : 'system'
}

export function setThemeMode(mode: ThemeMode) {
  localStorage.setItem(KEY, mode)
  applyTheme()
}

/** 当前实际生效的主题（system 模式解析后） */
export function currentTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function applyTheme() {
  const mode = getThemeMode()
  const dark =
    mode === 'dark' ||
    (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}

/** 跟随系统时监听系统主题变化 */
export function watchSystemTheme() {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', () => {
    if (getThemeMode() === 'system') applyTheme()
  })
}
