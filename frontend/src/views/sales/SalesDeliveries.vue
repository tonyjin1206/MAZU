<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- ========== 搜索区 ========== -->
    <el-card style="margin-bottom: 8px; flex: none">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="订单号/产品/客户/批次" clearable style="width: 200px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="订单状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 130px">
            <el-option label="已审" value="已审" />
            <el-option label="部分发货" value="部分发货" />
            <el-option label="已发货" value="已发货" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ========== 产品发货记录（上表，高度可拖） ========== -->
    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column' }">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>产品发货记录</span>
          <span style="margin-left: 10px; font-size: 12px; color: #909399">点击产品行，下方查看该产品的发货单明细</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openOrderSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="orderTableRef" class="drag-table-orders" :key="orderColumnVersion" :data="dataList" v-loading="loading" stripe border size="small" highlight-current-row show-summary :summary-method="orderSummary" :height="topHeight - 92 + 'px'" :row-class-name="deliveryRowClassName" @current-change="onOrderSelect">
        <el-table-column v-for="col in orderColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'delivery_confirmed'" #default="{ row }">
            <el-tag v-if="row.delivery_confirmed" type="success" size="small">已完成</el-tag>
            <el-tag v-else type="info" size="small">未完成</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.delivery_confirmed" link type="primary" @click="openShipDialog(row)">通知发货</el-button>
            <el-button v-if="(row.delivered_qty || 0) > 0" link type="warning" @click="openReturnDialog(row)">退货</el-button>
            <el-button v-if="!row.delivery_confirmed" link type="success" @click="confirmDone(row)">发货完成</el-button>
            <el-button v-else link type="info" @click="cancelDone(row)">撤销确认</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 6px; flex: none" />
    </el-card>

    <!-- 拖动条：上下拉动调节上下表高度 -->
    <div
      class="split-bar"
      style="flex: none; height: 8px; margin: 0 -16px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none"
      @mousedown="onSplitterDown"
    >
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>

    <!-- ========== 发货单明细（下表，跟随选中产品行） ========== -->
    <el-card style="flex: 1; min-height: 140px; display: flex; flexDirection: column; overflow: hidden">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>发货单明细</span>
          <span style="margin-left: 10px; font-size: 12px; color: #909399">{{ selectedRow ? selectedRow.order_no + ' / ' + selectedRow.product_name : '点击上方产品行查看' }}</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openItemSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="itemTableRef" class="drag-table-items" :key="itemColumnVersion" :data="deliveryList" v-loading="itemLoading" stripe border size="small" empty-text="点击上方产品行查看发货单明细" show-summary :summary-method="itemSummary" :height="'max(calc(100vh - ' + (topHeight + 264) + 'px), 140px)'">
        <el-table-column v-for="col in itemColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'is_return'" #default="{ row }">
            <el-tag v-if="row.is_return" type="danger" size="small">退货</el-tag>
            <el-tag v-else type="success" size="small">发货</el-tag>
          </template>
          <template v-else-if="col.prop === 'quantity'" #default="{ row }">
            <span :style="row.is_return ? 'color: #f56c6c' : ''">{{ row.is_return ? '-' : '' }}{{ $fq(row.quantity) }}</span>
          </template>
          <template v-else-if="col.prop === 'amount'" #default="{ row }">
            <span :style="row.is_return ? 'color: #f56c6c' : ''">{{ row.is_return ? '-' : '' }}{{ $fm(row.amount) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ========== 通知发货弹窗 ========== -->
    <el-dialog v-model="shipVisible" title="通知发货" width="520px" destroy-on-close>
      <el-form :model="shipForm" label-width="100px">
        <el-form-item label="销售订单"><span>{{ shipForm.order_no }}</span></el-form-item>
        <el-form-item label="产品"><span>{{ shipForm.product_name }}（单价 {{ $fm(shipForm.unit_price) }}）</span></el-form-item>
        <el-form-item label="订单量/已出/可通知">
          <span>订单 {{ $fq(shipForm.quantity) }} / 已出库 {{ $fq(shipForm.delivered_qty) }} / 可通知 {{ $fq(shipForm.max_notify) }}</span>
        </el-form-item>
        <el-form-item label="通知数量" required>
          <el-input type="number" v-model="shipForm.notify_qty" :min="1" :max="shipForm.max_notify" style="width: 100%" />
        </el-form-item>
        <el-form-item label="通知日期" required>
          <el-date-picker v-model="shipForm.notify_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="shipForm.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
        <el-alert type="info" :closable="false" title="已通知的货将在【库存管理→成品出库】中由库管选择批次出库。" />
      </el-form>
      <template #footer>
        <el-button @click="shipVisible = false">取消</el-button>
        <el-button type="primary" :loading="shipSubmitting" :disabled="shipForm.max_notify <= 0" @click="handleShipSubmit">通知发货</el-button>
      </template>
    </el-dialog>

    <!-- ========== 退货弹窗 ========== -->
    <el-dialog v-model="returnVisible" title="退货" width="560px" destroy-on-close>
      <el-form :model="returnForm" label-width="100px">
        <el-form-item label="销售订单"><span>{{ selectedRow?.order_no }}</span></el-form-item>
        <el-form-item label="产品"><span>{{ selectedRow?.product_name }}</span></el-form-item>
        <el-form-item label="发货/已退/可退">
          <span>已发 {{ $fq(selectedRow?.delivered_qty || 0) }} / 已退 {{ $fq(returnedTotal) }} / 可退 {{ $fq(returnMax) }}</span>
        </el-form-item>
        <el-form-item label="批次号" required>
          <el-select v-model="returnForm.batch_no" placeholder="请选择原发货批次" filterable style="width: 100%">
            <el-option v-for="b in returnBatchList" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>
        <el-form-item label="退货数量" required>
          <el-input type="number" v-model="returnForm.quantity" :min="1" :max="returnMax" style="width: 100%" />
        </el-form-item>
        <el-form-item label="退货日期" required>
          <el-date-picker v-model="returnForm.return_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="returnForm.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="returnVisible = false">取消</el-button>
        <el-button type="warning" :loading="returnSubmitting" :disabled="!returnForm.batch_no || returnMax <= 0" @click="handleReturnSubmit">确认退货</el-button>
      </template>
    </el-dialog>

    <ColumnSettingsDialog v-model:visible="orderSettingsVisible" :columns="orderSettingsList" @confirm="confirmOrderSettings" @reset="resetOrderSettings" />
    <ColumnSettingsDialog v-model:visible="itemSettingsVisible" :columns="itemSettingsList" @confirm="confirmItemSettings" @reset="resetItemSettings" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'

// ===== 上表列配置（产品发货记录）=====
const ORDER_STORAGE_KEY = 'mazu_sales_delivery_workbench_columns'
const defaultOrderColumns = [
  { prop: 'order_no', label: '订单号', width: 140, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 100, sortable: true },
  { prop: 'product_name', label: '产品名称', minWidth: 120, sortable: true },
  { prop: 'product_code', label: '产品编码', minWidth: 100, sortable: true },
  { prop: 'batch_no', label: '批次号', width: 150, sortable: true },
  { prop: 'quantity', label: '订单数量', width: 95, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'received_qty', label: '已入库', width: 90, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'delivered_qty', label: '已出库', width: 90, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'undelivered_qty', label: '未出库', width: 90, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'physical_stock', label: '实物库存', width: 95, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'available_stock', label: '可用库存', width: 95, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'delivery_confirmed', label: '出库状态', width: 95, align: 'center', sortable: true, fmt: 'tag' },
]
const {
  columns: orderColumns, columnVersion: orderColumnVersion, initColumnDrag: initOrderDrag,
  settingsVisible: orderSettingsVisible, settingsList: orderSettingsList,
  openColumnSettings: openOrderSettingsRaw, confirmSettings: confirmOrderSettingsRaw, resetSettings: resetOrderSettingsRaw,
} = useColumnDrag(defaultOrderColumns, ORDER_STORAGE_KEY)

// ===== 下表列配置（发货单明细）=====
const ITEM_STORAGE_KEY = 'mazu_sales_delivery_items_columns'
const defaultItemColumns = [
  { prop: 'delivery_no', label: '发货单号', width: 150, sortable: true },
  { prop: 'is_return', label: '类型', width: 80, align: 'center', sortable: true },
  { prop: 'batch_no', label: '批次号', width: 150, sortable: true },
  { prop: 'quantity', label: '数量', width: 95, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'amount', label: '金额', width: 110, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'delivery_date', label: '日期', width: 105, sortable: true },
  { prop: 'status', label: '状态', width: 90, sortable: true },
  { prop: 'remark', label: '备注', minWidth: 100, sortable: true },
]
const {
  columns: itemColumns, columnVersion: itemColumnVersion, initColumnDrag: initItemDrag,
  settingsVisible: itemSettingsVisible, settingsList: itemSettingsList,
  openColumnSettings: openItemSettingsRaw, confirmSettings: confirmItemSettingsRaw, resetSettings: resetItemSettingsRaw,
} = useColumnDrag(defaultItemColumns, ITEM_STORAGE_KEY)

const { fitTable } = useColumnAutoFit()

// ===== 上表 =====
const orderTableRef = ref(null)
const itemTableRef = ref(null)
const dataList = ref([])
const loading = ref(false)
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })
const searchForm = reactive({ keyword: '', status: '' })

// ===== 下表 =====
const deliveryList = ref([])
const itemLoading = ref(false)
const selectedRow = ref(null)
const returnedTotal = ref(0)
const returnMax = ref(0)

// ===== 分栏 =====
const topHeight = ref(420)

// ===== 通知发货弹窗 =====
const shipVisible = ref(false)
const shipSubmitting = ref(false)
const shipForm = reactive({
  order_id: null, order_item_id: null, product_id: null,
  order_no: '', product_name: '', unit_price: 0,
  quantity: 0, delivered_qty: 0, max_notify: 0,
  notify_qty: 1, notify_date: '', remark: '',
})

// ===== 退货弹窗 =====
const returnVisible = ref(false)
const returnSubmitting = ref(false)
const returnBatchList = ref([])
const returnForm = reactive({ batch_no: '', quantity: 1, return_date: '', remark: '' })

function resetSearch() { searchForm.keyword = ''; searchForm.status = ''; queryParams.page = 1; fetchData() }

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    const res = await request.get('/sales/delivery-workbench', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
    nextTick(() => {
      initOrderDrag()
      fitTable(orderTableRef.value, orderColumns.value, dataList.value)
      orderTableRef.value?.setCurrentRow(dataList.value[0] || null)
    })
  } catch (e) { ElMessage.error('加载失败') } finally { loading.value = false }
}

function onOrderSelect(row) {
  selectedRow.value = row
  if (row) loadDeliveries(row.item_id)
  else { deliveryList.value = []; returnedTotal.value = 0; returnMax.value = 0 }
}

async function loadDeliveries(itemId) {
  if (!itemId) { deliveryList.value = []; return }
  itemLoading.value = true
  try {
    const res = await request.get('/sales/deliveries', { params: { page: 1, page_size: 100, order_item_id: itemId } })
    deliveryList.value = res.items || []
    const ret = (res.items || []).filter(i => i.is_return).reduce((s, i) => s + (i.quantity || 0), 0)
    returnedTotal.value = ret
    returnMax.value = Math.max(0, (selectedRow.value?.delivered_qty || 0) - ret)
  } catch (e) { deliveryList.value = [] } finally {
    itemLoading.value = false
    nextTick(() => { initItemDrag(); fitTable(itemTableRef.value, itemColumns.value, deliveryList.value) })
  }
}

// ===== 通知发货 =====
async function openShipDialog(row) {
  if (row.delivery_confirmed) { ElMessage.warning('该产品已确认发货完成，不能通知（可先撤销确认）'); return }
  const maxNotify = Math.max(0, (row.quantity || 0) - (row.delivered_qty || 0))
  Object.assign(shipForm, {
    order_id: row.order_id, order_item_id: row.item_id, product_id: row.product_id,
    order_no: row.order_no, product_name: row.product_name, unit_price: 0,
    quantity: row.quantity || 0, delivered_qty: row.delivered_qty || 0, max_notify: maxNotify,
    notify_qty: maxNotify > 0 ? 1 : 0, notify_date: '', remark: '',
  })
  // 单价从订单详情取
  try {
    const detail = await request.get(`/sales/orders/${row.order_id}`)
    const it = (detail.items || []).find(i => i.id === row.item_id)
    if (it) shipForm.unit_price = it.unit_price || 0
  } catch (e) {}
  shipVisible.value = true
}

async function handleShipSubmit() {
  if (!shipForm.order_item_id || shipForm.max_notify <= 0) { ElMessage.warning('该产品已全部通知发货'); return }
  const qty = Number(shipForm.notify_qty)
  if (!qty || qty <= 0 || qty > shipForm.max_notify) { ElMessage.warning(`请输入 1~${shipForm.max_notify} 的通知数量`); return }
  shipSubmitting.value = true
  try {
    await request.post('/sales/deliveries/notify', {
      order_item_id: shipForm.order_item_id,
      quantity: qty,
      notify_date: shipForm.notify_date,
      remark: shipForm.remark,
    })
    ElMessage.success('已通知发货，等待库管出库')
    shipVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '通知发货失败') } finally { shipSubmitting.value = false }
}

// ===== 退货 =====
async function openReturnDialog(row) {
  Object.assign(returnForm, { batch_no: '', quantity: 1, return_date: '', remark: '' })
  // 已出库批次（正常发货单已出库的批次，去重；待出库未出库的不可退）
  const res = await request.get('/sales/deliveries', { params: { page: 1, page_size: 100, order_item_id: row.item_id } }).catch(() => ({ items: [] }))
  const shippedBatches = [...new Set((res.items || []).filter(i => !i.is_return && i.status !== '待出库' && (i.delivered_qty || 0) > 0 && i.batch_no).map(i => i.batch_no))]
  returnBatchList.value = shippedBatches
  const ret = (res.items || []).filter(i => i.is_return).reduce((s, i) => s + (i.quantity || 0), 0)
  returnedTotal.value = ret
  returnMax.value = Math.max(0, (row.delivered_qty || 0) - ret)
  returnVisible.value = true
}

async function handleReturnSubmit() {
  if (!selectedRow.value || !returnForm.batch_no) { ElMessage.warning('请选择批次'); return }
  returnSubmitting.value = true
  try {
    await request.post('/sales/deliveries/return', {
      order_item_id: selectedRow.value.item_id,
      batch_no: returnForm.batch_no,
      quantity: returnForm.quantity,
      delivery_date: returnForm.return_date,
      remark: returnForm.remark,
    })
    ElMessage.success('退货成功，库存已加回')
    returnVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退货失败') } finally { returnSubmitting.value = false }
}

// ===== 确认完成 / 撤销确认 =====
async function confirmDone(row) {
  try {
    await ElMessageBox.confirm(
      `确认「${row.product_name}」已发货完成？\n确认后该产品不能再发货，剩余库存将开放给其他订单。`,
      '确认发货完成', { type: 'warning', confirmButtonText: '确认完成', cancelButtonText: '取消' }
    )
  } catch (e) { return }
  try {
    await request.post(`/sales/orders/${row.order_id}/items/${row.item_id}/delivery-confirm`, { confirmed: true })
    ElMessage.success('已确认发货完成')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

async function cancelDone(row) {
  try {
    await ElMessageBox.confirm(
      `撤销「${row.product_name}」的发货完成确认？\n撤销后可继续发货，并恢复库存锁定。`,
      '撤销确认', { type: 'warning', confirmButtonText: '撤销', cancelButtonText: '取消' }
    )
  } catch (e) { return }
  try {
    await request.post(`/sales/orders/${row.order_id}/items/${row.item_id}/delivery-confirm`, { confirmed: false })
    ElMessage.success('已撤销确认')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

function deliveryRowClassName({ row }) {
  return row.delivery_confirmed ? 'mazu-disabled-row' : ''
}

// ===== 合计 =====
function orderSummary({ columns, data }) {
  const sumCols = ['quantity', 'received_qty', 'delivered_qty', 'undelivered_qty', 'physical_stock', 'available_stock']
  return columns.map((col, idx) => {
    if (idx === 0) return '合计'
    if (sumCols.includes(col.property)) {
      const s = data.reduce((acc, r) => acc + (r[col.property] || 0), 0)
      return s.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }
    return ''
  })
}

function itemSummary({ columns, data }) {
  return columns.map((col, idx) => {
    if (idx === 0) return '合计'
    if (col.property === 'quantity') {
      const s = data.reduce((acc, r) => acc + (r.is_return ? -1 : 1) * (r.quantity || 0), 0)
      return s.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }
    if (col.property === 'amount') {
      const s = data.reduce((acc, r) => acc + (r.is_return ? -1 : 1) * (r.amount || 0), 0)
      return '¥' + s.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }
    return ''
  })
}

// ===== 分栏拖动 =====
function onSplitterDown(e) {
  const startY = e.clientY
  const startH = topHeight.value
  const onMove = (ev) => {
    const h = startH + (ev.clientY - startY)
    topHeight.value = Math.min(Math.max(h, 220), window.innerHeight - 380)
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    nextTick(() => { fitTable(orderTableRef.value, orderColumns.value, dataList.value) })
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// ===== 列设置包装（解决构命名冲突：解构保留原名 + 页面包装函数）=====
function confirmOrderSettings() {
  confirmOrderSettingsRaw()
  nextTick(() => { initOrderDrag(); fitTable(orderTableRef.value, orderColumns.value, dataList.value) })
}
function resetOrderSettings() {
  resetOrderSettingsRaw()
  nextTick(() => { initOrderDrag(); fitTable(orderTableRef.value, orderColumns.value, dataList.value) })
}
function openOrderSettings() { openOrderSettingsRaw() }

function confirmItemSettings() {
  confirmItemSettingsRaw()
  nextTick(() => { initItemDrag(); fitTable(itemTableRef.value, itemColumns.value, deliveryList.value) })
}
function resetItemSettings() {
  resetItemSettingsRaw()
  nextTick(() => { initItemDrag(); fitTable(itemTableRef.value, itemColumns.value, deliveryList.value) })
}
function openItemSettings() { openItemSettingsRaw() }

async function fetchWarehouses() {}

watch(orderColumnVersion, () => { nextTick(() => { initOrderDrag() }) })
watch(itemColumnVersion, () => { nextTick(() => { initItemDrag() }) })

onMounted(() => { fetchData() })

</script>

<style scoped>
.mazu-disabled-row { opacity: 0.55; }
</style>
