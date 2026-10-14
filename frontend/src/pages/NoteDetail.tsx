import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, downloadExport, NoteResultFile } from '../lib/api'
import { Band, Button, Empty, useToast } from '../components/ui'
import MarkdownView, { extractHeadings } from '../features/MarkdownView'
import TimeRail from '../features/TimeRail'

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

  const markdown = result.markdown || ''
  const railItems = extractHeadings(markdown).map((h) => ({ id: h.id, label: h.label, time: h.time }))

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
        {markdown ? (
          <div className="note-layout">
            {railItems.length > 0 && <TimeRail items={railItems} />}
            <MarkdownView markdown={markdown} />
          </div>
        ) : (
          <Empty headline="这篇笔记没有内容" hint="重新生成一次试试。" />
        )}
      </Band>
    </div>
  )
}
