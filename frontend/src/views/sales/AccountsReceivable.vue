<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- 应收账款汇总（上） -->
    <el-card ref="summaryCardRef" :body-style="cardBodyStyle" :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <template #header>
        <div style="display: flex; justify-content: flex-end">
          <el-button size="small" @click="openOrderSettingsRaw">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="tableRef" class="drag-table-summary" :key="columnVersion" :data="summaryList" border stripe v-loading="loading" style="width: 100%" :summary-method="summaryTotal" show-summary @row-click="showDetail" :height="summaryTableHeight + 'px'">
            <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :align="col.align">
              <template #header>
                <el-dropdown trigger="contextmenu" :hide-on-click="false">
                  <span class="col-header-wrap">
                    <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                    {{ col.label }}
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click.stop="openOrderSettingsRaw" style="color: #409eff">列排序...</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
              <template v-if="col.prop === 'customer_name'" #default="{ row }"><span style="color: #409eff; cursor: pointer; font-weight: 500">{{ row.customer_name }}</span></template>
              <template v-else-if="col.prop === 'total_amount'" #default="{ row }">{{ $fm(row.total_amount) }}</template>
              <template v-else-if="col.prop === 'total_collected'" #default="{ row }">{{ $fm(row.total_collected) }}</template>
              <template v-else-if="col.prop === 'balance'" #default="{ row }">
                <span :style="{ color: row.balance < 0 ? '#f56c6c' : '#67c23a' }">{{ $fm(row.balance) }}</span>
              </template>
            </el-table-column>
          </el-table>
    </el-card>

    <!-- 分栏条 -->
    <div class="split-bar" style="flex: none; height: 8px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none" @mousedown="onSplitterDown">
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>

    <!-- 应收账款明细（下，跟随选中客户） -->
    <el-card ref="detailCardRef" :body-style="cardBodyStyle" style="flex: 1; min-height: 140px; display: flex; flexDirection: column; overflow: hidden">
      <template #header>
        <div style="display: flex; justify-content: flex-end">
          <el-button size="small" @click="openCdSettingsRaw">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table class="drag-table-detail" :key="cdColumnVersion" :data="cdList" border stripe v-loading="cdLoading" style="width: 100%" :summary-method="cdTotal" show-summary :height="detailTableHeight + 'px'">
            <el-table-column v-for="col in cdColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :align="col.align">
              <template #header>
                <el-dropdown trigger="contextmenu" :hide-on-click="false">
                  <span class="col-header-wrap">
                    <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                    {{ col.label }}
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click.stop="openCdSettingsRaw" style="color: #409eff">列排序...</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
              <template v-if="col.prop === 'ar_amount'" #default="{ row }">{{ $fm(row.ar_amount) }}</template>
              <template v-else-if="col.prop === 'collected_amount'" #default="{ row }">{{ $fm(row.collected_amount) }}</template>
              <template v-else-if="col.prop === 'balance'" #default="{ row }">
                <span :style="{ color: (row.ar_amount - row.collected_amount) < 0 ? '#f56c6c' : '#67c23a' }">{{ $fm(row.ar_amount - row.collected_amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="center" fixed="right">
              <template #default="{ row }">
                <template v-if="row.is_red">
                  <el-button v-if="(row.ar_amount - row.collected_amount) < -0.01" link type="warning" @click="openRefund(row)">退款</el-button>
                  <el-button v-if="(row.ar_amount - row.collected_amount) < -0.01" link type="danger" @click="openTransfer(row)">核销转移</el-button>
                </template>
                <el-button v-else-if="!row.collection_no" link type="primary" @click="openCollectionByDetail(row)">收款</el-button>
                <el-button v-else link type="success" @click="viewCollection(row)">查看收款单</el-button>
              </template>
            </el-table-column>
          </el-table>
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
        <el-form-item label="结算方式">
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
        <el-descriptions-item label="结算方式">{{ collectionDetail.payment_method }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ collectionDetail.operator }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2"><div style="white-space: pre-wrap">{{ collectionDetail.remark || '-' }}</div></el-descriptions-item>
      </el-descriptions>
      <el-divider>核销明细</el-divider>
      <el-table :data="collectionDetail?.allocations || []" stripe size="small" v-if="collectionDetail?.allocations?.length">
        <el-table-column prop="ar_no" label="应收单号" width="160" sortable />
        <el-table-column label="核销金额" width="120"><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
      </el-table>
      <span v-else style="color: #909399">无核销明细</span>
    </el-dialog>

    <!-- 退款弹窗（红字应收 → 负数收款单）-->
    <el-dialog v-model="refundVisible" title="退款（红字应收）" width="480px" destroy-on-close>
      <el-alert type="warning" :closable="false" title="退款将生成负数收款单并核销红字应收（应退余额向 0 靠拢）。实际退款请线下办理。" />
      <el-form :model="refundForm" label-width="100px">
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
        <el-form-item label="备注"><el-input v-model="refundForm.remark" type="textarea" :rows="2" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundVisible = false">取消</el-button>
        <el-button type="warning" :loading="refundLoading" @click="handleRefund">确认退款</el-button>
      </template>
    </el-dialog>

    <!-- 核销转移弹窗（红字应收 → 同客户正余额应收）-->
    <el-dialog v-model="transferVisible" title="核销转移" width="520px" destroy-on-close>
      <el-alert type="warning" :closable="false" title="把红字应收（应退客户）余额转移到同客户其他应收（货款抵扣）。钱不动，纯账务合并。" />
      <el-form :model="transferForm" label-width="100px">
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
        <el-form-item label="备注"><el-input v-model="transferForm.remark" type="textarea" :rows="2" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="danger" :loading="transferLoading" @click="handleTransfer">确认转移</el-button>
      </template>
    </el-dialog>
    
    <!-- 列排序弹窗 -->
    <ColumnSettingsDialog v-model:visible="orderSettingsVisible" :columns="orderSettingsList" @confirm="confirmOrderSettingsFn" />
    <ColumnSettingsDialog v-model:visible="cdSettingsVisible" :columns="cdSettingsList" @confirm="confirmCdSettingsFn" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { salesApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_ar_summary_columns'
const defaultColumns = [
  { prop: 'customer_name', label: '客户', minWidth: 180 , sortable: true },
  { prop: 'count', label: '应收笔数', width: 80, align: 'center' , sortable: true },
  { prop: 'total_amount', label: '应收金额', width: 130, align: 'right' , sortable: true },
  { prop: 'total_collected', label: '已收金额', width: 130, align: 'right' , sortable: true },
  { prop: 'balance', label: '余额', width: 130, align: 'right' , sortable: true },
]
const { columns, columnVersion, initColumnDrag, settingsVisible: orderSettingsVisible, settingsList: orderSettingsList, openColumnSettings: openOrderSettingsRaw, confirmSettings: confirmOrderSettingsFn, resetSettings: resetOrderSettings } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-summary .el-table__header-wrapper thead tr')

const CD_STORAGE_KEY = 'mazu_ar_detail_columns'
const defaultCdColumns = [
  { prop: 'customer_name', label: '客户', minWidth: 140 , sortable: true },
  { prop: 'ar_date', label: '应收日期', width: 110 , sortable: true },
  { prop: 'ar_no', label: '应收单号', width: 160 , sortable: true },
  { prop: 'ar_amount', label: '应收金额', width: 120, align: 'right' , sortable: true },
  { prop: 'cr_date', label: '收款日期', width: 110 , sortable: true },
  { prop: 'collection_no', label: '收款单号', width: 160 , sortable: true },
  { prop: 'collected_amount', label: '收款金额', width: 120, align: 'right' , sortable: true },
  { prop: 'balance', label: '余额', width: 110, align: 'right' , sortable: true },
]
const { columns: cdColumns, columnVersion: cdColumnVersion, initColumnDrag: initCdColumnDrag, settingsVisible: cdSettingsVisible, settingsList: cdSettingsList, openColumnSettings: openCdSettingsRaw, confirmSettings: confirmCdSettingsFn, resetSettings: resetCdSettings } = useColumnDrag(defaultCdColumns, CD_STORAGE_KEY, '.drag-table-detail .el-table__header-wrapper thead tr')

const activeTab = ref('summary')
const loading = ref(false)
const tableRef = ref(null)
const summaryCardRef = ref(null)
const detailCardRef = ref(null)
const summaryTableHeight = ref(300)
const detailTableHeight = ref(200)
const cardBodyStyle = { flex: '1', minHeight: '0', display: 'flex', flexDirection: 'column', padding: '8px 16px' }
const topHeight = ref(parseInt(localStorage.getItem('mazu_ar_split_height') || '400') || 400)
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
  } catch (e) {} finally { loading.value = false; nextTick(initColumnDrag) }
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
  } finally { cdLoading.value = false; nextTick(initCdColumnDrag) }
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
      amount, amount_fc: amount, currency_id: form.currency_id || 1, exchange_rate: form.exchange_rate || 1,
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
    const res = await salesApi.collections.get(row.collection_id)
    collectionDetail.value = res
    collectionDetailVisible.value = true
  } catch (e) {
    ElMessage.error('加载收款单详情失败')
  }
}

function onSplitterDown(e) {
  const startY = e.clientY
  const startH = topHeight.value
  const onMove = (ev) => {
    topHeight.value = Math.min(Math.max(startH + (ev.clientY - startY), 180), window.innerHeight - 360)
    nextTick(calcSummaryHeight)
    localStorage.setItem('mazu_ar_split_height', String(topHeight.value))
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

function _calcCardTableHeight(card) {
  if (!card) return 200
  const el = card.$el || card
  const body = el.querySelector('.el-card__body')
  return Math.max(120, Math.round((body || el).getBoundingClientRect().height - 16))
}

function calcSummaryHeight() {
  summaryTableHeight.value = _calcCardTableHeight(summaryCardRef.value)
}

function calcDetailHeight() {
  detailTableHeight.value = _calcCardTableHeight(detailCardRef.value)
}

onMounted(() => {
  fetchData()
  nextTick(() => { calcSummaryHeight(); calcDetailHeight() })
  window.addEventListener('resize', () => { calcSummaryHeight(); calcDetailHeight() })
})

// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})
watch(cdColumnVersion, () => {
  nextTick(() => { initCdColumnDrag() })
})

// ===== 退款（红字应收 → 负数收款单）=====
const refundVisible = ref(false)
const refundLoading = ref(false)
const refundForm = reactive({ ar_id: null, ar_no: '', customer_id: null, max_refund: 0, amount: 0, payment_method: '电汇退款', refund_date: '', remark: '' })

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
      currency_id: 1, exchange_rate: 1,
      collection_date: refundForm.refund_date || new Date().toISOString().slice(0, 10),
      payment_method: refundForm.payment_method, remark: refundForm.remark,
      ar_account_id: refundForm.ar_id,
    })
    ElMessage.success('退款成功，红字应收已核销')
    refundVisible.value = false; fetchData(); fetchCD()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退款失败') } finally { refundLoading.value = false }
}

// ===== 核销转移（红字应收 → 同客户正余额应收）=====
const transferVisible = ref(false)
const transferLoading = ref(false)
const transferTargets = ref([])
const transferForm = reactive({ source_ar_id: null, source_ar_no: '', max_amount: 0, target_ar_id: null, amount: 0, remark: '' })

async function openTransfer(row) {
  const balance = (row.ar_amount || 0) - (row.collected_amount || 0)
  transferForm.source_ar_id = row.ar_id
  transferForm.source_ar_no = row.ar_no || ''
  transferForm.max_amount = Math.abs(balance)
  transferForm.target_ar_id = null
  transferForm.amount = transferForm.max_amount
  transferForm.remark = ''
  transferVisible.value = true
  try {
    const res = await salesApi.ar.list({ page: 1, page_size: 100 })
    transferTargets.value = (res.items || []).filter(t => t.customer_id === row.customer_id && (t.balance || 0) > 0.01 && t.id !== row.ar_id)
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
    transferVisible.value = false; fetchData(); fetchCD()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '核销转移失败') } finally { transferLoading.value = false }
}
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
