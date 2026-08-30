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
        销售订单转委外：上面选明细行，供料方式在订单级统一选择；每道工序只配置加工商/加工单价/委外数量，全部配置完成后点上方列表「转委外」生成委外订单。
      </div>
    </el-card>

    <!-- ========== 上面：订单区域（转外发明细行列表） ========== -->
    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>转外发明细（订单区域）</span>
          <span style="margin-left: 10px; font-size: 12px; color: #909399">点击行，下方展示该产品工序层级关系面</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <div style="flex: 1; min-height: 0; overflow: auto">
        <el-table ref="tableRef" :key="columnVersion" v-loading="loading" :data="dataList" height="100%" border stripe size="small" highlight-current-row row-key="sales_item_id" @current-change="onSelectRow">
          <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :sort-method="col.sortMethod" :align="col.align" :show-overflow-tooltip="col.prop === 'customer_name' || col.prop === 'name' || col.prop === 'spec' || col.prop === 'batch_no'">
            <template #header>
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
            </template>
            <template v-if="col.prop === 'quantity'" #default="{ row }">{{ fmtQty(row.quantity) }}</template>
            <template v-else-if="col.prop === 'outsource_status'" #default="{ row }">
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
          <span style="margin-left: 10px; font-size: 12px; color: #909399">工序按工艺路线直接排列，可删除本次不委外的工序；配置完成后点上方列表「转委外」生成委外订单</span>
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
        <div v-loading="loadingDetail" style="flex: 1; min-height: 0; overflow: auto; display: flex; flex-direction: column; padding: 12px 4px">
          <!-- ========== 订单级操作区（供料方式 + 认领原料） ========== -->
          <div style="flex: none; margin-bottom: 10px; padding: 10px 12px; border: 1px solid #409eff; border-radius: 8px; background: #ecf5ff; display: flex; align-items: center; flex-wrap: wrap; gap: 16px">
            <div style="font-size: 13px; font-weight: 600; color: #303133">订单级供料方式</div>
            <el-radio-group v-model="supplyType" size="small">
              <el-radio-button value="己方提供">己方提供</el-radio-button>
              <el-radio-button value="包工包料">包工包料</el-radio-button>
            </el-radio-group>
            <el-button v-if="supplyType === '己方提供'" type="primary" size="small" @click="openClaim">认领原料</el-button>
            <el-tag v-else type="info" size="small">包工包料：材料由加工厂全包，无需认领</el-tag>
            <span v-if="groupedClaims.length" style="font-size: 12px; color: #606266">已认领 {{ groupedClaims.length }} 项材料（{{ fmtQty(totalClaimedQty) }}）</span>
          </div>

          <!-- 工序节点：按 seq 从左到右直接排列，节点间 ➜ 连线 -->
          <div style="flex: 1; min-height: 0; display: flex; align-items: flex-start; overflow: auto">
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
                  <div style="font-size: 12px; margin-top: 2px; color: #606266">单价 {{ fmtMoney(g.unit_price) }} ｜ 金额 {{ fmtMoney(g.amount) }}</div>
                </div>
                <div style="font-size: 11px; color: #67c23a; padding: 0 10px 8px">已生成工序只读；如需调整请到「委外订单」页操作</div>
              </div>

              <!-- 未生成工序：直接排列配置卡（只留 加工商/单价/数量/金额） -->
              <div v-else style="width: 310px; flex: none; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; background: #fff">
                <div style="padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; background: #f5f7fa; border-bottom: 1px solid #e4e7ed">
                  <span style="font-weight: 600">{{ proc.process_name }}<span style="color: #909399; font-weight: 400">（第{{ proc.seq }}道）</span></span>
                  <div style="display: flex; align-items: center; gap: 6px">
                    <el-tag type="info" size="small">未生成</el-tag>
                    <el-button link type="danger" size="small" @click="onRemoveProcess(proc)">删除</el-button>
                  </div>
                </div>
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
                  <div style="font-size: 13px; font-weight: 600; color: #303133; background: #f0f9eb; border-radius: 4px; padding: 6px 8px">
                    总金额 {{ fmtMoney(procTotal(proc)) }}
                  </div>
                </div>
              </div>
            </template>
          </div>

          <!-- 底部：损耗（生成入口=上方列表「转委外」）+ 待生成计数 + 恢复全部工序 -->
          <div style="flex: none; margin-top: 10px; display: flex; align-items: center; gap: 12px; border-top: 1px solid #e4e7ed; padding-top: 10px">
            <span style="font-size: 12px; color: #606266">
              损耗
              <el-input-number v-model="lossPct" :min="0" :max="50" :precision="0" size="small" controls-position="right" style="width: 90px" />
              %
            </span>
            <span style="font-size: 12px; color: #606266">待生成工序 {{ pendingProcessCount }} 道</span>
            <el-button v-if="hasRemoved" type="warning" size="small" plain @click="restoreProcesses">恢复全部工序</el-button>
            <span style="font-size: 12px; color: #909399">供料方式选「己方提供」时，需先「认领原料」再点转委外；全部工序配置完成后，点击上方列表的「转委外」生成委外订单</span>
          </div>
        </div>
      </template>
    </el-card>

    <!-- ========== 认领原料弹窗（订单级：BOM全部材料，只管总发料） ========== -->
    <el-dialog v-model="claimVisible" title="认领原料（订单级）" width="780px" destroy-on-close>
      <div style="font-size: 13px; margin-bottom: 10px">
        需求基准：成品数量 {{ fmtQty(detail ? detail.need_qty : 0) }} × BOM用量 ×（1+损耗 {{ lossPct }}%）；按仓库总数量认领，系统自动按先进先出从各批次扣减。
      </div>
      <div v-if="claimRows.length" style="max-height: 44vh; overflow: auto">
        <div v-for="row in claimRows" :key="row.material_id" style="border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px; margin-bottom: 8px">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px">
            <span style="font-size: 13px; font-weight: 600">{{ row.name }}<span style="color: #909399; font-weight: 400">（{{ row.code || '无编码' }}，{{ row.spec || '无规格' }}，{{ row.unit || '' }}）</span></span>
            <span style="font-size: 12px; color: #606266">BOM用量 {{ fmtQty(row.bom_qty) }} ｜ 需认领 ≥ {{ fmtQty(row.need) }} {{ row.unit || '' }}</span>
          </div>
          <div style="display: flex; gap: 10px">
            <div style="flex: 1">
              <div style="font-size: 12px; color: #606266; margin-bottom: 4px">仓库总可用</div>
              <div style="font-size: 14px; font-weight: 600; line-height: 28px">{{ row.batches.length ? fmtQty(row.maxQty) + ' ' + (row.unit || '') : '—' }}</div>
            </div>
            <div style="flex: 1">
              <div style="font-size: 12px; color: #606266; margin-bottom: 4px">认领数量（≥ 需 {{ fmtQty(row.need) }}）</div>
              <el-input-number v-model="row.quantity" :min="Math.min(row.need, row.maxQty || 0)" :max="row.maxQty || 999999" :precision="2" size="small" style="width: 100%" />
            </div>
          </div>
          <div v-if="!row.batches.length" style="font-size: 12px; color: #e6a23c; margin-top: 8px; padding: 6px 8px; background: #fdf6ec; border-radius: 4px">原料库暂无该材料（{{ row.name }}），请先完成采购→原料入库后再认领</div>
          <div v-else-if="row.maxQty < row.need" style="font-size: 12px; color: #e6a23c; margin-top: 8px; padding: 6px 8px; background: #fdf6ec; border-radius: 4px">仓库总可用 {{ fmtQty(row.maxQty) }} ＜ 需认领 {{ fmtQty(row.need) }}，不足 {{ fmtQty(row.need - row.maxQty) }} {{ row.unit || '' }}，请先补料入库</div>
        </div>
      </div>
      <div v-else style="font-size: 13px; color: #909399; text-align: center; padding: 20px 0">该产品暂无BOM材料</div>

      <!-- 已认领材料（订单级，按材料合并显示总数量，可删；删除=退回该材料全部认领量回库存） -->
      <div v-if="groupedClaims.length" style="margin-top: 12px">
        <div style="font-size: 12px; color: #606266; margin-bottom: 4px">已认领材料（{{ groupedClaims.length }}）</div>
        <div v-for="g in groupedClaims" :key="g.material_id" style="font-size: 12px; display: flex; align-items: center; justify-content: space-between; padding: 4px 6px; background: #f0f9eb; border-radius: 4px; margin-bottom: 4px">
          <span>{{ g.material_code }} {{ g.material_name }} × {{ fmtQty(g.total_qty) }} {{ g.unit || '' }}</span>
          <el-button type="danger" link size="small" @click="deleteClaimGroup(g)">删除</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmClaim">确认认领</el-button>
      </template>
    </el-dialog>
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { outsourceApi } from '../../api/business'; import { foundationApi } from '../../api/foundation'; import { inventoryApi } from '../../api/business'

// ===== 列配置 =====
const STORAGE_KEY = 'mazu_outsource_from_sales_columns'
const defaultColumns = [
  { prop: 'order_no', label: '销售订单号', minWidth: 135, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 90, sortable: true },
  { prop: 'code', label: '产品编码', minWidth: 95, sortable: true },
  { prop: 'name', label: '产品名称', minWidth: 105, sortable: true },
  { prop: 'spec', label: '规格', minWidth: 75, sortable: true },
  { prop: 'unit', label: '单位', width: 52, align: 'center', sortable: true },
  { prop: 'quantity', label: '数量', width: 82, align: 'right', sortable: true },
  { prop: 'batch_no', label: '批次号', minWidth: 130, sortable: true },
  { prop: 'outsource_status', label: '委外状态', width: 100, align: 'center', sortable: true, sortMethod: (a, b) => statusRank(a.outsource_status) - statusRank(b.outsource_status) },
]
const { columns, visibleColumns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)

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
    const res = await outsourceApi.salesToOutsource.list(params)
    dataList.value = res.items || []
    total.value = res.total || 0
    const keep = selectedItem.value && dataList.value.some(r => r.sales_item_id === selectedItem.value.sales_item_id)
    if (!keep) {
      selectedItem.value = dataList.value[0] || null
      detail.value = null
      if (selectedItem.value) loadDetail(selectedItem.value)
      nextTick(() => { tableRef.value?.setCurrentRow(dataList.value[0] || null) })
    }
  } catch (e) { ElMessage.error('加载销售订单失败') } finally { loading.value = false; nextTick(initColumnDrag) }
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
// 原始工序快照（本次加载的完整工艺路线，用于「恢复全部工序」）
const originalProcesses = ref([])
const loadingDetail = ref(false)
const lossPct = ref(10)
const submitting = ref(false)
const suppliers = ref([])
// 订单级供料方式 + 该行已认领材料（只管总发料，不挂工序/供应商）
const supplyType = ref('己方提供')
const claims = ref([])
const bomMaterials = ref([])
// 未生成工序的编辑数据: process_id -> {outsourcer_id, unit_price, quantity}
const editorMap = reactive({})

// 剩余可委外 = 销售数量 - 已转委外
const remainingQty = computed(() => {
  if (!detail.value) return 0
  return Math.max(0, (detail.value.need_qty || 0) - (detail.value.outsourced_qty || 0))
})

// 待生成工序数（已删除的不计入）
const pendingProcessCount = computed(() => {
  if (!detail.value) return 0
  return detail.value.processes.filter(p => !p.generated.length).length
})

// 是否有被删除的工序（有才显示「恢复全部工序」按钮）
const hasRemoved = computed(() => {
  if (!detail.value) return false
  const ids = new Set(detail.value.processes.map(p => p.process_id))
  return originalProcesses.value.some(p => !ids.has(p.process_id))
})

const totalClaimedQty = computed(() => claims.value.reduce((s, c) => s + (c.quantity || 0), 0))

// 已认领材料按材料合并（界面不显示批次；删除=退回该材料全部认领量）
const groupedClaims = computed(() => {
  const map = new Map()
  for (const c of claims.value) {
    if (!map.has(c.material_id)) {
      map.set(c.material_id, {
        material_id: c.material_id,
        material_code: c.material_code,
        material_name: c.material_name,
        unit: c.unit || '',
        total_qty: 0,
        claim_ids: [],
      })
    }
    const g = map.get(c.material_id)
    g.total_qty = (g.total_qty || 0) + (c.quantity || 0)
    g.claim_ids.push(c.claim_id)
  }
  return Array.from(map.values())
})

// 单材料认领需求 = 销售数量 × BOM用量 ×（1+损耗%）
function claimNeed(materialId) {
  const mat = bomMaterials.value.find(m => m.material_id === materialId)
  if (!mat || !detail.value) return 0
  return Math.round(((detail.value.need_qty || 0) * (mat.quantity || 0) * (1 + lossPct.value / 100)) * 100) / 100
}

// 单材料已认领总量（跨批次）
function claimedOf(materialId) {
  return claims.value.filter(c => c.material_id === materialId).reduce((s, c) => s + (c.quantity || 0), 0)
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
    const res = await outsourceApi.salesToOutsource.get(row.sales_item_id)
    detail.value = res
    // 快照原始工序（换行/刷新时删除状态自动重置）
    originalProcesses.value = (res.processes || []).map(p => ({ ...p, generated: [...(p.generated || [])] }))
    lossPct.value = 10
    // 订单级认领数据（BOM材料清单 + 已认领记录）
    try {
      const claimsRes = await outsourceApi.claims.list({ sales_item_id: row.sales_item_id })
      supplyType.value = claimsRes.supply_type || '己方提供'
      bomMaterials.value = claimsRes.bom_materials || []
      claims.value = claimsRes.claims || []
    } catch (e) { supplyType.value = '己方提供'; bomMaterials.value = []; claims.value = [] }
    initEditors()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载工序信息失败') } finally { loadingDetail.value = false }
}

// 未生成工序默认编辑数据（供初始化/恢复复用）
function createEditorFor(p) {
  const d = detail.value
  const remain = Math.max(0, (d.need_qty || 0) - (d.outsourced_qty || 0))
  return {
    process_id: p.process_id,
    outsourcer_id: p.default_supplier_id || null,
    unit_price: p.default_unit_price || 0,
    quantity: remain,
  }
}

// 换选中行：配置状态重置（已生成的工序保留绿框只读）
function initEditors() {
  for (const k of Object.keys(editorMap)) delete editorMap[k]
  const d = detail.value
  if (!d) return
  for (const p of d.processes) {
    if (!p.generated.length) editorMap[p.process_id] = createEditorFor(p)
  }
}

// 删除工序：本次不委外，仅前端移除（不影响已认领原料）
async function onRemoveProcess(proc) {
  try {
    await ElMessageBox.confirm(`确认删除工序「${proc.process_name}」?删除后本次转委外将不生成该工序的委外单,删除工序不影响已认领的原料`, '删除工序', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch (e) { return }
  const d = detail.value
  if (!d) return
  d.processes = d.processes.filter(p => p.process_id !== proc.process_id)
  delete editorMap[proc.process_id]
  ElMessage.success(`已删除工序「${proc.process_name}」，本次转委外不生成该工序`)
}

// 恢复全部工序：把被删除的工序按 seq 加回（保留已配置的工序不动）
function restoreProcesses() {
  const d = detail.value
  if (!d) return
  const currentIds = new Set(d.processes.map(p => p.process_id))
  const removed = originalProcesses.value.filter(p => !currentIds.has(p.process_id))
  if (!removed.length) { ElMessage.info('没有已删除的工序'); return }
  d.processes = [...d.processes, ...removed].sort((a, b) => a.seq - b.seq)
  for (const p of removed) {
    if (!p.generated.length) editorMap[p.process_id] = createEditorFor(p)
  }
  ElMessage.success(`已恢复 ${removed.length} 道工序`)
}

// ========== 加工商下拉 ==========
async function searchSuppliers() {
  try {
    const res = await foundationApi.suppliers.list({ page: 1, page_size: 100 })
    suppliers.value = res.items || []
  } catch (e) {}
}

// ========== 认领原料（订单级弹窗：BOM全部材料，按仓库总数量认领，不选批次） ==========
const claimVisible = ref(false)
const claimRows = ref([])

// 单材料行加载仓库总可用（available-batches 各批次可用量合计）
async function loadStockFor(row) {
  try {
    const res = await inventoryApi.availableBatches({ material_id: row.material_id })
    row.batches = (res.items || []).filter(b => (b.available || 0) > 0)
    row.maxQty = row.batches.reduce((s, b) => s + (b.available || 0), 0)
  } catch (e) { ElMessage.error(e.response?.data?.detail || `加载材料「${row.name}」库存失败`) }
}

async function openClaim() {
  const mats = bomMaterials.value
  if (!mats.length) { ElMessage.warning('该产品暂无BOM材料，无需认领原料'); return }
  // 重新拉取最新 BOM 材料 + 已认领记录
  try {
    const res = await outsourceApi.claims.list({ sales_item_id: selectedItem.value.sales_item_id })
    bomMaterials.value = res.bom_materials || []
    claims.value = res.claims || []
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载认领数据失败'); return }
  claimRows.value = mats.map(m => ({
    material_id: m.material_id,
    code: m.code,
    name: m.name,
    spec: m.spec || '',
    unit: m.unit || '',
    bom_qty: m.quantity || 0,
    need: claimNeed(m.material_id),
    quantity: claimNeed(m.material_id),
    batches: [],
    maxQty: 0,
  }))
  claimVisible.value = true
  await Promise.all(claimRows.value.map(row => loadStockFor(row)))
}

async function confirmClaim() {
  const errors = []
  const materials = []
  for (const row of claimRows.value) {
    if (!(row.quantity > 0)) {
      errors.push(`材料「${row.name}」请填写认领数量（≥ ${fmtQty(row.need)}）`)
      continue
    }
    if (row.maxQty < row.need) {
      errors.push(`材料「${row.name}」仓库总可用 ${fmtQty(row.maxQty)} 不足，缺 ${fmtQty(row.need - row.maxQty)}，请先补料入库`)
      continue
    }
    if (row.quantity < row.need) {
      errors.push(`材料「${row.name}」认领数量需 ≥ ${fmtQty(row.need)}`)
      continue
    }
    materials.push({ material_id: row.material_id, quantity: row.quantity })
  }
  if (errors.length) { ElMessage.warning(errors.join('\n')); return }
  if (!materials.length) { ElMessage.warning('请至少认领一种材料'); return }
  try {
    const res = await outsourceApi.claims.create({
      sales_item_id: selectedItem.value.sales_item_id,
      supply_type: '己方提供',
      loss_pct: lossPct.value,
      materials,
    })
    ElMessage.success(res.message || '认领成功')
    claimVisible.value = false
    // 刷新详情（订单级已认领）+ 列表状态
    await loadDetail(selectedItem.value)
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '认领失败') }
}

async function deleteClaimGroup(g) {
  try {
    await ElMessageBox.confirm(`确认删除「${g.material_name}」的认领记录（${fmtQty(g.total_qty)} ${g.unit || ''}）？材料将退回原料库。`, '删除认领', { type: 'warning' })
    for (const claimId of g.claim_ids) {
      await outsourceApi.claims.remove(claimId)
    }
    ElMessage.success('已删除，材料已退回原料库')
    await loadDetail(selectedItem.value)
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// ========== 转委外（唯一生成入口）：订单级校验 + 全部未生成工序校验，全部通过才生成 ==========
async function submitTransfer() {
  const d = detail.value
  if (!d) return
  const rows = []
  const errors = []
  const st = supplyType.value
  if (!st) { errors.push('请选择供料方式（己方提供/包工包料）') }
  // 己方提供：所有 BOM 材料已认领且够数（后端也会拦）
  if (st === '己方提供') {
    for (const mat of bomMaterials.value) {
      const need = claimNeed(mat.material_id)
      const claimed = claimedOf(mat.material_id)
      if (claimed < need) errors.push(`材料「${mat.name}」己方提供，认领不足（需 ${fmtQty(need)}，已领 ${fmtQty(claimed)}），请先认领原料`)
    }
  }
  for (const proc of d.processes) {
    if (proc.generated.length) continue
    const e = editorMap[proc.process_id]
    if (!e) continue
    if (!e.outsourcer_id) { errors.push(`工序「${proc.process_name}」请选择加工商`); continue }
    if (!(e.unit_price > 0)) { errors.push(`工序「${proc.process_name}」请填写加工单价（需大于0）`); continue }
    if (!(e.quantity > 0)) { errors.push(`工序「${proc.process_name}」请填写委外数量（需大于0）`); continue }
    rows.push({
      process_id: proc.process_id,
      outsourcer_id: e.outsourcer_id,
      unit_price: e.unit_price,
      quantity: e.quantity,
    })
  }
  if (errors.length) {
    ElMessageBox.alert(errors.join('\n'), '配置未完成', { confirmButtonText: '知道了', type: 'warning' })
    return
  }
  if (!rows.length) { ElMessage.warning('没有待配置的工序'); return }
  try {
    await ElMessageBox.confirm(`将为 ${rows.length} 道工序生成委外订单，是否继续？`, '转委外确认', { type: 'info' })
  } catch (e) { return }
  submitting.value = true
  try {
    const payload = {
      sales_order_id: selectedItem.value.order_id,
      sales_item_id: selectedItem.value.sales_item_id,
      supply_type: st,
      loss_pct: lossPct.value,
      rows,
    }
    const res = await outsourceApi.orders.fromSalesProcess(payload)
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
    const res = await outsourceApi.salesToOutsource.complete(row.sales_item_id)
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
    const res = await outsourceApi.salesToOutsource.uncomplete(row.sales_item_id)
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
    const res = await outsourceApi.salesToOutsource.return(row.sales_item_id)
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
