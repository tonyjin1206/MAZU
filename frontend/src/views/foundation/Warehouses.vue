<template>
  <div>
    <!-- 顶部卡片：header 靠右按钮 + body 搜索条件 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增仓库</el-button>
        </div>
      </template>
      <el-form :model="searchForm" inline>
        <el-form-item label="编码">
          <el-input v-model="searchForm.code" placeholder="编码" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="名称" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="searchForm.wh_type" placeholder="类型" clearable style="width: 120px">
            <el-option label="原料仓" value="原料仓" />
            <el-option label="成品仓" value="成品仓" />
            <el-option label="半成品仓" value="半成品仓" />
            <el-option label="不良品仓" value="不良品仓" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 底部卡片：边框表格 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: flex-end">
          <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table :data="filteredList" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'wh_type'" #default="{ row }">
            <el-tag size="small" :type="row.wh_type === '成品仓' ? 'primary' : (row.wh_type === '不良品仓' ? 'danger' : 'warning')">{{ row.wh_type }}</el-tag>
          </template>
          <template v-else-if="col.prop === 'is_active'" #default="{ row }">
            <el-tag size="small" :type="row.is_active === 1 ? 'success' : 'info'">{{ row.is_active === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 16px" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增仓库' : '编辑仓库'" width="520px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" :disabled="dialogMode === 'edit'" placeholder="如 WH-01（编辑时不可改）" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 原料仓" />
        </el-form-item>
        <el-form-item label="类型" prop="wh_type">
          <el-select v-model="form.wh_type" style="width: 100%">
            <el-option label="原料仓" value="原料仓" />
            <el-option label="成品仓" value="成品仓" />
            <el-option label="半成品仓" value="半成品仓" />
            <el-option label="不良品仓" value="不良品仓" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人" prop="manager">
          <el-input v-model="form.manager" placeholder="选填" />
        </el-form-item>
        <el-form-item label="地址" prop="address">
          <el-input v-model="form.address" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序 + 显隐）=====
const STORAGE_KEY = 'mazu_warehouse_columns'
const defaultColumns = [
  { prop: 'code', label: '编码', width: 130, sortable: true },
  { prop: 'name', label: '名称', minWidth: 160, sortable: true },
  { prop: 'wh_type', label: '类型', width: 110, sortable: true },
  { prop: 'manager', label: '负责人', width: 110, sortable: true },
  { prop: 'address', label: '地址', minWidth: 180, sortable: true },
  { prop: 'is_active', label: '状态', width: 80, align: 'center', sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const searchForm = reactive({ code: '', name: '', wh_type: '' })
const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filteredList = computed(() => list.value)

async function fetchData() {
  loading.value = true
  try {
    const res = await foundationApi.warehouses.list({
      page: page.value, page_size: pageSize.value,
      code: searchForm.code || undefined,
      name: searchForm.name || undefined,
    })
    list.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false; nextTick(initColumnDrag) }
}

function resetSearch() {
  searchForm.code = ''
  searchForm.name = ''
  searchForm.wh_type = ''
  page.value = 1
  fetchData()
}

// ===== 新建/编辑 =====
const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)
const formRef = ref()
const form = reactive({ id: null, code: '', name: '', wh_type: '原料仓', manager: '', address: '' })
const rules = {
  code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }],
}

function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'create') {
    Object.assign(form, { id: null, code: '', name: '', wh_type: '原料仓', manager: '', address: '' })
  } else {
    Object.assign(form, { id: row.id, code: row.code, name: row.name, wh_type: row.wh_type || '原料仓', manager: row.manager || '', address: row.address || '' })
  }
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { name: form.name, wh_type: form.wh_type, manager: form.manager, address: form.address }
    if (dialogMode.value === 'create') {
      payload.code = form.code
      await foundationApi.warehouses.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.warehouses.update(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除仓库「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await foundationApi.warehouses.remove(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(fetchData)
</script>
