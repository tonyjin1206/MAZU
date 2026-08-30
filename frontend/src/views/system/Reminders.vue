<template>
  <div>
    <el-card style="margin-bottom:12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">刷新</el-button>
          <el-button type="primary" data-testid="btn-create-reminder" @click="openCreate">新建提醒</el-button>
        </div>
      </template>
    </el-card>

    <el-card>
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef"
        :key="columnVersion"
        :data="list"
        v-loading="loading"
        stripe border size="small"
      >
        <el-table-column
          v-for="col in visibleColumns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
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
          <template v-if="col.prop === 'type'" #default="{ row }">
            <el-tag v-if="row.type==='daily_todo'" size="small">日待办</el-tag>
            <el-tag v-else-if="row.type==='expiry'" type="warning" size="small">到期提醒</el-tag>
            <el-tag v-else-if="row.type==='overdue'" type="danger" size="small">逾期告警</el-tag>
            <el-tag v-else-if="row.type==='weekly'" type="success" size="small">周报</el-tag>
            <el-tag v-else-if="row.type==='boss_report'" type="primary" size="small">老板日报</el-tag>
            <span v-else>{{ row.type }}</span>
          </template>
          <template v-else-if="col.prop === 'enabled'" #default="{ row }">
            <el-switch :model-value="row.enabled" @change="(v) => toggleEnable(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建提醒" width="500px" destroy-on-close data-testid="dialog-reminder">
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="用户" prop="user_id">
          <el-select v-model="form.user_id" placeholder="选择用户" filterable style="width:100%">
            <el-option v-for="u in userList" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提醒类型" prop="type">
          <el-select v-model="form.type" style="width:100%">
            <el-option v-for="t in typeList" :key="t.type" :label="t.label" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="推送时间">
          <el-time-picker v-model="form.pushTime" format="HH:mm" value-format="HH:mm" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" data-testid="btn-save" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import { systemConfigApi, authApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_reminder_columns'
const defaultColumns = [
  { prop: 'user_name', label: '用户', width: 120 , sortable: true },
  { prop: 'type', label: '提醒类型', width: 120 , sortable: true },
  { prop: 'enabled', label: '启用', width: 70, align: 'center' , sortable: true },
  { prop: 'push_time', label: '推送时间', width: 100 , sortable: true },
  { prop: 'push_days', label: '推送日', width: 100 , sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const loading = ref(false)
const saving = ref(false)
const tableRef = ref(null)
const list = ref([])
const typeList = ref([])
const userList = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)

const form = reactive({ user_id: null, type: '', pushTime: '09:00' })
const rules = {
  user_id: [{ required: true, message: '必选', trigger: 'change' }],
  type: [{ required: true, message: '必选', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try { list.value = await systemConfigApi.reminders.list() || [] } catch (e) { list.value = [] }
  loading.value = false
  nextTick(initColumnDrag)
}

async function fetchMeta() {
  try { typeList.value = await systemConfigApi.reminders.types() || [] } catch (e) {}
  try { userList.value = await authApi.listUsers() || [] } catch (e) {}
}

function openCreate() {
  form.user_id = null; form.type = ''; form.pushTime = '09:00'
  dialogVisible.value = true
}

async function toggleEnable(row, val) {
  try {
    await systemConfigApi.reminders.update(row.id, { enabled: val ? 1 : 0 })
    row.enabled = val ? 1 : 0
    ElMessage.success(val ? '已启用' : '已停用')
  } catch (e) {}
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await systemConfigApi.reminders.create({
      user_id: form.user_id,
      type: form.type,
      push_time: form.pushTime,
    })
    ElMessage.success('已创建')
    dialogVisible.value = false
    fetchData()
  } catch (e) {}
  saving.value = false
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await systemConfigApi.reminders.delete(row.id)
    ElMessage.success('已删除')
    fetchData()
  } catch (e) {}
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(() => { fetchData(); fetchMeta() })
</script>
