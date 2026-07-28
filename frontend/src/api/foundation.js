import request from './request'

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

// 基础档案 — 通用 CRUD 工厂
function crudApi(prefix) {
  return {
    list: (params) => request.get(`/foundation/${prefix}`, { params }),
    get: (id) => request.get(`/foundation/${prefix}/${id}`),
    create: (data) => request.post(`/foundation/${prefix}`, data),
    update: (id, data) => request.put(`/foundation/${prefix}/${id}`, data),
    delete: (id) => request.delete(`/foundation/${prefix}/${id}`),
    select: (keyword) => request.get(`/foundation/${prefix}-select`, { params: { keyword } }),
  }
}

export const foundationApi = {
  materials: crudApi('materials'),
  products: crudApi('products'),
  processes: crudApi('processes'),
  departments: crudApi('departments'),
  employees: crudApi('employees'),
  customers: crudApi('customers'),
  suppliers: crudApi('suppliers'),
  outsourcers: crudApi('outsourcers'),
  warehouses: crudApi('warehouses'),
  currencies: crudApi('currencies'),
  hsCodes: crudApi('hs-codes'),
  tradeTerms: crudApi('trade-terms'),

  // BOM
  getBomByProduct: (productId) => request.get(`/foundation/bom/by-product/${productId}`),
  createBomItem: (data) => request.post('/foundation/bom', data),
  updateBomItem: (id, data) => request.put(`/foundation/bom/${id}`, data),
  deleteBomItem: (id) => request.delete(`/foundation/bom/${id}`),

  // 汇率
  latestRates: () => request.get('/foundation/exchange-rates/latest'),
}
