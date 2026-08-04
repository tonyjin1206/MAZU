<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- ========== 搜索区 ========== -->
    <el-card style="margin-bottom: 8px; flex: none">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-input v-model="searchForm.keyword" placeholder="输入销售订单号/客户搜索，回车查询" clearable style="width: 280px" @keyup.enter="resetSearch" @clear="resetSearch" />
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <div style="font-size: 12px; color: #606266">
        已审核的销售订单转委外：点击「转委外」选择明细行生成委外订单（草稿），委外商/加工单价请在「委外订单」中维护后审核。
      </div>
    </el-card>

    <!-- ========== 销售明细行列表（销售订单那边点了「转外发」的行） ========== -->
    <el-card style="flex: 1; overflow: hidden; display: flex; flex-direction: column">
      <div style="flex: 1; overflow: auto">
        <el-table v-loading="loading" :data="dataList" height="100%" border stripe size="small" highlight-current-row class="drag-table-so">
          <el-table-column prop="order_no" label="销售订单号" min-width="150" sortable />
          <el-table-column prop="customer_name" label="客户" min-width="120" show-overflow-tooltip sortable />
          <el-table-column prop="code" label="产品编码" min-width="110" sortable />
          <el-table-column prop="name" label="产品名称" min-width="130" show-overflow-tooltip sortable />
          <el-table-column prop="spec" label="规格" min-width="90" show-overflow-tooltip sortable />
          <el-table-column prop="unit" label="单位" width="60" align="center" sortable />
          <el-table-column prop="quantity" label="数量" width="95" align="right" sortable>
            <template #default="{ row }">{{ fmtQty(row.quantity) }}</template>
          </el-table-column>
          <el-table-column prop="batch_no" label="批次号" min-width="150" show-overflow-tooltip sortable />
          <el-table-column label="委外状态" width="100" align="center" sortable :sort-method="(a, b) => statusRank(a.outsource_status) - statusRank(b.outsource_status)">
            <template #default="{ row }">
              <el-tag v-if="row.outsource_status === 'completed'" type="success" size="small">委外完成</el-tag>
              <el-tag v-else-if="row.outsource_status === 'partial'" type="warning" size="small">部分转委外</el-tag>
              <el-tag v-else type="info" size="small">未转委外</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.outsource_status === 'none' || row.outsource_status === 'partial'" type="primary" size="small" @click="openTransfer(row)">转委外</el-button>
              <el-button v-if="row.outsource_status !== 'completed'" type="danger" size="small" @click="handleReturn(row)">退回</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" />
      </div>
    </el-card>

    <!-- ========== 转委外弹窗 ========== -->
    <el-dialog v-model="transferVisible" :title="`销售订单转委外：${currentOrderNo || ''}`" width="1000px" destroy-on-close>
      <div style="margin-bottom: 10px; font-size: 12px; color: #606266">
        客户：{{ currentCustomer }} ｜ 批次 {{ currentBatchNo }} ｜ 勾选明细行并填写委外数量，确认后生成委外订单（草稿）。委外商/加工单价请在委外订单中维护。
      </div>
      <el-table :data="transferRows" height="420" border size="small" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="45" align="center" />
        <el-table-column label="产品编码" width="120">
          <template #default="{ row }">{{ row.code }}</template>
        </el-table-column>
        <el-table-column label="产品名称" min-width="140">
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="60" align="center" />
        <el-table-column label="销售数量" width="95" align="right">
          <template #default="{ row }">{{ fmtQty(row.need_qty) }}</template>
        </el-table-column>
        <el-table-column label="已转委外" width="90" align="right">
          <template #default="{ row }">{{ fmtQty(row.outsourced_qty) }}</template>
        </el-table-column>
        <el-table-column label="本次转委外" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="0" :max="Math.max(0, row.need_qty - row.outsourced_qty)" :precision="2" size="small" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-button type="primary" :loading="submitting" @click="submitTransfer">生成委外订单</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'

// ========== 销售订单列表 ==========
const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })
const searchForm = reactive({ keyword: '' })

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    const res = await request.get('/outsource/sales-to-outsource', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch { ElMessage.error('加载销售订单失败') } finally { loading.value = false }
}

function resetSearch() {
  searchForm.keyword = ''
  queryParams.page = 1
  fetchData()
}

function fmtMoney(v) {
  return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function fmtQty(v) {
  return Number(v || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function statusRank(s) {
  return s === 'completed' ? 2 : s === 'partial' ? 1 : 0
}

// ========== 转委外弹窗 ==========
const transferVisible = ref(false)
const currentOrderId = ref(null)
const currentOrderNo = ref('')
const currentCustomer = ref('')
const currentBatchNo = ref('')
const transferRows = ref([])
const selectedRows = ref([])
const submitting = ref(false)

async function openTransfer(row) {
  try {
    const res = await request.get(`/outsource/sales-to-outsource/${row.sales_item_id}`)
    currentOrderId.value = row.order_id || row.sales_item_id
    currentOrderNo.value = res.order_no || ''
    currentCustomer.value = res.customer_name || ''
    currentBatchNo.value = res.batch_no || ''
    transferRows.value = (res.rows || []).map(r => ({
      ...r,
      quantity: Math.max(0, (r.need_qty || 0) - (r.outsourced_qty || 0)),
    }))
    selectedRows.value = []
    transferVisible.value = true
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载销售明细失败') }
}

async function handleReturn(row) {
  try {
    const tip = row.outsource_status === 'none' ? '确定退回（撤销转外发）？退回后销售订单明细可重新变更/转委外。' : `确定退回 ${row.name}（批次 ${row.batch_no}）关联的委外订单？退回后销售订单明细可重新变更/转委外。`
    await ElMessageBox.confirm(tip, '退回确认', { type: 'warning' })
    const res = await request.post(`/outsource/sales-to-outsource/${row.sales_item_id}/return`)
    ElMessage.success(res.message || '已退回')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '退回失败')
  }
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

async function submitTransfer() {
  const validRows = selectedRows.value.filter(r => (r.quantity || 0) > 0)
  if (!validRows.length) { ElMessage.warning('请勾选明细行并填写委外数量'); return }
  submitting.value = true
  try {
    const payload = {
      sales_order_id: currentOrderId.value,
      rows: validRows.map(r => ({ sales_item_id: r.sales_item_id, quantity: r.quantity })),
    }
    const res = await request.post('/outsource/orders/from-sales', payload)
    ElMessage.success(res.message || '委外订单已生成')
    transferVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '生成委外订单失败') } finally { submitting.value = false }
}

onMounted(() => {
  fetchData()
})
</script>
