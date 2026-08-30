<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <el-card style="margin-bottom: 12px; flex: none">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键字">
          <el-input v-model="searchForm.keyword" placeholder="批次号/物料" clearable style="width: 170px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="待入库" value="待入库" />
            <el-option label="部分入库" value="部分入库" />
            <el-option label="已入库" value="已入库" />
            <el-option label="已退回" value="已退回" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="searchForm.sourceType" placeholder="全部" clearable style="width: 130px">
            <el-option label="采购转原料库" value="purchase" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <div style="flex: 1; min-height: 0; overflow: auto">
      <el-table ref="tableRef" :key="columnVersion" :data="dataList" v-loading="loading" stripe border size="small" show-summary :summary-method="getSummary" @row-click="openDetail" style="width: 100%" height="100%">
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
                  <el-dropdown-item @click.stop="openColumnSettings" style="color: #409eff">列设置...</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'quantity' || col.prop === 'received_qty'" #default="{ row }">{{ row[col.prop] || 0 }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待入库' || row.status === '部分入库'" link type="primary" size="small" @click="openReceive(row)">入库</el-button>
            <el-button v-if="row.status === '待入库'" link type="warning" size="small" @click="handleCancel(row)">退回</el-button>
            <el-button v-if="row.status === '部分入库'" link type="success" size="small" @click="handleComplete(row)">确认完成</el-button>
            <el-button v-if="row.status === '已入库' || row.status === '部分入库'" link type="danger" size="small" @click="openReturn(row)">退数量</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 16px; flex: none" />
      </el-card>

      <!-- 拖动条：上下拉动调节列表/明细区域高度 -->
      <div
        class="split-bar"
        style="flex: none; height: 8px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none"
        @mousedown="onSplitterDown"
      >
        <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
      </div>

      <!-- 收货明细分录（点击上方行穿透） -->
      <el-card v-if="selectedRow" :style="{ flex: '1', minHeight: '140px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <template #header>
        <span style="font-weight: 600">收货明细</span>
      </template>
      <div style="flex: 1; min-height: 0; overflow: auto">
      <el-table :data="detailList" v-loading="detailLoading" stripe border size="small" show-summary :summary-method="detailSummary" height="100%">
        <el-table-column prop="in_date" label="入库日期" width="120" sortable />
        <el-table-column prop="warehouse" label="仓库" width="110" sortable />
        <el-table-column prop="receipt_no" label="入库单号" minWidth="160" sortable />
        <el-table-column prop="quantity" label="本次入库数量" width="120" align="right" sortable />
      </el-table>
      </div>
      </el-card>

      <!-- 入库弹窗 -->
      <el-dialog v-model="receiveVisible" title="入库收货" width="440px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="批次号"><el-input :model-value="receiveForm.batch_no" readonly /></el-form-item>
        <el-form-item label="物料"><el-input :model-value="`${receiveForm.product_code || ''} ${receiveForm.product_name || ''}`" readonly /></el-form-item>
        <el-form-item label="应入数量"><span>{{ receiveForm.quantity }}</span> <span style="margin-left: 20px; color: #909399">已入：{{ receiveForm.received_qty }}</span></el-form-item>
        <el-form-item label="本次入库" required>
          <el-input-number v-model="receiveForm.quantity_now" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="入库仓库"><el-input :model-value="receiveForm.warehouse_name || '原辅料仓库（自动）'" readonly /></el-form-item>
        <div style="color: #909399; font-size: 12px">可分批入库，收满自动完成；未收满时由人工点「确认完成」判定结束。</div>
      </el-form>
      <template #footer>
        <el-button @click="receiveVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleReceive">入库</el-button>
      </template>
    </el-dialog>

    <!-- 退回已入库数量弹窗 -->
    <el-dialog v-model="returnVisible" title="退回" width="380px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="批次号"><el-input :model-value="returnForm.batch_no" readonly /></el-form-item>
        <el-form-item label="已入数量"><span>{{ returnForm.received_qty }}</span></el-form-item>
        <el-form-item label="退回数量" required>
          <el-input-number v-model="returnForm.return_qty" :min="0" :max="returnForm.received_qty" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="returnVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="handleReturn">确认退回</el-button>
      </template>
    </el-dialog>
    
    <!-- 列排序弹窗 -->
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { purchaseApi, outsourceApi, inventoryApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_material_in_columns'
const defaultColumns = [
  { prop: 'source_label', label: '来源单据', minWidth: 130, sortable: true },
  { prop: 'batch_no', label: '批次号', minWidth: 140, sortable: true },
  { prop: 'product_code', label: '物料编码', minWidth: 110, sortable: true },
  { prop: 'product_name', label: '物料名称', minWidth: 140, sortable: true },
  { prop: 'quantity', label: '应入', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'received_qty', label: '已入', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'status', label: '状态', width: 90, align: 'center', sortable: true, fmt: 'tag' },
]
const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings: openColumnSettingsRaw, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const tableRef = ref(null)
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

// ===== 列设置弹窗（注入当前显隐状态）=====
function openColumnSettings() {
  const visMap = {}
  for (const c of allColumns.value) visMap[c.prop] = c.visible !== false
  openColumnSettingsRaw(visMap)
}

const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })
const searchForm = reactive({ keyword: '', status: '', sourceType: '' })
const warehouseList = ref([])

function resetSearch() {
  searchForm.keyword = ''
  searchForm.status = ''
  searchForm.sourceType = ''
  queryParams.page = 1
  fetchData()
}

function statusType(status) {
  const map = { '待入库': 'info', '部分入库': 'warning', '已入库': 'success', '已退回': 'danger' }
  return map[status] || 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.sourceType) params.source_type = searchForm.sourceType
    params.kind = 'material'
    const res = await inventoryApi.stockIn.list(params)
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载数据失败') } finally { loading.value = false; nextTick(() => { initColumnDrag(); fitTable(tableRef.value, visibleColumns, dataList) }) }
}

async function loadWarehouses() {
  try {
    const res = await foundationApi.warehouses.list({ page: 1, page_size: 100 })
    warehouseList.value = res.items || []
  } catch (e) {}
}

// ========== 入库 ==========
const receiveVisible = ref(false)
const submitting = ref(false)
const receiveForm = reactive({ id: null, batch_no: '', product_code: '', product_name: '', quantity: 0, received_qty: 0, quantity_now: 0, warehouse_id: null })

function openReceive(row) {
  Object.assign(receiveForm, {
    id: row.id, batch_no: row.batch_no || '',
    product_code: row.product_code, product_name: row.product_name,
    quantity: row.quantity, received_qty: row.received_qty || 0,
    quantity_now: (row.quantity || 0) - (row.received_qty || 0), warehouse_id: row.warehouse_id || null,
  })
  if (!warehouseList.value.length) loadWarehouses()
  receiveVisible.value = true
}

async function handleReceive() {
  if (!receiveForm.quantity_now || receiveForm.quantity_now <= 0) { ElMessage.warning('入库数量必须大于 0'); return }
  submitting.value = true
  try {
    const res = await inventoryApi.stockIn.receive(receiveForm.id, {
      quantity: parseFloat(receiveForm.quantity_now) || 0,
    })
    ElMessage.success(res.message || '入库成功')
    receiveVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '入库失败') } finally { submitting.value = false }
}

// ========== 确认完成 / 退回 ==========
async function handleComplete(row) {
  await ElMessageBox.confirm(`确认「${row.batch_no || row.stock_in_no}」已全部入库完成？（已入 ${row.received_qty || 0} / 应入 ${row.quantity}，若数量不一致请确认后继续）`, '提示', { type: 'info' })
  try {
    const res = await inventoryApi.stockIn.complete(row.id)
    ElMessage.success(res.message || '已确认完成')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

async function handleCancel(row) {
  await ElMessageBox.confirm(`确定退回「${row.batch_no || row.stock_in_no}」？退回后销售明细行回到「未生产」状态（仅未收货的待入库单可退回）。`, '提示', { type: 'warning' })
  try {
    const res = await inventoryApi.stockIn.cancel(row.id)
    ElMessage.success(res.message || '已退回')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退回失败') }
}

onMounted(() => { initColumnVisible(); fetchData(); loadWarehouses() })

// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => {
    initColumnVisible()
    initColumnDrag()
    if (dataList.value.length) fitTable(tableRef.value, visibleColumns, dataList)
  })
})

function getSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => { sums[i] = '' })
  const qtyCols = ['quantity', 'received_qty']
  qtyCols.forEach(prop => {
    const idx = columns.findIndex(c => c.prop === prop)
    if (idx >= 0) sums[idx] = data.reduce((s, r) => s + (Number(r[prop]) || 0), 0)
  })
  if (data.length > 0) sums[0] = '合计'
  return sums
}

// ========== 退回已入库数量 ==========
const returnVisible = ref(false)
const returnForm = reactive({ id: null, batch_no: '', received_qty: 0, return_qty: 0 })
async function openReturn(row) {
  Object.assign(returnForm, { id: row.id, batch_no: row.batch_no || '', received_qty: row.received_qty || 0, return_qty: 0 })
  returnVisible.value = true
}
async function handleReturn() {
  if (!returnForm.return_qty || returnForm.return_qty <= 0) { ElMessage.warning('请输入退回数量'); return }
  if (returnForm.return_qty > returnForm.received_qty) { ElMessage.warning('退回数量不能超过已入数量'); return }
  try {
    const res = await inventoryApi.stockIn.return(returnForm.id, { return_qty: returnForm.return_qty })
    ElMessage.success(res.message || '已退回')
    returnVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退回失败') }
}

// ========== 上下区域高度拖动 ==========
const SPLIT_KEY = 'mazu_material_ins_splitH'
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

// ========== 穿透看收货明细 ==========
const selectedRow = ref(null)
const detailList = ref([])
const detailLoading = ref(false)
const detailStockInNo = ref('')
async function openDetail(row) {
  selectedRow.value = row
  detailStockInNo.value = row.stock_in_no || ''
  detailLoading.value = true
  try {
    const res = await inventoryApi.stockIn.records(row.id)
    detailList.value = res.items || []
  } catch (e) { detailList.value = [] } finally { detailLoading.value = false }
}

function detailSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) sums[i] = '合计'
    else if (col.property === 'quantity') sums[i] = data.reduce((s, r) => s + (r.quantity || 0), 0)
    else sums[i] = ''
  })
  return sums
}
</script>
