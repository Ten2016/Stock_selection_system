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

// 策略专属参数由 /strategies 返回的 ParamSpec 决定，这里原样透传，
// 新增策略无需改动本文件。
export const selectStocks = ({ strategyName, minMarketCap = null, params = {} }) => {
  const query = { strategy_name: strategyName, ...params }
  if (minMarketCap !== null && minMarketCap !== '') query.min_market_cap = minMarketCap
  return api.post('/strategies/select', null, { params: query, timeout: 300000 })
}

export const getLatestStrategyResult = (strategyName) => api.get('/strategies/latest-result', { params: { strategy_name: strategyName } })

export const searchStocks = (keyword, limit = 20) => api.get('/stocks', { params: { search: keyword, limit, skip: 0 } })

export const backtestStrategy = ({ strategyName, stockCode, startYear = 2020, params = {} }) => {
  const query = {
    strategy_name: strategyName,
    stock_code: stockCode,
    start_year: startYear,
    ...params,
  }
  return api.get('/strategies/backtest', { params: query, timeout: 300000 })
}

export const syncBasicInfo = () => api.post('/sync/sync-basic-info')

// ---------- 回测 ----------
export const getBacktestRules = () => api.get('/backtest/rules')

export const runBacktest = (payload) =>
  api.post('/backtest/run', payload, { timeout: 300000 })

export default api
