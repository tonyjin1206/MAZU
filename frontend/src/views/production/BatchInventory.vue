<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="query" style="flex-wrap: nowrap">
        <el-form-item label="批次号">
          <el-input v-model="query.batch_no" placeholder="模糊搜索" clearable style="width: 160px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="物料名称">
          <el-input v-model="query.keyword" placeholder="名称/编码" clearable style="width: 160px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="query.warehouse_id" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table
        ref="tableRef"
        :key="columnVersion"
        :data="batchList"
        border stripe v-loading="loading" show-summary :summary-method="getBatchSummary"
        size="small"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in visibleColumns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
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
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'quantity'" #default="{ row }">
            {{ $fq(row.quantity) }}
          </template>
          <template v-else-if="col.prop === 'source_type'" #default="{ row }">
            {{ { purchase: '采购入库', production: '完工入库', transfer: '调拨' }[row.source_type] || row.source_type }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }"><el-button type="primary" link @click="trace(row.batch_no)">追溯</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 追溯结果 -->
    <el-card v-if="traceData.length > 0" style="margin-top: 12px">
      <template #header><span>批次追溯 — {{ traceBatchNo }}</span></template>
      <el-timeline>
        <el-timeline-item v-for="t in traceData" :key="t.id" :timestamp="t.date" :color="t.quantity > 0 ? '#67c23a' : '#e6a23c'">
          {{ { purchase_in: '采购入库', production_in: '完工入库', sale_out: '销售出库', outsource_out: '委外发料' }[t.type] || t.type }}
          数量: {{ t.quantity > 0 ? '+' : '' }}{{ t.quantity }}
          <span style="color: #909399; margin-left: 8px">单据: {{ t.doc_type }} {{ t.doc_no }}</span>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import { productionApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_batchinv_columns'
const defaultColumns = [
  { prop: 'batch_no', label: '批次号', width: 160 },
  { prop: 'warehouse', label: '仓库', width: 120 },
  { prop: 'quantity', label: '库存数量', width: 100, align: 'right' },
  { prop: 'in_date', label: '入库日期', width: 110 },
  { prop: 'source_type', label: '来源', width: 120 },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const tableRef = ref(null)
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

const warehouseList = ref([])
const batchList = ref([])
const traceData = ref([])
const traceBatchNo = ref('')
const loading = ref(false)
const query = reactive({ batch_no: '', keyword: '', warehouse_id: null })

onMounted(async () => {
  initColumnVisible()
  try { warehouseList.value = (await foundationApi.warehouses.list({ page_size: 200 })).items || [] } catch {}
})

function getBatchSummary({ columns, data }) {
  const sums = []
  columns.forEach((col, i) => { sums[i] = '' })
  const qtyCols = ['quantity']
  qtyCols.forEach(prop => {
    const idx = columns.findIndex(c => c.prop === prop)
    if (idx >= 0) sums[idx] = data.reduce((s, r) => s + (Number(r[prop]) || 0), 0)
  })
  if (data.length > 0) sums[0] = '合计'
  return sums
}

async function search() {
  loading.value = true
  try {
    const params = {}
    if (query.batch_no) params.batch_no = query.batch_no
    if (query.keyword) params.keyword = query.keyword
    if (query.warehouse_id) params.warehouse_id = query.warehouse_id
    const res = await productionApi.batch.query(params)
    batchList.value = res.items || []
  } finally { loading.value = false
  nextTick(() => { initColumnDrag(); fitTable(tableRef.value, visibleColumns, batchList) }) }
}

async function trace(batchNo) {
  traceBatchNo.value = batchNo
  const res = await productionApi.batch.trace(batchNo)
  traceData.value = res.trace || []
}

function reset() {
  query.batch_no = ''; query.keyword = ''; query.warehouse_id = null
  batchList.value = []; traceData.value = []
}
</script>
