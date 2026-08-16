import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from 'axios'

// 请求拦截：自动携带登录 token
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 时清除登录态并跳转登录页（登录/注册接口本身的 401 除外）
axios.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || ''
    const status = err.response?.status
    if (status === 401 && !url.includes('/api/login') && !url.includes('/api/register')) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      if (router.currentRoute.value.path !== '/login') {
        router.push('/login')
      }
    }
    return Promise.reject(err)
  }
)

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')