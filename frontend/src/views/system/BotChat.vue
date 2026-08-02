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
    <div ref="msgContainer" style="flex: 1; overflow-y: auto; padding: 16px; background: #f5f7fa" @click="handleDocLinkClick">
      <div v-for="(msg, i) in messages" :key="i" style="margin-bottom: 12px; display: flex; flex-direction: column; align-items: flex-start">
        <!-- Bot 消息 -->
        <div v-if="msg.role === 'bot'" style="display: flex; gap: 8px; max-width: 80%">
          <div style="width: 28px; height: 28px; border-radius: 6px; background: linear-gradient(135deg, #1d4ed8, #7c3aed); display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-family: 'Segoe UI', sans-serif; font-weight: 800; font-size: 14px; color: #fff">M</div>
          <div class="bot-message-content" style="background: #fff; border-radius: 4px 12px 12px 12px; padding: 10px 14px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; box-shadow: 0 1px 2px rgba(0,0,0,0.06)">
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
import { useBotChat } from '../../composables/useBotChat'

const RICH_WELCOME = `你好！我是 **Mazu Trade System** 的 AI 助手，我是 **Matsu**！😊

📋 **创建单据**
  「采购PCB板100片15块」— 采购订单
  「100个产品A卖给美国客户500块」— 销售订单

💰 **收款/付款**
  「收美国客户5000块」— 创建收款单
  「付给深圳华强3000」— 创建付款单

📄 **发票录入**
  「采购单PO-001发票12345金额5000」— 采购发票
  「销售单SO-001发票67890金额8000」— 销售发票

🔍 **查询档案**
  「查一下客户深圳」— 查客户
  「全部供应商」— 供应商清单
  「应收账款清单」— 应收汇总
  「查库存PCB板」— 库存查询

🏭 **生产**
  「生产单MO-001发料PCB板50片」— 发料
  「生产单MO-001入库80个」— 完工入库

🛒 **审核**
  「有什么待审核的单」— 待审核清单
  「审核采购单PO-xxx」— 审核单据

你想做什么？`

const {
  messages, inputText, loading, sessionId, msgContainer, inputRef,
  renderMarkdown, handleDocLinkClick, scrollToBottom, sendMessage, resetChat,
} = useBotChat({ welcome: RICH_WELCOME })
</script>

<style scoped>
@keyframes blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}
.bot-message-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
  margin: 8px 0;
}
.bot-message-content :deep(th) {
  background: #f3f4f6;
  padding: 6px 10px;
  border: 1px solid #e5e7eb;
  text-align: left;
  font-weight: 600;
}
.bot-message-content :deep(td) {
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
}
.bot-message-content :deep(code) {
  background: #f3f4f6;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}
.bot-message-content :deep(strong) {
  font-weight: 600;
}
</style>
