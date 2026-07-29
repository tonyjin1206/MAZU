<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">刷新</el-button>
          <el-button type="primary" @click="openCreate">新建配置</el-button>
        </div>
      </template>
      <el-table :data="list" v-loading="loading" stripe border size="small">
        <el-table-column prop="corp_id" label="企业ID" width="200" />
        <el-table-column prop="agent_id" label="AgentID" width="80" />
        <el-table-column prop="token" label="Token" width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="callback_url" label="回调URL" min-width="200" show-overflow-tooltip />
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
          <el-input v-model="form.secret" type="password" show-password />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemConfigApi } from '../../api/foundation'

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const editId = ref(null)

const form = reactive({ corp_id: '', agent_id: '', secret: '', token: '', encoding_aes_key: '' })
const rules = {
  corp_id: [{ required: true, message: '必填', trigger: 'blur' }],
  agent_id: [{ required: true, message: '必填', trigger: 'blur' }],
  secret: [{ required: true, message: '必填', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try { list.value = await systemConfigApi.wecom.list() || [] } catch { list.value = [] }
  loading.value = false
}

function openCreate() {
  isEdit.value = false; editId.value = null
  form.corp_id = ''; form.agent_id = ''; form.secret = ''; form.token = ''; form.encoding_aes_key = ''
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true; editId.value = row.id
  Object.assign(form, { corp_id: row.corp_id, agent_id: row.agent_id, secret: row.secret, token: row.token || '', encoding_aes_key: row.encoding_aes_key || '' })
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await systemConfigApi.wecom.update(editId.value, { ...form })
      ElMessage.success('已更新')
    } else {
      await systemConfigApi.wecom.create({ ...form, is_active: 1 })
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
    await systemConfigApi.wecom.delete(row.id)
    ElMessage.success('已删除')
    fetchData()
  } catch {}
}

onMounted(fetchData)
</script>
