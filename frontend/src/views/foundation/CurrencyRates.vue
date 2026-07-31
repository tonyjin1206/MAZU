<template>
  <div>
    <!-- ===== 币种管理 ===== -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>币种档案</span>
          <el-button type="primary" @click="openCurrencyDialog('create')">新增币种</el-button>
        </div>
      </template>
      <el-table :data="currencyList" v-loading="currencyLoading" stripe border size="small" style="width: 100%">
        <el-table-column prop="code" label="编码" width="120" sortable />
        <el-table-column prop="name" label="名称" min-width="140" sortable />
        <el-table-column prop="symbol" label="符号" width="100" />
        <el-table-column prop="is_base" label="本位币" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_base === 1 ? 'success' : 'info'">{{ row.is_base === 1 ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openCurrencyDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDeleteCurrency(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="currencyPage" v-model:page-size="currencyPageSize" :total="currencyTotal"
        :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
        @size-change="fetchCurrencies" @current-change="fetchCurrencies" style="margin-top: 16px" />
    </el-card>

    <!-- ===== 汇率管理 ===== -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>汇率维护（{{ baseCurrencyLabel }}）<el-text v-if="rateFetchedAt" type="info" size="small" style="margin-left: 8px">上次自动获取：{{ rateFetchedAt }}</el-text></span>
          <div>
            <el-button :loading="rateFetching" @click="handleFetchRates">获取最新汇率</el-button>
            <el-button type="primary" @click="openRateDialog('create')">新增汇率</el-button>
          </div>
        </div>
      </template>
      <el-table :data="rateList" v-loading="rateLoading" stripe border size="small" style="width: 100%">
        <el-table-column prop="currency_code" label="币种" width="120" sortable />
        <el-table-column label="汇率" width="220" sortable>
          <template #default="{ row }">1 {{ row.currency_code }} = {{ row.rate }} {{ baseCurrencyLabel }}</template>
        </el-table-column>
        <el-table-column prop="rate_date" label="生效日期" width="140" sortable />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openRateDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDeleteRate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="ratePage" v-model:page-size="ratePageSize" :total="rateTotal"
        :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
        @size-change="fetchRates" @current-change="fetchRates" style="margin-top: 16px" />
    </el-card>

    <!-- 币种对话框 -->
    <el-dialog v-model="currencyDialogVisible" :title="currencyDialogMode === 'create' ? '新增币种' : '编辑币种'" width="440px">
      <el-form :model="currencyForm" label-width="80px">
        <el-form-item label="编码" required>
          <el-input v-model="currencyForm.code" :disabled="currencyDialogMode === 'edit'" placeholder="如 USD" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="currencyForm.name" placeholder="如 美元" />
        </el-form-item>
        <el-form-item label="符号">
          <el-input v-model="currencyForm.symbol" placeholder="如 $" style="width: 120px" />
        </el-form-item>
        <el-form-item label="本位币">
          <el-switch v-model="currencyForm.is_base" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="currencyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="currencySaving" @click="handleSaveCurrency">保存</el-button>
      </template>
    </el-dialog>

    <!-- 汇率对话框 -->
    <el-dialog v-model="rateDialogVisible" :title="rateDialogMode === 'create' ? '新增汇率' : '编辑汇率'" width="460px">
      <el-alert v-if="rateForm.currency_id && baseCurrency" type="info" :closable="false" style="margin-bottom: 10px"
        :title="`1 ${selectedCurrencyCode} = ${rateForm.rate} ${baseCurrency.code}（${baseCurrency.name}）`" />
      <el-form :model="rateForm" label-width="80px">
        <el-form-item label="币种" required>
          <el-select v-model="rateForm.currency_id" placeholder="选择币种（本位币无需维护，恒为 1）" style="width: 100%" filterable>
            <el-option v-for="c in rateableCurrencies" :key="c.id" :label="`${c.code} ${c.name}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="汇率" required>
          <el-input-number v-model="rateForm.rate" :min="0.0001" :precision="4" :step="0.1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker v-model="rateForm.rate_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="rateSaving" @click="handleSaveRate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { foundationApi } from '../../api/foundation'

// ===== 币种 =====
const currencyList = ref([])
const currencyLoading = ref(false)
const currencyTotal = ref(0)
const currencyPage = ref(1)
const currencyPageSize = ref(20)

async function fetchCurrencies() {
  currencyLoading.value = true
  try {
    const res = await foundationApi.currencies.list({ page: currencyPage.value, page_size: currencyPageSize.value })
    currencyList.value = res.items || []
    currencyTotal.value = res.total || 0
  } finally { currencyLoading.value = false }
}

const currencyDialogVisible = ref(false)
const currencyDialogMode = ref('create')
const currencySaving = ref(false)
const currencyForm = reactive({ id: null, code: '', name: '', symbol: '', is_base: 0 })

function openCurrencyDialog(mode, row) {
  currencyDialogMode.value = mode
  if (mode === 'create') {
    Object.assign(currencyForm, { id: null, code: '', name: '', symbol: '', is_base: 0 })
  } else {
    Object.assign(currencyForm, { id: row.id, code: row.code, name: row.name, symbol: row.symbol || '', is_base: row.is_base || 0 })
  }
  currencyDialogVisible.value = true
}

async function handleSaveCurrency() {
  if (!currencyForm.code || !currencyForm.name) {
    ElMessage.warning('编码和名称为必填')
    return
  }
  currencySaving.value = true
  try {
    const payload = { code: currencyForm.code, name: currencyForm.name, symbol: currencyForm.symbol, is_base: currencyForm.is_base }
    if (currencyDialogMode.value === 'create') {
      await foundationApi.currencies.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.currencies.update(currencyForm.id, payload)
      ElMessage.success('更新成功')
    }
    currencyDialogVisible.value = false
    fetchCurrencies()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { currencySaving.value = false }
}

async function handleDeleteCurrency(row) {
  await ElMessageBox.confirm(`确认删除币种「${row.code}」？`, '提示', { type: 'warning' })
  try {
    await foundationApi.currencies.remove(row.id)
    ElMessage.success('删除成功')
    fetchCurrencies()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败（可能已被单据引用）')
  }
}

// ===== 汇率 =====
const rateList = ref([])
const rateLoading = ref(false)
const rateTotal = ref(0)
const ratePage = ref(1)
const ratePageSize = ref(20)

// 本位币（is_base=1）与可维护汇率币种（排除本位币自身）
const baseCurrency = computed(() => currencyList.value.find(c => c.is_base === 1) || null)
const baseCurrencyLabel = computed(() => baseCurrency.value ? `兑${baseCurrency.value.code}（${baseCurrency.value.name}）` : '兑本位币')
const rateableCurrencies = computed(() => currencyList.value.filter(c => c.is_base !== 1))

async function fetchRates() {
  rateLoading.value = true
  try {
    const res = await foundationApi.exchangeRates.list({ page: ratePage.value, page_size: ratePageSize.value })
    rateList.value = res.items || []
    rateTotal.value = res.total || 0
  } finally { rateLoading.value = false }
}

// 从腾讯财经（国内源）自动获取最新汇率；每日 09:00 系统自动执行一次
const rateFetching = ref(false)
const rateFetchedAt = ref('')

async function handleFetchRates() {
  rateFetching.value = true
  try {
    const res = await foundationApi.fetchExchangeRates()
    ElMessage.success(res.message || '汇率已更新')
    rateFetchedAt.value = `${res.rate_date} ${new Date().toTimeString().slice(0, 5)}`
    fetchRates()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取失败（请检查网络）')
  } finally { rateFetching.value = false }
}

const rateDialogVisible = ref(false)
const rateDialogMode = ref('create')
const rateSaving = ref(false)
const rateForm = reactive({ id: null, currency_id: null, rate: 1, rate_date: new Date().toISOString().slice(0, 10) })

const selectedCurrencyCode = computed(() => {
  const c = currencyList.value.find(x => x.id === rateForm.currency_id)
  return c ? c.code : ''
})

function openRateDialog(mode, row) {
  rateDialogMode.value = mode
  if (mode === 'create') {
    Object.assign(rateForm, { id: null, currency_id: null, rate: 1, rate_date: new Date().toISOString().slice(0, 10) })
  } else {
    Object.assign(rateForm, { id: row.id, currency_id: row.currency_id, rate: row.rate, rate_date: row.rate_date })
  }
  rateDialogVisible.value = true
}

async function handleSaveRate() {
  if (!rateForm.currency_id) {
    ElMessage.warning('请选择币种')
    return
  }
  if (!baseCurrency.value) {
    ElMessage.warning('请先在币种档案中设置本位币（is_base=是）')
    return
  }
  // 同币种+同生效日期查重（编辑时排除自身）
  const dup = rateList.value.find(r =>
    r.currency_id === rateForm.currency_id && r.rate_date === rateForm.rate_date && r.id !== rateForm.id)
  if (dup) {
    ElMessage.warning(`该币种 ${rateForm.rate_date} 已有汇率记录，请直接编辑`)
    return
  }
  rateSaving.value = true
  try {
    const payload = { currency_id: rateForm.currency_id, rate: rateForm.rate, rate_date: rateForm.rate_date, source: '手动' }
    if (rateDialogMode.value === 'create') {
      await foundationApi.exchangeRates.create(payload)
      ElMessage.success('新增成功')
    } else {
      await foundationApi.exchangeRates.update(rateForm.id, payload)
      ElMessage.success('更新成功')
    }
    rateDialogVisible.value = false
    fetchRates()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { rateSaving.value = false }
}

async function handleDeleteRate(row) {
  await ElMessageBox.confirm(`确认删除该汇率记录？`, '提示', { type: 'warning' })
  try {
    await foundationApi.exchangeRates.remove(row.id)
    ElMessage.success('删除成功')
    fetchRates()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => { fetchCurrencies(); fetchRates() })
</script>
