<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">开票</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="发票号/订单号" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="invoice_no" label="发票号" width="160" sortable />
        <el-table-column prop="order_no" label="生产订单号" width="160" sortable />
        <el-table-column prop="supplier_name" label="销售方" min-width="140" sortable column-key="supplier_name" :filters="supplierFilters" :filter-method="filterSupplier" />
        <el-table-column label="含税金额" width="100" align="right" sortable><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column label="税率" width="90" align="right" prop="tax_rate" sortable><template #default="{ row }">{{ row.tax_rate }}%</template></el-table-column>
        <el-table-column label="不含税金额" width="100" align="right" sortable><template #default="{ row }">{{ $fm(row.amount_excl_tax) }}</template></el-table-column>
        <el-table-column prop="invoice_date" label="开票日期" width="110" sortable column-key="invoice_date" :filters="dateFilters" :filter-method="filterDate" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }"><el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 12px" />
    </el-card>

    <!-- 选候选单弹窗 -->
    <el-dialog v-model="createVisible" title="开票 - 选择完工入库单" width="800px">
      <el-table :data="candidates" v-loading="candLoading" border size="small" @row-click="openInvoiceForm">
        <el-table-column prop="receipt_no" label="入库单号" width="160" />
        <el-table-column prop="order_no" label="生产订单" width="160" />
        <el-table-column prop="product_name" label="产品" min-width="120" />
        <el-table-column label="加工费" width="100" align="right"><template #default="{ row }">{{ $fm(row.process_fee) }}</template></el-table-column>
        <el-table-column prop="supplier_name" label="销售方" min-width="120" />
      </el-table>
      <div v-if="!candidates.length && !candLoading" style="text-align: center; color: #909399; padding: 20px">无可开票的完工入库记录</div>
      <template #footer><el-button @click="createVisible = false">取消</el-button></template>
    </el-dialog>

    <!-- 发票信息维护弹窗 -->
    <el-dialog v-model="formVisible" title="维护发票信息" width="550px">
      <el-form :model="formData" label-width="130px" size="small">
        <el-form-item label="销售方名称"><el-input v-model="formData.supplier_name" /></el-form-item>
        <el-form-item label="销售方税号"><el-input v-model="formData.supplier_tax_id" /></el-form-item>
        <el-form-item label="服务类型"><el-input v-model="formData.service_type" /></el-form-item>
        <el-form-item label="服务数量"><el-input type="number" v-model="formData.service_qty" :min="0" /></el-form-item>
        <el-form-item label="单价"><el-input type="number" v-model="formData.unit_price" :min="0" step="0.01" /></el-form-item>
        <el-form-item label="含税金额"><el-input :model-value="$fm(formData.amount)" disabled /></el-form-item>
        <el-form-item label="税率(%)"><el-input type="number" v-model="formData.tax_rate" :min="0" step="0.01" @input="calcExclTax" /></el-form-item>
        <el-form-item label="不含税金额"><el-input :model-value="$fm(formData.amount_excl_tax)" disabled /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="confirmCreate">确认开票</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi } from '../../api/business'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const searchForm = reactive({ keyword: '', dateRange: null })

// 列筛选
const dateFilters = ref([])
const supplierFilters = ref([])
const filterDateVal = ref('')
const filterSupplierVal = ref('')

const filteredList = computed(() => {
  let items = list.value
  if (filterDateVal.value) items = items.filter(r => r.invoice_date === filterDateVal.value)
  if (filterSupplierVal.value) items = items.filter(r => r.supplier_name === filterSupplierVal.value)
  return items
})

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterSupplier(val, row) { filterSupplierVal.value = val; return true }

function resetSearch() {
  searchForm.keyword = ''; searchForm.dateRange = null
  filterDateVal.value = ''; filterSupplierVal.value = ''
  page.value = 1; fetchData()
}

const createVisible = ref(false)
const candLoading = ref(false)
const candidates = ref([])

const formVisible = ref(false)
const createLoading = ref(false)
const formData = ref({})
let selectedCandidate = null

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) { params.date_from = searchForm.dateRange[0]; params.date_to = searchForm.dateRange[1] }
    const res = await productionApi.productions.processingInvoices.list(params)
    list.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    dateFilters.value = [...new Set(list.value.map(r => r.invoice_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    supplierFilters.value = [...new Set(list.value.map(r => r.supplier_name).filter(Boolean))].map(v => ({ text: v, value: v }))
  } finally { loading.value = false }
}

async function openCreate() {
  candLoading.value = true; createVisible.value = true
  try {
    const res = await productionApi.productions.processingInvoices.candidates()
    candidates.value = res.items || []
  } catch {} finally { candLoading.value = false }
}

function openInvoiceForm(row) {
  selectedCandidate = row; createVisible.value = false
  const fee = row.process_fee || 0
  formData.value = {
    supplier_name: row.supplier_name || '',
    supplier_tax_id: row.supplier_tax_id || '',
    service_type: '加工费',
    service_qty: row.quantity || 0,
    unit_price: row.quantity > 0 ? parseFloat((fee / row.quantity).toFixed(2)) : 0,
    amount: fee,
    tax_rate: 0,
    amount_excl_tax: fee,
  }
  formVisible.value = true
}

function calcExclTax() {
  const amount = parseFloat(formData.value.amount) || 0
  const rate = parseFloat(formData.value.tax_rate) || 0
  formData.value.amount_excl_tax = rate > 0 ? parseFloat((amount / (1 + rate / 100)).toFixed(2)) : amount
}

async function confirmCreate() {
  if (!selectedCandidate) return
  createLoading.value = true
  try {
    const payload = {
      production_id: selectedCandidate.production_id,
      supplier_name: formData.value.supplier_name,
      supplier_tax_id: formData.value.supplier_tax_id,
      service_type: formData.value.service_type,
      service_qty: parseFloat(formData.value.service_qty) || 0,
      unit_price: parseFloat(formData.value.unit_price) || 0,
      tax_rate: parseFloat(formData.value.tax_rate) || 0,
      amount_excl_tax: formData.value.amount_excl_tax,
    }
    const res = await productionApi.productions.processingInvoices.create(payload)
    ElMessage.success(res.message)
    formVisible.value = false; fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '开票失败') } finally { createLoading.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除发票「${row.invoice_no}」？`, '提示', { type: 'warning' })
  try {
    await productionApi.productions.processingInvoices.delete(row.id)
    ElMessage.success('已删除'); fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

onMounted(fetchData)
</script>
