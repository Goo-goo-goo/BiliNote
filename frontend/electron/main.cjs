// Electron 主进程：加载 Vite 开发服务器或构建产物；渲染进程通过 preload 拿最小能力。
const { app, BrowserWindow, shell, ipcMain, dialog } = require('electron')
const path = require('node:path')
const fs = require('node:fs')

const DEV_URL = process.env.VITE_DEV_URL || 'http://localhost:5173'
const isDev = !!process.env.VITE_DEV_URL

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    backgroundColor: '#F2F4F2',
    title: 'BiliNote',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    win.loadURL(DEV_URL)
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  // 外部链接一律交给系统浏览器
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// 保存文件对话框：渲染进程把内容发过来，落盘到用户选的位置
ipcMain.handle('save-file', async (_event, { defaultName, content, mimeType }) => {
  const win = BrowserWindow.getFocusedWindow()
  const { canceled, filePath } = await dialog.showSaveDialog(win, {
    defaultPath: defaultName,
  })
  if (canceled || !filePath) return { ok: false }
  const data = typeof content === 'string' ? Buffer.from(content, 'utf8') : Buffer.from(content)
  fs.writeFileSync(filePath, data)
  return { ok: true, filePath }
})

ipcMain.handle('pick-file', async (_event, { filters }) => {
  const win = BrowserWindow.getFocusedWindow()
  const { canceled, filePaths } = await dialog.showOpenDialog(win, {
    properties: ['openFile'],
    filters: filters || [{ name: 'All Files', extensions: ['*'] }],
  })
  if (canceled || !filePaths.length) return { ok: false }
  return { ok: true, filePath: filePaths[0], content: fs.readFileSync(filePaths[0]) }
})

// ---- B 站登录窗口 + Cookie 抓取 ----
let biliWin = null

ipcMain.handle('open-bili-login', async () => {
  if (biliWin && !biliWin.isDestroyed()) {
    biliWin.focus()
    return { ok: true }
  }
  biliWin = new BrowserWindow({
    width: 1100,
    height: 780,
    title: 'B站登录 — 登录后回到 BiliNote 点「抓取 Cookie」',
    backgroundColor: '#ffffff',
  })
  biliWin.loadURL('https://www.bilibili.com')
  biliWin.on('closed', () => {
    biliWin = null
  })
  return { ok: true }
})

ipcMain.handle('grab-bili-cookie', async () => {
  // 从 B 站窗口所在的 session 里读 .bilibili.com 的 cookie，拼成 yt-dlp 可用的串
  const session = biliWin && !biliWin.isDestroyed() ? biliWin.webContents.session : null
  if (!session) return { ok: false, error: 'B站窗口还没打开：先点「去 B 站登录」并完成登录' }
  const cookies = await session.cookies.get({ domain: '.bilibili.com' })
  const www = await session.cookies.get({ domain: 'www.bilibili.com' })
  const all = [...cookies, ...www]
  const map = new Map()
  for (const c of all) map.set(c.name, c.value)
  if (!map.has('SESSDATA')) {
    return { ok: false, error: '还没拿到 SESSDATA：请在打开的 B站窗口里完成登录后再试' }
  }
  const order = ['SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'buvid3', 'b_nut', 'sid']
  const parts = []
  for (const name of order) {
    if (map.has(name)) parts.push(`${name}=${map.get(name)}`)
  }
  for (const [name, value] of map) {
    if (!order.includes(name)) parts.push(`${name}=${value}`)
  }
  return { ok: true, cookie: parts.join('; '), hasSessdata: true }
})

app.whenReady().then(createWindow)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
