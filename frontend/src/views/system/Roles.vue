<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">刷新</el-button>
          <el-button type="primary" @click="openCreate">新建角色</el-button>
        </div>
      </template>
    </el-card>

    <el-card>
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef"
        :key="columnVersion"
        :data="roleList"
        v-loading="loading"
        stripe border size="small"
        row-key="id"
      >
        <el-table-column
          v-for="col in visibleColumns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :align="col.align"
          :show-overflow-tooltip="col.prop === 'description'"
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
          <template v-if="col.prop === 'permissions'" #default="{ row }">
            <el-tag v-for="pc in row.permission_codes" :key="pc" size="small" style="margin: 2px 4px 2px 0">
              {{ getPermName(pc) }}
            </el-tag>
            <span v-if="!row.permission_codes?.length" style="color: #909399">无权限</span>
          </template>
          <template v-else-if="col.prop === 'is_system'" #default="{ row }">
            <el-tag v-if="row.is_system" type="info" size="small">是</el-tag>
            <span v-else style="color: #909399">否</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="!row.is_system" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新建角色'" width="700px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="角色名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色编码" prop="code">
              <el-input v-model="form.code" :disabled="isEdit" placeholder="英文编码，如 custom_role" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">权限设置</el-divider>
      <div v-if="permGroups.length === 0" style="color: #909399; text-align: center; padding: 20px">加载权限中...</div>
      <div v-for="group in permGroups" :key="group.module" style="margin-bottom: 12px">
        <div style="font-weight: 600; font-size: 13px; margin-bottom: 6px; color: #409eff">
          {{ group.module }}
        </div>
        <el-checkbox-group v-model="form.permission_codes">
          <el-checkbox
            v-for="perm in group.permissions"
            :key="perm.code"
            :label="perm.code"
            :value="perm.code"
            style="margin-right: 16px; margin-bottom: 6px"
          >
            {{ perm.name }}
          </el-checkbox>
        </el-checkbox-group>
      </div>

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
import { authApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_role_columns'
const defaultColumns = [
  { prop: 'name', label: '角色名称', width: 120 , sortable: true },
  { prop: 'code', label: '编码', width: 120 , sortable: true },
  { prop: 'permissions', label: '权限', minWidth: 300 , sortable: true },
  { prop: 'user_count', label: '用户数', width: 70, align: 'center' , sortable: true },
  { prop: 'is_system', label: '内置', width: 70, align: 'center' , sortable: true },
  { prop: 'description', label: '描述', minWidth: 180 , sortable: true },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

const loading = ref(false)
const saving = ref(false)
const tableRef = ref(null)
const roleList = ref([])
const permGroups = ref([])
const permNameMap = ref({})
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const editId = ref(null)

const form = reactive({
  name: '', code: '', description: '', permission_codes: [],
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
}

function getPermName(code) {
  return permNameMap.value[code] || code
}

async function fetchData() {
  loading.value = true
  try {
    const res = await authApi.listRoles()
    roleList.value = Array.isArray(res) ? res : []
  } catch (e) {
    roleList.value = []
  }
  loading.value = false
  nextTick(initColumnDrag)
}

async function fetchPermissions() {
  try {
    const res = await authApi.listPermissions()
    permGroups.value = Array.isArray(res) ? res : []
    // 构建编码→名称映射
    const map = {}
    for (const g of permGroups.value) {
      for (const p of g.permissions) {
        map[p.code] = p.name
      }
    }
    permNameMap.value = map
  } catch (e) {
    permGroups.value = []
  }
}

function openCreate() {
  isEdit.value = false
  editId.value = null
  form.name = ''
  form.code = ''
  form.description = ''
  form.permission_codes = []
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  form.name = row.name
  form.code = row.code
  form.description = row.description || ''
  form.permission_codes = [...(row.permission_codes || [])]
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await authApi.updateRole(editId.value, {
        name: form.name,
        description: form.description,
        permission_codes: form.permission_codes,
      })
      ElMessage.success('角色已更新')
    } else {
      await authApi.createRole({
        name: form.name,
        code: form.code,
        description: form.description,
        permission_codes: form.permission_codes,
      })
      ElMessage.success('角色已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已由拦截器处理
  }
  saving.value = false
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除角色「${row.name}」？`, '确认', { type: 'warning' })
    await authApi.deleteRole(row.id)
    ElMessage.success('角色已删除')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnDrag() })
})

onMounted(() => {
  fetchData()
  fetchPermissions()
})
</script>
