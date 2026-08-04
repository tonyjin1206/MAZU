<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <el-button type="primary" @click="openCreate">新建委外工单</el-button>
    </el-card>
    <el-card>
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table :key="columnVersion" :data="list" v-loading="loading" stripe>
        <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'quantity'" #default="{ row }">{{ $fq(row.quantity) }}</template>
          <template v-else-if="col.prop === 'unit_price'" #default="{ row }">{{ $fm(row.unit_price) }}</template>
          <template v-else-if="col.prop === 'total_amount'" #default="{ row }">{{ $fm(row.total_amount) }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div style="display: flex; gap: 4px; white-space: nowrap">
              <el-button v-if="row.status === '待发料'" type="primary" size="small" @click="emitMaterial(row)">发料</el-button>
              <el-button v-if="row.status === '待发料'" type="warning" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="row.status === '待发料'" type="danger" size="small" @click="handleDelete(row)">删除</el-button>
              <el-button v-if="row.status === '已发料'" type="success" size="small" @click="receiveProduct(row)">入库</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @size-change="fetchList" @current-change="fetchList" style="margin-top: 12px" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新建委外工单' : '编辑委外工单'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item v-if="form.production_id" label="生产订单">
          <el-input :model-value="'MO-' + form.production_id" disabled style="width: 100%" />
        </el-form-item>
        <el-form-item label="产品" prop="product_id">
          <el-select v-model="form.product_id" placeholder="请选择产品" filterable style="width: 100%" :disabled="!!form.production_id">
            <el-option v-for="p in productList" :key="p.id" :label="`${p.code} - ${p.name_cn}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="委外商" prop="supplier_id">
          <el-select v-model="form.supplier_id" placeholder="请选择委外商" filterable style="width: 100%">
            <el-option v-for="s in outsourcerList" :key="s.id" :label="`${s.code || ''} - ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工序" prop="process_id">
          <el-select v-model="form.process_id" placeholder="请选择工序" style="width: 100%">
            <el-option v-for="p in processList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input type="number" v-model="form.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="加工单价" prop="unit_price">
          <el-input type="number" v-model="form.unit_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="交期" prop="due_date">
          <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" placeholder="选填" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { productionApi } from '@/api/business'
import { foundationApi } from '@/api/foundation'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_outsourcing_columns'
const defaultColumns = [
  { prop: 'outsource_no', label: '委外工单号', width: 160, sortable: true },
  { prop: 'outsourcer_name', label: '委外商', minWidth: 150, sortable: true },
  { prop: 'product_name', label: '产品', minWidth: 150, sortable: true },
  { prop: 'quantity', label: '数量', width: 80, align: 'right', sortable: true },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true },
  { prop: 'total_amount', label: '金额', width: 120, align: 'right', sortable: true },
  { prop: 'status', label: '状态', width: 115, sortable: true },
  { prop: 'due_date', label: '交期', width: 110, sortable: true },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY)

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const submitting = ref(false)
const formRef = ref(null)
const page = ref(1)
const pageSize = ref(100)
const total = ref(0)
const outsourcerList = ref([])
const productList = ref([])
const processList = ref([])

const form = reactive({
  supplier_id: null, product_id: route.query.product_id ? parseInt(route.query.product_id) : null,
  process_id: null,
  quantity: 1, unit_price: 0, due_date: '', remark: '',
  production_id: route.query.production_id ? parseInt(route.query.production_id) : null,
})

const rules = {
  supplier_id: [{ required: true, message: '请选择委外商', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择产品', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

function statusType(s) {
  return { '待发料': 'info', '已发料': 'success', '加工中': 'warning', '已入库': 'success', '已完成': 'success', '已关闭': 'danger' }[s] || 'info'
}

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (route.query.production_id) params.production_id = route.query.production_id
    const res = await productionApi.outsourcings.list(params)
    list.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
    nextTick(initColumnDrag)
  }
}

async function fetchOutsourcers() {
  try {
    // 从供应商表取所有活跃供应商作为委外商选项
    const res = await foundationApi.suppliers.list({ page_size: 200 })
    const all = res.items || []
    outsourcerList.value = all.filter(s => s.is_active !== 0).map(s => ({
      id: s.id,
      supplier_id: s.id,
      code: s.code,
      name: s.name,
    }))
  } catch {}
}

async function fetchProducts() {
  try {
    const res = await foundationApi.products.list({ page: 1, page_size: 200 })
    productList.value = res.items || []
  } catch {}
}

async function fetchProcesses() {
  try {
    const res = await foundationApi.processes.list({ page: 1, page_size: 200 })
    processList.value = res.items || []
  } catch {}
}

function openCreate() {
  dialogMode.value = 'create'
  if (!form.production_id) {
    form.supplier_id = null; form.product_id = null; form.process_id = null
    form.quantity = 1; form.unit_price = 0; form.due_date = ''
    form.remark = ''
  }
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  form.id = row.id
  form.supplier_id = row.supplier_id || row.outsourcer_id
  form.product_id = row.product_id
  form.process_id = row.process_id
  form.quantity = row.quantity
  form.unit_price = row.unit_price
  form.due_date = row.due_date || ''
  form.remark = row.remark || ''
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await productionApi.outsourcings.create(form)
      ElMessage.success('委外工单创建成功')
    } else {
      await productionApi.outsourcings.update(form.id, form)
      ElMessage.success('委外工单已更新')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除委外工单「${row.outsource_no}」？`, '提示', { type: 'warning' })
  await productionApi.outsourcings.delete(row.id)
  ElMessage.success('已删除')
  fetchList()
}

function emitMaterial(row) {
  router.push(`/production/inventory?action=issue&outsource_id=${row.id}`)
}

function receiveProduct(row) {
  router.push(`/production/receipts?outsource_id=${row.id}`)
}

onMounted(() => {
  fetchList()
  fetchOutsourcers()
  fetchProducts()
  fetchProcesses()
  // 从生产订单跳转过来时自动弹出新建窗口
  if (form.production_id) {
    openCreate()
  }
})
</script>
