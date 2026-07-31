<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建报关单</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="报关单号">
          <el-input v-model="searchForm.keyword" placeholder="报关单号/客户" clearable style="width: 160px" @keyup.enter="fetchList" />
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="已报关" value="已报关" />
            <el-option label="已放行" value="已放行" />
            <el-option label="已结关" value="已结关" />
            <el-option label="已取消" value="已取消" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe>
        <el-table-column prop="customs_no" label="报关单号" width="160" sortable />
        <el-table-column prop="order_no" label="关联订单" width="140" sortable />
        <el-table-column prop="customer_name" label="客户" min-width="130" sortable column-key="customer_name" :filters="customerFilters" :filter-method="filterCustomer" />
        <el-table-column prop="hs_code" label="HS编码" width="120" sortable />
        <el-table-column label="报关金额" width="120" align="right" sortable><template #default="{ row }">{{ $fm(row.declare_amount) }}</template></el-table-column>
        <el-table-column prop="currency_code" label="币种" width="90" sortable />
        <el-table-column prop="customs_broker" label="报关行" min-width="120" sortable />
        <el-table-column prop="declare_date" label="报关日期" width="100" sortable column-key="declare_date" :filters="dateFilters" :filter-method="filterDate" />
        <el-table-column prop="status" label="状态" width="100" column-key="status" :filters="statusFilters" :filter-method="filterStatus">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
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
    <el-dialog v-model="dialogVisible" :title="editMode ? '编辑报关单' : '新建报关单'" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="报关单号" prop="customs_no">
          <el-input v-model="form.customs_no" placeholder="请输入报关单号" :disabled="editMode" />
        </el-form-item>
        <el-form-item label="关联订单" prop="order_id">
          <el-select v-model="form.order_id" placeholder="请选择销售订单" filterable style="width: 100%" :disabled="editMode" @change="onOrderChange">
            <el-option v-for="o in orderList" :key="o.id" :label="o.order_no + ' - ' + (o.customer_name || '')" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="HS编码" prop="hs_code_id">
          <el-select v-model="form.hs_code_id" placeholder="请选择HS编码" filterable style="width: 100%">
            <el-option v-for="h in hsCodeList" :key="h.id" :label="h.hs_code + ' - ' + (h.name_cn || '')" :value="h.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报关金额" prop="declare_amount">
          <el-input type="number" v-model="form.declare_amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="币种" prop="declare_currency">
          <el-select v-model="form.declare_currency" placeholder="请选择币种" style="width: 100%">
            <el-option v-for="c in currencyList" :key="c.id" :label="c.code + ' - ' + (c.name_cn || c.name || '')" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报关日期" prop="declare_date">
          <el-date-picker v-model="form.declare_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="报关行" prop="customs_broker">
          <el-input v-model="form.customs_broker" placeholder="请输入报关行名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
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
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'

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
  status: '',
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.status = ''
  filterDateVal.value = ''; filterCustomerVal.value = ''; filterStatusVal.value = ''
  page.value = 1
  fetchList()
}

// 列筛选
const dateFilters = ref([])
const customerFilters = ref([])
const statusFilters = ref([])
const filterDateVal = ref('')
const filterCustomerVal = ref('')
const filterStatusVal = ref('')

const filteredList = computed(() => {
  let items = list.value
  if (filterDateVal.value) items = items.filter(r => r.declare_date === filterDateVal.value)
  if (filterCustomerVal.value) items = items.filter(r => r.customer_name === filterCustomerVal.value)
  if (filterStatusVal.value) items = items.filter(r => r.status === filterStatusVal.value)
  return items
})

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterCustomer(val, row) { filterCustomerVal.value = val; return true }
function filterStatus(val, row) { filterStatusVal.value = val; return true }
const orderList = ref([])
const hsCodeList = ref([])
const currencyList = ref([])

const form = reactive({
  customs_no: '',
  order_id: null,
  hs_code_id: null,
  declare_amount: 0,
  declare_currency: null,
  declare_date: '',
  customs_broker: '',
  remark: '',
})

const rules = {
  customs_no: [{ required: true, message: '请输入报关单号', trigger: 'blur' }],
  order_id: [{ required: true, message: '请选择销售订单', trigger: 'change' }],
  hs_code_id: [{ required: true, message: '请选择HS编码', trigger: 'change' }],
  declare_amount: [{ required: true, message: '请输入报关金额', trigger: 'blur' }],
  declare_currency: [{ required: true, message: '请选择币种', trigger: 'change' }],
  declare_date: [{ required: true, message: '请选择报关日期', trigger: 'change' }],
  customs_broker: [{ required: true, message: '请输入报关行', trigger: 'blur' }],
}

onMounted(() => {
  fetchList()
  fetchOrders()
  fetchHsCodes()
  fetchCurrencies()
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
    if (searchForm.status) params.status = searchForm.status
    const res = await request.get('/sales/customs', { params })
    list.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    dateFilters.value = [...new Set(list.value.map(r => r.declare_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    customerFilters.value = [...new Set(list.value.map(r => r.customer_name).filter(Boolean))].map(v => ({ text: v, value: v }))
    statusFilters.value = [...new Set(list.value.map(r => r.status).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function fetchOrders() {
  try {
    const res = await request.get('/sales/orders', { params: { page: 1, page_size: 100 } })
    orderList.value = res.items || []
  } catch {}
}

async function fetchHsCodes() {
  try {
    const res = await request.get('/foundation/hs-codes', { params: { page: 1, page_size: 200 } })
    hsCodeList.value = res.items || res.list || []
  } catch {}
}

async function fetchCurrencies() {
  try {
    const res = await request.get('/foundation/currencies', { params: { page: 1, page_size: 50 } })
    currencyList.value = res.items || res.list || []
  } catch {}
}

function onOrderChange(orderId) {
  const o = orderList.value.find(x => x.id === orderId)
  if (o) {
    if (!form.declare_currency) form.declare_currency = o.currency_id || null
    if (!form.declare_amount || form.declare_amount === 0) form.declare_amount = o.total_amount_local || o.total_amount || 0
  }
}

function openCreate() {
  editMode.value = false
  Object.assign(form, { id: null, customs_no: '', order_id: null, hs_code_id: null, declare_amount: 0, declare_currency: null, declare_date: '', customs_broker: '', remark: '' })
  dialogVisible.value = true
}

async function openEdit(row) {
  editMode.value = true
  try {
    const res = await request.get(`/sales/customs/${row.id}`)
    Object.assign(form, {
      id: res.id, customs_no: res.customs_no, order_id: res.order_id,
      hs_code_id: res.hs_code_id, declare_amount: res.declare_amount,
      declare_currency: res.declare_currency, declare_date: res.declare_date,
      customs_broker: res.customs_broker, remark: res.remark || '',
    })
    dialogVisible.value = true
  } catch { ElMessage.error('加载详情失败') }
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editMode.value) {
      await request.put(`/sales/customs/${form.id}`, { ...form })
      ElMessage.success('修改成功')
    } else {
      await request.post('/sales/customs', { ...form })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally { submitting.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除报关单 ${row.customs_no}？`, '提示', { type: 'warning' })
  try {
    await request.delete(`/sales/customs/${row.id}`)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

function statusType(status) {
  const map = { 已报关: 'primary', 已放行: 'success', 已结关: 'success', 已取消: 'info' }
  return map[status] || 'info'
}
function statusLabel(status) {
  const map = { 已报关: '已报关', 已放行: '已放行', 已结关: '已结关', 已取消: '已取消' }
  return map[status] || status
}
</script>
