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
        :total="total" :page-sizes="[50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList" @size-change="fetchList"
      />
    </el-card>

    <!-- 新建申报 -->
    <el-dialog v-model="createDialog" title="新建退税申报" width="400px" destroy-on-close>
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="申报年月"><el-input v-model="createForm.period" placeholder="YYYYMM" maxlength="6" /></el-form-item>
        <el-form-item label="申报批次"><el-input-number v-model="createForm.batch" :min="1" :max="99" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建并编辑明细</el-button>
      </template>
    </el-dialog>

    <!-- 明细编辑弹窗 -->
    <el-dialog v-model="editDialog" :title="viewMode ? '退税申报详情 - ' + currentDeclNo : '退税申报明细编辑 - ' + currentDeclNo" width="98%" destroy-on-close>
      <template v-if="currentDecl">
        <el-descriptions :column="4" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="申报年月">{{ currentDecl.period }}</el-descriptions-item>
          <el-descriptions-item label="批次">{{ currentDecl.batch }}</el-descriptions-item>
          <el-descriptions-item label="申报单号">{{ currentDecl.declaration_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ currentDecl.status }}</el-descriptions-item>
        </el-descriptions>

        <div style="margin-bottom: 10px">
          <el-button v-if="!viewMode" size="small" type="primary" @click="openInvoiceSelector">+ 添加进项发票</el-button>
        </div>

        <el-table :data="draftRows" border stripe size="small" style="width: 100%">
          <el-table-column label="序号" width="80" align="center"><template #default="{ row }">{{ row._seq }}</template></el-table-column>
          <el-table-column label="关联号" width="180"><template #default="{ row }">{{ row.assoc_no || row._assoc_no }}</template></el-table-column>
          <el-table-column label="税种" width="50" align="center"><template #default="{ row }">V</template></el-table-column>
          <el-table-column label="凭证种类" width="140"><template #default="{ row }">{{ row.voucher_type }}</template></el-table-column>
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
          <el-table-column label="计税金额" width="100" align="right"><template #default="{ row }">{{ $fm(row.taxable_amount) }}</template></el-table-column>
          <el-table-column label="征税率%" width="70" align="center"><template #default="{ row }">{{ row.tax_rate }}</template></el-table-column>
          <el-table-column label="退税率%" width="70" align="center"><template #default="{ row }">{{ row.refund_rate }}</template></el-table-column>
          <el-table-column label="可退税额" width="100" align="right"><template #default="{ row }">{{ $fm(row.refundable_amount) }}</template></el-table-column>
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
import request from '../../api/request'

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const createDialog = ref(false)
const editDialog = ref(false)
const selectInvoiceDialog = ref(false)
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

const createForm = reactive({ period: '', batch: 1 })

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
    const res = await request.get('/tax-refund/declarations', { params })
    list.value = res.items || []; total.value = res.total || 0
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function fetchInvoices() {
  try {
    const res = await request.get('/tax-refund/input-invoices', { params: { page: 1, page_size: 100 } })
    invoiceList.value = res.items || []
  } catch {}
}

function openCreate() {
  const now = new Date()
  createForm.period = now.getFullYear() + String(now.getMonth() + 1).padStart(2, '0')
  createForm.batch = 1; createDialog.value = true
}

async function submitCreate() {
  if (!createForm.period || createForm.period.length !== 6) { ElMessage.warning('申报年月格式为 YYYYMM'); return }
  const declNo = `TS-${createForm.period}-${String(createForm.batch).padStart(2, '0')}`
  try {
    const res = await request.post('/tax-refund/declarations', {
      declaration_no: declNo, declare_date: new Date().toISOString().slice(0, 10),
      period: createForm.period, batch: createForm.batch,
      export_amount_fob: 0, domestic_tax: 0, input_tax: 0, last_period_deduction: 0,
    })
    createDialog.value = false
    ElMessage.success('申报已创建')
    fetchList()
    await loadDraft(res.id)
    currentDeclId.value = res.id; currentDeclNo.value = declNo
    editDialog.value = true
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') }
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
    const res = await request.get(`/tax-refund/declarations/${id}`)
    currentDecl.value = res
    draftRows.value = (res.rows || []).map(r => ({ ...r, _isNew: false, _pendingDelete: false }))
  } catch {}
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
  saving.value = true
  try {
    // 删除标记的行
    for (const row of draftRows.value) {
      if (row._pendingDelete && row.id) {
        await request.delete(`/tax-refund/declarations/${currentDeclId.value}/rows/${row.id}`)
      }
    }
    // 保存新行和更新已有行
    const savePromises = draftRows.value
      .filter(r => !r._pendingDelete)
      .map(async (row) => {
        if (row._isNew && row.input_invoice_id) {
          await request.post(`/tax-refund/declarations/${currentDeclId.value}/rows`, {
            input_invoice_id: row.input_invoice_id,
            voucher_type: row.voucher_type || '增值税专用发票',
            product_code: row.product_code || '',
            product_name: row.product_name || '',
            unit: row.unit || '', quantity: row.quantity || 0,
            taxable_amount: row.taxable_amount || 0,
            tax_rate: row.tax_rate || 13, refund_rate: row.refund_rate || 13,
          })
        } else if (row.id && !row._isNew) {
          // 更新已有行（商品代码/名称/单位/数量/计税金额等）
          await request.put(`/tax-refund/declarations/${currentDeclId.value}/rows/${row.id}`, {
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

async function confirmSelectInvoice() {
  const inv = selectedInvoice.value
  if (!inv) return
  selectInvoiceDialog.value = false
  const now = new Date()
  draftRows.value.push({
    _isNew: true, _pendingDelete: false,
    input_invoice_id: inv.id,
    voucher_type: '增值税专用发票',
    voucher_no: inv.invoice_no || '',
    supplier_tax_id: inv.supplier_tax_id || '',
    invoice_date: inv.invoice_date || '',
    product_code: '', product_name: '', unit: '', quantity: 0,
    taxable_amount: inv.amount || 0, tax_rate: 13, refund_rate: 13,
    refundable_amount: Math.round((inv.amount || 0) * 13 / 100 * 100) / 100,
    _seq: String(draftRows.value.length + 1).padStart(8, '0'),
    _assoc_no: currentDecl.value?.period + String(currentDecl.value?.batch || 1).padStart(3, '0') + (draftRows.value.length + 1),
  })
}

function markDeleteRow(index) {
  draftRows.value[index]._pendingDelete = true
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除申报 ${row.declaration_no}？`, '提示', { type: 'warning' })
  try {
    await request.delete(`/tax-refund/declarations/${row.id}`)
    ElMessage.success('已删除'); fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

async function handleSubmitDecl(row) {
  try {
    await request.put(`/tax-refund/declarations/${row.id}/submit`)
    ElMessage.success('申报成功')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '申报失败') }
}

async function handleCancelSubmit(row) {
  await ElMessageBox.confirm(`确定取消申报 ${row.declaration_no}？申报将返回待申报状态。`, '提示', { type: 'warning' })
  try {
    await request.put(`/tax-refund/declarations/${row.id}/cancel-submit`)
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
    await request.put(`/tax-refund/declarations/${refundTarget.value.id}/refund`, { amount: amt })
    ElMessage.success('退税完成')
    refundDialog.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '退税失败') }
}

async function handleCancelRefund(row) {
  await ElMessageBox.confirm(`确定取消退税？申报将返回"已申报"状态。`, '提示', { type: 'warning' })
  try {
    await request.put(`/tax-refund/declarations/${row.id}/cancel-refund`)
    ElMessage.success('退税已取消')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>