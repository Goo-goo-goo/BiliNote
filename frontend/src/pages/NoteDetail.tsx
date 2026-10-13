import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, downloadExport, NoteResultFile } from '../lib/api'
import { cueTime, hmsToSeconds } from '../lib/format'
import { Band, Button, Empty, useToast } from '../components/ui'
import NoteRenderer, { chapterId } from '../features/NoteRenderer'
import TimeRail from '../features/TimeRail'

function timeLinkBuilder(meta?: NoteResultFile['audio_meta']): (hms: string) => string | null {
  return (hms: string) => {
    const seconds = hmsToSeconds(hms)
    if (seconds == null || !meta) return null
    const id = meta.video_id
    if (meta.platform === 'bilibili') {
      return `https://www.bilibili.com/video/${id.replace('_p', '?p=')}&t=${seconds}`
    }
    if (meta.platform === 'youtube') {
      return `https://www.youtube.com/watch?v=${id}&t=${seconds}s`
    }
    if (meta.platform === 'douyin') {
      return `https://www.douyin.com/video/${id}`
    }
    return null
  }
}

export default function NoteDetail() {
  const { taskId } = useParams<{ taskId: string }>()
  const toast = useToast()
  const [result, setResult] = useState<NoteResultFile | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    if (!taskId) return
    api
      .taskStatus(taskId)
      .then((doc) => {
        if (doc.result) setResult(doc.result)
        else setMissing(true)
      })
      .catch(() => setMissing(true))
  }, [taskId])

  const exportNote = async (format: 'md' | 'html') => {
    if (!taskId) return
    try {
      const name = await downloadExport(`/api/export/note/${taskId}?format=${format}`, `${taskId}.${format}`)
      toast(`已导出 ${name}`)
    } catch (e) {
      toast(e instanceof Error ? e.message : '导出失败')
    }
  }

  if (missing) {
    return (
      <div className="page">
        <Empty
          headline="找不到这篇笔记"
          hint="可能任务还没完成，或任务 ID 不对。"
          action={<a className="btn" href="#/notes">回到笔记库</a>}
        />
      </div>
    )
  }

  if (!result) {
    return (
      <div className="page">
        <Empty headline="加载中…" />
      </div>
    )
  }

  const railItems = (result.note?.chapters || []).map((ch, ci) => ({
    id: chapterId(ci),
    time: cueTime(ch.time_stamp),
    label: ch.title,
  }))

  return (
    <div className="page">
      <Band
        title={result.audio_meta?.title || taskId}
        extra={
          <div className="rowflex">
            <Button variant="quiet" size="sm" onClick={() => exportNote('md')}>
              导出 Markdown
            </Button>
            <Button variant="quiet" size="sm" onClick={() => exportNote('html')}>
              导出 HTML
            </Button>
          </div>
        }
      >
        <div className="note-layout">
          {railItems.length > 0 && <TimeRail items={railItems} />}
          {result.note ? (
            <NoteRenderer note={result.note} imageBase="" timeLink={timeLinkBuilder(result.audio_meta)} />
          ) : (
            <article className="article">
              <p className="soft">这篇是旧版 Markdown 笔记，只提供原文：</p>
              <pre>
                <code>{result.markdown}</code>
              </pre>
            </article>
          )}
        </div>
      </Band>
    </div>
  )
}
