import request from './request'

// 认证相关
export const authApi = {
  login: (data) => request.post('/auth/login', data),
  getMe: () => request.get('/auth/me'),
  listUsers: () => request.get('/auth/users'),
  createUser: (data) => request.post('/auth/users', data),
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
