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
          <el-input v-model="searchForm.keyword" placeholder="需求单号/产品" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 110px">
            <el-option label="待处理" value="待处理" />
            <el-option label="已转单" value="已转单" />
            <el-option label="已关闭" value="已关闭" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="tableData" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="requisition_no" label="需求单号" width="160" sortable />
        <el-table-column prop="created_at" label="创建日期" width="160" sortable />
        <el-table-column prop="production_order_no" label="来源生产订单" width="160" />
        <el-table-column prop="product_code" label="产品编码" width="110" />
        <el-table-column prop="product_name" label="产品名称" min-width="140" />
        <el-table-column label="数量" width="90" align="right" sortable><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
        <el-table-column prop="created_by" label="提出人" width="90" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div style="display: flex; gap: 4px; white-space: nowrap">
              <template v-if="row.status === '待处理'">
                <el-button type="success" size="small" @click="handleToPurchase(row)">生成采购订单</el-button>
                <el-button type="danger" link size="small" @click="handleClose(row)">关闭</el-button>
              </template>
              <el-button v-else type="primary" size="small" @click="openDetail(row)">详情</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 16px" />
    </el-card>

    <!-- 转采购订单对话框 -->
    <el-dialog v-model="poDialogVisible" title="生成采购订单" width="520px" @close="resetPoForm">
      <el-form :model="poForm" label-width="100px" size="small">
        <el-form-item label="产品">
          <el-input :model-value="current?.product_name" disabled />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="poForm.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="供应商" required>
          <el-select v-model="poForm.supplier_id" placeholder="请选择供应商" filterable style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.code + ' - ' + s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="单价" required>
          <el-input-number v-model="poForm.unit_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="税率(%)">
          <el-input-number v-model="poForm.tax_rate" :min="0" :max="100" :precision="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预计到货">
          <el-date-picker v-model="poForm.expected_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="poDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirmToPurchase">确认生成采购订单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { purchaseApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchForm = reactive({ keyword: '', status: '' })

function statusType(status) {
  const map = { '待处理': 'warning', '已转单': 'success', '已关闭': 'info' }
  return map[status] || 'info'
}

function resetSearch() {
  searchForm.keyword = ''; searchForm.status = ''
  page.value = 1; fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    const res = await purchaseApi.requisitions.list(params)
    tableData.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

async function handleClose(row) {
  await ElMessageBox.confirm(`确认关闭采购需求「${row.requisition_no}」？关闭后生产可重新推需求。`, '提示', { type: 'warning' })
  try {
    await purchaseApi.requisitions.close(row.id, row.id)
    ElMessage.success('已关闭'); fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

// ============ 转采购订单 ============
const poDialogVisible = ref(false)
const submitting = ref(false)
const current = ref(null)
const suppliers = ref([])
const poForm = reactive({ quantity: 0, supplier_id: null, unit_price: 0, tax_rate: 13, expected_date: null })

function resetPoForm() {
  Object.assign(poForm, { quantity: 0, supplier_id: null, unit_price: 0, tax_rate: 13, expected_date: null })
  current.value = null
}

async function handleToPurchase(row) {
  current.value = row
  poForm.quantity = row.quantity
  try {
    const res = await foundationApi.suppliers.select()
    suppliers.value = Array.isArray(res) ? res : (res.items || [])
  } catch { suppliers.value = [] }
  poDialogVisible.value = true
}

async function confirmToPurchase() {
  if (!poForm.supplier_id) { ElMessage.warning('请选择供应商'); return }
  if (!poForm.quantity || poForm.quantity <= 0) { ElMessage.warning('数量必须大于0'); return }
  submitting.value = true
  try {
    const res = await purchaseApi.requisitions.toPurchase(current.value.id, current.value.id)
    ElMessage.success(`已生成 ${res.purchase_order_no}`)
    poDialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
  finally { submitting.value = false }
}

function openDetail(row) {
  ElMessageBox.alert(
    `需求单号：${row.requisition_no}\n来源生产订单：${row.production_order_no}\n产品：${row.product_code} ${row.product_name}\n数量：${row.quantity}\n状态：${row.status}\n提出人：${row.created_by}${row.remark ? '\n备注：' + row.remark : ''}`,
    '采购需求详情',
    { confirmButtonText: '关闭' }
  )
}

onMounted(fetchData)
</script>
