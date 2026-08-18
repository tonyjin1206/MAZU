<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="订单号/产品" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="已排产" value="已排产" />
            <el-option label="生产中" value="生产中" />
            <el-option label="已完成" value="已完成" />
            <el-option label="部分入库" value="部分入库" />
            <el-option label="已入库" value="已入库" />
            <el-option label="已关闭" value="已关闭" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card v-loading="loading">
      <template v-if="!list.length">
        <el-empty description="没有进行中的生产订单" />
      </template>
      <template v-else>
        <el-table :data="flatRows" stripe border size="small" :span-method="spanMethod" style="table-layout: auto">
          <el-table-column label="订单号" min-width="140">
            <template #default="{ row }"><span style="white-space: nowrap">{{ row.order_no }}</span></template>
          </el-table-column>
          <el-table-column label="产品" min-width="120" prop="product_name" sortable />
          <el-table-column label="数量" width="70" align="right" prop="quantity" sortable />
          <el-table-column label="订单状态" width="80">
            <template #default="{ row }"><el-tag :type="orderStatusType(row.status)" size="small">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="物料" width="90" align="center">
            <template #default="{ row }">
              <el-progress :percentage="row.material_pct" :stroke-width="12" :status="row.material_pct >= 100 ? 'success' : ''" />
            </template>
          </el-table-column>
          <el-table-column label="进度" width="90" align="center">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="14" :color="progressColor(row.progress)" />
            </template>
          </el-table-column>
          <el-table-column label="序号" width="50" align="center" prop="seq" sortable />
          <el-table-column label="工序" min-width="120" prop="process_name" sortable />
          <el-table-column label="工序状态" width="90">
            <template #default="{ row }"><el-tag :type="tagType(row.process_status)" size="small">{{ row.process_status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="委外商" min-width="120" prop="outsourcer_name" sortable />
          <el-table-column label="操作" min-width="380">
            <template #default="{ row }">
              <div style="display: flex; gap: 4px; white-space: nowrap">
                <el-button v-if="row.process_status !== '已完工' && row.process_status !== '待排产'" size="small" type="warning" @click="openIssueByRow(row)">发料</el-button>
                <el-button v-if="row.process_status !== '已完工' && row.process_status !== '待排产'" size="small" type="danger" @click="openCancelIssueByRow(row)">取消发料</el-button>
                <el-button v-if="row.process_status === '待发料' || row.process_status === '已发料' || row.process_status === '加工中'" size="small" type="success" @click="openFinishByRow(row)">完工</el-button>
                <el-button v-if="row.process_status !== '待排产'" size="small" type="info" @click="handleRevertByRow(row)">反退</el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="入库" width="160">
            <template #default="{ row }">
              <div style="display: flex; gap: 4px; white-space: nowrap">
                <el-button v-if="row._isFirst && row.status !== '已关闭'" size="small" type="success" @click="openReceiptByRow(row)">入库</el-button>
                <el-button v-if="row._isFirst && row.last_receipt_id && row.status !== '已关闭'" size="small" type="danger" @click="handleCancelReceiptByRow(row)">取消入库</el-button>
                <el-button v-if="row._isFirst && row.status === '已关闭'" size="small" type="info" @click="handleUncloseByRow(row)">取消关闭</el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="详情" width="80">
            <template #default="{ row }">
              <el-button v-if="row._isFirst" size="small" type="primary" @click="openDetailByRow(row)">详情</el-button>
            </template>
          </el-table-column>
          <el-table-column label="关闭" width="60">
            <template #default="{ row }">
              <el-button v-if="row._isFirst && row.status !== '已关闭'" size="small" type="info" @click="handleCloseByRow(row)">关闭</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <!-- 发料弹窗 -->
    <el-dialog v-model="issueVisible" title="发料" width="900px">
      <div style="margin-bottom: 8px">
        <b>工序：</b>{{ issueProcName }}
      </div>
      <el-table :data="issueRows" border size="small" max-height="400" style="table-layout: auto">
        <el-table-column label="物料" min-width="180">
          <template #default="{ row }">
            <el-select v-model="row.material_id" placeholder="选择" filterable size="small" style="width: 100%">
              <el-option v-for="m in issueMaterialOptions" :key="m.material_id" :label="m.material_name" :value="m.material_id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="计划用量" width="90" align="right">
          <template #default="{ row }"><span style="white-space: nowrap">{{ $fq(row.planned_qty || 0) }}</span></template>
        </el-table-column>
        <el-table-column label="已发" width="80" align="right">
          <template #default="{ row }"><span style="white-space: nowrap">{{ $fq(row.actual_qty || 0) }}</span></template>
        </el-table-column>
        <el-table-column label="批次号" min-width="240">
          <template #default="{ row }">
            <div style="display: flex; gap: 4px; align-items: center">
              <span v-if="row._selectedBatches?.length" style="font-size: 12px; color: #606266; white-space: nowrap">{{ row._selectedBatches.length }}个批次</span>
              <span v-else style="color: #c0c4cc; font-size: 12px">未选批次</span>
              <el-button size="small" @click="openBatchPicker(row)">选择</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="本次发料" width="110" align="right">
          <template #default="{ row }">{{ $fq(row.issue_qty || 0) }}</template>
        </el-table-column>
        <el-table-column width="50">
          <template #default="{ $index }"><el-button link type="danger" size="small" @click="issueRows.splice($index, 1)">删</el-button></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="issueLoading" @click="doIssue">确认发料</el-button>
      </template>
    </el-dialog>

    <!-- 批次选择弹窗 -->
    <el-dialog v-model="batchPickerVisible" title="选择发料批次" width="600px">
      <el-table :data="batchPickerOptions" border size="small" max-height="350" style="table-layout: auto">
        <el-table-column width="50">
          <template #default="{ row }"><el-checkbox v-model="row._selected" @change="recalcBatchPicker" /></template>
        </el-table-column>
        <el-table-column label="批次号" min-width="140" prop="batch_no" sortable />
        <el-table-column label="库存数量" width="100" align="right">
          <template #default="{ row }"><span style="white-space: nowrap">{{ $fq(row.quantity) }}</span></template>
        </el-table-column>
        <el-table-column label="本次发料" width="120">
          <template #default="{ row }"><el-input type="number" v-model="row.issue_qty" :min="0" size="small" style="text-align: right" @input="recalcBatchPicker" /></template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 8px; font-size: 13px; color: #606266">已选 <b>{{ batchPickerSelected }}/{{ batchPickerOptions.length }}</b> 个批次，合计发料 <b>{{ $fq(batchPickerTotal) }}</b></div>
      <template #footer>
        <el-button @click="batchPickerVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmBatchPicker">确认（{{ batchPickerSelected }}个批次）</el-button>
      </template>
    </el-dialog>

    <!-- 取消发料弹窗 -->
    <el-dialog v-model="cancelIssueVisible" title="取消发料" width="650px">
      <el-table :data="cancelIssueList" border size="small" max-height="300" style="table-layout: auto">
        <el-table-column label="发料单号" min-width="140" prop="issue_no" sortable />
        <el-table-column label="物料" min-width="140" prop="material_name" sortable />
        <el-table-column label="批次号" min-width="130" prop="batch_no" sortable />
        <el-table-column label="数量" width="80" align="right" prop="quantity" sortable />
        <el-table-column label="操作" width="80">
          <template #default="{ row }"><el-button size="small" type="danger" @click="doCancelIssue(row)">取消</el-button></template>
        </el-table-column>
      </el-table>
      <div v-if="!cancelIssueList.length" style="text-align: center; color: #909399; padding: 20px">无发料记录</div>
    </el-dialog>

    <!-- 取消入库弹窗 -->
    <el-dialog v-model="cancelReceiptVisible" title="取消入库 - 选择要取消的入库单" width="700px">
      <el-table :data="cancelReceiptList" border size="small" max-height="350" style="table-layout: auto" @selection-change="onCancelReceiptSelect">
        <el-table-column type="selection" width="45" />
        <el-table-column label="入库单号" min-width="140" prop="receipt_no" sortable />
        <el-table-column label="批次号" width="120" prop="batch_no" sortable />
        <el-table-column label="数量" width="70" align="right" prop="quantity" sortable />
        <el-table-column label="材料成本" width="90" align="right">
          <template #default="{ row }">{{ $fm(row.material_cost) }}</template>
        </el-table-column>
        <el-table-column label="加工费" width="80" align="right">
          <template #default="{ row }">{{ $fm(row.process_cost) }}</template>
        </el-table-column>
        <el-table-column label="日期" width="100" prop="receipt_date" sortable />
      </el-table>
      <div v-if="!cancelReceiptList.length" style="text-align: center; color: #909399; padding: 20px">无入库记录</div>
      <template #footer>
        <el-button @click="cancelReceiptVisible = false">取消</el-button>
        <el-button type="danger" :disabled="!cancelReceiptSelected.length" :loading="cancelReceiptLoading" @click="doCancelReceipts">取消选中入库（{{ cancelReceiptSelected.length }}项）</el-button>
      </template>
    </el-dialog>

    <!-- 完工弹窗 -->
    <el-dialog v-model="finishVisible" title="工序完工" width="500px">
      <el-form :model="finishForm" label-width="100px">
        <el-form-item label="工序"><el-input :model-value="finishForm.process_name" disabled /></el-form-item>
        <el-form-item label="委外商"><el-input :model-value="finishForm.outsourcer_name || '自产'" disabled /></el-form-item>
        <el-form-item label="加工单价" prop="unit_price"><el-input type="number" v-model="finishForm.unit_price" :min="0" /></el-form-item>
        <el-form-item label="加工数量" prop="process_qty"><el-input type="number" v-model="finishForm.process_qty" :min="0" /></el-form-item>
        <el-form-item label="加工费金额"><b>{{ $fm((parseFloat(finishForm.process_qty)||0) * (parseFloat(finishForm.unit_price)||0)) }}</b></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="finishVisible = false">取消</el-button>
        <el-button type="primary" :loading="finishLoading" @click="doFinish">确认完工</el-button>
      </template>
    </el-dialog>

    <!-- 入库弹窗 -->
    <el-dialog v-model="receiptVisible" title="完工入库" width="550px">
      <el-form :model="receiptForm" label-width="130px">
        <el-form-item label="生产订单"><el-input :model-value="receiptForm.order_no" disabled size="small" /></el-form-item>
        <el-form-item label="产品名称"><el-input :model-value="receiptForm.product_name" disabled size="small" /></el-form-item>
        <el-form-item label="订单数量"><el-input :model-value="receiptForm.order_qty" disabled size="small" /></el-form-item>
        <el-form-item label="已入库数量"><el-input :model-value="receiptForm.received_qty" disabled size="small" /></el-form-item>
        <el-form-item label="本次入库数量" prop="quantity" required><el-input type="number" v-model="receiptForm.quantity" :min="0" size="small" /></el-form-item>
        <el-form-item label="仓库" prop="warehouse_id" required><el-select v-model="receiptForm.warehouse_id" placeholder="选择" filterable style="width: 100%" size="small"><el-option v-for="w in warehouseOptions" :key="w.id" :label="`${w.code} - ${w.name}`" :value="w.id" /></el-select></el-form-item>
        <el-divider content-position="left">成本转出</el-divider>
        <el-form-item label="材料成本总额"><el-input :model-value="$fm(receiptForm.total_mat_cost)" disabled size="small" /></el-form-item>
        <el-form-item label="已转出材料成本"><el-input :model-value="$fm(receiptForm.transferred_mat_cost)" disabled size="small" /></el-form-item>
        <el-form-item label="本次转出材料成本" prop="material_cost">
          <el-input type="number" v-model="receiptForm.material_cost" :min="0" :max="receiptForm.remain_mat_cost" size="small"
            :placeholder="`自动: ${$fm(receiptForm.auto_mat_cost)}`" />
          <div style="font-size: 12px; color: #909399; line-height: 1.4">留空 = 按剩余投入比例自动结转</div>
        </el-form-item>
        <el-form-item label="加工费总额"><el-input :model-value="$fm(receiptForm.total_proc_cost)" disabled size="small" /></el-form-item>
        <el-form-item label="已转出加工费"><el-input :model-value="$fm(receiptForm.transferred_proc_cost)" disabled size="small" /></el-form-item>
        <el-form-item label="本次转出加工费" prop="process_cost">
          <el-input type="number" v-model="receiptForm.process_cost" :min="0" :max="receiptForm.remain_proc_cost" size="small"
            :placeholder="`自动: ${$fm(receiptForm.auto_proc_cost)}`" />
          <div style="font-size: 12px; color: #909399; line-height: 1.4">留空 = 按剩余投入比例自动结转</div>
        </el-form-item>
        <el-divider />
        <el-form-item label="入库单价(自动)"><el-input :model-value="$fm(receiptForm.auto_unit_cost)" disabled size="small" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="receiptVisible = false">取消</el-button>
        <el-button type="primary" :loading="receiptLoading" @click="doReceipt">确认入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

const router = useRouter()
const loading = ref(false)
const list = ref([])
const warehouseOptions = ref([])

const searchForm = reactive({ keyword: '', status: '' })

function resetSearch() {
  searchForm.keyword = ''; searchForm.status = ''
  fetchData()
}

// 展平：每个订单的工序拆成独立行
const flatRows = computed(() => {
  const result = []
  for (const order of list.value) {
    const procs = order.processes || []
    for (let i = 0; i < procs.length; i++) {
      const p = procs[i]
      result.push({
        _orderIndex: order.id,
        _isFirst: i === 0,
        _isLast: i === procs.length - 1,
        _processCount: procs.length,
        // 订单级字段
        id: order.id,
        order_no: order.order_no,
        product_name: order.product_name,
        quantity: order.quantity,
        status: order.status,
        material_pct: order.material_pct,
        progress: order.progress,
        last_receipt_id: order.last_receipt_id,
        last_receipt_no: order.last_receipt_no,
        // 工序级字段
        seq: p.seq,
        process_id: p.id,
        process_name: p.process_name,
        process_status: p.status,
        outsourcer_name: p.outsourcer_name,
        unit_price: p.unit_price,
        process_qty: p.process_qty,
      })
    }
  }
  return result
})

// 合并单元格：订单级字段在第一行显示，其余行合并
function spanMethod({ row, column, rowIndex, columnIndex }) {
  const orderFields = [0, 1, 2, 3, 4, 5] // 订单号/产品/数量/订单状态/物料/进度
  if (orderFields.includes(columnIndex) && row._processCount > 1) {
    if (row._isFirst) {
      return { rowspan: row._processCount, colspan: 1 }
    }
    return { rowspan: 0, colspan: 0 }
  }
  // 入库(11)、详情(12)和关闭(13)列也合并
  if ((columnIndex === 11 || columnIndex === 12 || columnIndex === 13) && row._processCount > 1) {
    if (row._isFirst) {
      return { rowspan: row._processCount, colspan: 1 }
    }
    return { rowspan: 0, colspan: 0 }
  }
}

function orderStatusType(s) {
  return { '待排产': 'info', '已排产': 'warning', '生产中': 'primary', '已完成': 'success', '部分入库': 'warning', '已入库': 'success', '已关闭': 'info' }[s] || 'info'
}
function tagType(s) {
  return { '待发料': 'info', '已发料': 'warning', '加工中': 'primary', '已完工': 'success' }[s] || 'info'
}
function progressColor(p) {
  if (p >= 100) return '#67c23a'
  if (p >= 50) return '#409eff'
  return '#e6a23c'
}

async function fetchData() {
  loading.value = true
  try {
    const params = {}
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    const res = await productionApi.productions.workspace(params)
    list.value = res.items || []
  } catch {} finally { loading.value = false }
}

async function loadOptions() {
  try { warehouseOptions.value = (await foundationApi.warehouses.list({ page_size: 200 })).items || [] } catch {}
}

// ===== 操作函数（通过 flatRow 反向查找 order 和 process） =====
function findOrder(row) { return list.value.find(o => o.id === row.id) }
function findProcess(row) {
  const order = findOrder(row)
  if (!order) return null
  return (order.processes || []).find(p => p.id === row.process_id)
}

function openDetailByRow(row) { router.push(`/production/detail/${row.id}`) }
function openReceiptByRow(row) { const o = findOrder(row); if (o) openReceipt(o) }
function openIssueByRow(row) { const p = findProcess(row); const o = findOrder(row); if (p && o) openIssue(p, o) }
function openCancelIssueByRow(row) { const p = findProcess(row); const o = findOrder(row); if (p && o) openCancelIssue(p, o) }
function openFinishByRow(row) { const p = findProcess(row); const o = findOrder(row); if (p && o) openFinish(p, o) }
async function handleRevertByRow(row) { const p = findProcess(row); const o = findOrder(row); if (p && o) await handleRevert(p, o) }

async function handleCancelReceiptByRow(row) {
  const o = findOrder(row)
  if (!o) return
  cancelReceiptProdId = o.id
  cancelReceiptVisible.value = true
  cancelReceiptSelected.value = []
  try {
    const res = await productionApi.productions.listReceipts(o.id)
    cancelReceiptList.value = res.items || []
  } catch {}
}

function onCancelReceiptSelect(rows) { cancelReceiptSelected.value = rows }

async function doCancelReceipts() {
  const selected = cancelReceiptSelected.value
  if (!selected.length) return
  await ElMessageBox.confirm(`确认取消 ${selected.length} 笔入库？库存和成本将回退。`, '提示', { type: 'warning' })
  cancelReceiptLoading.value = true
  let ok = 0, errs = []
  for (const r of selected) {
    try {
      await productionApi.productions.cancelReceipt(cancelReceiptProdId, r.id)
      ok++
    } catch (e) { errs.push(`${r.receipt_no}: ${e.response?.data?.detail || '失败'}`) }
  }
  cancelReceiptLoading.value = false
  if (ok) ElMessage.success(`已取消 ${ok} 笔入库`)
  if (errs.length) ElMessage.error(errs.join('; '))
  if (ok) { cancelReceiptVisible.value = false; fetchData() }
}

async function handleCloseByRow(row) {
  const o = findOrder(row)
  if (!o) return
  await ElMessageBox.confirm(`确认关闭生产订单「${o.order_no}」？关闭后无法进行任何操作。`, '提示', { type: 'warning' })
  try {
    await productionApi.productions.close(o.id)
    ElMessage.success('已关闭')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '关闭失败') }
}

async function handleUncloseByRow(row) {
  const o = findOrder(row)
  if (!o) return
  await ElMessageBox.confirm(`确认取消关闭「${o.order_no}」？`, '提示')
  try {
    await productionApi.productions.unclose(o.id)
    ElMessage.success('已取消关闭')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

// 发料
const issueVisible = ref(false)
const issueLoading = ref(false)
const issueRows = ref([])
const issueProcName = ref('')
const issueMaterialOptions = ref([])
let issueProdId = null
let issueProcId = null

const finishVisible = ref(false)
const finishLoading = ref(false)
const finishForm = ref({ process_name: '', outsourcer_name: '', unit_price: 0, process_qty: 0 })
let finishProdId = null
let finishProcId = null

const batchPickerVisible = ref(false)
const batchPickerOptions = ref([])
const batchPickerSelected = ref(0)
const batchPickerTotal = ref(0)
let batchPickerTargetRow = null

const cancelIssueVisible = ref(false)
const cancelIssueList = ref([])
let cancelIssueProdId = null

// 取消入库
const cancelReceiptVisible = ref(false)
const cancelReceiptList = ref([])
const cancelReceiptSelected = ref([])
const cancelReceiptLoading = ref(false)
let cancelReceiptProdId = null

const receiptVisible = ref(false)
const receiptLoading = ref(false)
const receiptForm = ref({
  order_no: '', product_name: '', order_qty: 0, received_qty: 0,
  quantity: 0, warehouse_id: null,
  total_mat_cost: 0, transferred_mat_cost: 0, remain_mat_cost: 0, material_cost: 0,
  total_proc_cost: 0, transferred_proc_cost: 0, remain_proc_cost: 0, process_cost: 0,
  auto_unit_cost: 0,
})
let receiptProdId = null

function recalcBatchPicker() {
  const checked = batchPickerOptions.value.filter(b => b._selected)
  batchPickerSelected.value = checked.length
  batchPickerTotal.value = checked.reduce((s, b) => s + (parseFloat(b.issue_qty) || 0), 0)
}

async function openBatchPicker(row) {
  batchPickerTargetRow = row
  if (!row.material_id) { ElMessage.warning('请先选择物料'); return }
  try {
    const res = await productionApi.batch.query({ material_id: row.material_id })
    const items = (res.items || []).filter(b => b.quantity > 0)
    batchPickerOptions.value = items.map(b => ({ batch_no: b.batch_no, quantity: b.quantity, issue_qty: 0, _selected: false }))
    if (row._selectedBatches) {
      for (const opt of batchPickerOptions.value) {
        const prev = row._selectedBatches.find(s => s.batch_no === opt.batch_no)
        if (prev) { opt._selected = true; opt.issue_qty = prev.issue_qty }
      }
    }
    recalcBatchPicker()
    batchPickerVisible.value = true
  } catch { ElMessage.error('获取批次失败') }
}

function confirmBatchPicker() {
  const checked = batchPickerOptions.value.filter(b => b._selected)
  if (!checked.length) { ElMessage.warning('请至少选择一个批次'); return }
  batchPickerTargetRow._selectedBatches = checked.map(b => ({ batch_no: b.batch_no, issue_qty: parseFloat(b.issue_qty) || 0 }))
  batchPickerTargetRow.issue_qty = batchPickerTotal.value
  batchPickerTargetRow.batch_no = checked.map(b => b.batch_no).join(',')
  batchPickerVisible.value = false
}

async function openIssue(proc, prod) {
  issueProdId = prod.id
  issueProcId = proc.id
  issueProcName.value = `${proc.seq}.${proc.process_name}`
  try {
    const detail = await productionApi.productions.detail(prod.id)
    const mats = detail.materials || []
    issueMaterialOptions.value = mats
    issueRows.value = mats.map(m => ({ material_id: m.material_id, _prevMaterialId: m.material_id, planned_qty: m.planned_qty || 0, actual_qty: m.actual_qty || 0, issue_qty: 0, _selectedBatches: null }))
    if (!issueRows.value.length) issueRows.value.push({ material_id: null, _prevMaterialId: null, planned_qty: 0, actual_qty: 0, issue_qty: 0, _selectedBatches: null })
  } catch {
    issueMaterialOptions.value = []
    issueRows.value = [{ material_id: null, _prevMaterialId: null, planned_qty: 0, actual_qty: 0, issue_qty: 0, _selectedBatches: null }]
  }
  issueVisible.value = true
}

async function openCancelIssue(proc, prod) {
  cancelIssueProdId = prod.id
  cancelIssueVisible.value = true
  cancelIssueList.value = []
  try {
    const res = await productionApi.productions.listIssues(prod.id, proc.id)
    cancelIssueList.value = res.items || []
  } catch {}
}

async function doCancelIssue(row) {
  await ElMessageBox.confirm(`确认取消发料「${row.issue_no}」？物料 ${row.material_name} × ${row.quantity} 将退回批次 ${row.batch_no}。`, '提示', { type: 'warning' })
  try {
    await productionApi.productions.cancelIssue(cancelIssueProdId, row.id)
    ElMessage.success('发料已取消')
    cancelIssueVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

async function doIssue() {
  const validRows = issueRows.value.filter(r => r.material_id && r._selectedBatches?.length)
  if (!validRows.length) { ElMessage.warning('请至少选择物料和批次'); return }
  // 检查是否填写了发料数量（选了批次但数量为0时静默无反应的问题）
  const hasQty = validRows.some(r => (r._selectedBatches || []).some(b => parseFloat(b.issue_qty) > 0))
  if (!hasQty) { ElMessage.warning('请填写发料数量'); return }
  issueLoading.value = true
  let success = 0
  let errors = []
  for (const row of validRows) {
    for (const batch of row._selectedBatches) {
      if (!batch.issue_qty) continue
      try {
        await productionApi.productions.issueMaterial(issueProdId, issueProcId, { material_id: row.material_id, batch_no: batch.batch_no, quantity: batch.issue_qty })
        success++
      } catch (e) { errors.push(`${batch.batch_no}: ${e.response?.data?.detail || '发料失败'}`) }
    }
  }
  issueLoading.value = false
  if (success) ElMessage.success(`发料成功 ${success} 笔`)
  if (errors.length) ElMessage.error(errors.join('; '))
  if (success) { issueVisible.value = false; fetchData() }
}

function openFinish(proc, prod) {
  finishProdId = prod.id
  finishProcId = proc.id
  finishForm.value = { process_name: proc.process_name || '', outsourcer_name: proc.outsourcer_name || '', unit_price: proc.unit_price || 0, process_qty: proc.process_qty || prod.quantity || 0 }
  finishVisible.value = true
}

async function doFinish() {
  if (finishForm.value.outsourcer_name && (parseFloat(finishForm.value.unit_price) <= 0 || parseFloat(finishForm.value.process_qty) <= 0)) {
    ElMessage.warning('委外工序必须录入加工单价和加工数量'); return
  }
  finishLoading.value = true
  try {
    await productionApi.productions.finishProcess(finishProdId, finishProcId, { unit_price: parseFloat(finishForm.value.unit_price) || 0, process_qty: parseFloat(finishForm.value.process_qty) || 0 })
    ElMessage.success('完工成功')
    finishVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '完工失败') } finally { finishLoading.value = false }
}

async function handleRevert(proc, prod) {
  await ElMessageBox.confirm(`反退工序「${proc.seq}.${proc.process_name}」到未开工状态？加工费将被清除。`, '提示', { type: 'warning' })
  try {
    await productionApi.productions.revertProcess(prod.id, proc.id)
    ElMessage.success('已反退')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '反退失败') }
}

function openReceipt(prod) {
  receiptProdId = prod.id
  receiptForm.value = {
    order_no: prod.order_no || '',
    product_name: prod.product_name || '',
    order_qty: prod.quantity || 0,
    received_qty: prod.received_qty || 0,
    quantity: 0,
    warehouse_id: null,
    total_mat_cost: prod.total_material_cost || 0,
    transferred_mat_cost: prod.transferred_material_cost || 0,
    remain_mat_cost: (prod.total_material_cost || 0) - (prod.transferred_material_cost || 0),
    material_cost: '',  // 留空 = 自动结转
    total_proc_cost: prod.total_process_cost || 0,
    transferred_proc_cost: prod.transferred_process_cost || 0,
    remain_proc_cost: (prod.total_process_cost || 0) - (prod.transferred_process_cost || 0),
    process_cost: '',  // 留空 = 自动结转
    auto_mat_cost: 0,
    auto_proc_cost: 0,
    auto_unit_cost: 0,
  }
  receiptVisible.value = true
  calcAutoCost()
}

// 自动结转：剩余投入 × 本次入库占比（最后一次全转）
function calcAutoCost() {
  const f = receiptForm.value
  const qty = parseFloat(f.quantity) || 0
  const remainQty = Math.max(0, f.order_qty - f.received_qty)
  const ratio = remainQty > 0 ? Math.min(1, qty / remainQty) : 1
  f.auto_mat_cost = qty >= remainQty && remainQty > 0
    ? f.remain_mat_cost
    : Math.round(f.remain_mat_cost * ratio * 100) / 100
  f.auto_proc_cost = qty >= remainQty && remainQty > 0
    ? f.remain_proc_cost
    : Math.round(f.remain_proc_cost * ratio * 100) / 100
  f.auto_unit_cost = qty > 0 ? (f.auto_mat_cost + f.auto_proc_cost) / qty : 0
}

async function doReceipt() {
  if (!receiptForm.value.warehouse_id) { ElMessage.warning('请选择仓库'); return }
  if (!receiptForm.value.quantity || receiptForm.value.quantity <= 0) { ElMessage.warning('请输入入库数量'); return }
  receiptLoading.value = true
  try {
    await productionApi.productions.receipt(receiptProdId, {
      quantity: parseFloat(receiptForm.value.quantity),
      warehouse_id: receiptForm.value.warehouse_id,
      material_cost: receiptForm.value.material_cost === '' || receiptForm.value.material_cost === null
        ? null : parseFloat(receiptForm.value.material_cost),
      process_cost: receiptForm.value.process_cost === '' || receiptForm.value.process_cost === null
        ? null : parseFloat(receiptForm.value.process_cost),
    })
    ElMessage.success('入库成功')
    receiptVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '入库失败') } finally { receiptLoading.value = false }
}

// 数量变化 → 重算自动结转建议值（输入框留空时后端按此结转；用户填写则覆盖）
watch(() => receiptForm.value.quantity, () => {
  calcAutoCost()
})

// 物料变更时重置批次选择
watch(issueRows, (rows) => {
  rows.forEach(r => {
    if (r._prevMaterialId !== r.material_id) {
      r._prevMaterialId = r.material_id
      r._selectedBatches = null
      r.issue_qty = 0
    }
  })
}, { deep: true })

onMounted(() => { fetchData(); loadOptions() })
</script>
