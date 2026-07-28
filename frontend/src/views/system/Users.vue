<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建用户</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="用户名/显示名" clearable style="width: 200px" @keyup.enter="fetchData" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="userList" v-loading="loading" stripe border size="small">
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="display_name" label="显示名" width="140" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="role_name" label="角色" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.role_code === 'admin'" type="danger" size="small">管理员</el-tag>
            <el-tag v-else-if="row.role_code === 'manager'" type="warning" size="small">经理</el-tag>
            <el-tag v-else-if="row.role_code === 'operator'" type="primary" size="small">操作员</el-tag>
            <el-tag v-else-if="row.role_code === 'readonly'" type="info" size="small">只读</el-tag>
            <el-tag v-else size="small">{{ row.role_name || '未分配' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">{{ row.created_at ? String(row.created_at).slice(0, 19) : '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.is_active" link type="warning" @click="toggleActive(row)">停用</el-button>
            <el-button v-else link type="success" @click="toggleActive(row)">启用</el-button>
            <el-button v-if="row.username !== 'admin'" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新建用户'" width="500px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? '留空不修改' : '必填'" />
        </el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%" clearable>
            <el-option v-for="r in roleList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active" v-if="isEdit">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
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
import { authApi } from '../../api/foundation'

const loading = ref(false)
const saving = ref(false)
const userList = ref([])
const roleList = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const editId = ref(null)

const searchForm = reactive({ keyword: '' })
const form = reactive({
  username: '', display_name: '', email: '', password: '', role_id: null, is_active: 1,
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await authApi.listUsers({ keyword: searchForm.keyword })
    userList.value = Array.isArray(res) ? res : []
  } catch (e) {
    userList.value = []
  }
  loading.value = false
}

async function fetchRoles() {
  try {
    const res = await authApi.listRoles()
    roleList.value = Array.isArray(res) ? res : []
  } catch (e) {
    roleList.value = []
  }
}

function resetSearch() {
  searchForm.keyword = ''
  fetchData()
}

function openCreate() {
  isEdit.value = false
  editId.value = null
  form.username = ''
  form.display_name = ''
  form.email = ''
  form.password = ''
  form.role_id = null
  form.is_active = 1
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  form.username = row.username
  form.display_name = row.display_name || ''
  form.email = row.email || ''
  form.password = ''
  form.role_id = row.role_id
  form.is_active = row.is_active
  rules.password[0].required = false
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      const payload = { display_name: form.display_name, email: form.email, role_id: form.role_id, is_active: form.is_active }
      if (form.password) payload.password = form.password
      await authApi.updateUser(editId.value, payload)
      ElMessage.success('用户已更新')
    } else {
      await authApi.createUser({
        username: form.username,
        display_name: form.display_name,
        email: form.email,
        password: form.password,
        role_id: form.role_id,
      })
      ElMessage.success('用户已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已由拦截器处理
  }
  saving.value = false
}

async function toggleActive(row) {
  const newStatus = row.is_active ? 0 : 1
  await authApi.updateUser(row.id, { is_active: newStatus })
  ElMessage.success(newStatus ? '用户已启用' : '用户已停用')
  fetchData()
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '确认', { type: 'warning' })
    await authApi.deleteUser(row.id)
    ElMessage.success('用户已删除')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

onMounted(() => {
  fetchData()
  fetchRoles()
})
</script>
