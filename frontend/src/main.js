import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'

// 启动时：清理无效的登录缓存
const token = localStorage.getItem('token')
const userStr = localStorage.getItem('user')
if (token && !userStr) {
  localStorage.removeItem('token')
}
// 如果过期了也清理（简单判断：token 是 JWT，过期会由后端返回 401）
// 前端不解析 JWT，让路由守卫和 axios 拦截器处理

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
  if (val === null || val === undefined || val === '') return '0.0000'
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return '0.0000'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
}

app.mount('#app')
