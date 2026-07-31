import request from './request'

export const purchaseApi = {
  orders: {
    list: (params) => request.get('/purchase/orders', { params }),
    get: (id) => request.get(`/purchase/orders/${id}`),
    create: (data) => request.post('/purchase/orders', data),
    delete: (id) => request.delete(`/purchase/orders/${id}`),
    approve: (id) => request.post(`/purchase/orders/${id}/approve`),
  },
  receipts: {
    list: (params) => request.get('/purchase/receipts', { params }),
    create: (data) => request.post('/purchase/receipts', data),
  },
  invoices: {
    create: (data) => request.post('/purchase/invoices', data),
  },
  payments: {
    create: (data) => request.post('/purchase/payments', data),
  },
  ap: {
    list: (params) => request.get('/purchase/ap', { params }),
  },
}

export const salesApi = {
  quotes: {
    list: (params) => request.get('/sales/quotes', { params }),
    create: (data) => request.post('/sales/quotes', data),
  },
  orders: {
    list: (params) => request.get('/sales/orders', { params }),
    create: (data) => request.post('/sales/orders', data),
    approve: (id) => request.post(`/sales/orders/${id}/approve`),
  },
  deliveries: {
    list: (params) => request.get('/sales/deliveries', { params }),
    create: (data) => request.post('/sales/deliveries', data),
  },
  customs: {
    list: (params) => request.get('/sales/customs', { params }),
    create: (data) => request.post('/sales/customs', data),
  },
  invoices: {
    create: (data) => request.post('/sales/invoices', data),
  },
  ar: {
    list: (params) => request.get('/sales/ar', { params }),
  },
  collections: {
    create: (data) => request.post('/sales/collections', data),
  },
}

export const productionApi = {
  productions: {
    update: (id, data) => request.put(`/production/productions/${id}`, data),
    list: (params) => request.get('/production/productions', { params }),
    detail: (id) => request.get(`/production/productions/${id}`),
    expandBom: (id) => request.post(`/production/productions/${id}/expand-bom`),
    saveMaterials: (id, items) => request.put(`/production/productions/${id}/materials`, { items }),
    saveProcesses: (id, items) => request.put(`/production/productions/${id}/processes`, { items }),
    release: (id) => request.post(`/production/productions/${id}/release`),
    unrelease: (id) => request.post(`/production/productions/${id}/unrelease`),
    issueMaterial: (prodId, procId, data) => request.post(`/production/productions/${prodId}/processes/${procId}/issue`, data),
    finishProcess: (prodId, procId, data) => request.post(`/production/productions/${prodId}/processes/${procId}/finish`, data),
    receipt: (prodId, data) => request.post(`/production/productions/${prodId}/receipt`, data),
    workspace: (params) => request.get('/production/workspace', { params }),
    listIssues: (prodId, processId) => request.get(`/production/productions/${prodId}/issues`, { params: { process_id: processId } }),
    listMaterialIssues: (prodId, materialId) => request.get(`/production/productions/${prodId}/material-issues/${materialId}`),
    listReceipts: (prodId) => request.get(`/production/productions/${prodId}/receipts`),
    listTransactions: (prodId) => request.get(`/production/productions/${prodId}/transactions`),
    cancelIssue: (prodId, issueId) => request.post(`/production/productions/${prodId}/issues/${issueId}/cancel`),
    cancelReceipt: (prodId, receiptId) => request.post(`/production/productions/${prodId}/receipts/${receiptId}/cancel`),
    close: (id) => request.post(`/production/productions/${id}/close`),
    unclose: (id) => request.post(`/production/productions/${id}/unclose`),
    revertProcess: (prodId, procId) => request.post(`/production/productions/${prodId}/processes/${procId}/revert`),
    processingInvoices: {
      list: (params) => request.get('/production/processing-invoices', { params }),
      create: (data) => request.post('/production/processing-invoices', data),
      delete: (id) => request.delete(`/production/processing-invoices/${id}`),
      candidates: () => request.get('/production/processing-invoices/receipt-candidates'),
    },
    delete: (id) => request.delete(`/production/productions/${id}`),
  },
  outsourcings: {
    list: (params) => request.get('/production/outsourcings', { params }),
    create: (data) => request.post('/production/outsourcings', data),
    update: (id, data) => request.put(`/production/outsourcings/${id}`, data),
    delete: (id) => request.delete(`/production/outsourcings/${id}`),
  },
  materialIssues: {
    create: (data) => request.post('/production/material-issues', data),
  },
  outsourceReceipts: {
    list: (params) => request.get('/production/outsource-receipts', { params }),
    create: (data) => request.post('/production/outsource-receipts', data),
  },
  batch: {
    query: (params) => request.get('/production/inventory/batch', { params }),
    trace: (batchNo) => request.get('/production/inventory/trace', { params: { batch_no: batchNo } }),
  },
}

export const foundationApi = {
  products: {
    processTemplates: {
      list: (productId) => request.get(`/foundation/products/${productId}/processes`),
      save: (productId, items) => request.put(`/foundation/products/${productId}/processes`, { items }),
      delete: (productId, id) => request.delete(`/foundation/products/${productId}/processes/${id}`),
    },
  },
}

export const taxRefundApi = {
  inputInvoices: {
    list: (params) => request.get('/tax-refund/input-invoices', { params }),
    create: (data) => request.post('/tax-refund/input-invoices', data),
  },
  declarations: {
    list: (params) => request.get('/tax-refund/declarations', { params }),
    create: (data) => request.post('/tax-refund/declarations', data),
    details: (declId) => request.get(`/tax-refund/declarations/${declId}/details`),
  },
  calculate: (data) => request.post('/tax-refund/calculate', data),
  customsForRefund: (params) => request.get('/tax-refund/customs-for-refund', { params }),
  progress: {
    get: (declId) => request.get(`/tax-refund/progress/${declId}`),
    create: (data) => request.post('/tax-refund/progress', data),
  },
  statistics: (params) => request.get('/tax-refund/statistics', { params }),
}
