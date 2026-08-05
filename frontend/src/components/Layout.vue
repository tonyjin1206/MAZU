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

        <!-- 预警提醒设置（1级菜单） -->
        <el-menu-item index="/system/reminders" v-if="hasPerm('menu:system:reminders')">
          <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-bell"/></svg>
          <span>预警提醒设置</span>
        </el-menu-item>

        <!-- 通知查询（1级菜单，管理端全量验证用） -->
        <el-menu-item index="/system/notifications" v-if="hasPerm('menu:system:notifications')">
          <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-inbox-in"/></svg>
          <span>通知查询</span>
        </el-menu-item>

        <!-- 系统管理 -->
        <el-sub-menu index="system" v-if="hasPerm('menu:system:users') || hasPerm('menu:system:roles') || hasPerm('menu:system:wecom')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-lock"/></svg>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/system/users" v-if="hasPerm('menu:system:users')">用户管理</el-menu-item>
          <el-menu-item index="/system/roles" v-if="hasPerm('menu:system:roles')">角色管理</el-menu-item>
          <el-menu-item index="/system/wecom" v-if="hasPerm('menu:system:wecom')">企业微信</el-menu-item>
        </el-sub-menu>

        <!-- 1. 基础档案 -->
        <el-sub-menu index="foundation" v-if="hasPerm('menu:customers') || hasPerm('menu:suppliers') || hasPerm('menu:materials') || hasPerm('menu:products') || hasPerm('menu:bom') || hasPerm('menu:processes') || hasPerm('menu:hs-codes') || hasPerm('menu:warehouses') || hasPerm('menu:currencies')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-layer-group"/></svg>
            <span>基础档案</span>
          </template>
          <el-menu-item index="/foundation/customers" v-if="hasPerm('menu:customers')">客户管理</el-menu-item>
          <el-menu-item index="/foundation/suppliers" v-if="hasPerm('menu:suppliers')">供应商管理</el-menu-item>
          <el-menu-item index="/foundation/materials" v-if="hasPerm('menu:materials')">原辅材料</el-menu-item>
          <el-menu-item index="/foundation/products" v-if="hasPerm('menu:products')">产品档案</el-menu-item>
          <el-menu-item index="/foundation/bom" v-if="hasPerm('menu:bom')">BOM管理</el-menu-item>
          <el-menu-item index="/foundation/processes" v-if="hasPerm('menu:processes')">工序管理</el-menu-item>
          <el-menu-item index="/foundation/hs-codes" v-if="hasPerm('menu:hs-codes')">HS编码/退税率</el-menu-item>
          <el-menu-item index="/foundation/warehouses" v-if="hasPerm('menu:warehouses')">仓库管理</el-menu-item>
          <el-menu-item index="/foundation/currencies" v-if="hasPerm('menu:currencies')">币种/汇率</el-menu-item>
        </el-sub-menu>

        <!-- 2. 销售管理 -->
        <el-sub-menu index="sales" v-if="hasPerm('menu:sales:orders') || hasPerm('menu:sales:deliveries') || hasPerm('menu:sales:invoices') || hasPerm('menu:sales:customs') || hasPerm('menu:sales:ar') || hasPerm('menu:sales:collections')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-exchange"/></svg>
            <span>销售管理</span>
          </template>
          <el-menu-item index="/sales/orders" v-if="hasPerm('menu:sales:orders')">销售订单</el-menu-item>
          <el-menu-item index="/sales/deliveries" v-if="hasPerm('menu:sales:deliveries')">销售发货</el-menu-item>
          <el-menu-item index="/sales/invoices" v-if="hasPerm('menu:sales:invoices')">销售发票</el-menu-item>
          <el-menu-item index="/sales/customs" v-if="hasPerm('menu:sales:customs')">报关管理</el-menu-item>
          <el-menu-item index="/sales/ar" v-if="hasPerm('menu:sales:ar')">应收账款</el-menu-item>
          <el-menu-item index="/sales/collections" v-if="hasPerm('menu:sales:collections')">收款管理</el-menu-item>
        </el-sub-menu>

        <!-- 3. 生产管理 -->
        <el-sub-menu index="production" v-if="hasPerm('menu:production:orders') || hasPerm('menu:production:workspace') || hasPerm('menu:production:invoices')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-cog"/></svg>
            <span>生产管理</span>
          </template>
          <el-menu-item index="/production/orders" v-if="hasPerm('menu:production:orders')">生产订单</el-menu-item>
          <el-menu-item index="/production/workspace" v-if="hasPerm('menu:production:workspace')">生产工作台</el-menu-item>
          <el-menu-item index="/production/invoices" v-if="hasPerm('menu:production:invoices')">加工费发票</el-menu-item>
        </el-sub-menu>

        <!-- 4. 采购管理 -->
        <el-sub-menu index="purchase" v-if="hasPerm('menu:purchase:requisitions') || hasPerm('menu:purchase:orders') || hasPerm('menu:purchase:receipts') || hasPerm('menu:purchase:invoices') || hasPerm('menu:purchase:ap') || hasPerm('menu:purchase:payments')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-inbox-in"/></svg>
            <span>采购管理</span>
          </template>
          <el-menu-item index="/purchase/requisitions" v-if="hasPerm('menu:purchase:requisitions')">采购需求</el-menu-item>
          <el-menu-item index="/purchase/orders" v-if="hasPerm('menu:purchase:orders')">采购订单</el-menu-item>
          <el-menu-item index="/purchase/receipts" v-if="hasPerm('menu:purchase:receipts')">采购入库</el-menu-item>
          <el-menu-item index="/purchase/invoices" v-if="hasPerm('menu:purchase:invoices')">采购发票</el-menu-item>
          <el-menu-item index="/purchase/ap" v-if="hasPerm('menu:purchase:ap')">应付账款</el-menu-item>
          <el-menu-item index="/purchase/payments" v-if="hasPerm('menu:purchase:payments')">付款管理</el-menu-item>
        </el-sub-menu>

        <!-- 5. 库存管理 -->
        <el-sub-menu index="inventory" v-if="hasPerm('menu:inventory') || hasPerm('menu:inventory:stocktake') || hasPerm('menu:production:batch')">
          <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-database-set"/></svg>
            <span>库存管理</span>
          </template>
          <el-menu-item index="/inventory/management" v-if="hasPerm('menu:inventory')">库存收发存</el-menu-item>
          <el-menu-item index="/inventory/stocktakes" v-if="hasPerm('menu:inventory:stocktake')">盘点管理</el-menu-item>
          <el-menu-item index="/production/inventory" v-if="hasPerm('menu:production:batch')">批次追溯</el-menu-item>
        </el-sub-menu>

        <!-- 6. 退税管理 -->
        <el-sub-menu index="tax-refund" v-if="hasPerm('menu:tax')">
                    <template #title>
            <svg width="16" height="16" style="margin-right: 4px; vertical-align: middle"><use href="#icon-clouddownload"/></svg>
            <span>退税管理</span>
          </template>
          <el-menu-item index="/tax-refund/declarations" v-if="hasPerm('menu:tax')">退税申报</el-menu-item>
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
          <!-- 站内通知铃铛 -->
          <el-popover placement="bottom-end" :width="380" trigger="click" @show="fetchNotifs">
            <template #reference>
              <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99" class="bell-badge">
                <el-button text class="bell-btn" :class="{ 'bell-ring': unreadCount > 0 }">
                  <svg width="18" height="18" style="vertical-align: middle"><use href="#icon-bell"/></svg>
                </el-button>
              </el-badge>
            </template>
            <div style="max-height: 420px; overflow-y: auto">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
                <span style="font-weight: 600; font-size: 14px">通知</span>
                <el-button link type="primary" @click="markAllRead">全部已读</el-button>
              </div>
              <div v-if="notifs.length === 0" style="text-align: center; color: #909399; padding: 24px 0">暂无通知</div>
              <div v-for="n in notifs" :key="n.id" @click="openNotif(n)"
                   style="padding: 8px 6px; border-bottom: 1px solid #f0f0f0; cursor: pointer; border-radius: 4px"
                   :style="{ background: n.read_status === 0 ? '#f5f7fa' : 'transparent' }">
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span style="font-size: 13px; font-weight: 600; color: #303133">{{ n.title }}</span>
                  <el-tag v-if="n.read_status === 0" size="small" type="danger">新</el-tag>
                </div>
                <div style="font-size: 12px; color: #606266; margin-top: 2px; line-height: 1.4">{{ n.content }}</div>
                <div style="font-size: 12px; color: #909399; margin-top: 2px">{{ n.created_at }}</div>
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
import { ElMessage } from 'element-plus'
import MatsuAssistant from './MatsuAssistant.vue'
import { notificationApi } from '../api/foundation'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const perms = ref(JSON.parse(localStorage.getItem('permissions') || '[]'))
function hasPerm(code) { return perms.value.includes(code) }

// ============ 站内通知铃铛 ============
const unreadCount = ref(0)
const notifs = ref([])
let notifTimer = null

async function fetchUnread() {
  if (!user.value?.id) return
  try {
    const r = await notificationApi.unreadCount()
    unreadCount.value = r.count || 0
  } catch {}
}

async function fetchNotifs() {
  try {
    notifs.value = await notificationApi.latest({ limit: 10, only_unread: true }) || []
  } catch {}
}

async function markAllRead() {
  try {
    await notificationApi.readAll()
    unreadCount.value = 0
    notifs.value = []  // 全部已读 → 弹框不再显示
    ElMessage.success('已全部标记为已读')
  } catch {}
}

const DOC_ROUTES = {
  so_order: '/sales/orders',
  mo_production: '/production/orders',
  ar_account: '/sales/ar',
  ap_account: '/purchase/ap',
}

async function openNotif(n) {
  if (n.read_status === 0) {
    try {
      await notificationApi.markRead(n.id)
      n.read_status = 1
      // 已读 → 从弹框列表移除（弹框只显示未读）
      notifs.value = notifs.value.filter(x => x.id !== n.id)
      if (unreadCount.value > 0) unreadCount.value -= 1
    } catch {}
  }
  const target = DOC_ROUTES[n.doc_type]
  if (target) router.push(target)
}

onMounted(() => {
  if (!user.value?.id) {
    router.push('/login')
    return
  }
  fetchUnread()
  // 每 60 秒刷新未读数
  notifTimer = setInterval(fetchUnread, 60000)
})

onUnmounted(() => {
  if (notifTimer) clearInterval(notifTimer)
})

const pageTitle = computed(() => {
  const path = route.path
  const titles = {
    '/dashboard': '工作台',
    '/foundation/materials': '原辅材料管理',
    '/foundation/products': '产品档案管理',
    '/foundation/bom': 'BOM管理',
    '/foundation/customers': '客户管理',
    '/foundation/suppliers': '供应商管理',
    '/foundation/hs-codes': 'HS编码/退税率管理',
    '/foundation/warehouses': '仓库管理',
    '/foundation/currencies': '币种/汇率',
    '/foundation/processes': '工序管理',
    '/purchase/requisitions': '采购需求',
    '/purchase/orders': '采购订单',
    '/purchase/receipts': '采购入库',
    '/purchase/invoices': '采购发票',
    '/purchase/ap': '应付账款',
    '/purchase/payments': '付款管理',
    '/sales/orders': '销售订单',
    '/sales/deliveries': '销售发货',
    '/sales/invoices': '销售发票',
    '/sales/customs': '报关管理',
    '/sales/ar': '应收账款',
    '/sales/collections': '收款单',
    '/production/orders': '生产订单',
    '/production/workspace': '生产工作台',
    '/production/invoices': '加工费发票',
    '/production/inventory': '批次库存/追溯',
    '/inventory/management': '库存管理',
    '/inventory/stocktakes': '盘点管理',
    '/tax-refund/declarations': '退税申报',
    '/system/users': '用户管理',
    '/system/roles': '角色管理',
    '/system/wecom': '企业微信配置',
    '/system/bot': 'Agent设置',
    '/system/bot-chat': 'AI 助手',
    '/system/reminders': '预警提醒设置',
    '/system/notifications': '通知查询',
  }
  if (path.startsWith('/production/detail')) return '生产订单详情'
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
  padding-left: 48px !important;
}
.el-header {
  height: 44px !important;
  font-size: 12px;
}
.el-main {
  font-size: 11px;
}
/* 通知铃铛：无提醒静态灰 / 有提醒红色动态闪烁 + 红点 */
.bell-btn {
  color: #909399;
  padding: 3px;
  display: inline-flex;
  margin-right: 24px; /* 与右侧操作员/退出拉开距离，铃铛视觉靠左 */
}
.bell-ring {
  color: #f56c6c;
  animation: bell-flash 1.2s ease-in-out infinite;
}
/* 红点数字：小一号、垂直对齐铃铛中线（top 定位代替 translateY） */
.bell-badge :deep(.el-badge__content) {
  font-size: 10px;
  height: 15px;
  line-height: 15px;
  min-width: 15px;
  padding: 0 4px;
  top: 5px;              /* 铃铛18px+padding3px，中线≈12px，badge中心=top+7.5 */
  transform: translate(40%, 0);
}
@keyframes bell-flash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.el-main :deep(*) {
  font-size: 11px;
}
</style>
