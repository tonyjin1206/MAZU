import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        // E2E 测试可用 VITE_PROXY_TARGET 覆盖后端地址（默认开发端口 8788）
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8788',
        changeOrigin: true,
      },
    },
  },
})
