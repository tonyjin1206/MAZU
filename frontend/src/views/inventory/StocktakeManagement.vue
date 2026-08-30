<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
          <el-button type="primary" @click="openStocktakeCreate">新建盘点</el-button>
          <el-button @click="fetchStocktakes">刷新</el-button>
        </div>
      </template>
      <el-table :key="columnVersion" :data="stocktakeList" v-loading="stocktakeLoading" stripe border>
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="row.status === '已提交' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewStocktake(row)">{{ row.status === '草稿' ? '修改' : '查看' }}</el-button>
            <el-button v-if="row.status === '草稿'" link type="danger" @click="handleDeleteStocktake(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="stocktakePage" v-model:page-size="stocktakePageSize" :total="stocktakeTotal" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next" @size-change="fetchStocktakes" @current-change="fetchStocktakes" style="margin-top: 12px" />
    </el-card>

    <!-- 新建盘点：选仓库 -->
    <el-dialog v-model="stocktakeCreateVisible" title="新建盘点单" width="420px">
      <el-form label-width="80px">
        <el-form-item label="盘点仓库" required>
          <el-select v-model="stocktakeCreateWarehouse" placeholder="选择仓库" style="width: 100%">
            <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stocktakeCreateRemark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stocktakeCreateVisible = false">取消</el-button>
        <el-button type="primary" :loading="stocktakeCreateLoading" @click="handleCreateStocktake">创建并盘点</el-button>
      </template>
    </el-dialog>

    <!-- 盘点明细：录实盘数 -->
    <el-dialog v-model="stocktakeEditVisible" :title="`盘点单 ${stocktakeEditNo}（${stocktakeEditStatus}）`" width="820px">
      <el-alert type="info" :closable="false" style="margin-bottom: 10px"
        title="录入实盘数量后自动保存；提交后按差异生成盘盈/盘亏流水并更新台账，不可再修改" />
      <el-table :data="stocktakeEditItems" v-loading="stocktakeEditLoading" stripe border max-height="420">
        <el-table-column prop="batch_no" label="批次号" width="140" />
        <el-table-column label="物料" min-width="150">
          <template #default="{ row }">{{ row.material_name || row.product_name }}</template>
        </el-table-column>
        <el-table-column label="类型" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.material_id ? 'warning' : 'primary'" size="small">{{ row.material_id ? '原料' : '成品' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="book_qty" label="账面数" width="100" align="right" />
        <el-table-column label="实盘数" width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.actual_qty" :min="0" :controls="false" size="small" style="width: 100%"
              :disabled="stocktakeEditStatus !== '草稿'" @change="(v) => saveStocktakeItem(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="差异" width="110" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.diff_qty > 0 ? '#67c23a' : (row.diff_qty < 0 ? '#f56c6c' : '#909399') }">
              {{ $fq(row.diff_qty) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column v-if="stocktakeEditStatus === '草稿'" label="" width="60" align="center">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="handleRemoveItem(row)">删</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增物料行（草稿） -->
      <div v-if="stocktakeEditStatus === '草稿'" style="margin-top: 12px; padding: 12px; border: 1px dashed #dcdfe6; border-radius: 6px">
        <div style="font-size: 13px; font-weight: 500; margin-bottom: 8px">新增盘点物料（支持账外批次：账面 0，实盘填实际数 → 提交自动盘盈入账）</div>
        <el-form :inline="true" label-width="70px">
          <el-form-item label="类型">
            <el-radio-group v-model="addItemForm.type" size="small">
              <el-radio-button value="material">原料</el-radio-button>
              <el-radio-button value="product">成品</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="物料">
            <el-select v-model="addItemForm.material_id" filterable clearable placeholder="选择原料" style="width: 180px" size="small" :disabled="addItemForm.type !== 'material'">
              <el-option v-for="m in materialList" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
            </el-select>
            <el-select v-model="addItemForm.product_id" filterable clearable placeholder="选择成品" style="width: 180px" size="small" :disabled="addItemForm.type !== 'product'">
              <el-option v-for="p in productList" :key="p.id" :label="`${p.name_cn} (${p.code})`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="批次号">
            <el-input v-model="addItemForm.batch_no" placeholder="如 PD20260801-001" style="width: 160px" size="small" />
          </el-form-item>
          <el-form-item label="实盘数">
            <el-input-number v-model="addItemForm.actual_qty" :min="0" :controls="false" style="width: 120px" size="small" />
          </el-form-item>
          <el-form-item label="成本">
            <el-input-number v-model="addItemForm.unit_cost" :min="0" :controls="false" style="width: 100px" size="small" placeholder="账外批次必填" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" :loading="addItemLoading" @click="handleAddItem">添加</el-button>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="stocktakeEditVisible = false">关闭</el-button>
        <el-button v-if="stocktakeEditStatus === '草稿'" type="primary" :loading="stocktakeSubmitting" @click="handleSubmitStocktake">提交盘点</el-button>
      </template>
    </el-dialog>
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import { inventoryApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

// ===== 列配置 =====
const STORAGE_KEY = 'mazu_stocktake_columns'
const defaultColumns = [
  { prop: 'stocktake_no', label: '盘点单号', width: 170, sortable: true },
  { prop: 'warehouse_name', label: '仓库', width: 120, sortable: true },
  { prop: 'status', label: '状态', width: 100, sortable: true },
  { prop: 'item_count', label: '明细项', width: 80, align: 'center', sortable: true },
  { prop: 'operator', label: '盘点人', width: 110, sortable: true },
  { prop: 'remark', label: '备注', minWidth: 140, sortable: true },
  { prop: 'created_at', label: '创建时间', width: 160, sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const warehouseList = ref([])
const materialList = ref([])
const productList = ref([])

// ===== 盘点单列表 =====
const stocktakeList = ref([])
const stocktakeLoading = ref(false)
const stocktakeTotal = ref(0)
const stocktakePage = ref(1)
const stocktakePageSize = ref(10)

async function fetchStocktakes() {
  stocktakeLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.list({ page: stocktakePage.value, page_size: stocktakePageSize.value })
    stocktakeList.value = res.items || []
    stocktakeTotal.value = res.total || 0
  } catch (e) { ElMessage.error('加载盘点单失败') } finally { stocktakeLoading.value = false; nextTick(initColumnDrag) }
}

// ===== 新建盘点 =====
const stocktakeCreateVisible = ref(false)
const stocktakeCreateWarehouse = ref(null)
const stocktakeCreateRemark = ref('')
const stocktakeCreateLoading = ref(false)

function openStocktakeCreate() {
  stocktakeCreateWarehouse.value = null
  stocktakeCreateRemark.value = ''
  stocktakeCreateVisible.value = true
}

async function handleCreateStocktake() {
  if (!stocktakeCreateWarehouse.value) { ElMessage.warning('请选择盘点仓库'); return }
  stocktakeCreateLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.create({
      warehouse_id: stocktakeCreateWarehouse.value,
      remark: stocktakeCreateRemark.value,
    })
    ElMessage.success(res.message || '盘点单已创建')
    stocktakeCreateVisible.value = false
    fetchStocktakes()
    openStocktakeEdit(res.id)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') } finally { stocktakeCreateLoading.value = false }
}

// ===== 盘点明细 =====
const stocktakeEditVisible = ref(false)
const stocktakeEditLoading = ref(false)
const stocktakeEditItems = ref([])
const stocktakeEditNo = ref('')
const stocktakeEditStatus = ref('')
const stocktakeEditId = ref(null)
const stocktakeSubmitting = ref(false)

async function openStocktakeEdit(id) {
  stocktakeEditVisible.value = true
  stocktakeEditLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.get(id)
    stocktakeEditId.value = res.id
    stocktakeEditNo.value = res.stocktake_no
    stocktakeEditStatus.value = res.status
    stocktakeEditItems.value = res.items || []
  } catch (e) { ElMessage.error('加载盘点明细失败') } finally { stocktakeEditLoading.value = false }
}

function viewStocktake(row) { openStocktakeEdit(row.id) }

async function saveStocktakeItem(item, val) {
  if (stocktakeEditStatus.value !== '草稿') return
  try {
    await inventoryApi.stocktakes.updateItem(stocktakeEditId.value, item.id, { actual_qty: val ?? 0 })
    item.diff_qty = Math.round(((val ?? 0) - item.book_qty) * 10000) / 10000
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存实盘数失败')
    item.actual_qty = item.book_qty
  }
}

async function handleSubmitStocktake() {
  await ElMessageBox.confirm('提交后按差异生成盘盈/盘亏流水并更新台账，且不可修改/删除。确定提交？', '提交盘点', { type: 'warning' })
  stocktakeSubmitting.value = true
  try {
    const res = await inventoryApi.stocktakes.submit(stocktakeEditId.value)
    ElMessage.success(res.message || '盘点已提交')
    stocktakeEditVisible.value = false
    fetchStocktakes()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '提交失败') } finally { stocktakeSubmitting.value = false }
}

async function handleDeleteStocktake(row) {
  await ElMessageBox.confirm(`删除盘点单 ${row.stocktake_no}？`, '提示', { type: 'warning' })
  try {
    await inventoryApi.stocktakes.remove(row.id)
    ElMessage.success('盘点单已删除')
    fetchStocktakes()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

// ===== 新增/删除明细行 =====
const addItemForm = ref({ type: 'material', material_id: null, product_id: null, batch_no: '', actual_qty: 0, unit_cost: 0 })
const addItemLoading = ref(false)

async function handleAddItem() {
  const f = addItemForm.value
  const payload = {
    batch_no: f.batch_no.trim(),
    actual_qty: f.actual_qty,
    unit_cost: f.unit_cost,
  }
  if (f.type === 'material') {
    if (!f.material_id) { ElMessage.warning('请选择原料'); return }
    payload.material_id = f.material_id
  } else {
    if (!f.product_id) { ElMessage.warning('请选择成品'); return }
    payload.product_id = f.product_id
  }
  if (!payload.batch_no) { ElMessage.warning('请填写批次号'); return }
  addItemLoading.value = true
  try {
    const res = await inventoryApi.stocktakes.addItem(stocktakeEditId.value, payload)
    ElMessage.success(res.message || '已添加')
    // 刷新明细（账面数由后端计算）
    const detail = await inventoryApi.stocktakes.get(stocktakeEditId.value)
    stocktakeEditItems.value = detail.items || []
    addItemForm.value = { type: 'material', material_id: null, product_id: null, batch_no: '', actual_qty: 0, unit_cost: 0 }
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') } finally { addItemLoading.value = false }
}

async function handleRemoveItem(row) {
  await ElMessageBox.confirm(`删除盘点行（批次 ${row.batch_no}）？`, '提示', { type: 'warning' })
  try {
    await inventoryApi.stocktakes.removeItem(stocktakeEditId.value, row.id)
    ElMessage.success('已删除')
    const detail = await inventoryApi.stocktakes.get(stocktakeEditId.value)
    stocktakeEditItems.value = detail.items || []
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

onMounted(() => {
  foundationApi.warehouses.list({ page_size: 50 }).then(res => {
    warehouseList.value = res.items || []
  }).catch(() => {})
  foundationApi.materials.list({ page_size: 200 }).then(res => {
    materialList.value = res.items || []
  }).catch(() => {})
  foundationApi.products.list({ page_size: 200 }).then(res => {
    productList.value = res.items || []
  }).catch(() => {})
  fetchStocktakes()
})
</script>

<style scoped>
:deep(.el-table) { table-layout: auto; }
:deep(.el-table .cell) { white-space: nowrap; }
</style>
