<template>
  <div>
    <!-- 顶部卡片：header 靠右按钮 + body 搜索条件 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openDialog('create')">新增供应商</el-button>
        </div>
      </template>
      <el-form :model="searchForm" inline>
        <el-form-item label="编码">
          <el-input v-model="searchForm.code" placeholder="编码" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="名称" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="searchForm.contact_person" placeholder="联系人" clearable style="width: 120px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="国家">
          <el-input v-model="searchForm.country" placeholder="国家" clearable style="width: 120px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="searchForm.supplier_type" placeholder="类型" clearable style="width: 120px">
            <el-option label="原材料" value="原材料" />
            <el-option label="委外" value="委外" />
            <el-option label="辅料" value="辅料" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 底部卡片：边框表格 -->
    <el-card>
      <el-table
        :key="columnVersion"
        :data="filteredList"
        v-loading="loading"
        stripe border size="small"
        style="width: 100%"
        :row-class-name="rowClassName"
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
          <template v-if="col.prop === 'is_active'" #default="{ row }">
            <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">
              {{ row.is_active === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
          <template v-else-if="col.prop === 'rating'" #default="{ row }">
            <el-rate :model-value="row.rating" disabled :max="5" size="small" />
          </template>
          <template v-else-if="col.prop === 'created_at'" #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
          <template v-else-if="col.prop === 'default_tax_rate'" #default="{ row }">
            {{ row.default_tax_rate }}%
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            <el-button link :type="row.is_active === 1 ? 'warning' : 'success'" size="small" @click="handleToggle(row)">
              {{ row.is_active === 1 ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @size-change="fetchData" @current-change="fetchData" style="margin-top: 16px" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增供应商' : '编辑供应商'" width="640px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" disabled placeholder="自动生成（SU+6位流水号）" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
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
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="税号" prop="tax_id">
          <el-input v-model="form.tax_id" />
        </el-form-item>
        <el-form-item label="供应商地址" prop="address">
          <el-input v-model="form.address" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="开户行" prop="bank_name">
          <el-input v-model="form.bank_name" />
        </el-form-item>
        <el-form-item label="银行账号" prop="bank_account">
          <el-input v-model="form.bank_account" />
        </el-form-item>
        <el-form-item label="默认税率(%)" prop="default_tax_rate">
          <el-input type="number" v-model="form.default_tax_rate" :min="0" :max="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="评级" prop="rating">
          <el-rate v-model="form.rating" :max="5" />
        </el-form-item>
        <el-form-item label="付款条件" prop="payment_terms">
          <el-select v-model="form.payment_terms" style="width: 100%">
            <el-option label="T/T" value="TT" />
            <el-option label="L/C" value="LC" />
            <el-option label="O/A" value="OA" />
          </el-select>
        </el-form-item>
        <el-form-item label="账期(天)" prop="account_period">
          <el-input type="number" v-model="form.account_period" :min="0" :step="15" style="width: 100%" />
        </el-form-item>
        <el-form-item label="类型" prop="supplier_type">
          <el-select v-model="form.supplier_type" style="width: 100%">
            <el-option label="原材料" value="原材料" />
            <el-option label="委外" value="委外" />
            <el-option label="辅料" value="辅料" />
          </el-select>
        </el-form-item>
        <el-form-item label="供货范围" prop="supply_range">
          <el-input v-model="form.supply_range" type="textarea" :rows="2" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Sortable from 'sortablejs'
import { foundationApi } from '../../api/foundation'

const countryList = [
  '中国', '美国', '日本', '韩国', '德国', '英国', '法国', '意大利', '西班牙',
  '荷兰', '比利时', '瑞士', '瑞典', '挪威', '丹麦', '芬兰', '澳大利亚',
  '新西兰', '加拿大', '墨西哥', '巴西', '阿根廷', '智利', '印度',
  '印度尼西亚', '马来西亚', '菲律宾', '新加坡', '泰国', '越南', '缅甸',
  '柬埔寨', '老挝', '阿联酋', '沙特阿拉伯', '土耳其', '俄罗斯', '南非',
  '尼日利亚', '埃及', '肯尼亚',
]

// ===== 列配置（可拖拽排序，localStorage 记住个人偏好）=====
const STORAGE_KEY = 'mazu_supplier_columns'
const defaultColumns = [
  { prop: 'code', label: '编码', width: 120, sortable: true },
  { prop: 'name', label: '名称', minWidth: 150, sortable: true },
  { prop: 'country', label: '国家', width: 100, sortable: true },
  { prop: 'contact_person', label: '联系人', width: 110, sortable: true },
  { prop: 'phone', label: '电话', width: 130, sortable: true },
  { prop: 'address', label: '供应商地址', minWidth: 180 },
  { prop: 'bank_name', label: '开户行', width: 140 },
  { prop: 'bank_account', label: '银行账号', width: 140 },
  { prop: 'default_tax_rate', label: '默认税率', width: 90, align: 'center' },
  { prop: 'rating', label: '评级', width: 110, align: 'center' },
  { prop: 'payment_terms', label: '付款条件', width: 100, sortable: true },
  { prop: 'account_period', label: '账期(天)', width: 90, sortable: true },
  { prop: 'tax_id', label: '税号', width: 140 },
  { prop: 'supplier_type', label: '类型', width: 100, sortable: true },
  { prop: 'created_at', label: '创建时间', width: 150 },
  { prop: 'is_active', label: '状态', width: 80, align: 'center' },
]

function loadColumnOrder() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    if (saved.length) {
      const savedSet = new Set(saved)
      const others = defaultColumns.filter(c => !savedSet.has(c.prop))
      // 按保存的顺序返回，缺失的列补在后面
      return [...saved.map(prop => defaultColumns.find(c => c.prop === prop)).filter(Boolean), ...others]
    }
  } catch (e) { /* 忽略损坏的存储 */ }
  return [...defaultColumns]
}

const columns = ref(loadColumnOrder())
const columnVersion = ref(0)
let sortableInstance = null
let dragRetryTimer = null

function initColumnDrag() {
  clearTimeout(dragRetryTimer)
  const thead = document.querySelector('.el-table__header-wrapper thead tr')
  if (!thead) {
    // 表格还没渲染好，稍后重试
    dragRetryTimer = setTimeout(initColumnDrag, 300)
    return
  }
  // 每次重建绑定：el-table 重渲染后旧绑定会失效
  destroyColumnDrag()
  sortableInstance = Sortable.create(thead, {
    animation: 150,
    handle: '.cell',
    filter: (el) => el.classList.contains('el-table-fixed-column--right'),
    onEnd: (evt) => {
      const { oldIndex, newIndex } = evt
      if (oldIndex === newIndex) return
      const cols = [...columns.value]
      const [moved] = cols.splice(oldIndex, 1)
      cols.splice(newIndex, 0, moved)
      columns.value = cols
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cols.map(c => c.prop)))
      // 强制重渲染表格列
      columnVersion.value++
      nextTick(initColumnDrag)
    },
  })
}

function destroyColumnDrag() {
  sortableInstance?.destroy()
  sortableInstance = null
  clearTimeout(dragRetryTimer)
}

function rowClassName({ row }) {
  return row.is_active === 0 ? 'mazu-disabled-row' : ''
}

function formatTime(t) {
  if (!t) return ''
  return t.replace('T', ' ').slice(0, 16)
}

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  code: '',
  name: '',
  contact_person: '',
  country: '',
  supplier_type: '',
})

const filteredList = computed(() => tableData.value)

function resetSearch() {
  Object.assign(searchForm, { code: '', name: '', contact_person: '', country: '', supplier_type: '' })
  page.value = 1
  fetchData()
}

const form = reactive({
  id: null, code: '', name: '', country: '', contact_person: '',
  phone: '', email: '', tax_id: '', address: '',
  payment_terms: 'TT', account_period: 30,
  supplier_type: '原材料', rating: 3,
  bank_name: '', bank_account: '', default_tax_rate: 13,
  supply_range: '', remark: '',
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await foundationApi.suppliers.list({
      page: page.value,
      page_size: pageSize.value,
      code: searchForm.code || undefined,
      name: searchForm.name || undefined,
      contact_person: searchForm.contact_person || undefined,
      country: searchForm.country || undefined,
      supplier_type: searchForm.supplier_type || undefined,
    })
    tableData.value = res.items || []
    total.value = res.total || 0
    nextTick(initColumnDrag)
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    id: null, code: '', name: '', country: '', contact_person: '',
    phone: '', email: '', tax_id: '', address: '',
    payment_terms: 'TT', account_period: 30,
    supplier_type: '原材料', rating: 3,
    bank_name: '', bank_account: '', default_tax_rate: 13,
    supply_range: '', remark: '',
  })
}

function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    Object.assign(form, {
      id: row.id, code: row.code || '', name: row.name || '', country: row.country || '',
      contact_person: row.contact_person || '', phone: row.phone || '',
      email: row.email || '', tax_id: row.tax_id || '', address: row.address || '',
      payment_terms: row.payment_terms || 'TT', account_period: row.account_period ?? 30,
      supplier_type: row.supplier_type || '原材料', rating: row.rating ?? 3,
      bank_name: row.bank_name || '', bank_account: row.bank_account || '',
      default_tax_rate: row.default_tax_rate ?? 13,
      supply_range: row.supply_range || '', remark: row.remark || '',
    })
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
      await foundationApi.suppliers.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.suppliers.update(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除供应商「${row.name}」？删除后不可恢复。`, '提示', { type: 'warning' })
    await foundationApi.suppliers.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || '删除失败')
    }
  }
}

async function handleToggle(row) {
  const toActive = row.is_active === 1 ? 0 : 1
  const action = toActive === 0 ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确认${action}供应商「${row.name}」？${toActive === 0 ? '停用后下单选择供应商时将看不到该供应商。' : ''}`,
      '提示', { type: 'warning' }
    )
    await foundationApi.suppliers.update(row.id, { is_active: toActive })
    ElMessage.success(`${action}成功`)
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(`${action}失败`)
  }
}

onMounted(() => {
  fetchData()
})
onBeforeUnmount(destroyColumnDrag)
</script>

<style scoped>
:deep(.mazu-disabled-row) {
  opacity: 0.55;
  background-color: #fafafa;
}
</style>
