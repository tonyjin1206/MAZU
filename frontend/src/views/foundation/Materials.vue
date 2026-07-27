<template>
  <div>

    <!-- 搜索栏 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增原材料</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="编码/名称/规格" clearable style="width: 200px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="searchForm.category" placeholder="全部" clearable style="width: 150px">
            <el-option label="原材料" value="原材料" />
            <el-option label="辅料" value="辅料" />
            <el-option label="包装材料" value="包装材料" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card>
      <el-table :data="tableData" v-loading="loading" border stripe size="small" style="width: 100%">
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="spec" label="规格" min-width="140" />
        <el-table-column prop="model" label="型号" min-width="120" />
        <el-table-column prop="unit" label="单位" width="80" align="center" />
        <el-table-column prop="category" label="类别" width="100" align="center" />
        <el-table-column label="单价" width="100" align="right"><template #default="{ row }">{{ $fm(row.purchase_price) }}</template></el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top: 16px; justify-content: flex-end"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增材料' : '编辑材料'" width="500px" @close="dialogVisible = false">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="规格" prop="spec">
          <el-input v-model="form.spec" />
        </el-form-item>
        <el-form-item label="型号" prop="model">
          <el-input v-model="form.model" />
        </el-form-item>
        <el-form-item label="单位" prop="unit">
          <el-input v-model="form.unit" />
        </el-form-item>
        <el-form-item label="类别" prop="category">
          <el-select v-model="form.category" placeholder="请选择">
            <el-option label="原材料" value="原材料" />
            <el-option label="辅料" value="辅料" />
            <el-option label="包装材料" value="包装材料" />
          </el-select>
        </el-form-item>
        <el-form-item label="单价" prop="purchase_price">
          <el-input type="number" v-model="form.purchase_price" :precision="2" :min="0" style="width: 100%" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { foundationApi } from '../../api/foundation'

const loading = ref(false)
const tableData = ref([])
const pagination = ref({ page: 1, pageSize: 10, total: 0 })

const searchForm = reactive({ keyword: '', category: '' })

const dialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogMode = ref('create')
const formRef = ref(null)
const form = reactive({ id: null, name: '', spec: '', model: '', unit: '', category: '', purchase_price: 0 })

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  spec: [{ required: true, message: '请输入规格', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }],
  category: [{ required: true, message: '请选择类别', trigger: 'change' }],
  purchase_price: [{ required: true, message: '请输入单价', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      pageSize: pagination.value.pageSize,
      keyword: searchForm.keyword || undefined,
      category: searchForm.category || undefined,
    }
    const res = await foundationApi.materials.list(params)
    tableData.value = res.items || res.data?.items || []
    pagination.value.total = res.total || res.data?.total || 0
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.keyword = ''
  searchForm.category = ''
  pagination.value.page = 1
  fetchData()
}

function openDialog(mode, row = {}) {
  dialogMode.value = mode
  if (mode === 'edit') {
    Object.assign(form, { id: row.id, name: row.name, spec: row.spec || '', model: row.model || '', unit: row.unit || '', category: row.category || '', purchase_price: row.purchase_price || 0 })
  } else {
    Object.assign(form, { id: null, name: '', spec: '', model: '', unit: '', category: '', purchase_price: 0 })
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  dialogLoading.value = true
  try {
    if (dialogMode.value === 'create') {
      await foundationApi.materials.create(form)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.materials.update(form.id, form)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    dialogLoading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除材料「${row.name}」？`, '删除确认', { type: 'warning' })
    await foundationApi.materials.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => fetchData())
</script>
