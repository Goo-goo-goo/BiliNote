import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, TaskStatusDoc } from '../lib/api'
import { fmtDuration, fmtPercent, fmtTime } from '../lib/format'
import { Band, Button, Empty, Pill, ProgressRail, StepDots, Timecode } from '../components/ui'

export default function Tasks() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<TaskStatusDoc[]>([])
  const [openId, setOpenId] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  const refresh = () => {
    api
      .listTasks(100)
      .then((list) => {
        setTasks(list)
        setFailed(false)
      })
      .catch(() => setFailed(true))
  }

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, 3000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="page">
      <Band title="全部任务" flush>
        {failed ? (
          <Empty
            headline="连不上后端"
            hint="确认后端已启动（默认 http://localhost:8483），或到「设置」里改服务地址。"
            action={<a className="btn" href="#/settings">打开设置</a>}
          />
        ) : tasks.length === 0 ? (
          <Empty
            headline="还没有任务"
            hint="到工作台贴一个视频链接开始。"
            action={<a className="btn" href="#/">去工作台</a>}
          />
        ) : (
          <div className="rows">
            {tasks.map((t) => (
              <TaskRow
                key={t.task_id}
                task={t}
                open={openId === t.task_id}
                onToggle={() => setOpenId(openId === t.task_id ? null : t.task_id)}
                onOpenNote={() => navigate(`/notes/${t.task_id}`)}
              />
            ))}
          </div>
        )}
      </Band>
    </div>
  )
}

function TaskRow(props: {
  task: TaskStatusDoc
  open: boolean
  onToggle: () => void
  onOpenNote: () => void
}) {
  const t = props.task
  const kind = t.status === 'SUCCESS' ? 'ok' : t.status === 'FAILED' ? 'fail' : 'run'

  return (
    <div className="row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 12 }}>
      <div className="rowflex" style={{ cursor: 'pointer' }} onClick={props.onToggle}>
        <div className="grow">
          <div
            className={t.title || t.result?.audio_meta?.title ? 'title' : 'title mono'}
            title={t.task_id}
          >
            {t.title || t.result?.audio_meta?.title || t.task_id}
          </div>
          <div className="desc">
            {t.label} · {t.message}
            {t.detail ? ` · ${t.detail}` : ''}
          </div>
        </div>
        <div style={{ width: 200 }}>
          <ProgressRail value={t.progress} cue={!t.finished} />
          <div className="small soft mono" style={{ marginTop: 4 }}>
            第 {t.step}/{t.total_steps} 步 · {fmtPercent(t.progress)} · 已跑 {fmtDuration(t.elapsed_seconds)}
            {!t.finished && t.stale_seconds > 120 ? ` · 静默 ${fmtDuration(t.stale_seconds)}` : ''}
          </div>
        </div>
        <Pill kind={kind as 'ok' | 'fail' | 'run'}>{t.label}</Pill>
        <Button variant="quiet" size="sm" onClick={props.onToggle}>
          {props.open ? '收起' : '详情'}
        </Button>
      </div>

      {props.open && (
        <div className="stack tight" style={{ paddingLeft: 8 }}>
          <StepDots step={t.step} total={t.total_steps} />
          {t.error && <p className="inline-error">失败原因：{t.error}</p>}

          {(t.history ?? []).length > 0 && (
            <div className="stack tight">
              {(t.history ?? []).map((h, i) => (
                <div key={i} className="rowflex small">
                  <Timecode value={`0:${String(Math.floor(h.elapsed / 60)).padStart(2, '0')}:${String(Math.round(h.elapsed % 60)).padStart(2, '0')}`} />
                  <strong>{h.label}</strong>
                  <span className="soft">{h.message}</span>
                  <span className="soft mono" style={{ marginLeft: 'auto' }}>
                    {fmtTime(h.at)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {t.status === 'SUCCESS' && (
            <div>
              <Button size="sm" onClick={props.onOpenNote}>
                打开笔记
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
