import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 全部依赖本地打包：运行时零 CDN 请求（字体经 @fontsource 打进 bundle）
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5173,
    strictPort: true,
    // 开发时同源请求代理到本地后端（与 Docker 里 nginx 的转发行为一致）
    proxy: {
      '/api': 'http://localhost:8483',
      '/static': 'http://localhost:8483',
      '/uploads': 'http://localhost:8483',
    },
  },
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 1200,
  },
})
