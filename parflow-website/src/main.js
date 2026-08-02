import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// 如果想把 axios 挂载到全局（可选）
// import axios from 'axios'
// const app = createApp(App)
// app.config.globalProperties.$axios = axios

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')