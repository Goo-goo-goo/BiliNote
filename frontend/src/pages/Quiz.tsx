import { useEffect, useState } from 'react'
import { api, GradeResult, Provider, QuizQuestion, TaskStatusDoc } from '../lib/api'
import { DIFFICULTY_LABEL, QTYPE_LABEL } from '../lib/format'
import { Button, Empty, Field, Panel, Select, TextInput, Timecode, useToast } from '../components/ui'
import { useApp } from '../state/store'

export default function Quiz() {
  const toast = useToast()
  const { defaultProviderId, defaultModelName, setDefaults } = useApp()

  const [tasks, setTasks] = useState<TaskStatusDoc[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [models, setModels] = useState<string[]>([])
  const [taskId, setTaskId] = useState('')
  const [providerId, setProviderId] = useState(defaultProviderId)
  const [modelName, setModelName] = useState(defaultModelName)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .listTasks(200)
      .then((list) => {
        const done = list.filter((t) => t.status === 'SUCCESS' && t.result?.note)
        setTasks(done)
        if (done.length && !taskId) setTaskId(done[0].task_id)
      })
      .catch(() => setTasks([]))
    api.listProviders().then(setProviders).catch(() => setProviders([]))
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

  const loadExisting = async (id: string) => {
    const qs = await api.quizQuestions(id)
    setQuestions(qs)
  }

  useEffect(() => {
    if (taskId) loadExisting(taskId).catch(() => setQuestions([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId])

  const generate = async () => {
    setError('')
    if (!taskId || !providerId || !modelName) {
      setError('先选笔记和模型。')
      return
    }
    setLoading(true)
    try {
      setDefaults(providerId, modelName)
      const res = await api.generateQuiz(taskId, modelName, providerId)
      setQuestions(res.questions)
      toast(`已生成 ${res.count} 道题`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '出题失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <Panel title="自测练习">
        <div className="stack">
          <div className="form-grid">
            <Field label="选择笔记">
              <Select
                value={taskId}
                onChange={setTaskId}
                placeholder="选择一篇有结构化笔记的任务"
                options={tasks.map((t) => ({ value: t.task_id, label: t.result?.audio_meta?.title || t.task_id }))}
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
          </div>
          <div className="rowflex">
            <Button onClick={generate} disabled={loading || !taskId}>
              {loading ? '出题中…' : '生成自测题'}
            </Button>
            <span className="small soft">重新生成会替换这套题；已做错的题会进错题本。</span>
          </div>
          {error && <p className="inline-error">{error}</p>}
        </div>
      </Panel>

      {questions.length === 0 ? (
        <Panel flush>
          <Empty headline="还没有题目" hint="选一篇笔记点「生成自测题」，基础/中档/拔高各出几道。" />
        </Panel>
      ) : (
        questions.map((q) => <QuizCard key={q.id} question={q} model={{ modelName, providerId }} onVariant={(nq) => setQuestions((prev) => [...prev, nq])} />)
      )}
    </div>
  )
}

function QuizCard(props: {
  question: QuizQuestion
  model: { modelName: string; providerId: string }
  onVariant: (q: QuizQuestion) => void
}) {
  const q = props.question
  const toast = useToast()
  const [answer, setAnswer] = useState('')
  const [fillParts, setFillParts] = useState<string[]>([])
  const [result, setResult] = useState<GradeResult | null>(null)
  const [busy, setBusy] = useState(false)

  const blanks = Math.max(1, (q.stem.match(/_{3,}/g) || []).length)

  const grade = async () => {
    setBusy(true)
    try {
      const userAnswer = q.qtype === 'fill' ? fillParts.join(' | ') : answer
      const res = await api.gradeQuestion({
        question_id: q.id,
        user_answer: userAnswer,
        model_name: props.model.modelName,
        provider_id: props.model.providerId,
      })
      setResult(res)
    } catch (e) {
      toast(e instanceof Error ? e.message : '判分失败')
    } finally {
      setBusy(false)
    }
  }

  const variant = async () => {
    try {
      const nq = await api.variantQuestion(q.id, props.model.modelName, props.model.providerId)
      props.onVariant(nq)
      toast('变式题已生成')
    } catch (e) {
      toast(e instanceof Error ? e.message : '变式题生成失败')
    }
  }

  const judgedClass =
    result?.correct === true ? 'judged-right' : result?.correct === false ? 'judged-wrong' : ''

  return (
    <div className={`quiz-block ${judgedClass}`}>
      <div className="head">
        <span className="kind">{QTYPE_LABEL[q.qtype] || q.qtype}</span>
        <span>{DIFFICULTY_LABEL[q.difficulty] || q.difficulty}</span>
        {q.knowledge_point && <span style={{ marginLeft: 'auto' }}>{q.knowledge_point}</span>}
        {q.time_stamp && <Timecode value={q.time_stamp} />}
      </div>
      <div className="body">
        <p>{q.stem}</p>

        {q.qtype === 'single' &&
          q.options.map((opt, i) => {
            const key = String.fromCharCode(65 + i)
            return (
              <div
                key={i}
                className={answer === key ? 'option selected' : 'option'}
                onClick={() => !result && setAnswer(key)}
              >
                <span className="key">{key}</span>
                <span>{opt}</span>
              </div>
            )
          })}

        {q.qtype === 'judge' && (
          <div className="rowflex">
            {['正确', '错误'].map((v) => (
              <Button
                key={v}
                variant={answer === v ? 'cue' : 'quiet'}
                size="sm"
                onClick={() => !result && setAnswer(v)}
              >
                {v}
              </Button>
            ))}
          </div>
        )}

        {q.qtype === 'fill' &&
          Array.from({ length: blanks }, (_, i) => (
            <TextInput
              key={i}
              value={fillParts[i] || ''}
              onChange={(v) => setFillParts((prev) => prev.map((x, j) => (j === i ? v : x)).concat(i >= fillParts.length ? [v] : []))}
              placeholder={`第 ${i + 1} 空`}
            />
          ))}

        {q.qtype === 'calc' && (
          <TextInput value={answer} onChange={setAnswer} placeholder="写下你的答案" />
        )}

        {!result ? (
          <div className="rowflex">
            <Button size="sm" onClick={grade} disabled={busy}>
              {busy ? '批改中…' : '提交作答'}
            </Button>
            <Button variant="quiet" size="sm" onClick={variant}>
              换个问法（变式题）
            </Button>
          </div>
        ) : (
          <div className={result.correct === true ? 'verdict right' : 'verdict wrong'}>
            {result.correct === true && <strong>答对了。</strong>}
            {result.correct === false && <strong>答错了。</strong>}
            {result.correct === null && <strong>需要自评：</strong>}
            <span>参考答案：{result.answer}</span>
            {result.feedback && <p className="small" style={{ marginTop: 6 }}>{result.feedback}</p>}
            {result.graded_by === 'ai' && <p className="small soft">由模型批改</p>}
          </div>
        )}
      </div>
    </div>
  )
}
