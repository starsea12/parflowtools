import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import DataView from '../views/DataView.vue'
import HelpPage from '../views/HelpPage.vue'
import NoticePage from '../views/NoticePage.vue'
import LoginView from '../views/Login.vue'

const routes = [
  { path: '/', redirect: '/data/view' },
  { path: '/home', component: HomePage },
  { path: '/data/view', component: DataView },
  { path: '/help', component: HelpPage },
  { path: '/notice', component: NoticePage },
  { path: '/login', component: LoginView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})
export default router