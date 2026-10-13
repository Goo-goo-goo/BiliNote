// 章节时间轨：笔记页左侧的竖向刻度轨，播放头随阅读位置在刻度间移动，点刻度跳章节。
// 语汇来自视频时间轴——时间码是这个产品的一等公民。
import { useEffect, useRef, useState } from 'react'

export interface RailItem {
  id: string
  time?: string
  label: string
}

export default function TimeRail(props: { items: RailItem[] }) {
  const [activeId, setActiveId] = useState<string>('')
  const [headTop, setHeadTop] = useState(0) // 播放头在轨内的像素位置
  const trackRef = useRef<HTMLDivElement>(null)

  const { items } = props

  useEffect(() => {
    const scroller = document.querySelector('.main')
    if (!scroller) return

    const onScroll = () => {
      const track = trackRef.current
      if (!track) return
      const scRect = scroller.getBoundingClientRect()
      // 阅读头：视口 30% 高度处，代表「眼睛当前在哪」
      const headY = scRect.top + scRect.height * 0.3

      const chapterEls = items.map((it) => document.getElementById(it.id))
      const tickEls = Array.from(track.querySelectorAll<HTMLElement>('.timerail-item'))

      // 当前章节 + 章内进度，映射到刻度之间的位置（播放头不越出刻度序列）
      let index = -1
      let frac = 0
      for (let i = 0; i < chapterEls.length; i++) {
        const el = chapterEls[i]
        if (!el) continue
        const rect = el.getBoundingClientRect()
        if (rect.top > headY) break
        index = i
        const nextEl = chapterEls[i + 1]
        const nextTop = nextEl ? nextEl.getBoundingClientRect().top : rect.top + rect.height
        frac = Math.max(0, Math.min(1, (headY - rect.top) / Math.max(1, nextTop - rect.top)))
      }

      const firstTickTop = tickEls[0]?.offsetTop ?? 0
      if (index < 0) {
        setHeadTop(firstTickTop)
        setActiveId(items[0]?.id || '')
        return
      }

      const curTickTop = tickEls[index]?.offsetTop ?? firstTickTop
      const nextTickTop = tickEls[index + 1]?.offsetTop ?? track.scrollHeight
      setHeadTop(curTickTop + frac * (nextTickTop - curTickTop))
      setActiveId(items[index].id)
    }

    onScroll()
    scroller.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      scroller.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [items])

  const jump = (id: string) => {
    const el = document.getElementById(id)
    const scroller = document.querySelector('.main')
    if (!el || !scroller) return
    const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 24
    scroller.scrollTo({ top, behavior: 'smooth' })
  }

  return (
    <aside className="timerail" aria-label="章节时间轨">
      <div className="timerail-track" ref={trackRef}>
        <div className="timerail-playhead" style={{ top: `${Math.round(headTop) - 3}px` }} />
        {items.map((it) => (
          <button
            key={it.id}
            type="button"
            className={it.id === activeId ? 'timerail-item active' : 'timerail-item'}
            onClick={() => jump(it.id)}
            title={it.label}
          >
            <span className="t">{it.time || '—'}</span>
            <span className="l">{it.label}</span>
          </button>
        ))}
      </div>
    </aside>
  )
}
