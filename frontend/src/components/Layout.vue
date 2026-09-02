<template>
  <el-container style="height: 100vh">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" style="background: linear-gradient(180deg, #0c2d7a 0%, #123d8a 100%); overflow-y: auto; overflow-x: hidden; height: 100vh">
      <div style="height: 60px; display: flex; align-items: center; justify-content: center; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.07)">
        <img v-if="!isCollapse" src="/LOGO-light.svg" alt="MTS" style="width: 34px; height: 34px; border-radius: 7px">
        <img v-else src="/LOGO-light.svg" alt="MTS" style="width: 34px; height: 34px; border-radius: 7px">
        <span v-if="!isCollapse" style="color: #d8dce6; font-size: 16px; font-weight: 600; letter-spacing: 0.5px">MTS</span>
      </div>
      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        background-color="transparent"
        text-color="rgba(255,255,255,0.65)"
        active-text-color="#ffffff"
        router
        style="border-right: none; padding: 4px 0"
      >
        <el-menu-item index="/dashboard" v-if="hasPerm('menu:dashboard')">
          <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-diagnose"/></svg>
          <span>工作台</span>
        </el-menu-item>

        <!-- Agent设置（1级菜单） -->
        <el-menu-item index="/system/bot" v-if="hasPerm('menu:system:bot')">
          <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-cog"/></svg>
          <span>Agent设置</span>
        </el-menu-item>

        <!-- 系统管理 -->
        <el-sub-menu index="system" v-if="hasPerm('menu:system:users') || hasPerm('menu:system:roles') || hasPerm('menu:system:wecom') || hasPerm('menu:system:reminders')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-lock"/></svg>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/system/users" v-if="hasPerm('menu:system:users')">用户管理</el-menu-item>
          <el-menu-item index="/system/roles" v-if="hasPerm('menu:system:roles')">角色管理</el-menu-item>
          <el-menu-item index="/system/wecom" v-if="hasPerm('menu:system:wecom')">企业微信</el-menu-item>
          <el-menu-item index="/system/notifications" v-if="hasPerm('menu:system:reminders')">通知管理</el-menu-item>
        </el-sub-menu>

        <!-- 1. 基础档案 -->
        <el-sub-menu index="foundation" v-if="hasPerm('menu:customers') || hasPerm('menu:suppliers') || hasPerm('menu:materials') || hasPerm('menu:products') || hasPerm('menu:processes') || hasPerm('menu:bom') || hasPerm('menu:currencies') || hasPerm('menu:params')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-layer-group"/></svg>
            <span>基础档案</span>
          </template>
          <el-menu-item index="/foundation/params" v-if="hasPerm('menu:params')">参数设置</el-menu-item>
          <el-menu-item index="/foundation/customers" v-if="hasPerm('menu:customers')">客户管理</el-menu-item>
          <el-menu-item index="/foundation/suppliers" v-if="hasPerm('menu:suppliers')">供应商管理</el-menu-item>
          <el-menu-item index="/foundation/currencies" v-if="hasPerm('menu:currencies')">币种/汇率</el-menu-item>
          <el-menu-item index="/foundation/materials" v-if="hasPerm('menu:materials')">原辅材料</el-menu-item>
          <el-menu-item index="/foundation/products" v-if="hasPerm('menu:products')">产品档案</el-menu-item>
          <el-menu-item index="/foundation/processes" v-if="hasPerm('menu:processes')">工艺维护</el-menu-item>
          <el-menu-item index="/foundation/bom" v-if="hasPerm('menu:bom')">BOM管理</el-menu-item>
        </el-sub-menu>

        <!-- 2. 销售管理 -->
        <el-sub-menu index="sales" v-if="hasPerm('menu:sales:orders') || hasPerm('menu:sales:deliveries') || hasPerm('menu:sales:invoices') || hasPerm('menu:sales:ar') || hasPerm('menu:sales:collections')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-exchange"/></svg>
            <span>销售管理</span>
          </template>
          <el-menu-item index="/sales/orders" v-if="hasPerm('menu:sales:orders')">销售订单</el-menu-item>
          <el-menu-item index="/sales/deliveries" v-if="hasPerm('menu:sales:deliveries')">销售发货</el-menu-item>
          <el-menu-item index="/sales/invoices" v-if="hasPerm('menu:sales:invoices')">销售发票</el-menu-item>
          <el-menu-item index="/sales/ar" v-if="hasPerm('menu:sales:ar')">应收账款</el-menu-item>
          <el-menu-item index="/sales/collections" v-if="hasPerm('menu:sales:collections')">收款管理</el-menu-item>
        </el-sub-menu>

        <!-- 3. 采购管理 -->
        <el-sub-menu index="purchase" v-if="hasPerm('menu:purchase:from-sales') || hasPerm('menu:purchase:orders') || hasPerm('menu:purchase:invoices') || hasPerm('menu:purchase:ap') || hasPerm('menu:purchase:payments')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-inbox-in"/></svg>
            <span>采购管理</span>
          </template>
          <el-menu-item index="/purchase/from-sales" v-if="hasPerm('menu:purchase:from-sales')">销售订单转采购</el-menu-item>
          <el-menu-item index="/purchase/orders" v-if="hasPerm('menu:purchase:orders')">采购订单</el-menu-item>
          <el-menu-item index="/purchase/invoices" v-if="hasPerm('menu:purchase:invoices')">采购发票</el-menu-item>
          <el-menu-item index="/purchase/ap" v-if="hasPerm('menu:purchase:ap')">应付账款</el-menu-item>
          <el-menu-item index="/purchase/payments" v-if="hasPerm('menu:purchase:payments')">付款管理</el-menu-item>
        </el-sub-menu>

        <!-- 3. 委外管理 -->
        <el-sub-menu index="outsource" v-if="hasPerm('menu:outsource:from-sales') || hasPerm('menu:outsource:orders')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-cog"/></svg>
            <span>委外管理</span>
          </template>
          <el-menu-item index="/outsource/from-sales" v-if="hasPerm('menu:outsource:from-sales')">销售订单转委外</el-menu-item>
          <el-menu-item index="/outsource/orders" v-if="hasPerm('menu:outsource:orders')">委外订单</el-menu-item>
        </el-sub-menu>

        <!-- 4. 库存管理（批次追溯=原生产批次追溯，挪到库存菜单） -->
        <el-sub-menu index="inventory" v-if="hasPerm('menu:inventory') || hasPerm('menu:inventory:summary') || hasPerm('menu:inventory:stock-ins') || hasPerm('menu:inventory:material-ins') || hasPerm('menu:inventory:material-outs') || hasPerm('menu:inventory:delivery-outs') || hasPerm('menu:inventory:stocktake') || hasPerm('menu:production:batch')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-database-set"/></svg>
            <span>库存管理</span>
          </template>
          <el-menu-item index="/inventory/material-ins" v-if="hasPerm('menu:inventory:material-ins')">原料入库</el-menu-item>
          <el-menu-item index="/inventory/material-outs" v-if="hasPerm('menu:inventory:material-outs')">原料出库</el-menu-item>
          <el-menu-item index="/inventory/stock-ins" v-if="hasPerm('menu:inventory:stock-ins')">成品入库</el-menu-item>
          <el-menu-item index="/inventory/delivery-outs" v-if="hasPerm('menu:inventory:delivery-outs')">成品出库</el-menu-item>
          <el-menu-item index="/inventory/stocktakes" v-if="hasPerm('menu:inventory:stocktake')">盘点管理</el-menu-item>
          <el-menu-item index="/inventory/management" v-if="hasPerm('menu:inventory')">库存查询</el-menu-item>
          <el-menu-item index="/inventory/batch-trace" v-if="hasPerm('menu:production:batch')">批次追溯</el-menu-item>
          <el-menu-item index="/inventory/summary" v-if="hasPerm('menu:inventory:summary')">收发存明细</el-menu-item>
        </el-sub-menu>

      </el-menu>
    </el-aside>

    <!-- 主区域 -->
    <el-container>
      <el-header style="height: 50px; background: #fff; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; justify-content: space-between; padding: 0 20px">
        <div>
          <el-button @click="isCollapse = !isCollapse" text>
            <el-icon><Fold /></el-icon>
          </el-button>
          <span style="margin-left: 10px; font-size: 14px; color: #606266">{{ pageTitle }}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px">
          <!-- 站内通知铃铛（所有登录用户可见） -->
          <el-popover placement="bottom-end" width="340" trigger="click" @show="loadNotifications">
            <template #reference>
              <el-badge :value="unreadCount" :hidden="!unreadCount" :max="99" style="cursor: pointer; margin-top: 2px">
                <el-icon size="20"><Bell /></el-icon>
              </el-badge>
            </template>
            <div style="max-height: 360px; overflow-y: auto">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px">
                <span style="font-size: 13px; font-weight: 600">消息通知</span>
                <el-button link type="primary" size="small" @click="handleMarkAllRead">全部已读</el-button>
              </div>
              <el-empty v-if="!notifications.length" description="暂无通知" :image-size="50" />
              <div v-for="n in notifications" :key="n.id" @click="handleNotificationClick(n)"
                   :style="{ padding: '8px 6px', borderBottom: '1px solid #f0f0f0', cursor: 'pointer' }">
                <div style="display: flex; align-items: center; gap: 6px">
                  <span v-if="n.read_status === 0" style="width: 6px; height: 6px; border-radius: 50%; background: #f56c6c; flex: none"></span>
                  <span style="font-size: 13px; font-weight: 500; flex: 1">{{ n.title }}</span>
                </div>
                <div style="font-size: 12px; color: #909399; margin-top: 2px">{{ n.content }}</div>
              </div>
            </div>
          </el-popover>
          <el-tag type="info" size="small">{{ user?.role === 'admin' ? '管理员' : '操作员' }}</el-tag>
          <span style="font-size: 13px">{{ user?.display_name || user?.username }}</span>
          <el-button @click="logout" type="danger" size="small" plain>退出</el-button>
        </div>
      </el-header>

      <el-main style="background: #f5f7fa; padding: 16px; overflow-y: auto">
        <router-view />
      </el-main>
    </el-container>

    <!-- 全局 AI 助手悬浮球 -->
    <MatsuAssistant />
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MatsuAssistant from './MatsuAssistant.vue'
import { notificationApi } from '../api/business'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const perms = ref(JSON.parse(localStorage.getItem('permissions') || '[]'))
function hasPerm(code) { return perms.value.includes(code) }
const unreadCount = ref(0)
const notifications = ref([])
let timer = null

function docRoute(docType) {
  const base = { so_order: '/sales/orders', so_delivery: '/sales/deliveries', ar_account: '/sales/ar', ap_account: '/purchase/ap' }
  return base[docType] || '/'
}

async function loadUnread() {
  if (!user.value?.id) return
  try {
    const res = await notificationApi.unreadCount()
    unreadCount.value = res.count || 0
  } catch (e) { /* 静默 */ }
}

async function loadNotifications() {
  try {
    const res = await notificationApi.latest({ limit: 20 })
    notifications.value = res || []
  } catch (e) { /* 静默 */ }
}

async function handleNotificationClick(n) {
  if (n.read_status === 0) {
    try { await notificationApi.markRead(n.id) } catch (e) { /* 静默 */ }
    n.read_status = 1
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  }
  const path = docRoute(n.doc_type)
  if (path !== '/') router.push(path)
}

async function handleMarkAllRead() {
  try {
    await notificationApi.markAllRead()
    notifications.value = notifications.value.map(n => ({ ...n, read_status: 1 }))
    unreadCount.value = 0
  } catch (e) { /* 静默 */ }
}

onMounted(() => {
  if (!user.value?.id) {
    router.push('/login')
    return
  }
  loadUnread()
  timer = setInterval(loadUnread, 30000)
})

onUnmounted(() => { if (timer) clearInterval(timer) })

const pageTitle = computed(() => {
  const path = route.path
  const titles = {
    '/foundation/materials': '原辅材料管理',
    '/foundation/products': '产品档案管理',
    '/foundation/bom': 'BOM管理',
    '/foundation/customers': '客户管理',
    '/foundation/suppliers': '供应商管理',
    '/foundation/warehouses': '仓库管理',
    '/foundation/currencies': '币种/汇率',
    '/foundation/processes': '工艺维护',
    '/purchase/from-sales': '销售订单转采购',
    '/purchase/orders': '采购订单',
    '/purchase/invoices': '采购发票',
    '/purchase/ap': '应付账款',
    '/purchase/payments': '付款管理',
    '/sales/orders': '销售订单',
    '/sales/deliveries': '销售发货',
    '/sales/invoices': '销售发票',
    '/sales/ar': '应收账款',
    '/sales/collections': '收款单',
    '/inventory/batch-trace': '批次追溯',
    '/inventory/management': '库存管理',
    '/inventory/stocktakes': '盘点管理',
    '/inventory/stock-ins': '成品入库',
    '/inventory/material-ins': '原料入库',
    '/inventory/material-outs': '原料出库',
    '/inventory/delivery-outs': '成品出库',
    '/outsource/from-sales': '销售订单转委外',
    '/outsource/orders': '委外订单',
    '/system/users': '用户管理',
    '/system/roles': '角色管理',
    '/system/wecom': '企业微信配置',
    '/system/bot': 'Agent设置',
    '/system/bot-chat': 'AI 助手',
    '/system/reminders': '预警提醒设置',
  }
  return titles[path] || 'MTS'
})

const currentRoute = computed(() => route.path)

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  localStorage.removeItem('permissions')
  router.push('/login')
}
</script>

<style scoped>
:deep(.el-menu) {
  --el-menu-item-height: 34px;
  --el-menu-sub-item-height: 34px;
  font-size: 12px;
}
:deep(.el-menu-item) {
  height: 34px;
  line-height: 34px;
  padding-left: 20px !important;
}
:deep(.el-sub-menu__title) {
  height: 38px;
  line-height: 38px;
  font-size: 12px;
}
:deep(.el-sub-menu .el-menu-item) {
  padding-left: 56px !important;
}
.el-header {
  height: 44px !important;
  font-size: 12px;
}
.el-main {
  font-size: 11px;
}
.el-main :deep(*) {
  font-size: 11px;
}
</style>
