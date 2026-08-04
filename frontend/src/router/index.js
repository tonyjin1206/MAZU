import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },

      // 基础档案
      { path: 'foundation/materials', name: 'Materials', component: () => import('../views/foundation/Materials.vue') },
      { path: 'foundation/products', name: 'Products', component: () => import('../views/foundation/Products.vue') },
      { path: 'foundation/bom', name: 'Bom', component: () => import('../views/foundation/Bom.vue') },
      { path: 'foundation/customers', name: 'Customers', component: () => import('../views/foundation/Customers.vue') },
      { path: 'foundation/suppliers', name: 'Suppliers', component: () => import('../views/foundation/Suppliers.vue') },
      { path: 'foundation/hs-codes', name: 'HsCodes', component: () => import('../views/foundation/HsCodes.vue') },
      { path: 'foundation/processes', name: 'Processes', component: () => import('../views/foundation/Processes.vue') },
      { path: 'foundation/params', name: 'SystemParams', component: () => import('../views/foundation/SystemParams.vue') },

      // 采购管理
      { path: 'purchase/from-sales', name: 'PurchaseFromSales', component: () => import('../views/purchase/PurchaseFromSales.vue') },
      { path: 'purchase/orders', name: 'PurchaseOrders', component: () => import('../views/purchase/PurchaseOrders.vue') },
      { path: 'purchase/receipts', name: 'PurchaseReceipts', component: () => import('../views/purchase/PurchaseReceipts.vue') },
      { path: 'purchase/invoices', name: 'PurchaseInvoices', component: () => import('../views/purchase/PurchaseInvoices.vue') },
      { path: 'purchase/ap', name: 'AccountsPayable', component: () => import('../views/purchase/AccountsPayable.vue') },
      { path: 'purchase/payments', name: 'Payments', component: () => import('../views/purchase/Payments.vue') },

      // 销售管理
      { path: 'sales/orders', name: 'SalesOrders', component: () => import('../views/sales/SalesOrders.vue') },
      { path: 'sales/deliveries', name: 'SalesDeliveries', component: () => import('../views/sales/SalesDeliveries.vue') },
      { path: 'sales/invoices', name: 'SalesInvoices', component: () => import('../views/sales/SalesInvoices.vue') },
      { path: 'sales/customs', name: 'CustomsDeclarations', component: () => import('../views/sales/CustomsDeclarations.vue') },
      { path: 'sales/ar', name: 'AccountsReceivable', component: () => import('../views/sales/AccountsReceivable.vue') },
      { path: 'sales/collections', name: 'Collections', component: () => import('../views/sales/Collections.vue') },

      // 委外管理
      { path: 'outsource/from-sales', name: 'OutsourceFromSales', component: () => import('../views/outsource/OutsourceFromSales.vue') },
      { path: 'outsource/orders', name: 'OutsourceOrders', component: () => import('../views/outsource/OutsourceOrders.vue') },
      { path: 'production/invoices', name: 'ProcessingInvoices', component: () => import('../views/production/ProcessingInvoices.vue') },

      // 库存管理
      { path: 'inventory/management', name: 'InventoryManagement', component: () => import('../views/inventory/InventoryManagement.vue') },
      { path: 'inventory/summary', name: 'StockSummary', component: () => import('../views/inventory/StockSummary.vue') },
      { path: 'inventory/stock-ins', name: 'StockIns', component: () => import('../views/inventory/StockIns.vue') },
      { path: 'production/inventory', name: 'BatchInventory', component: () => import('../views/production/BatchInventory.vue') },

      // 退税管理
      { path: 'tax-refund/declarations', name: 'TaxRefund', component: () => import('../views/taxRefund/TaxRefundDeclarations.vue') },

      // 系统管理
      { path: 'system/users', name: 'SystemUsers', component: () => import('../views/system/Users.vue') },
      { path: 'system/roles', name: 'SystemRoles', component: () => import('../views/system/Roles.vue') },
      { path: 'system/wecom', name: 'WecomConfig', component: () => import('../views/system/WecomConfig.vue') },
      { path: 'system/bot', name: 'BotConfig', component: () => import('../views/system/BotConfig.vue') },
      { path: 'system/bot-chat', name: 'BotChat', component: () => import('../views/system/BotChat.vue') },
      { path: 'system/reminders', name: 'Reminders', component: () => import('../views/system/Reminders.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转登录页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  const isValid = token && userStr

  if (to.path !== '/login' && !isValid) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    next('/login')
  } else if (to.path === '/login' && isValid) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
