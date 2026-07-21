import { createRouter, createWebHistory } from 'vue-router'
import StockList from '../views/StockList.vue'
import SyncPage from '../views/SyncPage.vue'
import Strategy from '../views/Strategy.vue'

const routes = [
  { path: '/', component: StockList },
  { path: '/sync', component: SyncPage },
  { path: '/strategy', component: Strategy },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
