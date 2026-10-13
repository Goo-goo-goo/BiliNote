// 通用组件套件：面板 / 行 / 表单 / 时间码 / 进度 / 提示
import React, { createContext, useContext, useEffect, useRef, useState } from 'react'

// ---------- 提示 ----------
const ToastCtx = createContext<(msg: string) => void>(() => {})

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const show = (msg: string) => {
    setToast(msg)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setToast(null), 2600)
  }
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast && <div className="toast">{toast}</div>}
    </ToastCtx.Provider>
  )
}

export function useToast() {
  return useContext(ToastCtx)
}

// ---------- 按钮 ----------
export function Button(props: {
  children: React.ReactNode
  onClick?: () => void
  variant?: 'primary' | 'quiet' | 'danger' | 'cue'
  size?: 'sm' | 'md'
  disabled?: boolean
  type?: 'button' | 'submit'
  title?: string
}) {
  const cls = [
    'btn',
    props.variant === 'quiet' ? 'quiet' : '',
    props.variant === 'danger' ? 'danger' : '',
    props.variant === 'cue' ? 'cue' : '',
    props.size === 'sm' ? 'small' : '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button
      className={cls}
      type={props.type || 'button'}
      onClick={props.onClick}
      disabled={props.disabled}
      title={props.title}
    >
      {props.children}
    </button>
  )
}

// ---------- 面板 ----------
export function Panel(props: {
  title?: string
  extra?: React.ReactNode
  children: React.ReactNode
  flush?: boolean
}) {
  return (
    <section className="panel">
      {(props.title || props.extra) && (
        <header>
          <h2>{props.title}</h2>
          {props.extra}
        </header>
      )}
      <div className={props.flush ? 'body flush' : 'body'}>{props.children}</div>
    </section>
  )
}

export function Empty(props: { headline: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="empty">
      <div className="headline">{props.headline}</div>
      {props.hint && <p className="hint">{props.hint}</p>}
      {props.action && <div className="empty-action">{props.action}</div>}
    </div>
  )
}

// ---------- 无框内容流（三档层级里的 band） ----------
export function Band(props: {
  title?: string
  extra?: React.ReactNode
  children: React.ReactNode
  flush?: boolean
}) {
  return (
    <section className="band">
      {(props.title || props.extra) && (
        <header>
          <h2>{props.title}</h2>
          {props.extra}
        </header>
      )}
      <div className={props.flush ? 'body flush' : 'body'}>{props.children}</div>
    </section>
  )
}

// ---------- 时间码 ----------
export function Timecode(props: {
  value?: string
  onClick?: () => void
  hot?: boolean
  title?: string
}) {
  const text = cueLabel(props.value)
  if (!text) return null
  const cls = ['timecode', props.onClick ? 'clickable' : '', props.hot ? 'hot' : '']
    .filter(Boolean)
    .join(' ')
  return (
    <span className={cls} onClick={props.onClick} title={props.title || props.value}>
      {text}
    </span>
  )
}

function cueLabel(hms?: string): string {
  if (!hms) return ''
  const parts = hms.split(':').map(Number)
  if (parts.some((n) => Number.isNaN(n))) return ''
  const seconds = parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1]
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

// ---------- 状态徽记 ----------
export function Pill(props: { kind?: 'ok' | 'fail' | 'run' | 'idle'; children: React.ReactNode }) {
  const cls = ['pill', props.kind === 'ok' ? 'ok' : '', props.kind === 'fail' ? 'fail' : '', props.kind === 'run' ? 'run' : '']
    .filter(Boolean)
    .join(' ')
  return <span className={cls}>{props.children}</span>
}

// ---------- 进度 ----------
export function ProgressRail(props: { value: number; cue?: boolean }) {
  const pct = Math.max(0, Math.min(1, props.value)) * 100
  return (
    <div className={props.cue ? 'progress-rail cue' : 'progress-rail'}>
      <i style={{ width: `${pct}%` }} />
    </div>
  )
}

export function StepDots(props: { step: number; total: number }) {
  return (
    <div className="step-dots">
      {Array.from({ length: props.total }, (_, i) => (
        <span key={i} className={i + 1 < props.step ? 'done' : i + 1 === props.step ? 'now' : ''} />
      ))}
    </div>
  )
}

// ---------- 表单 ----------
export function Field(props: {
  label: string
  children: React.ReactNode
  hint?: string
}) {
  return (
    <div className="field">
      <label>{props.label}</label>
      {props.children}
      {props.hint && <span className="small soft">{props.hint}</span>}
    </div>
  )
}

export function TextInput(props: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  mono?: boolean
  type?: string
  onKeyDown?: (e: React.KeyboardEvent) => void
}) {
  return (
    <input
      className={props.mono ? 'input mono' : 'input'}
      type={props.type || 'text'}
      value={props.value}
      placeholder={props.placeholder}
      onChange={(e) => props.onChange(e.target.value)}
      onKeyDown={props.onKeyDown}
    />
  )
}

export function Select(props: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
}) {
  return (
    <select className="input" value={props.value} onChange={(e) => props.onChange(e.target.value)}>
      {props.placeholder && <option value="">{props.placeholder}</option>}
      {props.options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function TextArea(props: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <textarea
      className="input"
      value={props.value}
      placeholder={props.placeholder}
      onChange={(e) => props.onChange(e.target.value)}
    />
  )
}

export function Check(props: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="check">
      <input type="checkbox" checked={props.checked} onChange={(e) => props.onChange(e.target.checked)} />
      {props.label}
    </label>
  )
}

// ---------- 对话框 ----------
export function Modal(props: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') props.onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [props])

  return (
    <div className="modal-backdrop" onClick={props.onClose}>
      <div
        className="panel"
        style={{ width: 'min(560px, 92vw)', maxHeight: '84vh', overflow: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>{props.title}</h2>
          <Button variant="quiet" size="sm" onClick={props.onClose}>
            关闭
          </Button>
        </header>
        <div className="body">{props.children}</div>
      </div>
    </div>
  )
}
