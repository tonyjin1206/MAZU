<template>
  <TablePageLayout>
    <!-- 搜索栏 -->
    <template #search>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建发票</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="客户/发票号">
          <el-input v-model="searchForm.keyword" placeholder="客户名称/发票号" clearable style="width: 160px" @keyup.enter="fetchList" />
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
        <el-form-item label="金额范围">
          <el-input v-model="searchForm.amountMin" placeholder="最小" type="number" style="width: 100px" />
          <span style="margin: 0 6px">~</span>
          <el-input v-model="searchForm.amountMax" placeholder="最大" type="number" style="width: 100px" />
        </el-form-item>
      </el-form>
    </el-card>
    </template>

    <!-- 列表 -->
    <template #header>
      <div style="display: flex; justify-content: flex-end">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
    </template>
    <template #default="{ height }">
      <el-table ref="tableRef" :key="columnVersion" :data="list" v-loading="loading" stripe border size="small" :height="height">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align" :show-overflow-tooltip="col.prop === 'remark'">
          <template #header>
                <el-dropdown trigger="contextmenu" :hide-on-click="false">
                  <span class="col-header-wrap">
                    <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                    {{ col.label }}
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click.stop="openColumnSettings" style="color: #409eff">列排序...</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
          <template v-if="col.prop === 'amount'" #default="{ row }">
            <span :style="{ color: row.is_red ? '#f56c6c' : '' }">{{ $fm(row.amount) }}</span>
          </template>
          <template v-else-if="col.prop === 'tax_amount'" #default="{ row }">
            <span :style="{ color: row.is_red ? '#f56c6c' : '' }">{{ $fm(row.tax_amount) }}</span>
          </template>
          <template v-else-if="col.prop === 'total_amount'" #default="{ row }">
            <span :style="{ color: row.is_red ? '#f56c6c' : '' }">{{ $fm(row.total_amount) }}</span>
          </template>
          <template v-else-if="col.prop === 'red_of_invoice_no'" #default="{ row }">
            <span v-if="row.is_red && row.red_of_invoice_no" style="color: #f56c6c">{{ row.red_of_invoice_no }}</span>
            <span v-else style="color: #909399">-</span>
          </template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <template v-if="!row.is_red">
              <el-button v-if="row.status !== '已红冲'" link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="row.status === '已开票'" link type="danger" @click="openRedReverse(row)">红冲</el-button>
              <el-button v-if="row.status !== '已红冲'" link type="danger" @click="handleDelete(row)">删除</el-button>
              <el-tag v-else-if="row.status === '已红冲'" size="small" type="info">已红冲</el-tag>
            </template>
            <el-tag v-else size="small" type="danger">红字</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </template>
    <template #footer>
      <el-pagination
        style="margin-top: 12px; flex: none"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="fetchList"
      />
    </template>

    <template #dialog>
    <!-- 新建弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editMode ? '编辑发票' : '新建发票'" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="客户" prop="customer_id">
          <el-select v-model="form.customer_id" placeholder="请选择客户" filterable style="width: 100%" :disabled="editMode" @change="onCustomerChange">
            <el-option v-for="c in customerList" :key="c.id" :label="`${c.code} - ${c.name_cn || c.name}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="销售订单" prop="sales_order_id">
          <el-select v-model="form.sales_order_id" placeholder="请选择销售订单" filterable style="width: 100%" :disabled="editMode" @change="onOrderChange">
            <el-option v-for="o in orderList" :key="o.id" :label="`${o.order_no} - ${o.customer_name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedOrderUninvoiced > 0" label="未开票金额">
          <span style="color: #e6a23c; font-weight: bold; font-size: 16px">{{ $fm(selectedOrderUninvoiced) }}</span>
        </el-form-item>
        <el-form-item label="发票号" prop="invoice_no">
          <el-input v-model="form.invoice_no" placeholder="请输入发票号" :disabled="editMode" />
        </el-form-item>
        <el-form-item label="含税金额" prop="total_amount">
          <el-input type="number" v-model="form.total_amount" :min="0" :precision="2" style="width: 100%" @change="calcAmount" />
        </el-form-item>
        <el-form-item label="税率(%)" prop="tax_rate">
          <el-input type="number" v-model="form.tax_rate" :min="0" :max="100" :step="1" style="width: 120px" @change="calcAmount" />
        </el-form-item>
        <el-form-item label="税额">
          <el-input type="number" v-model="form.tax_amount" :min="0" :precision="2" style="width: 100%" readonly />
        </el-form-item>
        <el-form-item label="不含税金额">
          <span style="color: #409eff; font-size: 18px; font-weight: bold">
            {{ $fm(form.amount) }}
          </span>
        </el-form-item>
        <el-form-item label="发票日期" prop="invoice_date">
          <el-date-picker v-model="form.invoice_date" type="date" value-format="YYYY-MM-DD" placeholder="请选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 红冲弹窗（全额红冲）-->
    <el-dialog v-model="redVisible" title="发票红冲" width="520px" destroy-on-close>
      <el-alert type="warning" :closable="false" title="全额红冲：红字发票金额固定为原发票全额负数，不可修改。红冲后原发票标记「已红冲」，系统自动生成等额红字应收。" />
      <el-form :model="redForm" label-width="110px">
        <el-form-item label="原发票号"><span>{{ redForm.orig_invoice_no }}</span></el-form-item>
        <el-form-item label="原发票金额"><span>{{ $fm(redForm.orig_total) }}</span></el-form-item>
        <el-form-item label="红字票号" required>
          <el-input v-model="redForm.invoice_no" placeholder="从开票系统抄录的红字发票号" style="width: 100%" />
        </el-form-item>
        <el-form-item label="红字金额">
          <span style="color: #f56c6c; font-weight: bold">{{ $fm(-redForm.orig_total) }}</span>
        </el-form-item>
        <el-form-item label="红冲日期" required>
          <el-date-picker v-model="redForm.invoice_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="redForm.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="redVisible = false">取消</el-button>
        <el-button type="danger" :loading="redLoading" :disabled="!redForm.invoice_no" @click="handleRedReverse">确认红冲</el-button>
      </template>
    </el-dialog>
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsListDlg" @confirm="confirmSettings" />
    </template>
  </TablePageLayout>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import TablePageLayout from '../../components/TablePageLayout.vue'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { salesApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_sales_invoice_columns'
const defaultColumns = [
  { prop: 'invoice_no', label: '发票号', width: 160, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 150, sortable: true },
  { prop: 'order_no', label: '订单号', width: 140, sortable: true },
  { prop: 'amount', label: '不含税金额', width: 120, align: 'right', sortable: true },
  { prop: 'tax_amount', label: '税额', width: 100, align: 'right', sortable: true },
  { prop: 'total_amount', label: '价税合计', width: 120, align: 'right', sortable: true },
  { prop: 'red_of_invoice_no', label: '红冲发票号码', width: 150, sortable: true },
  { prop: 'invoice_date', label: '发票日期', width: 120, sortable: true },
  { prop: 'status', label: '状态', width: 100, sortable: true },
  { prop: 'remark', label: '备注', minWidth: 150, sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList: settingsListDlg, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const tableRef = ref(null)
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editMode = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const page = ref(1)
const pageSize = ref(100)
const total = ref(0)

// 搜索条件
const searchForm = reactive({
  keyword: '', dateRange: null, amountMin: '', amountMax: '', status: '',
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.amountMin = ''; searchForm.amountMax = ''; searchForm.status = ''
  page.value = 1
  fetchList()
}

const customerList = ref([])
const orderList = ref([])
const selectedOrderUninvoiced = ref(0)

const form = reactive({
  customer_id: null,
  sales_order_id: null,
  invoice_no: '',
  amount: 0,
  tax_rate: 13,
  tax_amount: 0,
  total_amount: 0,
  invoice_date: '',
  remark: '',
})

const rules = {
  customer_id: [{ required: true, message: '请选择客户', trigger: 'change' }],
  sales_order_id: [{ required: true, message: '请选择销售订单', trigger: 'change' }],
  invoice_no: [{ required: true, message: '请输入发票号', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
  invoice_date: [{ required: true, message: '请选择发票日期', trigger: 'change' }],
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(() => {
  fetchList()
  fetchCustomers()
  fetchOrders()
})

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) {
      params.date_from = searchForm.dateRange[0]
      params.date_to = searchForm.dateRange[1]
    }
    if (searchForm.amountMin) params.amount_min = parseFloat(searchForm.amountMin)
    if (searchForm.amountMax) params.amount_max = parseFloat(searchForm.amountMax)
    if (searchForm.status) params.status = searchForm.status
    const res = await salesApi.invoices.list(params)
    list.value = res.items || res.list || []
    total.value = res.total || 0
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
    nextTick(initColumnDrag)
  }
}

async function fetchCustomers() {
  try {
    const res = await foundationApi.customers.list({ page: 1, page_size: 100 })
    customerList.value = res.items || res.list || []
  } catch (e) {}
}

async function fetchOrders() {
  try {
    const res = await salesApi.orders.list({ page: 1, page_size: 100 })
    orderList.value = (res.items || []).filter(o => (o.uninvoiced_amount || 0) > 0)
  } catch (e) {}
}

function onCustomerChange() {
  form.sales_order_id = null
}

function calcAmount() {
  const totalAmount = form.total_amount || 0
  const taxRate = form.tax_rate || 0
  // 含税 → 不含税反推
  form.amount = Math.round(totalAmount / (1 + taxRate / 100) * 100) / 100
  form.tax_amount = Math.round((totalAmount - form.amount) * 100) / 100
}

function onOrderChange() {
  const o = orderList.value.find(x => x.id === form.sales_order_id)
  if (o) {
    form.customer_id = o.customer_id || null
    form.total_amount = o.total_amount || o.total_amount_local || 0
    selectedOrderUninvoiced.value = o.uninvoiced_amount || 0
    calcAmount()
  } else {
    selectedOrderUninvoiced.value = 0
  }
}

function openCreate() {
  editMode.value = false
  selectedOrderUninvoiced.value = 0
  form.id = null
  form.customer_id = null
  form.sales_order_id = null
  form.invoice_no = ''
  form.amount = 0
  form.tax_rate = 13
  form.tax_amount = 0
  form.total_amount = 0
  form.invoice_date = ''
  form.remark = ''
  dialogVisible.value = true
}

function openEdit(row) {
  editMode.value = true
  Object.assign(form, {
    id: row.id, customer_id: row.customer_id, sales_order_id: row.order_id,
    invoice_no: row.invoice_no, amount: row.amount, tax_rate: row.tax_rate || 13,
    tax_amount: row.tax_amount || 0, total_amount: row.total_amount || 0,
    invoice_date: row.invoice_date, remark: row.remark || ''
  })
  dialogVisible.value = true
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除发票 ${row.invoice_no}？`, '提示', { type: 'warning' })
  try {
    await salesApi.invoices.delete(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) {}
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editMode.value) {
      await salesApi.invoices.update(form.id, { ...form })
      ElMessage.success('修改成功')
    } else {
      await salesApi.invoices.create({ ...form })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
    fetchOrders()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

// ===== 红冲 =====
const redVisible = ref(false)
const redLoading = ref(false)
const redForm = reactive({
  id: null, order_id: null, orig_invoice_no: '', orig_total: 0,
  invoice_no: '', invoice_date: '', remark: '',
})

function openRedReverse(row) {
  redForm.id = row.id
  redForm.order_id = row.order_id
  redForm.orig_invoice_no = row.invoice_no
  redForm.orig_total = row.total_amount
  redForm.invoice_no = ''
  redForm.invoice_date = new Date().toISOString().slice(0, 10)
  redForm.remark = ''
  redVisible.value = true
}

async function handleRedReverse() {
  if (!redForm.invoice_no) { ElMessage.warning('请输入红字发票号'); return }
  await ElMessageBox.confirm(
    `确认全额红冲发票 ${redForm.orig_invoice_no}？红字金额 ${(-redForm.orig_total).toFixed(2)}，原发票将标记「已红冲」并自动生成等额红字应收。`,
    '红冲确认', { type: 'warning', confirmButtonText: '确认红冲', cancelButtonText: '再想想' }
  )
  redLoading.value = true
  try {
    const taxRate = 13
    const total = redForm.orig_total
    await salesApi.invoices.create({
      invoice_no: redForm.invoice_no,
      order_id: redForm.order_id,
      red_of_invoice_id: redForm.id,
      invoice_date: redForm.invoice_date,
      amount: Math.round(-total / (1 + taxRate / 100) * 100) / 100,
      tax_amount: Math.round((-total - (-total / (1 + taxRate / 100))) * 100) / 100,
      total_amount: -total,
      tax_rate: taxRate,
      remark: redForm.remark,
    })
    ElMessage.success('红冲成功，红字应收已生成')
    redVisible.value = false
    fetchList()
    fetchOrders()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '红冲失败')
  } finally {
    redLoading.value = false
  }
}

function statusType(status) {
  const map = { '待开票': 'info', '已开票': 'success', '已作废': 'danger', '已红冲': 'warning' }
  return map[status] || 'info'
}
</script>
