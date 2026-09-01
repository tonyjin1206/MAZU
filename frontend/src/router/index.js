import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { perm: 'menu:dashboard' } },
      // 基础档案
      { path: 'foundation/materials', name: 'Materials', component: () => import('../views/foundation/Materials.vue'), meta: { perm: 'menu:materials' } },
      { path: 'foundation/products', name: 'Products', component: () => import('../views/foundation/Products.vue'), meta: { perm: 'menu:products' } },
      { path: 'foundation/bom', name: 'Bom', component: () => import('../views/foundation/Bom.vue'), meta: { perm: 'menu:bom' } },
      { path: 'foundation/customers', name: 'Customers', component: () => import('../views/foundation/Customers.vue'), meta: { perm: 'menu:customers' } },
      { path: 'foundation/suppliers', name: 'Suppliers', component: () => import('../views/foundation/Suppliers.vue'), meta: { perm: 'menu:suppliers' } },
      { path: 'foundation/processes', name: 'Processes', component: () => import('../views/foundation/Processes.vue'), meta: { perm: 'menu:processes' } },
      { path: 'foundation/params', name: 'SystemParams', component: () => import('../views/foundation/SystemParams.vue'), meta: { perm: 'menu:params' } },
      { path: 'foundation/warehouses', name: 'Warehouses', component: () => import('../views/foundation/Warehouses.vue'), meta: { perm: 'menu:warehouses' } },
      { path: 'foundation/currencies', name: 'CurrencyRates', component: () => import('../views/foundation/CurrencyRates.vue'), meta: { perm: 'menu:currencies' } },

      // 采购管理
      { path: 'purchase/from-sales', name: 'PurchaseFromSales', component: () => import('../views/purchase/PurchaseFromSales.vue'), meta: { perm: 'menu:purchase:from-sales' } },
      { path: 'purchase/requisitions', redirect: '/purchase/from-sales' },
      { path: 'purchase/orders', name: 'PurchaseOrders', component: () => import('../views/purchase/PurchaseOrders.vue'), meta: { perm: 'menu:purchase:orders' } },
      { path: 'purchase/receipts', name: 'PurchaseReceipts', component: () => import('../views/purchase/PurchaseReceipts.vue'), meta: { perm: 'menu:purchase:receipts' } },
      { path: 'purchase/invoices', name: 'PurchaseInvoices', component: () => import('../views/purchase/PurchaseInvoices.vue'), meta: { perm: 'menu:purchase:invoices' } },
      { path: 'purchase/ap', name: 'AccountsPayable', component: () => import('../views/purchase/AccountsPayable.vue'), meta: { perm: 'menu:purchase:ap' } },
      { path: 'purchase/payments', name: 'Payments', component: () => import('../views/purchase/Payments.vue'), meta: { perm: 'menu:purchase:payments' } },
      // 销售管理
      { path: 'sales/orders', name: 'SalesOrders', component: () => import('../views/sales/SalesOrders.vue'), meta: { perm: 'menu:sales:orders' } },
      { path: 'sales/deliveries', name: 'SalesDeliveries', component: () => import('../views/sales/SalesDeliveries.vue'), meta: { perm: 'menu:sales:deliveries' } },
      { path: 'sales/invoices', name: 'SalesInvoices', component: () => import('../views/sales/SalesInvoices.vue'), meta: { perm: 'menu:sales:invoices' } },
      { path: 'sales/ar', name: 'AccountsReceivable', component: () => import('../views/sales/AccountsReceivable.vue'), meta: { perm: 'menu:sales:ar' } },
      { path: 'sales/collections', name: 'Collections', component: () => import('../views/sales/Collections.vue'), meta: { perm: 'menu:sales:collections' } },

      // 生产管理（路由保留，菜单不显示）
      { path: 'production/orders', name: 'ProductionOrders', component: () => import('../views/production/ProductionOrders.vue'), meta: { perm: 'menu:production:orders' } },
      { path: 'production/detail/:id', name: 'ProductionDetail', component: () => import('../views/production/ProductionDetail.vue'), meta: { perm: 'menu:production:orders' } },
      { path: 'production/workspace', name: 'ProductionWorkspace', component: () => import('../views/production/ProductionWorkspace.vue'), meta: { perm: 'menu:production:workspace' } },
      { path: 'production/invoices', name: 'ProcessingInvoices', component: () => import('../views/production/ProcessingInvoices.vue'), meta: { perm: 'menu:production:invoices' } },
      { path: 'production/inventory', name: 'BatchInventory', component: () => import('../views/production/BatchInventory.vue'), meta: { perm: 'menu:production:batch' } },

      // 委外管理
      { path: 'outsource/from-sales', name: 'OutsourceFromSales', component: () => import('../views/outsource/OutsourceFromSales.vue'), meta: { perm: 'menu:outsource:from-sales' } },
      { path: 'outsource/orders', name: 'OutsourceOrders', component: () => import('../views/outsource/OutsourceOrders.vue'), meta: { perm: 'menu:outsource:orders' } },

      // 库存管理
      { path: 'inventory/management', name: 'InventoryManagement', component: () => import('../views/inventory/InventoryManagement.vue'), meta: { perm: 'menu:inventory' } },
      { path: 'inventory/summary', name: 'StockSummary', component: () => import('../views/inventory/StockSummary.vue'), meta: { perm: 'menu:inventory:summary' } },
      { path: 'inventory/stock-ins', name: 'StockIns', component: () => import('../views/inventory/StockIns.vue'), meta: { perm: 'menu:inventory:stock-ins' } },
      { path: 'inventory/material-ins', name: 'MaterialIns', component: () => import('../views/inventory/MaterialIns.vue'), meta: { perm: 'menu:inventory:material-ins' } },
      { path: 'inventory/material-outs', name: 'MaterialOuts', component: () => import('../views/inventory/MaterialOuts.vue'), meta: { perm: 'menu:inventory:material-outs' } },
      { path: 'inventory/delivery-outs', name: 'DeliveryOuts', component: () => import('../views/inventory/DeliveryOuts.vue'), meta: { perm: 'menu:inventory:delivery-outs' } },
      { path: 'inventory/stocktakes', name: 'StocktakeManagement', component: () => import('../views/inventory/StocktakeManagement.vue'), meta: { perm: 'menu:inventory:stocktake' } },

      // 系统管理
      { path: 'system/users', name: 'SystemUsers', component: () => import('../views/system/Users.vue'), meta: { perm: 'menu:system:users' } },
      { path: 'system/roles', name: 'SystemRoles', component: () => import('../views/system/Roles.vue'), meta: { perm: 'menu:system:roles' } },
      { path: 'system/wecom', name: 'WecomConfig', component: () => import('../views/system/WecomConfig.vue'), meta: { perm: 'menu:system:wecom' } },
      { path: 'system/bot', name: 'BotConfig', component: () => import('../views/system/BotConfig.vue'), meta: { perm: 'menu:system:bot' } },
      { path: 'system/bot-chat', name: 'BotChat', component: () => import('../views/system/BotChat.vue'), meta: { perm: 'menu:system:bot-chat' } },
      { path: 'system/notifications', name: 'Notifications', component: () => import('../views/system/Notifications.vue'), meta: { perm: 'menu:system:reminders' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转登录页；无权限跳回销售订单
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  const isValid = token && userStr

  if (to.path !== '/login' && !isValid) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('permissions')
    next('/login')
  } else if (to.path === '/login' && isValid) {
    next('/dashboard')
  } else {
    // 菜单级权限校验（to.meta.perm 为该页面所需权限码）
    const required = to.meta?.perm
    if (required) {
      let perms = []
      try { perms = JSON.parse(localStorage.getItem('permissions') || '[]') } catch (e) { /* ignore */ }
      if (!perms.includes(required)) {
        ElMessage.warning('没有访问该页面的权限')
        next('/dashboard')
        return
      }
    }
    next()
  }
})

export default router
