<template>
  <div>
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- ===== Tab 1: 库存余额 ===== -->
      <el-tab-pane label="库存余额" name="balance">
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
            <el-form-item label="物料名称">
              <el-input v-model="balanceQuery.keyword" placeholder="名称/编码" clearable style="width: 160px" @keyup.enter="fetchBalance" />
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker v-model="balanceQuery.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 280px" @change="onDateRangeChange" />
            </el-form-item>
          </el-form>
          <el-table :data="balanceList" v-loading="balanceLoading" stripe border @row-click="viewTransactions" :show-summary="true" :summary-method="getBalanceSummary">
            <el-table-column prop="warehouse" label="仓库" width="100" />
            <el-table-column label="物料" min-width="45">
              <template #default="{ row }">
                <span style="font-weight: 500; color: #409eff; cursor: pointer">{{ row.material_name || row.product_name }}</span>
                <el-tag size="small" type="info" style="margin-left: 4px">{{ row.material_code || row.product_code }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="规格" min-width="80">
              <template #default="{ row }">{{ row.material_spec || row.product_spec || '-' }}</template>
            </el-table-column>
            <el-table-column label="型号" min-width="80">
              <template #default="{ row }">{{ row.material_model || row.product_model || '-' }}</template>
            </el-table-column>
            <el-table-column label="类型" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.material_id ? 'warning' : 'primary'" size="small">{{ row.material_id ? '原料' : '成品' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="batch_no" label="批次号" width="120" />
            <!-- 无日期：当前快照 -->
            <template v-if="!balancePeriod">
              <el-table-column prop="quantity" label="数量" width="90" align="right"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
              <el-table-column prop="unit_cost" label="单价(¥)" width="90" align="right"><template #default="{ row }">{{ $fm(row.unit_cost) }}</template></el-table-column>
              <el-table-column prop="total_cost" label="金额(¥)" width="110" align="right"><template #default="{ row }">{{ $fm(row.total_cost) }}</template></el-table-column>
            </template>
            <!-- 有日期：期间视图 -->
            <template v-else>
              <el-table-column prop="opening_qty" label="期初" width="80" align="right">
                <template #default="{ row }">
                  <span style="color: #909399">{{ $fq(row.opening_qty) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="period_in_qty" label="入库" width="80" align="right">
                <template #default="{ row }">
                  <span style="color: #67c23a">{{ $fq(row.period_in_qty) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="period_out_qty" label="出库" width="80" align="right">
                <template #default="{ row }">
                  <span style="color: #f56c6c">{{ $fq(row.period_out_qty) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="closing_qty" label="期末数量" width="90" align="right">
                <template #default="{ row }">
                  <span style="font-weight: bold">{{ $fq(row.closing_qty) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="closing_cost" label="期末金额" width="110" align="right">
                <template #default="{ row }">
                  <span style="color: #409eff; font-weight: bold">{{ $fm(row.closing_cost) }}</span>
                </template>
              </el-table-column>
            </template>
            <el-table-column label="来源" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.source_type === 'purchase'" type="success" size="small">采购</el-tag>
                <el-tag v-else-if="row.source_type === 'production'" type="primary" size="small">生产</el-tag>
                <el-tag v-else size="small">{{ row.source_type }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="balancePage" v-model:page-size="balancePageSize" :total="balanceTotal" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchBalance" @current-change="fetchBalance" style="margin-top: 12px" />
        </el-card>
      </el-tab-pane>

      <!-- ===== Tab 2: 库存流水 ===== -->
      <el-tab-pane label="库存流水" name="transactions">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: flex-end; gap: 8px">
              <el-button type="primary" @click="fetchTransactions">查询</el-button>
              <el-button @click="resetTransactions">重置</el-button>
              <el-button v-if="transQuery.keyword || transQuery.material_id || transQuery.product_id" @click="clearTransLink">✕ 清除联查筛选</el-button>
            </div>
          </template>
          <el-form :inline="true" label-width="70px" style="margin-bottom: 12px">
            <el-form-item label="仓库">
              <el-select v-model="transQuery.warehouse_id" clearable placeholder="全部" style="width: 140px" @change="fetchTransactions">
                <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="物料类型">
              <el-select v-model="transQuery.type" clearable placeholder="全部" style="width: 120px" @change="fetchTransactions">
                <el-option label="原材料" value="material" />
                <el-option label="成品" value="product" />
              </el-select>
            </el-form-item>
            <el-form-item label="出入库">
              <el-select v-model="transQuery.direction" clearable placeholder="全部" style="width: 100px" @change="fetchTransactions">
                <el-option label="入库" value="in" />
                <el-option label="出库" value="out" />
              </el-select>
            </el-form-item>
            <el-form-item label="物料名称">
              <el-input v-model="transQuery.keyword" placeholder="名称/编码" clearable style="width: 160px" @keyup.enter="fetchTransactions" />
            </el-form-item>
          </el-form>
          <el-table :data="transactionList" v-loading="transLoading" stripe border :show-summary="true" :summary-method="getTransSummary">
            <el-table-column label="日期" width="100">
              <template #default="{ row }">{{ (row.trans_date || '').slice(0, 10) }}</template>
            </el-table-column>
            <el-table-column prop="trans_no" label="库存流水号" width="160" />
            <el-table-column prop="trans_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.trans_type === 'issue_cancel' || row.trans_type.includes('in') ? 'success' : 'danger'" size="small">
                  {{ transTypeLabel(row.trans_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="物料" min-width="160">
              <template #default="{ row }">
                <span style="font-weight: 500">{{ row.material_name || row.product_name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="batch_no" label="批次号" width="140" />
            <el-table-column prop="quantity" label="数量" width="100" align="right"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
            <el-table-column label="单价(¥)" width="100" align="right"><template #default="{ row }">{{ $fm(row.unit_cost) }}</template></el-table-column>
            <el-table-column prop="total_amount" label="金额(¥)" width="120" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
            <el-table-column prop="warehouse" label="仓库" width="100" />
            <el-table-column prop="source_doc_type" label="单据" width="100" />
            <el-table-column prop="source_doc_no" label="单据号" width="140" />
          </el-table>
          <el-pagination v-model:current-page="transPage" v-model:page-size="transPageSize" :total="transTotal" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchTransactions" @current-change="fetchTransactions" style="margin-top: 12px" />
        </el-card>
      </el-tab-pane>

      <!-- ===== Tab 3: 盘点管理 ===== -->
      <el-tab-pane label="盘点管理" name="stocktake">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: flex-end; gap: 8px">
              <el-button type="primary" @click="openStocktakeCreate">新建盘点</el-button>
              <el-button @click="fetchStocktakes">刷新</el-button>
            </div>
          </template>
          <el-table :data="stocktakeList" v-loading="stocktakeLoading" stripe border>
            <el-table-column prop="stocktake_no" label="盘点单号" width="170" />
            <el-table-column prop="warehouse_name" label="仓库" width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === '已提交' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="item_count" label="明细项" width="80" align="center" />
            <el-table-column prop="operator" label="盘点人" width="110" />
            <el-table-column prop="remark" label="备注" min-width="140" />
            <el-table-column prop="created_at" label="创建时间" width="160" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewStocktake(row)">详情</el-button>
                <el-button v-if="row.status === '草稿'" link type="danger" @click="handleDeleteStocktake(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="stocktakePage" v-model:page-size="stocktakePageSize" :total="stocktakeTotal" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next" @size-change="fetchStocktakes" @current-change="fetchStocktakes" style="margin-top: 12px" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建盘点：选仓库 -->
    <el-dialog v-model="stocktakeCreateVisible" title="新建盘点单" width="420px">
      <el-form label-width="80px">
        <el-form-item label="盘点仓库" required>
          <el-select v-model="stocktakeCreateWarehouse" placeholder="选择仓库" style="width: 100%">
            <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stocktakeCreateRemark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stocktakeCreateVisible = false">取消</el-button>
        <el-button type="primary" :loading="stocktakeCreateLoading" @click="handleCreateStocktake">创建并盘点</el-button>
      </template>
    </el-dialog>

    <!-- 盘点明细：录实盘数 -->
    <el-dialog v-model="stocktakeEditVisible" :title="`盘点单 ${stocktakeEditNo}（${stocktakeEditStatus}）`" width="780px">
      <el-alert type="info" :closable="false" style="margin-bottom: 10px"
        title="录入实盘数量后自动保存；提交后按差异生成盘盈/盘亏流水并更新台账，不可再修改" />
      <el-table :data="stocktakeEditItems" v-loading="stocktakeEditLoading" stripe border max-height="460">
        <el-table-column prop="batch_no" label="批次号" width="140" />
        <el-table-column label="物料" min-width="150">
          <template #default="{ row }">{{ row.material_name || row.product_name }}</template>
        </el-table-column>
        <el-table-column label="类型" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.material_id ? 'warning' : 'primary'" size="small">{{ row.material_id ? '原料' : '成品' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="book_qty" label="账面数" width="100" align="right" />
        <el-table-column label="实盘数" width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.actual_qty" :min="0" :controls="false" size="small" style="width: 100%"
              :disabled="stocktakeEditStatus !== '草稿'" @change="(v) => saveStocktakeItem(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="差异" width="110" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.diff_qty > 0 ? '#67c23a' : (row.diff_qty < 0 ? '#f56c6c' : '#909399') }">
              {{ $fq(row.diff_qty) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="stocktakeEditVisible = false">关闭</el-button>
        <el-button v-if="stocktakeEditStatus === '草稿'" type="primary" :loading="stocktakeSubmitting" @click="handleSubmitStocktake">提交盘点</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { inventoryApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

const activeTab = ref('balance')
const warehouseList = ref([])

// ===== 库存余额 =====
const balanceList = ref([])
const balanceLoading = ref(false)
const balanceTotal = ref(0)
const balancePage = ref(1)
const balancePageSize = ref(20)
const balanceQuery = reactive({ warehouse_id: null, type: '', keyword: '', dateRange: null })
const balancePeriod = ref(false) // 是否显示期间视图

async function fetchBalance() {
  balanceLoading.value = true
  balancePeriod.value = !!balanceQuery.dateRange
  try {
    const params = { page: balancePage.value, page_size: balancePageSize.value }
    if (balanceQuery.warehouse_id) params.warehouse_id = balanceQuery.warehouse_id
    if (balanceQuery.type) params.type = balanceQuery.type
    if (balanceQuery.keyword) params.keyword = balanceQuery.keyword
    if (balanceQuery.dateRange && balanceQuery.dateRange[0]) {
      params.start_date = balanceQuery.dateRange[0]
      params.end_date = balanceQuery.dateRange[1]
    }
    const res = await inventoryApi.balance(params)
    balanceList.value = res.items || []
    balanceTotal.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') } finally { balanceLoading.value = false }
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
const transPageSize = ref(20)
const transQuery = reactive({ warehouse_id: null, type: '', direction: '', keyword: '', material_id: null, product_id: null })

const transTypeMap = {
  purchase_in: '采购入库', production_in: '完工入库',
  sale_out: '销售出库', outsource_out: '委外发料', material_issue_out: '生产领料',
  purchase_return_out: '采购红冲', sale_return_in: '销售退货',
  stocktake_in: '盘点盘盈', stocktake_out: '盘点盘亏',
  issue_cancel: '取消发料', receipt_cancel: '取消入库',
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
    const res = await inventoryApi.transactions(params)
    transactionList.value = res.items || []
    transTotal.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') } finally { transLoading.value = false }
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

function onTabChange(tab) {
  if (tab === 'transactions' && (transQuery.material_id || transQuery.product_id)) {
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
  foundationApi.warehouses.list({ page_size: 50 }).then(res => {
    warehouseList.value = res.items || []
  }).catch(() => {})
  fetchBalance()
})

// ===== 盘点 =====
const stocktakeList = ref([])
const stocktakeLoading = ref(false)
const stocktakeTotal = ref(0)
const stocktakePage = ref(1)
const stocktakePageSize = ref(10)
const stocktakeCreateVisible = ref(false)
const stocktakeCreateWarehouse = ref(null)
const stocktakeCreateRemark = ref('')
const stocktakeCreateLoading = ref(false)
const stocktakeEditVisible = ref(false)
const stocktakeEditLoading = ref(false)
const stocktakeEditItems = ref([])
const stocktakeEditNo = ref('')
const stocktakeEditStatus = ref('')
const stocktakeEditId = ref(null)
const stocktakeSubmitting = ref(false)

async function fetchStocktakes() {
  stocktakeLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.list({ page: stocktakePage.value, page_size: stocktakePageSize.value })
    stocktakeList.value = res.items || []
    stocktakeTotal.value = res.total || 0
  } catch (e) { ElMessage.error('加载盘点单失败') } finally { stocktakeLoading.value = false }
}

function openStocktakeCreate() {
  stocktakeCreateWarehouse.value = null
  stocktakeCreateRemark.value = ''
  stocktakeCreateVisible.value = true
}

async function handleCreateStocktake() {
  if (!stocktakeCreateWarehouse.value) { ElMessage.warning('请选择盘点仓库'); return }
  stocktakeCreateLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.create({
      warehouse_id: stocktakeCreateWarehouse.value,
      remark: stocktakeCreateRemark.value,
    })
    ElMessage.success(res.message || '盘点单已创建')
    stocktakeCreateVisible.value = false
    fetchStocktakes()
    openStocktakeEdit(res.id)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') } finally { stocktakeCreateLoading.value = false }
}

async function openStocktakeEdit(id) {
  stocktakeEditVisible.value = true
  stocktakeEditLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.get(id)
    stocktakeEditId.value = res.id
    stocktakeEditNo.value = res.stocktake_no
    stocktakeEditStatus.value = res.status
    stocktakeEditItems.value = res.items || []
  } catch (e) { ElMessage.error('加载盘点明细失败') } finally { stocktakeEditLoading.value = false }
}

function viewStocktake(row) { openStocktakeEdit(row.id) }

async function saveStocktakeItem(item, val) {
  if (stocktakeEditStatus.value !== '草稿') return
  try {
    await inventoryApi.stocktakes.updateItem(stocktakeEditId.value, item.id, { actual_qty: val ?? 0 })
    item.diff_qty = Math.round(((val ?? 0) - item.book_qty) * 10000) / 10000
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存实盘数失败')
    item.actual_qty = item.book_qty
  }
}

async function handleSubmitStocktake() {
  await ElMessageBox.confirm('提交后按差异生成盘盈/盘亏流水并更新台账，且不可修改/删除。确定提交？', '提交盘点', { type: 'warning' })
  stocktakeSubmitting.value = true
  try {
    const res = await inventoryApi.stocktakes.submit(stocktakeEditId.value)
    ElMessage.success(res.message || '盘点已提交')
    stocktakeEditVisible.value = false
    fetchStocktakes()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '提交失败') } finally { stocktakeSubmitting.value = false }
}

async function handleDeleteStocktake(row) {
  await ElMessageBox.confirm(`删除盘点单 ${row.stocktake_no}？`, '提示', { type: 'warning' })
  try {
    await inventoryApi.stocktakes.remove(row.id)
    ElMessage.success('盘点单已删除')
    fetchStocktakes()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
