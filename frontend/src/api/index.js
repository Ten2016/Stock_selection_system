import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.response.use(
  response => {
    const res = response.data
    if (res && res.code === 0) return res
    const msg = res?.msg || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(new Error(msg))
  },
  error => {
    const msg = error?.response?.data?.msg || error.message || '网络错误'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export const getStrategies = () => api.get('/strategies')

export const selectStocks = (strategyName, minMarketCap = null, xDays = 30, yDays = 10, zDays = 2, yPct = 5.0) => {
  const params = { strategy_name: strategyName, x_days: xDays, y_days: yDays, z_days: zDays, y_pct: yPct }
  if (minMarketCap !== null && minMarketCap !== '') params.min_market_cap = minMarketCap
  return api.post('/strategies/select', null, { params, timeout: 300000 })
}

export const getLatestStrategyResult = (strategyName) => api.get('/strategies/latest-result', { params: { strategy_name: strategyName } })

export const searchStocks = (keyword, limit = 20) => api.get('/stocks', { params: { search: keyword, limit, skip: 0 } })

export const backtestStrategy = (strategyName, stockCode, startYear = 2020, xDays = 30, yDays = 10, zDays = 2, yPct = 5.0) => {
  const params = {
    strategy_name: strategyName,
    stock_code: stockCode,
    start_year: startYear,
    x_days: xDays,
    y_days: yDays,
    z_days: zDays,
    y_pct: yPct,
  }
  return api.get('/strategies/backtest', { params, timeout: 300000 })
}

export const syncBasicInfo = () => api.post('/sync/sync-basic-info')

export const getSystemHealth = () => api.get('/system/health')

export default api
