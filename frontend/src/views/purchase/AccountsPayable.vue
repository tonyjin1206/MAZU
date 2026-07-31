<template>
  <div>
    <el-card>
      <template #header></template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="汇总" name="summary">
          <el-form :inline="true" style="margin-bottom: 12px">
            <el-form-item label="供应商">
              <el-input v-model="searchKeyword" placeholder="输入供应商名称查询" clearable style="width: 260px" @input="filterSummary" />
            </el-form-item>
          </el-form>
          <el-table class="drag-table-summary" :key="columnVersion" :data="summaryList" border stripe v-loading="loading" style="width: 100%" :summary-method="summaryTotal" show-summary @row-click="showDetail">
            <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :align="col.align">
              <template #header>
                <span class="col-header-wrap">
                  <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                  {{ col.label }}
                </span>
              </template>
              <template v-if="col.prop === 'supplier_name'" #default="{ row }"><span style="color: #409eff; cursor: pointer; font-weight: 500">{{ row.supplier_name }}</span></template>
              <template v-else-if="col.prop === 'total_amount'" #default="{ row }">{{ $fm(row.total_amount) }}</template>
              <template v-else-if="col.prop === 'total_paid'" #default="{ row }">{{ $fm(row.total_paid) }}</template>
              <template v-else-if="col.prop === 'balance'" #default="{ row }">
                <span :style="{ color: row.balance > 0 ? '#e6a23c' : '#67c23a' }">{{ $fm(row.balance) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="明细" name="detail">
          <el-table class="drag-table-detail" :key="pdColumnVersion" :data="paymentDetailList" border stripe v-loading="pdLoading" style="width: 100%" :summary-method="pdTotal" show-summary>
            <el-table-column v-for="col in pdColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :align="col.align">
              <template #header>
                <span class="col-header-wrap">
                  <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                  {{ col.label }}
                </span>
              </template>
              <template v-if="col.prop === 'ap_amount'" #default="{ row }">{{ $fm(row.ap_amount) }}</template>
              <template v-else-if="col.prop === 'paid_amount'" #default="{ row }">{{ $fm(row.paid_amount) }}</template>
              <template v-else-if="col.prop === 'balance'" #default="{ row }">
                <span :style="{ color: (row.ap_amount - row.paid_amount) > 0 ? '#e6a23c' : '#67c23a' }">{{ $fm(row.ap_amount - row.paid_amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-if="!row.payment_no" type="primary" size="small" @click="openPaymentByDetail(row)">付款</el-button>
                <el-button v-else type="success" size="small" @click="viewPayment(row)">查看付款单</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
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
import { ref, reactive, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import request from '../../api/request'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_ap_summary_columns'
const defaultColumns = [
  { prop: 'supplier_name', label: '供应商', minWidth: 180 },
  { prop: 'count', label: '应付笔数', width: 80, align: 'center' },
  { prop: 'total_amount', label: '应付金额', width: 130, align: 'right' },
  { prop: 'total_paid', label: '已付金额', width: 130, align: 'right' },
  { prop: 'balance', label: '余额', width: 130, align: 'right' },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-summary .el-table__header-wrapper thead tr')

const PD_STORAGE_KEY = 'mazu_ap_detail_columns'
const defaultPdColumns = [
  { prop: 'supplier_name', label: '供应商', minWidth: 140 },
  { prop: 'ap_date', label: '应付日期', width: 110 },
  { prop: 'ap_no', label: '应付单号', width: 160 },
  { prop: 'ap_amount', label: '应付金额', width: 120, align: 'right' },
  { prop: 'pm_date', label: '付款日期', width: 110 },
  { prop: 'payment_no', label: '付款单号', width: 160 },
  { prop: 'paid_amount', label: '付款金额', width: 120, align: 'right' },
  { prop: 'balance', label: '余额', width: 110, align: 'right' },
]
const { columns: pdColumns, columnVersion: pdColumnVersion, initColumnDrag: initPdColumnDrag } = useColumnDrag(defaultPdColumns, PD_STORAGE_KEY, '.drag-table-detail .el-table__header-wrapper thead tr')

const activeTab = ref('summary')
const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const searchKeyword = ref('')
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const pdLoading = ref(false)
const pdList = ref([])

const paymentDetailVisible = ref(false)
const paymentDetail = ref(null)

const form = reactive({
  ap_id: null, supplier_name: '', supplier_id: null,
  amount: 0, paid_amount: 0, balance: 0,
  payment_amount: 0, payment_date: '', payment_method: '银行转账', remark: '',
})

const rules = { payment_amount: [{ required: true, message: '请输入付款金额', trigger: 'blur' }] }

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
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    if (col.label === '应付金额') sums[i] = '¥' + pdList.value.reduce((s, r) => s + (r.ap_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '付款金额') sums[i] = '¥' + pdList.value.reduce((s, r) => s + (r.paid_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
 else if (col.label === '余额') sums[i] = '¥' + pdList.value.reduce((s, r) => s + (r.ap_amount || 0) - (r.paid_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else sums[i] = ''
  })
  return sums
}

function filterSummary() {} // computed handles it

function showDetail(row) {
  pdFilter.value = row.supplier_name
  activeTab.value = 'detail'
  fetchPaymentDetails()
}

async function fetchData() {
  loading.value = true
  try {
    const res = await request.get('/purchase/ap', { params: { page: 1, page_size: 100 } })
    list.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false; nextTick(initColumnDrag) }
}

watch(activeTab, (tab) => { if (tab === 'detail') { if (!pdFilter.value) pdFilter.value = ' '; fetchPaymentDetails() } })

async function fetchPaymentDetails() {
  pdLoading.value = true
  try {
    const res = await request.get('/purchase/ap/payment-detail')
    pdList.value = res.items || []
  } finally { pdLoading.value = false; nextTick(initPdColumnDrag) }
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
    await request.post('/purchase/payments', {
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

async function viewPayment(row) {
  if (!row.payment_id) return
  try {
    const res = await request.get(`/purchase/payments/${row.payment_id}`)
    paymentDetail.value = res
    paymentDetailVisible.value = true
  } catch {
    ElMessage.error('加载付款单详情失败')
  }
}

onMounted(fetchData)
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>