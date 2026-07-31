<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display:flex;justify-content:flex-end;gap:8px">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建发货</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap:nowrap">
        <el-form-item label="关键词"><el-input v-model="searchForm.keyword" placeholder="发货单号/客户" clearable style="width:160px" @keyup.enter="fetchList" /></el-form-item>
        <el-form-item label="日期范围"><el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width:220px" /></el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :key="columnVersion" :data="list" v-loading="loading" stripe border size="small" style="width:100%">
        <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'quantity'" #default="{ row }">{{ $fq(row.quantity) }}</template>
          <template v-else-if="col.prop === 'unit_price'" #default="{ row }">{{ $fm(row.unit_price) }}</template>
          <template v-else-if="col.prop === 'amount'" #default="{ row }">{{ $fm(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchList" style="margin-top: 12px" />
    </el-card>

    <!-- 新建发货弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建发货" width="750px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="销售订单" required>
          <el-select v-model="form.order_id" placeholder="请选择订单" filterable style="width: 100%" @change="onOrderChange">
            <el-option v-for="o in orderList" :key="o.id" :label="`${o.order_no} - ${o.customer_name}`" :value="o.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="orderItems.length" label="选择产品" required>
          <el-table :data="orderItems.filter(r => r.quantity - (r.delivered_qty||0) > 0)" border highlight-current-row @row-click="onItemRowClick" size="small" style="width: 100%">
            <el-table-column prop="product_name" label="产品名称" />
            <el-table-column label="订单数量" width="100" align="right"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
            <el-table-column label="已发" width="80" align="right"><template #default="{ row }">{{ $fq(row.delivered_qty) }}</template></el-table-column>
            <el-table-column label="未发" width="80" align="right">
              <template #default="{ row }">{{ row.quantity - (row.delivered_qty||0) }}</template>
            </el-table-column>
          </el-table>
        </el-form-item>

        <template v-if="selectedItem">
          <el-divider content-position="left">已选择：{{ selectedItem.product_name }}</el-divider>
          <el-form-item label="单价"><span>{{ $fm(selectedItem.unit_price) }}</span></el-form-item>
          <el-form-item label="批次号" required>
            <el-select v-model="form.batch_no" placeholder="请选择批次" filterable style="width: 100%" :disabled="!selectedItem" @change="onBatchChange">
              <el-option v-for="b in batchList" :key="b.id" :label="`${b.batch_no} (库存${b.quantity})`" :value="b.batch_no" />
            </el-select>
          </el-form-item>
          <el-form-item label="发货数量" required>
            <el-input type="number" v-model="form.quantity" :min="1" :max="selectedItem.quantity - (selectedItem.delivered_qty||0)" style="width: 100%" />
          </el-form-item>
          <el-form-item label="仓库" required>
            <el-select v-model="form.warehouse_id" placeholder="请选择仓库" style="width: 100%">
              <el-option v-for="w in warehouseList" :key="w.id" :label="`${w.code||''} - ${w.name}`" :value="w.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="发货日期" required>
            <el-date-picker v-model="form.delivery_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!form.order_id || !selectedItem" @click="handleSubmit">提交发货</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="发货详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="发货单号">{{ detailData.delivery_no }}</el-descriptions-item>
        <el-descriptions-item label="关联订单">{{ detailData.order_no }}</el-descriptions-item>
        <el-descriptions-item label="产品">{{ detailData.product_name }}</el-descriptions-item>
        <el-descriptions-item label="批次号">{{ detailData.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ $fq(detailData.quantity) }}</el-descriptions-item>
        <el-descriptions-item label="单价">{{ $fm(detailData.unit_price) }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ $fm(detailData.amount) }}</el-descriptions-item>
        <el-descriptions-item label="发货日期">{{ detailData.delivery_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailData.status }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ detailData.remark }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import request from '../../api/request'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_sales_delivery_columns'
const defaultColumns = [
  { prop: 'delivery_no', label: '发货单号', width: 160, sortable: true },
  { prop: 'order_no', label: '关联订单', width: 160, sortable: true },
  { prop: 'product_name', label: '产品', minWidth: 140, sortable: true },
  { prop: 'batch_no', label: '批次号', width: 140, sortable: true },
  { prop: 'quantity', label: '数量', width: 90, align: 'right', sortable: true },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true },
  { prop: 'amount', label: '金额', width: 100, align: 'right', sortable: true },
  { prop: 'delivery_date', label: '发货日期', width: 110, sortable: true },
  { prop: 'status', label: '状态', width: 100, sortable: true },
  { prop: 'created_at', label: '创建时间', width: 160, sortable: true },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY)

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)

const searchForm = reactive({ keyword: '', dateRange: null })

function resetSearch() { searchForm.keyword = ''; searchForm.dateRange = null; page.value = 1; fetchList() }

const dialogVisible = ref(false)
const submitting = ref(false)
const orderList = ref([])
const orderItems = ref([])
const selectedItem = ref(null)
const warehouseList = ref([])
const batchList = ref([])

const form = reactive({
  order_id: null,
  order_item_id: null,
  product_id: null,
  batch_no: '',
  quantity: 1,
  warehouse_id: null,
  delivery_date: '',
  remark: '',
})

const detailVisible = ref(false)
const detailData = ref({})

async function fetchList() {
  loading.value = true
  try {
    const res = await request.get('/sales/deliveries', { params: { page: page.value, page_size: pageSize.value } })
    list.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') } finally { loading.value = false; nextTick(initColumnDrag) }
}

async function fetchOrders() {
  try {
    const res = await request.get('/sales/orders', { params: { page: 1, page_size: 100 } })
    orderList.value = res.items || []
  } catch {}
}

async function fetchWarehouses() {
  try {
    const res = await request.get('/foundation/warehouses', { params: { page: 1, page_size: 100 } })
    warehouseList.value = res.items || []
  } catch {}
}

function openCreate() {
  form.order_id = null; form.order_item_id = null; form.product_id = null
  form.batch_no = ''; form.quantity = 1; form.warehouse_id = null
  form.delivery_date = ''; form.remark = ''
  orderItems.value = []
  selectedItem.value = null
  dialogVisible.value = true
}

async function onOrderChange() {
  if (!form.order_id) return
  try {
    const res = await request.get(`/sales/orders/${form.order_id}`)
    orderItems.value = res.items || []
    selectedItem.value = null
  } catch {}
}

function onItemRowClick(row) {
  selectedItem.value = row
  form.order_item_id = row.id
  form.product_id = row.product_id
  form.quantity = 1
  form.batch_no = ''
  loadBatches(row.product_id)
}

async function loadBatches(productId) {
  if (!productId) { batchList.value = []; return }
  try {
    const res = await request.get('/inventory/available-batches', { params: { product_id: productId } })
    batchList.value = res.items || []
  } catch { batchList.value = [] }
}

function onBatchChange(batchNo) {
  const b = batchList.value.find(x => x.batch_no === batchNo)
  if (b) form.warehouse_id = b.warehouse_id
}

async function handleSubmit() {
  if (!form.order_id || !selectedItem.value) { ElMessage.warning('请选择订单和产品'); return }
  if (!form.batch_no) { ElMessage.warning('请输入批次号'); return }
  submitting.value = true
  try {
    await request.post('/sales/deliveries', { ...form })
    ElMessage.success('发货成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '发货失败') } finally { submitting.value = false }
}

function showDetail(row) {
  detailData.value = row
  detailVisible.value = true
}

onMounted(() => { fetchList(); fetchOrders(); fetchWarehouses() })
</script>
