<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增HS编码</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="HS编码">
          <el-input v-model="searchForm.hs_code" placeholder="HS编码" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="商品名称" clearable style="width: 180px" @keyup.enter="fetchData" />
        </el-form-item>
      </el-form>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="hs_code" label="HS编码" width="130" sortable column-key="hs_code" :filters="hsCodeFilters" :filter-method="filterHsCode" />
        <el-table-column prop="name" label="商品名称" min-width="200" sortable column-key="name" :filters="nameFilters" :filter-method="filterName" />
        <el-table-column prop="unit" label="单位" width="100" sortable column-key="unit" :filters="unitFilters" :filter-method="filterUnit" />
        <el-table-column prop="refund_rate" label="退税率%" width="100" sortable>
          <template #default="{ row }">{{ row.refund_rate }}%</template>
        </el-table-column>
        <el-table-column prop="tax_rate" label="增值税率%" width="100" sortable>
          <template #default="{ row }">{{ row.tax_rate }}%</template>
        </el-table-column>
        <el-table-column prop="effective_date" label="生效日期" width="120" sortable />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top: 16px" v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增HS编码' : '编辑HS编码'" width="550px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item label="HS编码" prop="hs_code">
          <el-input v-model="form.hs_code" placeholder="如 8471300000" />
        </el-form-item>
        <el-form-item label="商品名称" prop="name">
          <el-input v-model="form.name" placeholder="商品名称" />
        </el-form-item>
        <el-form-item label="单位" prop="unit">
          <el-select v-model="form.unit" placeholder="请选择" style="width: 100%">
            <el-option label="台" value="台" /><el-option label="套" value="套" />
            <el-option label="件" value="件" /><el-option label="个" value="个" />
            <el-option label="千克" value="千克" /><el-option label="米" value="米" />
            <el-option label="平方米" value="平方米" /><el-option label="立方米" value="立方米" />
          </el-select>
        </el-form-item>
        <el-form-item label="退税率(%)" prop="refund_rate">
          <el-input type="number" v-model="form.refund_rate" :min="0" :max="17" :precision="2" :step="0.5" style="width: 100%" />
        </el-form-item>
        <el-form-item label="增值税率(%)" prop="tax_rate">
          <el-input type="number" v-model="form.tax_rate" :min="0" :max="17" :precision="2" :step="0.5" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日期" prop="effective_date">
          <el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="监管条件" prop="supervision_conditions">
          <el-input v-model="form.supervision_conditions" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
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
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)
const formRef = ref(null)
const searchForm = reactive({ hs_code: '', name: '' })

// 列筛选
const hsCodeFilters = ref([])
const nameFilters = ref([])
const unitFilters = ref([])
const filterHsCodeVal = ref('')
const filterNameVal = ref('')
const filterUnitVal = ref('')

const filteredList = computed(() => {
  let items = tableData.value
  if (filterHsCodeVal.value) items = items.filter(r => r.hs_code === filterHsCodeVal.value)
  if (filterNameVal.value) items = items.filter(r => r.name === filterNameVal.value)
  if (filterUnitVal.value) items = items.filter(r => r.unit === filterUnitVal.value)
  return items
})
function filterHsCode(val, row) { filterHsCodeVal.value = val; return true }
function filterName(val, row) { filterNameVal.value = val; return true }
function filterUnit(val, row) { filterUnitVal.value = val; return true }

const form = reactive({
  id: null, hs_code: '', name: '', unit: '个',
  refund_rate: 13, tax_rate: 13,
  effective_date: '', supervision_conditions: '',
})

const rules = {
  hs_code: [{ required: true, message: '请输入HS编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  unit: [{ required: true, message: '请选择单位', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await foundationApi.hsCodes.list({
      page: page.value,
      page_size: pageSize.value,
      hs_code: searchForm.hs_code || undefined,
      name: searchForm.name || undefined,
    })
    tableData.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    hsCodeFilters.value = [...new Set(tableData.value.map(r => r.hs_code).filter(Boolean))].map(v => ({ text: v, value: v }))
    nameFilters.value = [...new Set(tableData.value.map(r => r.name).filter(Boolean))].map(v => ({ text: v, value: v }))
    unitFilters.value = [...new Set(tableData.value.map(r => r.unit).filter(Boolean))].map(v => ({ text: v, value: v }))
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.hs_code = ''
  searchForm.name = ''
  page.value = 1
  fetchData()
}

function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    form.id = row.id
    form.hs_code = row.hs_code
    form.name = row.name
    form.unit = row.unit || '个'
    form.refund_rate = row.refund_rate ?? 13
    form.tax_rate = row.tax_rate ?? 13
    form.effective_date = row.effective_date || ''
    form.supervision_conditions = row.supervision_conditions || ''
  } else {
    form.id = null
    form.hs_code = ''
    form.name = ''
    form.unit = '个'
    form.refund_rate = 13
    form.tax_rate = 13
    form.effective_date = ''
    form.supervision_conditions = ''
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.id
    if (dialogMode.value === 'create') {
      await foundationApi.hsCodes.create(payload)
      ElMessage.success('创建成功')
    } else {
      await foundationApi.hsCodes.update(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除HS编码「${row.hs_code}」？`, '提示', { type: 'warning' })
    await foundationApi.hsCodes.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(fetchData)
</script>
