<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="font-weight: 600">参数设置</div>
          <el-button type="primary" @click="openCreate">新增参数</el-button>
        </div>
      </template>
      <el-tabs v-model="activeGroup" @tab-change="loadGroup">
        <el-tab-pane v-for="g in groups" :key="g" :label="groupLabel(g)" :name="g" />
      </el-tabs>
      <div style="color: #909399; font-size: 12px; margin-bottom: 8px">
        在这里维护好选项后，新增供应商/材料/收付款单时，下拉框会自动出现这些选项。停用的选项不再出现在下拉里（历史数据不受影响）。
      </div>
    </el-card>

    <el-card>
      <el-table :data="list" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column prop="sort_order" label="排序" width="70" align="center" />
        <el-table-column prop="param_label" label="显示名称" min-width="140" />
        <el-table-column prop="param_key" label="参数值" min-width="140" />
        <el-table-column prop="remark" label="说明" min-width="160" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.is_active === 1" @change="(v) => toggleActive(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editId ? '编辑参数' : '新增参数'" width="480px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="参数组" prop="group_name">
          <el-select v-model="form.group_name" style="width: 100%" :disabled="!!editId">
            <el-option v-for="g in groupOptions" :key="g" :label="groupLabel(g)" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称" prop="param_label">
          <el-input v-model="form.param_label" placeholder="下拉框里看到的文字，如：原材料" />
        </el-form-item>
        <el-form-item label="参数值">
          <el-input :model-value="form.param_key" disabled>
            <template #append>
              <el-button v-if="!editId" @click="regenerateKey">重新编号</el-button>
            </template>
          </el-input>
          <div style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px">
            系统自动编号（01、02、03…），不用手动填。下拉选中后存入数据的是显示名称，编号仅作内部标识。
          </div>
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="选填，备注用途" />
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
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import request from '../../api/request'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_system_param_columns'
const defaultColumns = [
  { prop: 'sort_order', label: '排序', width: 70, align: 'center' },
  { prop: 'param_label', label: '显示名称', minWidth: 140 },
  { prop: 'param_key', label: '参数值', minWidth: 140 },
  { prop: 'remark', label: '说明', minWidth: 160 },
  { prop: 'is_active', label: '状态', width: 90, align: 'center' },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY)

const GROUP_LABELS = {
  supplier_type: '供应商类型',
  material_category: '材料类别',
  unit: '计量单位',
  payment_method: '付款方式',
}

function groupLabel(g) { return GROUP_LABELS[g] || g }

const groups = ref([])
const activeGroup = ref('')
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref(null)
const formRef = ref(null)

const form = reactive({ group_name: '', param_label: '', param_key: '', sort_order: 0, remark: '' })
const rules = {
  group_name: [{ required: true, message: '请选择参数组', trigger: 'change' }],
  param_label: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  param_key: [{ required: true, message: '请输入参数值', trigger: 'blur' }],
}

const groupOptions = computed(() => {
  const all = [...new Set([...groups.value, ...Object.keys(GROUP_LABELS)])]
  return all
})

async function loadGroups() {
  try { groups.value = await request.get('/foundation/params/groups') || [] } catch { groups.value = [] }
  if (!activeGroup.value && groups.value.length) {
    activeGroup.value = groups.value[0]
    loadGroup()
  }
}

async function loadGroup() {
  if (!activeGroup.value) return
  loading.value = true
  try {
    const res = await request.get(`/foundation/params/group/${activeGroup.value}`)
    list.value = res.items || []
  } catch { list.value = [] } finally { loading.value = false; nextTick(initColumnDrag) }
}

function nextParamKey() {
  // 组内下一个编号：取现有两位数字编号最大值 +1
  let max = 0
  for (const r of list.value) {
    const n = parseInt(r.param_key, 10)
    if (!isNaN(n) && n > max) max = n
  }
  return String(max + 1).padStart(2, '0')
}

function regenerateKey() {
  form.param_key = nextParamKey()
}

function openCreate() {
  editId.value = null
  Object.assign(form, { group_name: activeGroup.value || groups.value[0] || '', param_label: '', param_key: nextParamKey(), sort_order: (list.value.length || 0) + 1, remark: '' })
  dialogVisible.value = true
}

function openEdit(row) {
  editId.value = row.id
  Object.assign(form, { group_name: row.group_name, param_label: row.param_label, param_key: row.param_key, sort_order: row.sort_order, remark: row.remark || '' })
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editId.value) {
      await request.put(`/foundation/params/${editId.value}`, { ...form })
      ElMessage.success('已保存')
    } else {
      await request.post('/foundation/params', { ...form })
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    loadGroup()
    loadGroups()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

async function toggleActive(row, v) {
  try {
    await request.put(`/foundation/params/${row.id}`, { is_active: v ? 1 : 0 })
    row.is_active = v ? 1 : 0
    ElMessage.success(v ? '已启用' : '已停用')
  } catch { }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除「${row.param_label}」？删除后相关下拉不再出现。`, '提示', { type: 'warning' })
  try {
    await request.delete(`/foundation/params/${row.id}/hard`)
    ElMessage.success('已删除')
    loadGroup()
  } catch { }
}

onMounted(() => { loadGroups() })
</script>
