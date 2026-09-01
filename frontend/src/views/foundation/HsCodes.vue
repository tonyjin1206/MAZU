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
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef"
        :key="columnVersion"
        :data="filteredList"
        v-loading="loading"
        stripe border size="small"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in visibleColumns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :sortable="col.sortable"
          :align="col.align"
        >
          <template #header>
                <el-dropdown trigger="contextmenu" :hide-on-click="false">
                  <span class="col-header-wrap">
                    <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                    {{ col.label }}
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click.stop="openColumnSettings" style="color: #409eff">列排序...</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
          <template v-if="col.prop === 'refund_rate'" #default="{ row }">
            {{ row.refund_rate }}%
          </template>
          <template v-else-if="col.prop === 'tax_rate'" #default="{ row }">
            {{ row.tax_rate }}%
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top: 16px" v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增HS编码' : '编辑HS编码'" width="800px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
<el-form-item label="HS编码" prop="hs_code">
          <el-input v-model="form.hs_code" placeholder="如 8471300000" />
        </el-form-item>
          </el-col>
          <el-col :span="12">
<el-form-item label="商品名称" prop="name">
          <el-input v-model="form.name" placeholder="商品名称" />
        </el-form-item>
          </el-col>
          <el-col :span="12">
<el-form-item label="单位" prop="unit">
          <el-select v-model="form.unit" placeholder="请选择" style="width: 100%">
            <el-option v-for="o in unitOptions" :key="o.key" :label="o.label" :value="o.label" />
          </el-select>
        </el-form-item>
          </el-col>
          <el-col :span="12">
<el-form-item label="退税率(%)" prop="refund_rate">
          <el-input type="number" v-model="form.refund_rate" :min="0" :max="17" :precision="2" :step="0.5" style="width: 100%" />
        </el-form-item>
          </el-col>
          <el-col :span="12">
<el-form-item label="增值税率(%)" prop="tax_rate">
          <el-input type="number" v-model="form.tax_rate" :min="0" :max="17" :precision="2" :step="0.5" style="width: 100%" />
        </el-form-item>
          </el-col>
          <el-col :span="12">
<el-form-item label="生效日期" prop="effective_date">
          <el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
          </el-col>
          <el-col :span="24">
<el-form-item label="监管条件" prop="supervision_conditions">
          <el-input v-model="form.supervision_conditions" placeholder="选填" />
        </el-form-item>
          </el-col>
        </el-row>
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
import { ref, reactive, onMounted, computed, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { foundationApi } from '../../api/foundation'

// 单位选项（来自参数设置）
const tableRef = ref(null)
const unitOptions = ref([])
async function loadUnitOptions() {
  try { unitOptions.value = await foundationApi.params.options({ group: 'unit' }) || [] } catch (e) { unitOptions.value = [] }
}

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_hscode_columns'
const defaultColumns = [
  { prop: 'hs_code', label: 'HS编码', width: 130, sortable: true },
  { prop: 'name', label: '商品名称', minWidth: 200, sortable: true },
  { prop: 'unit', label: '单位', width: 100, sortable: true },
  { prop: 'refund_rate', label: '退税率%', width: 100, sortable: true },
  { prop: 'tax_rate', label: '增值税率%', width: 100, sortable: true },
  { prop: 'effective_date', label: '生效日期', width: 120, sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

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

const filteredList = computed(() => tableData.value)

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
    nextTick(initColumnDrag)
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
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(() => { fetchData(); loadUnitOptions() })
</script>
