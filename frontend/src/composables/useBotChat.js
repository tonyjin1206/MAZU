/**
 * useBotChat — AI 助手对话逻辑（悬浮组件 / 全屏页共用）
 * 会话持久化到 localStorage（键名与旧版一致，切组件不丢历史）
 */
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { chatApi } from '../api/business'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

// 单据号 → 跳转路由（消息内单据号渲染成可点击链接）
const DOC_ROUTES = {
  'PO-': '/purchase/orders',
  'SO-': '/sales/orders',
  'MO-': '/production/orders',
  'RC-': '/sales/collections',
  'PAY-': '/purchase/payments',
  'FG-': '/production/orders',
  'IS-': '/production/workspace',
}

const DEFAULT_WELCOME = `你好！我是 **Matsu** 😊

📋 **试试这样对我说**
- 「采购PCB板100片15块」— 采购订单
- 「100个产品A卖给美国客户500块」— 销售订单
- 「查一下客户深圳」/「全部供应商」— 查档案
- 「PCB板还有多少」— 查库存
- 「有什么待审核的单」— 审核清单
- 「采购入库怎么操作」— 查操作手册

你想做什么？`

export function useBotChat(options = {}) {
  const welcome = options.welcome || DEFAULT_WELCOME
  const router = useRouter()

  const messages = ref([])
  const inputText = ref('')
  const loading = ref(false)
  const sessionId = ref(localStorage.getItem('bot_session_id') || '')
  const msgContainer = ref(null)
  const inputRef = ref(null)

  // 恢复历史消息
  const savedMessages = localStorage.getItem('bot_messages')
  if (savedMessages) {
    try { messages.value = JSON.parse(savedMessages) } catch { /* ignore */ }
  }

  function saveState() {
    localStorage.setItem('bot_session_id', sessionId.value)
    localStorage.setItem('bot_messages', JSON.stringify(messages.value))
  }

  function renderMarkdown(text) {
    if (!text) return ''
    // 单据号先替换为占位符，marked 渲染后再还原成可点击链接
    const docMap = []
    let t = String(text).replace(/\b((?:PO|SO|MO|RC|PAY|FG|IS)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b/g, (m) => {
      const prefix = m.substring(0, m.indexOf('-') + 1)
      const route = DOC_ROUTES[prefix]
      if (!route) return m
      docMap.push({ route, text: m })
      return `@@DOC${docMap.length - 1}@@`
    })
    let html = ''
    try {
      html = marked.parse(t)
    } catch {
      html = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
    }
    html = html.replace(/@@DOC(\d+)@@/g, (_, i) => {
      const d = docMap[+i]
      return d ? `<a class="doc-link" data-route="${d.route}">${d.text}</a>` : '@@DOC' + i + '@@'
    })
    return html
  }

  function handleDocLinkClick(e) {
    const el = e.target && e.target.closest ? e.target.closest('.doc-link') : null
    if (!el) return
    e.preventDefault()
    router.push(el.dataset.route)
  }

  function scrollToBottom() {
    nextTick(() => {
      if (msgContainer.value) {
        msgContainer.value.scrollTop = msgContainer.value.scrollHeight
      }
    })
  }

  async function sendMessage() {
    const text = inputText.value.trim()
    if (!text || loading.value) return

    messages.value.push({ role: 'user', content: text })
    inputText.value = ''
    loading.value = true
    scrollToBottom()

    try {
      const res = await chatApi.message({
        message: text,
        session_id: sessionId.value,
      })
      sessionId.value = res.session_id
      messages.value.push({ role: 'bot', content: res.reply })
      saveState()
    } catch (e) {
      messages.value.push({ role: 'bot', content: '❌ 请求失败，请重试' })
    }

    loading.value = false
    scrollToBottom()
    nextTick(() => inputRef.value?.focus())
  }

  async function resetChat() {
    if (sessionId.value) {
      try { await chatApi.reset() } catch { /* ignore */ }
    }
    messages.value = [{ role: 'bot', content: welcome }]
    sessionId.value = ''
    localStorage.removeItem('bot_session_id')
    localStorage.removeItem('bot_messages')
    scrollToBottom()
  }

  // 有历史记录就加载，没有就显示欢迎语
  if (!sessionId.value) {
    resetChat()
  } else {
    scrollToBottom()
  }
  nextTick(() => inputRef.value?.focus())

  return {
    messages,
    inputText,
    loading,
    sessionId,
    msgContainer,
    inputRef,
    renderMarkdown,
    handleDocLinkClick,
    scrollToBottom,
    sendMessage,
    resetChat,
  }
}
