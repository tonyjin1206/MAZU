<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">收发存（原辅料仓库 / 成品仓库）</span>
          <div style="display: flex; gap: 8px">
            <el-button type="primary" @click="fetchData">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
          </div>
        </div>
      </template>
      <el-form :inline="true" label-width="70px">
        <el-form-item label="仓库">
          <el-select v-model="query.warehouse_id" clearable placeholder="全部" style="width: 140px" @change="fetchData">
            <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="物料类型">
          <el-select v-model="query.type" clearable placeholder="全部" style="width: 120px" @change="fetchData">
            <el-option label="原辅料" value="material" />
            <el-option label="成品" value="product" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="query.code" placeholder="物料编码" clearable style="width: 130px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="query.keyword" placeholder="物料名称" clearable style="width: 140px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="query.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 260px" @change="fetchData" />
        </el-form-item>
      </el-form>
<el-table ref="tableRef" :data="dataList" v-loading="loading" stripe border size="small" show-summary :summary-method="summaryMethod">
        <el-table-column prop="warehouse" label="仓库" width="110" sortable />
        <el-table-column prop="material_name" label="物料名称" min-width="140" sortable>
          <template #default="{ row }"><span style="font-weight:500">{{ row.material_name || row.product_name }}</span></template>
        </el-table-column>
        <el-table-column prop="material_code" label="物料编码" min-width="100" sortable>
          <template #default="{ row }"><span style="color: #909399">{{ row.material_code || row.product_code }}</span></template>
        </el-table-column>
        <el-table-column prop="material_spec" label="规格" width="80" sortable>
          <template #default="{ row }">{{ row.material_spec || row.product_spec || '-' }}</template>
        </el-table-column>
        <el-table-column prop="material_id" label="类型" width="80" align="center" sortable>
          <template #default="{ row }">
            <el-tag :type="row.material_id ? 'warning' : 'primary'" size="small">{{ row.material_id ? '原辅料' : '成品' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="opening_qty" label="期初" width="80" align="right" sortable />
        <el-table-column prop="period_in_qty" label="本期入库" width="100" align="right" sortable />
        <el-table-column prop="period_out_qty" label="本期出库" width="100" align="right" sortable />
        <el-table-column prop="closing_qty" label="期末数量" width="100" align="right" sortable />
        <el-table-column prop="closing_cost" label="期末金额" width="110" align="right" sortable>
          <template #default="{ row }">{{ $fm(row.closing_cost) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[50,100,200]" layout="total,sizes,prev,pager,next" @size-change="fetchData" @current-change="fetchData" style="margin-top:12px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'; import { inventoryApi } from '@/api/business'; import { foundationApi } from '@/api/foundation'

const loading = ref(false)
const tableRef = ref(null)
const dataList = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const warehouseList = ref([])

const query = reactive({ warehouse_id: null, type: '', code: '', keyword: '', dateRange: null })

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (query.warehouse_id) params.warehouse_id = query.warehouse_id
    if (query.type) params.type = query.type
    if (query.code) params.code = query.code
    if (query.keyword) params.keyword = query.keyword
    if (query.dateRange && query.dateRange[0]) {
      params.start_date = query.dateRange[0]
      params.end_date = query.dateRange[1]
    }
    const res = await inventoryApi.balance(params)
    dataList.value = res.items || []
    total.value = res.total || 0
  } catch (e) { ElMessage.error('加载失败') } finally { loading.value = false }
}

function resetQuery() {
  Object.assign(query, { warehouse_id: null, type: '', code: '', keyword: '', dateRange: null })
  page.value = 1
  fetchData()
}

function summaryMethod({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) { sums[i] = '合计'; return }
    if (['period_in_qty','period_out_qty','closing_qty'].includes(col.property)) {
      sums[i] = data.reduce((s, r) => s + (r[col.property] || 0), 0)
    } else if (col.property === 'closing_cost') {
      sums[i] = '¥' + data.reduce((s, r) => s + (r.closing_cost || 0), 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
    } else { sums[i] = '' }
  })
  return sums
}

onMounted(async () => {
  try {
    const res = await foundationApi.warehouses.list({ page_size: 100 })
    warehouseList.value = res.items || []
  } catch (e) {}
  // 默认本月
  const now = new Date()
  query.dateRange = [`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-01`, now.toISOString().slice(0,10)]
  fetchData()
})
</script>
