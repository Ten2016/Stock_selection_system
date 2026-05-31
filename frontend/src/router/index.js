import { createRouter, createWebHistory } from 'vue-router'
import StockList from '../views/StockList.vue'
import StockDetail from '../views/StockDetail.vue'
import SyncPage from '../views/SyncPage.vue'

const routes = [
  { path: '/', component: StockList },
  { path: '/stock/:code', component: StockDetail },
  { path: '/sync', component: SyncPage },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
