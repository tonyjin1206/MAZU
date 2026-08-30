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
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef" :key="columnVersion" :data="list" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align" :show-overflow-tooltip="col.prop === 'remark'">
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
            <span :style="{ color: row.amount < 0 ? '#f56c6c' : '' }">{{ $fm(row.amount) }}</span>
            <el-tag v-if="row.amount < 0" type="danger" size="small" style="margin-left: 4px">退款</el-tag>
          </template>
          <template v-else-if="col.prop === 'allocated_amount'" #default="{ row }">{{ $fm(row.allocated_amount) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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
        <el-descriptions-item label="金额"><span :style="{ color: detail.amount < 0 ? '#f56c6c' : '', fontWeight: 'bold' }">{{ $fm(detail.amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="外币金额">{{ $fm(detail.amount_fc) }}</el-descriptions-item>
        <el-descriptions-item label="付款方式">{{ detail.payment_method }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ detail.operator }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">
          <div style="width: 100%; white-space: pre-wrap">{{ detail.remark || '-' }}</div>
        </el-descriptions-item>
      </el-descriptions>
      <el-divider>核销明细</el-divider>
      <el-table :data="detail?.allocations || []" stripe size="small" v-if="detail?.allocations?.length">
        <el-table-column prop="ar_no" label="应收单号" width="160" sortable />
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
            <el-option v-for="o in paymentMethodOptions" :key="o.key" :label="o.label" :value="o.label" />
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
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { salesApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'

// 付款方式选项（来自参数设置）
const tableRef = ref(null)
const paymentMethodOptions = ref([])
async function loadPaymentMethods() {
  try { paymentMethodOptions.value = await foundationApi.params.options({ group: 'payment_method' }) || [] } catch (e) { paymentMethodOptions.value = [] }
}

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_collection_columns'
const defaultColumns = [
  { prop: 'collection_no', label: '收款单号', width: 160, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 150, sortable: true },
  { prop: 'collection_date', label: '收款日期', width: 120, sortable: true },
  { prop: 'amount', label: '金额', width: 120, align: 'right', sortable: true },
  { prop: 'allocated_amount', label: '核销金额', width: 120, align: 'right', sortable: true },
  { prop: 'payment_method', label: '付款方式', width: 100, sortable: true },
  { prop: 'operator', label: '操作人', width: 90, sortable: true },
  { prop: 'remark', label: '备注', minWidth: 140, sortable: true },
]
const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

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

function resetSearch() { searchForm.keyword = ''; searchForm.dateRange = null; page.value = 1; fetchList() }

const editForm = reactive({
  id: null, collection_no: '', customer_name: '', amount: 0,
  collection_date: '', payment_method: '银行转账', remark: '',
})


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(fetchList)
loadPaymentMethods()

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) { params.start_date = searchForm.dateRange[0]; params.end_date = searchForm.dateRange[1] }
    const res = await salesApi.collections.list(params)
    list.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') }
  finally { loading.value = false; nextTick(initColumnDrag) }
}

async function openDetail(row) {
  try {
    const res = await salesApi.collections.get(row.id)
    detail.value = res
    detailVisible.value = true
  } catch (e) { ElMessage.error('加载详情失败') }
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
    await salesApi.collections.update(editForm.id, {
      collection_date: editForm.collection_date,
      payment_method: editForm.payment_method,
      remark: editForm.remark,
    })
    ElMessage.success('修改成功')
    editVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '修改失败') }
  finally { submitting.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确定删除收款单 ${row.collection_no}？应收金额将同步回滚。`,
    '提示', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  try {
    await salesApi.collections.delete(row.id)
    ElMessage.success('删除成功，应收已回滚')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

// ===== 审核锁定（财务确认标记，审核后业务全部锁定） =====
async function handleReview(row) {
  await ElMessageBox.confirm(
    `审核收款单 ${row.collection_no}？审核后该单据不可修改/删除（财务确认，业务锁定），只能取消审核。`,
    '收款单审核', { type: 'warning', confirmButtonText: '确认审核', cancelButtonText: '取消' }
  )
  try {
    const res = await salesApi.collections.review(row.id)
    ElMessage.success(res.message || '审核成功')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审核失败') }
}

async function handleUnreview(row) {
  await ElMessageBox.confirm(
    `取消审核收款单 ${row.collection_no}？取消后该单据可修改/删除。`,
    '取消审核', { type: 'warning', confirmButtonText: '确认取消审核', cancelButtonText: '再想想' }
  )
  try {
    const res = await salesApi.collections.unreview(row.id)
    ElMessage.success(res.message || '已取消审核')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}
</script>
