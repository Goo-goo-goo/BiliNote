import { useEffect, useState } from 'react'
import { api, Collection, CollectionItem, TaskStatusDoc } from '../lib/api'
import { platformLabel } from '../lib/format'
import { Band, Button, Empty, Field, Modal, Select, TextInput, useToast } from '../components/ui'

const STATUS_LABEL: Record<string, string> = { unlearned: '未学', learning: '学习中', completed: '已学完' }

export default function Collections() {
  const toast = useToast()
  const [collections, setCollections] = useState<Collection[]>([])
  const [tasks, setTasks] = useState<TaskStatusDoc[]>([])
  const [openId, setOpenId] = useState<number | null>(null)
  const [detail, setDetail] = useState<Collection | null>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [addTaskId, setAddTaskId] = useState('')

  const refresh = () => {
    api.listCollections().then(setCollections).catch(() => setCollections([]))
    api
      .listTasks(200)
      .then((list) => setTasks(list.filter((t) => t.status === 'SUCCESS')))
      .catch(() => setTasks([]))
  }

  useEffect(refresh, [])

  const openDetail = (id: number) => {
    if (openId === id) {
      setOpenId(null)
      setDetail(null)
      return
    }
    setOpenId(id)
    api.collectionDetail(id).then(setDetail).catch(() => setDetail(null))
  }

  const create = async () => {
    if (!name.trim()) return
    await api.createCollection(name.trim(), desc.trim())
    toast('合集已创建')
    setCreating(false)
    setName('')
    setDesc('')
    refresh()
  }

  const addItem = async () => {
    if (!detail || !addTaskId) return
    const t = tasks.find((x) => x.task_id === addTaskId)
    await api.addCollectionItem(detail.id, {
      task_id: addTaskId,
      video_id: t?.result?.audio_meta?.video_id || '',
      platform: t?.result?.audio_meta?.platform || '',
    })
    toast('已加入合集')
    setAddTaskId('')
    const d = await api.collectionDetail(detail.id)
    setDetail(d)
    refresh()
  }

  const setStatus = async (item: CollectionItem, status: string) => {
    if (!detail) return
    await api.setItemStatus(item.id, status)
    const d = await api.collectionDetail(detail.id)
    setDetail(d)
    refresh()
  }

  const removeItem = async (item: CollectionItem) => {
    if (!detail) return
    await api.removeCollectionItem(detail.id, item.id)
    toast('已移出合集')
    const d = await api.collectionDetail(detail.id)
    setDetail(d)
    refresh()
  }

  const remove = async (c: Collection) => {
    await api.deleteCollection(c.id)
    toast('合集已删除')
    if (openId === c.id) {
      setOpenId(null)
      setDetail(null)
    }
    refresh()
  }

  return (
    <div className="page">
      <Band
        title="合集与课程"
        extra={
          <Button size="sm" onClick={() => setCreating(true)}>
            新建合集
          </Button>
        }
        flush
      >
        {collections.length === 0 ? (
          <Empty
            headline="还没有合集"
            hint="合集把多篇笔记聚成一门课程或专辑。"
            action={
              <Button size="sm" onClick={() => setCreating(true)}>
                新建合集
              </Button>
            }
          />
        ) : (
          <div className="rows">
            {collections.map((c) => (
              <div key={c.id} style={{ borderBottom: '1px solid var(--line)' }}>
                <div className="row">
                  <div className="grow" style={{ cursor: 'pointer' }} onClick={() => openDetail(c.id)}>
                    <div className="title">{c.name}</div>
                    <div className="desc">
                      {c.description || '没有描述'} · {c.item_count ?? 0} 篇笔记 · 已学完 {c.completed_count ?? 0}
                    </div>
                  </div>
                  <Button variant="quiet" size="sm" onClick={() => openDetail(c.id)}>
                    {openId === c.id ? '收起' : '管理'}
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => remove(c)}>
                    删除
                  </Button>
                </div>

                {openId === c.id && detail && (
                  <div className="body" style={{ background: 'var(--bg)' }}>
                    <div className="rowflex" style={{ marginBottom: 12 }}>
                      <Select
                        value={addTaskId}
                        onChange={setAddTaskId}
                        placeholder="选择一篇已完成的笔记"
                        options={tasks.map((t) => ({
                          value: t.task_id,
                          label: t.result?.audio_meta?.title || t.task_id,
                        }))}
                      />
                      <Button size="sm" onClick={addItem} disabled={!addTaskId}>
                        加入合集
                      </Button>
                    </div>

                    {(detail.items || []).length === 0 ? (
                      <Empty headline="合集里还没有笔记" hint="从上面选择一篇加入。" />
                    ) : (
                      <div className="rows">
                        {(detail.items || []).map((item) => (
                          <div className="row" key={item.id}>
                            <div className="grow">
                              <div className="title">
                                {tasks.find((t) => t.task_id === item.task_id)?.result?.audio_meta?.title ||
                                  item.task_id}
                              </div>
                              <div className="desc">{platformLabel(item.platform)}</div>
                            </div>
                            <Select
                              value={item.learning_status}
                              onChange={(v) => setStatus(item, v)}
                              options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
                            />
                            <Button variant="quiet" size="sm" onClick={() => removeItem(item)}>
                              移出
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Band>

      {creating && (
        <Modal title="新建合集" onClose={() => setCreating(false)}>
          <div className="stack">
            <Field label="名称">
              <TextInput value={name} onChange={setName} placeholder="例如：机器学习入门" />
            </Field>
            <Field label="描述">
              <TextInput value={desc} onChange={setDesc} placeholder="可选" />
            </Field>
            <div>
              <Button onClick={create} disabled={!name.trim()}>
                创建
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
