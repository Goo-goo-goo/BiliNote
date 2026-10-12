import { useEffect, useState } from 'react'
import { api, Collection, downloadExport, Provider, ReviewMaterial } from '../lib/api'
import { Button, Empty, Field, Panel, Select, useToast } from '../components/ui'
import { useApp } from '../state/store'

export default function Review() {
  const toast = useToast()
  const { defaultProviderId, defaultModelName, setDefaults } = useApp()

  const [collections, setCollections] = useState<Collection[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [models, setModels] = useState<string[]>([])
  const [collectionId, setCollectionId] = useState('')
  const [providerId, setProviderId] = useState(defaultProviderId)
  const [modelName, setModelName] = useState(defaultModelName)
  const [mode, setMode] = useState<'full' | 'brief'>('full')
  const [materials, setMaterials] = useState<ReviewMaterial[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [openId, setOpenId] = useState<number | null>(null)

  useEffect(() => {
    api.listCollections().then((list) => {
      setCollections(list)
      if (list.length && !collectionId) setCollectionId(String(list[0].id))
    }).catch(() => setCollections([]))
    api.listProviders().then(setProviders).catch(() => setProviders([]))
    api.listReviews().then(setMaterials).catch(() => setMaterials([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!providerId) return
    api
      .modelListByProvider(providerId)
      .then((list) => {
        const names = list.map((m) => m.id)
        setModels(names)
        if (!names.includes(modelName)) setModelName(names[0] || '')
      })
      .catch(() => setModels([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId])

  // 生成是后台任务：轮询进度
  useEffect(() => {
    const hasRunning = materials.some((m) => m.status === 'processing' || m.status === 'pending')
    if (!hasRunning) return
    const timer = window.setInterval(() => {
      api.listReviews().then(setMaterials).catch(() => {})
    }, 2500)
    return () => window.clearInterval(timer)
  }, [materials])

  const generate = async () => {
    setError('')
    if (!collectionId || !providerId || !modelName) {
      setError('先选合集和模型。')
      return
    }
    setBusy(true)
    try {
      setDefaults(providerId, modelName)
      await api.generateReview(Number(collectionId), modelName, providerId, mode)
      toast('复习资料开始生成')
      const list = await api.listReviews()
      setMaterials(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setBusy(false)
    }
  }

  const open = async (m: ReviewMaterial) => {
    if (openId === m.id) {
      setOpenId(null)
      return
    }
    const full = await api.getReview(m.id)
    setMaterials((prev) => prev.map((x) => (x.id === m.id ? full : x)))
    setOpenId(m.id)
  }

  const exportMaterial = async (m: ReviewMaterial, format: 'md' | 'html') => {
    try {
      const name = await downloadExport(`/api/export/review/${m.id}?format=${format}`, `${m.title || '复习资料'}.${format}`)
      toast(`已导出 ${name}`)
    } catch (e) {
      toast(e instanceof Error ? e.message : '导出失败')
    }
  }

  return (
    <div className="page">
      <Panel title="生成复习资料">
        <div className="stack">
          <div className="form-grid">
            <Field label="合集" hint="复习资料按合集生成，把多篇笔记按知识逻辑重排">
              <Select
                value={collectionId}
                onChange={setCollectionId}
                placeholder="选择合集"
                options={collections.map((c) => ({ value: String(c.id), label: `${c.name}（${c.item_count ?? 0} 篇）` }))}
              />
            </Field>
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
            <Field label="生成方式" hint="详版分三步：大纲 → 逐章 → 总览，慢但写得足">
              <Select
                value={mode}
                onChange={(v) => setMode(v as 'full' | 'brief')}
                options={[
                  { value: 'full', label: '详版（大纲 → 逐章 → 总览）' },
                  { value: 'brief', label: '简版（一次成型）' },
                ]}
              />
            </Field>
          </div>
          <div className="rowflex">
            <Button onClick={generate} disabled={busy || !collectionId}>
              {busy ? '提交中…' : '生成复习资料'}
            </Button>
          </div>
          {error && <p className="inline-error">{error}</p>}
        </div>
      </Panel>

      <Panel title="复习资料" flush>
        {materials.length === 0 ? (
          <Empty headline="还没有复习资料" hint="选一个合集生成，产出可导出 Markdown / HTML（浏览器直接打印成 PDF）。" />
        ) : (
          <div className="rows">
            {materials.map((m) => (
              <div key={m.id} style={{ borderBottom: '1px solid var(--line)' }}>
                <div className="row">
                  <div className="grow">
                    <div className="title">{m.title}</div>
                    <div className="desc">
                      {m.detail_mode === 'full' ? '详版' : '简版'} · {m.status === 'done' ? '已完成' : m.status === 'failed' ? `失败：${m.error}` : m.progress}
                    </div>
                  </div>
                  {m.status === 'done' && (
                    <>
                      <Button variant="quiet" size="sm" onClick={() => open(m)}>
                        {openId === m.id ? '收起' : '查看'}
                      </Button>
                      <Button variant="quiet" size="sm" onClick={() => exportMaterial(m, 'md')}>
                        Markdown
                      </Button>
                      <Button variant="quiet" size="sm" onClick={() => exportMaterial(m, 'html')}>
                        HTML
                      </Button>
                    </>
                  )}
                  <Button variant="danger" size="sm" onClick={() => api.deleteReview(m.id).then(() => setMaterials((p) => p.filter((x) => x.id !== m.id)))}>
                    删除
                  </Button>
                </div>

                {openId === m.id && m.content && <ReviewContent content={m.content} />}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}

function ReviewContent({ content }: { content: NonNullable<ReviewMaterial['content']> }) {
  return (
    <div className="body" style={{ background: 'var(--paper)' }}>
      <article className="article" style={{ maxWidth: 'none' }}>
        {content.summary && <div className="lead">{content.summary}</div>}
        {content.goals?.length > 0 && (
          <>
            <h2>学习目标</h2>
            <ul>
              {content.goals.map((g, i) => (
                <li key={i}>{g}</li>
              ))}
            </ul>
          </>
        )}
        {content.chapters?.map((ch, i) => (
          <section key={i}>
            <h2>
              {i + 1}. {ch.title}
            </h2>
            {ch.intro && <p className="soft">{ch.intro}</p>}
            {ch.sections?.map((s, j) => (
              <div key={j}>
                <h3>{s.heading}</h3>
                <p>{s.content}</p>
              </div>
            ))}
            {ch.exercises?.length > 0 && (
              <>
                <h3>章节测试</h3>
                <ol>
                  {ch.exercises.map((q, k) => (
                    <li key={k}>
                      {q.stem}
                      {q.answer && <span className="soft">（答案：{q.answer}）</span>}
                    </li>
                  ))}
                </ol>
              </>
            )}
          </section>
        ))}
        {content.confusions?.length > 0 && (
          <>
            <h2>易混辨析</h2>
            <table>
              <thead>
                <tr>
                  <th>易混点</th>
                  <th>辨析</th>
                </tr>
              </thead>
              <tbody>
                {content.confusions.map((c, i) => (
                  <tr key={i}>
                    <td>{c.pair}</td>
                    <td>{c.difference}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {content.cards?.length > 0 && (
          <>
            <h2>速记卡</h2>
            <table>
              <thead>
                <tr>
                  <th>问</th>
                  <th>答</th>
                </tr>
              </thead>
              <tbody>
                {content.cards.map((c, i) => (
                  <tr key={i}>
                    <td>{c.front}</td>
                    <td>{c.back}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </article>
    </div>
  )
}
