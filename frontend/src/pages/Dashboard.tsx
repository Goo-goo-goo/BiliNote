import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Provider, TaskStatusDoc } from '../lib/api'
import { fmtDuration, fmtPercent, platformLabel } from '../lib/format'
import { Band, Button, Check, Empty, Field, Panel, ProgressRail, Select, TextArea, useToast } from '../components/ui'
import { useApp } from '../state/store'

function detectPlatform(url: string): string {
  const u = url.toLowerCase()
  if (u.includes('bilibili.com') || u.includes('b23.tv')) return 'bilibili'
  if (u.includes('youtube.com') || u.includes('youtu.be')) return 'youtube'
  if (u.includes('douyin.com') || u.includes('v.douyin.com')) return 'douyin'
  if (u.includes('kuaishou.com')) return 'kuaishou'
  return ''
}

const STYLE_OPTIONS = [
  { value: 'detailed', label: '详细' },
  { value: 'minimal', label: '精简' },
  { value: 'academic', label: '学术' },
  { value: 'tutorial', label: '教程' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'life_journal', label: '生活向' },
  { value: 'task_oriented', label: '任务导向' },
  { value: 'business', label: '商业风格' },
  { value: 'meeting_minutes', label: '会议纪要' },
]

const FORMAT_OPTIONS = [
  { value: 'toc', label: '目录' },
  { value: 'link', label: '原片跳转' },
  { value: 'screenshot', label: '原片截图' },
  { value: 'summary', label: 'AI总结' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const toast = useToast()
  const { defaultProviderId, defaultModelName, setDefaults } = useApp()

  const [url, setUrl] = useState('')
  const [style, setStyle] = useState('detailed')
  const [formats, setFormats] = useState<string[]>(['toc', 'link', 'summary'])
  const [extras, setExtras] = useState('')
  const [showOptions, setShowOptions] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [models, setModels] = useState<string[]>([])
  const [providerId, setProviderId] = useState(defaultProviderId)
  const [modelName, setModelName] = useState(defaultModelName)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [tasks, setTasks] = useState<TaskStatusDoc[]>([])

  const platform = useMemo(() => detectPlatform(url), [url])

  const refreshTasks = () => {
    api
      .listTasks(30)
      .then(setTasks)
      .catch(() => setTasks([]))
  }

  useEffect(() => {
    refreshTasks()
    const timer = window.setInterval(refreshTasks, 3000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    api
      .listProviders()
      .then((list) => {
        setProviders(list)
        if (!providerId && list.length) {
          setProviderId(String(list[0].id))
        }
      })
      .catch(() => setProviders([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!providerId) return
    api
      .modelListByProvider(providerId)
      .then((r) => {
        const names = r.models.map((m) => m.id)
        setModels(names)
        if (!names.includes(modelName)) setModelName(names[0] || '')
      })
      .catch(() => setModels([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId])

  const toggleFormat = (value: string) => {
    setFormats((prev) => (prev.includes(value) ? prev.filter((f) => f !== value) : [...prev, value]))
  }

  const submit = async () => {
    setError('')
    if (!url.trim()) {
      setError('先贴一个视频链接。')
      return
    }
    if (!platform) {
      setError('没认出这个链接支持的平台（支持 B站 / YouTube / 抖音 / 快手 / 本地文件）。')
      return
    }
    if (!providerId || !modelName) {
      setError('还没有可用的模型：到「设置」里添加供应商与模型，或在上方选择。')
      return
    }
    setSubmitting(true)
    try {
      setDefaults(providerId, modelName)
      const res = await api.generateNote({
        video_url: url.trim(),
        platform,
        quality: 'medium',
        model_name: modelName,
        provider_id: providerId,
        link: formats.includes('link'),
        screenshot: formats.includes('screenshot'),
        format: formats,
        style,
        extras: extras.trim() || null,
      })
      toast(`任务已提交（${res.task_id.slice(0, 8)}…）`)
      setUrl('')
      navigate('/tasks')
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const running = tasks.filter((t) => !t.finished)
  const recent = tasks.filter((t) => t.finished).slice(0, 5)

  return (
    <div className="page">
      {/* 工作台 hero：贴链接即主操作 */}
      <div className="hero">
        <div className="hero-title">把视频，变成带时间戳的 Markdown 笔记。</div>
        <div className="hero-sub">贴一个链接，从下载一路走到结构化笔记。</div>

        <div className="hero-form">
          <div className="hero-field">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.bilibili.com/video/BV…"
              aria-label="视频链接"
              onKeyDown={(e) => {
                if (e.key === 'Enter') submit()
              }}
            />
            <Button onClick={submit} disabled={submitting}>
              {submitting ? '提交中…' : '生成笔记'}
            </Button>
          </div>
        </div>
        <div className="hero-hint">
          {platform ? `识别为 ${platformLabel(platform)}` : '支持 B站 / YouTube / 抖音 / 快手'}
        </div>
        {error && <p className="inline-error">{error}</p>}
        <div className="hero-flow">下载 → 转写 → Markdown 笔记</div>
      </div>

      <Panel
        title="笔记选项"
        extra={
          <Button variant="quiet" size="sm" onClick={() => setShowOptions(!showOptions)}>
            {showOptions ? '收起选项' : '更多选项'}
          </Button>
        }
      >
        <div className="stack">
          <div className="form-grid">
            <Field label="模型供应商">
              <Select
                value={providerId}
                onChange={setProviderId}
                placeholder="选择供应商"
                options={providers.map((p) => ({ value: String(p.id), label: `${p.name}（${p.type}）` }))}
              />
            </Field>
            <Field label="模型">
              <Select
                value={modelName}
                onChange={setModelName}
                placeholder="选择模型"
                options={models.map((m) => ({ value: m, label: m }))}
              />
            </Field>
            <Field label="笔记风格">
              <Select value={style} onChange={setStyle} options={STYLE_OPTIONS} />
            </Field>
          </div>

          {showOptions && (
            <>
              <Field label="输出能力">
                <div className="checks">
                  {FORMAT_OPTIONS.map((f) => (
                    <Check
                      key={f.value}
                      checked={formats.includes(f.value)}
                      onChange={() => toggleFormat(f.value)}
                      label={f.label}
                    />
                  ))}
                </div>
              </Field>
              <Field label="额外要求" hint="会作为必须满足的补充指令传给模型">
                <TextArea value={extras} onChange={setExtras} placeholder="例如：多保留公式推导；忽略广告部分" />
              </Field>
            </>
          )}
        </div>
      </Panel>

      <Band title="进行中的任务" flush>
        {running.length === 0 ? (
          <Empty headline="现在没有跑着的任务" hint="上面贴一个视频链接就能开始。" />
        ) : (
          <div className="rows">
            {running.map((t) => (
              <div className="row" key={t.task_id}>
                <div className="grow">
                  <div className="title">
                    {t.label} · {t.message}
                  </div>
                  <div className="desc">
                    {t.detail || `第 ${t.step}/${t.total_steps} 步`}
                    {t.stale_seconds > 120 ? ` · 已 ${fmtDuration(t.stale_seconds)} 没有新动静` : ''}
                  </div>
                </div>
                <div style={{ width: 180 }}>
                  <ProgressRail value={t.progress} cue />
                </div>
                <span className="small mono soft">{fmtPercent(t.progress)}</span>
              </div>
            ))}
          </div>
        )}
      </Band>

      <Band title="最近完成" flush>
        {recent.length === 0 ? (
          <Empty headline="还没有完成的笔记" hint="生成完成后会出现在这里。" />
        ) : (
          <div className="rows">
            {recent.map((t) => (
              <div
                className="row"
                key={t.task_id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/notes/${t.task_id}`)}
              >
                <div className="grow">
                  <div className="title">{t.result?.audio_meta?.title || t.task_id}</div>
                  <div className="desc">{t.message}</div>
                </div>
                <span className="pill ok">完成</span>
              </div>
            ))}
          </div>
        )}
      </Band>
    </div>
  )
}
