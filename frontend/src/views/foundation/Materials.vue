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
        <el-form-item label="编码">
          <el-input v-model="searchForm.code" placeholder="编码" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="名称" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="searchForm.spec" placeholder="规格" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="searchForm.category" placeholder="全部" clearable style="width: 120px">
            <el-option label="原材料" value="原材料" />
            <el-option label="辅料" value="辅料" />
            <el-option label="包装材料" value="包装材料" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card>
      <el-table
        :key="columnVersion"
        :data="filteredList"
        v-loading="loading"
        stripe border size="small"
        style="width: 100%"
        :row-class-name="rowClassName"
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
                  <el-dropdown-item v-for="c in allColumns" :key="c.prop">
                    <el-checkbox :model-value="c.visible !== false" @change="toggleColumn(c)">{{ c.label }}</el-checkbox>
                  </el-dropdown-item>
                                  <el-dropdown-item divided @click.stop="openOrderDialog" style="color: #409eff">列排序...</el-dropdown-item>
</el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'purchase_price'" #default="{ row }">
            {{ $fm(row.purchase_price) }}
          </template>
          <template v-else-if="col.prop === 'is_active'" #default="{ row }">
            <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">
              {{ row.is_active === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            <el-button link :type="row.is_active === 1 ? 'warning' : 'success'" size="small" @click="handleToggle(row)">
              {{ row.is_active === 1 ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top: 16px"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[50, 100, 200]"
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
          <el-select v-model="form.unit" placeholder="请选择" filterable allow-create style="width: 100%">
            <el-option v-for="o in unitOptions" :key="o.key" :label="o.label" :value="o.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="大类" prop="category">
          <el-select v-model="form.category" placeholder="请选择大类" style="width: 100%" @change="onMainCategoryChange">
            <el-option v-for="o in mainCategoryOptions" :key="o.key" :label="o.label" :value="o.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="小类" prop="category_sub">
          <el-select v-model="form.category_sub" placeholder="请选择小类" style="width: 100%" :disabled="!form.category">
            <el-option v-for="o in subCategoryOptions" :key="o.key" :label="o.label" :value="o.label" />
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
    <ColumnOrderDialog v-model:visible="orderDialogVisible" :columns="orderList" @opened="initOrderDrag" @confirm="confirmOrder" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnOrderDialog from '../../components/ColumnOrderDialog.vue'
import { foundationApi } from '../../api/foundation'
import request from '../../api/request'

// 下拉选项（来自参数设置）
const unitOptions = ref([])
const mainCategoryOptions = ref([])
const subCategoryOptionsRaw = ref([])
// 小类下拉：按所选大类过滤（参数里小类用 parent_key 关联大类）
const subCategoryOptions = computed(() => {
  if (!form.category) return []
  const main = mainCategoryOptions.value.find(o => o.label === form.category)
  if (!main) return []
  return subCategoryOptionsRaw.value.filter(o => o.parent_key === main.key)
})
function onMainCategoryChange() { form.category_sub = '' }
async function loadParamOptions() {
  try { unitOptions.value = await request.get('/foundation/params/options', { params: { group: 'unit' } }) || [] } catch { unitOptions.value = [] }
  try { mainCategoryOptions.value = await request.get('/foundation/params/options', { params: { group: 'material_main_category' } }) || [] } catch { mainCategoryOptions.value = [] }
  try { subCategoryOptionsRaw.value = await request.get('/foundation/params/options', { params: { group: 'material_sub_category' } }) || [] } catch { subCategoryOptionsRaw.value = [] }
}

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_material_columns'
const defaultColumns = [
  { prop: 'code', label: '编码', width: 140, sortable: true },
  { prop: 'name', label: '名称', minWidth: 160, sortable: true },
  { prop: 'spec', label: '规格', minWidth: 140, sortable: true },
  { prop: 'model', label: '型号', minWidth: 120, sortable: true },
  { prop: 'unit', label: '单位', width: 100, align: 'center', sortable: true },
  { prop: 'category', label: '大类', width: 100, align: 'center', sortable: true },
  { prop: 'category_sub', label: '小类', width: 100, align: 'center', sortable: true },
  { prop: 'purchase_price', label: '单价', width: 100, align: 'right', sortable: true },
  { prop: 'is_active', label: '状态', width: 80, align: 'center' , sortable: true },
]
const { columns, columnVersion, initColumnDrag, orderDialogVisible, orderList, openOrderDialog, initOrderDrag, confirmOrder } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

const loading = ref(false)
const tableData = ref([])
const pagination = ref({ page: 1, pageSize: 100, total: 0 })

const searchForm = reactive({ code: '', name: '', spec: '', category: '' })

const filteredList = computed(() => tableData.value)

const dialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogMode = ref('create')
const formRef = ref(null)
const form = reactive({ id: null, name: '', spec: '', model: '', unit: '', category: '', category_sub: '', purchase_price: 0 })

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }],
  category: [{ required: true, message: '请选择大类', trigger: 'change' }],
  category_sub: [{ required: true, message: '请选择小类', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      pageSize: pagination.value.pageSize,
      code: searchForm.code || undefined,
      name: searchForm.name || undefined,
      spec: searchForm.spec || undefined,
      category: searchForm.category || undefined,
    }
    const res = await foundationApi.materials.list(params)
    tableData.value = res.items || res.data?.items || []
    pagination.value.total = res.total || res.data?.total || 0
    nextTick(() => { initColumnDrag(); fitTable(tableRef.value, columns, filteredList) })
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.code = ''
  searchForm.name = ''
  searchForm.spec = ''
  searchForm.category = ''
  pagination.value.page = 1
  fetchData()
}

function openDialog(mode, row = {}) {
  dialogMode.value = mode
  if (mode === 'edit') {
    Object.assign(form, { id: row.id, name: row.name, spec: row.spec || '', model: row.model || '', unit: row.unit || '', category: row.category || '', category_sub: row.category_sub || '', purchase_price: row.purchase_price || 0 })
  } else {
    Object.assign(form, { id: null, name: '', spec: '', model: '', unit: '', category: '', category_sub: '', purchase_price: 0 })
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
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleToggle(row) {
  const next = row.is_active === 1 ? 0 : 1
  try {
    await foundationApi.materials.update(row.id, { is_active: next })
    row.is_active = next
    ElMessage.success(next ? '已启用' : '已停用')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

function rowClassName({ row }) {
  return row.is_active === 1 ? '' : 'mazu-disabled-row'
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnVisible(); initColumnDrag() })
})

onMounted(() => { fetchData(); loadParamOptions() })
initColumnVisible()
</script>

<style scoped>
:deep(.mazu-disabled-row) {
  opacity: 0.55;
}
</style>
