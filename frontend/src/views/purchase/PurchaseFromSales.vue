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
        已审核的销售订单转采购：点击「采购」按 BOM 展开物料清单，每个物料可指定不同供应商，系统自动按供应商拆成多张采购订单。
      </div>
    </el-card>

    <!-- ========== 销售明细行列表（销售订单那边点了「转入库」的行） ========== -->
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
          <el-table-column prop="source" label="来源" width="90" align="center" sortable>
            <template #default="{ row }">
              <el-tag v-if="row.source === '转外发'" type="success" size="small">转外发</el-tag>
              <el-tag v-else type="info" size="small">转直采</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="采购状态" width="120" align="center" sortable :sort-method="(a, b) => statusRank(a.purchase_status) - statusRank(b.purchase_status)">
            <template #default="{ row }">
              <el-tag v-if="row.purchase_status === 'completed'" type="success" size="small">采购完成</el-tag>
              <el-tag v-else-if="row.purchase_status === 'transferred'" type="success" size="small">已转采购订单</el-tag>
              <el-tag v-else-if="row.purchase_status === 'partial'" type="warning" size="small">部分采购</el-tag>
              <el-tag v-else type="info" size="small">未采购</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.purchase_status === 'none' || row.purchase_status === 'partial'" type="primary" size="small" @click="openPurchase(row)">采购</el-button>
              <el-button v-if="row.purchase_status === 'completed'" type="warning" size="small" @click="handleUncomplete(row)">取消完成</el-button>
              <el-button v-if="row.purchase_status === 'none'" type="danger" size="small" @click="handleReturn(row)">退回</el-button>
              <el-button v-if="row.purchase_status === 'transferred'" type="danger" size="small" @click="handleReturn(row)">退回</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" />
      </div>
    </el-card>

    <!-- ========== 采购弹窗（选供应商/数量/单价，自动拆单） ========== -->
    <el-dialog v-model="purchaseVisible" :title="`销售订单转采购：${currentOrderNo || ''}`" width="1280px" destroy-on-close>
      <div style="margin-bottom: 10px; display: flex; align-items: center; gap: 12px; font-size: 12px; color: #606266">
        <span>客户：{{ currentCustomer }} ｜ 产品：{{ currentProductName }}（批次 {{ currentBatchNo }}）</span>
        <span style="margin-left: auto; display: flex; align-items: center; gap: 4px">
          损耗
          <el-input-number v-model="lossPct" :min="0" :max="50" :precision="0" size="small" controls-position="right" style="width: 90px" />
          %
        </span>
      </div>
      <div style="margin-bottom: 10px; font-size: 12px; color: #909399">
        每个物料行选择供应商后，系统按供应商自动拆成多张采购订单，一次生成。单价默认带出参考采购价，可改。采购数量上限 = 需求数量 ×（1+损耗%），损耗默认 10%。
      </div>
      <el-table :data="purchaseRows" height="420" border size="small">
        <el-table-column type="index" label="#" width="45" align="center" />
        <el-table-column label="物料编码" width="120">
          <template #default="{ row }">{{ row.code }}</template>
        </el-table-column>
        <el-table-column label="物料名称" min-width="140">
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip sortable />
        <el-table-column prop="unit" label="单位" width="60" align="center" sortable />
        <el-table-column label="需求数量" width="95" align="right">
          <template #default="{ row }">{{ fmtQty(row.need_qty) }}</template>
        </el-table-column>
        <el-table-column label="已采购" width="80" align="right">
          <template #default="{ row }">{{ fmtQty(row.purchased_qty) }}</template>
        </el-table-column>
        <el-table-column label="本次采购" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="0" :max="Math.max(0, row.need_qty * (1 + lossPct / 100) - row.purchased_qty)" :precision="2" size="small" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="供应商" min-width="170">
          <template #default="{ row }">
            <el-button size="small" style="width: 100%" @click="openSupplierPicker(row)">
              {{ row.supplier_name || '选择供应商' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="单价" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="金额" width="100" align="right">
          <template #default="{ row }">{{ fmtMoney((row.quantity || 0) * (row.unit_price || 0)) }}</template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center">
        <div style="font-size: 12px; color: #909399">
          本次将拆成 <b style="color: #409eff">{{ supplierGroupCount }}</b> 张采购订单（按供应商分组）
        </div>
        <el-button type="primary" :loading="submitting" @click="submitPurchase">生成采购订单</el-button>
      </div>
    </el-dialog>

    <!-- ========== 供应商选择弹窗 ========== -->
    <el-dialog v-model="supplierPickerVisible" title="选择供应商" width="760px" destroy-on-close>
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-input v-model="supplierSearch" placeholder="输入编码/名称搜索，回车查询" clearable @keyup.enter="searchSuppliers" @clear="searchSuppliers" />
        <el-button type="primary" @click="searchSuppliers">搜索</el-button>
      </div>
      <el-table :data="pickerSupplierList" height="420" border size="small" highlight-current-row @row-click="pickSupplier">
        <el-table-column prop="code" label="编码" width="120" sortable />
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip sortable />
        <el-table-column prop="country" label="国家/地区" width="110" sortable />
        <el-table-column prop="contact_person" label="联系人" width="100" sortable />
        <el-table-column prop="phone" label="电话" width="120" show-overflow-tooltip sortable />
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="supplierPage" v-model:page-size="supplierPageSize" :total="supplierTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="searchSuppliers" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
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
    const res = await request.get('/purchase/sales-to-purchase', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载销售订单失败') } finally { loading.value = false }
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
  return s === 'completed' ? 3 : s === 'transferred' ? 2 : s === 'partial' ? 1 : 0
}

// ========== 采购弹窗 ==========
const purchaseVisible = ref(false)
const currentOrderId = ref(null)
const currentOrderNo = ref('')
const currentCustomer = ref('')
const currentBatchNo = ref('')
const currentProductName = ref('')
const lossPct = ref(10)
const purchaseRows = ref([])
const submitting = ref(false)

async function openPurchase(row) {
  try {
    const res = await request.get(`/purchase/sales-to-purchase/${row.sales_item_id}`)
    currentOrderId.value = row.order_id || row.sales_item_id
    currentOrderNo.value = res.order_no || ''
    currentCustomer.value = res.customer_name || ''
    currentBatchNo.value = res.batch_no || ''
    currentProductName.value = res.product_name || ''
    purchaseRows.value = (res.rows || []).map(r => ({
      ...r,
      quantity: Math.max(0, (r.need_qty || 0) * 1.1 - (r.purchased_qty || 0)),
      unit_price: r.ref_price || 0,
      supplier_id: r.default_supplier_id || null,
      supplier_name: '',
    }))
    // 默认供应商名称回填
    for (const r of purchaseRows.value) {
      if (r.supplier_id) {
        const s = pickerSupplierList.value.find(x => x.id === r.supplier_id)
        if (s) r.supplier_name = s.name
      }
    }
    purchaseVisible.value = true
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载采购需求明细失败') }
}

async function handleUncomplete(row) {
  try {
    await ElMessageBox.confirm(`确定取消采购完成？取消后可以继续追加采购。`, '取消完成确认', { type: 'warning' })
    const res = await request.post(`/purchase/sales-to-purchase/${row.sales_item_id}/uncomplete`)
    ElMessage.success(res.message || '已取消采购完成')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleReturn(row) {
  try {
    await ElMessageBox.confirm(`确定退回（撤销转入库）？退回后销售订单明细可重新变更/转采购。`, '退回确认', { type: 'warning' })
    const res = await request.post(`/purchase/sales-to-purchase/${row.sales_item_id}/return`)
    ElMessage.success(res.message || '已退回')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '退回失败')
  }
}

const supplierGroupCount = computed(() => {
  const sids = new Set(purchaseRows.value.filter(r => r.supplier_id && r.quantity > 0).map(r => r.supplier_id))
  return sids.size
})

async function submitPurchase() {
  const validRows = purchaseRows.value.filter(r => r.supplier_id && (r.quantity || 0) > 0)
  if (!validRows.length) { ElMessage.warning('请至少选择供应商并填写采购数量'); return }
  const missing = purchaseRows.value.filter(r => (r.quantity || 0) > 0 && !r.supplier_id)
  if (missing.length) { ElMessage.warning(`「${missing[0].name}」选择了数量但未选供应商`); return }
  const zeroPrice = validRows.filter(r => !(r.unit_price > 0))
  if (zeroPrice.length) { ElMessage.warning(`「${zeroPrice[0].name}」单价为 0，请填写单价`); return }
  submitting.value = true
  try {
    const payload = {
      sales_order_id: currentOrderId.value,
      loss_pct: lossPct.value,
      rows: validRows.map(r => ({
        sales_item_id: r.sales_item_id,
        material_id: r.material_id,
        product_id: r.product_id,
        supplier_id: r.supplier_id,
        quantity: r.quantity,
        unit_price: r.unit_price || 0,
        tax_rate: 13,
        need_qty: r.need_qty,
        name: r.name,
      })),
    }
    const res = await request.post('/purchase/orders/from-sales', payload)
    ElMessage.success(res.message || '采购订单已生成')
    purchaseVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '生成采购订单失败') } finally { submitting.value = false }
}

// ========== 供应商选择弹窗 ==========
const supplierPickerVisible = ref(false)
const supplierSearch = ref('')
const pickerSupplierList = ref([])
const supplierTotal = ref(0)
const supplierPage = ref(1)
const supplierPageSize = ref(100)
const supplierTargetRow = ref(null)

async function searchSuppliers() {
  try {
    const params = { page: supplierPage.value, page_size: supplierPageSize.value }
    if (supplierSearch.value) params.keyword = supplierSearch.value
    const res = await request.get('/foundation/suppliers', { params })
    pickerSupplierList.value = res.items || []
    supplierTotal.value = res.total || 0
  } catch (e) {}
}

function openSupplierPicker(row) {
  supplierTargetRow.value = row
  supplierSearch.value = ''
  supplierPage.value = 1
  searchSuppliers()
  supplierPickerVisible.value = true
}

function pickSupplier(s) {
  if (supplierTargetRow.value) {
    supplierTargetRow.value.supplier_id = s.id
    supplierTargetRow.value.supplier_name = s.name
  }
  supplierPickerVisible.value = false
}

onMounted(() => {
  fetchData()
  searchSuppliers()
})
</script>
