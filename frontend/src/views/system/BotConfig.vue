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
          v-for="col in columns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :align="col.align"
          :show-overflow-tooltip="col.prop === 'base_url'"
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
          <template v-if="col.prop === 'is_active'" #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑AI配置' : '新建AI配置'" width="800px" destroy-on-close>
      <el-form :model="form" label-width="110px" ref="formRef" :rules="rules">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="提供商" prop="provider">
              <el-select v-model="form.provider" style="width:100%">
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="OpenAI" value="openai" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="模型" prop="model">
              <el-input v-model="form.model" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="温度" prop="temperature">
              <el-slider v-model="form.temperature" :min="0" :max="1" :step="0.05" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="form.api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="API 地址" prop="base_url">
          <el-input v-model="form.base_url" placeholder="留空使用官方地址" />
        </el-form-item>
        <el-form-item label="系统提示词">
          <div style="margin-bottom: 6px">
            <el-button size="small" @click="restoreDefault">恢复默认</el-button>
            <span style="color:#909399;font-size:11px;margin-left:8px">编辑此提示词可调整 Bot 行为</span>
          </div>
          <el-input v-model="form.system_prompt" type="textarea" :rows="16" style="font-family: monospace; font-size: 12px" />
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
const STORAGE_KEY = 'mazu_bot_columns'
const defaultColumns = [
  { prop: 'provider', label: '提供商', width: 100 , sortable: true },
  { prop: 'model', label: '模型', width: 160 , sortable: true },
  { prop: 'is_active', label: '状态', width: 70, align: 'center' , sortable: true },
  { prop: 'temperature', label: '温度', width: 60 , sortable: true },
  { prop: 'base_url', label: 'API地址', minWidth: 200 , sortable: true },
]
const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const loading = ref(false)
const saving = ref(false)
const tableRef = ref(null)
const list = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const editId = ref(null)

const defaultPrompt = ref('')

const form = reactive({
  provider: 'deepseek', api_key: '', base_url: '', model: 'deepseek-chat',
  temperature: 0.1, max_tokens: 1024, system_prompt: '',
  is_active: 1,
})
const rules = {
  provider: [{ required: true, message: '必选', trigger: 'change' }],
  api_key: [{ required: true, message: '必填', trigger: 'blur' }],
  model: [{ required: true, message: '必填', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try { list.value = await systemConfigApi.bot.list() || [] } catch { list.value = [] }
  loading.value = false
  nextTick(initColumnDrag)
}

async function fetchDefaultPrompt() {
  try {
    const res = await systemConfigApi.bot.defaultPrompt()
    defaultPrompt.value = res.system_prompt
  } catch {}
}

function openCreate() {
  isEdit.value = false; editId.value = null
  form.provider = 'deepseek'; form.api_key = ''; form.base_url = ''
  form.model = 'deepseek-chat'; form.temperature = 0.1; form.system_prompt = defaultPrompt.value
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true; editId.value = row.id
  Object.assign(form, {
    provider: row.provider, api_key: row.api_key, base_url: row.base_url || '',
    model: row.model, temperature: row.temperature, system_prompt: row.system_prompt || '',
  })
  dialogVisible.value = true
}

async function restoreDefault() {
  if (!defaultPrompt.value) await fetchDefaultPrompt()
  form.system_prompt = defaultPrompt.value
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await systemConfigApi.bot.update(editId.value, { ...form })
      ElMessage.success('已更新')
    } else {
      await systemConfigApi.bot.create({ ...form })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch {}
  saving.value = false
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await systemConfigApi.bot.delete(row.id)
    ElMessage.success('已删除')
    fetchData()
  } catch {}
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(() => { fetchData(); fetchDefaultPrompt() })
</script>
