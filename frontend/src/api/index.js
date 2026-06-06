import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 统一响应拦截器，后端返回格式: { code, msg, data }
api.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code === 0) {
      // 直接返回整个响应体，组件通过 res.msg 访问消息，res.data 访问业务数据
      return res
    } else {
      ElMessage.error(res.msg || '请求失败')
      return Promise.reject(new Error(res.msg || '请求失败'))
    }
  },
  error => {
    ElMessage.error(error.message || '网络错误')
    return Promise.reject(error)
  }
)

// 获取策略列表
export const getStrategies = () => {
  return api.get('/strategies')
}

// 运行选股策略
export const selectStocks = (strategyName, minMarketCap = null, xDays = 30, yDays = 10, zDays = 2, yPct = 5.0) => {
  const params = { strategy_name: strategyName, x_days: xDays, y_days: yDays, z_days: zDays, y_pct: yPct }
  if (minMarketCap !== null && minMarketCap !== '') {
    params.min_market_cap = minMarketCap
  }
  return api.post('/strategies/select', null, { params, timeout: 300000 })
}

// 获取策略最新结果
export const getLatestStrategyResult = (strategyName) => {
  return api.get('/strategies/latest-result', { params: { strategy_name: strategyName } })
}

// 同步股票基本信息（市值、市盈率等）
export const syncBasicInfo = () => {
  return api.post('/sync/sync-basic-info')
}

export default api
