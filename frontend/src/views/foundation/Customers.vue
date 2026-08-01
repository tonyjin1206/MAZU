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
        <el-form-item label="编码">
          <el-input v-model="searchForm.code" placeholder="编码" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name_cn" placeholder="名称" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="searchForm.contact_person" placeholder="联系人" clearable style="width: 120px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="国家">
          <el-input v-model="searchForm.country" placeholder="国家" clearable style="width: 120px" @keyup.enter="fetchData" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 底部：数据表格卡片 -->
    <el-card>
      <el-table
        :key="columnVersion"
        ref="tableRef"
        :data="filteredList"
        v-loading="loading"
        border stripe size="small"
        style="width: 100%"
        :row-class-name="rowClassName"
      >
        <el-table-column
          v-for="col in visibleColumns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :sortable="col.sortable"
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
                  <el-dropdown-item v-for="c in allColumns" :key="c.prop">
                    <el-checkbox :model-value="c.visible !== false" @change="toggleColumn(c)">{{ c.label }}</el-checkbox>
                  </el-dropdown-item>
                                  <el-dropdown-item divided @click.stop="openOrderDialog" style="color: #409eff">列排序...</el-dropdown-item>
</el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
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
      <el-pagination
        style="margin-top: 16px"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增客户' : '编辑客户'" width="640px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" disabled />
        </el-form-item>
        <el-form-item label="中文名" prop="name_cn">
          <el-input v-model="form.name_cn" />
        </el-form-item>
        <el-form-item label="英文名" prop="name_en">
          <el-input v-model="form.name_en" />
        </el-form-item>
        <el-form-item label="国家" prop="country">
          <el-select v-model="form.country" filterable placeholder="选择国家" style="width: 100%">
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
        <el-form-item label="客户地址" prop="address">
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
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
    <ColumnOrderDialog v-model:visible="orderDialogVisible" :columns="orderList" @opened="initOrderDrag" @confirm="confirmOrder" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick , watch} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnOrderDialog from '../../components/ColumnOrderDialog.vue'
import { foundationApi } from '../../api/foundation'
import request from '../../api/request'

// 国家列表（来自参数设置「国家」组，可在参数设置里自行增删）
const countryList = ref([])
async function loadCountries() {
  try {
    const opts = await request.get('/foundation/params/options', { params: { group: 'country' } }) || []
    countryList.value = opts.map(o => o.label)
  } catch { countryList.value = [] }
}

// ===== 列配置（可拖拽排序，localStorage 记住个人偏好）=====
const STORAGE_KEY = 'mazu_customer_columns'
const defaultColumns = [
  { prop: 'code', label: '编码', width: 120, sortable: true },
  { prop: 'name_cn', label: '中文名', minWidth: 150, sortable: true },
  { prop: 'country', label: '国家', width: 100, sortable: true },
  { prop: 'contact_person', label: '联系人', width: 110, sortable: true },
  { prop: 'phone', label: '电话', width: 130, sortable: true },
  { prop: 'address', label: '客户地址', minWidth: 180 },
  { prop: 'bank_name', label: '开户行', width: 140 },
  { prop: 'bank_account', label: '银行账号', width: 140 },
  { prop: 'default_tax_rate', label: '默认税率', width: 90, align: 'center' },
  { prop: 'rating', label: '评级', width: 110, align: 'center' },
  { prop: 'payment_terms', label: '结算方式', width: 100, sortable: true },
  { prop: 'account_period', label: '账期(天)', width: 90, sortable: true },
  { prop: 'tax_id', label: '税号', width: 140 },
  { prop: 'created_at', label: '创建时间', width: 150 },
  { prop: 'is_active', label: '状态', width: 80, align: 'center' },
]

const { columns, columnVersion, initColumnDrag, orderDialogVisible, orderList, openOrderDialog, initOrderDrag, confirmOrder } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

function rowClassName({ row }) {
  return row.is_active === 0 ? 'mazu-disabled-row' : ''
}

function formatTime(t) {
  if (!t) return ''
  return t.replace('T', ' ').slice(0, 16)
}

const loading = ref(false)
const tableData = ref([])
const pagination = ref({ page: 1, pageSize: 100, total: 0 })

const filteredList = computed(() => tableData.value)

const searchForm = reactive({ code: '', name_cn: '', contact_person: '', country: '' })

const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)
const formRef = ref(null)
const tableRef = ref(null)

const form = reactive({
  id: null, code: '', name_cn: '', name_en: '', country: '',
  contact_person: '', phone: '', email: '', tax_id: '', address: '',
  bank_name: '', bank_account: '', default_tax_rate: 13, rating: 3,
  payment_terms: 'TT', account_period: 30, remark: '',
})

const rules = {
  name_cn: [{ required: true, message: '请输入中文名', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      code: searchForm.code || undefined,
      name_cn: searchForm.name_cn || undefined,
      contact_person: searchForm.contact_person || undefined,
      country: searchForm.country || undefined,
    }
    const res = await foundationApi.customers.list(params)
    tableData.value = res.items || res.data?.items || []
    pagination.value.total = res.total || res.data?.total || 0
    nextTick(() => { initColumnDrag(); fitTable(tableRef.value, columns, filteredList) })
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  Object.assign(searchForm, { code: '', name_cn: '', contact_person: '', country: '' })
  pagination.value.page = 1
  fetchData()
}

function resetForm() {
  Object.assign(form, {
    id: null, code: '', name_cn: '', name_en: '', country: '',
    contact_person: '', phone: '', email: '', tax_id: '', address: '',
    bank_name: '', bank_account: '', default_tax_rate: 13, rating: 3,
    payment_terms: 'TT', account_period: 30, remark: '',
  })
}

async function openDialog(mode, row) {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    Object.assign(form, {
      id: row.id, code: row.code || '', name_cn: row.name_cn || '',
      name_en: row.name_en || '', country: row.country || '',
      contact_person: row.contact_person || '', phone: row.phone || '',
      email: row.email || '', tax_id: row.tax_id || '', address: row.address || '',
      bank_name: row.bank_name || '', bank_account: row.bank_account || '',
      default_tax_rate: row.default_tax_rate ?? 13, rating: row.rating ?? 3,
      payment_terms: row.payment_terms || 'TT', account_period: row.account_period ?? 30,
      remark: row.remark || '',
    })
  } else {
    resetForm()
    // 预取下一个编码号，显示在编码框中让用户预览
    try {
      const res = await foundationApi.customers.nextCode()
      form.code = res.code
    } catch (e) { /* 获取失败不阻塞用户操作 */ }
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
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除客户「${row.name_cn}」？删除后不可恢复。`, '提示', { type: 'warning' })
    await foundationApi.customers.delete(row.id)
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
      `确认${action}客户「${row.name_cn}」？${toActive === 0 ? '停用后下单选择客户时将看不到该客户。' : ''}`,
      '提示', { type: 'warning' }
    )
    await foundationApi.customers.update(row.id, { is_active: toActive })
    ElMessage.success(`${action}成功`)
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(`${action}失败`)
  }
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnVisible(); initColumnDrag() })
})

onMounted(() => {
  initColumnVisible()
  fetchData()
  loadCountries()
})
</script>

<style scoped>
:deep(.mazu-disabled-row) {
  opacity: 0.55;
  background-color: #fafafa;
}

:deep(.col-header-wrap) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

:deep(.col-drag-handle) {
  cursor: grab;
  color: #909399;
  font-size: 13px;
  user-select: none;
  padding: 0 2px;
  border-radius: 3px;
}

:deep(.col-drag-handle:hover) {
  color: #409eff;
  background: #ecf5ff;
}

:deep(.col-drag-handle:active) {
  cursor: grabbing;
}
</style>
