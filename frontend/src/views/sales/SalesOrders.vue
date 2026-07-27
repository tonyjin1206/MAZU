<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建订单</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="客户">
          <el-input v-model="searchForm.keyword" placeholder="客户名称/订单号" clearable style="width: 160px" @keyup.enter="fetchData" />
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
      <el-table :data="filteredList" v-loading="loading" stripe border size="small">
        <el-table-column prop="order_date" label="订单日期" width="100" column-key="order_date" :filters="dateFilters" :filter-method="filterDate" />
        <el-table-column prop="order_no" label="订单号" min-width="140" />
        <el-table-column prop="customer_name" label="客户" min-width="120" column-key="customer_name" :filters="customerFilters" :filter-method="filterCustomer" />
        <el-table-column prop="item_count" label="明细" width="50" align="center" />
          <el-table-column label="含税金额" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
          <el-table-column label="已开票" align="right"><template #default="{ row }">{{ $fm(row.invoiced_amount) }}</template></el-table-column>
          <el-table-column label="未开票" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.total_amount - row.invoiced_amount) > 0 ? '#e6a23c' : '#909399' }">
                {{ $fm((row.total_amount || 0) - (row.invoiced_amount || 0)) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="currency_code" label="币种" width="60" />
          <el-table-column prop="trade_term" label="贸易术语" width="80" />
          <el-table-column label="发货" align="center" min-width="60">
            <template #default="{ row }">
              <el-tag v-if="row.status === '已发货'" type="success" size="small">已发货</el-tag>
              <el-tag v-else-if="row.status === '部分发货'" type="warning" size="small">部分</el-tag>
              <el-tag v-else size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="已发货" align="right"><template #default="{ row }">{{ $fm(row.delivered_amount) }}</template></el-table-column>
          <el-table-column label="未发货" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.undelivered_amount || 0) > 0 ? '#e6a23c' : '#909399' }">
                {{ $fm(row.undelivered_amount) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="已收款" align="right"><template #default="{ row }">{{ $fm(row.collected_amount) }}</template></el-table-column>
          <el-table-column label="未收款" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.uncollected_amount || 0) > 0 ? '#e6a23c' : '#909399' }">
                {{ $fm(row.uncollected_amount) }}
              </span>
            </template>
          </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待审核'" link type="primary" @click="handleApprove(row)">审核</el-button>
            <el-button v-if="row.status === '待审核'" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button link type="primary" @click="openDialog(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[100]" layout="total, prev, pager, next" @change="fetchData" style="margin-top: 12px" />
    </el-card>

    <!-- 新建/详情弹窗 -->
    <el-dialog v-model="dialogVisible" :title="viewMode ? '订单详情' : '新建订单'" width="900px" destroy-on-close>
      <el-form :model="orderForm" label-width="90px" :disabled="viewMode">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer_id">
              <el-select v-model="orderForm.customer_id" placeholder="请选择客户" filterable style="width: 100%" :disabled="viewMode">
                <el-option v-for="c in customerList" :key="c.id" :label="`${c.code} - ${c.name_cn}`" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="币种">
              <el-select v-model="orderForm.currency_id" placeholder="选择币种" style="width: 100%" :disabled="viewMode">
                <el-option v-for="c in currencyList" :key="c.id" :label="c.code" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="贸易术语">
              <el-select v-model="orderForm.trade_term_id" placeholder="选择" style="width: 100%" :disabled="viewMode">
                <el-option v-for="t in tradeTermList" :key="t.id" :label="t.code" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="付款条款">
              <el-input v-model="orderForm.payment_terms" placeholder="TT/LC" :disabled="viewMode" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="订单日期">
              <el-date-picker v-model="orderForm.order_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" :disabled="viewMode" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="交期">
              <el-date-picker v-model="orderForm.delivery_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" :disabled="viewMode" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="orderForm.remark" type="textarea" :rows="2" :disabled="viewMode" />
        </el-form-item>

        <!-- 订单明细 -->
        <el-form-item label="订单明细">
          <div style="width: 100%">
            <el-button v-if="!viewMode" size="small" @click="addItem">+ 添加产品</el-button>
            <el-table :data="orderForm.items" border size="small" style="width: 100%; margin-top: 4px">
              <el-table-column label="产品" width="200">
                <template #default="{ row }">
                  <el-select v-if="!viewMode" v-model="row.product_id" placeholder="选择" filterable size="small" style="width: 100%" @change="onProductChange(row)">
                    <el-option v-for="p in productList" :key="p.id" :label="`${p.code} - ${p.name_cn}`" :value="p.id" />
                  </el-select>
                  <span v-else>{{ row.product_name }}</span>
                </template>
              </el-table-column>
              <el-table-column label="数量" width="100">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.quantity" :min="0" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="单价" width="100">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.unit_price" :min="0" :precision="2" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="税率%" width="70">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.tax_rate" :min="0" :max="17" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="含税金额" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.total_amount) }}</template>
              </el-table-column>
              <el-table-column label="税额" width="80" align="right">
                <template #default="{ row }">{{ $fm(row.tax_amount) }}</template>
              </el-table-column>
              <el-table-column label="不含税" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.total_amount_excl_tax) }}</template>
              </el-table-column>
              <el-table-column v-if="!viewMode" width="50">
                <template #default="{ $index }">
                  <el-button link type="danger" size="small" @click="removeItem($index)">删</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>

      <!-- 底部汇总 -->
      <div style="border-top: 1px solid #e4e7ed; padding-top: 12px; margin-top: 12px; display: flex; gap: 40px">
        <div>含税总金额 <b style="color: #409eff">{{ $fm(orderForm.total_amount) }}</b></div>
        <div>总税额 <b style="color: #e6a23c">{{ $fm(orderForm.tax_amount) }}</b></div>
        <div>不含税总金额 <b style="color: #909399">{{ $fm(orderForm.total_amount_excl_tax) }}</b></div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">{{ viewMode ? '关闭' : '取消' }}</el-button>
        <el-button v-if="!viewMode" type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'

const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })

// 搜索条件
const searchForm = reactive({
  keyword: '', dateRange: null, amountMin: '', amountMax: '',
})

// 列筛选
const customerFilters = ref([])
const dateFilters = ref([])
const filterCustomerVal = ref('')
const filterDateVal = ref('')

const filteredList = computed(() => {
  let items = dataList.value
  if (filterDateVal.value) {
    items = items.filter(r => r.order_date === filterDateVal.value)
  }
  if (filterCustomerVal.value) {
    items = items.filter(r => r.customer_name === filterCustomerVal.value)
  }
  return items
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.amountMin = ''
  searchForm.amountMax = ''
  filterCustomerVal.value = ''
  filterDateVal.value = ''
  queryParams.page = 1
  fetchData()
}

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterCustomer(val, row) { filterCustomerVal.value = val; return true }
const dialogVisible = ref(false)
const viewMode = ref(false)
const submitting = ref(false)
const customerList = ref([])
const currencyList = ref([])
const tradeTermList = ref([])
const productList = ref([])

const orderForm = reactive({
  id: null, customer_id: null, currency_id: null, trade_term_id: null,
  payment_terms: 'TT', order_date: '', delivery_date: '', remark: '',
  total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
  items: [],
})

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) {
      params.date_from = searchForm.dateRange[0]
      params.date_to = searchForm.dateRange[1]
    }
    if (searchForm.amountMin) params.amount_min = parseFloat(searchForm.amountMin)
    if (searchForm.amountMax) params.amount_max = parseFloat(searchForm.amountMax)
    const res = await request.get('/sales/orders', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选选项
    dateFilters.value = [...new Set(dataList.value.map(r => r.order_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    customerFilters.value = [...new Set(dataList.value.map(r => r.customer_name).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch {} finally { loading.value = false }
}

async function loadCustomers() {
  try { const res = await request.get('/foundation/customers', { params: { page: 1, page_size: 100 } }); customerList.value = res.items || [] } catch {}
}
async function loadCurrencies() {
  try { const res = await request.get('/foundation/currencies', { params: { page: 1, page_size: 100 } }); currencyList.value = res.items || [] } catch {}
}
async function loadTradeTerms() {
  try { const res = await request.get('/foundation/trade-terms', { params: { page: 1, page_size: 100 } }); tradeTermList.value = res.items || [] } catch {}
}
async function loadProducts() {
  try { const res = await request.get('/foundation/products', { params: { page: 1, page_size: 100 } }); productList.value = res.items || [] } catch {}
}

function openCreate() {
  viewMode.value = false
  Object.assign(orderForm, {
    id: null, customer_id: null, currency_id: null, trade_term_id: null,
    payment_terms: 'TT', order_date: '', delivery_date: '', remark: '',
    total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
    items: [{ product_id: null, quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 }],
  })
  dialogVisible.value = true
}

async function openDialog(row) {
  viewMode.value = true
  try {
    const res = await request.get(`/sales/orders/${row.id}`)
    Object.assign(orderForm, { ...res, items: res.items || [] })
    calcTotals()
  } catch {}
  dialogVisible.value = true
}

function addItem() {
  orderForm.items.push({ product_id: null, quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 })
}

function removeItem(idx) {
  orderForm.items.splice(idx, 1)
  calcTotals()
}

function onProductChange(row) {
  if (!row) return
  const p = productList.value.find(x => x.id === row.product_id)
  if (p) { row.unit_price = p.sale_price || 0; calcItem(row) }
}

function calcItem(row) {
  if (!row) return
  const qty = parseFloat(row.quantity) || 0
  const price = parseFloat(row.unit_price) || 0
  const rate = parseFloat(row.tax_rate) || 0
  row.total_amount = qty * price
  row.total_amount_excl_tax = Math.round(row.total_amount / (1 + rate / 100) * 100) / 100
  row.tax_amount = Math.round((row.total_amount_excl_tax * rate / 100) * 100) / 100
  calcTotals()
}

function calcTotals() {
  orderForm.total_amount = orderForm.items.reduce((s, i) => s + (i.total_amount || 0), 0)
  orderForm.tax_amount = orderForm.items.reduce((s, i) => s + (i.tax_amount || 0), 0)
  orderForm.total_amount_excl_tax = orderForm.items.reduce((s, i) => s + (i.total_amount_excl_tax || 0), 0)
}

async function handleSubmit() {
  if (!orderForm.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!orderForm.items.length) { ElMessage.warning('请添加明细'); return }
  submitting.value = true
  try {
    const items = orderForm.items.map(item => ({
      ...item,
      quantity: parseFloat(item.quantity) || 0,
      unit_price: parseFloat(item.unit_price) || 0,
      total_amount: parseFloat(item.total_amount) || 0,
      tax_amount: parseFloat(item.tax_amount) || 0,
      total_amount_excl_tax: parseFloat(item.total_amount_excl_tax) || 0,
      tax_rate: parseFloat(item.tax_rate) || 13,
    }))
    await request.post('/sales/orders', {
      customer_id: orderForm.customer_id, currency_id: orderForm.currency_id,
      trade_term_id: orderForm.trade_term_id, payment_terms: orderForm.payment_terms,
      order_date: orderForm.order_date, delivery_date: orderForm.delivery_date,
      remark: orderForm.remark, items,
    })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') } finally { submitting.value = false }
}

async function handleApprove(row) {
  await ElMessageBox.confirm(`审核订单 ${row.order_no}？审核后将生成生产订单。`, '提示', { type: 'info' })
  try {
    const res = await request.post(`/sales/orders/${row.id}/approve`)
    ElMessage.success(res.message || '审核成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审核失败') }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除订单 ${row.order_no}？`, '提示', { type: 'warning' })
  try {
    await request.delete(`/sales/orders/${row.id}`)
    ElMessage.success('删除成功')
    fetchData()
  } catch {}
}

// 监听明细行增减时自动重算（不 deep watch，避免 calcItem 修改属性导致循环触发）
watch(() => orderForm.items.length, () => {
  orderForm.items.forEach(item => calcItem(item))
})

onMounted(() => { fetchData(); loadCustomers(); loadCurrencies(); loadTradeTerms(); loadProducts() })
</script>
