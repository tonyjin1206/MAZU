<template>
  <div>
    <!-- 顶部卡片：header 靠右按钮 + body 搜索条件 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增供应商</el-button>
        </div>
      </template>
      <el-form :model="searchForm" inline>
        <el-form-item label="编码">
          <el-input v-model="searchForm.code" placeholder="编码" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="名称" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="searchForm.contact_person" placeholder="联系人" clearable style="width: 120px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="searchForm.supplier_type" placeholder="类型" clearable style="width: 120px">
            <el-option label="原材料" value="原材料" />
            <el-option label="委外" value="委外" />
            <el-option label="辅料" value="辅料" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 底部卡片：边框表格 -->
    <el-card>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="code" label="编码" width="120" sortable column-key="code" :filters="codeFilters" :filter-method="filterCode" />
        <el-table-column prop="name" label="名称" min-width="150" sortable column-key="name" :filters="nameFilters" :filter-method="filterName" />
        <el-table-column prop="contact_person" label="联系人" width="110" sortable column-key="contact" :filters="contactFilters" :filter-method="filterContact" />
        <el-table-column prop="phone" label="电话" width="140" sortable />
        <el-table-column prop="tax_id" label="税号" width="150" sortable />
        <el-table-column prop="payment_terms" label="付款条件" width="100" sortable />
        <el-table-column prop="account_period" label="账期(天)" width="90" sortable />
        <el-table-column prop="rating" label="评级" width="80" align="center" sortable />
        <el-table-column prop="supplier_type" label="类型" width="100" sortable column-key="supplier_type" :filters="typeFilters" :filter-method="filterType" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 16px" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增供应商' : '编辑供应商'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系人" prop="contact_person">
          <el-input v-model="form.contact_person" />
        </el-form-item>
        <el-form-item label="电话" prop="phone">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="税号" prop="tax_id">
          <el-input v-model="form.tax_id" />
        </el-form-item>
        <el-form-item label="付款条件" prop="payment_terms">
          <el-select v-model="form.payment_terms" style="width: 100%">
            <el-option label="T/T" value="TT" />
            <el-option label="L/C" value="LC" />
            <el-option label="O/A" value="OA" />
          </el-select>
        </el-form-item>
        <el-form-item label="账期(天)" prop="account_period">
          <el-input type="number" v-model="form.account_period" :min="0" :step="15" style="width: 100%" />
        </el-form-item>
        <el-form-item label="类型" prop="supplier_type">
          <el-select v-model="form.supplier_type" style="width: 100%">
            <el-option label="原材料" value="原材料" />
            <el-option label="委外" value="委外" />
            <el-option label="辅料" value="辅料" />
          </el-select>
        </el-form-item>
        <el-form-item label="评级" prop="rating">
          <el-rate v-model="form.rating" :max="5" />
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

const searchForm = reactive({
  code: '',
  name: '',
  contact_person: '',
  supplier_type: '',
})

// 列筛选
const codeFilters = ref([])
const nameFilters = ref([])
const contactFilters = ref([])
const typeFilters = ref([])
const filterCodeVal = ref('')
const filterNameVal = ref('')
const filterContactVal = ref('')
const filterTypeVal = ref('')

const filteredList = computed(() => {
  let items = tableData.value
  if (filterCodeVal.value) items = items.filter(r => r.code === filterCodeVal.value)
  if (filterNameVal.value) items = items.filter(r => r.name === filterNameVal.value)
  if (filterContactVal.value) items = items.filter(r => r.contact_person === filterContactVal.value)
  if (filterTypeVal.value) items = items.filter(r => r.supplier_type === filterTypeVal.value)
  return items
})
function filterCode(val, row) { filterCodeVal.value = val; return true }
function filterName(val, row) { filterNameVal.value = val; return true }
function filterContact(val, row) { filterContactVal.value = val; return true }
function filterType(val, row) { filterTypeVal.value = val; return true }

function resetSearch() {
  Object.assign(searchForm, { code: '', name: '', contact_person: '', supplier_type: '' })
  filterCodeVal.value = ''; filterNameVal.value = ''; filterContactVal.value = ''; filterTypeVal.value = ''
  page.value = 1
  fetchData()
}

const form = reactive({
  id: null, name: '', contact_person: '', phone: '', tax_id: '',
  payment_terms: 'TT', account_period: 30,
  supplier_type: '原材料', rating: 3,
})

const rules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  contact_person: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入电话', trigger: 'blur' }],
  tax_id: [{ required: true, message: '请输入税号', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await foundationApi.suppliers.list({
      page: page.value,
      page_size: pageSize.value,
      code: searchForm.code || undefined,
      name: searchForm.name || undefined,
      contact_person: searchForm.contact_person || undefined,
      supplier_type: searchForm.supplier_type || undefined,
    })
    tableData.value = res.items || []
    total.value = res.total || 0
    // 更新列筛选
    codeFilters.value = [...new Set(tableData.value.map(r => r.code).filter(Boolean))].map(v => ({ text: v, value: v }))
    nameFilters.value = [...new Set(tableData.value.map(r => r.name).filter(Boolean))].map(v => ({ text: v, value: v }))
    contactFilters.value = [...new Set(tableData.value.map(r => r.contact_person).filter(Boolean))].map(v => ({ text: v, value: v }))
    typeFilters.value = [...new Set(tableData.value.map(r => r.supplier_type).filter(Boolean))].map(v => ({ text: v, value: v }))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    id: null, name: '', contact_person: '', phone: '',
    payment_terms: 'TT', account_period: 30,
    supplier_type: '原材料', rating: 3,
  })
}

function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    form.id = row.id
    form.name = row.name || ''
    form.contact_person = row.contact_person || ''
    form.phone = row.phone || ''
    form.tax_id = row.tax_id || ''
    form.payment_terms = row.payment_terms || 'TT'
    form.account_period = row.account_period ?? 30
    form.supplier_type = row.supplier_type || '原材料'
    form.rating = row.rating ?? 3
  } else {
    resetForm()
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
      await foundationApi.suppliers.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.suppliers.update(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除供应商「${row.name}」？`, '提示', { type: 'warning' })
    await foundationApi.suppliers.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(fetchData)
</script>
