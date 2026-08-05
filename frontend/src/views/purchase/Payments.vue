<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="付款单号/供应商" clearable @keyup.enter="fetchList" style="width: 160px" />
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="payment_no" label="付款单号" width="160" sortable>
          <template #default="{ row }">
            <span>{{ row.payment_no }}</span>
            <el-tag v-if="row.reviewed" type="success" size="small" style="margin-left: 4px">已审核</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="supplier_name" label="供应商" min-width="150" column-key="supplier_name" :filters="supplierFilters" :filter-method="filterSupplier" sortable />
        <el-table-column prop="payment_date" label="付款日期" width="120" column-key="payment_date" :filters="dateFilters" :filter-method="filterDate" sortable />
        <el-table-column label="金额" width="120" align="right" sortable><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column label="核销金额" width="120" align="right" sortable><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
        <el-table-column prop="payment_method" label="付款方式" width="100" sortable />
        <el-table-column prop="operator" label="操作人" width="90" sortable />
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip sortable />
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <!-- 已审核 = 财务确认，业务全部锁定：只能取消审核 -->
            <template v-if="row.reviewed">
              <el-button link type="warning" @click="handleUnreview(row)">取消审核</el-button>
            </template>
            <template v-else>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
              <el-button link type="success" @click="handleReview(row)">审核</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top: 12px"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="fetchList"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="付款单详情" width="600px">
      <el-descriptions :column="2" border v-if="detail">
        <el-descriptions-item label="付款单号" span="2">{{ detail.payment_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ detail.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="付款日期">{{ detail.payment_date }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ $fm(detail.amount) }}</el-descriptions-item>
        <el-descriptions-item label="外币金额">{{ $fm(detail.amount_fc) }}</el-descriptions-item>
        <el-descriptions-item label="付款方式">{{ detail.payment_method }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ detail.operator }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">
          <div style="width: 100%; white-space: pre-wrap">{{ detail.remark || '-' }}</div>
        </el-descriptions-item>
      </el-descriptions>
      <el-divider>核销明细</el-divider>
      <el-table :data="detail?.allocations || []" stripe size="small" v-if="detail?.allocations?.length">
        <el-table-column prop="ap_no" label="应付单号" width="160" />
        <el-table-column label="核销金额" width="120"><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
      </el-table>
      <span v-else style="color: #909399">无核销明细</span>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑付款单" width="500px" destroy-on-close>
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="付款单号">
          <el-input :model-value="editForm.payment_no" disabled />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input :model-value="editForm.supplier_name" disabled />
        </el-form-item>
        <el-form-item label="金额">
          <span style="font-weight: bold">{{ $fm(editForm.amount) }}</span>
        </el-form-item>
        <el-form-item label="付款日期">
          <el-date-picker v-model="editForm.payment_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="editForm.payment_method" placeholder="请选择" style="width: 100%">
            <el-option label="银行转账" value="银行转账" />
            <el-option label="现金" value="现金" />
            <el-option label="承兑汇票" value="承兑汇票" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" style="width: 100%">
          <el-input v-model="editForm.remark" type="textarea" :rows="3" placeholder="请输入备注" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { purchaseApi } from '../../api/business'

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const detailVisible = ref(false)
const detail = ref(null)
const editVisible = ref(false)
const submitting = ref(false)
const searchForm = reactive({ keyword: '', dateRange: null })

// 列筛选
const dateFilters = ref([])
const supplierFilters = ref([])
const filterDateVal = ref('')
const filterSupplierVal = ref('')

const filteredList = computed(() => {
  let items = list.value
  if (filterDateVal.value) items = items.filter(r => r.payment_date === filterDateVal.value)
  if (filterSupplierVal.value) items = items.filter(r => r.supplier_name === filterSupplierVal.value)
  return items
})

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterSupplier(val, row) { filterSupplierVal.value = val; return true }

function resetSearch() { searchForm.keyword = ''; searchForm.dateRange = null; filterDateVal.value = ''; filterSupplierVal.value = ''; page.value = 1; fetchList() }

const editForm = reactive({
  id: null, payment_no: '', supplier_name: '', amount: 0,
  payment_date: '', payment_method: '银行转账', remark: '',
})

onMounted(fetchList)

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) { params.start_date = searchForm.dateRange[0]; params.end_date = searchForm.dateRange[1] }
    const res = await purchaseApi.payments.list(params)
    list.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    dateFilters.value = [...new Set(list.value.map(r => r.payment_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    supplierFilters.value = [...new Set(list.value.map(r => r.supplier_name).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function openDetail(row) {
  try {
    const res = await purchaseApi.payments.get(row.id, row.id)
    detail.value = res
    detailVisible.value = true
  } catch { ElMessage.error('加载详情失败') }
}

function openEdit(row) {
  editForm.id = row.id
  editForm.payment_no = row.payment_no
  editForm.supplier_name = row.supplier_name
  editForm.amount = row.amount
  editForm.payment_date = row.payment_date
  editForm.payment_method = row.payment_method || '银行转账'
  editForm.remark = row.remark || ''
  editVisible.value = true
}

async function submitEdit() {
  submitting.value = true
  try {
    await purchaseApi.payments.update(editForm.id, {
      payment_date: editForm.payment_date,
      payment_method: editForm.payment_method,
      remark: editForm.remark || '',
    })
    ElMessage.success('修改成功')
    editVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '修改失败') }
  finally { submitting.value = false }
}

// ===== 审核锁定（财务确认标记，审核后业务全部锁定） =====
async function handleReview(row) {
  await ElMessageBox.confirm(
    `审核付款单 ${row.payment_no}？审核后该单据不可修改/删除（财务确认，业务锁定），只能取消审核。`,
    '付款单审核', { type: 'warning', confirmButtonText: '确认审核', cancelButtonText: '取消' }
  )
  try {
    const res = await purchaseApi.payments.review(row.id)
    ElMessage.success(res.message || '审核成功')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审核失败') }
}

async function handleUnreview(row) {
  await ElMessageBox.confirm(
    `取消审核付款单 ${row.payment_no}？取消后单据恢复可编辑/删除。`,
    '取消审核', { type: 'warning', confirmButtonText: '确认取消审核', cancelButtonText: '取消' }
  )
  try {
    const res = await purchaseApi.payments.unreview(row.id)
    ElMessage.success(res.message || '已取消审核')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确定删除付款单 ${row.payment_no}？应付金额将同步回滚。`,
    '提示', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  try {
    await purchaseApi.payments.delete(row.id, row.id)
    ElMessage.success('删除成功，应付已回滚')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}
</script>