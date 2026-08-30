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
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef" :key="columnVersion" :data="list" v-loading="loading" stripe>
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
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
          <template v-if="col.prop === 'declare_amount'" #default="{ row }">{{ $fm(row.declare_amount) }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
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
        <el-form-item label="商品行" required>
          <el-table :data="form.items" size="small" border max-height="260" style="width: 100%">
            <el-table-column label="商品" min-width="150">
              <template #default="{ row }">
                <span>{{ row.product_name || ('商品#' + row.product_id) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="HS编码" min-width="200">
              <template #default="{ row }">
                <el-select v-model="row.hs_code_id" placeholder="选择HS" filterable size="small" style="width: 100%">
                  <el-option v-for="h in hsCodeList" :key="h.id"
                             :label="h.hs_code + ' - ' + (h.name_cn || h.name || '')" :value="h.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="110">
              <template #default="{ row }">
                <el-input-number v-model="row.quantity" :min="0.01" size="small" style="width: 100%" @change="calcItemAmount(row)" />
              </template>
            </el-table-column>
            <el-table-column label="单价" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" style="width: 100%" @change="calcItemAmount(row)" />
              </template>
            </el-table-column>
            <el-table-column label="报关金额" width="130" align="right">
              <template #default="{ row }">{{ $fm(row.declare_amount || 0) }}</template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 6px; color: #909399; font-size: 12px">
            选择订单后自动带出商品明细；可修改 HS/数量/单价，报关金额自动计算。
          </div>
        </el-form-item>
        <el-form-item label="报关金额">
          <el-input :model-value="$fm(form.declare_amount)" disabled style="width: 100%" />
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
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsListDlg" @confirm="confirmSettings" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { salesApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_customs_declaration_columns'
const defaultColumns = [
  { prop: 'customs_no', label: '报关单号', width: 160, sortable: true },
  { prop: 'order_no', label: '关联订单', width: 140, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 130, sortable: true },
  { prop: 'hs_code', label: 'HS编码', width: 120, sortable: true },
  { prop: 'declare_amount', label: '报关金额', width: 120, align: 'right', sortable: true },
  { prop: 'currency_code', label: '币种', width: 90, sortable: true },
  { prop: 'customs_broker', label: '报关行', minWidth: 120, sortable: true },
  { prop: 'declare_date', label: '报关日期', width: 100, sortable: true },
  { prop: 'status', label: '状态', width: 100, sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList: settingsListDlg, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const tableRef = ref(null)
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
  page.value = 1
  fetchList()
}

const orderList = ref([])
const hsCodeList = ref([])
const currencyList = ref([])

const form = reactive({
  customs_no: '',
  order_id: null,
  declare_amount: 0,
  declare_currency: null,
  declare_date: '',
  customs_broker: '',
  remark: '',
  items: [],
})

const rules = {
  customs_no: [{ required: true, message: '请输入报关单号', trigger: 'blur' }],
  order_id: [{ required: true, message: '请选择销售订单', trigger: 'change' }],
  declare_currency: [{ required: true, message: '请选择币种', trigger: 'change' }],
  declare_date: [{ required: true, message: '请选择报关日期', trigger: 'change' }],
  customs_broker: [{ required: true, message: '请输入报关行', trigger: 'blur' }],
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

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
    const res = await salesApi.customs.list(params)
    list.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') }
  finally { loading.value = false; nextTick(initColumnDrag) }
}

async function fetchOrders() {
  try {
    const res = await salesApi.orders.list({ page: 1, page_size: 100 })
    orderList.value = res.items || []
  } catch (e) {}
}

async function fetchHsCodes() {
  try {
    const res = await foundationApi.hsCodes.list({ page: 1, page_size: 200 })
    hsCodeList.value = res.items || res.list || []
  } catch (e) {}
}

async function fetchCurrencies() {
  try {
    const res = await foundationApi.currencies.list({ page: 1, page_size: 50 })
    currencyList.value = (res.items || res.list || []).filter(c => c.is_active !== 0)
  } catch (e) {}
}

function onOrderChange(orderId) {
  const o = orderList.value.find(x => x.id === orderId)
  if (o) {
    if (!form.declare_currency) form.declare_currency = o.currency_id || null
    // 带出订单明细商品行（HS 默认产品档案，后端再兜底）
    salesApi.orders.get(orderId).then(res => {
      form.items = (res.items || []).map(it => ({
        product_id: it.product_id,
        product_name: it.product_name,
        hs_code_id: it.hs_code_id || null,
        quantity: it.quantity || 0,
        unit_price: it.unit_price || 0,
        declare_amount: Math.round((it.quantity || 0) * (it.unit_price || 0) * 100) / 100,
      }))
      calcTotalAmount()
    }).catch(() => {})
  }
}

function calcItemAmount(row) {
  row.declare_amount = Math.round(((row.quantity || 0) * (row.unit_price || 0)) * 100) / 100
  calcTotalAmount()
}

function calcTotalAmount() {
  form.declare_amount = Math.round((form.items || []).reduce((s, it) => s + (it.declare_amount || 0), 0) * 100) / 100
}

function openCreate() {
  editMode.value = false
  Object.assign(form, { id: null, customs_no: '', order_id: null, declare_amount: 0, declare_currency: null, declare_date: '', customs_broker: '', remark: '', items: [] })
  dialogVisible.value = true
}

async function openEdit(row) {
  editMode.value = true
  try {
    const res = await salesApi.customs.get(row.id)
    Object.assign(form, {
      id: res.id, customs_no: res.customs_no, order_id: res.order_id,
      declare_amount: res.declare_amount,
      declare_currency: res.declare_currency, declare_date: res.declare_date,
      customs_broker: res.customs_broker, remark: res.remark || '',
      items: (res.items || []).map(it => ({
        product_id: it.product_id, product_name: it.product_name,
        hs_code_id: it.hs_code_id, quantity: it.quantity,
        unit_price: it.unit_price, declare_amount: it.declare_amount,
      })),
    })
    dialogVisible.value = true
  } catch (e) { ElMessage.error('加载详情失败') }
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editMode.value) {
      await salesApi.customs.update(form.id, { ...form })
      ElMessage.success('修改成功')
    } else {
      await salesApi.customs.create({ ...form })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { submitting.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除报关单 ${row.customs_no}？`, '提示', { type: 'warning' })
  try {
    await salesApi.customs.delete(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

function statusType(status) {
  const map = { 已报关: 'success', 已放行: 'success', 已结关: 'success', 已取消: 'danger' }
  return map[status] || 'info'
}
function statusLabel(status) {
  const map = { 已报关: '已报关', 已放行: '已放行', 已结关: '已结关', 已取消: '已取消' }
  return map[status] || status
}
</script>
