<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <el-button type="primary" @click="openCreate">新建完工入库</el-button>
    </el-card>

    <el-card>
      <el-table :key="columnVersion" :data="list" v-loading="loading" stripe>
        <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'quantity'" #default="{ row }">{{ $fq(row.quantity) }}</template>
          <template v-else-if="col.prop === 'unit_price'" #default="{ row }">{{ $fm(row.unit_price) }}</template>
          <template v-else-if="col.prop === 'amount'" #default="{ row }">{{ $fm(row.amount) }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="info" size="small" @click="viewDetail(row)">详情</el-button>
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

    <!-- 新建弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建完工入库" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="委外工单" prop="outsourcing_id">
          <el-select v-model="form.outsourcing_id" placeholder="请选择委外工单" filterable style="width: 100%" @change="onOutsourcingChange">
            <el-option v-for="o in outsourcingList" :key="o.id" :label="o.outsourcing_no + ' - ' + o.supplier_name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="产品">
          <el-input :model-value="selectedOutsourcing?.product_name || ''" disabled />
        </el-form-item>
        <el-form-item label="仓库" prop="warehouse_id">
          <el-select v-model="form.warehouse_id" placeholder="请选择仓库" style="width: 100%">
            <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库数量" prop="quantity">
          <el-input type="number" v-model="form.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="入库批次号">
          <el-input v-model="form.batch_no" placeholder="系统自动生成，可手动修改">
            <template #append>
              <el-button @click="generateBatchNo">生成</el-button>
            </template>
          </el-input>
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="完工入库详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="入库单号">{{ detailData.receipt_no }}</el-descriptions-item>
        <el-descriptions-item label="委外工单">{{ detailData.outsourcing_no }}</el-descriptions-item>
        <el-descriptions-item label="产品">{{ detailData.product_name }}</el-descriptions-item>
        <el-descriptions-item label="成品批次号">{{ detailData.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ detailData.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="入库数量">{{ $fq(detailData.quantity) }}</el-descriptions-item>
        <el-descriptions-item label="单价">{{ $fm(detailData.unit_price) }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ $fm(detailData.amount) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(detailData.status)" size="small">{{ statusLabel(detailData.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailData.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailData.remark }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { productionApi } from '@/api/business'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_production_receipt_columns'
const defaultColumns = [
  { prop: 'receipt_no', label: '入库单号', width: 150 },
  { prop: 'outsourcing_no', label: '委外工单', width: 150 },
  { prop: 'product_name', label: '产品', minWidth: 150 },
  { prop: 'batch_no', label: '成品批次号', width: 150 },
  { prop: 'warehouse_name', label: '仓库', width: 100 },
  { prop: 'quantity', label: '入库数量', width: 100, align: 'right' },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right' },
  { prop: 'amount', label: '金额', width: 120, align: 'right' },
  { prop: 'status', label: '状态', width: 90 },
  { prop: 'created_at', label: '创建时间', width: 160 },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY)

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const page = ref(1)
const pageSize = ref(100)
const total = ref(0)
const outsourcingList = ref([])
const warehouseList = ref([])
const selectedOutsourcing = ref(null)

const detailData = ref({})

const form = reactive({
  outsourcing_id: null,
  warehouse_id: null,
  quantity: 1,
  batch_no: '',
  remark: '',
})

const rules = {
  outsourcing_id: [{ required: true, message: '请选择委外工单', trigger: 'change' }],
  warehouse_id: [{ required: true, message: '请选择仓库', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入入库数量', trigger: 'blur' }],
}

onMounted(() => {
  fetchList()
  fetchOutsourcings()
  fetchWarehouses()
})

async function fetchList() {
  loading.value = true
  try {
    const res = await productionApi.outsourceReceipts.list({ page: page.value, page_size: pageSize.value })
    list.value = res.items || res.list || []
    total.value = res.total || 0
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
    nextTick(initColumnDrag)
  }
}

async function fetchOutsourcings() {
  try {
    const res = await productionApi.outsourcings.list({ page: 1, page_size: 100 })
    outsourcingList.value = res.items || []
  } catch {
    outsourcingList.value = []
  }
}

async function fetchWarehouses() {
  try {
    const res = await request.get('/foundation/warehouses').catch(() => ({ items: [] }))
    warehouseList.value = res.items || res.list || []
  } catch {
    warehouseList.value = []
  }
}

function onOutsourcingChange(outsourcingId) {
  selectedOutsourcing.value = outsourcingList.value.find(o => o.id === outsourcingId) || null
  if (selectedOutsourcing.value) {
    form.quantity = selectedOutsourcing.value.quantity || 1
  }
}

function generateBatchNo() {
  const date = new Date()
  const prefix = 'CP'
  const dateStr = `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`
  const random = String(Math.floor(Math.random() * 10000)).padStart(4, '0')
  form.batch_no = `${prefix}${dateStr}${random}`
}

function openCreate() {
  Object.assign(form, { outsourcing_id: null, warehouse_id: null, quantity: 1, batch_no: '', remark: '' })
  selectedOutsourcing.value = null
  generateBatchNo()
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await productionApi.outsourceReceipts.create(form)
    ElMessage.success('完工入库创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

function viewDetail(row) {
  detailData.value = row
  detailVisible.value = true
}

function statusType(status) {
  const map = { pending: 'info', received: 'success', cancelled: 'danger' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { pending: '待入库', received: '已入库', cancelled: '已取消' }
  return map[status] || status
}
</script>
