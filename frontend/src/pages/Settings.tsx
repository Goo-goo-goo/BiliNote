import { useEffect, useState } from 'react'
import { api, downloadExport, Provider } from '../lib/api'
import { Button, Check, Empty, Field, Panel, Select, TextInput, useToast } from '../components/ui'
import { useApp } from '../state/store'

export default function Settings() {
  const toast = useToast()
  const { server, setServer } = useApp()

  return (
    <div className="page">
      <ServerPanel server={server} onSave={setServer} />
      <ProviderPanel />
      <TranscriberPanel />
      <ProxyPanel />
      <CookiePanel />
      <HealthPanel />
      <ArchivePanel toast={toast} />
    </div>
  )
}

function ServerPanel({ server, onSave }: { server: string; onSave: (v: string) => void }) {
  const [value, setValue] = useState(server)
  return (
    <Panel title="后端服务">
      <div className="rowflex" style={{ alignItems: 'flex-end' }}>
        <div style={{ flex: 1 }}>
          <Field label="服务地址" hint="BiliNote 后端 API 的地址，默认 http://localhost:8483">
            <TextInput value={value} onChange={setValue} mono />
          </Field>
        </div>
        <Button onClick={() => onSave(value.trim())}>保存</Button>
      </div>
    </Panel>
  )
}

function ProviderPanel() {
  const toast = useToast()
  const [providers, setProviders] = useState<Provider[]>([])
  const [name, setName] = useState('')
  const [type, setType] = useState('openai')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [models, setModels] = useState<Record<string, string[]>>({})
  const [newModel, setNewModel] = useState<Record<string, string>>({})

  const refresh = () => {
    api.listProviders().then(setProviders).catch(() => setProviders([]))
  }
  useEffect(refresh, [])

  const loadModels = (providerId: string) => {
    api
      .modelListByProvider(providerId)
      .then((list) => setModels((m) => ({ ...m, [providerId]: list.map((x) => x.id) })))
      .catch(() => {})
  }

  const add = async () => {
    if (!name.trim() || !baseUrl.trim() || !apiKey.trim()) {
      toast('名称、接口地址、API Key 都要填')
      return
    }
    await api.addProvider({ name: name.trim(), type, base_url: baseUrl.trim(), api_key: apiKey.trim() })
    toast('供应商已保存到 SQLite')
    setName('')
    setApiKey('')
    refresh()
  }

  const test = async (p: Provider) => {
    try {
      await api.connectTest(String(p.id))
      toast(`${p.name} 连接正常`)
    } catch (e) {
      toast(e instanceof Error ? e.message : '连接失败')
    }
  }

  return (
    <Panel title="模型供应商" extra={<span className="small soft">密钥存 SQLite，不进 .env</span>}>
      <div className="stack">
        <div className="form-grid">
          <Field label="名称">
            <TextInput value={name} onChange={setName} placeholder="例如 DeepSeek" />
          </Field>
          <Field label="类型">
            <Select
              value={type}
              onChange={setType}
              options={[
                { value: 'openai', label: 'OpenAI 兼容' },
                { value: 'deepseek', label: 'DeepSeek' },
                { value: 'qwen', label: '通义千问' },
                { value: 'kimi', label: 'Kimi' },
                { value: 'ollama', label: 'Ollama 本地' },
              ]}
            />
          </Field>
          <Field label="接口地址 base_url">
            <TextInput value={baseUrl} onChange={setBaseUrl} mono placeholder="https://api.deepseek.com/v1" />
          </Field>
          <Field label="API Key">
            <TextInput value={apiKey} onChange={setApiKey} mono type="password" placeholder="sk-…" />
          </Field>
        </div>
        <div>
          <Button onClick={add}>添加供应商</Button>
        </div>

        {providers.length === 0 ? (
          <Empty headline="还没有供应商" hint="添加后才能生成笔记、出题和复习资料。" />
        ) : (
          <div className="rows">
            {providers.map((p) => (
              <div className="row" key={p.id} style={{ flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
                <div className="rowflex">
                  <div className="grow">
                    <div className="title">
                      {p.name} <span className="tag">{p.type}</span>
                    </div>
                    <div className="desc mono">{p.base_url}</div>
                  </div>
                  <Button variant="quiet" size="sm" onClick={() => loadModels(String(p.id))}>
                    查看模型
                  </Button>
                  <Button variant="quiet" size="sm" onClick={() => test(p)}>
                    测试连接
                  </Button>
                </div>
                <div className="rowflex">
                  <TextInput
                    value={newModel[p.id] || ''}
                    onChange={(v) => setNewModel((m) => ({ ...m, [p.id]: v }))}
                    placeholder="手动登记模型名"
                  />
                  <Button
                    size="sm"
                    onClick={async () => {
                      const model = (newModel[p.id] || '').trim()
                      if (!model) return
                      await api.addModel({ provider_id: String(p.id), model_name: model })
                      toast('模型已登记')
                      setNewModel((m) => ({ ...m, [p.id]: '' }))
                      loadModels(String(p.id))
                    }}
                  >
                    登记
                  </Button>
                </div>
                {models[p.id] && (
                  <div className="rowflex" style={{ flexWrap: 'wrap' }}>
                    {models[p.id].map((m) => (
                      <span className="tag" key={m}>
                        {m}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  )
}

function TranscriberPanel() {
  const toast = useToast()
  const [cfg, setCfg] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<Record<string, { model_size: string; downloaded: boolean; downloading: boolean; failed: boolean; error?: string }[]>>({})
  const [customName, setCustomName] = useState('')
  const [customTarget, setCustomTarget] = useState('')

  const refresh = () => {
    api.transcriberConfig().then((c) => setCfg(c as Record<string, string>)).catch(() => {})
    api.transcriberModelsStatus().then(setStatus).catch(() => {})
  }
  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, 3000)
    return () => window.clearInterval(timer)
  }, [])

  const save = async () => {
    await api.updateTranscriberConfig(cfg)
    toast('转写配置已保存')
    refresh()
  }

  return (
    <Panel title="语音转写">
      <div className="stack">
        <div className="form-grid">
          <Field label="转写引擎">
            <Select
              value={cfg.transcriber_type || 'fast-whisper'}
              onChange={(v) => setCfg({ ...cfg, transcriber_type: v })}
              options={[
                { value: 'fast-whisper', label: 'fast-whisper（本地）' },
                { value: 'mlx-whisper', label: 'mlx-whisper（Apple 芯片）' },
                { value: 'groq', label: 'Groq（云端）' },
                { value: 'bcut', label: '必剪 BCut' },
                { value: 'kuaishou', label: '快手' },
                { value: 'openai-api', label: 'OpenAI 兼容 ASR' },
              ]}
            />
          </Field>
          <Field label="Whisper 模型">
            <Select
              value={cfg.whisper_model_size || 'tiny'}
              onChange={(v) => setCfg({ ...cfg, whisper_model_size: v })}
              options={[
                { value: 'tiny', label: 'tiny（约 75MB，快）' },
                { value: 'base', label: 'base' },
                { value: 'small', label: 'small' },
                { value: 'medium', label: 'medium' },
                { value: 'large-v3', label: 'large-v3（准，重）' },
              ]}
            />
          </Field>
          {cfg.transcriber_type === 'openai-api' && (
            <>
              <Field label="ASR 接口地址">
                <TextInput value={cfg.openai_api_base_url || ''} onChange={(v) => setCfg({ ...cfg, openai_api_base_url: v })} mono />
              </Field>
              <Field label="ASR API Key">
                <TextInput value={cfg.openai_api_key || ''} onChange={(v) => setCfg({ ...cfg, openai_api_key: v })} mono type="password" />
              </Field>
              <Field label="ASR 模型名">
                <TextInput value={cfg.openai_api_model || ''} onChange={(v) => setCfg({ ...cfg, openai_api_model: v })} mono />
              </Field>
            </>
          )}
        </div>
        <div>
          <Button onClick={save}>保存转写配置</Button>
        </div>

        <div>
          <div className="spread" style={{ marginBottom: 8 }}>
            <strong>Whisper 模型下载</strong>
            <span className="small soft">默认 ModelScope 国内源，失败自动回退 hf-mirror</span>
          </div>
          <div className="rows">
            {(status.whisper || []).map((m) => (
              <div className="row" key={m.model_size}>
                <div className="grow">
                  <div className="title mono">faster-whisper-{m.model_size}</div>
                  <div className="desc">
                    {m.downloaded ? '已下载' : m.downloading ? '下载中…' : m.failed ? `失败：${m.error || ''}` : '未下载'}
                  </div>
                </div>
                <Button
                  size="sm"
                  disabled={m.downloading}
                  onClick={async () => {
                    try {
                      await api.transcriberDownload(m.model_size)
                      toast('开始下载')
                      refresh()
                    } catch (e) {
                      toast(e instanceof Error ? e.message : '下载失败')
                    }
                  }}
                >
                  {m.downloaded ? '重新下载' : '下载'}
                </Button>
              </div>
            ))}
          </div>
        </div>

        <div>
          <strong>自定义模型</strong>
          <div className="rowflex" style={{ marginTop: 8 }}>
            <TextInput value={customName} onChange={setCustomName} placeholder="名称" />
            <TextInput value={customTarget} onChange={setCustomTarget} mono placeholder="HF repo_id 或本地路径" />
            <Button
              size="sm"
              onClick={async () => {
                if (!customName.trim() || !customTarget.trim()) return
                await api.addWhisperModel({ name: customName.trim(), target: customTarget.trim() })
                toast('自定义模型已登记')
                setCustomName('')
                setCustomTarget('')
              }}
            >
              登记
            </Button>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function ProxyPanel() {
  const toast = useToast()
  const [cfg, setCfg] = useState<{ enabled: boolean; url: string }>({ enabled: false, url: '' })

  useEffect(() => {
    api.proxyConfig().then((c) => setCfg({ enabled: !!c.enabled, url: String(c.url || '') })).catch(() => {})
  }, [])

  return (
    <Panel title="网络代理">
      <div className="stack">
        <Check checked={cfg.enabled} onChange={(v) => setCfg({ ...cfg, enabled: v })} label="启用代理（作用于 AI 接口、转写接口与视频下载）" />
        <TextInput value={cfg.url} onChange={(v) => setCfg({ ...cfg, url: v })} mono placeholder="http://127.0.0.1:7890" />
        <div>
          <Button
            onClick={async () => {
              await api.updateProxyConfig(cfg)
              toast('代理配置已保存')
            }}
          >
            保存代理
          </Button>
        </div>
      </div>
    </Panel>
  )
}

function CookiePanel() {
  const toast = useToast()
  const [platform, setPlatform] = useState('bilibili')
  const [cookie, setCookie] = useState('')
  const [grabbing, setGrabbing] = useState(false)
  const [showManual, setShowManual] = useState(false)

  const bridge = (window as unknown as {
    bilinote?: {
      openBiliLogin: () => Promise<{ ok: boolean }>
      grabBiliCookie: () => Promise<{ ok: boolean; cookie?: string; error?: string }>
    }
  }).bilinote

  const load = (p: string) => {
    api
      .downloaderCookie(p)
      .then((c) => setCookie(String(c.cookie || '')))
      .catch(() => setCookie(''))
  }
  useEffect(() => {
    load(platform)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform])

  const grab = async () => {
    if (!bridge?.grabBiliCookie) {
      toast('自动抓取只在桌面应用里可用，当前请手动粘贴')
      setShowManual(true)
      return
    }
    setGrabbing(true)
    try {
      const res = await bridge.grabBiliCookie()
      if (res.ok && res.cookie) {
        setCookie(res.cookie)
        await api.updateDownloaderCookie({ platform: 'bilibili', cookie: res.cookie })
        setPlatform('bilibili')
        toast('Cookie 已抓取并保存（含 SESSDATA）')
      } else {
        toast(res.error || '还没抓到 Cookie')
      }
    } finally {
      setGrabbing(false)
    }
  }

  const save = async () => {
    await api.updateDownloaderCookie({ platform, cookie })
    toast('Cookie 已保存')
  }

  return (
    <Panel title="下载 Cookie">
      <div className="stack">
        {platform === 'bilibili' ? (
          <>
            <div className="cue-strip" style={{ padding: 'var(--s4) var(--s5)', gap: 'var(--s4)' }}>
              <span className="tc">B站</span>
              <div style={{ flex: 1 }}>
                <div className="line" style={{ fontSize: 'var(--fs-lg)' }}>
                  去 B 站登录，回来点一下就自动抓好
                </div>
                <div className="sub">
                  打开登录窗口 → 完成登录（扫码 / 验证码都行）→ 回来点「抓取 Cookie 并保存」，含 SESSDATA 的 Cookie 串自动填好。
                </div>
              </div>
            </div>
            <div className="rowflex">
              <Button
                variant="cue"
                onClick={async () => {
                  if (!bridge?.openBiliLogin) {
                    toast('内嵌登录只在桌面应用里可用，当前请手动粘贴')
                    setShowManual(true)
                    return
                  }
                  await bridge.openBiliLogin()
                  toast('B站窗口已打开，登录后回来点「抓取」')
                }}
              >
                去 B 站登录
              </Button>
              <Button onClick={grab} disabled={grabbing}>
                {grabbing ? '抓取中…' : '抓取 Cookie 并保存'}
              </Button>
              {cookie && (
                <span className="small soft">
                  当前：{cookie.includes('SESSDATA') ? '已含 SESSDATA' : '缺 SESSDATA'} · {cookie.slice(0, 24)}…
                </span>
              )}
            </div>
            <button
              className="btn quiet small"
              style={{ alignSelf: 'flex-start' }}
              onClick={() => setShowManual(!showManual)}
            >
              {showManual ? '收起手动方式' : '手动粘贴（出问题时用）'}
            </button>
          </>
        ) : (
          <p className="small soft">
            {platform === 'youtube' ? 'YouTube' : platform === 'douyin' ? '抖音' : '快手'} 的 Cookie 请手动粘贴（登录态能降低风控概率）。
          </p>
        )}

        {(showManual || platform !== 'bilibili') && (
          <>
            <Field label="平台">
              <Select
                value={platform}
                onChange={setPlatform}
                options={[
                  { value: 'bilibili', label: 'B站' },
                  { value: 'youtube', label: 'YouTube' },
                  { value: 'douyin', label: '抖音' },
                  { value: 'kuaishou', label: '快手' },
                ]}
              />
            </Field>
            <TextInput value={cookie} onChange={setCookie} mono placeholder="粘贴 Cookie（B站需含 SESSDATA）" />
            <div>
              <Button onClick={save}>保存 Cookie</Button>
            </div>
          </>
        )}
      </div>
    </Panel>
  )
}

function HealthPanel() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    api.sysHealth().then(setHealth).catch(() => setHealth(null))
  }, [])

  return (
    <Panel
      title="运行状态"
      extra={
        <Button variant="quiet" size="sm" onClick={() => api.sysHealth().then(setHealth).catch(() => {})}>
          刷新
        </Button>
      }
    >
      {health ? (
        <div className="rows">
          <div className="row">
            <div className="grow">后端</div>
            <span className="pill ok">{String(health.backend)}</span>
          </div>
          <div className="row">
            <div className="grow">数据库</div>
            <span className="pill ok">{String(health.db)}</span>
          </div>
          <div className="row">
            <div className="grow">FFmpeg（截图/音频提取依赖）</div>
            <span className={health.ffmpeg === 'ok' ? 'pill ok' : 'pill fail'}>{String(health.ffmpeg)}</span>
          </div>
          <div className="row">
            <div className="grow">Whisper 模型</div>
            <span className="pill">
              {String((health.whisper_model as Record<string, unknown>)?.downloaded ? '已就绪' : '未下载')}
            </span>
          </div>
        </div>
      ) : (
        <Empty headline="拿不到健康状态" hint="确认后端服务地址正确。" />
      )}
    </Panel>
  )
}

function ArchivePanel({ toast }: { toast: (msg: string) => void }) {
  const fileRef = useState<React.RefObject<HTMLInputElement>>(() => ({ current: null }) as React.RefObject<HTMLInputElement>)[0]

  return (
    <Panel title="学习存档">
      <div className="stack">
        <p className="small soft">
          导出一个 zip（数据库快照 + 笔记 + 截图），换机器时导入自动合并去重，不会覆盖本机的 API Key 与设置。
        </p>
        <div className="rowflex">
          <Button
            onClick={async () => {
              try {
                const name = await downloadExport('/api/archive/export', 'bilinote-archive.zip')
                toast(`已导出 ${name}`)
              } catch (e) {
                toast(e instanceof Error ? e.message : '导出失败')
              }
            }}
          >
            导出存档
          </Button>
          <Button
            variant="quiet"
            onClick={() => fileRef.current?.click()}
          >
            导入存档
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".zip"
            style={{ display: 'none' }}
            onChange={async (e) => {
              const file = e.target.files?.[0]
              if (!file) return
              try {
                const res = (await api.importArchive(file)) as { files?: Record<string, number> }
                toast(`导入完成（文件：新增 ${res.files?.imported ?? 0}，跳过 ${res.files?.skipped ?? 0}）`)
              } catch (err) {
                toast(err instanceof Error ? err.message : '导入失败')
              }
              e.target.value = ''
            }}
          />
        </div>
      </div>
    </Panel>
  )
}
