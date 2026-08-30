<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">刷新</el-button>
          <el-button type="primary" @click="openCreate">新建配置</el-button>
        </div>
      </template>
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
          :show-overflow-tooltip="col.prop === 'token' || col.prop === 'callback_url'"
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
          <template v-if="col.prop === 'is_active'" #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑企微配置' : '新建企微配置'" width="600px" destroy-on-close>
      <el-form :model="form" label-width="130px" ref="formRef" :rules="rules">
        <el-form-item label="企业ID CorpID" prop="corp_id">
          <el-input v-model="form.corp_id" />
        </el-form-item>
        <el-form-item label="AgentID" prop="agent_id">
          <el-input v-model="form.agent_id" />
        </el-form-item>
        <el-form-item label="Secret" prop="secret">
          <el-input v-model="form.secret" type="password" show-password :placeholder="isEdit ? '留空则不修改' : '请输入 Secret'" />
        </el-form-item>
        <el-form-item label="Token" prop="token">
          <el-input v-model="form.token" />
        </el-form-item>
        <el-form-item label="EncodingAESKey" prop="encoding_aes_key">
          <el-input v-model="form.encoding_aes_key" />
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
import { ref, reactive, onMounted, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import { systemConfigApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_wecom_columns'
const defaultColumns = [
  { prop: 'corp_id', label: '企业ID', width: 200 , sortable: true },
  { prop: 'agent_id', label: 'AgentID', width: 80 , sortable: true },
  { prop: 'token', label: 'Token', width: 150 , sortable: true },
  { prop: 'is_active', label: '状态', width: 80, align: 'center' , sortable: true },
  { prop: 'callback_url', label: '回调URL', minWidth: 200 , sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const loading = ref(false)
const saving = ref(false)
const tableRef = ref(null)
const list = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const editId = ref(null)

const form = reactive({ corp_id: '', agent_id: '', secret: '', token: '', encoding_aes_key: '' })
const rules = {
  corp_id: [{ required: true, message: '必填', trigger: 'blur' }],
  agent_id: [{ required: true, message: '必填', trigger: 'blur' }],
  secret: isEdit.value ? [] : [{ required: true, message: '必填', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try { list.value = await systemConfigApi.wecom.list() || [] } catch (e) { list.value = [] }
  loading.value = false
  nextTick(initColumnDrag)
}

function openCreate() {
  isEdit.value = false; editId.value = null
  form.corp_id = ''; form.agent_id = ''; form.secret = ''; form.token = ''; form.encoding_aes_key = ''
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true; editId.value = row.id
  Object.assign(form, { corp_id: row.corp_id, agent_id: row.agent_id, secret: '', token: row.token || '', encoding_aes_key: row.encoding_aes_key || '' })
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      const payload = { ...form }
      if (!payload.secret) delete payload.secret   // 留空不修改
      await systemConfigApi.wecom.update(editId.value, payload)
      ElMessage.success('已更新')
    } else {
      await systemConfigApi.wecom.create({ ...form, is_active: 1 })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {}
  saving.value = false
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await systemConfigApi.wecom.delete(row.id)
    ElMessage.success('已删除')
    fetchData()
  } catch (e) {}
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(fetchData)
</script>
