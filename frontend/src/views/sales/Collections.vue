<template>
  <div>
    <!-- 搜索栏 -->
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="page = 1; fetchList()">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary">新建</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="收款单号/客户" clearable @keyup.enter="fetchList" style="width: 160px" />
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 列表 -->
    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="collection_no" label="收款单号" width="160" sortable />
        <el-table-column prop="customer_name" label="客户" min-width="150" sortable column-key="customer_name" :filters="customerFilters" :filter-method="filterCustomer" />
        <el-table-column prop="collection_date" label="收款日期" width="120" sortable column-key="collection_date" :filters="dateFilters" :filter-method="filterDate" />
        <el-table-column label="金额" width="120" align="right" sortable><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column label="核销金额" width="120" align="right" sortable><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
        <el-table-column prop="payment_method" label="付款方式" width="100" sortable />
        <el-table-column prop="operator" label="操作人" width="90" sortable />
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip sortable />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="收款单详情" width="600px">
      <el-descriptions :column="2" border v-if="detail">
        <el-descriptions-item label="收款单号" span="2">{{ detail.collection_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ detail.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="收款日期">{{ detail.collection_date }}</el-descriptions-item>
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
        <el-table-column prop="ar_no" label="应收单号" width="160" />
        <el-table-column label="核销金额" width="120"><template #default="{ row }">{{ $fm(row.allocated_amount) }}</template></el-table-column>
      </el-table>
      <span v-else style="color: #909399">无核销明细</span>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑收款单" width="500px" destroy-on-close>
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="收款单号">
          <el-input :model-value="editForm.collection_no" disabled />
        </el-form-item>
        <el-form-item label="客户">
          <el-input :model-value="editForm.customer_name" disabled />
        </el-form-item>
        <el-form-item label="金额">
          <span style="font-weight: bold">{{ $fm(editForm.amount) }}</span>
        </el-form-item>
        <el-form-item label="收款日期" prop="collection_date">
          <el-date-picker v-model="editForm.collection_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式" prop="payment_method">
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
import request from '../../api/request'

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const detailVisible = ref(false)
const detail = ref(null)
const editVisible = ref(false)
const submitting = ref(false)
const searchForm = reactive({ keyword: '', dateRange: null })

// 列筛选
const dateFilters = ref([])
const customerFilters = ref([])
const filterDateVal = ref('')
const filterCustomerVal = ref('')

const filteredList = computed(() => {
  let items = list.value
  if (filterDateVal.value) items = items.filter(r => r.collection_date === filterDateVal.value)
  if (filterCustomerVal.value) items = items.filter(r => r.customer_name === filterCustomerVal.value)
  return items
})

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterCustomer(val, row) { filterCustomerVal.value = val; return true }

function resetSearch() { searchForm.keyword = ''; searchForm.dateRange = null; filterDateVal.value = ''; filterCustomerVal.value = ''; page.value = 1; fetchList() }

const editForm = reactive({
  id: null, collection_no: '', customer_name: '', amount: 0,
  collection_date: '', payment_method: '银行转账', remark: '',
})

onMounted(fetchList)

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) { params.start_date = searchForm.dateRange[0]; params.end_date = searchForm.dateRange[1] }
    const res = await request.get('/sales/collections', { params })
    list.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    dateFilters.value = [...new Set(list.value.map(r => r.collection_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    customerFilters.value = [...new Set(list.value.map(r => r.customer_name).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function openDetail(row) {
  try {
    const res = await request.get(`/sales/collections/${row.id}`)
    detail.value = res
    detailVisible.value = true
  } catch { ElMessage.error('加载详情失败') }
}

function openEdit(row) {
  editForm.id = row.id
  editForm.collection_no = row.collection_no
  editForm.customer_name = row.customer_name
  editForm.amount = row.amount
  editForm.collection_date = row.collection_date
  editForm.payment_method = row.payment_method || '银行转账'
  editForm.remark = row.remark || ''
  editVisible.value = true
}

async function submitEdit() {
  submitting.value = true
  try {
    await request.put(`/sales/collections/${editForm.id}`, {
      collection_date: editForm.collection_date,
      payment_method: editForm.payment_method,
      remark: editForm.remark,
    })
    ElMessage.success('修改成功')
    editVisible.value = false
    fetchList()
  } catch { ElMessage.error('修改失败') }
  finally { submitting.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确定删除收款单 ${row.collection_no}？应收金额将同步回滚。`,
    '提示', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  try {
    await request.delete(`/sales/collections/${row.id}`)
    ElMessage.success('删除成功，应收已回滚')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}
</script>
