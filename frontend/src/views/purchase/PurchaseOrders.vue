<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate()">新建订单</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="供应商">
          <el-input v-model="searchForm.keyword" placeholder="订单号/供应商" clearable style="width: 160px" @keyup.enter="fetchData" />
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
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column label="日期" width="115" column-key="order_date" :filters="dateFilters" :filter-method="filterDate" sortable>
          <template #default="{ row }">{{ row.order_date }}</template>
        </el-table-column>
        <el-table-column prop="order_no" label="订单号" width="130" sortable />
        <el-table-column prop="supplier_name" label="供应商" width="100" show-overflow-tooltip column-key="supplier_name" :filters="supplierFilters" :filter-method="filterSupplier" sortable />
        <el-table-column prop="item_count" label="明细" width="70" align="center" sortable />
        <el-table-column label="含税金额" align="right" width="100" sortable><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
        <el-table-column label="已入库" align="right" width="90" sortable><template #default="{ row }">{{ $fm(row.received_amount) }}</template></el-table-column>
        <el-table-column label="未入库" align="right" width="90" sortable>
          <template #default="{ row }">
            <span :style="{ color: (row.unreceived_amount || 0) > 0 ? '#e6a23c' : '#909399' }">{{ $fm(row.unreceived_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="已开票" align="right" width="90" sortable><template #default="{ row }">{{ $fm(row.invoiced_amount) }}</template></el-table-column>
        <el-table-column label="未开票" align="right" width="90" sortable>
          <template #default="{ row }">
            <span :style="{ color: (row.uninvoiced_amount || 0) > 0 ? '#e6a23c' : '#909399' }">{{ $fm(row.uninvoiced_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="已付款" align="right" width="90" sortable><template #default="{ row }">{{ $fm(row.paid_amount) }}</template></el-table-column>
        <el-table-column label="未付款" align="right" width="90" sortable>
          <template #default="{ row }">
            <span :style="{ color: (row.unpaid_amount || 0) > 0 ? '#e6a23c' : '#909399' }">{{ $fm(row.unpaid_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="60" sortable>
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待审核'" link type="success" @click="handleApprove(row)">审核</el-button>
            <el-button v-if="row.status === '待审核'" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.status === '已审核'" link type="warning" @click="handleUnapprove(row)">取消审核</el-button>
            <el-button v-if="row.status === '已审核' || row.status === '部分入库'" link type="primary" @click="handleInStore(row)">入库</el-button>
            <el-button v-if="row.status === '待审核'" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button link @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @change="fetchData"
        style="margin-top: 16px"
      />
    </el-card>

    <!-- 新建/编辑/详情弹窗（保持不变） -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form :model="orderForm" :rules="orderRules" ref="orderFormRef" label-width="90px" :disabled="viewMode">
        <el-form-item label="供应商" prop="supplier_id">
          <el-select v-model="orderForm.supplier_id" placeholder="请选择供应商" filterable style="width: 100%" :disabled="!!orderForm.id" @change="onSupplierChange">
            <el-option v-for="s in supplierList" :key="s.id" :label="s.code + ' - ' + s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="订单明细">
          <el-table :data="orderForm.items" border size="small" style="width: 100%">
            <el-table-column label="物料编码" width="140">
              <template #default="{ row, $index }">
                <el-select v-model="row.material_id" placeholder="选择物料" filterable size="small" @change="onMaterialChange($index)">
                  <el-option v-for="m in materialList" :key="m.id" :label="m.code + ' - ' + m.name" :value="m.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column prop="material_name" label="物料名称" width="150" />
            <el-table-column prop="material_code" label="物料编码" width="100" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="数量" width="100">
              <template #default="{ row, $index }">
                <el-input type="number" v-model="row.quantity" :min="0" size="small" controls-position="right" @change="calcAmount($index)" />
              </template>
            </el-table-column>
            <el-table-column label="单价" width="110">
              <template #default="{ row, $index }">
                <el-input type="number" v-model="row.unit_price" :min="0" :precision="2" size="small" controls-position="right" @change="calcAmount($index)" />
              </template>
            </el-table-column>
            <el-table-column label="含税金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
            <el-table-column label="税率(%)" width="80">
              <template #default="{ row, $index }">
                <el-input type="number" v-model="row.tax_rate" :min="0" :max="17" size="small" controls-position="right" @change="calcAmount($index)" />
              </template>
            </el-table-column>
            <el-table-column label="税额" width="100" align="right"><template #default="{ row }">{{ $fm(row.tax_amount) }}</template></el-table-column>
            <el-table-column label="不含税金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.total_amount_excl_tax) }}</template></el-table-column>
            <el-table-column v-if="!viewMode" label="" width="60">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeItem($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item v-if="!viewMode">
          <el-button size="small" @click="addItem">+ 添加物料</el-button>
        </el-form-item>
        <el-form-item label="含税总金额"><span style="font-size: 18px; color: #409eff; font-weight: bold">{{ $fm(orderForm.total_amount) }}</span></el-form-item>
        <el-form-item label="总税额"><span style="font-size: 16px; color: #e6a23c; font-weight: bold">{{ $fm(orderForm.tax_amount) }}</span></el-form-item>
        <el-form-item label="不含税总金额"><span style="font-size: 16px; color: #909399; font-weight: bold">{{ $fm(orderForm.total_amount_excl_tax) }}</span></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ viewMode ? '关闭' : '取消' }}</el-button>
        <el-button v-if="!viewMode" type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { purchaseApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'
import request from '../../api/request'

const router = useRouter()

const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })

// 搜索条件
const searchForm = reactive({
  keyword: '', dateRange: null, amountMin: '', amountMax: '',
})

// 列筛选
const dateFilters = ref([])
const supplierFilters = ref([])
const filterDateVal = ref('')
const filterSupplierVal = ref('')

const filteredList = computed(() => {
  let items = dataList.value
  if (filterDateVal.value) items = items.filter(r => r.order_date === filterDateVal.value)
  if (filterSupplierVal.value) items = items.filter(r => r.supplier_name === filterSupplierVal.value)
  return items
})

function resetSearch() {
  searchForm.keyword = ''; searchForm.dateRange = null
  searchForm.amountMin = ''; searchForm.amountMax = ''
  filterDateVal.value = ''; filterSupplierVal.value = ''
  queryParams.page = 1; fetchData()
}

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterSupplier(val, row) { filterSupplierVal.value = val; return true }

const dialogVisible = ref(false)
const viewMode = ref(false)
const dialogTitle = computed(() => viewMode.value ? '订单详情' : '新建采购订单')
const submitting = ref(false)
const orderFormRef = ref(null)

const supplierList = ref([])
const materialList = ref([])

const orderForm = reactive({
  id: null, supplier_id: null, supplier_name: '',
  total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
  tax_rate: 13, payment_terms: '', remark: '', items: [],
})

const orderRules = {
  supplier_id: [{ required: true, message: '请选择供应商', trigger: 'change' }],
}

function newItem() {
  return { material_id: null, material_name: '', material_code: '', unit: '', quantity: 1, unit_price: 0, total_amount: 0, tax_rate: 13, tax_amount: 0, total_amount_excl_tax: 0 }
}

function addItem() { orderForm.items.push(newItem()) }
function removeItem(index) { orderForm.items.splice(index, 1); calcTotal() }

function onMaterialChange(index) {
  const m = materialList.value.find(x => x.id === orderForm.items[index].material_id)
  if (m) {
    const item = orderForm.items[index]
    item.material_name = m.name || ''
    item.material_code = m.code || ''
    item.unit = m.unit || ''
  }
}

function calcAmount(index) {
  const item = orderForm.items[index]
  item.total_amount = (item.quantity || 0) * (item.unit_price || 0)
  item.total_amount_excl_tax = Math.round(item.total_amount / (1 + (item.tax_rate || 0) / 100) * 100) / 100
  item.tax_amount = Math.round(((item.total_amount_excl_tax || 0) * (item.tax_rate || 0) / 100) * 100) / 100
  calcTotal()
}

function calcTotal() {
  orderForm.total_amount = orderForm.items.reduce((s, i) => s + (i.total_amount || 0), 0)
  orderForm.tax_amount = orderForm.items.reduce((s, i) => s + (i.tax_amount || 0), 0)
  orderForm.total_amount_excl_tax = orderForm.items.reduce((s, i) => s + (i.total_amount_excl_tax || 0), 0)
}

function onSupplierChange() {
  const s = supplierList.value.find(x => x.id === orderForm.supplier_id)
  if (s) orderForm.supplier_name = s.name
}

function statusType(status) {
  const map = {
    '待审核': 'warning', '已审核': 'success', '部分入库': 'warning',
    '待开票': 'info', '已开票': 'primary', '部分付款': 'warning', '已付款': 'success',
    '已完成': 'info', '已入库': 'success',
    pending: 'warning', approved: 'success', received: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = {
    '待审核': '待审核', '已审核': '已审核', '部分入库': '部分入库',
    '待开票': '待开票', '已开票': '已开票', '部分付款': '部分付款', '已付款': '已付款',
    '已完成': '已完成', '已入库': '已入库',
    pending: '待审核', approved: '已审核', received: '已入库',
  }
  return map[status] || status
}

function openCreate() {
  viewMode.value = false
  Object.assign(orderForm, { id: null, supplier_id: null, supplier_name: '', total_amount: 0, tax_rate: 13, payment_terms: '', remark: '', items: [newItem()] })
  if (!supplierList.value.length) loadSuppliers()
  if (!materialList.value.length) loadMaterials()
  dialogVisible.value = true
}

async function openEdit(row) {
  viewMode.value = false
  if (!supplierList.value.length) loadSuppliers()
  if (!materialList.value.length) loadMaterials()
  Object.assign(orderForm, { id: row.id, supplier_id: row.supplier_id, supplier_name: row.supplier_name || '', total_amount: row.total_amount || 0, tax_rate: row.tax_rate || 13, payment_terms: row.payment_terms || '', remark: row.remark || '', items: [] })
  await loadOrderDetail(row.id)
  dialogVisible.value = true
}

async function openDetail(row) {
  viewMode.value = true
  if (!supplierList.value.length) loadSuppliers()
  Object.assign(orderForm, { id: row.id, supplier_id: row.supplier_id, supplier_name: row.supplier_name || '', total_amount: row.total_amount || 0, tax_rate: row.tax_rate || 13, payment_terms: row.payment_terms || '', remark: row.remark || '', items: [] })
  await loadOrderDetail(row.id)
  dialogVisible.value = true
}

async function loadOrderDetail(orderId) {
  try {
    const res = await request.get(`/purchase/orders/${orderId}`)
    if (res.items) orderForm.items = res.items
    if (res.total_amount_excl_tax !== undefined) orderForm.total_amount_excl_tax = res.total_amount_excl_tax
    if (res.tax_amount !== undefined) orderForm.tax_amount = res.tax_amount
  } catch {}
}

async function loadSuppliers() {
  try {
    const res = await foundationApi.suppliers.list({ page: 1, pageSize: 100 })
    supplierList.value = res.items || res.list || res.data || []
  } catch {}
}

async function loadMaterials() {
  try {
    const res = await foundationApi.materials.list({ page: 1, pageSize: 100 })
    materialList.value = res.items || res.list || res.data || []
  } catch {}
}

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
    const res = await purchaseApi.orders.list(params)
    dataList.value = res.items || res.list || res.data || []
    total.value = res.total || dataList.value.length
    // 更新列筛选
    dateFilters.value = [...new Set(dataList.value.map(r => r.order_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    supplierFilters.value = [...new Set(dataList.value.map(r => r.supplier_name).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch (e) { ElMessage.error('加载数据失败') } finally { loading.value = false }
}

async function handleSubmit() {
  const valid = await orderFormRef.value.validate().catch(() => false)
  if (!valid) return
  if (orderForm.items.length === 0) { ElMessage.warning('请添加至少一条物料明细'); return }
  submitting.value = true
  try {
    const payload = { supplier_id: orderForm.supplier_id, payment_terms: orderForm.payment_terms, remark: orderForm.remark, tax_rate: orderForm.tax_rate, items: orderForm.items.map(({ material_id, quantity, unit_price }) => ({ material_id, quantity: parseFloat(quantity) || 0, unit_price: parseFloat(unit_price) || 0 })) }
    if (orderForm.id) {
      await request.put(`/purchase/orders/${orderForm.id}`, payload)
      ElMessage.success('修改成功')
    } else {
      await purchaseApi.orders.create(payload)
      ElMessage.success('订单创建成功')
    }
    dialogVisible.value = false; fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { submitting.value = false }
}

async function handleApprove(row) {
  await ElMessageBox.confirm('确定审核通过该订单？', '提示', { type: 'warning' })
  try { await purchaseApi.orders.approve(row.id); ElMessage.success('审核成功'); fetchData() } catch (e) {}
}

async function handleUnapprove(row) {
  await ElMessageBox.confirm('确定取消审核该订单？取消后可重新编辑。', '提示', { type: 'warning' })
  try { await request.post(`/purchase/orders/${row.id}/unapprove`); ElMessage.success('已取消审核'); fetchData() } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

function handleInStore(row) { router.push({ path: '/purchase/receipts', query: { oid: row.id } }) }

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除订单 ${row.order_no}？`, '提示', { type: 'warning' })
  try { await purchaseApi.orders.delete(row.id); ElMessage.success('删除成功'); fetchData() } catch (e) {}
}

onMounted(() => { fetchData(); loadSuppliers(); loadMaterials() })
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
