<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display:flex;justify-content:flex-end;gap:8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建发货</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap:nowrap">
        <el-form-item label="关键词"><el-input v-model="searchForm.keyword" placeholder="发货单号/客户" clearable style="width:160px" @keyup.enter="fetchList" /></el-form-item>
        <el-form-item label="日期范围"><el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width:220px" /></el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width:100%">
        <el-table-column prop="delivery_no" label="发货单号" width="160" sortable />
        <el-table-column prop="order_no" label="关联订单" width="160" sortable />
        <el-table-column prop="product_name" label="产品" min-width="140" sortable column-key="product_name" :filters="productFilters" :filter-method="filterProduct" />
        <el-table-column prop="batch_no" label="批次号" width="140" sortable />
        <el-table-column label="数量" width="90" align="right" sortable><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
        <el-table-column label="单价" width="100" align="right" sortable><template #default="{ row }">{{ $fm(row.unit_price) }}</template></el-table-column>
        <el-table-column label="金额" width="100" align="right" sortable><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column prop="delivery_date" label="发货日期" width="110" sortable column-key="delivery_date" :filters="dateFilters" :filter-method="filterDate" />
        <el-table-column prop="status" label="状态" width="100" column-key="status" :filters="statusFilters" :filter-method="filterStatus" sortable />
        <el-table-column prop="created_at" label="创建时间" width="160" sortable />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
            <el-button v-if="!row.is_return" link type="warning" @click="openReturn(row)">退货</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchList" @current-change="fetchList" style="margin-top: 12px" />
    </el-card>

    <!-- 新建发货弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建发货" width="750px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="销售订单" required>
          <el-select v-model="form.order_id" placeholder="请选择订单" filterable style="width: 100%" @change="onOrderChange">
            <el-option v-for="o in orderList" :key="o.id" :label="`${o.order_no} - ${o.customer_name}`" :value="o.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="orderItems.length" label="选择产品" required>
          <el-table :data="orderItems.filter(r => r.quantity - (r.delivered_qty||0) > 0)" border highlight-current-row @row-click="onItemRowClick" size="small" style="width: 100%">
            <el-table-column prop="product_name" label="产品名称" />
            <el-table-column label="订单数量" width="100" align="right"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
            <el-table-column label="已发" width="80" align="right"><template #default="{ row }">{{ $fq(row.delivered_qty) }}</template></el-table-column>
            <el-table-column label="未发" width="80" align="right">
              <template #default="{ row }">{{ row.quantity - (row.delivered_qty||0) }}</template>
            </el-table-column>
          </el-table>
        </el-form-item>

        <template v-if="selectedItem">
          <el-divider content-position="left">已选择：{{ selectedItem.product_name }}</el-divider>
          <el-form-item label="单价"><span>{{ $fm(selectedItem.unit_price) }}</span></el-form-item>
          <el-form-item label="批次号" required>
            <el-select v-model="form.batch_no" placeholder="请选择批次" filterable style="width: 100%" :disabled="!selectedItem" @change="onBatchChange">
              <el-option v-for="b in batchList" :key="b.id" :label="`${b.batch_no} (库存${b.quantity})`" :value="b.batch_no" />
            </el-select>
          </el-form-item>
          <el-form-item label="发货数量" required>
            <el-input type="number" v-model="form.quantity" :min="1" :max="selectedItem.quantity - (selectedItem.delivered_qty||0)" style="width: 100%" />
          </el-form-item>
          <el-form-item label="仓库" required>
            <el-select v-model="form.warehouse_id" placeholder="请选择仓库" style="width: 100%">
              <el-option v-for="w in warehouseList" :key="w.id" :label="`${w.code||''} - ${w.name}`" :value="w.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="发货日期" required>
            <el-date-picker v-model="form.delivery_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!form.order_id || !selectedItem" @click="handleSubmit">提交发货</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="发货详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="发货单号">{{ detailData.delivery_no }}</el-descriptions-item>
        <el-descriptions-item label="关联订单">{{ detailData.order_no }}</el-descriptions-item>
        <el-descriptions-item label="产品">{{ detailData.product_name }}</el-descriptions-item>
        <el-descriptions-item label="批次号">{{ detailData.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ $fq(detailData.quantity) }}</el-descriptions-item>
        <el-descriptions-item label="单价">{{ $fm(detailData.unit_price) }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ $fm(detailData.amount) }}</el-descriptions-item>
        <el-descriptions-item label="发货日期">{{ detailData.delivery_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailData.status }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ detailData.remark }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 退货弹窗 -->
    <el-dialog v-model="returnVisible" :title="`销售退货 ${returnDeliveryNo}`" width="520px">
      <el-alert type="warning" :closable="false" style="margin-bottom: 10px"
        title="退货将把数量退回原批次（原发货成本），生成负向退货单并回退订单已发数量" />
      <el-alert v-if="returnInvoiceHint" type="info" :closable="false" style="margin-bottom: 10px"
        :title="returnInvoiceHint" />
      <el-form label-width="90px">
        <el-form-item label="发货数量">{{ $fq(returnOriginalQty) }}</el-form-item>
        <el-form-item label="退货数量" required>
          <el-input-number v-model="returnQty" :min="0.01" :max="returnOriginalQty" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="退货原因">
          <el-input v-model="returnRemark" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="returnVisible = false">取消</el-button>
        <el-button type="warning" :loading="returnLoading" @click="handleReturn">确认退货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { salesApi, inventoryApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// 列筛选
const dateFilters = ref([])
const productFilters = ref([])
const statusFilters = ref([])
const filterDateVal = ref('')
const filterProductVal = ref('')
const filterStatusVal = ref('')

const filteredList = computed(() => {
  let items = list.value
  if (filterDateVal.value) items = items.filter(r => r.delivery_date === filterDateVal.value)
  if (filterProductVal.value) items = items.filter(r => r.product_name === filterProductVal.value)
  if (filterStatusVal.value) items = items.filter(r => r.status === filterStatusVal.value)
  return items
})

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterProduct(val, row) { filterProductVal.value = val; return true }
function filterStatus(val, row) { filterStatusVal.value = val; return true }

const searchForm = reactive({ keyword: '', dateRange: null })

function resetSearch() { searchForm.keyword = ''; searchForm.dateRange = null; filterDateVal.value = ''; filterProductVal.value = ''; filterStatusVal.value = ''; page.value = 1; fetchList() }

const dialogVisible = ref(false)
const submitting = ref(false)
const orderList = ref([])
const orderItems = ref([])
const selectedItem = ref(null)
const warehouseList = ref([])
const batchList = ref([])

const form = reactive({
  order_id: null,
  order_item_id: null,
  product_id: null,
  batch_no: '',
  quantity: 1,
  warehouse_id: null,
  delivery_date: '',
  remark: '',
})

const detailVisible = ref(false)
const detailData = ref({})

async function fetchList() {
  loading.value = true
  try {
    const res = await salesApi.deliveries.list({ page: page.value, page_size: pageSize.value })
    list.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    dateFilters.value = [...new Set(list.value.map(r => r.delivery_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    productFilters.value = [...new Set(list.value.map(r => r.product_name).filter(Boolean))].map(v => ({ text: v, value: v }))
    statusFilters.value = [...new Set(list.value.map(r => r.status).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch (e) { ElMessage.error('加载失败') } finally { loading.value = false }
}

async function fetchOrders() {
  try {
    const res = await salesApi.orders.list({ page: 1, page_size: 100 })
    orderList.value = res.items || []
  } catch {}
}

async function fetchWarehouses() {
  try {
    const res = await foundationApi.warehouses.list({ page: 1, page_size: 100 })
    warehouseList.value = res.items || []
  } catch {}
}

function openCreate() {
  form.order_id = null; form.order_item_id = null; form.product_id = null
  form.batch_no = ''; form.quantity = 1; form.warehouse_id = null
  form.delivery_date = ''; form.remark = ''
  orderItems.value = []
  selectedItem.value = null
  dialogVisible.value = true
}

async function onOrderChange() {
  if (!form.order_id) return
  try {
    const res = await salesApi.orders.get(form.order_id, form.order_id)
    orderItems.value = res.items || []
    selectedItem.value = null
  } catch {}
}

function onItemRowClick(row) {
  selectedItem.value = row
  form.order_item_id = row.id
  form.product_id = row.product_id
  form.quantity = 1
  form.batch_no = ''
  loadBatches(row.product_id)
}

async function loadBatches(productId) {
  if (!productId) { batchList.value = []; return }
  try {
    const res = await inventoryApi.availableBatches({ product_id: productId })
    batchList.value = res.items || []
  } catch { batchList.value = [] }
}

function onBatchChange(batchNo) {
  const b = batchList.value.find(x => x.batch_no === batchNo)
  if (b) form.warehouse_id = b.warehouse_id
}

async function handleSubmit() {
  if (!form.order_id || !selectedItem.value) { ElMessage.warning('请选择订单和产品'); return }
  if (!form.batch_no) { ElMessage.warning('请输入批次号'); return }
  submitting.value = true
  try {
    await salesApi.deliveries.create({ ...form })
    ElMessage.success('发货成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '发货失败') } finally { submitting.value = false }
}

function showDetail(row) {
  detailData.value = row
  detailVisible.value = true
}

// ===== 退货 =====
const returnVisible = ref(false)
const returnLoading = ref(false)
const returnDeliveryId = ref(null)
const returnDeliveryNo = ref('')
const returnOriginalQty = ref(0)
const returnQty = ref(0)
const returnRemark = ref('')
const returnInvoiceHint = ref('')

async function openReturn(row) {
  returnDeliveryId.value = row.id
  returnDeliveryNo.value = row.delivery_no
  returnOriginalQty.value = Math.abs(row.quantity)
  returnQty.value = Math.abs(row.quantity)
  returnRemark.value = ''
  returnInvoiceHint.value = ''
  // 订单发票状态提示（退货涉及已开票部分 → 提示先全额红冲）
  try {
    const od = await salesApi.orders.get(row.order_id, row.order_id)
    const invoiced = od.invoiced_amount || 0
    if (invoiced > 0) {
      returnInvoiceHint.value = `该订单已开票 ${$fm(invoiced)}：退货涉及已开票部分时，请到「销售发票」列表全额红冲对应发票并补开新票（未开票部分无需处理）。`
    }
  } catch { /* 忽略提示加载失败 */ }
  returnVisible.value = true
}

async function handleReturn() {
  if (!returnQty.value || returnQty.value <= 0) { ElMessage.warning('请输入退货数量'); return }
  await ElMessageBox.confirm(
    `确认退货 ${returnQty.value}？数量将退回原批次，订单已发数量同步回退。`,
    '退货确认', { type: 'warning', confirmButtonText: '确认退货', cancelButtonText: '再想想' }
  )
  returnLoading.value = true
  try {
    const res = await salesApi.deliveries.return(returnDeliveryId.value, {
      quantity: returnQty.value, remark: returnRemark.value,
    })
    let msg = res.message || '退货成功'
    if (res.invoice_status && res.invoice_status.invoiced_amount > 0) {
      msg += `（该订单已开票 ${$fm(res.invoice_status.invoiced_amount)}，已红冲 ${$fm(res.invoice_status.red_reversed_amount)}，涉及已开票部分请做全额红冲）`
    }
    ElMessage.success(msg, 6000)
    returnVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退货失败') } finally { returnLoading.value = false }
}

onMounted(() => { fetchList(); fetchOrders(); fetchWarehouses() })
</script>
