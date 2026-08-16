import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import DataView from '../views/DataView.vue'
import HelpPage from '../views/HelpPage.vue'
import NoticePage from '../views/NoticePage.vue'
import LoginView from '../views/Login.vue'
import MyDownloadsView from '../views/MyDownloads.vue'
import UserCenterView from '../views/UserCenter.vue'

const routes = [
  { path: '/', redirect: '/data/view' },
  { path: '/home', component: HomePage },
  { path: '/data/view', component: DataView },
  { path: '/help', component: HelpPage },
  { path: '/notice', component: NoticePage },
  { path: '/login', component: LoginView },
  { path: '/downloads', component: MyDownloadsView },
  { path: '/profile', component: UserCenterView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录只能访问 /login
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router