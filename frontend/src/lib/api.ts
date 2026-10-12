// BiliNote 后端 API 客户端。后端统一返回 {code,msg,data}，code===0 为成功。
// 运行时只连本地后端（默认 http://localhost:8483），无任何外部请求。

const DEFAULT_BASE = 'http://localhost:8483'

export function getBaseUrl(): string {
  return localStorage.getItem('bilinote.server') || DEFAULT_BASE
}

export function setBaseUrl(url: string) {
  localStorage.setItem('bilinote.server', url.replace(/\/$/, ''))
}

export class ApiError extends Error {
  code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
  }
}

interface Envelope<T> {
  code: number
  msg: string
  data: T
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${getBaseUrl()}${path}`, init)
  if (!resp.ok && !resp.headers.get('content-type')?.includes('json')) {
    throw new ApiError(resp.status, `请求失败：${resp.status} ${resp.statusText}`)
  }
  const body = (await resp.json()) as Envelope<T>
  if (body.code !== 0) {
    throw new ApiError(body.code, body.msg || '请求失败')
  }
  return body.data
}

function json(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

// ---------------------------------------------------------------- 类型

export interface TaskStatusDoc {
  task_id: string
  status: string
  label: string
  step: number
  total_steps: number
  message: string
  detail: string
  progress: number
  created_at?: string
  updated_at?: string
  elapsed_seconds: number
  stale_seconds: number
  finished: boolean
  history: { status: string; label: string; message: string; at: string; elapsed: number }[]
  error?: string | null
  result?: NoteResultFile
}

export interface NoteBlock {
  type: string
  content?: string
  items?: string[]
  ordered?: boolean
  language?: string
  headers?: string[]
  rows?: string[][]
  time_stamp?: string
  image_url?: string
}

export interface NoteSection {
  type: string
  heading: string
  time_stamp?: string
  important?: boolean
  blocks: NoteBlock[]
}

export interface NoteChapter {
  title: string
  time_stamp?: string
  intro?: string
  sections: NoteSection[]
  summary?: string
  key_points?: string[]
}

export interface NoteJson {
  title: string
  summary?: string
  chapters: NoteChapter[]
  key_takeaways?: string[]
  tags?: string[]
}

export interface NoteResultFile {
  markdown: string
  note: NoteJson | null
  audio_meta?: {
    title: string
    video_id: string
    platform: string
    duration: number
    cover_url?: string
  }
}

export interface Provider {
  id: number
  name: string
  type: string
  base_url: string
  api_key_masked?: string
  api_key?: string
  logo?: string
  enabled?: number
}

export interface Collection {
  id: number
  name: string
  description: string
  item_count?: number
  completed_count?: number
  learning_count?: number
  items?: CollectionItem[]
  created_at?: string
}

export interface CollectionItem {
  id: number
  collection_id: number
  task_id: string
  video_id: string
  platform: string
  sort_order: number
  learning_status: 'unlearned' | 'learning' | 'completed'
}

export interface QuizQuestion {
  id: number
  task_id: string
  collection_id: number | null
  qtype: 'single' | 'judge' | 'fill' | 'calc'
  difficulty: 'basic' | 'medium' | 'advanced'
  stem: string
  options: string[]
  answer: string
  explanation: string
  knowledge_point: string
  time_stamp: string
}

export interface WrongAnswer {
  id: number
  question_id: number | null
  task_id: string
  qtype: string
  question: string
  user_answer: string
  correct_answer: string
  explanation: string
  feedback: string
  knowledge_point: string
  time_stamp: string
  status: 'active' | 'mastered'
  wrong_count: number
}

export interface ReviewMaterial {
  id: number
  collection_id: number
  title: string
  detail_mode: 'full' | 'brief'
  status: 'pending' | 'processing' | 'done' | 'failed'
  progress: string
  error: string
  content?: ReviewContent
}

export interface ReviewContent {
  title: string
  summary: string
  goals: string[]
  chapters: {
    title: string
    intro: string
    sections: { heading: string; content: string }[]
    exercises: QuizQuestion[]
  }[]
  confusions: { pair: string; difference: string }[]
  glossary: { term: string; meaning: string }[]
  cards: { front: string; back: string }[]
}

export interface GradeResult {
  correct: boolean | null
  answer: string
  feedback: string
  graded_by: 'local' | 'ai' | 'none'
  wrong_record?: WrongAnswer
  cleared_wrong_count?: number
}

// ---------------------------------------------------------------- 接口

export const api = {
  // 任务 / 笔记
  generateNote: (payload: Record<string, unknown>) =>
    request<{ task_id: string }>('/api/generate_note', json(payload)),
  taskStatus: (taskId: string) => request<TaskStatusDoc>(`/api/task_status/${taskId}`),
  listTasks: (limit = 50) => request<TaskStatusDoc[]>(`/api/tasks?limit=${limit}`),
  deleteTask: (videoId: string, platform: string) =>
    request('/api/delete_task', json({ video_id: videoId, platform })),

  // 供应商 / 模型
  addProvider: (payload: { name: string; type: string; base_url: string; api_key: string; logo?: string }) =>
    request<Provider>('/api/add_provider', json(payload)),
  listProviders: () => request<Provider[]>('/api/get_all_providers'),
  updateProvider: (payload: Record<string, unknown>) => request('/api/update_provider', json(payload)),
  connectTest: (id: string, model?: string) =>
    request('/api/connect_test', json({ id, model })),
  modelList: () => request<{ id: string }[]>('/api/model_list'),
  modelListByProvider: (providerId: string) =>
    request<{ id: string }[]>(`/api/model_list/${providerId}`),
  addModel: (payload: { provider_id: string; model_name: string }) =>
    request('/api/models', json(payload)),
  deleteModel: (modelId: string) => request(`/api/models/delete/${modelId}`),

  // 合集 / 课程
  createCollection: (name: string, description = '') =>
    request<Collection>('/api/collection/create', json({ name, description })),
  listCollections: () => request<Collection[]>('/api/collection/list'),
  collectionDetail: (id: number) => request<Collection>(`/api/collection/detail/${id}`),
  updateCollection: (id: number, name?: string, description?: string) =>
    request('/api/collection/update', json({ id, name, description })),
  deleteCollection: (id: number) => request(`/api/collection/${id}`, { method: 'DELETE' }),
  addCollectionItem: (collectionId: number, payload: { task_id: string; video_id?: string; platform?: string }) =>
    request<CollectionItem>(`/api/collection/${collectionId}/items/add`, json(payload)),
  removeCollectionItem: (collectionId: number, itemId: number) =>
    request(`/api/collection/${collectionId}/items/${itemId}`, { method: 'DELETE' }),
  setItemStatus: (itemId: number, learning_status: string) =>
    request(`/api/collection/items/${itemId}/status`, json({ learning_status })),

  // 自测题 / 错题本
  generateQuiz: (taskId: string, model_name: string, provider_id: string, per_tier = 3, collection_id?: number) =>
    request<{ count: number; questions: QuizQuestion[] }>(
      '/api/quiz/generate',
      json({ task_id: taskId, model_name, provider_id, per_tier, collection_id }),
    ),
  quizQuestions: (taskId: string) => request<QuizQuestion[]>(`/api/quiz/questions/${taskId}`),
  gradeQuestion: (payload: {
    question_id?: number
    question?: Partial<QuizQuestion>
    user_answer: string
    model_name?: string
    provider_id?: string
  }) => request<GradeResult>('/api/quiz/grade', json(payload)),
  variantQuestion: (questionId: number, model_name: string, provider_id: string) =>
    request<QuizQuestion>('/api/quiz/variant', json({ question_id: questionId, model_name, provider_id })),
  listWrong: (activeOnly = 1, taskId?: string) =>
    request<WrongAnswer[]>(`/api/quiz/wrong?active_only=${activeOnly}${taskId ? `&task_id=${taskId}` : ''}`),
  masterWrong: (id: number) => request(`/api/quiz/wrong/${id}/master`, json({})),
  deleteWrong: (id: number) => request(`/api/quiz/wrong/${id}`, { method: 'DELETE' }),

  // 复习资料
  generateReview: (collection_id: number, model_name: string, provider_id: string, detail_mode: 'full' | 'brief') =>
    request<ReviewMaterial>('/api/review/generate', json({ collection_id, model_name, provider_id, detail_mode })),
  listReviews: (collectionId?: number) =>
    request<ReviewMaterial[]>(`/api/review/list${collectionId ? `?collection_id=${collectionId}` : ''}`),
  getReview: (id: number) => request<ReviewMaterial>(`/api/review/${id}`),
  deleteReview: (id: number) => request(`/api/review/${id}`, { method: 'DELETE' }),

  // 转写器 / 下载 / 代理 / 健康
  transcriberConfig: () => request<Record<string, unknown>>('/api/transcriber_config'),
  updateTranscriberConfig: (payload: Record<string, unknown>) =>
    request('/api/transcriber_config', json(payload)),
  whisperModels: () => request<Record<string, unknown>>('/api/whisper_models'),
  addWhisperModel: (payload: { name: string; target: string }) =>
    request('/api/whisper_models', json(payload)),
  deleteWhisperModel: (name: string) =>
    request(`/api/whisper_models/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  transcriberModelsStatus: () => request<Record<string, { model_size: string; downloaded: boolean; downloading: boolean; failed: boolean; error?: string }[]>>('/api/transcriber_models_status'),
  transcriberDownload: (model_size: string, transcriber_type = 'fast-whisper') =>
    request('/api/transcriber_download', json({ model_size, transcriber_type })),
  proxyConfig: () => request<Record<string, unknown>>('/api/proxy_config'),
  updateProxyConfig: (payload: { enabled: boolean; url: string }) =>
    request('/api/proxy_config', json(payload)),
  sysHealth: () => request<Record<string, unknown>>('/api/sys_health'),
  sysCheck: () => request<Record<string, unknown>>('/api/sys_check'),
  downloaderCookie: (platform: string) =>
    request<Record<string, unknown>>(`/api/get_downloader_cookie/${platform}`),
  updateDownloaderCookie: (payload: { platform: string; cookie: string }) =>
    request('/api/update_downloader_cookie', json(payload)),

  // 存档
  archiveExportUrl: () => `${getBaseUrl()}/api/archive/export`,
  importArchive: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Record<string, unknown>>('/api/archive/import', { method: 'POST', body: form })
  },
}

/** 下载导出文件：浏览器走 blob，Electron 走系统保存对话框。 */
export async function downloadExport(path: string, defaultName: string) {
  const url = `${getBaseUrl()}${path}`
  const resp = await fetch(url)
  if (!resp.ok) throw new ApiError(resp.status, `导出失败：${resp.status}`)
  const blob = await resp.blob()

  const bridge = (window as unknown as { bilinote?: { saveFile: (p: unknown) => Promise<{ ok: boolean; filePath?: string }> } }).bilinote
  if (bridge?.saveFile) {
    const buffer = await blob.arrayBuffer()
    const saved = await bridge.saveFile({
      defaultName,
      content: Array.from(new Uint8Array(buffer)),
      mimeType: blob.type,
    })
    return saved.filePath || defaultName
  }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = defaultName
  a.click()
  URL.revokeObjectURL(a.href)
  return defaultName
}
