<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="编码">
          <el-input v-model="searchForm.code" placeholder="编码" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name_cn" placeholder="名称" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="searchForm.spec" placeholder="规格" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
      </el-form>
    </el-card>
    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="code" label="编码" width="140" sortable column-key="code" :filters="codeFilters" :filter-method="filterCode" />
        <el-table-column prop="name_cn" label="中文名" min-width="160" sortable column-key="name_cn" :filters="nameFilters" :filter-method="filterName" />
        <el-table-column prop="name_en" label="英文名" min-width="180" sortable />
        <el-table-column prop="spec" label="规格" min-width="140" sortable column-key="spec" :filters="specFilters" :filter-method="filterSpec" />
        <el-table-column prop="unit" label="单位" width="100" align="center" sortable column-key="unit" :filters="unitFilters" :filter-method="filterUnit" />
        <el-table-column label="销售价" width="100" align="right" sortable><template #default="{ row }">{{ $fm(row.sale_price) }}</template></el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top: 16px" v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" />
    </el-card>
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增产品' : '编辑产品'" width="500px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="80px">
        <el-form-item label="中文名" prop="name_cn">
          <el-input v-model="form.name_cn" />
        </el-form-item>
        <el-form-item label="英文名" prop="name_en">
          <el-input v-model="form.name_en" />
        </el-form-item>
        <el-form-item label="规格" prop="spec">
          <el-input v-model="form.spec" />
        </el-form-item>
        <el-form-item label="单位" prop="unit">
          <el-input v-model="form.unit" />
        </el-form-item>
        <el-form-item label="销售价" prop="sale_price">
          <el-input type="number" v-model="form.sale_price" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="HS编码" prop="hs_code">
          <el-input v-model="form.hs_code" placeholder="如 52094200" />
        </el-form-item>
        <el-form-item label="退税率%" prop="refund_rate">
          <el-input type="number" v-model="form.refund_rate" :min="0" :max="17" />
        </el-form-item>
        <el-form-item label="征税率%" prop="tax_rate">
          <el-input type="number" v-model="form.tax_rate" :min="0" :max="17" />
        </el-form-item>
        <el-form-item label="选择已有HS" prop="hs_code_id">
          <el-select v-model="form.hs_code_id" placeholder="(可选)选择已有HS编码" clearable filterable style="width: 100%" @change="onHsCodeSelect">
            <el-option v-for="h in hsCodeOptions" :key="h.id" :label="`${h.hs_code} - ${h.name}`" :value="h.id" />
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
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { foundationApi } from '../../api/foundation'

const loading = ref(false)
const tableData = ref([])
const pagination = ref({ page: 1, pageSize: 100, total: 0 })
const searchForm = reactive({ code: '', name_cn: '', spec: '' })

// 列筛选
const codeFilters = ref([])
const nameFilters = ref([])
const specFilters = ref([])
const unitFilters = ref([])
const filterCodeVal = ref('')
const filterNameVal = ref('')
const filterSpecVal = ref('')
const filterUnitVal = ref('')

const filteredList = computed(() => {
  let items = tableData.value
  if (filterCodeVal.value) items = items.filter(r => r.code === filterCodeVal.value)
  if (filterNameVal.value) items = items.filter(r => r.name_cn === filterNameVal.value)
  if (filterSpecVal.value) items = items.filter(r => r.spec === filterSpecVal.value)
  if (filterUnitVal.value) items = items.filter(r => r.unit === filterUnitVal.value)
  return items
})
function filterCode(val, row) { filterCodeVal.value = val; return true }
function filterName(val, row) { filterNameVal.value = val; return true }
function filterSpec(val, row) { filterSpecVal.value = val; return true }
function filterUnit(val, row) { filterUnitVal.value = val; return true }
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogMode = ref('create')
const formRef = ref(null)
const hsCodeOptions = ref([])
const form = reactive({ id: null, name_cn: '', name_en: '', spec: '', unit: '', sale_price: 0, hs_code: '', refund_rate: 13, tax_rate: 13, hs_code_id: null })

onMounted(() => {
  fetchData()
  loadHsCodes()
})

async function loadHsCodes() {
  try {
    const res = await foundationApi.hsCodes.list({ page: 1, page_size: 200 })
    hsCodeOptions.value = res.items || []
  } catch (e) { /* ignore */ }
}

function onHsCodeSelect(id) {
  if (!id) return
  const h = hsCodeOptions.value.find(x => x.id === id)
  if (h) {
    form.hs_code = h.hs_code
    form.refund_rate = h.refund_rate || 13
    form.tax_rate = h.tax_rate || 13
  }
}

const formRules = {
  name_cn: [{ required: true, message: '请输入中文名', trigger: 'blur' }],
  spec: [{ required: true, message: '请输入规格', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }],
  sale_price: [{ required: true, message: '请输入销售价', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await foundationApi.products.list({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      code: searchForm.code || undefined,
      name_cn: searchForm.name_cn || undefined,
      spec: searchForm.spec || undefined,
    })
    tableData.value = res.items || []
    pagination.value.total = res.total || 0
    // 更新列筛选
    codeFilters.value = [...new Set(tableData.value.map(r => r.code).filter(Boolean))].map(v => ({ text: v, value: v }))
    nameFilters.value = [...new Set(tableData.value.map(r => r.name_cn).filter(Boolean))].map(v => ({ text: v, value: v }))
    specFilters.value = [...new Set(tableData.value.map(r => r.spec).filter(Boolean))].map(v => ({ text: v, value: v }))
    unitFilters.value = [...new Set(tableData.value.map(r => r.unit).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch (e) {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.code = ''
  searchForm.name_cn = ''
  searchForm.spec = ''
  filterCodeVal.value = ''; filterNameVal.value = ''; filterSpecVal.value = ''; filterUnitVal.value = ''
  pagination.value.page = 1
  fetchData()
}

function openDialog(mode, row = {}) {
  dialogMode.value = mode
  if (mode === 'edit') {
    form.id = row.id
    form.name_cn = row.name_cn || ''
    form.name_en = row.name_en || ''
    form.spec = row.spec || ''
    form.unit = row.unit || ''
    form.sale_price = row.sale_price || 0
    form.hs_code = row.hs_code || (row.hs_code_obj && row.hs_code_obj.hs_code) || ''
    form.refund_rate = row.refund_rate || (row.hs_code_obj && row.hs_code_obj.refund_rate) || 13
    form.tax_rate = row.tax_rate || (row.hs_code_obj && row.hs_code_obj.tax_rate) || 13
    form.hs_code_id = row.hs_code_id || null
  } else {
    form.id = null
    form.name_cn = ''
    form.name_en = ''
    form.spec = ''
    form.unit = ''
    form.sale_price = 0
    form.hs_code = ''
    form.refund_rate = 13
    form.tax_rate = 13
    form.hs_code_id = null
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  dialogLoading.value = true
  try {
    const payload = { ...form }
    delete payload.id
    if (dialogMode.value === 'create') {
      await foundationApi.products.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.products.update(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // handled by interceptor
  } finally {
    dialogLoading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除产品「${row.name_cn}」？`, '删除确认', { type: 'warning' })
    await foundationApi.products.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

</script>
