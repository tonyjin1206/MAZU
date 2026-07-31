<template>
  <div>
    <el-card>
      <template #header></template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="汇总" name="summary">
          <el-table :data="summaryList" border stripe v-loading="loading" style="width: 100%" :summary-method="summaryTotal" show-summary @row-click="showDetail">
            <el-table-column prop="customer_name" label="客户" min-width="180">
              <template #default="{ row }"><span style="color: #409eff; cursor: pointer; font-weight: 500">{{ row.customer_name }}</span></template>
            </el-table-column>
            <el-table-column label="应收笔数" width="80" align="center"><template #default="{ row }">{{ row.count }}</template></el-table-column>
            <el-table-column label="应收金额" width="130" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
            <el-table-column label="已收金额" width="130" align="right"><template #default="{ row }">{{ $fm(row.total_collected) }}</template></el-table-column>
            <el-table-column label="余额" width="130" align="right">
              <template #default="{ row }"><span :style="{ color: row.balance > 0 ? '#e6a23c' : '#67c23a' }">{{ $fm(row.balance) }}</span></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="明细" name="detail">
          <el-table :data="cdList" border stripe v-loading="cdLoading" style="width: 100%" :summary-method="cdTotal" show-summary>
            <el-table-column prop="customer_name" label="客户" min-width="140" />
            <el-table-column prop="ar_date" label="应收日期" width="110" />
            <el-table-column prop="ar_no" label="应收单号" width="160" />
            <el-table-column label="应收金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.ar_amount) }}</template></el-table-column>
            <el-table-column prop="cr_date" label="收款日期" width="110" />
            <el-table-column prop="collection_no" label="收款单号" width="160" />
            <el-table-column label="收款金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.collected_amount) }}</template></el-table-column>
            <el-table-column label="余额" width="110" align="right">
              <template #default="{ row }"><span :style="{ color: (row.ar_amount - row.collected_amount) > 0 ? '#e6a23c' : '#67c23a' }">{{ $fm(row.ar_amount - row.collected_amount) }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-if="!row.collection_no" type="primary" size="small" @click="openCollectionByDetail(row)">收款</el-button>
                <el-button v-else type="success" size="small" @click="viewCollection(row)">查看收款单</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

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
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { salesApi } from '../../api/business'

const activeTab = ref('summary')
const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
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

async function fetchData() {
  loading.value = true
  try {
    const res = await salesApi.ar.list({ page: 1, page_size: 100 })
    list.value = res.items || []
    total.value = res.total || 0
  } catch {} finally { loading.value = false }
}

watch(activeTab, (tab) => { if (tab === 'detail') { if (!cdFilter.value) cdFilter.value = ' '; fetchCD() } })

async function fetchCD() {
  if (!cdFilter.value) return
  cdLoading.value = true
  try {
    const res = await salesApi.ar.collectionDetail()
    cdList.value = (res.items || []).filter(r =>
      (r.customer_name || '').toLowerCase().includes(cdFilter.value.toLowerCase())
    )
  } finally { cdLoading.value = false }
}

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
    if (col.label === '应收金额') sums[i] = '¥' + cdList.value.reduce((s, r) => s + (r.ar_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else if (col.label === '收款金额') sums[i] = '¥' + cdList.value.reduce((s, r) => s + (r.collected_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
 else if (col.label === '余额') sums[i] = '¥' + cdList.value.reduce((s, r) => s + (r.ar_amount || 0) - (r.collected_amount || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
    else sums[i] = ''
  })
  return sums
}

function showDetail(row) {
  cdFilter.value = row.customer_name
  activeTab.value = 'detail'
  fetchCD()
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

onMounted(fetchData)
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
