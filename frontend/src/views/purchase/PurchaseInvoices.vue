<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建发票</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="供应商">
          <el-input v-model="searchForm.keyword" placeholder="发票号/供应商" clearable style="width: 160px" @keyup.enter="fetchList" />
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

    <el-card>
<el-table :key="columnVersion" :data="list" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align" :show-overflow-tooltip="col.prop === 'remark'">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'amount'" #default="{ row }">{{ $fm(row.amount) }}</template>
          <template v-else-if="col.prop === 'tax_amount'" #default="{ row }">{{ $fm(row.tax_amount) }}</template>
          <template v-else-if="col.prop === 'total_amount'" #default="{ row }">{{ $fm(row.total_amount) }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top: 12px"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="fetchList"
      />
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editMode ? '编辑发票' : '新建发票'" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="供应商" prop="supplier_id">
          <el-select v-model="form.supplier_id" placeholder="请选择供应商" filterable style="width: 100%" :disabled="editMode" @change="onSupplierChange">
            <el-option v-for="s in supplierList" :key="s.id" :label="`${s.code} - ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="采购订单" prop="purchase_order_id">
          <el-select v-model="form.purchase_order_id" placeholder="请选择采购订单" filterable style="width: 100%" :disabled="editMode" @change="onOrderChange">
            <el-option v-for="o in orderList" :key="o.id" :label="`${o.order_no} - ${o.supplier_name}`" :value="o.id" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import request from '../../api/request'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_purchase_invoice_columns'
const defaultColumns = [
  { prop: 'invoice_no', label: '发票号', width: 160, sortable: true },
  { prop: 'supplier_name', label: '供应商', minWidth: 150, sortable: true },
  { prop: 'order_no', label: '采购单号', width: 140, sortable: true },
  { prop: 'amount', label: '不含税金额', width: 120, align: 'right', sortable: true },
  { prop: 'tax_amount', label: '税额', width: 100, align: 'right', sortable: true },
  { prop: 'total_amount', label: '价税合计', width: 120, align: 'right', sortable: true },
  { prop: 'invoice_date', label: '发票日期', width: 120, sortable: true },
  { prop: 'status', label: '状态', width: 100, sortable: true },
  { prop: 'remark', label: '备注', minWidth: 150, sortable: true },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY)

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
  keyword: '',
  dateRange: null,
  amountMin: null,
  amountMax: null,
  status: '',
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.amountMin = null; searchForm.amountMax = null; searchForm.status = ''
  page.value = 1
  fetchList()
}

const supplierList = ref([])
const orderList = ref([])
const selectedOrderUninvoiced = ref(0)
const statusList = ref([])

const form = reactive({
  supplier_id: null,
  purchase_order_id: null,
  invoice_no: '',
  amount: 0,
  tax_rate: 13,
  tax_amount: 0,
  total_amount: 0,
  invoice_date: '',
  remark: '',
})

const rules = {
  supplier_id: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  purchase_order_id: [{ required: true, message: '请选择采购订单', trigger: 'change' }],
  invoice_no: [{ required: true, message: '请输入发票号', trigger: 'blur' }],
  total_amount: [{ required: true, message: '请输入含税金额', trigger: 'blur' }],
  invoice_date: [{ required: true, message: '请选择发票日期', trigger: 'change' }],
}

onMounted(() => {
  fetchList()
  fetchSuppliers()
  fetchOrders()
})

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) { params.date_from = searchForm.dateRange[0]; params.date_to = searchForm.dateRange[1] }
    if (searchForm.amountMin) params.amount_min = parseFloat(searchForm.amountMin)
    if (searchForm.amountMax) params.amount_max = parseFloat(searchForm.amountMax)
    if (searchForm.status) params.status = searchForm.status
    const res = await request.get('/purchase/invoices', { params })
    list.value = res.items || res.list || []
    total.value = res.total || 0
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
    nextTick(initColumnDrag)
  }
}

async function fetchSuppliers() {
  try {
    const res = await request.get('/foundation/suppliers', { params: { page: 1, page_size: 100 } })
    supplierList.value = res.items || res.list || []
  } catch {}
}

async function fetchOrders() {
  try {
    const res = await request.get('/purchase/orders', { params: { page: 1, page_size: 100 } })
    orderList.value = (res.items || []).filter(o => ['已审核', '部分入库', '待开票', '已开票', '部分付款'].includes(o.status) && (o.uninvoiced_amount || 0) > 0)
  } catch {}
}

function onSupplierChange() {
  form.purchase_order_id = null
}

function calcAmount() {
  const totalAmount = form.total_amount || 0
  const taxRate = form.tax_rate || 0
  form.amount = Math.round(totalAmount / (1 + taxRate / 100) * 100) / 100
  form.tax_amount = Math.round((totalAmount - form.amount) * 100) / 100
}

function onOrderChange() {
  const o = orderList.value.find(x => x.id === form.purchase_order_id)
  if (o) {
    form.supplier_id = o.supplier_id || null
    form.total_amount = o.total_amount || 0
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
  form.supplier_id = null
  form.purchase_order_id = null
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
    id: row.id, supplier_id: row.supplier_id, purchase_order_id: row.order_id,
    invoice_no: row.invoice_no, amount: row.amount, tax_rate: row.tax_rate || 13,
    tax_amount: row.tax_amount || 0, total_amount: row.total_amount || 0,
    invoice_date: row.invoice_date, remark: row.remark || ''
  })
  dialogVisible.value = true
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除发票 ${row.invoice_no}？`, '提示', { type: 'warning' })
  try {
    await request.delete(`/purchase/invoices/${row.id}`)
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
      await request.put(`/purchase/invoices/${form.id}`, { ...form })
      ElMessage.success('修改成功')
    } else {
      await request.post('/purchase/invoices', {
        order_id: form.purchase_order_id,
        supplier_id: form.supplier_id,
        invoice_no: form.invoice_no,
        amount: form.amount,
        tax_amount: form.tax_amount || 0,
        invoice_date: form.invoice_date,
        remark: form.remark || '',
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
    fetchOrders()
  } catch {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

function statusType(status) {
  const map = { '待开票': 'info', '已开票': 'success', '已作废': 'danger' }
  return map[status] || 'info'
}
</script>