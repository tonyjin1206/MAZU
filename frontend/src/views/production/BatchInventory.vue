<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <el-card style="margin-bottom: 12px; flex: none">
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

    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px; flex: none">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
      <div style="flex: 1; min-height: 0; overflow: auto">
<el-table
        ref="tableRef"
        :key="columnVersion"
        :data="batchList"
        border stripe v-loading="loading" show-summary :summary-method="getBatchSummary"
        size="small"
        style="width: 100%"
        height="100%"
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
                                  <el-dropdown-item @click.stop="openColumnSettings" style="color: #409eff">列设置...</el-dropdown-item>
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
      </div>
    </el-card>

    <!-- 拖动条：上下拉动调节列表/追溯区域高度 -->
    <div
      class="split-bar"
      style="flex: none; height: 8px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none"
      @mousedown="onSplitterDown"
    >
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>

    <!-- 追溯结果 -->
    <el-card v-if="traceData.length > 0" :style="{ flex: '1', minHeight: '140px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <template #header><span>批次追溯 — {{ traceBatchNo }}</span></template>
      <div style="flex: 1; min-height: 0; overflow: auto">
      <el-timeline>
        <el-timeline-item v-for="t in traceData" :key="t.id" :timestamp="t.date" :color="t.quantity > 0 ? '#67c23a' : '#e6a23c'">
          {{ { purchase_in: '采购入库', production_in: '完工入库', sale_out: '销售出库', outsource_out: '委外发料' }[t.type] || t.type }}
          数量: {{ t.quantity > 0 ? '+' : '' }}{{ t.quantity }}
          <span style="color: #909399; margin-left: 8px">单据: {{ t.doc_type }} {{ t.doc_no }}</span>
        </el-timeline-item>
      </el-timeline>
      </div>
    </el-card>
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick , watch} from 'vue'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
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
const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings: openColumnSettingsRaw, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const tableRef = ref(null)
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

// ===== 列设置弹窗（注入当前显隐状态）=====
function openColumnSettings() {
  const visMap = {}
  for (const c of allColumns.value) visMap[c.prop] = c.visible !== false
  openColumnSettingsRaw(visMap)
}

const warehouseList = ref([])
const batchList = ref([])
const traceData = ref([])
const traceBatchNo = ref('')
const loading = ref(false)
const query = reactive({ batch_no: '', keyword: '', warehouse_id: null })

// ========== 上下区域高度拖动 ==========
const SPLIT_KEY = 'mazu_batch_inventory_splitH'
const topHeight = ref(parseInt(localStorage.getItem(SPLIT_KEY) || '400') || 400)
function onSplitterDown(e) {
  const startY = e.clientY
  const startH = topHeight.value
  const onMove = (ev) => {
    const h = startH + (ev.clientY - startY)
    topHeight.value = Math.min(Math.max(h, 140), window.innerHeight - 320)
    localStorage.setItem(SPLIT_KEY, String(topHeight.value))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
}


// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnVisible(); initColumnDrag() })
})

onMounted(async () => {
  initColumnVisible()
  try { warehouseList.value = (await foundationApi.warehouses.list({ page_size: 200 })).items || [] } catch (e) {}
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
