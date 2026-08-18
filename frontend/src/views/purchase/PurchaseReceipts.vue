<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- ========== 搜索区 ========== -->
    <el-card style="margin-bottom: 8px; flex: none">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>查询条件</span>
          <span style="flex: 1" />
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog()">新建入库</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="入库单号/关联订单" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="入库日期">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="已入库" value="已入库" />
            <el-option label="已取消" value="已取消" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ========== 入库单列表（上） ========== -->
    <el-card style="flex: none">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>采购入库单</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openOrderSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="orderTableRef" class="drag-table-receipts" :key="columnVersion" :data="dataList" v-loading="loading" stripe border size="small" highlight-current-row @current-change="onReceiptSelect" :height="topHeight - 92 + 'px'">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <el-dropdown trigger="contextmenu" :hide-on-click="false">
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="c in allColumns" :key="c.prop">
                    <el-checkbox :model-value="c.visible !== false" @change="toggleColumn(c)">{{ c.label }}</el-checkbox>
                  </el-dropdown-item>
                  <el-dropdown-item @click.stop="openOrderSettings" style="color: #409eff">列设置...</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'status'" #default="{ row }">
            <el-tag type="success" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="handleCancel(row)">取消入库</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.pageSize" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 6px; flex: none" />
    </el-card>

    <!-- 拖动条：上下拉动调节列表/明细区域高度 -->
    <div
      class="split-bar"
      style="flex: none; height: 8px; margin: 0 -16px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none"
      @mousedown="onSplitterDown"
    >
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>

    <!-- ========== 收货明细（跟随选中入库单，占剩余高度） ========== -->
    <el-card style="flex: 1; min-height: 140px; display: flex; flexDirection: column; overflow: hidden">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>收货明细</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openItemSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="itemTableRef" class="drag-table-receipt-items" :key="itemColumnVersion" :data="receiptDetailList" v-loading="itemLoading" stripe border size="small" empty-text="点击上方入库单行查看明细" show-summary :summary-method="itemSummary" :height="'max(calc(100vh - ' + (topHeight + 264) + 'px), 140px)'">
        <el-table-column v-for="col in visibleItemColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <el-dropdown trigger="contextmenu" :hide-on-click="false">
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="c in allItemColumns" :key="c.prop">
                    <el-checkbox :model-value="c.visible !== false" @change="toggleItemColumn(c)">{{ c.label }}</el-checkbox>
                  </el-dropdown-item>
                  <el-dropdown-item @click.stop="openItemSettings" style="color: #409eff">列设置...</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'quantity' || col.prop === 'total_amount'" #default="{ row }">{{ col.prop === 'total_amount' ? $fm(row[col.prop]) : $fq(row[col.prop]) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建入库对话框 -->
    <el-dialog v-model="dialogVisible" title="新建采购入库" width="800px" destroy-on-close>
      <el-form :model="receiptForm" :rules="receiptRules" ref="receiptFormRef" label-width="100px">
        <el-form-item label="采购订单" prop="order_id">
          <el-select
            v-model="receiptForm.order_id"
            placeholder="请选择订单"
            filterable
            style="width: 100%"
            :disabled="autoFillMode"
            @change="onOrderChange"
          >
            <el-option
              v-for="o in orderList"
              :key="o.id"
              :label="o.order_no + ' - ' + o.supplier_name"
              :value="o.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="仓库" prop="warehouse_id">
          <el-select v-model="receiptForm.warehouse_id" placeholder="请选择仓库" style="width: 100%">
            <el-option
              v-for="w in warehouseList"
              :key="w.id"
              :label="`${w.code || '' } - ${w.name}`"
              :value="w.id"
            />
          </el-select>
        </el-form-item>

        <!-- 入库明细 -->
        <el-form-item label="入库明细">
          <el-table :data="receiptForm.items" border size="small" style="width: 100%">
            <el-table-column prop="material_name" label="物料名称" width="150" sortable />
            <el-table-column prop="material_code" label="编码" width="100" sortable />
            <el-table-column prop="unit" label="单位" width="70" sortable />
            <el-table-column label="入库数量" width="100" align="right"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
            <el-table-column label="单价" width="100" align="right"><template #default="{ row }">{{ $fm(row.unit_price) }}</template></el-table-column>
            <el-table-column prop="batch_no" label="批次号" width="140" sortable />
            <el-table-column prop="order_quantity" label="订单数量" width="100" align="right" sortable />
            <el-table-column prop="received_quantity" label="已入库" width="100" align="right" sortable />
            <el-table-column label="本次入库" width="130">
              <template #default="{ row, $index }">
                <el-input type="number"
                  v-model="row.receivedQty"
                  :min="0"
                  :max="row.order_quantity - row.received_quantity"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="入库批次" width="160">
              <template #default="{ row }">
                <span v-if="row.batchNo" style="color: #67c23a; font-size: 12px">{{ row.batchNo }}</span>
                <span v-else style="color: #909399; font-size: 12px">保存后生成</span>
              </template>
            </el-table-column>
          </el-table>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认入库</el-button>
      </template>
    </el-dialog>

    <!-- 列设置弹窗 -->
    <ColumnSettingsDialog v-model:visible="orderSettingsVisible" :columns="orderSettingsList" @confirm="confirmReceiptSettingsFn" @reset="resetReceiptSettingsFn" />
    <ColumnSettingsDialog v-model:visible="itemSettingsVisible" :columns="itemSettingsList" @confirm="confirmItemSettingsFn" @reset="resetItemSettingsFn" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import { purchaseApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'
import request from '../../api/request'

const route = useRoute()
const { fitTable } = useColumnAutoFit()

const autoFillMode = ref(false)

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_purchase_receipt_columns'
const defaultColumns = [
  { prop: 'receipt_no', label: '入库单号', width: 160, sortable: true },
  { prop: 'order_no', label: '关联订单', width: 160, sortable: true },
  { prop: 'warehouse_name', label: '仓库', minWidth: 120, sortable: true },
  { prop: 'total_qty', label: '总数量', width: 100, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'status', label: '状态', width: 100, sortable: true, fmt: 'tag' },
  { prop: 'item_count', label: '明细项', width: 80, align: 'center', sortable: true, fmt: 'qty' },
  { prop: 'receipt_date', label: '入库日期', width: 120, sortable: true },
]
const { columns, columnVersion, initColumnDrag, settingsVisible: orderSettingsVisible, settingsList: orderSettingsList, openColumnSettings: openOrderSettingsRaw, confirmSettings: confirmOrderSettingsRaw, resetSettings: resetOrderSettingsRaw } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-receipts .el-table__header-wrapper thead tr')
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

const ITEM_STORAGE_KEY = 'mazu_purchase_receipt_item_columns'
const defaultItemColumns = [
  { prop: 'material_name', label: '物料名称', minWidth: 150, sortable: true },
  { prop: 'material_code', label: '编码', width: 100, sortable: true },
  { prop: 'batch_no', label: '批次号', width: 140, sortable: true },
  { prop: 'quantity', label: '数量', width: 90, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'total_amount', label: '金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
]
const { columns: itemColumns, columnVersion: itemColumnVersion, initColumnDrag: initItemColumnDrag, settingsVisible: itemSettingsVisible, settingsList: itemSettingsList, openColumnSettings: openItemSettingsRaw, confirmSettings: confirmItemSettingsRaw, resetSettings: resetItemSettingsRaw } = useColumnDrag(defaultItemColumns, ITEM_STORAGE_KEY, '.drag-table-receipt-items .el-table__header-wrapper thead tr')
const { visibleColumns: visibleItemColumns, allColumns: allItemColumns, toggleColumn: toggleItemColumn, initColumnVisible: initItemVisible } = useColumnCustomize(itemColumns, ITEM_STORAGE_KEY)

// ========== 列设置包装函数 ==========
function confirmReceiptSettingsFn() {
  confirmOrderSettingsRaw()
  nextTick(() => { initColumnVisible(); initColumnDrag(); fitTable(orderTableRef.value, columns, dataList) })
}

function resetReceiptSettingsFn() {
  resetOrderSettingsRaw()
  nextTick(() => { initColumnVisible(); initColumnDrag(); fitTable(orderTableRef.value, columns, dataList) })
}

function confirmItemSettingsFn() {
  confirmItemSettingsRaw()
  nextTick(() => { initItemVisible(); initItemColumnDrag(); fitTable(itemTableRef.value, itemColumns, receiptDetailList) })
}

function resetItemSettingsFn() {
  resetItemSettingsRaw()
  nextTick(() => { initItemVisible(); initItemColumnDrag(); fitTable(itemTableRef.value, itemColumns, receiptDetailList) })
}

const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, pageSize: 100 })

// 搜索条件
const searchForm = reactive({
  keyword: '',
  dateRange: null,
  status: '',
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.status = ''
  queryParams.page = 1
  fetchData()
}

// ========== 收货明细（跟随选中入库单） ==========
const orderTableRef = ref(null)
const itemTableRef = ref(null)
const itemLoading = ref(false)
const selectedReceipt = ref(null)
const receiptDetailList = ref([])

// ========== 上下区域高度拖动 ==========
const SPLIT_KEY = 'mazu_purchase_receipt_split_height'
const topHeight = ref(parseInt(localStorage.getItem(SPLIT_KEY) || '400') || 400)

function onSplitterDown(e) {
  const startY = e.clientY
  const startH = topHeight.value
  const onMove = (ev) => {
    const h = startH + (ev.clientY - startY)
    topHeight.value = Math.min(Math.max(h, 140), window.innerHeight - 320)
    localStorage.setItem(SPLIT_KEY, String(topHeight.value))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
}

// ========== 合计栏 ==========
function fmtMoney(v) {
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (n === null || n === undefined || isNaN(n)) return '¥0.00'
  return '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function itemSummary({ columns: cols, data }) {
  const sumCols = new Set(['quantity', 'total_amount'])
  return cols.map((col, idx) => {
    if (idx === 0) return '合计'
    if (sumCols.has(col.property)) {
      const v = data.reduce((s, r) => s + (parseFloat(r[col.property]) || 0), 0)
      return col.property === 'quantity' ? String(v) : fmtMoney(v)
    }
    return ''
  })
}

function onReceiptSelect(row) {
  if (!row) return
  selectedReceipt.value = row
  loadReceiptDetail(row.id)
}

async function loadReceiptDetail(receiptId) {
  if (!receiptId) { receiptDetailList.value = []; return }
  itemLoading.value = true
  try {
    const res = await request.get(`/purchase/receipts/${receiptId}`)
    receiptDetailList.value = res.items || []
  } catch {} finally {
    itemLoading.value = false
    nextTick(() => {
      initItemColumnDrag()
      fitTable(itemTableRef.value, itemColumns, receiptDetailList)
    })
  }
}

const dialogVisible = ref(false)
const submitting = ref(false)
const receiptFormRef = ref(null)

const orderList = ref([])
const warehouseList = ref([])

const receiptForm = reactive({
  order_id: null,
  order_no: '',
  supplier_id: null,
  supplier_name: '',
  warehouse_id: null,
  warehouse_name: '',
  items: [],
})

const receiptRules = {
  order_id: [{ required: true, message: '请选择采购订单', trigger: 'change' }],
  warehouse_id: [{ required: true, message: '请选择仓库', trigger: 'change' }],
}

function openDialog() {
  Object.assign(receiptForm, {
    order_id: null, order_no: '', supplier_id: null, supplier_name: '',
    warehouse_id: null, warehouse_name: '', items: [],
  })
  dialogVisible.value = true
}

async function onOrderChange(orderId) {
  const order = orderList.value.find((x) => x.id === orderId)
  if (!order) return
  receiptForm.order_no = order.order_no
  receiptForm.supplier_id = order.supplier_id
  receiptForm.supplier_name = order.supplier_name
  // 获取订单明细（列表接口不返回 items，需要调详情）
  let orderItems = order.items
  if (!orderItems || !orderItems.length) {
    try {
      const detail = await purchaseApi.orders.get(orderId)
      orderItems = detail.items || []
    } catch (e) {
      console.error('onOrderChange: fetch detail failed', e)
      orderItems = []
    }
  }
  const batchNo = 'BATCH-' + Date.now()
  receiptForm.items = orderItems.map((item) => ({
    material_id: item.material_id,
    material_name: item.material_name,
    material_code: item.material_code || '',
    spec: item.spec || '',
    unit: item.unit || '',
    unit_price: item.unit_price || 0,
    quantity: item.quantity || 0,
    order_quantity: item.quantity,
    received_quantity: item.received_qty || 0,
    receivedQty: Math.max(0, (item.quantity || 0) - (item.received_qty || 0)),
    batch_no: batchNo,
  }))
}

async function loadOrders() {
  try {
    const res = await purchaseApi.orders.list({ page: 1, pageSize: 100 })
    orderList.value = (res.items || res.list || res.data || []).filter((o) =>
      ['已审核', '部分入库', '待开票'].includes(o.status) && (o.item_count || 0) > 0
    )
  } catch {}
}

async function loadWarehouses() {
  try {
    const res = await foundationApi.warehouses.list({ page: 1, pageSize: 100 })
    warehouseList.value = res.items || res.list || res.data || []
  } catch {}
}

async function fetchData() {
  loading.value = true
  try {
    const res = await purchaseApi.receipts.list(queryParams)
    dataList.value = res.items || res.list || res.data || []
    total.value = res.total || dataList.value.length
    // 自动选中第一行，联动加载明细
    if (dataList.value.length) {
      selectedReceipt.value = dataList.value[0]
      loadReceiptDetail(selectedReceipt.value.id)
      nextTick(() => { orderTableRef.value?.setCurrentRow(dataList.value[0]) })
    } else {
      selectedReceipt.value = null
      receiptDetailList.value = []
    }
  } catch (e) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
    nextTick(() => {
      initColumnDrag()
      fitTable(orderTableRef.value, columns, dataList)
    })
  }
}

async function handleSubmit() {
  const valid = await receiptFormRef.value.validate().catch(() => false)
  if (!valid) return
  const hasItem = receiptForm.items.some((i) => i.receivedQty > 0)
  if (!hasItem) {
    ElMessage.warning('请输入至少一项入库数量')
    return
  }
  submitting.value = true
  try {
    const warehouse = warehouseList.value.find((w) => w.id === receiptForm.warehouse_id)
    receiptForm.warehouse_name = warehouse?.name || ''
    const payload = {
      order_id: receiptForm.order_id,
      order_no: receiptForm.order_no,
      warehouse_id: receiptForm.warehouse_id,
      warehouse_name: receiptForm.warehouse_name,
      supplier_id: receiptForm.supplier_id,
      supplier_name: receiptForm.supplier_name,
      items: receiptForm.items
        .filter((i) => i.receivedQty > 0)
        .map((i) => ({
          material_id: i.material_id,
          material_name: i.material_name,
          spec: i.spec,
          unit: i.unit,
          quantity: i.receivedQty,
          unit_price: i.unit_price || 0,
          batch_no: i.batch_no,
        })),
    }
    await purchaseApi.receipts.create(payload)
    ElMessage.success('入库成功')
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // error handled by interceptor
  } finally {
    submitting.value = false
  }
}

async function handleCancel(row) {
  await ElMessageBox.confirm(
    `确定取消入库单 ${row.receipt_no}？库存、批次数据将同步回滚。`,
    '提示', { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '再想想' }
  )
  try {
    await request.delete(`/purchase/receipts/${row.id}`)
    ElMessage.success('入库已取消，库存已回滚')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '取消失败')
  }
}

onMounted(async () => {
  initColumnVisible()
  initItemVisible()
  await fetchData()
  await loadOrders()
  await loadWarehouses()

  // ===== 模式1：从采购订单点"入库"跳转过来 =====
  const orderId = route.query.oid
  if (orderId) {
    autoFillMode.value = true
    try {
      const res = await request.get('/purchase/orders/' + orderId)
      if (res && res.items) {
        const batchNo = 'BATCH-' + Date.now()
        // 直接赋值，不用 openDialog（避免重置 items）
        receiptForm.items = res.items.map((item) => ({
          material_id: item.material_id, material_name: item.material_name,
          material_code: item.material_code || '', spec: item.spec || '',
          unit: item.unit || '', unit_price: item.unit_price || 0,
          quantity: item.quantity || 0, order_quantity: item.quantity,
          received_quantity: item.received_qty || 0,
          receivedQty: Math.max(0, (item.quantity || 0) - (item.received_qty || 0)),
          batch_no: batchNo,
        }))
        receiptForm.order_no = res.order_no
        receiptForm.supplier_id = res.supplier_id
        receiptForm.supplier_name = res.supplier_name
        receiptForm.warehouse_id = 1  // 默认原材料仓
        receiptForm.order_id = res.id
      }
      dialogVisible.value = true
    } catch (e) {
      console.error('auto-fill failed:', e?.response?.data || e.message || e)
      ElMessage.error('加载订单明细失败')
    }
    return
  }

  // ===== 模式2：手工"新建入库" =====
  // 纯空表单，用户自己选订单触发 onOrderChange
})

// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnVisible(); initColumnDrag() })
})
watch(itemColumnVersion, () => {
  nextTick(() => { initItemVisible(); initItemColumnDrag() })
})
</script>
