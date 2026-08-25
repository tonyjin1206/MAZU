<template>
  <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: url('/login-bg.jpg') center / cover no-repeat">
    <el-card style="width: 400px; padding: 20px">
      <template #header>
        <div style="text-align: center">
          <img src="/LOGO-light.svg" alt="MTS" style="width: 64px; height: 64px; border-radius: 14px; margin-bottom: 8px">
          <h2 style="margin: 0; color: #1e293b">MTS</h2>
          <p style="color: #909399; font-size: 13px; margin: 4px 0 0">Mazu Trade System · 请登录</p>
        </div>
      </template>
      <el-form :model="form" :rules="rules" ref="formRef" @keyup.enter="login">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" style="width: 100%" :loading="loading" @click="login">登 录</el-button>
        </el-form-item>
      </el-form>
      <div style="text-align: center; color: #909399; font-size: 12px">
        默认管理员: admin / admin123
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api/foundation'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function login() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await authApi.login(form)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    // 获取用户权限
    try {
      const permRes = await authApi.getMyPermissions()
      localStorage.setItem('permissions', JSON.stringify(permRes.permissions || []))
    } catch {
      localStorage.setItem('permissions', '[]')
    }
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>
