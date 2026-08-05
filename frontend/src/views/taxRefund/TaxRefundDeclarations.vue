<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建退税申报</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="申报单号" clearable style="width: 160px" @keyup.enter="fetchList" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 100px">
            <el-option label="待申报" value="待申报" />
            <el-option label="已申报" value="已申报" />
            <el-option label="已退税" value="已退税" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="list" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column label="申报年月" width="90"><template #default="{ row }">{{ row.period }}</template></el-table-column>
        <el-table-column label="批次" width="60" align="center"><template #default="{ row }">{{ row.batch || 1 }}</template></el-table-column>
        <el-table-column prop="declaration_no" label="申报单号" width="180" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }"><el-tag :type="row.status === '已退税' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="可退税额" width="110" align="right"><template #default="{ row }">{{ $fm(row.refundable_amount) }}</template></el-table-column>
        <el-table-column label="实际退税" width="110" align="right"><template #default="{ row }">{{ $fm(row.actual_refund_amount) }}</template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="150" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待申报'" link type="success" @click="handleSubmitDecl(row)">申报</el-button>
            <el-button v-if="row.status === '已申报'" link type="success" @click="openRefundDialog(row)">已退税</el-button>
            <el-button v-if="row.status === '已申报'" link type="warning" @click="handleCancelSubmit(row)">取消申报</el-button>
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === '待申报'" link type="primary" @click="openEdit(row)">修改</el-button>
            <el-button v-if="row.status === '待申报'" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button v-if="row.status === '已退税'" link type="danger" @click="handleCancelRefund(row)">取消退税</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top: 12px"
        v-model:current-page="page" v-model:page-size="pageSize"
        :total="total" :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList" @size-change="fetchList"
      />
    </el-card>

    <!-- 明细编辑弹窗（新建=草稿模式，点保存才建库） -->
    <el-dialog v-model="editDialog" :title="viewMode ? '退税申报详情 - ' + (currentDeclNo || draftForm.period) : (isNewDraft ? '新建退税申报 - 填好全部内容后点保存' : '退税申报明细编辑 - ' + currentDeclNo)" width="98%" destroy-on-close>
      <template v-if="isNewDraft || currentDecl">
        <el-form :inline="true" :model="draftForm" label-width="88px" style="margin-bottom: 8px">
          <el-form-item label="申报年月">
            <el-input v-model="draftForm.period" :disabled="!isNewDraft" placeholder="YYYYMM" maxlength="6" style="width: 110px" />
          </el-form-item>
          <el-form-item label="批次">
            <el-input-number v-model="draftForm.batch" :min="1" :max="99" :disabled="!isNewDraft" style="width: 110px" />
          </el-form-item>
          <el-form-item label="进项税额">
            <el-input-number v-model="draftForm.input_tax" :min="0" :precision="2" :disabled="viewMode" style="width: 140px" @change="calcPreview" />
          </el-form-item>
          <el-form-item label="内销销项税">
            <el-input-number v-model="draftForm.domestic_tax" :min="0" :precision="2" :disabled="viewMode" style="width: 140px" @change="calcPreview" />
          </el-form-item>
          <el-form-item label="上期留抵">
            <el-input-number v-model="draftForm.last_period_deduction" :min="0" :precision="2" :disabled="viewMode" style="width: 140px" @change="calcPreview" />
          </el-form-item>
        </el-form>
        <el-alert type="info" :closable="false" style="margin-bottom: 10px; padding: 8px 12px">
          <div style="font-size: 12px; line-height: 1.7">
            出口FOB <b>{{ $fm(preview.fob) }}</b> × 退税率 {{ draftForm.refund_rate }}% → 免抵退税额 <b>{{ $fm(preview.refundable) }}</b>
            ｜ 留抵(可退上限) <b>{{ $fm(preview.deduction) }}</b> → <span style="color: #67c23a">实际应退 <b>{{ $fm(preview.actual) }}</b></span>
            ｜ 免抵税额 {{ $fm(preview.exemption) }} ｜ 不得免征抵扣 {{ $fm(preview.nonDeductible) }}
            <div style="color: #909399">应退 = min(留抵, 免抵退税额)；留抵 = 进项税额 − 内销销项 − 不得免征抵扣 − 上期留抵</div>
          </div>
        </el-alert>

        <div style="margin-bottom: 10px">
          <el-button v-if="!viewMode" size="small" type="primary" @click="openInvoiceSelector">+ 添加申报行（发票+报关单）</el-button>
          <el-button v-if="!viewMode" size="small" type="danger" @click="openReturnSelector">＋ 添加退货冲减（负数申报）</el-button>
        </div>

        <el-table :data="draftRows" border stripe size="small" style="width: 100%">
          <el-table-column label="序号" width="80" align="center"><template #default="{ row }">{{ row._seq }}</template></el-table-column>
          <el-table-column label="关联号" width="180"><template #default="{ row }">{{ row.assoc_no || row._assoc_no }}</template></el-table-column>
          <el-table-column label="税种" width="50" align="center"><template #default="{ row }">V</template></el-table-column>
          <el-table-column label="凭证种类" width="140"><template #default="{ row }">{{ row.voucher_type }}</template></el-table-column>
          <el-table-column label="报关单号" width="170">
            <template #default="{ row }">
              <span v-if="row.customs_no" style="color: #409eff">{{ row.customs_no }}</span>
              <span v-else style="color: #c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column label="进货凭证号" width="160"><template #default="{ row }">{{ row.voucher_no }}</template></el-table-column>
          <el-table-column label="供货方税号" width="150"><template #default="{ row }">{{ row.supplier_tax_id }}</template></el-table-column>
          <el-table-column label="开票日期" width="100"><template #default="{ row }">{{ row.invoice_date }}</template></el-table-column>
          <el-table-column label="商品代码" width="110">
            <template #default="{ row, $index }">
              <el-input v-if="!viewMode" v-model="row.product_code" size="small" placeholder="代码" @input="recalcRow($index)" />
              <span v-else>{{ row.product_code }}</span>
            </template>
          </el-table-column>
          <el-table-column label="商品名称" width="150">
            <template #default="{ row, $index }">
              <el-input v-if="!viewMode" v-model="row.product_name" size="small" placeholder="名称" />
              <span v-else>{{ row.product_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="单位" width="70">
            <template #default="{ row, $index }">
              <el-select v-if="!viewMode" v-model="row.unit" size="small" placeholder="单位" style="width: 100%">
                <el-option label="个" value="个" /><el-option label="件" value="件" /><el-option label="套" value="套" />
                <el-option label="kg" value="kg" /><el-option label="米" value="米" /><el-option label="台" value="台" />
              </el-select>
              <span v-else>{{ row.unit }}</span>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="100" align="right">
            <template #default="{ row, $index }">
              <el-input v-if="!viewMode" v-model="row.quantity" type="number" :min="0" size="small" @input="recalcRow($index)" />
              <span v-else>{{ $fq(row.quantity) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="计税金额" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.taxable_amount || 0) < 0 ? '#f56c6c' : '' }">{{ $fm(row.taxable_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="征税率%" width="70" align="center"><template #default="{ row }">{{ row.tax_rate }}</template></el-table-column>
          <el-table-column label="退税率%" width="70" align="center"><template #default="{ row }">{{ row.refund_rate }}</template></el-table-column>
          <el-table-column label="可退税额" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.refundable_amount || 0) < 0 ? '#f56c6c' : '' }">{{ $fm(row.refundable_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" fixed="right">
          <template #default="{ row, $index }">
            <el-button v-if="!viewMode && !row._pendingDelete" link type="danger" size="small" @click="markDeleteRow($index)">删除</el-button>
            <span v-else-if="row._pendingDelete" style="color: #909399">待删除</span>
          </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button @click="editDialog = false">关闭</el-button>
        <el-button v-if="!viewMode" type="primary" :loading="saving" @click="saveRows">保存</el-button>
      </template>
    </el-dialog>

    <!-- 选择进项发票弹窗 -->
    <el-dialog v-model="selectInvoiceDialog" title="选择进项发票" width="700px" destroy-on-close>
      <el-table :data="filteredInvoiceList" stripe border size="small" highlight-current-row @current-change="onInvoiceSelect">
        <el-table-column prop="invoice_no" label="发票号" width="160" />
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column label="金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column label="税额" width="90" align="right"><template #default="{ row }">{{ $fm(row.tax_amount) }}</template></el-table-column>
        <el-table-column label="价税合计" width="110" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
        <el-table-column prop="invoice_date" label="开票日期" width="100" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row._disabled" type="info" size="small">已关联</el-tag>
            <el-tag v-else type="success" size="small">可选</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="selectInvoiceDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedInvoice" @click="confirmSelectInvoice">确认选择</el-button>
      </template>
    </el-dialog>

    <!-- 选择报关单商品行弹窗（出口端，双端匹配第二步） -->
    <el-dialog v-model="selectCustomsDialog" title="选择报关单商品行（出口货物）" width="760px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom: 10px"
        title="已选过/已匹配的报关单商品行不可重复选择；仅已放行/已结关的报关单可选。" />
      <el-table :data="customsItemList" stripe border size="small" highlight-current-row @current-change="onCustomsSelect">
        <el-table-column prop="customs_no" label="报关单号" width="165" />
        <el-table-column prop="product_name" label="商品" min-width="130" />
        <el-table-column prop="hs_code" label="HS编码" width="100" />
        <el-table-column label="数量" width="90" align="right"><template #default="{ row }">{{ $fq(row.export_quantity) }}</template></el-table-column>
        <el-table-column label="FOB金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.declare_amount) }}</template></el-table-column>
        <el-table-column label="退税率%" width="85" align="center"><template #default="{ row }">{{ row.refund_rate }}</template></el-table-column>
        <el-table-column label="状态" width="85">
          <template #default="{ row }">
            <el-tag v-if="row._disabled" type="info" size="small">已选</el-tag>
            <el-tag v-else type="success" size="small">可选</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="selectCustomsDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedCustomsItem" @click="confirmSelectCustoms">确认选择</el-button>
      </template>
    </el-dialog>

    <!-- 选择退货冲减弹窗（已报税退货 → 负数申报） -->
    <el-dialog v-model="returnSelDialog" title="选择退货冲减（已报税退货 → 负数申报）" width="820px" destroy-on-close>
      <el-alert type="warning" :closable="false" style="margin-bottom: 10px"
        title="已报税发货单发生退货后，需在次月申报表做负数申报冲减出口额（负退税结转下期，不产生退税）。" />
      <el-table v-if="returnCandidates.length" :data="returnCandidates" stripe border size="small" highlight-current-row @current-change="onReturnSelect">
        <el-table-column prop="return_no" label="退货单号" width="150" />
        <el-table-column prop="customs_no" label="报关单号" width="160" />
        <el-table-column prop="return_date" label="退货日期" width="100" />
        <el-table-column prop="product_name" label="商品" min-width="120" />
        <el-table-column label="数量" width="90" align="right"><template #default="{ row }"><span style="color: #f56c6c">{{ $fq(row.quantity) }}</span></template></el-table-column>
        <el-table-column label="计税金额" width="110" align="right"><template #default="{ row }"><span style="color: #f56c6c">{{ $fm(row.taxable_amount) }}</span></template></el-table-column>
        <el-table-column label="退税率%" width="80" align="center"><template #default="{ row }">{{ row.refund_rate }}</template></el-table-column>
        <el-table-column label="可退税额" width="110" align="right"><template #default="{ row }"><span style="color: #f56c6c">{{ $fm(row.refundable_amount) }}</span></template></el-table-column>
      </el-table>
      <el-empty v-else description="暂无已报税退货单（退货后会在次月申报自动带出）" :image-size="60" />
      <template #footer>
        <el-button @click="returnSelDialog = false">取消</el-button>
        <el-button type="danger" :disabled="!selectedReturn" :loading="saving" @click="confirmSelectReturn">确认冲减</el-button>
      </template>
    </el-dialog>

    <!-- 退税金额弹窗 -->
    <el-dialog v-model="refundDialog" title="输入实际退税金额" width="400px" destroy-on-close>
      <el-form label-width="120px">
        <el-form-item label="实际退税金额">
          <el-input v-model="refundAmount" type="number" :min="0" :precision="2" placeholder="请输入实际退税金额" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmRefund">确认退税</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taxRefundApi } from '../../api/business'

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const editDialog = ref(false)
const selectInvoiceDialog = ref(false)

// script 内金额格式化（$fm 仅模板可用，script 里用本地实现）
const fmtMoney = (val) => {
  if (val === null || val === undefined || val === '') return '¥0.00'
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return '¥0.00'
  return '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
const currentDeclId = ref(null)
const currentDeclNo = ref('')
const currentDecl = ref(null)
const draftRows = ref([])
const invoiceList = ref([])
const filteredInvoiceList = ref([])
const selectedInvoice = ref(null)
const refundDialog = ref(false)
const refundAmount = ref(0)
const refundTarget = ref(null)
const saving = ref(false)
const viewMode = ref(false)

// 草稿模式：新建申报（未建库）或编辑已有申报
const isNewDraft = computed(() => currentDeclId.value === null)
const draftForm = reactive({
  period: '', batch: 1, input_tax: 0, domestic_tax: 0,
  last_period_deduction: 0, tax_rate: 13, refund_rate: 13,
})

// 出口FOB = 明细行计税金额汇总（负数冲减行计入）
const fobTotal = computed(() =>
  Math.round(draftRows.value.filter(r => !r._pendingDelete)
    .reduce((s, r) => s + (Number(r.taxable_amount) || 0), 0) * 100) / 100)

// 免抵退预览（与后端 calculate_exempt_credit_refund 同公式）
const preview = computed(() => {
  const fob = fobTotal.value
  const taxRate = Number(draftForm.tax_rate) || 13
  const rate = Number(draftForm.refund_rate) || 13
  const inputTax = Number(draftForm.input_tax) || 0
  const domestic = Number(draftForm.domestic_tax) || 0
  const last = Number(draftForm.last_period_deduction) || 0
  const nonDeductible = fob * (taxRate - rate) / 100
  const currentDue = domestic - (inputTax - nonDeductible) - last
  const refundable = fob * rate / 100
  const deduction = Math.max(0, -currentDue)
  let actual = 0, exemption = refundable
  if (deduction > 0) { actual = Math.min(deduction, refundable); exemption = refundable - actual }
  return { fob, nonDeductible, refundable, deduction, actual, exemption }
})
function calcPreview() { /* preview 为 computed，此处仅触发生效 */ }

// 退货冲减（负数申报）
const returnSelDialog = ref(false)
const returnCandidates = ref([])
const selectedReturn = ref(null)

// 搜索过滤
const searchForm = reactive({ keyword: '', status: '', dateRange: null })

function resetSearch() {
  searchForm.keyword = ''; searchForm.status = ''; searchForm.dateRange = null
  page.value = 1; fetchList()
}

onMounted(() => { fetchList(); fetchInvoices() })

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.dateRange) { params.date_from = searchForm.dateRange[0]; params.date_to = searchForm.dateRange[1] }
    const res = await taxRefundApi.declarations.list(params)
    list.value = res.items || []; total.value = res.total || 0
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function fetchInvoices() {
  try {
    const res = await taxRefundApi.inputInvoices.list({ page: 1, page_size: 100 })
    invoiceList.value = res.items || []
  } catch {}
}

function openCreate() {
  const now = new Date()
  currentDeclId.value = null
  currentDecl.value = null
  currentDeclNo.value = ''
  viewMode.value = false
  Object.assign(draftForm, {
    period: String(now.getFullYear()) + String(now.getMonth() + 1).padStart(2, '0'),
    batch: 1, input_tax: 0, domestic_tax: 0, last_period_deduction: 0,
    tax_rate: 13, refund_rate: 13,
  })
  draftRows.value = []
  editDialog.value = true
}

async function openDetail(row) {
  viewMode.value = true
  currentDeclId.value = row.id; currentDeclNo.value = row.declaration_no
  await loadDraft(row.id)
  editDialog.value = true
}

async function openEdit(row) {
  viewMode.value = false
  currentDeclId.value = row.id; currentDeclNo.value = row.declaration_no
  await loadDraft(row.id)
  editDialog.value = true
}

async function loadDraft(id) {
  try {
    const res = await taxRefundApi.declarations.get(id, id)
    currentDecl.value = res
    draftRows.value = (res.rows || []).map(r => ({ ...r, _isNew: false, _pendingDelete: false }))
    Object.assign(draftForm, {
      period: res.period || '', batch: res.batch || 1,
      input_tax: res.input_tax || 0, domestic_tax: res.domestic_tax || 0,
      last_period_deduction: res.last_period_deduction || 0,
      tax_rate: res.tax_rate || 13, refund_rate: res.refund_rate || 13,
    })
  } catch { ElMessage.error('加载申报详情失败') }
}

function closeEdit() {
  if (draftRows.value.some(r => r._isNew || r._pendingDelete)) {
    ElMessageBox.confirm('有未保存的修改，确定放弃？', '提示', { type: 'warning' }).then(() => {
      editDialog.value = false
    }).catch(() => {})
  } else {
    editDialog.value = false
  }
}

async function saveRows() {
  if (!draftForm.period || draftForm.period.length !== 6) { ElMessage.warning('请填写申报年月（YYYYMM）'); return }
  saving.value = true
  try {
    let declId = currentDeclId.value
    // 草稿模式：先建申报表（此时才落库），再存明细行
    if (isNewDraft.value) {
      const declNo = `TS-${draftForm.period}-${String(draftForm.batch || 1).padStart(2, '0')}`
      const res = await taxRefundApi.declarations.create({
        declaration_no: declNo, declare_date: new Date().toISOString().slice(0, 10),
        period: draftForm.period, batch: draftForm.batch || 1,
        domestic_tax: draftForm.domestic_tax || 0, input_tax: draftForm.input_tax || 0,
        last_period_deduction: draftForm.last_period_deduction || 0,
      })
      declId = res.id
      currentDeclId.value = declId
      currentDeclNo.value = declNo
      // 创建后所有行都是新行
      draftRows.value = draftRows.value.map(r => ({ ...r, _isNew: true, id: undefined }))
    } else {
      // 已有申报：更新表头（进项税额/内销销项/上期留抵/退税率）
      await taxRefundApi.declarations.update(currentDeclId.value, {
        domestic_tax: draftForm.domestic_tax || 0, input_tax: draftForm.input_tax || 0,
        last_period_deduction: draftForm.last_period_deduction || 0,
        tax_rate: draftForm.tax_rate || 13, refund_rate: draftForm.refund_rate || 13,
      })
    }
    // 删除标记的行
    for (const row of draftRows.value) {
      if (row._pendingDelete && row.id) {
        await taxRefundApi.declarations.deleteRow(declId, row.id)
      }
    }
    // 保存新行和更新已有行
    const savePromises = draftRows.value
      .filter(r => !r._pendingDelete)
      .map(async (row) => {
        if (row._isNew) {
          // 双端行：进项发票 + 报关单商品行；负数申报行走独立入口
          await taxRefundApi.declarations.addRow(declId, {
            input_invoice_id: row.input_invoice_id || null,
            customs_item_id: row.customs_item_id || null,
            voucher_type: row.voucher_type || '',
            voucher_no: row.voucher_no || '',
            product_code: row.product_code || '',
            product_name: row.product_name || '',
            unit: row.unit || '',
            quantity: row.quantity || 0,
            taxable_amount: row.taxable_amount || 0,
            tax_rate: row.tax_rate || 13,
            refund_rate: row.refund_rate || 13,
          })
        } else if (row.id && !row._isNew) {
          // 更新已有行（商品代码/名称/单位/数量/计税金额等）
          await taxRefundApi.declarations.updateRow(declId, row.id, {
            product_code: row.product_code || '',
            product_name: row.product_name || '',
            unit: row.unit || '',
            quantity: row.quantity || 0,
            taxable_amount: row.taxable_amount || 0,
            tax_rate: row.tax_rate || 13,
            refund_rate: row.refund_rate || 13,
          })
        }
      })
    await Promise.all(savePromises)

    ElMessage.success('保存成功')
    editDialog.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}

function openInvoiceSelector() {
  selectedInvoice.value = null
  const usedIds = new Set(draftRows.value.filter(r => !r._pendingDelete).map(r => r.input_invoice_id).filter(Boolean))
  filteredInvoiceList.value = invoiceList.value.map(inv => ({
    ...inv, _disabled: usedIds.has(inv.id) || inv.refund_match_status === '已匹配'
  }))
  selectInvoiceDialog.value = true
}

function recalcRow(index) {
  const row = draftRows.value[index]
  if (row) {
    const rate = parseFloat(row.refund_rate) || 0
    const amt = parseFloat(row.taxable_amount) || 0
    row.refundable_amount = Math.round(amt * rate / 100 * 100) / 100
  }
}

function onInvoiceSelect(row) {
  if (row && !row._disabled) selectedInvoice.value = row
}

// ===== 双端匹配：选完进项发票 → 选报关单商品行 =====
const selectCustomsDialog = ref(false)
const customsItemList = ref([])
const selectedCustomsItem = ref(null)
const pendingInvoice = ref(null)

async function confirmSelectInvoice() {
  const inv = selectedInvoice.value
  if (!inv) return
  selectInvoiceDialog.value = false
  pendingInvoice.value = inv
  // 第二步：选报关单商品行（出口端，过滤已选）
  const usedItemIds = new Set(draftRows.value.filter(r => !r._pendingDelete).map(r => r.customs_item_id).filter(Boolean))
  try {
    const res = await taxRefundApi.customsForRefund({ page: 1, page_size: 100 })
    customsItemList.value = (res.items || []).map(it => ({
      ...it, _disabled: usedItemIds.has(it.id)
    }))
    selectedCustomsItem.value = null
    selectCustomsDialog.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载报关单商品行失败')
  }
}

function onCustomsSelect(row) {
  if (row && !row._disabled) selectedCustomsItem.value = row
}

async function confirmSelectCustoms() {
  const item = selectedCustomsItem.value
  const inv = pendingInvoice.value
  if (!item || !inv) return
  selectCustomsDialog.value = false
  const now = new Date()
  const rate = parseFloat(item.refund_rate) || 13
  const amt = parseFloat(item.declare_amount) || 0
  draftRows.value.push({
    _isNew: true, _pendingDelete: false,
    input_invoice_id: inv.id,
    invoice_no: inv.invoice_no || '',
    supplier_name: inv.supplier_name || '',
    voucher_type: '增值税专用发票',
    voucher_no: item.customs_no || '',          // 报关单号
    supplier_tax_id: inv.supplier_tax_id || '',
    invoice_date: inv.invoice_date || '',
    product_code: item.product_code || '',
    product_name: item.product_name || '',
    unit: item.unit || '',
    quantity: item.export_quantity || 0,
    taxable_amount: amt,
    tax_rate: 13, refund_rate: rate,
    refundable_amount: Math.round(amt * rate / 100 * 100) / 100,
    customs_item_id: item.id,
    customs_no: item.customs_no || '',
    _seq: String(draftRows.value.length + 1).padStart(8, '0'),
    _assoc_no: currentDecl.value?.period + String(currentDecl.value?.batch || 1).padStart(3, '0') + (draftRows.value.length + 1),
  })
  pendingInvoice.value = null
}

// ===== 退货冲减（负数申报） =====
async function openReturnSelector() {
  selectedReturn.value = null
  try {
    const res = await taxRefundApi.declarations.returnCandidates(currentDeclId.value)
    returnCandidates.value = res.items || []
    returnSelDialog.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载退货冲减候选失败')
  }
}

function onReturnSelect(row) {
  if (row) selectedReturn.value = row
}

async function confirmSelectReturn() {
  const rd = selectedReturn.value
  if (!rd) return
  await ElMessageBox.confirm(
    `确认冲减退货单 ${rd.return_no}？将生成负数明细行（冲减出口额 ${fmtMoney(Math.abs(rd.taxable_amount))}），申报表出口金额自动重算。`,
    '退货冲减确认', { type: 'warning', confirmButtonText: '确认冲减', cancelButtonText: '再想想' }
  )
  saving.value = true
  try {
    const res = await taxRefundApi.declarations.returnAdjustments(currentDeclId.value, {
      delivery_id: rd.delivery_id,
    })
    ElMessage.success(res.message || '退货冲减已添加')
    returnSelDialog.value = false
    await loadDraft(currentDeclId.value)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') } finally { saving.value = false }
}

function markDeleteRow(index) {
  draftRows.value[index]._pendingDelete = true
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除申报 ${row.declaration_no}？`, '提示', { type: 'warning' })
  try {
    await taxRefundApi.declarations.delete(row.id, row.id)
    // 本地立即移除（不依赖刷新时序），再兜底刷新
    list.value = list.value.filter(x => x.id !== row.id)
    total.value = Math.max(0, total.value - 1)
    ElMessage.success('已删除'); fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

async function handleSubmitDecl(row) {
  try {
    await taxRefundApi.declarations.submit(row.id, row.id)
    ElMessage.success('申报成功')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '申报失败') }
}

async function handleCancelSubmit(row) {
  await ElMessageBox.confirm(`确定取消申报 ${row.declaration_no}？申报将返回待申报状态。`, '提示', { type: 'warning' })
  try {
    await taxRefundApi.declarations.cancelSubmit(row.id, row.id)
    ElMessage.success('已取消申报')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

function openRefundDialog(row) {
  refundTarget.value = row
  refundAmount.value = row.refundable_amount || 0
  refundDialog.value = true
}

async function confirmRefund() {
  const amt = parseFloat(refundAmount.value)
  if (amt <= 0) { ElMessage.warning('请输入有效的退税金额'); return }
  try {
    await taxRefundApi.declarations.refund(refundTarget.value.id, refundTarget.value.id)
    ElMessage.success('退税完成')
    refundDialog.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退税失败') }
}

async function handleCancelRefund(row) {
  await ElMessageBox.confirm(`确定取消退税？申报将返回"已申报"状态。`, '提示', { type: 'warning' })
  try {
    await taxRefundApi.declarations.cancelRefund(row.id, row.id)
    ElMessage.success('退税已取消')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>