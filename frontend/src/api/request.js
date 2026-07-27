import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 驼峰 → 蛇形转换
function toSnakeCase(str) {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function transformKeys(obj) {
  if (obj === null || obj === undefined) return obj
  if (Array.isArray(obj)) return obj.map(transformKeys)
  if (typeof obj === 'object' && !(obj instanceof Date) && !(obj instanceof File)) {
    const result = {}
    for (const [key, value] of Object.entries(obj)) {
      result[toSnakeCase(key)] = transformKeys(value)
    }
    return result
  }
  return obj
}

// 请求拦截器：添加 JWT token + 驼峰→蛇形转换
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // POST/PUT/GET 请求自动转换字段名
    if (config.params) {
      config.params = transformKeys(config.params)
    }
    if (config.data && (config.method === 'post' || config.method === 'put')) {
      config.data = transformKeys(config.data)
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器：统一错误处理
let isRedirecting = false
request.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401 && !isRedirecting) {
        isRedirecting = true
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
      } else if (status !== 401) {
        ElMessage.error(data?.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络错误')
    }
    return Promise.reject(error)
  }
)

export default request
