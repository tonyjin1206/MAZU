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
          <el-input v-model="searchForm.keyword" placeholder="SD单号/订单号/产品/客户/备注" clearable style="width: 220px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="出库状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="待出库" value="待出库" />
            <el-option label="部分出库" value="部分出库" />
            <el-option label="已出库" value="已出库" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ========== 成品出库列表 ========== -->
    <el-card style="flex: 1; min-height: 0; display: flex; flexDirection: column; overflow: hidden">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>成品出库（业务员通知发货后，由库管选择批次出库）</span>
          <span style="flex: 1" />
        </div>
      </template>
      <el-table :data="dataList" v-loading="loading" stripe border size="small" :height="'calc(100vh - 180px)'">
        <el-table-column prop="delivery_no" label="SD单号" width="150" sortable />
        <el-table-column prop="order_no" label="销售订单号" width="140" sortable />
        <el-table-column prop="customer_name" label="客户名称" minWidth="110" sortable />
        <el-table-column prop="product_code" label="产品编码" width="110" sortable />
        <el-table-column prop="product_name" label="产品名称" minWidth="130" sortable />
        <el-table-column prop="notify_qty" label="通知数量" width="95" align="right" sortable>
          <template #default="{ row }">{{ $fq(row.notify_qty) }}</template>
        </el-table-column>
        <el-table-column prop="delivered_qty" label="已出库" width="90" align="right" sortable>
          <template #default="{ row }"><span>{{ $fq(row.delivered_qty) }}</span></template>
        </el-table-column>
        <el-table-column prop="unout_qty" label="未出库" width="90" align="right" sortable>
          <template #default="{ row }"><span :style="row.unout_qty > 0 ? '' : 'color:#c0c4cc'">{{ $fq(row.unout_qty) }}</span></template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="110" align="right" sortable>
          <template #default="{ row }">{{ $fm(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="notify_date" label="通知日期" width="105" sortable />
        <el-table-column prop="status" label="状态" width="95" align="center" sortable>
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.unout_qty > 0" link type="primary" @click="openIssueDialog(row)">出库</el-button>
            <el-button v-else-if="row.out_records && row.out_records.length" link type="info" @click="showOutRecords(row)">出库记录</el-button>
            <el-button v-if="(row.delivered_qty || 0) > 0" link type="warning" @click="openIssueReturnDialog(row)">退回</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 6px; flex: none" />
    </el-card>

    <!-- ========== 出库弹窗 ========== -->
    <el-dialog v-model="issueVisible" title="库管出库" width="560px" destroy-on-close>
      <el-form :model="issueForm" label-width="100px">
        <el-form-item label="SD单号"><span>{{ issueForm.delivery_no }}</span></el-form-item>
        <el-form-item label="产品"><span>{{ issueForm.product_name }}（{{ issueForm.product_code }}）</span></el-form-item>
        <el-form-item label="通知/已出/可出">
          <span>通知 {{ $fq(issueForm.notify_qty) }} / 已出 {{ $fq(issueForm.delivered_qty) }} / 可出 {{ $fq(issueForm.max_issue) }}</span>
        </el-form-item>
        <el-form-item label="批次号" required>
          <el-select v-model="issueForm.batch_no" placeholder="请选择批次" filterable style="width: 100%">
            <el-option v-for="b in issueBatchList" :key="b.batch_no" :label="batchLabel(b)" :value="b.batch_no" :disabled="b.available <= 0" />
          </el-select>
        </el-form-item>
        <el-form-item label="出库数量" required>
          <el-input type="number" v-model="issueForm.quantity" :min="1" :max="issueMax" style="width: 100%" />
        </el-form-item>
        <el-form-item label="出库日期" required>
          <el-date-picker v-model="issueForm.issue_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="issueForm.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="issueSubmitting" :disabled="!issueForm.batch_no || issueForm.max_issue <= 0" @click="handleIssueSubmit">确认出库</el-button>
      </template>
    </el-dialog>

    <!-- ========== 出库记录弹窗 ========== -->
    <el-dialog v-model="recordsVisible" title="出库记录" width="640px">
      <el-table :data="recordsList" stripe border size="small">
        <el-table-column prop="batch_no" label="批次号" width="170" />
        <el-table-column prop="quantity" label="数量" width="100" align="right">
          <template #default="{ row }">{{ $fq(row.quantity) }}</template>
        </el-table-column>
        <el-table-column prop="warehouse" label="仓库" width="150" />
        <el-table-column prop="operator" label="操作人" width="110" />
        <el-table-column prop="trans_date" label="日期" width="110" />
      </el-table>
    </el-dialog>
    <!-- ========== 出库退回弹窗 ========== -->
    <el-dialog v-model="issueReturnVisible" title="出库退回" width="560px" destroy-on-close>
      <el-form :model="issueReturnForm" label-width="100px">
        <el-form-item label="SD单号"><span>{{ issueReturnForm.delivery_no }}</span></el-form-item>
        <el-form-item label="产品"><span>{{ issueReturnForm.product_name }}（{{ issueReturnForm.product_code }}）</span></el-form-item>
        <el-form-item label="已出库"><span>{{ $fq(issueReturnForm.delivered_qty) }}</span></el-form-item>
        <el-form-item label="批次号" required>
          <el-select v-model="issueReturnForm.batch_no" placeholder="选择该单出库过的批次" filterable style="width: 100%">
            <el-option v-for="b in issueReturnBatchList" :key="b.batch_no" :label="`${b.batch_no}（已出 ${$fq(b.quantity)}）`" :value="b.batch_no" />
          </el-select>
        </el-form-item>
        <el-form-item label="退回数量" required>
          <el-input type="number" v-model="issueReturnForm.quantity" :min="1" :max="issueReturnMax" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="issueReturnForm.remark" type="textarea" :rows="2" placeholder="退回原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueReturnVisible = false">取消</el-button>
        <el-button type="warning" :loading="issueReturnSubmitting" :disabled="!issueReturnForm.batch_no" @click="handleIssueReturnSubmit">确认退回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../../api/request'

const dataList = ref([])
const loading = ref(false)
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 20 })
const searchForm = reactive({ keyword: '', status: '' })

const issueVisible = ref(false)
const issueSubmitting = ref(false)
const issueBatchList = ref([])
const issueMax = ref(1)
const issueForm = reactive({
  id: null, delivery_no: '', product_id: null, product_name: '', product_code: '',
  notify_qty: 0, delivered_qty: 0, max_issue: 0,
  batch_no: '', quantity: 1, issue_date: '', remark: '',
})

const recordsVisible = ref(false)
const recordsList = ref([])

function statusType(s) {
  if (s === '待出库') return 'warning'
  if (s === '部分出库') return 'warning'
  if (s === '已出库') return 'success'
  if (s === '已退货') return 'danger'
  return 'info'
}

function resetSearch() { searchForm.keyword = ''; searchForm.status = ''; queryParams.page = 1; fetchData() }

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    const res = await request.get('/sales/deliveries/outs', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载失败') } finally { loading.value = false }
}

async function openIssueDialog(row) {
  Object.assign(issueForm, {
    id: row.id, delivery_no: row.delivery_no, product_id: row.product_id,
    product_name: row.product_name, product_code: row.product_code,
    notify_qty: row.notify_qty, delivered_qty: row.delivered_qty, max_issue: row.unout_qty,
    batch_no: '', quantity: 1, issue_date: '', remark: '',
  })
  issueMax.value = Math.max(1, row.unout_qty || 1)
  issueBatchList.value = []
  try {
    const res = await request.get('/inventory/available-batches', { params: { product_id: row.product_id, order_id: null } })
    issueBatchList.value = res.items || []
  } catch { issueBatchList.value = [] }
  issueVisible.value = true
}

function batchLabel(b) {
  let label = `${b.batch_no} (可发${b.available})`
  if (b.locked_qty > 0 && b.owner_order_no) label += ` · ${b.locked_qty}锁定给${b.owner_order_no}`
  return label
}

async function handleIssueSubmit() {
  if (!issueForm.id || !issueForm.batch_no) { ElMessage.warning('请选择批次'); return }
  const qty = Number(issueForm.quantity)
  if (!qty || qty <= 0 || qty > issueForm.max_issue) { ElMessage.warning(`请输入 1~${issueForm.max_issue} 的出库数量`); return }
  issueSubmitting.value = true
  try {
    await request.post(`/sales/deliveries/${issueForm.id}/issue`, {
      batch_no: issueForm.batch_no,
      quantity: qty,
      issue_date: issueForm.issue_date,
      remark: issueForm.remark,
    })
    ElMessage.success('出库成功，库存已扣减')
    issueVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '出库失败') } finally { issueSubmitting.value = false }
}

function showOutRecords(row) {
  recordsList.value = row.out_records || []
  recordsVisible.value = true
}

// ========== 出库退回（红冲撤销出库） ==========
const issueReturnVisible = ref(false)
const issueReturnSubmitting = ref(false)
const issueReturnBatchList = ref([])
const issueReturnMax = ref(1)
const issueReturnForm = reactive({
  id: null, delivery_no: '', product_id: null, product_name: '', product_code: '',
  delivered_qty: 0, batch_no: '', quantity: 1, remark: '',
})

function openIssueReturnDialog(row) {
  Object.assign(issueReturnForm, {
    id: row.id, delivery_no: row.delivery_no, product_id: row.product_id,
    product_name: row.product_name, product_code: row.product_code,
    delivered_qty: row.delivered_qty || 0, batch_no: '', quantity: 1, remark: '',
  })
  issueReturnMax.value = Math.max(1, row.delivered_qty || 1)
  issueReturnBatchList.value = (row.out_records || []).map(r => ({ batch_no: r.batch_no, quantity: r.quantity }))
  issueReturnVisible.value = true
}

async function handleIssueReturnSubmit() {
  if (!issueReturnForm.id || !issueReturnForm.batch_no) { ElMessage.warning('请选择批次'); return }
  const qty = Number(issueReturnForm.quantity)
  if (!qty || qty <= 0 || qty > issueReturnMax.value) { ElMessage.warning(`请输入 1~${issueReturnMax.value} 的退回数量`); return }
  issueReturnSubmitting.value = true
  try {
    await request.post(`/sales/deliveries/${issueReturnForm.id}/issue-return`, {
      batch_no: issueReturnForm.batch_no,
      quantity: qty,
      remark: issueReturnForm.remark,
    })
    ElMessage.success('出库已退回，库存已回补')
    issueReturnVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退回失败') } finally { issueReturnSubmitting.value = false }
}

onMounted(() => { fetchData() })
</script>
