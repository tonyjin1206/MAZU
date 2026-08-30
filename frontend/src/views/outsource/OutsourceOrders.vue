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
        <el-form-item label="关键字">
          <el-input v-model="searchForm.keyword" placeholder="委外单号/产品" clearable style="width: 170px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="待确认" value="待确认" />
            <el-option label="已审核" value="已审核" />
            <el-option label="已完工" value="已完工" />
            <el-option label="已入库" value="已入库" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef" :key="columnVersion" :data="dataList" v-loading="loading" stripe border size="small" show-summary :summary-method="getSummary" style="width: 100%">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <el-dropdown trigger="contextmenu" :hide-on-click="false">
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="c in allColumns" :key="c.prop">
                    <el-checkbox :model-value="c.visible !== false" @change="toggleColumn(c)">{{ c.label }}</el-checkbox>
                  </el-dropdown-item>
                                  <el-dropdown-item @click.stop="openColumnSettings" style="color: #409eff">列设置...</el-dropdown-item>
</el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'quantity' || col.prop === 'received_qty'" #default="{ row }">{{ row[col.prop] || 0 }}</template>
          <template v-else-if="col.prop === 'unit_price' || col.prop === 'amount'" #default="{ row }">{{ $fm(row[col.prop]) }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待确认'" link type="primary" @click="openEdit(row)">维护</el-button>
            <el-button v-if="row.status === '待确认'" link type="success" @click="handleApprove(row)">审核</el-button>
            <el-button v-if="row.status === '待确认'" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button v-if="row.status === '已审核'" link type="warning" @click="handleUnapprove(row)">取消审核</el-button>
            <el-button link @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 16px" />
    </el-card>

    <!-- 维护弹窗（委外商/加工单价/交期） -->
    <el-dialog v-model="editVisible" title="维护委外订单" width="520px" destroy-on-close>
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="委外单号"><el-input :model-value="editForm.outsource_no" readonly /></el-form-item>
        <el-form-item label="产品"><el-input :model-value="`${editForm.product_code || ''} ${editForm.product_name || ''}`" readonly /></el-form-item>
        <el-form-item label="数量"><span>{{ editForm.quantity }}</span></el-form-item>
        <el-form-item label="委外商" required>
          <el-select v-model="editForm.outsourcer_id" placeholder="选择委外商（供应商）" filterable style="width: 100%">
            <el-option v-for="s in supplierList" :key="s.id" :label="`${s.code || ''} - ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="加工单价" required>
          <el-input-number v-model="editForm.unit_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="约定交期">
          <el-date-picker v-model="editForm.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
        <div style="color: #909399; font-size: 12px">审核后生成加工费应付账款，并自动生成待入库单；收货请到「库存管理 → 成品入库」办理。</div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="委外订单详情" width="520px" destroy-on-close>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="委外单号">{{ detailForm.outsource_no }}</el-descriptions-item>
        <el-descriptions-item label="来源销售单">{{ detailForm.sales_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="产品">{{ `${detailForm.product_code || ''} ${detailForm.product_name || ''}` }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ detailForm.quantity }}</el-descriptions-item>
        <el-descriptions-item label="委外商">{{ detailForm.outsourcer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="加工单价">{{ $fm(detailForm.unit_price) }}</el-descriptions-item>
        <el-descriptions-item label="加工费金额">{{ $fm(detailForm.amount) }}</el-descriptions-item>
        <el-descriptions-item label="约定交期">{{ detailForm.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(detailForm.status)" size="small">{{ detailForm.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注">{{ detailForm.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
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
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { purchaseApi, outsourceApi, inventoryApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_outsource_order_columns'
const defaultColumns = [
  { prop: 'outsource_no', label: '委外单号', width: 150, sortable: true },
  { prop: 'sales_order_no', label: '销售订单号', minWidth: 130, sortable: true },
  { prop: 'product_code', label: '产品编码', minWidth: 110, sortable: true },
  { prop: 'product_name', label: '产品名称', minWidth: 140, sortable: true },
  { prop: 'quantity', label: '数量', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'received_qty', label: '已入库', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'outsourcer_name', label: '委外商', minWidth: 120, sortable: true },
  { prop: 'unit_price', label: '加工单价', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'amount', label: '加工费', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'due_date', label: '交期', width: 100, sortable: true },
  { prop: 'status', label: '状态', width: 90, align: 'center', sortable: true, fmt: 'tag' },
]
const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings: openColumnSettingsRaw, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const tableRef = ref(null)
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

// ===== 列设置弹窗（注入当前显隐状态）=====
function openColumnSettings() {
  const visMap = {}
  for (const c of allColumns.value) visMap[c.prop] = c.visible !== false
  openColumnSettingsRaw(visMap)
}

const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })
const searchForm = reactive({ keyword: '', status: '' })
const supplierList = ref([])

function resetSearch() {
  searchForm.keyword = ''
  searchForm.status = ''
  queryParams.page = 1
  fetchData()
}

function statusType(status) {
  const map = { '待确认': 'info', '已审核': 'success', '已完工': 'success', '已入库': 'success', '已退回': 'danger' }
  return map[status] || 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status
    const res = await outsourceApi.orders.list(params)
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载数据失败') } finally { loading.value = false; nextTick(() => { initColumnDrag(); fitTable(tableRef.value, visibleColumns, dataList) }) }
}

async function loadSuppliers() {
  try {
    const res = await foundationApi.suppliers.list({ page: 1, page_size: 100 })
    supplierList.value = res.items || []
  } catch (e) {}
}

// ========== 维护 ==========
const editVisible = ref(false)
const submitting = ref(false)
const editForm = reactive({ id: null, outsource_no: '', product_code: '', product_name: '', quantity: 0, outsourcer_id: null, unit_price: 0, due_date: '', remark: '' })

function openEdit(row) {
  Object.assign(editForm, {
    id: row.id, outsource_no: row.outsource_no,
    product_code: row.product_code, product_name: row.product_name,
    quantity: row.quantity, outsourcer_id: row.outsourcer_id || null,
    unit_price: row.unit_price || 0, due_date: row.due_date || '', remark: row.remark || '',
  })
  if (!supplierList.value.length) loadSuppliers()
  editVisible.value = true
}

async function handleSave() {
  if (!editForm.outsourcer_id) { ElMessage.warning('请选择委外商'); return }
  if (!editForm.unit_price || editForm.unit_price <= 0) { ElMessage.warning('请填写加工单价'); return }
  submitting.value = true
  try {
    const res = await outsourceApi.orders.update(editForm.id, {
      outsourcer_id: editForm.outsourcer_id,
      unit_price: parseFloat(editForm.unit_price) || 0,
      due_date: editForm.due_date || null,
      remark: editForm.remark || '',
    })
    ElMessage.success(res.message || '保存成功')
    editVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { submitting.value = false }
}

// ========== 审核 / 完工 / 删除 / 详情 ==========
async function handleApprove(row) {
  await ElMessageBox.confirm(`审核委外订单 ${row.outsource_no}？审核后生成加工费应付账款 ${row.quantity} × ${row.unit_price}。`, '提示', { type: 'info' })
  try {
    const res = await outsourceApi.orders.approve(row.id)
    ElMessage.success(res.message || '已审核')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审核失败') }
}

async function handleDelete(row) {
  const matCount = new Set((row.materials || []).map(m => m.material_id)).size
  const matTip = matCount > 0 ? `该单已认领 ${matCount} 种材料，删除后材料将退回原批次。` : ''
  await ElMessageBox.confirm(`确定删除委外订单 ${row.outsource_no}？${matTip}删除后销售明细行回到「未生产」。`, '提示', { type: 'warning' })
  try {
    const res = await outsourceApi.orders.remove(row.id)
    ElMessage.success(res.message || '已删除')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

async function handleUnapprove(row) {
  await ElMessageBox.confirm(`确定取消审核委外订单 ${row.outsource_no}？取消后可修改或删除。`, '提示', { type: 'warning' })
  try {
    const res = await outsourceApi.orders.unapprove(row.id)
    ElMessage.success(res.message || '已取消审核')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

const detailVisible = ref(false)
const detailForm = reactive({})

async function openDetail(row) {
  try {
    const res = await outsourceApi.orders.get(row.id)
    Object.assign(detailForm, res)
  } catch (e) {}
  detailVisible.value = true
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnVisible(); initColumnDrag() })
})

onMounted(() => { initColumnVisible(); fetchData(); loadSuppliers() })

function getSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => { sums[i] = '' })
  const qtyCols = ['quantity', 'received_qty']
  qtyCols.forEach(prop => {
    const idx = columns.findIndex(c => c.prop === prop)
    if (idx >= 0) sums[idx] = data.reduce((s, r) => s + (Number(r[prop]) || 0), 0)
  })
  if (data.length > 0) sums[0] = '合计'
  return sums
}
</script>
