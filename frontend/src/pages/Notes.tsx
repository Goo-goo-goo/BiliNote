import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, TaskStatusDoc } from '../lib/api'
import { fmtDuration, platformLabel } from '../lib/format'
import { Empty, Panel, Timecode } from '../components/ui'

export default function Notes() {
  const navigate = useNavigate()
  const [notes, setNotes] = useState<TaskStatusDoc[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    api
      .listTasks(200)
      .then((list) => {
        setNotes(list.filter((t) => t.status === 'SUCCESS'))
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }, [])

  return (
    <div className="page">
      <Panel title="笔记库" flush>
        {!loaded ? null : notes.length === 0 ? (
          <Empty headline="还没有笔记" hint="生成完成后自动进入这里。" action={<a className="btn" href="#/">去生成</a>} />
        ) : (
          <div className="rows">
            {notes.map((t) => (
              <div
                className="row"
                key={t.task_id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/notes/${t.task_id}`)}
              >
                <Timecode value={`0:00:00`} />
                <div className="grow">
                  <div className="title">{t.result?.audio_meta?.title || t.task_id}</div>
                  <div className="desc">
                    {platformLabel(t.result?.audio_meta?.platform)} · 时长{' '}
                    {fmtDuration(t.result?.audio_meta?.duration)} · {t.updated_at ? t.updated_at.slice(0, 10) : ''}
                  </div>
                </div>
                {t.result?.note?.tags?.slice(0, 3).map((tag) => (
                  <span className="tag" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
