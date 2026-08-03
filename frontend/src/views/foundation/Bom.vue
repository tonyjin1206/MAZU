<template>
  <div style="display: flex; gap: 12px">
    <!-- 左侧：产品列表 -->
    <el-card style="width: 40%; flex-shrink: 0">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchProducts">刷新</el-button>
        </div>
      </template>
      <el-input v-model="productKeyword" placeholder="按产品名称搜索" clearable style="margin-bottom: 8px" @input="filterProducts" />
      <el-table :data="filteredProducts" v-loading="productLoading" stripe border size="small" style="width: 100%" highlight-current-row @row-click="onProductClick" max-height="550">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column label="规格" width="100" show-overflow-tooltip><template #default="{ row }">{{ row.spec || '-' }}</template></el-table-column>
        <el-table-column label="型号" width="100" show-overflow-tooltip><template #default="{ row }">{{ row.model || '-' }}</template></el-table-column>
      </el-table>
    </el-card>

    <!-- 右侧：BOM 明细 -->
    <el-card style="flex: 1">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" :disabled="!selectedProductId" @click="openDialog('create')">新增材料</el-button>
        </div>
      </template>
      <div v-if="!selectedProductId" style="text-align: center; color: #909399; padding: 40px">请在左侧选择一个产品查看 BOM</div>
      <el-table v-else :data="bomData" v-loading="bomLoading" stripe border size="small" style="width: 100%">
        <el-table-column prop="material_code" label="材料编码" width="120" />
        <el-table-column prop="material_name" label="材料名称" min-width="140" />
        <el-table-column prop="material_spec" label="规格" min-width="120" />
        <el-table-column prop="material_unit" label="单位" width="70" align="center" />
        <el-table-column label="用量" width="80" align="center"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
        <el-table-column prop="loss_rate" label="损耗率(%)" width="100" align="center" />
        <el-table-column prop="process_name" label="工序" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
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
        <el-form-item label="用量" prop="quantity"><el-input type="number" v-model="form.quantity" :min="0" :precision="4" style="width: 100%" /></el-form-item>
        <el-form-item label="损耗率(%)" prop="loss_rate"><el-input type="number" v-model="form.loss_rate" :min="0" :max="100" :precision="2" style="width: 100%" /></el-form-item>
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { foundationApi } from '../../api/foundation'

const productKeyword = ref('')
const selectedProductId = ref(null)
const productList = ref([])
const productLoading = ref(false)
const bomData = ref([])
const bomLoading = ref(false)
const materialList = ref([])
const processList = ref([])

const filteredProducts = computed(() => {
  if (!productKeyword.value) return productList.value
  const kw = productKeyword.value.toLowerCase()
  return productList.value.filter(p =>
    (p.name || '').toLowerCase().includes(kw)
  )
})

async function fetchProducts() {
  try {
    const res = await foundationApi.products.select('')
    productList.value = Array.isArray(res) ? res : (res.items || res.data || [])
  } catch {}
}

async function fetchBom() {
  if (!selectedProductId.value) return
  bomLoading.value = true
  try {
    const res = await foundationApi.getBomByProduct(selectedProductId.value)
    bomData.value = res.items || res.data || []
  } catch { ElMessage.error('加载 BOM 失败') } finally { bomLoading.value = false }
}

async function fetchMaterials() {
  try {
    const res = await foundationApi.materials.select('')
    materialList.value = Array.isArray(res) ? res : []
  } catch {}
}

async function fetchProcesses() {
  try {
    const res = await foundationApi.processes.select('')
    processList.value = Array.isArray(res) ? res : []
  } catch {}
}

function onProductClick(row) {
  selectedProductId.value = row.id
  fetchBom()
}
function filterProducts() {} // computed handles it

const dialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogMode = ref('create')
const formRef = ref(null)
const form = reactive({ id: null, material_id: null, material_spec: '', quantity: 1, loss_rate: 0, process_id: null })

const formRules = {
  material_id: [{ required: true, message: '请选择材料', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入用量', trigger: 'blur' }],
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
  } catch (e) { ElMessage.error('保存失败') } finally { dialogLoading.value = false }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该 BOM 材料？', '删除确认', { type: 'warning' })
    await foundationApi.deleteBomItem(row.id)
    ElMessage.success('删除成功')
    fetchBom()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

onMounted(() => { fetchProducts(); fetchMaterials(); fetchProcesses() })
</script>

<style scoped>
</style>
