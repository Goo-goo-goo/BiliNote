import { useEffect, useState } from 'react'
import { api, WrongAnswer } from '../lib/api'
import { QTYPE_LABEL } from '../lib/format'
import { Band, Button, Check, Empty, Pill, Timecode, useToast } from '../components/ui'

export default function WrongAnswers() {
  const toast = useToast()
  const [items, setItems] = useState<WrongAnswer[]>([])
  const [activeOnly, setActiveOnly] = useState(true)
  const [loaded, setLoaded] = useState(false)

  const refresh = () => {
    api
      .listWrong(activeOnly ? 1 : 0)
      .then((list) => {
        setItems(list)
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }

  useEffect(refresh, [activeOnly])

  const master = async (w: WrongAnswer) => {
    await api.masterWrong(w.id)
    toast('已标记为掌握')
    refresh()
  }

  const remove = async (w: WrongAnswer) => {
    await api.deleteWrong(w.id)
    toast('错题已删除')
    refresh()
  }

  return (
    <div className="page">
      <Band
        title="错题本"
        extra={
          <div className="rowflex">
            <Check checked={activeOnly} onChange={setActiveOnly} label="只看待攻克" />
          </div>
        }
        flush
      >
        {!loaded ? null : items.length === 0 ? (
          <Empty
            headline={activeOnly ? '没有待攻克的错题' : '错题本是空的'}
            hint="自测里做错的题会自动归集到这里；答对会自动销掉。"
          />
        ) : (
          <div className="rows">
            {items.map((w) => (
              <div className="row" key={w.id} style={{ flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
                <div className="rowflex">
                  <Pill kind={w.status === 'active' ? 'fail' : 'ok'}>{w.status === 'active' ? '待攻克' : '已掌握'}</Pill>
                  <span className="tag">{QTYPE_LABEL[w.qtype] || w.qtype}</span>
                  {w.knowledge_point && <span className="tag">{w.knowledge_point}</span>}
                  {w.time_stamp && <Timecode value={w.time_stamp} />}
                  <span className="small soft mono" style={{ marginLeft: 'auto' }}>
                    错过 {w.wrong_count} 次
                  </span>
                </div>
                <p>{w.question}</p>
                <div className="small">
                  <span className="soft">你的答案：</span>
                  <span style={{ color: 'var(--flag)' }}>{w.user_answer || '（空）'}</span>
                  <span className="soft"> · 正确答案：</span>
                  <strong style={{ color: 'var(--ok)' }}>{w.correct_answer}</strong>
                </div>
                {(w.feedback || w.explanation) && (
                  <p className="small soft">{w.feedback || w.explanation}</p>
                )}
                <div className="rowflex">
                  {w.status === 'active' && (
                    <Button size="sm" variant="quiet" onClick={() => master(w)}>
                      标记已掌握
                    </Button>
                  )}
                  <Button size="sm" variant="danger" onClick={() => remove(w)}>
                    删除
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Band>
    </div>
  )
}
