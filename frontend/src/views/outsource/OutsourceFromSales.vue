<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- ========== 搜索区 ========== -->
    <el-card style="margin-bottom: 8px; flex: none">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-input v-model="searchForm.keyword" placeholder="输入销售订单号/客户搜索，回车查询" clearable style="width: 280px" @keyup.enter="resetSearch" @clear="resetSearch" />
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </template>
      <div style="font-size: 12px; color: #606266">
        销售订单转委外：上面选明细行，下面按该产品工艺路线直接排列工序；每道工序配置加工商/加工单价/供料方式/认领原料，全部配置完成后点上方列表「转委外」生成委外订单。
      </div>
    </el-card>

    <!-- ========== 上面：订单区域（转外发明细行列表） ========== -->
    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>转外发明细（订单区域）</span>
          <span style="margin-left: 10px; font-size: 12px; color: #909399">点击行，下方展示该产品工序层级关系面</span>
        </div>
      </template>
      <div style="flex: 1; min-height: 0; overflow: auto">
        <el-table ref="tableRef" v-loading="loading" :data="dataList" height="100%" border stripe size="small" highlight-current-row row-key="sales_item_id" @current-change="onSelectRow">
          <el-table-column prop="order_no" label="销售订单号" min-width="135" sortable />
          <el-table-column prop="customer_name" label="客户" min-width="90" show-overflow-tooltip sortable />
          <el-table-column prop="code" label="产品编码" min-width="95" sortable />
          <el-table-column prop="name" label="产品名称" min-width="105" show-overflow-tooltip sortable />
          <el-table-column prop="spec" label="规格" min-width="75" show-overflow-tooltip sortable />
          <el-table-column prop="unit" label="单位" width="52" align="center" sortable />
          <el-table-column prop="quantity" label="数量" width="82" align="right" sortable>
            <template #default="{ row }">{{ fmtQty(row.quantity) }}</template>
          </el-table-column>
          <el-table-column prop="batch_no" label="批次号" min-width="130" show-overflow-tooltip sortable />
          <el-table-column label="委外状态" width="100" align="center" sortable :sort-method="(a, b) => statusRank(a.outsource_status) - statusRank(b.outsource_status)">
            <template #default="{ row }">
              <el-tag v-if="row.outsource_status === 'completed'" type="success" size="small">委外完成</el-tag>
              <el-tag v-else-if="row.outsource_status === 'transferred'" type="success" size="small">已转委外订单</el-tag>
              <el-tag v-else-if="row.outsource_status === 'partial'" type="warning" size="small">部分转委外</el-tag>
              <el-tag v-else type="info" size="small">未转委外</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" align="center" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.outsource_status === 'none' || row.outsource_status === 'partial'" type="primary" size="small" @click="onTransferClick(row)">转委外</el-button>
              <el-button v-if="row.outsource_status === 'partial' || row.outsource_status === 'transferred'" type="success" size="small" @click="handleComplete(row)">完成</el-button>
              <el-button v-if="row.outsource_status === 'completed'" type="warning" size="small" @click="handleUncomplete(row)">取消完成</el-button>
              <el-button v-if="row.outsource_status === 'none'" type="danger" size="small" @click="handleReturn(row)">退回</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div style="flex: none; margin-top: 6px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" />
      </div>
    </el-card>

    <!-- 拖动条：上下拉动调节订单/工序图区域高度 -->
    <div
      class="split-bar"
      style="flex: none; height: 8px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none"
      @mousedown="onSplitterDown"
    >
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>

    <!-- ========== 下面：明细区域（工序层级关系面，从左到右） ========== -->
    <el-card style="flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>工序层级关系面</span>
          <span style="margin-left: 10px; font-size: 12px; color: #909399">工序按工艺路线直接排列，配置完成后点上方列表「转委外」生成委外订单</span>
        </div>
      </template>

      <template v-if="!selectedItem">
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: #909399; font-size: 13px">
          请先在上面选择一条已转外发的销售明细行
        </div>
      </template>
      <template v-else-if="!detail">
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: #909399; font-size: 13px">
          正在加载工序信息…
        </div>
      </template>
      <template v-else>
        <div v-loading="loadingDetail" style="flex: 1; min-height: 0; overflow: auto; display: flex; align-items: flex-start; padding: 12px 4px">
          <!-- 工序节点：按 seq 从左到右直接排列（不用点开配置），节点间 ➜ 连线 -->
          <template v-for="(proc, idx) in detail.processes" :key="proc.process_id">
            <div style="flex: none; align-self: center; padding: 0 6px; color: #c0c4cc; font-size: 20px" v-if="idx > 0">➜</div>

            <!-- 已生成工序：绿框只读 -->
            <div v-if="proc.generated.length" style="width: 310px; flex: none; border: 1px solid #67c23a; border-radius: 8px; overflow: hidden; background: #f0f9eb">
              <div style="padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; background: #e1f3d8; border-bottom: 1px solid #67c23a">
                <span style="font-weight: 600">{{ proc.process_name }}<span style="color: #909399; font-weight: 400">（第{{ proc.seq }}道）</span></span>
                <el-tag type="success" size="small">已生成</el-tag>
              </div>
              <div v-for="g in proc.generated" :key="g.outsource_no" style="margin: 8px; padding: 8px; background: #fff; border: 1px solid #67c23a; border-radius: 6px">
                <div style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px">
                  {{ g.outsource_no }}
                  <el-tag type="success" size="small">{{ g.status }}</el-tag>
                </div>
                <div style="font-size: 12px; margin-top: 4px; color: #606266">数量 {{ fmtQty(g.quantity) }} ｜ 加工商 {{ g.outsourcer_name || '-' }}</div>
                <div style="font-size: 12px; margin-top: 2px; color: #606266">单价 {{ fmtMoney(g.unit_price) }} ｜ 供料方式 {{ g.supply_type || '己方提供' }}</div>
                <div v-if="g.materials.length" style="font-size: 12px; margin-top: 4px; color: #606266">
                  <div style="color: #909399; margin-bottom: 2px">认领材料：</div>
                  <div v-for="m in g.materials" :key="m.batch_no" style="margin-top: 2px">{{ m.material_code }} {{ m.material_name }}（批次 {{ m.batch_no }}）{{ fmtQty(m.quantity) }}<el-tag :type="(m.supply_type || '己方提供') === '包工包料' ? 'info' : 'success'" size="small" style="margin-left: 4px">{{ m.supply_type || '己方提供' }}</el-tag></div>
                </div>
              </div>
              <div style="font-size: 11px; color: #67c23a; padding: 0 10px 8px">已生成工序只读；如需调整请到「委外订单」页操作</div>
            </div>

            <!-- 未生成工序：直接排列配置卡（不点开） -->
            <div v-else style="width: 310px; flex: none; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; background: #fff">
              <div style="padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; background: #f5f7fa; border-bottom: 1px solid #e4e7ed">
                <span style="font-weight: 600">{{ proc.process_name }}<span style="color: #909399; font-weight: 400">（第{{ proc.seq }}道）</span></span>
                <el-tag type="info" size="small">未生成</el-tag>
              </div>

              <!-- 直接排列的配置项（紧凑卡片） -->
              <div style="padding: 10px">
                <div style="font-size: 12px; margin-bottom: 8px; color: #606266">
                  加工商
                  <el-select v-model="editorMap[proc.process_id].outsourcer_id" placeholder="默认=该工序默认供应商" filterable clearable size="small" style="width: 100%; margin-top: 4px">
                    <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
                  </el-select>
                </div>
                <div style="display: flex; gap: 8px; margin-bottom: 8px">
                  <div style="flex: 1; font-size: 12px; color: #606266">
                    加工单价
                    <el-input-number v-model="editorMap[proc.process_id].unit_price" :min="0" :precision="2" :controls="false" size="small" style="width: 100%; margin-top: 4px" />
                  </div>
                  <div style="flex: 1; font-size: 12px; color: #606266">
                    委外数量
                    <el-input-number v-model="editorMap[proc.process_id].quantity" :min="0" :precision="2" :controls="false" size="small" style="width: 100%; margin-top: 4px" />
                    <div style="font-size: 11px; color: #909399; margin-top: 2px">剩余可委外 {{ fmtQty(remainingQty) }}</div>
                  </div>
                </div>
                <div style="font-size: 13px; font-weight: 600; color: #303133; background: #f0f9eb; border-radius: 4px; padding: 6px 8px; margin-bottom: 8px">
                  总金额 {{ fmtMoney(procTotal(proc)) }}
                </div>
                <div style="font-size: 12px; color: #606266; margin-bottom: 8px">
                  供料方式
                  <el-radio-group v-model="editorMap[proc.process_id].supply_type" size="small" style="margin-left: 8px">
                    <el-radio-button value="己方提供">己方提供</el-radio-button>
                    <el-radio-button value="包工包料">包工包料</el-radio-button>
                  </el-radio-group>
                </div>
                <div v-if="editorMap[proc.process_id].supply_type === '己方提供'" style="margin-bottom: 8px">
                  <el-button type="primary" size="small" @click="openClaim(proc)">认领原料</el-button>
                  <div style="font-size: 11px; color: #909399; margin-top: 4px">每材料需认领 ≥ 成品 {{ fmtQty(detail.need_qty) }} × BOM用量 ×（1+损耗 {{ lossPct }}%）</div>
                </div>
                <div v-if="editorMap[proc.process_id].claims.length" style="font-size: 12px; color: #909399; margin: 6px 0 4px">已认领材料（{{ editorMap[proc.process_id].claims.length }}）</div>
                <div v-for="(c, ci) in editorMap[proc.process_id].claims" :key="ci" style="font-size: 12px; display: flex; align-items: center; justify-content: space-between; padding: 4px 6px; background: #f0f9eb; border-radius: 4px; margin-bottom: 4px">
                  <span>{{ c.name }}（批次 {{ c.batch_no }}）{{ fmtQty(c.quantity) }} / 需 {{ fmtQty(claimNeed(proc, c.material_id)) }}</span>
                  <el-button type="danger" link size="small" @click="editorMap[proc.process_id].claims.splice(ci, 1)">删除</el-button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 底部：损耗（生成入口=上方列表「转委外」） -->
        <div style="flex: none; margin-top: 10px; display: flex; align-items: center; gap: 12px; border-top: 1px solid #e4e7ed; padding-top: 10px">
          <span style="font-size: 12px; color: #606266">
            损耗
            <el-input-number v-model="lossPct" :min="0" :max="50" :precision="0" size="small" controls-position="right" style="width: 90px" />
            %
          </span>
          <span style="font-size: 12px; color: #909399">全部工序配置完成后，点击上方列表的「转委外」生成委外订单</span>
        </div>
      </template>
    </el-card>

    <!-- ========== 认领原料弹窗（逐材料行: 供料方式选择, 己方提供=批次+数量, 包工包料=不认领） ========== -->
    <el-dialog v-model="claimVisible" title="认领原料" width="720px" destroy-on-close>
      <div style="font-size: 13px; margin-bottom: 10px">
        工序：{{ claimTarget ? claimTarget.proc.process_name : '' }} ｜ 需求基准：成品数量 {{ fmtQty(detail ? detail.need_qty : 0) }} × BOM用量 ×（1+损耗 {{ lossPct }}%）
      </div>
      <div v-if="claimRows.length" style="max-height: 46vh; overflow: auto">
        <div v-for="(row, ri) in claimRows" :key="row.material_id" style="border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px; margin-bottom: 8px">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px">
            <span style="font-size: 13px; font-weight: 600">{{ row.name }}<span style="color: #909399; font-weight: 400">（{{ row.spec || '无规格' }}，{{ row.unit || '' }}）</span></span>
            <span style="font-size: 12px; color: #606266">BOM用量 {{ fmtQty(row.bom_qty) }} ｜ 需 {{ fmtQty(claimNeed(claimTarget.proc, row.material_id)) }} {{ row.unit || '' }}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #606266">
            <span style="flex: none">供料方式</span>
            <el-radio-group v-model="row.supply_type" size="small" @change="onRowSupplyChange(row)">
              <el-radio-button value="己方提供">己方提供</el-radio-button>
              <el-radio-button value="包工包料">包工包料</el-radio-button>
            </el-radio-group>
          </div>
          <div v-if="row.supply_type === '包工包料'" style="font-size: 12px; color: #909399; margin-top: 8px; padding: 6px 8px; background: #f4f4f5; border-radius: 4px">由加工厂提供（本材料不认领、不出库）</div>
          <div v-else style="display: flex; gap: 10px; margin-top: 8px">
            <div style="flex: 1">
              <div style="font-size: 12px; color: #606266; margin-bottom: 4px">批次</div>
              <el-select v-model="row.batch_no" placeholder="选择原料批次" filterable size="small" style="width: 100%" @change="onRowBatchChange(row)">
                <el-option v-for="b in row.batches" :key="b.batch_no" :label="`${b.batch_no}（可用 ${fmtQty(b.available)}，${b.warehouse_name || ''}）`" :value="b.batch_no" />
              </el-select>
            </div>
            <div style="flex: 1">
              <div style="font-size: 12px; color: #606266; margin-bottom: 4px">认领数量（≥ 需 {{ fmtQty(claimNeed(claimTarget.proc, row.material_id)) }}）</div>
              <el-input-number v-model="row.quantity" :min="claimNeed(claimTarget.proc, row.material_id)" :max="row.maxQty || 999999" :precision="2" size="small" style="width: 100%" />
            </div>
          </div>
        </div>
      </div>
      <div v-else style="font-size: 13px; color: #909399; text-align: center; padding: 20px 0">该产品暂无BOM材料</div>
      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmClaim">确认认领</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'

// ========== 上下区域高度拖动 ==========
const SPLIT_KEY = 'mazu_outsource_from_sales_splitH'
const topHeight = ref(parseInt(localStorage.getItem(SPLIT_KEY) || '340') || 340)
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

// ========== 上面：转外发明细行列表（订单区域） ==========
const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const tableRef = ref(null)
const queryParams = reactive({ page: 1, page_size: 100 })
const searchForm = reactive({ keyword: '' })

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    const res = await request.get('/outsource/sales-to-outsource', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
    // 首次加载默认选中第一行；生成成功后刷新列表保留当前行
    const keep = selectedItem.value && dataList.value.some(r => r.sales_item_id === selectedItem.value.sales_item_id)
    if (!keep) {
      selectedItem.value = dataList.value[0] || null
      detail.value = null
      if (selectedItem.value) loadDetail(selectedItem.value)
      nextTick(() => { tableRef.value?.setCurrentRow(dataList.value[0] || null) })
    }
  } catch { ElMessage.error('加载销售订单失败') } finally { loading.value = false }
}

function resetSearch() {
  searchForm.keyword = ''
  queryParams.page = 1
  fetchData()
}

function fmtMoney(v) {
  return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function fmtQty(v) {
  return Number(v || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function statusRank(s) {
  return s === 'completed' ? 3 : s === 'transferred' ? 2 : s === 'partial' ? 1 : 0
}

// ========== 下面：工序层级关系面（明细区域） ==========
const selectedItem = ref(null)
const detail = ref(null)
const loadingDetail = ref(false)
const lossPct = ref(10)
const submitting = ref(false)
const suppliers = ref([])
// 未生成工序的编辑数据: process_id -> {outsourcer_id, unit_price, quantity, supply_type, claims: []}
const editorMap = reactive({})

// 剩余可委外 = 销售数量 - 已转委外
const remainingQty = computed(() => {
  if (!detail.value) return 0
  return Math.max(0, (detail.value.need_qty || 0) - (detail.value.outsourced_qty || 0))
})

// 单材料认领需求 = 成品数量 × BOM用量 ×（1+损耗%）
function claimNeed(proc, materialId) {
  const mat = (proc.bom_materials || []).find(m => m.material_id === materialId)
  if (!mat || !detail.value) return 0
  return Math.round(((detail.value.need_qty || 0) * (mat.quantity || 0) * (1 + lossPct.value / 100)) * 100) / 100
}

// 工序总金额 = 加工单价 × 委外数量
function procTotal(proc) {
  const e = editorMap[proc.process_id]
  if (!e) return 0
  return (e.unit_price || 0) * (e.quantity || 0)
}

function selectRow(row) {
  if (!row) return
  if (selectedItem.value && selectedItem.value.sales_item_id === row.sales_item_id && detail.value) {
    tableRef.value?.setCurrentRow(row)
    return
  }
  selectedItem.value = row
  tableRef.value?.setCurrentRow(row)
  loadDetail(row)
}

// 上方列表「转委外」= 唯一生成入口：选中该行 → 加载详情 → 校验全部未生成工序 → 生成
async function onTransferClick(row) {
  if (!row) return
  if (selectedItem.value && selectedItem.value.sales_item_id === row.sales_item_id && detail.value) {
    await submitTransfer()
    return
  }
  selectedItem.value = row
  tableRef.value?.setCurrentRow(row)
  await loadDetail(row)
  await submitTransfer()
}

function onSelectRow(currentRow) {
  if (currentRow) selectRow(currentRow)
}

async function loadDetail(row) {
  loadingDetail.value = true
  try {
    const res = await request.get(`/outsource/sales-to-outsource/${row.sales_item_id}`)
    detail.value = res
    lossPct.value = 10
    initEditors()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载工序信息失败') } finally { loadingDetail.value = false }
}

// 换选中行：配置状态重置（已生成的工序保留绿框只读）
function initEditors() {
  for (const k of Object.keys(editorMap)) delete editorMap[k]
  const d = detail.value
  if (!d) return
  const remain = Math.max(0, (d.need_qty || 0) - (d.outsourced_qty || 0))
  for (const p of d.processes) {
    if (!p.generated.length) {
      editorMap[p.process_id] = {
        process_id: p.process_id,
        outsourcer_id: p.default_supplier_id || null,
        unit_price: p.default_unit_price || 0,
        quantity: remain,
        supply_type: '己方提供',
        claims: [],
        materialSupply: {},
      }
    }
  }
}

// ========== 加工商下拉 ==========
async function searchSuppliers() {
  try {
    const res = await request.get('/foundation/suppliers', { params: { page: 1, page_size: 100 } })
    suppliers.value = res.items || []
  } catch {}
}

// ========== 认领原料（逐材料行: 供料方式选择, 己方提供=批次+数量, 包工包料=不认领） ==========
const claimVisible = ref(false)
const claimTarget = ref(null) // {proc}
const claimRows = ref([]) // 每材料一行: {material_id, code, name, spec, unit, bom_qty, supply_type, batch_no, quantity, batches, maxQty}

// 单材料行加载可用批次
async function loadBatchesFor(row) {
  try {
    const res = await request.get('/inventory/available-batches', { params: { material_id: row.material_id } })
    row.batches = (res.items || []).filter(b => (b.available || 0) > 0)
    if (!row.batch_no && row.batches.length) row.batch_no = row.batches[0].batch_no
    const b = row.batches.find(x => x.batch_no === row.batch_no)
    row.maxQty = b ? (b.available || 0) : (row.batches.length ? row.batches[0].available : 0)
    if (!row.batches.length) ElMessage.warning(`材料「${row.name}」原料库暂无可用库存，请先完成采购→原料入库`)
  } catch (e) { ElMessage.error(e.response?.data?.detail || `加载材料「${row.name}」批次失败`) }
}

async function openClaim(proc) {
  const mats = proc.bom_materials || []
  if (!mats.length) { ElMessage.warning('该产品暂无BOM材料，无需认领原料'); return }
  const e = editorMap[proc.process_id]
  if (!e) return
  const matSupply = e.materialSupply || {}
  const defaultSupply = e.supply_type || '己方提供'
  claimTarget.value = { proc }
  claimRows.value = mats.map(m => {
    const olds = e.claims.filter(c => c.material_id === m.material_id)
    const claimedQty = olds.reduce((s, c) => s + (c.quantity || 0), 0)
    return {
      material_id: m.material_id,
      code: m.code,
      name: m.name,
      spec: m.spec || '',
      unit: m.unit || '',
      bom_qty: m.quantity || 0,
      supply_type: matSupply[m.material_id] || defaultSupply,
      batch_no: olds.length ? olds[0].batch_no : '',
      quantity: claimedQty || claimNeed(proc, m.material_id),
      batches: [],
      maxQty: 0,
    }
  })
  claimVisible.value = true
  // 己方提供的材料行加载可用批次
  await Promise.all(claimRows.value.map(row => row.supply_type === '包工包料' ? Promise.resolve() : loadBatchesFor(row)))
}

// 切换材料行供料方式: 包工包料清空批次/数量(不参与认领)
function onRowSupplyChange(row) {
  if (row.supply_type === '包工包料') {
    row.batch_no = ''
    row.quantity = 0
    return
  }
  row.batch_no = row.batches.length ? row.batches[0].batch_no : ''
  row.quantity = claimNeed(claimTarget.value ? claimTarget.value.proc : null, row.material_id)
}

// 切换批次: 数量上限跟随批次可用量
function onRowBatchChange(row) {
  const b = row.batches.find(x => x.batch_no === row.batch_no)
  row.maxQty = b ? (b.available || 0) : 0
  if (row.maxQty > 0 && row.quantity > row.maxQty) row.quantity = row.maxQty
}

function confirmClaim() {
  const t = claimTarget.value
  if (!t) return
  const e = editorMap[t.proc.process_id]
  if (!e) return
  const keep = []
  const supplyMap = {}
  const errors = []
  for (const row of claimRows.value) {
    supplyMap[row.material_id] = row.supply_type
    if (row.supply_type === '包工包料') continue // 不提交、不参与认领
    if (!row.batch_no || !(row.quantity > 0)) {
      errors.push(`材料「${row.name}」已选己方提供，请选择批次并填写认领数量`)
      continue
    }
    keep.push({
      material_id: row.material_id,
      code: row.code,
      name: row.name,
      spec: row.spec,
      unit: row.unit,
      bom_qty: row.bom_qty,
      batch_no: row.batch_no,
      quantity: row.quantity,
      supply_type: '己方提供',
    })
  }
  if (errors.length) { ElMessage.warning(errors.join('\n')); return }
  e.claims = keep
  e.materialSupply = { ...(e.materialSupply || {}), ...supplyMap }
  claimVisible.value = false
}

// ========== 转委外（唯一生成入口）：校验全部未生成工序，全部通过才生成 ==========
async function submitTransfer() {
  const d = detail.value
  if (!d) return
  const rows = []
  const errors = []
  for (const proc of d.processes) {
    if (proc.generated.length) continue
    const e = editorMap[proc.process_id]
    if (!e) continue
    if (!e.outsourcer_id) { errors.push(`工序「${proc.process_name}」请选择加工商`); continue }
    if (!(e.unit_price > 0)) { errors.push(`工序「${proc.process_name}」请填写加工单价（需大于0）`); continue }
    const supplyType = e.supply_type
    if (!supplyType) { errors.push(`工序「${proc.process_name}」请选择供料方式`); continue }
    // 材料级供料方式校验: 凡未标「包工包料」的材料须认领够数; 全部包工包料则无己方提供材料, 不强制认领
    const matSupply = e.materialSupply || {}
    for (const mat of proc.bom_materials || []) {
      const st = matSupply[mat.material_id] || supplyType
      if (st === '包工包料') continue
      const need = claimNeed(proc, mat.material_id)
      const claimed = e.claims.filter(c => c.material_id === mat.material_id).reduce((s, c) => s + (c.quantity || 0), 0)
      if (claimed < need) errors.push(`工序「${proc.process_name}」材料「${mat.name}」己方提供，认领不足（需 ${fmtQty(need)}，已领 ${fmtQty(claimed)}）`)
    }
    rows.push({
      process_id: proc.process_id,
      outsourcer_id: e.outsourcer_id,
      unit_price: e.unit_price,
      quantity: e.quantity,
      supply_type: supplyType,
      materials: supplyType === '包工包料' ? [] : e.claims.map(c => ({
        material_id: c.material_id, batch_no: c.batch_no, quantity: c.quantity, supply_type: '己方提供',
      })),
    })
  }
  if (errors.length) {
    ElMessageBox.alert(errors.join('\n'), '配置未完成', { confirmButtonText: '知道了', type: 'warning' })
    return
  }
  if (!rows.length) { ElMessage.warning('没有待配置的工序'); return }
  try {
    await ElMessageBox.confirm(`将为 ${rows.length} 道工序生成委外订单，是否继续？`, '转委外确认', { type: 'info' })
  } catch { return }
  submitting.value = true
  try {
    const payload = {
      sales_order_id: selectedItem.value.order_id,
      sales_item_id: selectedItem.value.sales_item_id,
      loss_pct: lossPct.value,
      rows,
    }
    const res = await request.post('/outsource/orders/from-sales-process', payload)
    ElMessage.success(res.message || '委外订单已生成')
    // 成功后刷新详情（已生成工序变绿框只读）+ 刷新上面列表（委外状态更新）
    await loadDetail(selectedItem.value)
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '生成委外订单失败') } finally { submitting.value = false }
}

// ========== 完成 / 取消完成 / 退回 ==========
async function handleComplete(row) {
  try {
    await ElMessageBox.confirm(`确认完成委外？系统按人工判定：数量是否足够由你决定。完成后不能再追加委外，可随时「取消完成」。`, '完成确认', { type: 'info' })
    const res = await request.post(`/outsource/sales-to-outsource/${row.sales_item_id}/complete`)
    ElMessage.success(res.message || '已标记委外完成')
    if (selectedItem.value && selectedItem.value.sales_item_id === row.sales_item_id) loadDetail(row)
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleUncomplete(row) {
  try {
    await ElMessageBox.confirm(`确定取消委外完成？取消后可以继续追加委外。`, '取消完成确认', { type: 'warning' })
    const res = await request.post(`/outsource/sales-to-outsource/${row.sales_item_id}/uncomplete`)
    ElMessage.success(res.message || '已取消委外完成')
    if (selectedItem.value && selectedItem.value.sales_item_id === row.sales_item_id) loadDetail(row)
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleReturn(row) {
  try {
    await ElMessageBox.confirm(`确定退回（撤销转外发）？退回后销售订单明细可重新变更/转委外。`, '退回确认', { type: 'warning' })
    const res = await request.post(`/outsource/sales-to-outsource/${row.sales_item_id}/return`)
    ElMessage.success(res.message || '已退回')
    if (selectedItem.value && selectedItem.value.sales_item_id === row.sales_item_id) {
      selectedItem.value = null
      detail.value = null
    }
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '退回失败')
  }
}

onMounted(() => {
  fetchData()
  searchSuppliers()
})
</script>
