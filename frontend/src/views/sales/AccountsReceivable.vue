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
        <el-form-item label="客户">
          <el-input v-model="searchKeyword" placeholder="客户名称" clearable style="width: 220px" @keyup.enter="search" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 汇总 -->
    <el-card style="margin-bottom: 12px">
      <template #header><span style="font-weight: 600">汇总</span></template>
      <el-table :data="summaryList" border stripe size="small" v-loading="loading" style="width: 100%" :summary-method="summaryTotal" show-summary @row-click="showDetail">
        <el-table-column prop="customer_name" label="客户" min-width="180">
          <template #default="{ row }"><span style="color: #409eff; cursor: pointer; font-weight: 500">{{ row.customer_name }}</span></template>
        </el-table-column>
        <el-table-column label="应收笔数" width="80" align="center"><template #default="{ row }">{{ row.count }}</template></el-table-column>
        <el-table-column label="应收金额" width="130" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
        <el-table-column label="已收金额" width="130" align="right"><template #default="{ row }">{{ $fm(row.total_collected) }}</template></el-table-column>
        <el-table-column label="余额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.balance < 0 ? '#f56c6c' : '#67c23a' }">{{ $fm(row.balance) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 明细 -->
    <el-card id="ar-detail-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">明细</span>
          <el-tag v-if="cdFilter" closable type="info" size="small" @close="clearCdFilter">{{ cdFilter }}</el-tag>
        </div>
      </template>
      <el-table :data="collectionDetailList" border stripe size="small" v-loading="cdLoading" style="width: 100%" :summary-method="cdTotal" show-summary>
        <el-table-column prop="customer_name" label="客户" min-width="140" />
        <el-table-column prop="ar_date" label="应收日期" width="110" />
        <el-table-column prop="ar_no" label="应收单号" width="160" />
        <el-table-column label="应收金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.ar_amount) }}</template></el-table-column>
        <el-table-column prop="cr_date" label="收款日期" width="110" />
        <el-table-column prop="collection_no" label="收款单号" width="160" />
        <el-table-column label="收款金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.collected_amount) }}</template></el-table-column>
        <el-table-column label="余额" width="110" align="right">
          <template #default="{ row }">
            <span :style="{ color: (row.ar_amount - row.collected_amount) < 0 ? '#f56c6c' : '#67c23a' }">{{ $fm(row.ar_amount - row.collected_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <template v-if="row.ar_amount < 0">
              <!-- 红字应收（应退客户）：退款 / 核销转移 -->
              <el-button type="warning" size="small" @click="openRefund(row)">退款</el-button>
              <el-button type="danger" size="small" @click="openTransfer(row)">核销转移</el-button>
            </template>
            <template v-else>
              <el-button v-if="!row.collection_no" type="primary" size="small" @click="openCollectionByDetail(row)">收款</el-button>
              <el-button v-else type="success" size="small" @click="viewCollection(row)">查看收款单</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 收款弹窗 -->
    <el-dialog v-model="dialogVisible" title="收款" width="500px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户"><el-input :model-value="form.customer_name" disabled /></el-form-item>
        <el-form-item label="应收金额"><el-input :model-value="$fm(form.amount)" readonly /></el-form-item>
        <el-form-item label="已收金额"><el-input :model-value="$fm(form.collected_amount)" readonly /></el-form-item>
        <el-form-item label="可收金额"><el-input :model-value="$fm(form.balance)" readonly input-style="color: #e6a23c; font-weight: bold" /></el-form-item>
        <el-form-item label="本次收款" prop="collection_amount">
          <el-input v-model="form.collection_amount" placeholder="请输入收款金额" type="number" min="0" :max="form.balance" />
        </el-form-item>
        <el-form-item label="收款日期"><el-date-picker v-model="form.collection_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" /></el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="form.payment_method" placeholder="请选择" style="width: 100%">
            <el-option label="银行转账" value="银行转账" /><el-option label="现金" value="现金" /><el-option label="承兑汇票" value="承兑汇票" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" style="width: 100%"><el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认收款</el-button>
      </template>
    </el-dialog>

    <!-- 退款弹窗（红字应收 → 负数收款单） -->
    <el-dialog v-model="refundVisible" title="退款（红字应收）" width="480px" destroy-on-close>
      <el-alert type="warning" :closable="false" style="margin-bottom: 10px"
        title="退款将生成负数收款单并核销红字应收（应退余额向 0 靠拢）。实际退款请线下办理。" />
      <el-form label-width="110px">
        <el-form-item label="红字应收单"><span>{{ refundForm.ar_no }}</span></el-form-item>
        <el-form-item label="应退余额"><span style="color: #f56c6c; font-weight: bold">{{ $fm(refundForm.max_refund) }}</span></el-form-item>
        <el-form-item label="退款金额" required>
          <el-input v-model="refundForm.amount" type="number" :min="0.01" :max="refundForm.max_refund" style="width: 100%" />
        </el-form-item>
        <el-form-item label="退款方式">
          <el-select v-model="refundForm.payment_method" style="width: 100%">
            <el-option label="电汇退款" value="电汇退款" /><el-option label="银行转账" value="银行转账" /><el-option label="现金" value="现金" />
          </el-select>
        </el-form-item>
        <el-form-item label="退款日期">
          <el-date-picker v-model="refundForm.refund_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="refundForm.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundVisible = false">取消</el-button>
        <el-button type="warning" :loading="refundLoading" @click="handleRefund">确认退款</el-button>
      </template>
    </el-dialog>

    <!-- 核销转移弹窗（红字应收 → 同客户正余额应收） -->
    <el-dialog v-model="transferVisible" title="核销转移" width="520px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom: 10px"
        title="把红字应收（应退客户）余额转移到同客户其他应收（货款抵扣）。钱不动，纯账务合并。" />
      <el-form label-width="110px">
        <el-form-item label="源应收（红字）"><span style="color: #f56c6c">{{ transferForm.source_ar_no }}</span></el-form-item>
        <el-form-item label="可转移余额"><span style="color: #f56c6c; font-weight: bold">{{ $fm(transferForm.max_amount) }}</span></el-form-item>
        <el-form-item label="目标应收" required>
          <el-select v-model="transferForm.target_ar_id" filterable placeholder="选择同客户正余额应收" style="width: 100%">
            <el-option v-for="t in transferTargets" :key="t.id" :label="`${t.ar_no}（余额 ${$fm(t.balance)}）`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="转移金额" required>
          <el-input v-model="transferForm.amount" type="number" :min="0.01" :max="transferForm.max_amount" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="transferForm.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="danger" :loading="transferLoading" @click="handleTransfer">确认转移</el-button>
      </template>
    </el-dialog>

    <!-- 查看收款单弹窗 -->
    <el-dialog v-model="collectionDetailVisible" title="收款单详情" width="600px">
      <el-descriptions :column="2" border v-if="collectionDetail">
        <el-descriptions-item label="收款单号" span="2">{{ collectionDetail.collection_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ collectionDetail.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="收款日期">{{ collectionDetail.collection_date }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ $fm(collectionDetail.amount) }}</el-descriptions-item>
        <el-descriptions-item label="付款方式">{{ collectionDetail.payment_method }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ collectionDetail.operator }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2"><div style="white-space: pre-wrap">{{ collectionDetail.remark || '-' }}</div></el-descriptions-item>
      </el-descriptions>
      <el-divider>核销明细</el-divider>
      <el-table :data="collectionDetail?.allocations || []" stripe size="small" v-if="collectionDetail?.allocations?.length">
        <el-table-column prop="ar_no" label="应收单号" width="160" />
        <el-table-column label="核销金额" width="120"><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
      </el-table>
      <span v-else style="color: #909399">无核销明细</span>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { salesApi } from '../../api/business'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const searchKeyword = ref('')
const dialogVisible = ref(false)
const submitting = ref(false)

const cdLoading = ref(false)
const cdList = ref([])
const cdFilter = ref('')

const collectionDetailVisible = ref(false)
const collectionDetail = ref(null)

const form = reactive({
  ar_id: null, customer_id: null, customer_name: '', amount: 0,
  collected_amount: 0, balance: 0, collection_amount: 0,
  collection_date: '', payment_method: '银行转账', remark: '',
})

// 汇总：按客户分组（前端过滤）
const summaryList = computed(() => {
  const groups = {}
  list.value.forEach(r => {
    const key = r.customer_name || '未知'
    if (!groups[key]) groups[key] = { customer_name: key, count: 0, total_amount: 0, total_collected: 0, balance: 0 }
    groups[key].count++; groups[key].total_amount += r.amount || 0
    groups[key].total_collected += r.collected_amount || 0; groups[key].balance += r.balance || 0
  })
  let arr = Object.values(groups)
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    arr = arr.filter(g => g.customer_name.toLowerCase().includes(kw))
  }
  return arr
})

// 明细：全量拉取，前端按 cdFilter 过滤
const collectionDetailList = computed(() => {
  let items = [...cdList.value]
  if (cdFilter.value) {
    const kw = cdFilter.value.toLowerCase()
    items = items.filter(r => (r.customer_name || '').toLowerCase().includes(kw))
  }
  return items.sort((a, b) => (a.ar_date || '').localeCompare(b.ar_date || ''))
})

function summaryTotal({ columns }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    if (col.property === 'count') sums[i] = summaryList.value.reduce((s, r) => s + r.count, 0)
    else if (col.label === '应收金额') sums[i] = '¥' + summaryList.value.reduce((s, r) => s + r.total_amount, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '已收金额') sums[i] = '¥' + summaryList.value.reduce((s, r) => s + r.total_collected, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '余额') sums[i] = '¥' + summaryList.value.reduce((s, r) => s + r.balance, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else sums[i] = ''
  })
  return sums
}

function cdTotal({ columns }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    if (col.label === '应收金额') sums[i] = '¥' + collectionDetailList.value.reduce((s, r) => s + (r.ar_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '收款金额') sums[i] = '¥' + collectionDetailList.value.reduce((s, r) => s + (r.collected_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '余额') sums[i] = '¥' + collectionDetailList.value.reduce((s, r) => s + (r.ar_amount || 0) - (r.collected_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else sums[i] = ''
  })
  return sums
}

async function fetchData() {
  loading.value = true
  try {
    const res = await salesApi.ar.list({ page: 1, page_size: 100 })
    list.value = res.items || []
    total.value = res.total || 0
  } catch {} finally { loading.value = false }
}

async function fetchCD() {
  cdLoading.value = true
  try {
    const res = await salesApi.ar.collectionDetail()
    cdList.value = res.items || []
  } finally { cdLoading.value = false }
}

// 查询 / 重置（整体风格）
function search() {
  fetchData()
  fetchCD()
}

function resetSearch() {
  searchKeyword.value = ''
  cdFilter.value = ''
  search()
}

// 点击汇总行 → 明细按该客户过滤并定位
function showDetail(row) {
  cdFilter.value = row.customer_name
  fetchCD()
  const el = document.getElementById('ar-detail-card')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function clearCdFilter() {
  cdFilter.value = ''
}

function openCollection(row) {
  form.ar_id = row.id; form.customer_name = row.customer_name
  form.customer_id = row.customer_id
  form.amount = row.amount; form.collected_amount = row.collected_amount || 0; form.balance = row.balance
  form.collection_amount = row.balance
  form.collection_date = ''; form.payment_method = '银行转账'; form.remark = ''
  dialogVisible.value = true
}

async function handleSubmit() {
  const amount = parseFloat(form.collection_amount)
  if (!amount || amount <= 0) { ElMessage.warning('请输入有效金额'); return }
  if (amount > form.balance) { ElMessage.warning('收款金额不能超过余额'); return }
  submitting.value = true
  try {
    await salesApi.collections.create({
      customer_id: form.customer_id,
      amount, amount_fc: amount, currency_id: 2, exchange_rate: 7.2,
      collection_date: form.collection_date || new Date().toISOString().slice(0, 10),
      payment_method: form.payment_method, remark: form.remark,
      ar_account_id: form.ar_id,
    })
    ElMessage.success('收款成功'); dialogVisible.value = false; fetchData(); fetchCD()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '收款失败') } finally { submitting.value = false }
}

function openCollectionByDetail(row) {
  form.ar_id = row.ar_id
  form.customer_name = row.customer_name
  form.customer_id = row.customer_id
  form.amount = row.ar_amount
  form.collected_amount = row.collected_amount || 0
  form.balance = (row.ar_amount || 0) - (row.collected_amount || 0)
  form.collection_amount = form.balance
  form.collection_date = new Date().toISOString().slice(0, 10)
  form.payment_method = '银行转账'
  form.remark = ''
  dialogVisible.value = true
}

async function viewCollection(row) {
  if (!row.collection_id) return
  try {
    const res = await salesApi.collections.get(row.collection_id, row.collection_id)
    collectionDetail.value = res
    collectionDetailVisible.value = true
  } catch {
    ElMessage.error('加载收款单详情失败')
  }
}

// ===== 退款（红字应收 → 负数收款单） =====
const refundVisible = ref(false)
const refundLoading = ref(false)
const refundForm = reactive({
  ar_id: null, ar_no: '', customer_id: null, max_refund: 0,
  amount: 0, payment_method: '电汇退款', refund_date: '', remark: '',
})

function openRefund(row) {
  const balance = (row.ar_amount || 0) - (row.collected_amount || 0)
  refundForm.ar_id = row.ar_id
  refundForm.ar_no = row.ar_no || ''
  refundForm.customer_id = row.customer_id
  refundForm.max_refund = Math.abs(balance)
  refundForm.amount = refundForm.max_refund
  refundForm.payment_method = '电汇退款'
  refundForm.refund_date = new Date().toISOString().slice(0, 10)
  refundForm.remark = ''
  refundVisible.value = true
}

async function handleRefund() {
  const amount = parseFloat(refundForm.amount)
  if (!amount || amount <= 0) { ElMessage.warning('请输入有效退款金额'); return }
  if (amount > refundForm.max_refund + 0.01) { ElMessage.warning('退款金额不能超过应退余额'); return }
  refundLoading.value = true
  try {
    await salesApi.collections.create({
      customer_id: refundForm.customer_id,
      amount: -amount, amount_fc: -amount,
      collection_date: refundForm.refund_date || new Date().toISOString().slice(0, 10),
      payment_method: refundForm.payment_method, remark: refundForm.remark,
      ar_account_id: refundForm.ar_id,
    })
    ElMessage.success(`退款登记成功（${$fm(amount)}）`)
    refundVisible.value = false
    fetchData(); fetchCD()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退款失败') } finally { refundLoading.value = false }
}

// ===== 核销转移（红字应收 → 同客户正余额应收） =====
const transferVisible = ref(false)
const transferLoading = ref(false)
const transferTargets = ref([])
const transferForm = reactive({
  source_ar_id: null, source_ar_no: '', max_amount: 0,
  target_ar_id: null, amount: 0, remark: '',
})

async function openTransfer(row) {
  const balance = (row.ar_amount || 0) - (row.collected_amount || 0)
  transferForm.source_ar_id = row.ar_id
  transferForm.source_ar_no = row.ar_no || ''
  transferForm.max_amount = Math.abs(balance)
  transferForm.target_ar_id = null
  transferForm.amount = Math.min(transferForm.max_amount, 1)
  transferForm.remark = ''
  transferVisible.value = true
  // 加载同客户正余额应收作为目标
  try {
    const res = await salesApi.ar.list({ page: 1, page_size: 100 })
    transferTargets.value = (res.items || []).filter(t =>
      t.customer_id === row.customer_id && (t.balance || 0) > 0.01 && t.id !== row.ar_id
    )
  } catch { transferTargets.value = [] }
}

async function handleTransfer() {
  const amount = parseFloat(transferForm.amount)
  if (!transferForm.target_ar_id) { ElMessage.warning('请选择目标应收'); return }
  if (!amount || amount <= 0) { ElMessage.warning('请输入有效转移金额'); return }
  if (amount > transferForm.max_amount + 0.01) { ElMessage.warning('转移金额超过可转移余额'); return }
  transferLoading.value = true
  try {
    const res = await salesApi.ar.transfer({
      source_ar_id: transferForm.source_ar_id,
      target_ar_id: transferForm.target_ar_id,
      amount, remark: transferForm.remark,
    })
    ElMessage.success(res.message || '核销转移成功')
    transferVisible.value = false
    fetchData(); fetchCD()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '核销转移失败') } finally { transferLoading.value = false }
}

onMounted(() => {
  fetchData()
  fetchCD()
})
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
