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

export default api
