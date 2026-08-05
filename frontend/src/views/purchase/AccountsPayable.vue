<template>
  <div>
    <!-- 查询条件（整体风格） -->
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <el-form :inline="true">
        <el-form-item label="供应商">
          <el-input v-model="searchKeyword" placeholder="供应商名称" clearable style="width: 220px" @keyup.enter="search" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 汇总 -->
    <el-card style="margin-bottom: 12px">
      <template #header><span style="font-weight: 600">汇总</span></template>
      <el-table :data="summaryList" border stripe size="small" v-loading="loading" style="width: 100%" :summary-method="summaryTotal" show-summary @row-click="showDetail">
        <el-table-column prop="supplier_name" label="供应商" min-width="180">
          <template #default="{ row }"><span style="color: #409eff; cursor: pointer; font-weight: 500">{{ row.supplier_name }}</span></template>
        </el-table-column>
        <el-table-column label="应付笔数" width="80" align="center"><template #default="{ row }">{{ row.count }}</template></el-table-column>
        <el-table-column label="应付金额" width="130" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
        <el-table-column label="已付金额" width="130" align="right"><template #default="{ row }">{{ $fm(row.total_paid) }}</template></el-table-column>
        <el-table-column label="余额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.balance > 0 ? '#e6a23c' : '#67c23a' }">{{ $fm(row.balance) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 明细 -->
    <el-card id="ap-detail-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">明细</span>
          <el-tag v-if="pdFilter" closable type="info" size="small" @close="clearPdFilter">{{ pdFilter }}</el-tag>
        </div>
      </template>
      <el-table :data="paymentDetailList" border stripe size="small" v-loading="pdLoading" style="width: 100%" :summary-method="pdTotal" show-summary>
        <el-table-column prop="supplier_name" label="供应商" min-width="140" />
        <el-table-column prop="ap_date" label="应付日期" width="110" />
        <el-table-column prop="ap_no" label="应付单号" width="160" />
        <el-table-column label="应付金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.ap_amount) }}</template></el-table-column>
        <el-table-column label="付款单号" width="180">
          <template #default="{ row }">
            <div style="display: flex; flex-wrap: wrap; gap: 4px">
              <el-tag v-for="no in (row.payment_nos || '').split(',').map(s => s.trim()).filter(Boolean)" :key="no" size="small" type="info">{{ no }}</el-tag>
              <span v-if="!(row.payment_nos || '').trim()" style="color: #909399">-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="付款金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.paid_amount) }}</template></el-table-column>
        <el-table-column label="余额" width="110" align="right">
          <template #default="{ row }"><span :style="{ color: (row.ap_amount - (row.paid_amount || 0)) > 0 ? '#e6a23c' : '#67c23a' }">{{ $fm(row.ap_amount - (row.paid_amount || 0)) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <!-- 余额 > 0 始终可付款（部分付款后也不隐藏），操作只对应应付单 -->
            <el-button v-if="(row.ap_amount - (row.paid_amount || 0)) > 0.01" link type="primary" @click="openPaymentByDetail(row)">付款</el-button>
            <el-button link type="primary" @click="openApDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 付款弹窗 -->
    <el-dialog v-model="dialogVisible" title="付款" width="500px" destroy-on-close>
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="供应商"><el-input :model-value="form.supplier_name" readonly /></el-form-item>
        <el-form-item label="应付金额"><el-input :model-value="$fm(form.amount)" readonly input-style="font-weight: bold; font-size: 16px; color: #e6a23c" /></el-form-item>
        <el-form-item label="已付金额"><el-input :model-value="$fm(form.paid_amount)" readonly /></el-form-item>
        <el-form-item label="余额"><el-input :model-value="$fm(form.balance)" readonly input-style="color: #e6a23c; font-weight: bold" /></el-form-item>
        <el-form-item label="本次付款" prop="payment_amount">
          <el-input v-model="form.payment_amount" placeholder="请输入付款金额" type="number" min="0" :max="form.balance" />
        </el-form-item>
        <el-form-item label="付款日期"><el-date-picker v-model="form.payment_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" /></el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="form.payment_method" placeholder="请选择" style="width: 100%">
            <el-option label="银行转账" value="银行转账" /><el-option label="现金" value="现金" /><el-option label="承兑汇票" value="承兑汇票" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" style="width: 100%"><el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认付款</el-button>
      </template>
    </el-dialog>

    <!-- 应付详情弹窗（点击「详情」） -->
    <el-dialog v-model="apDetailVisible" :title="`应付详情 — ${apDetail?.ap_no || ''}`" width="720px">
      <template v-if="apDetail">
        <el-descriptions :column="3" border style="margin-bottom: 10px">
          <el-descriptions-item label="供应商" span="2">{{ apDetail.supplier_name }}</el-descriptions-item>
          <el-descriptions-item label="应付日期">{{ apDetail.ap_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="应付金额">{{ $fm(apDetail.ap_amount) }}</el-descriptions-item>
          <el-descriptions-item label="已付金额">{{ $fm(apDetail.paid_amount) }}</el-descriptions-item>
          <el-descriptions-item label="余额">
            <span :style="{ color: apDetail.balance > 0 ? '#e6a23c' : '#67c23a', fontWeight: 'bold' }">{{ $fm(apDetail.balance) }}</span>
          </el-descriptions-item>
        </el-descriptions>
        <el-table :data="apDetailFlows" stripe size="small" style="width: 100%">
          <el-table-column prop="pm_date" label="付款日期" width="110" />
          <el-table-column prop="payment_no" label="付款单号" width="160" />
          <el-table-column label="金额" width="110" align="right">
            <template #default="{ row }">{{ $fm(row.allocated_amount) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="140">
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button v-if="row.payment_id" link type="success" @click="viewPayment(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-dialog>

    <!-- 查看付款单弹窗 -->
    <el-dialog v-model="paymentDetailVisible" title="付款单详情" width="600px">
      <el-descriptions :column="2" border v-if="paymentDetail">
        <el-descriptions-item label="付款单号" span="2">{{ paymentDetail.payment_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ paymentDetail.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="付款日期">{{ paymentDetail.payment_date }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ $fm(paymentDetail.amount) }}</el-descriptions-item>
        <el-descriptions-item label="付款方式">{{ paymentDetail.payment_method }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ paymentDetail.operator }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2"><div style="white-space: pre-wrap">{{ paymentDetail.remark || '-' }}</div></el-descriptions-item>
      </el-descriptions>
      <el-divider>核销明细</el-divider>
      <el-table :data="paymentDetail?.allocations || []" stripe size="small" v-if="paymentDetail?.allocations?.length">
        <el-table-column prop="ap_no" label="应付单号" width="160" />
        <el-table-column label="核销金额" width="120"><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
      </el-table>
      <span v-else style="color: #909399">无核销明细</span>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { purchaseApi } from '../../api/business'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const searchKeyword = ref('')
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const pdLoading = ref(false)
const pdList = ref([])

const paymentDetailVisible = ref(false)
const paymentDetail = ref(null)

// 应付详情弹窗
const apDetailVisible = ref(false)
const apDetail = ref(null)
const apDetailFlows = ref([])

const form = reactive({
  ap_id: null, supplier_name: '', supplier_id: null,
  amount: 0, paid_amount: 0, balance: 0,
  payment_amount: 0, payment_date: '', payment_method: '银行转账', remark: '',
})

const rules = { payment_amount: [{ required: true, message: '请输入付款金额', trigger: 'blur' }] }

// 汇总：按供应商分组（前端过滤）
const summaryList = computed(() => {
  const groups = {}
  list.value.forEach(r => {
    const key = r.supplier_name || '未知'
    if (!groups[key]) groups[key] = { supplier_name: key, count: 0, total_amount: 0, total_paid: 0, balance: 0 }
    groups[key].count++
    groups[key].total_amount += r.amount || 0
    groups[key].total_paid += r.paid_amount || 0
    groups[key].balance += r.balance || 0
  })
  let arr = Object.values(groups)
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    arr = arr.filter(g => g.supplier_name.toLowerCase().includes(kw))
  }
  return arr
})

const pdFilter = ref('')

const paymentDetailList = computed(() => {
  let items = [...pdList.value]
  if (pdFilter.value) {
    const kw = pdFilter.value.toLowerCase()
    items = items.filter(r => (r.supplier_name || '').toLowerCase().includes(kw))
  }
  return items.sort((a, b) => (a.ap_date || '').localeCompare(b.ap_date || ''))
})

function summaryTotal({ columns }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    if (col.property === 'count') sums[i] = summaryList.value.reduce((s, r) => s + r.count, 0)
    else if (col.property === 'total_amount') sums[i] = '¥' + summaryList.value.reduce((s, r) => s + r.total_amount, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.property === 'total_paid') sums[i] = '¥' + summaryList.value.reduce((s, r) => s + r.total_paid, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '余额') sums[i] = '¥' + summaryList.value.reduce((s, r) => s + r.balance, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else sums[i] = ''
  })
  return sums
}

function pdTotal({ columns }) {
  // 明细每行 = 一张应付单（后端已聚合），直接全行合计
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    if (col.label === '应付金额') sums[i] = '¥' + paymentDetailList.value.reduce((s, r) => s + (r.ap_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '付款金额') sums[i] = '¥' + paymentDetailList.value.reduce((s, r) => s + (r.paid_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '余额') sums[i] = '¥' + paymentDetailList.value.reduce((s, r) => s + (r.ap_amount || 0) - (r.paid_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else sums[i] = ''
  })
  return sums
}

async function fetchData() {
  loading.value = true
  try {
    const res = await purchaseApi.ap.list({ page: 1, page_size: 100 })
    list.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

async function fetchPaymentDetails() {
  pdLoading.value = true
  try {
    const res = await purchaseApi.ap.paymentDetail()
    pdList.value = res.items || []
  } finally { pdLoading.value = false }
}

// 查询 / 重置（整体风格）
function search() {
  fetchData()
  fetchPaymentDetails()
}

function resetSearch() {
  searchKeyword.value = ''
  pdFilter.value = ''
  search()
}

// 点击汇总行 → 明细按该供应商过滤并定位
function showDetail(row) {
  pdFilter.value = row.supplier_name
  fetchPaymentDetails()
  const el = document.getElementById('ap-detail-card')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function clearPdFilter() {
  pdFilter.value = ''
}

function openPayment(row) {
  form.ap_id = row.id; form.supplier_name = row.supplier_name
  form.supplier_id = row.supplier_id
  form.amount = row.amount; form.paid_amount = row.paid_amount || 0; form.balance = row.balance || 0
  form.payment_amount = row.balance || 0
  form.payment_date = new Date().toISOString().slice(0, 10)
  form.payment_method = '银行转账'; form.remark = ''
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  const amt = parseFloat(form.payment_amount)
  if (amt <= 0) { ElMessage.warning('付款金额必须大于0'); return }
  if (amt > form.balance) { ElMessage.warning('付款金额不能超过余额'); return }
  submitting.value = true
  try {
    await purchaseApi.payments.create({
      supplier_id: form.supplier_id,
      amount: amt, payment_date: form.payment_date,
      payment_method: form.payment_method, remark: form.remark || '',
      ap_account_ids: form.ap_id,
    })
    ElMessage.success('付款成功')
    dialogVisible.value = false; fetchData(); fetchPaymentDetails()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '付款失败') }
  finally { submitting.value = false }
}

function openPaymentByDetail(row) {
  form.ap_id = row.ap_id
  form.supplier_name = row.supplier_name
  form.supplier_id = row.supplier_id
  form.amount = row.ap_amount
  form.paid_amount = row.paid_amount || 0
  form.balance = (row.ap_amount || 0) - (row.paid_amount || 0)
  form.payment_amount = form.balance
  form.payment_date = new Date().toISOString().slice(0, 10)
  form.payment_method = '银行转账'
  form.remark = ''
  dialogVisible.value = true
}

// 应付详情弹窗：应付汇总信息 + 该应付行级付款核销流水
function openApDetail(row) {
  apDetail.value = {
    ap_no: row.ap_no || '',
    supplier_name: row.supplier_name,
    ap_date: row.ap_date || '',
    ap_amount: row.ap_amount || 0,
    paid_amount: row.paid_amount || 0,
    balance: (row.ap_amount || 0) - (row.paid_amount || 0),
  }
  apDetailFlows.value = row.flows || []
  apDetailVisible.value = true
}

async function viewPayment(row) {
  if (!row.payment_id) return
  try {
    const res = await purchaseApi.payments.get(row.payment_id, row.payment_id)
    paymentDetail.value = res
    paymentDetailVisible.value = true
  } catch {
    ElMessage.error('加载付款单详情失败')
  }
}

onMounted(() => {
  fetchData()
  fetchPaymentDetails()
})
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
