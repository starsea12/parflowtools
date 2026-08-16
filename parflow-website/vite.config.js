import http from 'node:http'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// API 代理目标:默认直连服务器(172.16.103.49:50001),无需 SSH 隧道。
// 校园网关会拦截 Host 为 IP 的 HTTP 请求,因此必须保持 changeOrigin: false,
// 让转发出去的 Host 头仍是 localhost:5173(网关白名单只放行 localhost 系 Host)。
// 如需恢复隧道模式:VITE_API_TARGET=http://localhost:50001 npm run dev
const API_TARGET = process.env.VITE_API_TARGET || 'http://172.16.103.49:50001'

// 上游连接复用,降低新建连接频率(网关偶发断新连接);
// 1 秒闲置即由客户端回收,早于 gunicorn 的 2 秒 keep-alive,避免复用半死连接
const apiAgent = new http.Agent({ keepAlive: true, keepAliveMsecs: 1000, maxSockets: 10 })

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: false,
        agent: apiAgent,
      },
    },
  },
})
