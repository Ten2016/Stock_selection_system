import { createRouter, createWebHistory } from 'vue-router'
import StockList from '../views/StockList.vue'
import SyncPage from '../views/SyncPage.vue'
import Strategy from '../views/Strategy.vue'
import Backtest from '../views/Backtest.vue'

const routes = [
  { path: '/', component: StockList },
  { path: '/sync', component: SyncPage },
  { path: '/strategy', component: Strategy },
  { path: '/backtest', component: Backtest },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
