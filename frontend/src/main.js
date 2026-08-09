import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import '../../docs/vi-design/mts-variables.css'
import './assets/drag-fix.css'

// 启动时：清理无效的登录缓存
const token = localStorage.getItem('token')
const userStr = localStorage.getItem('user')
if (token && !userStr) {
  localStorage.removeItem('token')
}

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus, { locale: zhCn })
app.use(router)

// 全局格式化工具
app.config.globalProperties.$fm = (val) => {
  if (val === null || val === undefined || val === '') return '¥0.00'
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return '¥0.00'
  return '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
app.config.globalProperties.$fq = (val) => {
  if (val === null || val === undefined || val === '') return '0.00'
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 全局权限检查方法
app.config.globalProperties.$hasPermission = (code) => {
  const perms = localStorage.getItem('permissions')
  if (!perms) return false
  try {
    const list = JSON.parse(perms)
    return list.includes(code)
  } catch {
    return false
  }
}

app.mount('#app')
