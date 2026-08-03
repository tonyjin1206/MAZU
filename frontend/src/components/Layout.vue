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
        <el-menu-item index="/dashboard">工作台</el-menu-item>

        <!-- 系统管理 -->
        <el-sub-menu index="system">
          <template #title>系统管理</template>
          <el-menu-item index="/system/users">用户管理</el-menu-item>
          <el-menu-item index="/system/roles">角色管理</el-menu-item>
          <el-menu-item index="/system/wecom">企业微信</el-menu-item>
          <el-menu-item index="/system/bot">AI 模型</el-menu-item>
          <el-menu-item index="/system/bot-chat">AI 助手</el-menu-item>
          <el-menu-item index="/system/reminders">提醒管理</el-menu-item>
        </el-sub-menu>

        <!-- 1. 基础档案 -->
        <el-sub-menu index="foundation">
          <template #title>基础档案</template>
          <el-menu-item index="/foundation/customers">客户管理</el-menu-item>
          <el-menu-item index="/foundation/suppliers">供应商管理</el-menu-item>
          <el-menu-item index="/foundation/materials">原辅材料</el-menu-item>
          <el-menu-item index="/foundation/products">产品档案</el-menu-item>
          <el-menu-item index="/foundation/bom">BOM管理</el-menu-item>
          <el-menu-item index="/foundation/processes">工序管理</el-menu-item>
          <el-menu-item index="/foundation/hs-codes">HS编码/退税率</el-menu-item>
          <el-menu-item index="/foundation/params">参数设置</el-menu-item>
        </el-sub-menu>

        <!-- 2. 销售管理 -->
        <el-sub-menu index="sales">
          <template #title>销售管理</template>
          <el-menu-item index="/sales/orders">销售订单</el-menu-item>
          <el-menu-item index="/sales/deliveries">销售发货</el-menu-item>
          <el-menu-item index="/sales/invoices">销售发票</el-menu-item>
          <el-menu-item index="/sales/customs">报关管理</el-menu-item>
          <el-menu-item index="/sales/ar">应收账款</el-menu-item>
          <el-menu-item index="/sales/collections">收款管理</el-menu-item>
        </el-sub-menu>

        <!-- 3. 委外管理 -->
        <el-sub-menu index="outsource">
          <template #title>委外管理</template>
          <el-menu-item index="/outsource/orders">委外订单</el-menu-item>
          <el-menu-item index="/production/invoices">加工费发票</el-menu-item>
        </el-sub-menu>

        <!-- 4. 采购管理 -->
        <el-sub-menu index="purchase">
          <template #title>采购管理</template>
          <el-menu-item index="/purchase/from-sales">销售订单转采购</el-menu-item>
          <el-menu-item index="/purchase/orders">采购订单</el-menu-item>
          <el-menu-item index="/purchase/receipts">采购入库</el-menu-item>
          <el-menu-item index="/purchase/invoices">采购发票</el-menu-item>
          <el-menu-item index="/purchase/ap">应付账款</el-menu-item>
          <el-menu-item index="/purchase/payments">付款管理</el-menu-item>
        </el-sub-menu>

        <!-- 5. 库存管理 -->
        <el-sub-menu index="inventory">
          <template #title>库存管理</template>
          <el-menu-item index="/inventory/management">库存查询</el-menu-item>
          <el-menu-item index="/inventory/summary">收发存</el-menu-item>
          <el-menu-item index="/inventory/stock-ins">成品入库</el-menu-item>
          <el-menu-item index="/production/inventory">批次追溯</el-menu-item>
        </el-sub-menu>

        <!-- 6. 退税管理 -->
        <el-sub-menu index="tax-refund">
          <template #title>退税管理</template>
          <el-menu-item index="/tax-refund/declarations">退税申报</el-menu-item>
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
          <el-tag type="info" size="small">{{ user?.role === 'admin' ? '管理员' : '操作员' }}</el-tag>
          <span style="font-size: 13px">{{ user?.display_name || user?.username }}</span>
          <el-button @click="logout" type="danger" size="small" plain>退出</el-button>
        </div>
      </el-header>

      <el-main style="background: #f5f7fa; padding: 16px; overflow-y: auto">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))

onMounted(() => {
  if (!user.value?.id) {
    router.push('/login')
  }
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
    '/foundation/processes': '工序管理',
    '/purchase/from-sales': '销售订单转采购',
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
    '/production/outsourcings': '委外工单',
    '/production/orders': '生产订单',
    '/production/workspace': '生产工作台',
    '/production/invoices': '加工费发票',
    '/production/receipts': '完工入库',
    '/production/inventory': '批次库存/追溯',
    '/inventory/management': '库存管理',
    '/inventory/stock-ins': '成品入库',
    '/outsource/orders': '委外订单',
    '/tax-refund/declarations': '退税申报',
    '/system/users': '用户管理',
    '/system/roles': '角色管理',
    '/system/wecom': '企业微信配置',
    '/system/bot': 'AI 模型配置',
    '/system/bot-chat': 'AI 助手',
    '/system/reminders': '提醒管理',
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
