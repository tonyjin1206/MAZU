<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <el-form :inline="true" :model="searchForm">
            <el-form-item label="关键字">
              <el-input v-model="searchForm.keyword" placeholder="物料编码/名称/批次" clearable style="width: 170px" @keyup.enter="fetchData" />
            </el-form-item>
            <el-form-item label="日期">
              <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width: 240px" @change="fetchData" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="fetchData">查询</el-button>
              <el-button @click="resetSearch">重置</el-button>
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="openOutDialog">原料出库</el-button>
        </div>
      </template>
    </el-card>

    <el-card>
      <el-table :data="dataList" v-loading="loading" stripe border size="small" show-summary :summary-method="getSummary" style="width: 100%">
        <el-table-column prop="out_date" label="日期" width="160" sortable />
        <el-table-column prop="out_no" label="出库单号" width="150" sortable />
        <el-table-column prop="material_code" label="物料编码" width="120" sortable />
        <el-table-column prop="material_name" label="物料名称" min-width="140" show-overflow-tooltip sortable />
        <el-table-column prop="batch_no" label="批次号" min-width="130" sortable />
        <el-table-column prop="quantity" label="数量" width="100" align="right" sortable>
          <template #default="{ row }">{{ row.quantity || 0 }}</template>
        </el-table-column>
        <el-table-column prop="warehouse" label="仓库" min-width="120" sortable />
        <el-table-column prop="source" label="来源" width="100" align="center" sortable>
          <template #default="{ row }">
            <el-tag :type="row.source === '手动出库' ? 'success' : 'warning'" size="small">{{ row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="130" show-overflow-tooltip sortable />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.source === '手动出库'" link type="warning" size="small" @click="handleReturn(row)">退回</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 16px" />
    </el-card>

    <!-- 原料出库弹窗 -->
    <el-dialog v-model="outVisible" title="原料出库" width="900px" destroy-on-close>
      <div style="display: flex; justify-content: flex-end; margin-bottom: 10px">
        <el-button type="primary" size="small" @click="addRow">添加明细</el-button>
      </div>
      <el-table :data="outRows" border size="small" style="width: 100%">
        <el-table-column label="物料" min-width="220">
          <template #default="{ row }">
            <el-input :model-value="row.material_label" placeholder="点击选择物料" readonly @click="openMaterialPicker(row)" />
          </template>
        </el-table-column>
        <el-table-column label="批次" width="200">
          <template #default="{ row }">
            <el-select v-model="row.batch_no" placeholder="选择批次" :disabled="!row.material_id" style="width: 100%" :loading="row.batchLoading">
              <el-option v-for="b in row.batches" :key="b.batch_no" :label="`${b.batch_no}（可用 ${b.available}）`" :value="b.batch_no" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="0" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="150">
          <template #default="{ row }">
            <el-input v-model="row.remark" placeholder="备注（可选）" />
          </template>
        </el-table-column>
        <el-table-column label="" width="60" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" size="small" @click="outRows.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="outVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交出库</el-button>
      </template>
    </el-dialog>

    <!-- 物料选择弹窗 -->
    <el-dialog v-model="pickerVisible" title="选择材料" width="720px" destroy-on-close>
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-input v-model="materialSearch" placeholder="输入编码/名称搜索，回车查询" clearable @keyup.enter="searchMaterial" @clear="searchMaterial" />
        <el-button type="primary" @click="searchMaterial">搜索</el-button>
      </div>
      <el-table :data="materialList" height="380" border size="small" highlight-current-row @row-click="pickMaterial">
        <el-table-column prop="code" label="编码" width="120" sortable />
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip sortable />
        <el-table-column prop="spec" label="规格" min-width="130" show-overflow-tooltip sortable />
        <el-table-column prop="unit" label="单位" width="70" sortable />
        <el-table-column prop="purchase_price" label="采购价" width="100" align="right" sortable />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../../api/request'

const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })
const searchForm = reactive({ keyword: '', start_date: '', end_date: '' })
const dateRange = ref(null)

function resetSearch() {
  searchForm.keyword = ''
  dateRange.value = null
  queryParams.page = 1
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await request.get('/inventory/material-outs', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载数据失败') } finally { loading.value = false }
}

function getSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => { sums[i] = '' })
  const idx = columns.findIndex(c => c.prop === 'quantity')
  if (idx >= 0) sums[idx] = data.reduce((s, r) => s + (Number(r.quantity) || 0), 0)
  if (data.length > 0) sums[0] = '合计'
  return sums
}

// ========== 原料出库弹窗 ==========
const outVisible = ref(false)
const submitting = ref(false)
const outRows = ref([])
const pickerVisible = ref(false)
const materialSearch = ref('')
const materialList = ref([])
let pickTargetRow = null

function openOutDialog() {
  if (!outRows.value.length) addRow()
  outVisible.value = true
}

function addRow() {
  outRows.value.push({ material_id: null, material_label: '', batch_no: '', batches: [], quantity: 0, remark: '', batchLoading: false })
}

function openMaterialPicker(row) {
  pickTargetRow = row
  materialSearch.value = ''
  searchMaterial()
  pickerVisible.value = true
}

async function searchMaterial() {
  try {
    const res = await request.get('/foundation/materials-select', { params: { keyword: materialSearch.value, page: 1, page_size: 100 } })
    materialList.value = res || []
  } catch {}
}

async function pickMaterial(m) {
  pickTargetRow.material_id = m.id
  pickTargetRow.material_label = `${m.code} ${m.name}${m.spec ? ' ' + m.spec : ''}`
  pickTargetRow.batch_no = ''
  pickTargetRow.batches = []
  pickerVisible.value = false
  await loadBatches(pickTargetRow)
}

async function loadBatches(row) {
  row.batchLoading = true
  row.batches = []
  try {
    const res = await request.get('/inventory/available-batches', { params: { material_id: row.material_id } })
    row.batches = (res.items || []).filter(b => b.available > 0)
  } catch {} finally { row.batchLoading = false }
}

async function handleSubmit() {
  const items = outRows.value
    .filter(r => r.material_id && r.quantity > 0)
    .map(r => ({ material_id: r.material_id, batch_no: r.batch_no, quantity: r.quantity, remark: r.remark }))
  if (!items.length) { ElMessage.warning('请至少填写一行有效出库明细（物料+数量）'); return }
  if (items.some(r => !r.batch_no)) { ElMessage.warning('存在未选择批次的明细行'); return }
  for (const it of items) {
    const row = outRows.value.find(r => r.material_id === it.material_id && r.batch_no === it.batch_no)
    const b = row?.batches?.find(x => x.batch_no === it.batch_no)
    if (b && it.quantity > b.available) { ElMessage.warning(`批次 ${it.batch_no} 可用 ${b.available}，超出出库数量`); return }
  }
  submitting.value = true
  try {
    const res = await request.post('/inventory/material-outs', { items })
    ElMessage.success(res.message || '原料出库成功')
    outVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '出库失败') } finally { submitting.value = false }
}

onMounted(fetchData)

async function handleReturn(row) {
  try {
    await ElMessageBox.confirm(`确认退回出库单「${row.out_no}」？库存将回补原批次，并生成红字流水。`, '退回确认', { type: 'warning' })
    const res = await request.post(`/inventory/material-outs/${row.out_no}/return`)
    ElMessage.success(res.message || '已退回')
    fetchData()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '操作失败') }
}
</script>
