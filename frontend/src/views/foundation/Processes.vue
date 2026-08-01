<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display:flex;justify-content:flex-end;gap:8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增工序</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap:nowrap">
        <el-form-item label="编码"><el-input v-model="searchForm.code" placeholder="编码" clearable style="width:140px" @keyup.enter="fetchData" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="searchForm.name" placeholder="名称" clearable style="width:160px" @keyup.enter="fetchData" /></el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table
        :key="columnVersion"
        :data="filteredList"
        v-loading="loading"
        stripe border
      >
        <el-table-column
          v-for="col in columns"
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
                      <el-dropdown-item @click.stop="openOrderDialog" style="color: #409eff">列排序...</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
          <template v-if="col.prop === 'is_outsource'" #default="{ row }">
            <el-tag :type="row.is_outsource === 1 ? 'warning' : 'info'" size="small">{{ row.is_outsource === 1 ? '委外' : '自制' }}</el-tag>
          </template>
          <template v-else-if="col.prop === 'unit_price'" #default="{ row }">
            {{ $fm(row.unit_price) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 16px" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增工序' : '编辑工序'" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="工序名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="标准工时(h)" prop="standard_hours">
          <el-input type="number" v-model="form.standard_hours" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="类型" prop="is_outsource">
          <el-radio-group v-model="form.is_outsource">
            <el-radio :value="0">自制</el-radio>
            <el-radio :value="1">委外</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="加工单价" prop="unit_price">
          <el-input type="number" v-model="form.unit_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
    <ColumnOrderDialog v-model:visible="orderDialogVisible" :columns="orderList" @opened="initOrderDrag" @confirm="confirmOrder" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import ColumnOrderDialog from '../../components/ColumnOrderDialog.vue'
import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_process_columns'
const defaultColumns = [
  { prop: 'code', label: '编码', width: 120, sortable: true },
  { prop: 'name', label: '工序名称', minWidth: 160, sortable: true },
  { prop: 'standard_hours', label: '标准工时(h)', width: 110, align: 'right', sortable: true },
  { prop: 'is_outsource', label: '类型', width: 80, align: 'center', sortable: true },
  { prop: 'unit_price', label: '加工单价', width: 100, align: 'right', sortable: true },
]
const { columns, columnVersion, initColumnDrag, orderDialogVisible, orderList, openOrderDialog, initOrderDrag, confirmOrder } = useColumnDrag(defaultColumns, STORAGE_KEY)

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null, code: '', name: '', standard_hours: 0,
  is_outsource: 0, unit_price: 0, remark: '',
})

const rules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入工序名称', trigger: 'blur' }],
}

const searchForm = reactive({ code: '', name: '' })

const filteredList = computed(() => tableData.value)

function resetSearch() { searchForm.code = ''; searchForm.name = ''; page.value = 1; fetchData() }

async function fetchData() {
  loading.value = true
  try {
    const res = await foundationApi.processes.list({ page: page.value, page_size: pageSize.value, code: searchForm.code || undefined, name: searchForm.name || undefined })
    tableData.value = res.items || []
    total.value = res.total || 0
    nextTick(initColumnDrag)
  } finally {
    loading.value = false
  }
}

function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    Object.assign(form, {
      id: row.id, code: row.code, name: row.name,
      standard_hours: row.standard_hours ?? 0,
      is_outsource: row.is_outsource ?? 0,
      unit_price: row.unit_price ?? 0,
      remark: row.remark || '',
    })
  } else {
    form.id = null; form.code = ''; form.name = ''
    form.standard_hours = 0; form.is_outsource = 0
    form.unit_price = 0; form.remark = ''
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
      await foundationApi.processes.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.processes.update(form.id, payload)
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
    await ElMessageBox.confirm(`确认删除工序「${row.name}」？`, '提示', { type: 'warning' })
    await foundationApi.processes.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(fetchData)
</script>
