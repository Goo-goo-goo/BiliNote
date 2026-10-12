// 最小能力暴露：文件保存/选择。渲染进程不碰 Node。
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('bilinote', {
  saveFile: (payload) => ipcRenderer.invoke('save-file', payload),
  pickFile: (payload) => ipcRenderer.invoke('pick-file', payload),
  openBiliLogin: () => ipcRenderer.invoke('open-bili-login'),
  grabBiliCookie: () => ipcRenderer.invoke('grab-bili-cookie'),
  isElectron: true,
})
