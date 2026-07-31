import request from './request'

export const purchaseApi = {
  orders: {
    list: (params) => request.get('/purchase/orders', { params }),
    get: (id) => request.get(`/purchase/orders/${id}`),
    create: (data) => request.post('/purchase/orders', data),
    update: (id, data) => request.put(`/purchase/orders/${id}`, data),
    delete: (id) => request.delete(`/purchase/orders/${id}`),
    approve: (id) => request.post(`/purchase/orders/${id}/approve`),
    unapprove: (id) => request.post(`/purchase/orders/${id}/unapprove`),
  },
  requisitions: {
    list: (params) => request.get('/purchase/requisitions', { params }),
    close: (id) => request.post(`/purchase/requisitions/${id}/close`),
    toPurchase: (id, data) => request.post(`/purchase/requisitions/${id}/to-purchase`, data),
  },
  receipts: {
    list: (params) => request.get('/purchase/receipts', { params }),
    get: (id) => request.get(`/purchase/receipts/${id}`),
    create: (data) => request.post('/purchase/receipts', data),
    delete: (id) => request.delete(`/purchase/receipts/${id}`),
    red: (id, data) => request.post(`/purchase/receipts/${id}/red`, data),
  },
  invoices: {
    list: (params) => request.get('/purchase/invoices', { params }),
    create: (data) => request.post('/purchase/invoices', data),
    update: (id, data) => request.put(`/purchase/invoices/${id}`, data),
    delete: (id) => request.delete(`/purchase/invoices/${id}`),
  },
  payments: {
    list: (params) => request.get('/purchase/payments', { params }),
    get: (id) => request.get(`/purchase/payments/${id}`),
    create: (data) => request.post('/purchase/payments', data),
    update: (id, data) => request.put(`/purchase/payments/${id}`, data),
    delete: (id) => request.delete(`/purchase/payments/${id}`),
  },
  ap: {
    list: (params) => request.get('/purchase/ap', { params }),
    paymentDetail: (params) => request.get('/purchase/ap/payment-detail', { params }),
  },
}

export const salesApi = {
  quotes: {
    list: (params) => request.get('/sales/quotes', { params }),
    create: (data) => request.post('/sales/quotes', data),
  },
  orders: {
    list: (params) => request.get('/sales/orders', { params }),
    get: (id) => request.get(`/sales/orders/${id}`),
    create: (data) => request.post('/sales/orders', data),
    update: (id, data) => request.put(`/sales/orders/${id}`, data),
    delete: (id) => request.delete(`/sales/orders/${id}`),
    approve: (id) => request.post(`/sales/orders/${id}/approve`),
    listItems: (params) => request.get('/sales/order-items', { params }),
    reProduce: (orderId, itemId) => request.post(`/sales/orders/${orderId}/items/${itemId}/re-produce`),
    updateItem: (orderId, itemId, data) => request.put(`/sales/orders/${orderId}/items/${itemId}`, data),
  },
  deliveries: {
    list: (params) => request.get('/sales/deliveries', { params }),
    create: (data) => request.post('/sales/deliveries', data),
    return: (id, data) => request.post(`/sales/deliveries/${id}/return`, data),
  },
  customs: {
    list: (params) => request.get('/sales/customs', { params }),
    get: (id) => request.get(`/sales/customs/${id}`),
    create: (data) => request.post('/sales/customs', data),
    update: (id, data) => request.put(`/sales/customs/${id}`, data),
    delete: (id) => request.delete(`/sales/customs/${id}`),
  },
  invoices: {
    list: (params) => request.get('/sales/invoices', { params }),
    create: (data) => request.post('/sales/invoices', data),
    update: (id, data) => request.put(`/sales/invoices/${id}`, data),
    delete: (id) => request.delete(`/sales/invoices/${id}`),
  },
  ar: {
    list: (params) => request.get('/sales/ar', { params }),
    collectionDetail: (params) => request.get('/sales/ar/collection-detail', { params }),
  },
  collections: {
    list: (params) => request.get('/sales/collections', { params }),
    get: (id) => request.get(`/sales/collections/${id}`),
    create: (data) => request.post('/sales/collections', data),
    update: (id, data) => request.put(`/sales/collections/${id}`, data),
    delete: (id) => request.delete(`/sales/collections/${id}`),
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
    setType: (id, data) => request.post(`/production/productions/${id}/set-type`, data),
    toRequisition: (id, data) => request.post(`/production/productions/${id}/to-requisition`, data),
    processingInvoices: {
      list: (params) => request.get('/production/processing-invoices', { params }),
      create: (data) => request.post('/production/processing-invoices', data),
      delete: (id) => request.delete(`/production/processing-invoices/${id}`),
      candidates: () => request.get('/production/processing-invoices/receipt-candidates'),
    },
    delete: (id) => request.delete(`/production/productions/${id}`),
  },
  batch: {
    query: (params) => request.get('/production/inventory/batch', { params }),
    trace: (batchNo) => request.get('/production/inventory/trace', { params: { batch_no: batchNo } }),
  },
}

export const foundationApi = {
  procurementItemsSelect: () => request.get('/foundation/procurement-items-select'),
  outsourcers: {
    select: () => request.get('/foundation/outsourcers-select'),
  },
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
    get: (id) => request.get(`/tax-refund/declarations/${id}`),
    create: (data) => request.post('/tax-refund/declarations', data),
    delete: (id) => request.delete(`/tax-refund/declarations/${id}`),
    submit: (id) => request.put(`/tax-refund/declarations/${id}/submit`),
    cancelSubmit: (id) => request.put(`/tax-refund/declarations/${id}/cancel-submit`),
    refund: (id) => request.put(`/tax-refund/declarations/${id}/refund`),
    cancelRefund: (id) => request.put(`/tax-refund/declarations/${id}/cancel-refund`),
    addRow: (declId, data) => request.post(`/tax-refund/declarations/${declId}/rows`, data),
    updateRow: (declId, rowId, data) => request.put(`/tax-refund/declarations/${declId}/rows/${rowId}`, data),
    deleteRow: (declId, rowId) => request.delete(`/tax-refund/declarations/${declId}/rows/${rowId}`),
  },
  calculate: (data) => request.post('/tax-refund/calculate', data),
  customsForRefund: (params) => request.get('/tax-refund/customs-for-refund', { params }),
  progress: {
    get: (declId) => request.get(`/tax-refund/progress/${declId}`),
    create: (data) => request.post('/tax-refund/progress', data),
  },
  statistics: (params) => request.get('/tax-refund/statistics', { params }),
}

// 驾驶舱
export const dashboardApi = {
  summary: () => request.get('/dashboard'),
  netCashDetail: (month) => request.get(`/dashboard/net-cash-detail/${month}`),
  profitDetail: (productId) => request.get(`/dashboard/profit-detail/${productId}`),
}

// 库存
export const inventoryApi = {
  balance: (params) => request.get('/inventory/balance', { params }),
  transactions: (params) => request.get('/inventory/transactions', { params }),
  availableBatches: (params) => request.get('/inventory/available-batches', { params }),
  // 盘点
  stocktakes: {
    list: (params) => request.get('/inventory/stocktakes', { params }),
    get: (id) => request.get(`/inventory/stocktakes/${id}`),
    create: (data) => request.post('/inventory/stocktakes', data),
    updateItem: (stocktakeId, itemId, data) => request.put(`/inventory/stocktakes/${stocktakeId}/items/${itemId}`, data),
    submit: (id) => request.post(`/inventory/stocktakes/${id}/submit`),
    remove: (id) => request.delete(`/inventory/stocktakes/${id}`),
  },
}

// AI 对话
export const chatApi = {
  message: (data) => request.post('/chat/message', data),
  reset: () => request.post('/chat/reset'),
}

