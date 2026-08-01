<template>
  <div>
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: flex-end; gap: 8px">
              <el-button type="primary" @click="fetchBalance">查询</el-button>
              <el-button @click="resetBalance">重置</el-button>
            </div>
          </template>
          <el-form :inline="true" label-width="70px">
            <el-form-item label="仓库">
              <el-select v-model="balanceQuery.warehouse_id" clearable placeholder="全部" style="width: 140px" @change="fetchBalance">
                <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="物料类型">
              <el-select v-model="balanceQuery.type" clearable placeholder="全部" style="width: 120px" @change="fetchBalance">
                <el-option label="原材料" value="material" />
                <el-option label="成品" value="product" />
              </el-select>
            </el-form-item>
            <el-form-item label="编码">
              <el-input v-model="balanceQuery.code" placeholder="物料编码" clearable style="width: 130px" @keyup.enter="fetchBalance" />
            </el-form-item>
            <el-form-item label="名称">
              <el-input v-model="balanceQuery.keyword" placeholder="物料名称" clearable style="width: 140px" @keyup.enter="fetchBalance" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="fetchBalance">搜索</el-button>
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker v-model="balanceQuery.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 280px" @change="onDateRangeChange" />
            </el-form-item>
          </el-form>
          <el-table ref="balanceTableRef" class="drag-table-balance" :key="columnVersion" :data="balanceList" v-loading="balanceLoading" stripe border @row-click="openBatchReceipts" :show-summary="true" :summary-method="getBalanceSummary">
            <el-table-column v-for="col in visibleBalanceColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :align="col.align">
              <template #header>
                <el-dropdown trigger="contextmenu" :hide-on-click="false">
                  <span class="col-header-wrap">
                    <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                    {{ col.label }}
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-for="c in allBalanceColumns" :key="c.prop">
                        <el-checkbox :model-value="c.visible !== false" @change="toggleBalanceColumn(c)">{{ c.label }}</el-checkbox>
                      </el-dropdown-item>
                      <el-dropdown-item divided @click.stop="openOrderDialog" style="color: #409eff">列排序...</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
              <template v-if="col.prop === 'material_name'" #default="{ row }">
                <span style="font-weight: 500">{{ row.material_name || row.product_name }}</span>
              </template>
              <template v-else-if="col.prop === 'material_code'" #default="{ row }">
                <span style="color: #909399">{{ row.material_code || row.product_code }}</span>
              </template>
              <template v-else-if="col.prop === 'material_spec'" #default="{ row }">{{ row.material_spec || row.product_spec || '-' }}</template>
              <template v-else-if="col.prop === 'material_model'" #default="{ row }">{{ row.material_model || row.product_model || '-' }}</template>
              <template v-else-if="col.prop === 'material_id'" #default="{ row }">
                <el-tag :type="row.material_id ? 'warning' : 'primary'" size="small">{{ row.material_id ? '原料' : '成品' }}</el-tag>
              </template>
              <template v-else-if="col.prop === 'unit_cost'" #default="{ row }">{{ $fm(row.unit_cost) }}</template>
              <template v-else-if="col.prop === 'total_cost'" #default="{ row }">{{ $fm(row.total_cost) }}</template>
              <template v-else-if="col.prop === 'opening_qty'" #default="{ row }">
                <span style="color: #909399">{{ $fq(row.opening_qty) }}</span>
              </template>
              <template v-else-if="col.prop === 'period_in_qty'" #default="{ row }">
                <span style="color: #67c23a">{{ $fq(row.period_in_qty) }}</span>
              </template>
              <template v-else-if="col.prop === 'period_out_qty'" #default="{ row }">
                <span style="color: #f56c6c">{{ $fq(row.period_out_qty) }}</span>
              </template>
              <template v-else-if="col.prop === 'closing_qty'" #default="{ row }">
                <span style="font-weight: bold">{{ $fq(row.closing_qty) }}</span>
              </template>
              <template v-else-if="col.prop === 'closing_cost'" #default="{ row }">
                <span style="color: #409eff; font-weight: bold">{{ $fm(row.closing_cost) }}</span>
              </template>
              <template v-else-if="col.prop === 'so_order_qty' || col.prop === 'so_received_qty'" #default="{ row }">{{ $fq(row[col.prop]) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="balancePage" v-model:page-size="balancePageSize" :total="balanceTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @size-change="fetchBalance" @current-change="fetchBalance" style="margin-top: 12px" />
        </el-card>
    
    <!-- 列排序弹窗 -->
    <ColumnOrderDialog v-model:visible="orderDialogVisible" :columns="orderList" @opened="initOrderDrag" @confirm="confirmOrder" />
    
    <!-- 批次收货记录弹窗（点击批次行穿透） -->
    <el-dialog v-model="batchReceiptVisible" :title="'批次收货记录 — ' + (batchReceiptBatch || '')" width="640px" destroy-on-close>
      <el-table :data="batchReceiptList" border stripe size="small" show-summary :summary-method="batchReceiptSummary">
        <el-table-column prop="in_date" label="入库日期" width="120" />
        <el-table-column prop="warehouse" label="仓库" width="120" />
        <el-table-column prop="receipt_no" label="入库单号" min-width="140" />
        <el-table-column prop="quantity" label="本次数量" width="100" align="right" />
      </el-table>
      <div style="color: #909399; font-size: 12px; margin-top: 8px">点击上方批次行查看该批次的每次入库记录</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnOrderDialog from '../../components/ColumnOrderDialog.vue'
import request from '@/api/request'

// ===== 列配置（可拖拽排序）=====
// 余额表：快照视图(snapshot)与期间视图(period)列互斥，由 balancePeriod 过滤显示
const STORAGE_KEY = 'mazu_inventory_balance_columns'
const defaultColumns = [
  { prop: 'warehouse', label: '仓库', width: 100, sortable: true },
  { prop: 'material_name', label: '物料名称', minWidth: 45, sortable: true, measureKeys: ['material_name', 'product_name'] },
  { prop: 'material_code', label: '物料编码', minWidth: 90, sortable: true, measureKeys: ['material_code', 'product_code'] },
  { prop: 'material_spec', label: '规格', minWidth: 80, sortable: true, measureKeys: ['material_spec', 'product_spec'] },
  { prop: 'material_model', label: '型号', minWidth: 80, sortable: true, measureKeys: ['material_model', 'product_model'] },
  { prop: 'material_id', label: '类型', width: 80, align: 'center', sortable: true },
  { prop: 'batch_no', label: '批次号', width: 140, sortable: true },
  { prop: 'unit_cost', label: '单价(¥)', width: 90, align: 'right', group: 'snapshot', sortable: true, fmt: 'money' },
  { prop: 'total_cost', label: '金额(¥)', width: 110, align: 'right', group: 'snapshot', sortable: true, fmt: 'money' },
  { prop: 'opening_qty', label: '期初', width: 80, align: 'right', group: 'period', sortable: true, fmt: 'qty' },
  { prop: 'period_in_qty', label: '入库', width: 80, align: 'right', group: 'period', sortable: true, fmt: 'qty' },
  { prop: 'period_out_qty', label: '出库', width: 80, align: 'right', group: 'period', sortable: true, fmt: 'qty' },
  { prop: 'closing_qty', label: '期末数量', width: 90, align: 'right', group: 'period', sortable: true, fmt: 'qty' },
  { prop: 'closing_cost', label: '期末金额', width: 110, align: 'right', group: 'period', sortable: true, fmt: 'money' },
  { prop: 'so_order_qty', label: '订单数', width: 70, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'so_received_qty', label: '已入库', width: 70, align: 'right', sortable: true, fmt: 'qty' },
]
const { columns, columnVersion, initColumnDrag, orderDialogVisible, orderList, openOrderDialog, initOrderDrag, confirmOrder } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-balance .el-table__header-wrapper thead tr')
const { fitTable } = useColumnAutoFit()
const balanceTableRef = ref(null)
const transTableRef = ref(null)
const balanceColumns = computed(() => columns.value.filter(c => balancePeriod.value ? c.group !== 'snapshot' : c.group !== 'period'))
const { visibleColumns: visibleBalanceColumns, allColumns: allBalanceColumns, toggleColumn: toggleBalanceColumn, initColumnVisible: initBalanceVisible } = useColumnCustomize(balanceColumns, STORAGE_KEY)

const TRANS_STORAGE_KEY = 'mazu_inventory_trans_columns'
const defaultTransColumns = [
  { prop: 'trans_date', label: '日期', width: 100, sortable: true },
  { prop: 'trans_no', label: '库存流水号', width: 160, sortable: true },
  { prop: 'trans_type', label: '类型', width: 100, sortable: true },
  { prop: 'material_name', label: '物料名称', minWidth: 160, sortable: true, measureKeys: ['material_name', 'product_name'] },
  { prop: 'material_code', label: '物料编码', minWidth: 90, sortable: true, measureKeys: ['material_code', 'product_code'] },
  { prop: 'batch_no', label: '批次号', width: 140, sortable: true },
  { prop: 'quantity', label: '数量', width: 100, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'unit_cost', label: '单价(¥)', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'total_amount', label: '金额(¥)', width: 120, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'warehouse', label: '仓库', width: 100, sortable: true },
  { prop: 'source_doc_type', label: '单据', width: 100 , sortable: true },
  { prop: 'source_doc_no', label: '单据号', width: 140 , sortable: true },
]
const { columns: transColumns, columnVersion: transColumnVersion, initColumnDrag: initTransColumnDrag } = useColumnDrag(defaultTransColumns, TRANS_STORAGE_KEY, '.drag-table-trans .el-table__header-wrapper thead tr')
const { visibleColumns: visibleTransColumns, allColumns: allTransColumns, toggleColumn: toggleTransColumn, initColumnVisible: initTransVisible } = useColumnCustomize(transColumns, TRANS_STORAGE_KEY)

const activeTab = ref('balance')
const warehouseList = ref([])

// ===== 库存余额 =====
const balanceList = ref([])
const balanceLoading = ref(false)
const balanceTotal = ref(0)
const balancePage = ref(1)
const balancePageSize = ref(100)
const balanceQuery = reactive({ warehouse_id: null, type: '', code: '', keyword: '', dateRange: null })
const balancePeriod = ref(false) // 是否显示期间视图

async function fetchBalance() {
  balanceLoading.value = true
  balancePeriod.value = !!balanceQuery.dateRange
  try {
    const params = { page: balancePage.value, page_size: balancePageSize.value }
    if (balanceQuery.warehouse_id) params.warehouse_id = balanceQuery.warehouse_id
    if (balanceQuery.type) params.type = balanceQuery.type
    if (balanceQuery.keyword) params.keyword = balanceQuery.keyword
    if (balanceQuery.code) params.code = balanceQuery.code
    if (balanceQuery.dateRange && balanceQuery.dateRange[0]) {
      params.start_date = balanceQuery.dateRange[0]
      params.end_date = balanceQuery.dateRange[1]
    }
    const res = await request.get('/inventory/balance', { params })
    balanceList.value = res.items || []
    balanceTotal.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') } finally {
    balanceLoading.value = false
    nextTick(() => { initColumnDrag(); fitTable(balanceTableRef.value, visibleBalanceColumns, balanceList) })
  }
}

function onDateRangeChange() {
  fetchBalance()
}

function getBalanceSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    const prop = col.property || col.type
    // 数字列汇总
    if (['quantity', 'total_cost', 'opening_qty', 'period_in_qty', 'period_out_qty', 'closing_qty', 'closing_cost'].includes(prop)) {
      sums[i] = data.reduce((s, r) => s + (parseFloat(r[prop]) || 0), 0)
      // 金额格式化
      if (['total_cost', 'closing_cost'].includes(prop)) {
        sums[i] = '¥' + sums[i].toLocaleString(undefined, { minimumFractionDigits: 2 })
      } else {
        sums[i] = sums[i].toLocaleString(undefined, { minimumFractionDigits: 2 })
      }
    } else {
      sums[i] = ''
    }
  })
  return sums
}

function resetBalance() {
  balanceQuery.warehouse_id = null
  balanceQuery.type = ''
  balanceQuery.keyword = ''
  balanceQuery.dateRange = null
  balancePeriod.value = false
  balancePage.value = 1
  fetchBalance()
}

// ===== 库存流水 =====
const transactionList = ref([])
const transLoading = ref(false)
const transTotal = ref(0)
const transPage = ref(1)
const transPageSize = ref(100)
const transQuery = reactive({ warehouse_id: null, type: '', direction: '', keyword: '', material_id: null, product_id: null })

const transTypeMap = {
  purchase_in: '采购入库', production_in: '完工入库',
  sale_out: '销售出库', outsource_out: '委外发料',
  transfer_in: '调拨入库', transfer_out: '调拨出库',
  check_in: '盘点盘盈', check_out: '盘点盘亏',
  issue_cancel: '取消发料', receipt_cancel: '取消入库',
  stock_in_return: '入库退回',
}
function transTypeLabel(type) { return transTypeMap[type] || type }

async function fetchTransactions() {
  transLoading.value = true
  try {
    const params = { page: transPage.value, page_size: transPageSize.value }
    if (transQuery.warehouse_id) params.warehouse_id = transQuery.warehouse_id
    if (transQuery.type) params.type = transQuery.type
    if (transQuery.direction) params.direction = transQuery.direction
    if (transQuery.keyword) params.keyword = transQuery.keyword
    if (transQuery.material_id) params.material_id = transQuery.material_id
    if (transQuery.product_id) params.product_id = transQuery.product_id
    const res = await request.get('/inventory/transactions', { params })
    transactionList.value = res.items || []
    transTotal.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') } finally {
    transLoading.value = false
    nextTick(() => { initTransColumnDrag(); fitTable(transTableRef.value, visibleTransColumns, transactionList) })
  }
}

function resetTransactions() {
  transQuery.warehouse_id = null
  transQuery.type = ''
  transQuery.direction = ''
  transQuery.keyword = ''
  transQuery.material_id = null
  transQuery.product_id = null
  transPage.value = 1
  fetchTransactions()
}

function clearTransLink() {
  transQuery.keyword = ''
  transQuery.material_id = null
  transQuery.product_id = null
  transQuery.direction = ''
  transQuery.type = ''
  transQuery.warehouse_id = null
  transPage.value = 1
  fetchTransactions()
}

// ===== 联查：点击余额行 → 跳转流水并筛选该物料 =====
function viewTransactions(row) {
  transQuery.keyword = row.material_name || row.product_name || ''
  transQuery.material_id = row.material_id || null
  transQuery.product_id = row.product_id || null
  transQuery.warehouse_id = null
  transQuery.direction = ''
  transQuery.type = ''
  transPage.value = 1
  activeTab.value = 'transactions'
  fetchTransactions()
}

// ===== 批次收货记录弹窗（点击批次行穿透） =====
const batchReceiptVisible = ref(false)
const batchReceiptBatch = ref('')
const batchReceiptList = ref([])

async function openBatchReceipts(row) {
  if (!row.batch_no) return
  batchReceiptBatch.value = row.batch_no
  batchReceiptVisible.value = true
  batchReceiptList.value = []
  try {
    const res = await request.get('/inventory/batch-receipts', { params: { batch_no: row.batch_no } })
    batchReceiptList.value = res.items || []
  } catch { batchReceiptList.value = [] }
}

function batchReceiptSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) sums[i] = '合计'
    else if (col.property === 'quantity') sums[i] = data.reduce((s, r) => s + (r.quantity || 0), 0)
    else sums[i] = ''
  })
  return sums
}

function onTabChange(tab) {
  if (tab === 'period') {
    // 收发存默认显示本月
    if (!balanceQuery.dateRange) {
      const now = new Date()
      const first = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
      balanceQuery.dateRange = [first, now.toISOString().slice(0, 10)]
    }
    balancePeriod.value = true
    fetchBalance()
  } else if (tab === 'transactions' && (transQuery.material_id || transQuery.product_id)) {
    fetchTransactions()
  }
}

// ===== 流水合计行 =====
const fmt = (v) => (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fqt = (v) => (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
function getTransSummary({ columns, data }) {
  const sums = []
  columns.forEach((column, index) => {
    if (index === 0) { sums[index] = '合计'; return }
    if (column.property === 'quantity') {
      sums[index] = fqt(data.reduce((s, r) => s + (r.quantity || 0), 0))
    } else if (column.property === 'total_amount' || column.property === 'total_cost') {
      sums[index] = '¥' + fmt(data.reduce((s, r) => s + (r.total_amount || 0), 0))
    } else {
      sums[index] = ''
    }
  })
  return sums
}

onMounted(() => {
  initBalanceVisible()
  initTransVisible()
  request.get('/foundation/warehouses', { params: { page_size: 50 } }).then(res => {
    warehouseList.value = res.items || []
  }).catch(() => {})
  fetchBalance()
  nextTick(initTransColumnDrag)
})

// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initBalanceVisible(); initColumnDrag() })
})

</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
