import { useEffect, useRef, useState } from 'react'
import { api, BiliQrcode, downloadExport, getBaseUrl, Provider } from '../lib/api'
import { Button, Check, Empty, Field, Modal, Panel, Pill, Select, TextInput, useToast } from '../components/ui'
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
      <McpPanel />
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
  const [newModel, setNewModel] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState<Provider | null>(null)
  const [menu, setMenu] = useState<{ providerId: string; loading: boolean; models: string[]; error: string } | null>(null)

  const refresh = () => {
    api.listProviders().then(setProviders).catch(() => setProviders([]))
  }
  useEffect(refresh, [])

  /** 「自动获取」：拉取该供应商的可选模型清单，展开下拉供点选 */
  const fetchModels = (p: Provider) => {
    const id = String(p.id)
    setMenu({ providerId: id, loading: true, models: [], error: '' })
    api
      .modelListByProvider(id)
      .then((r) => setMenu({ providerId: id, loading: false, models: r.models.map((x) => x.id), error: r.error || '' }))
      .catch((e) =>
        setMenu({ providerId: id, loading: false, models: [], error: e instanceof Error ? e.message : '获取模型失败' })
      )
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
                  <Button variant="quiet" size="sm" onClick={() => test(p)}>
                    测试连接
                  </Button>
                  <Button variant="quiet" size="sm" onClick={() => setEditing(p)}>
                    编辑
                  </Button>
                </div>
                <div className="rowflex">
                  <TextInput
                    value={newModel[p.id] || ''}
                    onChange={(v) => setNewModel((m) => ({ ...m, [p.id]: v }))}
                    placeholder="手动登记模型名"
                  />
                  <div style={{ position: 'relative' }}>
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() => (menu?.providerId === String(p.id) ? setMenu(null) : fetchModels(p))}
                    >
                      {menu?.providerId === String(p.id) && menu.loading ? '获取中…' : '自动获取 ▾'}
                    </Button>
                    {menu?.providerId === String(p.id) && (
                      <>
                        <div className="pop-overlay" onClick={() => setMenu(null)} />
                        <div className="pop-menu">
                          {menu.loading ? (
                            <div className="pop-item soft">正在拉取模型列表…</div>
                          ) : menu.models.length ? (
                            menu.models.map((m) => (
                              <button
                                key={m}
                                className="pop-item"
                                onClick={() => {
                                  setNewModel((s) => ({ ...s, [p.id]: m }))
                                  setMenu(null)
                                }}
                              >
                                {m}
                              </button>
                            ))
                          ) : (
                            <div className="pop-item soft">{menu.error || '没有可选模型'}</div>
                          )}
                          {!menu.loading && menu.models.length > 0 && menu.error && (
                            <div className="pop-item soft">{menu.error}</div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                  <Button
                    size="sm"
                    onClick={async () => {
                      const model = (newModel[p.id] || '').trim()
                      if (!model) return
                      try {
                        await api.addModel({ provider_id: String(p.id), model_name: model })
                        toast('模型已登记')
                        setNewModel((m) => ({ ...m, [p.id]: '' }))
                      } catch (e) {
                        toast(e instanceof Error ? e.message : '模型登记失败')
                      }
                    }}
                  >
                    登记
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {editing && (
        <ProviderEditModal
          provider={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            refresh()
          }}
        />
      )}
    </Panel>
  )
}

/** 编辑供应商：改 base_url / API Key；API Key 留空表示不修改。 */
function ProviderEditModal({
  provider,
  onClose,
  onSaved,
}: {
  provider: Provider
  onClose: () => void
  onSaved: () => void
}) {
  const toast = useToast()
  const [baseUrl, setBaseUrl] = useState(provider.base_url || '')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)

  const save = async () => {
    if (!baseUrl.trim()) {
      toast('接口地址不能为空')
      return
    }
    setSaving(true)
    try {
      const payload: { id: string; base_url: string; api_key?: string } = {
        id: String(provider.id),
        base_url: baseUrl.trim(),
      }
      // 留空不回传，避免空串覆盖原 Key（后端对掩码值也有防护）
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      await api.updateProvider(payload)
      toast('供应商已更新')
      onSaved()
    } catch (e) {
      toast(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`编辑供应商 · ${provider.name}`} onClose={onClose}>
      <div className="stack">
        <Field label="接口地址 base_url">
          <TextInput value={baseUrl} onChange={setBaseUrl} mono placeholder="https://api.example.com/v1" />
        </Field>
        <Field label="API Key" hint="留空则不修改当前 Key；保存后只显示掩码">
          <TextInput value={apiKey} onChange={setApiKey} mono type="password" placeholder="sk-…" />
        </Field>
        <div className="rowflex">
          <Button onClick={save} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </Button>
          <Button variant="quiet" onClick={onClose}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
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
  const [qrOpen, setQrOpen] = useState(false)

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
    <>
    <Panel title="下载 Cookie">
      <div className="stack">
        {platform === 'bilibili' ? (
          <>
            <div className="callout">
              <div style={{ flex: 1 }}>
                <div className="title">两种方式拿到 B 站登录态，抓到即自动保存</div>
                <div className="sub">
                  扫码登录：点「扫码登录」用哔哩哔哩 App 扫码，确认后 Cookie 自动保存，Web / 桌面通用。
                  桌面应用里也可打开登录窗口完成登录（扫码 / 验证码都行）→ 回来点「抓取 Cookie 并保存」。
                </div>
              </div>
            </div>
            <div className="rowflex">
              <Button onClick={() => setQrOpen(true)}>扫码登录</Button>
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
    {qrOpen && (
      <BiliQrLoginModal
        onClose={() => setQrOpen(false)}
        onSuccess={(c) => {
          setQrOpen(false)
          setPlatform('bilibili')
          if (c) setCookie(c)
          else load('bilibili')
          toast('扫码登录成功，Cookie 已保存')
        }}
      />
    )}
    </>
  )
}

/** B 站扫码登录弹窗：申请二维码 → 每 2s 轮询状态 → success 时后端已自动保存 Cookie。 */
function BiliQrLoginModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: (cookie: string | null) => void
}) {
  const [qr, setQr] = useState<BiliQrcode | null>(null)
  const [status, setStatus] = useState<'pending' | 'scanned' | 'expired' | 'success'>('pending')
  const [error, setError] = useState('')
  const [round, setRound] = useState(0)
  const doneRef = useRef(false)
  const successRef = useRef(onSuccess)
  successRef.current = onSuccess

  useEffect(() => {
    let cancelled = false
    let timer = 0
    let failures = 0
    doneRef.current = false
    setQr(null)
    setStatus('pending')
    setError('')

    api
      .biliQrcode()
      .then((res) => {
        if (cancelled) return
        setQr(res)
        timer = window.setInterval(async () => {
          try {
            const s = await api.biliQrcodeStatus(res.qrcode_key)
            if (cancelled || doneRef.current) return
            failures = 0
            if (s.status === 'success') {
              doneRef.current = true
              window.clearInterval(timer)
              setStatus('success')
              successRef.current(s.cookie)
            } else if (s.status === 'expired') {
              window.clearInterval(timer)
              setStatus('expired')
            } else {
              setStatus(s.status)
            }
          } catch {
            if (cancelled || doneRef.current) return
            failures += 1
            if (failures >= 3) {
              window.clearInterval(timer)
              setError('扫码状态查询失败，请确认后端服务可用后重试')
            }
          }
        }, 2000)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : '二维码生成失败')
      })

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [round])

  const done = status === 'success'
  const stuck = status === 'expired' || !!error
  const hint = error
    ? error
    : done
      ? '登录成功，Cookie 已保存'
      : status === 'scanned'
        ? '已扫码，请在手机上确认登录'
        : qr
          ? '请用哔哩哔哩 App「扫一扫」登录，成功后 Cookie 自动保存'
          : '二维码生成中…'

  return (
    <Modal title="B站扫码登录" onClose={onClose}>
      <div className="stack">
        <div className="qr-stage">
          <div className="qr-frame">
            {qr && !stuck ? (
              <img src={`data:image/png;base64,${qr.qr_png_base64}`} alt="B站登录二维码" />
            ) : (
              <span>{status === 'expired' ? '二维码已过期' : error ? '二维码加载失败' : '生成中…'}</span>
            )}
          </div>
        </div>
        <div className="stack tight" style={{ alignItems: 'center' }}>
          <Pill kind={done ? 'ok' : stuck ? 'fail' : 'run'}>
            {done ? '已登录' : status === 'expired' ? '已过期' : status === 'scanned' ? '已扫码，待确认' : error ? '出错' : '等待扫码'}
          </Pill>
          <div className="small soft qr-hint">{hint}</div>
        </div>
        {stuck && (
          <div className="rowflex" style={{ justifyContent: 'center' }}>
            <Button variant="cue" onClick={() => setRound((r) => r + 1)}>
              刷新二维码
            </Button>
          </div>
        )}
      </div>
    </Modal>
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

// ---------- MCP 接入 ----------

/** 复制到剪贴板：非 HTTPS 页面 navigator.clipboard 不可用，走 execCommand 兜底 */
async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* 落到兜底 */
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

function CodeBlock({ text, onCopy }: { text: string; onCopy: (text: string) => void }) {
  return (
    <div className="code-block">
      <pre>{text}</pre>
      <Button variant="quiet" size="sm" onClick={() => onCopy(text)}>
        复制
      </Button>
    </div>
  )
}

function McpPanel() {
  const toast = useToast()
  const [endpoint, setEndpoint] = useState(`${getBaseUrl()}/mcp`)

  const copy = (text: string) => {
    copyText(text).then((ok) => toast(ok ? '已复制到剪贴板' : '复制失败，请手动选中复制'))
  }

  const claudeCode = `claude mcp add --transport http bilinote ${endpoint}`
  const mcpJson = JSON.stringify(
    { mcpServers: { bilinote: { type: 'http', url: endpoint } } },
    null,
    2,
  )

  return (
    <Panel title="MCP 接入" extra={<span className="small soft">让 AI 客户端直接生成笔记、查任务、读笔记</span>}>
      <div className="stack">
        <Field
          label="MCP 端点地址"
          hint="Web 部署走前端端口转发，自动填好；客户端和后端不同机器时（比如 Claude 在电脑、BiliNote 在 NAS），改成 http://<后端主机>:<后端端口>/mcp"
        >
          <div className="rowflex">
            <TextInput value={endpoint} onChange={setEndpoint} mono />
            <Button variant="quiet" onClick={() => copy(endpoint)}>
              复制
            </Button>
          </div>
        </Field>

        <div className="stack tight">
          <span className="small soft">Claude Code（终端里执行）</span>
          <CodeBlock text={claudeCode} onCopy={copy} />
        </div>

        <div className="stack tight">
          <span className="small soft">Claude Desktop / Cursor（mcpServers 配置）</span>
          <CodeBlock text={mcpJson} onCopy={copy} />
        </div>

        <div className="stack tight">
          <span className="small soft">
            Cherry Studio 等图形界面客户端：添加 MCP 服务器 → 传输方式选「流式 HTTP / Streamable HTTP」→ 地址填上面的端点
          </span>
        </div>

        <div className="stack tight">
          <span className="small soft">接入后可用的工具</span>
          <div>
            <div className="mcp-tool">
              <span className="name">generate_note</span>
              <span className="desc">提交视频 → 笔记任务（异步，返回 task_id）</span>
            </div>
            <div className="mcp-tool">
              <span className="name">list_notes</span>
              <span className="desc">已完成笔记列表（标题 / 平台 / 时长）</span>
            </div>
            <div className="mcp-tool">
              <span className="name">get_task_status</span>
              <span className="desc">任务进度、阶段与失败原因</span>
            </div>
            <div className="mcp-tool">
              <span className="name">get_note</span>
              <span className="desc">读取笔记 Markdown 正文</span>
            </div>
          </div>
        </div>
      </div>
    </Panel>
  )
}
