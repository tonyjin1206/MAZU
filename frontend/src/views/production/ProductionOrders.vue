<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="订单号/产品" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 110px">
            <el-option label="待确认" value="待确认" />
            <el-option label="待排产" value="待排产" />
            <el-option label="已排产" value="已排产" />
            <el-option label="生产中" value="生产中" />
            <el-option label="已完成" value="已完成" />
            <el-option label="部分入库" value="部分入库" />
            <el-option label="已入库" value="已入库" />
            <el-option label="待采购" value="待采购" />
            <el-option label="采购中" value="采购中" />
            <el-option label="已关闭" value="已关闭" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="order_no" label="生产订单号" width="160" sortable />
        <el-table-column prop="created_at" label="保存日期" width="100" sortable column-key="created_at" :filters="dateFilters" :filter-method="filterDate" />
        <el-table-column prop="product_name" label="产品" min-width="150" sortable column-key="product_name" :filters="productFilters" :filter-method="filterProduct" />
        <el-table-column label="数量" width="80" align="right" sortable><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
        <el-table-column prop="production_type" label="方式" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.production_type" :type="typeTagType(row.production_type)" size="small">{{ row.production_type }}</el-tag>
            <span v-else style="color: #999">待定</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" column-key="status" :filters="statusFilters" :filter-method="filterStatus">
          <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="due_date" label="交期" width="110" sortable />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div style="display: flex; gap: 8px; white-space: nowrap">
              <template v-if="row.status === '待确认'">
                <el-dropdown @command="(cmd) => handleSetType(row, cmd)">
                  <el-button link type="warning">确认备货方式<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="自产">🏭 自产</el-dropdown-item>
                      <el-dropdown-item command="委外">🔧 委外</el-dropdown-item>
                      <el-dropdown-item command="外购">🛒 外购(直采)</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button link type="primary" @click="openDetail(row)">查看</el-button>
                <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
              <template v-else-if="row.status === '待排产'">
                <el-button link type="primary" @click="openDetail(row)">维护</el-button>
                <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
              <template v-else-if="row.status === '待采购' || row.status === '采购中'">
                <el-button link type="primary" @click="openDetail(row)">详情</el-button>
                <el-button v-if="row.status === '待采购'" link type="success" @click="handleToPurchase(row)">推采购需求</el-button>
              </template>
              <template v-else-if="row.status === '已排产' || row.status === '生产中'">
                <el-button link type="primary" @click="openDetail(row, 'view')">详情</el-button>
                <el-button link type="success" @click="goWorkspace">工作台</el-button>
                <el-button link type="warning" @click="handleUnrelease(row)">反派产</el-button>
              </template>
              <template v-else>
                <el-button link type="primary" @click="openDetail(row, 'view')">详情</el-button>
              </template>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 16px" />
    </el-card>

    <!-- 推采购需求对话框 -->
    <el-dialog v-model="purchaseDialogVisible" title="推采购需求" width="480px" @close="resetPurchaseForm">
      <el-form :model="purchaseForm" label-width="100px" size="small">
        <el-form-item label="产品">
          <el-input :model-value="purchaseTarget?.product_name" disabled />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="purchaseForm.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="purchaseForm.remark" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <div style="color: #909399; font-size: 12px; padding: 0 8px">
        生成采购需求后由采购部门确认供应商与价格并转采购订单
      </div>
      <template #footer>
        <el-button @click="purchaseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="purchasing" @click="confirmToPurchase">确认生成采购需求</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { productionApi } from '../../api/business'

const router = useRouter()
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const searchForm = reactive({ keyword: '', status: '', dateRange: null })

// 列筛选
const dateFilters = ref([])
const productFilters = ref([])
const statusFilters = ref([])
const filterDateVal = ref('')
const filterProductVal = ref('')
const filterStatusVal = ref('')

const filteredList = computed(() => {
  let items = tableData.value
  if (filterDateVal.value) items = items.filter(r => r.created_at === filterDateVal.value)
  if (filterProductVal.value) items = items.filter(r => r.product_name === filterProductVal.value)
  if (filterStatusVal.value) items = items.filter(r => r.status === filterStatusVal.value)
  return items
})

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterProduct(val, row) { filterProductVal.value = val; return true }
function filterStatus(val, row) { filterStatusVal.value = val; return true }

function resetSearch() {
  searchForm.keyword = ''; searchForm.status = ''; searchForm.dateRange = null
  filterDateVal.value = ''; filterProductVal.value = ''; filterStatusVal.value = ''
  page.value = 1; fetchData()
}

function statusType(status) {
  const map = { '待确认': 'danger', '待排产': 'info', '已排产': 'warning', '生产中': 'primary', '已完成': 'success', '部分入库': 'warning', '已入库': 'success', '待采购': 'warning', '采购中': 'primary', '已关闭': 'danger' }
  return map[status] || 'info'
}

function typeTagType(t) {
  const map = { '自产': '', '委外': 'warning', '外购': 'success' }
  return map[t] || ''
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.dateRange) {
      params.date_from = searchForm.dateRange[0]
      params.date_to = searchForm.dateRange[1]
    }
    const res = await productionApi.productions.list(params)
    tableData.value = res.items || []
    total.value = res.total || 0
    dateFilters.value = [...new Set(tableData.value.map(r => r.created_at).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    productFilters.value = [...new Set(tableData.value.map(r => r.product_name).filter(Boolean))].map(v => ({ text: v, value: v }))
    statusFilters.value = [...new Set(tableData.value.map(r => r.status).filter(Boolean))].map(v => ({ text: v, value: v }))
  } finally { loading.value = false }
}

function openDetail(row, tab) {
  if (!row) { router.push('/production/orders/new'); return }
  router.push({ path: `/production/detail/${row.id}`, query: tab ? { tab } : {} })
}

function goWorkspace() { router.push('/production/workspace') }

async function handleSetType(row, productionType) {
  await ElMessageBox.confirm(`确认备货方式为「${productionType}」？确认后不可更改。`, '确认', { type: 'warning' })
  try {
    await productionApi.productions.setType(row.id, { production_type: productionType })
    ElMessage.success(`备货方式已确认为「${productionType}」`)
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除生产订单「${row.order_no}」？`, '提示', { type: 'warning' })
  try {
    await productionApi.productions.delete(row.id)
    ElMessage.success('已删除'); fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

async function handleUnrelease(row) {
  await ElMessageBox.confirm(`确认反派产「${row.order_no}」？`, '提示', { type: 'warning' })
  try {
    await productionApi.productions.unrelease(row.id)
    ElMessage.success('已反派产'); fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '反派产失败') }
}

// ============ 推采购需求 ============
const purchaseDialogVisible = ref(false)
const purchasing = ref(false)
const purchaseTarget = ref(null)
const purchaseForm = reactive({
  quantity: 0,
  remark: '',
})

function resetPurchaseForm() {
  purchaseForm.quantity = 0
  purchaseForm.remark = ''
  purchaseTarget.value = null
}

async function handleToPurchase(row) {
  purchaseTarget.value = row
  purchaseForm.quantity = row.quantity
  purchaseDialogVisible.value = true
}

async function confirmToPurchase() {
  if (!purchaseForm.quantity || purchaseForm.quantity <= 0) { ElMessage.warning('数量必须大于0'); return }
  purchasing.value = true
  try {
    await productionApi.productions.toRequisition(purchaseTarget.value.id, {
      quantity: purchaseForm.quantity,
      remark: purchaseForm.remark,
    })
    ElMessage.success('已生成采购需求')
    purchaseDialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
  finally { purchasing.value = false }
}

onMounted(fetchData)
</script>
