// 展示格式化：时间码是本站的一等公民（字幕 cue 语汇）

export function hmsToSeconds(value?: string): number | null {
  if (!value) return null
  const parts = value.split(':').map(Number)
  if (parts.some((n) => Number.isNaN(n))) return null
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return null
}

/** HH:MM:SS → mm:ss（总分钟，字幕 cue 风格） */
export function cueTime(hms?: string): string {
  const seconds = hmsToSeconds(hms)
  if (seconds === null) return ''
  const mm = Math.floor(seconds / 60)
  const ss = seconds % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function fmtDuration(seconds?: number): string {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} 秒`
  const mm = Math.floor(s / 60)
  const ss = s % 60
  if (mm < 60) return ss ? `${mm} 分 ${ss} 秒` : `${mm} 分`
  return `${Math.floor(mm / 60)} 时 ${mm % 60} 分`
}

export function fmtPercent(value?: number): string {
  if (value == null) return '0%'
  return `${Math.round(value * 100)}%`
}

export function fmtTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function platformLabel(platform?: string): string {
  const map: Record<string, string> = {
    bilibili: 'B站',
    youtube: 'YouTube',
    douyin: '抖音',
    kuaishou: '快手',
    local: '本地',
  }
  return map[platform || ''] || platform || '—'
}

export const QTYPE_LABEL: Record<string, string> = {
  single: '单选',
  judge: '判断',
  fill: '填空',
  calc: '计算/简答',
}

export const DIFFICULTY_LABEL: Record<string, string> = {
  basic: '基础',
  medium: '中档',
  advanced: '拔高',
}
