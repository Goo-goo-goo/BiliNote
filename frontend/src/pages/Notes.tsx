import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, TaskStatusDoc } from '../lib/api'
import { fmtDuration, platformLabel } from '../lib/format'
import { Band, Empty, Timecode } from '../components/ui'

function dayLabel(day: string): string {
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (day === fmt(today)) return '今天'
  if (day === fmt(yesterday)) return '昨天'
  return day
}

/** updated_at 是 UTC ISO，按浏览器本地时区取日期，避免跨 8 点错位分组。 */
function dayKey(iso?: string): string {
  if (!iso) return '未知日期'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function noteTitle(t: TaskStatusDoc): string {
  return t.title || t.result?.audio_meta?.title || t.task_id
}

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

  // 按日期分组展示（后端已按更新时间倒序，这里维持组序与组内顺序）
  const groups = useMemo(() => {
    const map = new Map<string, TaskStatusDoc[]>()
    for (const t of notes) {
      const day = dayKey(t.updated_at)
      const arr = map.get(day)
      if (arr) arr.push(t)
      else map.set(day, [t])
    }
    return Array.from(map.entries())
  }, [notes])

  return (
    <div className="page">
      <Band title="笔记库" flush>
        {!loaded ? null : notes.length === 0 ? (
          <Empty headline="还没有笔记" hint="生成完成后自动进入这里。" action={<a className="btn" href="#/">去生成</a>} />
        ) : (
          <div className="day-groups">
            {groups.map(([day, items]) => (
              <section className="day-group" key={day}>
                <div className="day-label">
                  <strong>{dayLabel(day)}</strong>
                  {dayLabel(day) !== day && <span className="soft mono">{day}</span>}
                </div>
                <div className="rows">
                  {items.map((t) => {
                    const duration = t.result?.audio_meta?.duration
                    const durHms = duration
                      ? `0:${String(Math.floor(duration / 60)).padStart(2, '0')}:${String(Math.round(duration % 60)).padStart(2, '0')}`
                      : undefined
                    return (
                      <div
                        className="row"
                        key={t.task_id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/notes/${t.task_id}`)}
                      >
                        {durHms ? <Timecode value={durHms} title="视频时长" /> : null}
                        <div className="grow">
                          <div className="title" title={t.task_id}>
                            {noteTitle(t)}
                          </div>
                          <div className="desc">
                            {[
                              t.result?.audio_meta?.platform
                                ? platformLabel(t.result?.audio_meta?.platform)
                                : '',
                              duration ? `时长 ${fmtDuration(duration)}` : '',
                              dayKey(t.updated_at),
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
        )}
      </Band>
    </div>
  )
}
