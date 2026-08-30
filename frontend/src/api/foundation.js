import request from './request'

// 系统配置 API
export const systemConfigApi = {
  wecom: {
    list: () => request.get('/system/wecom'),
    create: (data) => request.post('/system/wecom', data),
    update: (id, data) => request.put(`/system/wecom/${id}`, data),
    delete: (id) => request.delete(`/system/wecom/${id}`),
  },
  bot: {
    list: () => request.get('/system/bot'),
    active: () => request.get('/system/bot/active'),
    create: (data) => request.post('/system/bot', data),
    update: (id, data) => request.put(`/system/bot/${id}`, data),
    delete: (id) => request.delete(`/system/bot/${id}`),
    defaultPrompt: () => request.get('/system/bot/default-prompt'),
  },
  reminders: {
    list: (params) => request.get('/system/reminders', { params }),
    types: () => request.get('/system/reminder-types'),
    create: (data) => request.post('/system/reminders', data),
    update: (id, data) => request.put(`/system/reminders/${id}`, data),
    delete: (id) => request.delete(`/system/reminders/${id}`),
    logs: (params) => request.get('/system/reminder-logs', { params }),
  },
}

// 认证相关
export const authApi = {
  login: (data) => request.post('/auth/login', data),
  getMe: () => request.get('/auth/me'),
  getMyPermissions: () => request.get('/auth/me/permissions'),
  listUsers: (params) => request.get('/auth/users', { params }),
  getUser: (id) => request.get(`/auth/users/${id}`),
  createUser: (data) => request.post('/auth/users', data),
  updateUser: (id, data) => request.put(`/auth/users/${id}`, data),
  deleteUser: (id) => request.delete(`/auth/users/${id}`),

  // 角色
  listRoles: () => request.get('/auth/roles'),
  createRole: (data) => request.post('/auth/roles', data),
  updateRole: (id, data) => request.put(`/auth/roles/${id}`, data),
  deleteRole: (id) => request.delete(`/auth/roles/${id}`),

  // 权限
  listPermissions: () => request.get('/auth/permissions'),
}

// 基础档案 — 通用 CRUD 工厂（methods 指定实际可用的方法，避免定义后端不存在的接口）
function crudApi(prefix, methods = ['list', 'get', 'create', 'update', 'delete', 'select']) {
  const map = {
    list: (params) => request.get(`/foundation/${prefix}`, { params }),
    get: (id) => request.get(`/foundation/${prefix}/${id}`),
    create: (data) => request.post(`/foundation/${prefix}`, data),
    update: (id, data) => request.put(`/foundation/${prefix}/${id}`, data),
    delete: (id) => request.delete(`/foundation/${prefix}/${id}`),
    select: (keyword) => request.get(`/foundation/${prefix}-select`, { params: { keyword } }),
  }
  const obj = {}
  for (const m of methods) {
    obj[m] = map[m]
    if (m === 'delete') obj.remove = map.delete  // 别名兼容（历史页面用 remove 调用）
  }
  return obj
}

export const foundationApi = {
  procurementItemsSelect: () => request.get('/foundation/procurement-items-select'),
  materials: crudApi('materials', ['list', 'create', 'update', 'delete', 'select']),
  products: Object.assign(crudApi('products'), {
    processTemplates: {
      list: (productId) => request.get(`/foundation/products/${productId}/processes`),
      save: (productId, items) => request.put(`/foundation/products/${productId}/processes`, { items }),
      delete: (productId, id) => request.delete(`/foundation/products/${productId}/processes/${id}`),
    },
  }),
  productCustomers: {
    update: (productId, data) => request.put(`/foundation/products/${productId}/customers`, data),
  },
  processes: crudApi('processes'),
  departments: crudApi('departments'),
  employees: crudApi('employees'),
  customers: { ...crudApi('customers'), nextCode: () => request.get('/foundation/customers/next-code') },
  suppliers: { ...crudApi('suppliers'), nextCode: () => request.get('/foundation/suppliers/next-code') },
  warehouses: crudApi('warehouses'),
  currencies: crudApi('currencies', ['list', 'get', 'create', 'update', 'delete']),
  exchangeRates: crudApi('exchange-rates', ['list', 'create', 'update', 'delete']),
  fetchExchangeRates: () => request.post('/foundation/exchange-rates/fetch'),
  hsCodes: crudApi('hs-codes', ['list', 'create', 'update', 'delete']),
  tradeTerms: crudApi('trade-terms', ['list', 'get', 'create', 'update', 'delete']),

  // BOM
  getBomByProduct: (productId) => request.get(`/foundation/bom/by-product/${productId}`),
  createBomItem: (data) => request.post('/foundation/bom', data),
  updateBomItem: (id, data) => request.put(`/foundation/bom/${id}`, data),
  deleteBomItem: (id) => request.delete(`/foundation/bom/${id}`),

  // 汇率
  latestRates: () => request.get('/foundation/exchange-rates/latest'),

  // 参数设置（SystemParams.vue）
  params: {
    list: (params) => request.get('/foundation/params', { params }),
    getGroup: (group) => request.get(`/foundation/params/group/${group}`),
    groups: () => request.get('/foundation/params/groups'),
    options: (params) => request.get('/foundation/params/options', { params }),
    create: (data) => request.post('/foundation/params', data),
    update: (id, data) => request.put(`/foundation/params/${id}`, data),
    remove: (id) => request.delete(`/foundation/params/${id}/hard`),
  },
}
