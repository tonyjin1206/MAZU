<template>
  <div style="height: calc(100vh - 120px); display: flex; flex-direction: column">
    <!-- 聊天头部 -->
    <div style="padding: 12px 16px; background: #fff; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; gap: 10px">
      <div style="width: 32px; height: 32px; border-radius: 8px; background: #1d4ed8; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 16px">🤖</div>
      <div>
        <div style="font-weight: 600; font-size: 13px">MTS Bot</div>
        <div style="font-size: 11px; color: #909399">说「采购」「销售」「生产」开始下单</div>
      </div>
      <div style="margin-left: auto">
        <el-button size="small" @click="resetChat">新对话</el-button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div ref="msgContainer" style="flex: 1; overflow-y: auto; padding: 16px; background: #f5f7fa">
      <div v-for="(msg, i) in messages" :key="i" style="margin-bottom: 12px; display: flex; flex-direction: column; align-items: flex-start">
        <!-- Bot 消息 -->
        <div v-if="msg.role === 'bot'" style="display: flex; gap: 8px; max-width: 80%">
          <div style="width: 28px; height: 28px; border-radius: 6px; background: #1d4ed8; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 14px; flex-shrink: 0">🤖</div>
          <div style="background: #fff; border-radius: 4px 12px 12px 12px; padding: 10px 14px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; box-shadow: 0 1px 2px rgba(0,0,0,0.06)">
            <div v-html="renderMarkdown(msg.content)"></div>
          </div>
        </div>
        <!-- 用户消息 -->
        <div v-else style="display: flex; gap: 8px; max-width: 80%; align-self: flex-end; flex-direction: row-reverse">
          <div style="width: 28px; height: 28px; border-radius: 6px; background: #3b82f6; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 14px; flex-shrink: 0">👤</div>
          <div style="background: #3b82f6; color: #fff; border-radius: 12px 4px 12px 12px; padding: 10px 14px; font-size: 13px; line-height: 1.5; box-shadow: 0 1px 2px rgba(0,0,0,0.06)">
            {{ msg.content }}
          </div>
        </div>
      </div>
      <!-- 加载中 -->
      <div v-if="loading" style="display: flex; gap: 8px; max-width: 80%">
        <div style="width: 28px; height: 28px; border-radius: 6px; background: #1d4ed8; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 14px; flex-shrink: 0">🤖</div>
        <div style="background: #fff; border-radius: 4px 12px 12px 12px; padding: 10px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.06)">
          <span style="display: inline-flex; gap: 4px">
            <span style="width: 6px; height: 6px; border-radius: 50%; background: #909399; animation: blink 1.4s infinite both"></span>
            <span style="width: 6px; height: 6px; border-radius: 50%; background: #909399; animation: blink 1.4s infinite both; animation-delay: 0.2s"></span>
            <span style="width: 6px; height: 6px; border-radius: 50%; background: #909399; animation: blink 1.4s infinite both; animation-delay: 0.4s"></span>
          </span>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div style="padding: 12px 16px; background: #fff; border-top: 1px solid #e4e7ed">
      <el-input
        v-model="inputText"
        placeholder="输入消息，回车发送..."
        @keyup.enter="sendMessage"
        :disabled="loading"
        size="large"
        ref="inputRef"
      >
        <template #append>
          <el-button @click="sendMessage" :disabled="loading || !inputText.trim()" type="primary">发送</el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { systemConfigApi } from '../../api/foundation'
import request from '../../api/request'

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const sessionId = ref(localStorage.getItem('bot_session_id') || '')
const msgContainer = ref(null)
const inputRef = ref(null)

// 加载历史消息
const savedMessages = localStorage.getItem('bot_messages')
if (savedMessages) {
  try { messages.value = JSON.parse(savedMessages) } catch {}
}

function saveState() {
  localStorage.setItem('bot_session_id', sessionId.value)
  localStorage.setItem('bot_messages', JSON.stringify(messages.value))
}

function renderMarkdown(text) {
  if (!text) return ''
  // 简单 markdown 渲染：粗体 + 换行 + 序号
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/^(\d+[\.)])/gm, '<span style="color:#1d4ed8;font-weight:600">$1</span>')
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
    const res = await request.post('/chat/message', {
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
    try { await request.post('/chat/reset', { session_id: sessionId.value }) } catch {}
  }
  messages.value = [{
    role: 'bot',
    content: '你好！我是 MTS Bot 🤖\n\n📋 **创建单据**\n  「采购PCB板100片15块」— 采购订单\n  「100个产品A卖给美国客户500块」— 销售订单\n\n💰 **收款/付款**\n  「收美国客户5000块」— 创建收款单\n  「付给深圳华强3000」— 创建付款单\n\n📄 **发票录入**\n  「采购单PO-001发票12345金额5000」— 采购发票\n  「销售单SO-001发票67890金额8000」— 销售发票\n\n🔍 **查询档案**\n  「查一下客户深圳」— 查客户\n  「全部供应商」— 供应商清单\n  「应收账款清单」— 应收汇总\n\n🏭 **生产**\n  「委外工序1给深圳华强加工100个」— 委外单\n  「生产单MO-001发料PCB板50片」— 发料\n  「生产单MO-001入库80个」— 完工入库\n\n你想做什么？',
  }]
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
</script>

<style scoped>
@keyframes blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}
</style>
