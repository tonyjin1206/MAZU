<template>
  <div class="matsu-assistant">
    <!-- 悬浮球 -->
    <div class="matsu-ball" @click="toggle" title="Matsu AI 助手">
      <span class="matsu-ball-logo">M</span>
    </div>

    <!-- 聊天窗 -->
    <transition name="matsu-pop">
      <div v-if="open" class="matsu-window">
        <!-- 头部 -->
        <div class="matsu-header">
          <div class="matsu-avatar">M</div>
          <div style="flex: 1; min-width: 0">
            <div class="matsu-title">Matsu AI 助手</div>
            <div class="matsu-sub">录单 / 查库存 / 审核 / 操作手册</div>
          </div>
          <el-button size="small" text style="color: #fff" @click="resetChat()">新对话</el-button>
          <el-button size="small" text style="color: #fff" @click="open = false">✕</el-button>
        </div>

        <!-- 消息列表 -->
        <div ref="msgContainer" class="matsu-msgs" @click="handleDocLinkClick">
          <div v-for="(msg, i) in messages" :key="i" class="matsu-row" :class="msg.role">
            <div v-if="msg.role === 'bot'" class="matsu-avatar matsu-avatar-sm">M</div>
            <div v-else class="matsu-avatar matsu-avatar-sm matsu-avatar-user">👤</div>
            <div v-if="msg.role === 'bot'" class="matsu-bubble bot" v-html="renderMarkdown(msg.content)"></div>
            <div v-else class="matsu-bubble user">{{ msg.content }}</div>
          </div>

          <!-- 加载中 -->
          <div v-if="loading" class="matsu-row bot">
            <div class="matsu-avatar matsu-avatar-sm">M</div>
            <div class="matsu-bubble bot">
              <span class="matsu-dots">
                <span></span><span></span><span></span>
              </span>
            </div>
          </div>

          <!-- 快捷确认（bot 正在等用户确认时） -->
          <div v-if="showConfirm && !loading" class="matsu-confirm">
            <el-button size="small" type="primary" @click="quickReply('确认')">✅ 确认</el-button>
            <el-button size="small" @click="quickReply('取消')">❌ 取消</el-button>
          </div>
        </div>

        <!-- 可用能力提示 -->
        <div class="matsu-caps">
          <span v-for="cap in caps" :key="cap" class="matsu-cap">{{ cap }}</span>
        </div>

        <!-- 输入区 -->
        <div class="matsu-input">
          <el-input
            v-model="inputText"
            placeholder="输入消息，回车发送…"
            :disabled="loading"
            size="default"
            @keyup.enter="sendMessage"
            ref="inputRef"
          >
            <template #append>
              <el-button :disabled="loading || !inputText.trim()" type="primary" @click="sendMessage">发送</el-button>
            </template>
          </el-input>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useBotChat } from '../composables/useBotChat'

const open = ref(false)
const {
  messages, inputText, loading, msgContainer, inputRef,
  renderMarkdown, handleDocLinkClick, sendMessage, resetChat,
} = useBotChat()

function toggle() {
  open.value = !open.value
  if (open.value) nextTick(() => inputRef.value?.focus())
}

function quickReply(text) {
  inputText.value = text
  sendMessage()
}

// bot 回复含确认问句（三步确认流程）时显示快捷按钮
const showConfirm = computed(() => {
  const last = [...messages.value].reverse().find((m) => m.role === 'bot')
  if (!last) return false
  if (/已(创建|审核|确认|录入|反审核)/.test(last.content)) return false
  return /确认|对吗|是否|对不对|核对/.test(last.content)
})

// 可用能力（按菜单权限显示）
const perms = ref(JSON.parse(localStorage.getItem('permissions') || '[]'))
const CAP_DEFS = [
  ['menu:purchase:orders', '采购·建/审'],
  ['menu:sales:orders', '销售·建/审'],
  ['menu:inventory', '查库存'],
  ['menu:sales:collections', '收款'],
  ['menu:purchase:payments', '付款'],
]
const caps = computed(() => {
  const list = ['查档案', '操作手册']
  for (const [perm, label] of CAP_DEFS) {
    if (perms.value.includes(perm)) list.push(label)
  }
  return list.slice(0, 6)
})
</script>

<style scoped>
.matsu-ball {
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1d4ed8, #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(29, 78, 216, 0.45);
  z-index: 3000;
  transition: transform 0.2s;
}
.matsu-ball:hover {
  transform: scale(1.08);
}
.matsu-ball-logo {
  font-family: 'Segoe UI', sans-serif;
  font-weight: 800;
  font-size: 22px;
  color: #fff;
}

.matsu-window {
  position: fixed;
  right: 20px;
  bottom: 84px;
  width: 380px;
  max-width: calc(100vw - 32px);
  height: 62vh;
  max-height: 560px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 2999;
}

.matsu-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #1d4ed8, #7c3aed);
  color: #fff;
}
.matsu-avatar {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Segoe UI', sans-serif;
  font-weight: 800;
  font-size: 15px;
  flex-shrink: 0;
}
.matsu-avatar-sm {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  font-size: 13px;
  background: linear-gradient(135deg, #1d4ed8, #7c3aed);
  color: #fff;
}
.matsu-avatar-user {
  background: #3b82f6;
  font-size: 13px;
}
.matsu-title {
  font-weight: 600;
  font-size: 13px;
}
.matsu-sub {
  font-size: 11px;
  opacity: 0.8;
}

.matsu-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: #f5f7fa;
}
.matsu-row {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  align-items: flex-start;
}
.matsu-row.user {
  flex-direction: row-reverse;
}
.matsu-bubble {
  max-width: 78%;
  padding: 8px 12px;
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.matsu-bubble.bot {
  background: #fff;
  border-radius: 4px 12px 12px 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.matsu-bubble.user {
  background: #3b82f6;
  color: #fff;
  border-radius: 12px 4px 12px 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.matsu-dots {
  display: inline-flex;
  gap: 4px;
}
.matsu-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #909399;
  animation: matsu-blink 1.4s infinite both;
}
.matsu-dots span:nth-child(2) { animation-delay: 0.2s; }
.matsu-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes matsu-blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

.matsu-confirm {
  display: flex;
  gap: 8px;
  padding: 2px 0 10px 32px;
}

.matsu-caps {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 12px;
  border-top: 1px solid #f0f2f5;
  background: #fafbfc;
}
.matsu-cap {
  font-size: 11px;
  color: #4b5563;
  background: #eef2ff;
  border: 1px solid #e0e7ff;
  border-radius: 4px;
  padding: 2px 8px;
}

.matsu-input {
  padding: 10px 12px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

/* 消息内单据号链接 */
:deep(.doc-link) {
  color: #1d4ed8;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}
:deep(.matsu-bubble.bot table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 11px;
  margin: 6px 0;
}
:deep(.matsu-bubble.bot th) {
  background: #f3f4f6;
  padding: 4px 8px;
  border: 1px solid #e5e7eb;
  text-align: left;
}
:deep(.matsu-bubble.bot td) {
  padding: 3px 8px;
  border: 1px solid #e5e7eb;
}

.matsu-pop-enter-active,
.matsu-pop-leave-active {
  transition: all 0.18s ease;
}
.matsu-pop-enter-from,
.matsu-pop-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}
</style>
