<template>
  <div>
    <!-- 顶部：搜索条件卡片 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增客户</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="编码/名称/联系人" clearable style="width: 200px" @keyup.enter="fetchData" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 底部：数据表格卡片 -->
    <el-card>
      <el-table :data="tableData" v-loading="loading" border stripe size="small" style="width: 100%">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name_cn" label="中文名" min-width="150" />
        <el-table-column prop="name_en" label="英文名" min-width="150" />
        <el-table-column prop="country" label="国家" width="100" />
        <el-table-column prop="contact_person" label="联系人" width="120" />
        <el-table-column prop="phone" label="电话" width="140" />
        <el-table-column prop="tax_id" label="税号" width="150" />
        <el-table-column prop="payment_terms" label="结算方式" width="100" />
        <el-table-column prop="account_period" label="账期(天)" width="100" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top: 16px; justify-content: flex-end"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增客户' : '编辑客户'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="中文名" prop="name_cn">
          <el-input v-model="form.name_cn" />
        </el-form-item>
        <el-form-item label="英文名" prop="name_en">
          <el-input v-model="form.name_en" />
        </el-form-item>
        <el-form-item label="国家" prop="country">
          <el-select v-model="form.country" filterable allow-create placeholder="搜索或输入" style="width: 100%">
            <el-option v-for="c in countryList" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人" prop="contact_person">
          <el-input v-model="form.contact_person" />
        </el-form-item>
        <el-form-item label="电话" prop="phone">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="税号" prop="tax_id">
          <el-input v-model="form.tax_id" />
        </el-form-item>
        <el-form-item label="结算方式" prop="payment_terms">
          <el-select v-model="form.payment_terms" style="width: 100%">
            <el-option label="T/T" value="TT" />
            <el-option label="L/C" value="LC" />
            <el-option label="D/P" value="DP" />
            <el-option label="D/A" value="DA" />
            <el-option label="O/A" value="OA" />
          </el-select>
        </el-form-item>
        <el-form-item label="账期(天)" prop="account_period">
          <el-input type="number" v-model="form.account_period" :min="0" :step="15" style="width: 100%" />
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
import { foundationApi } from '../../api/foundation'

const countryList = [
  '中国', '美国', '日本', '韩国', '德国', '英国', '法国', '意大利', '西班牙',
  '荷兰', '比利时', '瑞士', '瑞典', '挪威', '丹麦', '芬兰', '澳大利亚',
  '新西兰', '加拿大', '墨西哥', '巴西', '阿根廷', '智利', '印度',
  '印度尼西亚', '马来西亚', '菲律宾', '新加坡', '泰国', '越南', '缅甸',
  '柬埔寨', '老挝', '阿联酋', '沙特阿拉伯', '土耳其', '俄罗斯', '南非',
  '尼日利亚', '埃及', '肯尼亚',
]

const loading = ref(false)
const tableData = ref([])
const pagination = ref({ page: 1, pageSize: 20, total: 0 })

const searchForm = reactive({ keyword: '' })

const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null, code: '', name_cn: '', name_en: '', country: '',
  contact_person: '', phone: '', tax_id: '', payment_terms: 'TT', account_period: 30,
})

const rules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name_cn: [{ required: true, message: '请输入中文名', trigger: 'blur' }],
  country: [{ required: true, message: '请选择国家', trigger: 'change' }],
  contact_person: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入电话', trigger: 'blur' }],
  tax_id: [{ required: true, message: '请输入税号', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      keyword: searchForm.keyword || undefined,
    }
    const res = await foundationApi.customers.list(params)
    tableData.value = res.items || res.data?.items || []
    pagination.value.total = res.total || res.data?.total || 0
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.keyword = ''
  pagination.value.page = 1
  fetchData()
}

function resetForm() {
  Object.assign(form, {
    id: null, code: '', name_cn: '', name_en: '', country: '',
    contact_person: '', phone: '', tax_id: '', payment_terms: 'TT', account_period: 30,
  })
}

function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    form.id = row.id
    form.code = row.code
    form.name_cn = row.name_cn || ''
    form.name_en = row.name_en || ''
    form.country = row.country || ''
    form.contact_person = row.contact_person || ''
    form.phone = row.phone || ''
    form.tax_id = row.tax_id || ''
    form.payment_terms = row.payment_terms || 'TT'
    form.account_period = row.account_period ?? 30
  } else {
    resetForm()
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
      await foundationApi.customers.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.customers.update(form.id, payload)
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
    await ElMessageBox.confirm(`确认删除客户「${row.name_cn}」？`, '提示', { type: 'warning' })
    await foundationApi.customers.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(fetchData)
</script>
