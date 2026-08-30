<template>
  <div>
    <!-- 顶部：全部产品列表 -->
    <el-card style="margin-bottom: 12px">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px">
        <el-input v-model="productKeyword" placeholder="按编码/名称搜索" clearable style="flex: 1" />
        <el-button @click="fetchProducts">刷新</el-button>
      </div>
      <el-table
        ref="productTableRef"
        :data="filteredProducts"
        v-loading="productLoading"
        stripe
        border
        size="small"
        style="width: 100%"
        :height="tableHeight"
        highlight-current-row
        :row-key="row => row.id"
        @row-click="onProductSelect"
      >
        <el-table-column prop="code" label="编码" width="120" sortable />
        <el-table-column prop="name" label="名称" min-width="120" sortable />
        <el-table-column prop="spec" label="规格" min-width="100" show-overflow-tooltip sortable>
          <template #default="{ row }">{{ row.spec || '-' }}</template>
        </el-table-column>
        <el-table-column prop="model" label="型号" min-width="100" show-overflow-tooltip sortable>
          <template #default="{ row }">{{ row.model || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上下区域分隔条：可拖动调整上面产品列表高度 -->
    <div class="bom-divider" @mousedown="startDrag" title="拖动调整高度"></div>

    <!-- 下面：组成材料 / 工艺流程 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
          <el-tabs v-model="rightTab" class="header-tabs" size="small">
            <el-tab-pane label="组成材料" name="bom" />
            <el-tab-pane label="工艺流程" name="process" />
          </el-tabs>
          <el-button v-if="rightTab === 'bom'" type="primary" :disabled="!selectedProductId" @click="openDialog('create')">新增材料</el-button>
          <el-button v-else type="primary" :disabled="!selectedProductId" @click="openProcessDialog">添加工序</el-button>
        </div>
      </template>
      <div v-if="!selectedProductId" style="text-align: center; color: #909399; padding: 40px">请先选择产品查看 BOM</div>
      <el-table v-else-if="rightTab === 'bom'" :data="bomData" v-loading="bomLoading" stripe border size="small" style="width: 100%">
        <el-table-column prop="material_code" label="材料编码" width="120" sortable />
        <el-table-column prop="material_name" label="材料名称" min-width="140" sortable />
        <el-table-column prop="material_spec" label="规格" min-width="120" sortable />
        <el-table-column prop="material_unit" label="单位" width="70" align="center" sortable />
        <el-table-column label="用量" width="80" align="center"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
        <el-table-column prop="loss_rate" label="损耗率(%)" width="100" align="center" sortable />
        <el-table-column prop="process_name" label="工序" width="120" sortable />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-table v-else :data="processData" v-loading="processLoading" stripe border size="small" style="width: 100%">
        <el-table-column prop="process_code" label="工序编码" width="120" sortable />
        <el-table-column prop="process_name" label="工序名称" min-width="140" sortable />
        <el-table-column label="默认加工单价" width="120" align="center"><template #default="{ row }">{{ $fq(row.default_unit_price) }}</template></el-table-column>
        <el-table-column prop="supplier_name" label="默认供应商" min-width="120" />
        <el-table-column prop="seq" label="序号" width="70" align="center" sortable />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row, $index }">
            <el-button link type="primary" size="small" :disabled="$index === 0" @click="moveProcess($index, -1)">上移</el-button>
            <el-button link type="primary" size="small" :disabled="$index === processData.length - 1" @click="moveProcess($index, 1)">下移</el-button>
            <el-button link type="danger" size="small" @click="handleProcessDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增 BOM 材料' : '编辑 BOM 材料'" width="500px" @close="dialogVisible = false">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px">
        <el-form-item label="材料" prop="material_id">
          <el-select v-model="form.material_id" filterable placeholder="请选择材料" style="width: 100%" @change="onMaterialChange">
            <el-option v-for="m in materialList" :key="m.id" :label="`${m.code} - ${m.name}`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格"><el-input v-model="form.material_spec" disabled /></el-form-item>
        <el-form-item label="用量" prop="quantity"><el-input-number v-model="form.quantity" :min="0" :precision="4" style="width: 100%" /></el-form-item>
        <el-form-item label="损耗率(%)" prop="loss_rate"><el-input-number v-model="form.loss_rate" :min="0" :max="100" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="工序" prop="process_id">
          <el-select v-model="form.process_id" placeholder="请选择工序" style="width: 100%">
            <el-option v-for="p in processList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加工序弹窗 -->
    <el-dialog v-model="processDialogVisible" title="添加工序" width="500px" @close="processDialogVisible = false">
      <el-form :model="processForm" :rules="processFormRules" ref="processFormRef" label-width="110px">
        <el-form-item label="工序" prop="process_id">
          <el-select v-model="processForm.process_id" filterable placeholder="请选择工序" style="width: 100%">
            <el-option v-for="p in processList" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认加工单价" prop="default_unit_price">
          <el-input-number v-model="processForm.default_unit_price" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认供应商" prop="default_supplier_id">
          <el-select v-model="processForm.default_supplier_id" filterable clearable placeholder="请选择默认供应商" style="width: 100%">
            <el-option v-for="s in supplierList" :key="s.id" :label="`${s.code} - ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="processDialogLoading" @click="handleProcessSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'; import { foundationApi } from '../../api/foundation'

const productKeyword = ref('')
const selectedProductId = ref(null)
const productList = ref([])
const productLoading = ref(false)
const bomData = ref([])
const bomLoading = ref(false)
const processData = ref([])
const processLoading = ref(false)
const materialList = ref([])
const processList = ref([])
const supplierList = ref([])
const rightTab = ref('bom')
const topHeight = ref(parseInt(localStorage.getItem('mazu_bom_top_height') || '240'))
const tableHeight = computed(() => Math.max(topHeight.value - 50, 100))

const selectedProduct = ref(null)

const productTableRef = ref(null)

function startDrag(e) {
  e.preventDefault()
  const startY = e.clientY
  const startH = topHeight.value
  const onMove = (ev) => {
    const h = Math.min(Math.max(startH + (ev.clientY - startY), 140), window.innerHeight - 320)
    topHeight.value = h
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    localStorage.setItem('mazu_bom_top_height', String(topHeight.value))
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

const filteredProducts = computed(() => {
  if (!productKeyword.value) return productList.value
  const kw = productKeyword.value.toLowerCase()
  return productList.value.filter(p =>
    (p.name || '').toLowerCase().includes(kw) ||
    (p.code || '').toLowerCase().includes(kw)
  )
})

async function fetchProducts() {
  productLoading.value = true
  try {
    const res = await foundationApi.products.select('')
    productList.value = Array.isArray(res) ? res : (res.items || res.data || [])
    nextTick(() => {
      productTableRef.value?.setCurrentRow(productList.value[0] || null)
      onProductSelect(productList.value[0])
    })
  } catch (e) {} finally { productLoading.value = false }
}

async function fetchBom() {
  if (!selectedProductId.value) return
  bomLoading.value = true
  try {
    const res = await foundationApi.getBomByProduct(selectedProductId.value)
    bomData.value = res.items || res.data || []
  } catch (e) { ElMessage.error('加载 BOM 失败') } finally { bomLoading.value = false }
}

function findProcess(id) {
  return processList.value.find(p => p.id === id)
}

async function fetchProcessTemplates() {
  if (!selectedProductId.value) return
  if (!processList.value.length) await fetchProcesses()
  processLoading.value = true
  try {
    const res = await foundationApi.products.processTemplates.list(selectedProductId.value)
    const items = Array.isArray(res) ? res : (res.items || res.data || [])
    processData.value = items.map(row => {
      const p = findProcess(row.process_id)
      return { ...row, process_code: p?.code || '', process_name: p?.name || '' }
    })
  } catch (e) { ElMessage.error('加载工艺流程失败') } finally { processLoading.value = false }
}

async function fetchMaterials() {
  try {
    const res = await foundationApi.materials.select('')
    materialList.value = Array.isArray(res) ? res : []
  } catch (e) {}
}

async function fetchProcesses() {
  try {
    const res = await foundationApi.processes.select('')
    processList.value = Array.isArray(res) ? res : []
  } catch (e) {}
}

async function fetchSupplierList() {
  try {
    const res = await foundationApi.suppliers.select()
    supplierList.value = Array.isArray(res) ? res : []
  } catch (e) {}
}

function onProductSelect(row) {
  if (!row) return
  selectedProductId.value = row.id
  selectedProduct.value = row
  fetchBom()
  fetchProcessTemplates()
}

const dialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogMode = ref('create')
const formRef = ref(null)
const form = reactive({ id: null, material_id: null, material_spec: '', quantity: 1, loss_rate: 0, process_id: null })

const formRules = {
  material_id: [{ required: true, message: '请选择材料', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入用量', trigger: 'blur' }],
}

const processDialogVisible = ref(false)
const processDialogLoading = ref(false)
const processFormRef = ref(null)
const processForm = reactive({ process_id: null, default_unit_price: 0, default_supplier_id: null })
const processFormRules = {
  process_id: [{ required: true, message: '请选择工序', trigger: 'change' }],
}

function openProcessDialog() {
  Object.assign(processForm, { process_id: null, default_unit_price: 0, default_supplier_id: null })
  processDialogVisible.value = true
}

async function handleProcessSave() {
  const valid = await processFormRef.value.validate().catch(() => false)
  if (!valid) return
  const p = processList.value.find(x => x.id === processForm.process_id)
  if (!p) return
  const maxSeq = processData.value.reduce((m, r) => Math.max(m, r.seq || 0), 0)
  processData.value.push({
    id: null,
    process_id: p.id,
    process_code: p.code,
    process_name: p.name,
    seq: maxSeq + 1,
    default_unit_price: processForm.default_unit_price,
    default_supplier_id: processForm.default_supplier_id,
    supplier_name: supplierList.value.find(s => s.id === processForm.default_supplier_id)?.name || '',
  })
  processDialogVisible.value = false
  saveProcessTemplates()
}

async function saveProcessTemplates() {
  if (!selectedProductId.value) return
  processLoading.value = true
  try {
    const payload = processData.value.map((row, i) => ({
      process_id: row.process_id,
      seq: i + 1,
      default_unit_price: row.default_unit_price || 0,
      default_supplier_id: row.default_supplier_id ?? null,
    }))
    await foundationApi.products.processTemplates.save(selectedProductId.value, payload)
    ElMessage.success('保存成功')
    await fetchProcessTemplates()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { processLoading.value = false }
}

function moveProcess(idx, dir) {
  const target = idx + dir
  if (target < 0 || target >= processData.value.length) return
  const arr = processData.value
  const tmp = arr[idx]
  arr[idx] = arr[target]
  arr[target] = tmp
  arr.forEach((row, i) => { row.seq = i + 1 })
  saveProcessTemplates()
}

async function handleProcessDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该工序？', '删除确认', { type: 'warning' })
    processData.value = processData.value.filter(x => x !== row)
    saveProcessTemplates()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败') }
}

function onMaterialChange(id) {
  const m = materialList.value.find(x => x.id === id)
  if (m) form.material_spec = m.spec || ''
}

function openDialog(mode, row = {}) {
  dialogMode.value = mode
  if (mode === 'edit') {
    Object.assign(form, { id: row.id, material_id: row.material_id, material_spec: row.material_spec || '', quantity: row.quantity || 1, loss_rate: row.loss_rate || 0, process_id: row.process_id || null })
  } else {
    Object.assign(form, { id: null, material_id: null, material_spec: '', quantity: 1, loss_rate: 0, process_id: null })
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  dialogLoading.value = true
  try {
    const payload = { bom_name: '默认BOM', product_id: selectedProductId.value, ...form }
    if (dialogMode.value === 'create') {
      await foundationApi.createBomItem(payload)
    } else {
      await foundationApi.updateBomItem(form.id, { ...payload, id: undefined })
    }
    ElMessage.success(dialogMode.value === 'create' ? '新增成功' : '更新成功')
    dialogVisible.value = false
    fetchBom()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { dialogLoading.value = false }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该 BOM 材料？', '删除确认', { type: 'warning' })
    await foundationApi.deleteBomItem(row.id)
    ElMessage.success('删除成功')
    fetchBom()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败') }
}

onMounted(() => { fetchProducts(); fetchMaterials(); fetchProcesses(); fetchSupplierList() })
</script>

<style scoped>
:deep(.header-tabs .el-tabs__header) { margin: 0; border-bottom: none; }
:deep(.header-tabs .el-tabs__nav-wrap::after) { display: none; }
.bom-divider {
  height: 8px;
  margin-bottom: 12px;
  cursor: row-resize;
  background: #dcdfe6;
  border-radius: 2px;
}
.bom-divider:hover { background: #409eff; }
</style>
