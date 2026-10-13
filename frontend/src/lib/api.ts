// BiliNote 后端 API 客户端。后端统一返回 {code,msg,data}，code===0 为成功。
// 默认走「同源」：Web 部署下由 nginx / Vite 代理转发到后端（跨机访问零配置）；
// Electron（file://）没有源，直连本地后端。设置页「后端服务地址」可随时覆盖。
// 运行时无任何外部请求。
const DEFAULT_BASE = 'http://localhost:8483'

function defaultBase(): string {
  if (typeof window === 'undefined') return DEFAULT_BASE
  const { protocol, origin } = window.location
  if (protocol === 'file:' || !origin || origin === 'null') return DEFAULT_BASE
  return origin
}

export function getBaseUrl(): string {
  return localStorage.getItem('bilinote.server') || defaultBase()
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

/** B 站扫码登录：GET /api/bili_qrcode */
export interface BiliQrcode {
  qrcode_key: string
  qr_png_base64: string
  login_url: string
}

/** 扫码状态：GET /api/bili_qrcode/status（success 时后端已自动把 cookie 存进下载配置） */
export interface BiliQrcodeStatus {
  status: 'pending' | 'scanned' | 'expired' | 'success'
  cookie: string | null
}

/** 模型条目（OpenAI /v1/models 形状，id 即模型名） */
export interface ModelListItem {
  id: string
  object?: string
  owned_by?: string
}

/** /api/model_list/{provider_id} 返回 {models, error?}；兼容旧版裸数组 */
export interface ModelListResult {
  models: ModelListItem[]
  error?: string
}

function normalizeModelList(raw: ModelListResult | ModelListItem[] | null | undefined): ModelListResult {
  if (Array.isArray(raw)) return { models: raw }
  if (raw && Array.isArray(raw.models)) return raw
  return { models: [], error: raw?.error }
}

export interface TaskStatusDoc {
  task_id: string
  title?: string
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
  history?: { status: string; label: string; message: string; at: string; elapsed: number }[]
  error?: string | null
  result?: NoteResultFile
}

export interface NoteResultFile {
  markdown: string
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
  updateProvider: (payload: {
    id: string
    name?: string
    base_url?: string
    api_key?: string
    logo?: string
    type?: string
    enabled?: number
  }) => request('/api/update_provider', json(payload)),
  connectTest: (id: string, model?: string) =>
    request('/api/connect_test', json({ id, model })),
  modelList: () => request<{ id: string }[]>('/api/model_list'),
  modelListByProvider: (providerId: string) =>
    request<ModelListResult | ModelListItem[]>(`/api/model_list/${providerId}`).then(normalizeModelList),
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
  // B 站扫码登录（Web / 通用）
  biliQrcode: () => request<BiliQrcode>('/api/bili_qrcode'),
  biliQrcodeStatus: (qrcodeKey: string) =>
    request<BiliQrcodeStatus>(`/api/bili_qrcode/status?qrcode_key=${encodeURIComponent(qrcodeKey)}`),
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
