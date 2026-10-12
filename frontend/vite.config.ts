import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 全部依赖本地打包：运行时零 CDN 请求（字体经 @fontsource 打进 bundle）
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 1200,
  },
})
