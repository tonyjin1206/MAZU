<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- ========== 搜索区 ========== -->
    <el-card style="margin-bottom: 8px; flex: none">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">新建订单</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" style="flex-wrap: nowrap">
        <el-form-item label="供应商">
          <el-input v-model="searchForm.keyword" placeholder="订单号/供应商" clearable style="width: 160px" @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 220px" />
        </el-form-item>
        <el-form-item label="金额范围">
          <el-input v-model="searchForm.amountMin" placeholder="最小" type="number" style="width: 100px" />
          <span style="margin: 0 6px">~</span>
          <el-input v-model="searchForm.amountMax" placeholder="最大" type="number" style="width: 100px" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ========== 采购订单列表（高度可拖） ========== -->
    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column' }">
      <template #header>
        <span>采购订单</span>
        <span style="margin-left: 10px; font-size: 12px; color: #909399">点击订单行，下方查看该订单明细</span>
      </template>
      <el-table ref="orderTableRef" class="drag-table-orders" :key="columnVersion" :data="dataList" v-loading="loading" stripe border size="small" highlight-current-row show-summary :summary-method="orderSummary" :height="topHeight - 92 + 'px'" @current-change="onOrderSelect">
        <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'total_amount'" #default="{ row }">{{ $fm(row.total_amount) }}</template>
          <template v-else-if="col.prop === 'received_amount'" #default="{ row }">{{ $fm(row.received_amount) }}</template>
          <template v-else-if="col.prop === 'unreceived_amount'" #default="{ row }">
            <span :style="{ color: (row.unreceived_amount || 0) > 0 ? '#e6a23c' : '#909399' }">{{ $fm(row.unreceived_amount) }}</span>
          </template>
          <template v-else-if="col.prop === 'invoiced_amount'" #default="{ row }">{{ $fm(row.invoiced_amount) }}</template>
          <template v-else-if="col.prop === 'uninvoiced_amount'" #default="{ row }">
            <span :style="{ color: (row.uninvoiced_amount || 0) > 0 ? '#e6a23c' : '#909399' }">{{ $fm(row.uninvoiced_amount) }}</span>
          </template>
          <template v-else-if="col.prop === 'paid_amount'" #default="{ row }">{{ $fm(row.paid_amount) }}</template>
          <template v-else-if="col.prop === 'unpaid_amount'" #default="{ row }">
            <span :style="{ color: (row.unpaid_amount || 0) > 0 ? '#e6a23c' : '#909399' }">{{ $fm(row.unpaid_amount) }}</span>
          </template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待审核'" link type="success" @click="handleApprove(row)">审核</el-button>
            <el-button v-if="row.status === '待审核'" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.status === '已审核'" link type="warning" @click="handleUnapprove(row)">取消审核</el-button>
            <el-button v-if="row.status === '已审核' || row.status === '部分入库'" link type="primary" @click="handleInStore(row)">入库</el-button>
            <el-button v-if="row.status === '待审核'" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button link @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 6px; flex: none" />
    </el-card>

    <!-- 拖动条：上下拉动调节订单/明细区域高度 -->
    <div
      class="split-bar"
      style="flex: none; height: 8px; margin: 0 -16px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none"
      @mousedown="onSplitterDown"
    >
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>

    <!-- ========== 订单明细（跟随选中订单，占剩余高度） ========== -->
    <el-card style="flex: 1; min-height: 140px; display: flex; flexDirection: column; overflow: hidden">
      <template #header>
        <span>订单明细</span>
        <span v-if="selectedOrder" style="margin-left: 10px; font-size: 12px; color: #606266">
          {{ selectedOrder.order_no }} · {{ selectedOrder.supplier_name }} · {{ $fm(selectedOrder.total_amount) }}
        </span>
      </template>
      <el-table ref="itemTableRef" class="drag-table-items" :key="itemColumnVersion" :data="orderDetailList" v-loading="itemLoading" stripe border size="small" empty-text="点击上方订单行查看明细" show-summary :summary-method="itemSummary" :height="'max(calc(100vh - ' + (topHeight + 264) + 'px), 140px)'">
        <el-table-column v-for="col in itemColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <span class="col-header-wrap">
              <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
              {{ col.label }}
            </span>
          </template>
          <template v-if="col.prop === 'unit_price' || col.prop === 'total_amount' || col.prop === 'tax_amount' || col.prop === 'total_amount_excl_tax'" #default="{ row }">{{ $fm(row[col.prop]) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑/详情弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
      <el-form :model="orderForm" label-width="90px" :disabled="viewMode">
        <el-form-item label="供应商" prop="supplier_id">
          <el-input v-if="viewMode" :model-value="supplierDisplayName" readonly placeholder="-" />
          <el-input v-else :model-value="supplierDisplayName" placeholder="点击选择供应商" readonly @click="openSupplierPicker">
            <template #append>
              <el-button @click="openSupplierPicker">选择</el-button>
            </template>
          </el-input>
        </el-form-item>

        <!-- 订单明细 -->
        <el-form-item label="订单明细">
          <div style="width: 100%">
            <el-button v-if="!viewMode" size="small" @click="addItem">+ 添加物料</el-button>
            <el-table :data="orderForm.items" border size="small" style="width: 100%; margin-top: 4px">
              <el-table-column label="物料" width="220">
                <template #default="{ row }">
                  <template v-if="viewMode">{{ row.material_code }} {{ row.material_name }}</template>
                  <template v-else>
                    <el-input v-if="row.material_name" :model-value="`${row.material_code || ''} ${row.material_name}`" readonly size="small" @click="openMaterialPicker(row)">
                      <template #append>
                        <el-button size="small" @click.stop="openMaterialPicker(row)">换</el-button>
                      </template>
                    </el-input>
                    <el-button v-else size="small" style="width: 100%" @click="openMaterialPicker(row)">+ 选择物料</el-button>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="数量" width="90">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.quantity" :min="0" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="单价" width="110">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.unit_price" :min="0" :precision="2" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="税率%" width="70">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.tax_rate" :min="0" :max="17" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="含税金额" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.total_amount) }}</template>
              </el-table-column>
              <el-table-column label="税额" width="90" align="right">
                <template #default="{ row }">{{ $fm(row.tax_amount) }}</template>
              </el-table-column>
              <el-table-column label="不含税" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.total_amount_excl_tax) }}</template>
              </el-table-column>
              <el-table-column v-if="!viewMode" width="50">
                <template #default="{ $index }">
                  <el-button link type="danger" size="small" @click="removeItem($index)">删</el-button>
                </template>
              </el-table-column>
              <el-table-column v-if="viewMode" label="去向" width="100" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.receive_type === '成品库'" type="success" size="small">成品库</el-tag>
                  <el-tag v-else-if="row.receive_type === '原料库'" type="primary" size="small">原料库</el-tag>
                  <el-tag v-else type="info" size="small">未转</el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="viewMode && orderForm.status === '已审核'" label="操作" width="190" fixed="right">
                <template #default="{ row }">
                  <template v-if="!row.receive_type">
                    <el-button v-if="row.product_id" :disabled="false" link type="primary" size="small" @click="openToStockIn(row)">转成品库</el-button>
                    <el-button v-else :disabled="false" link type="primary" size="small" @click="handleToMaterial(row)">转原料库</el-button>
                  </template>
                  <span v-else style="color: #909399; font-size: 12px">{{ row.receive_type === '成品库' ? '待收货' : '待入库' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>

      <!-- 底部汇总 -->
      <div style="border-top: 1px solid #e4e7ed; padding-top: 12px; margin-top: 12px; display: flex; gap: 40px">
        <div>含税总金额 <b style="color: #409eff">{{ $fm(orderForm.total_amount) }}</b></div>
        <div>总税额 <b style="color: #e6a23c">{{ $fm(orderForm.tax_amount) }}</b></div>
        <div>不含税总金额 <b style="color: #909399">{{ $fm(orderForm.total_amount_excl_tax) }}</b></div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">{{ viewMode ? '关闭' : '取消' }}</el-button>
        <el-button v-if="editMode" type="primary" :loading="submitting" @click="handleUpdate">保存修改</el-button>
        <el-button v-if="!viewMode && !editMode" type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 供应商选择弹窗 -->
    <el-dialog v-model="supplierPickerVisible" title="选择供应商" width="760px" destroy-on-close>
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-input v-model="supplierSearch" placeholder="输入编码/名称搜索，回车查询" clearable @keyup.enter="searchSuppliers" @clear="searchSuppliers" />
        <el-button type="primary" @click="searchSuppliers">搜索</el-button>
      </div>
      <el-table :data="pickerSupplierList" height="420" border size="small" highlight-current-row @row-click="pickSupplier">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="country" label="国家/地区" width="110" />
        <el-table-column prop="contact_person" label="联系人" width="100" />
        <el-table-column prop="phone" label="电话" width="120" show-overflow-tooltip />
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="supplierPage" v-model:page-size="supplierPageSize" :total="supplierTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="searchSuppliers" />
      </div>
    </el-dialog>

    <!-- 材料/产品选择弹窗 -->
    <el-dialog v-model="materialPickerVisible" :title="pickerTab === 'material' ? '选择材料' : '选择产品'" width="780px" destroy-on-close>
      <el-tabs v-model="pickerTab" style="margin-bottom: 4px">
        <el-tab-pane label="原辅材料" name="material" />
        <el-tab-pane label="产品" name="product" />
      </el-tabs>
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-input v-model="materialSearch" placeholder="输入编码/名称搜索，回车查询" clearable @keyup.enter="searchPicker" @clear="searchPicker" />
        <el-button type="primary" @click="searchPicker">搜索</el-button>
      </div>
      <el-table v-if="pickerTab === 'material'" :data="pickerMaterialList" height="380" border size="small" highlight-current-row @row-click="pickMaterial">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="130" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="purchase_price" label="采购价" width="100" align="right" />
      </el-table>
      <el-table v-else :data="pickerProductList" height="380" border size="small" highlight-current-row @row-click="pickProduct">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name_cn" label="品名（公司）" min-width="140" show-overflow-tooltip />
        <el-table-column prop="name_en" label="品名（客户）" min-width="130" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="estimated_cost" label="参考成本" width="100" align="right" />
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="materialPage" v-model:page-size="materialPageSize" :total="materialTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="searchPicker" />
      </div>
    </el-dialog>
    <!-- 转成品库入库弹窗（选择关联待入库单 / 备货新建） -->
    <el-dialog v-model="toStockInVisible" title="转成品库入库" width="600px" destroy-on-close>
      <div style="margin-bottom: 10px; font-size: 12px; color: #606266">
        这批货进哪个待入库单？选择已有的（同一产品、未完成），或作为备货新建一张：
      </div>
      <el-radio-group v-model="toStockInForm.linkType" style="margin-bottom: 10px">
        <el-radio value="link">关联已有待入库单</el-radio>
        <el-radio value="new">备货新建一张</el-radio>
      </el-radio-group>
      <el-table v-if="toStockInForm.linkType === 'link'" :data="candidateStockIns" height="240" border size="small" highlight-current-row @row-click="pickCandidate">
        <el-table-column prop="stock_in_no" label="入库单号" width="140" />
        <el-table-column prop="source_label" label="来源" min-width="120" show-overflow-tooltip />
        <el-table-column prop="quantity" label="应入" width="70" align="right" />
        <el-table-column prop="received_qty" label="已入" width="70" align="right" />
        <el-table-column prop="status" label="状态" width="80" align="center" />
      </el-table>
      <el-empty v-if="toStockInForm.linkType === 'link' && !candidateStockIns.length" description="没有可关联的待入库单（该产品没有未完成、未关联采购的单据）" :image-size="60" />
      <template #footer>
        <el-button @click="toStockInVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleToStockIn">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { purchaseApi } from '../../api/business'
import request from '../../api/request'

const router = useRouter()
const { fitTable } = useColumnAutoFit()

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_purchase_order_columns'
const defaultColumns = [
  { prop: 'order_date', label: '日期', width: 100, sortable: true },
  { prop: 'order_no', label: '订单号', minWidth: 130, sortable: true },
  { prop: 'supplier_name', label: '供应商', minWidth: 120, sortable: true },
  { prop: 'item_count', label: '明细', width: 70, align: 'center', sortable: true, fmt: 'qty' },
  { prop: 'total_amount', label: '含税金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'received_amount', label: '已入库', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'unreceived_amount', label: '未入库', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'invoiced_amount', label: '已开票', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'uninvoiced_amount', label: '未开票', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'paid_amount', label: '已付款', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'unpaid_amount', label: '未付款', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'status', label: '状态', width: 90, align: 'center', sortable: true, fmt: 'tag' },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-orders .el-table__header-wrapper thead tr')

const ITEM_STORAGE_KEY = 'mazu_purchase_order_item_columns'
const defaultItemColumns = [
  { prop: 'material_code', label: '物料编码', minWidth: 110, sortable: true },
  { prop: 'material_name', label: '物料名称', minWidth: 150, sortable: true },
  { prop: 'unit', label: '单位', width: 60, sortable: true },
  { prop: 'quantity', label: '数量', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'received_qty', label: '已入库', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'tax_rate', label: '税率%', width: 70, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'total_amount', label: '含税金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'tax_amount', label: '税额', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'total_amount_excl_tax', label: '不含税', width: 100, align: 'right', sortable: true, fmt: 'money' },
]
const { columns: itemColumns, columnVersion: itemColumnVersion, initColumnDrag: initItemColumnDrag } = useColumnDrag(defaultItemColumns, ITEM_STORAGE_KEY, '.drag-table-items .el-table__header-wrapper thead tr')

// ========== 采购订单查询 ==========
const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })

const searchForm = reactive({
  keyword: '', dateRange: null, amountMin: '', amountMax: '',
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.amountMin = ''
  searchForm.amountMax = ''
  queryParams.page = 1
  fetchData()
}

// ========== 订单明细（跟随选中订单） ==========
const orderTableRef = ref(null)
const itemTableRef = ref(null)
const itemLoading = ref(false)
const selectedOrder = ref(null)
const orderDetailList = ref([])

// ========== 上下区域高度拖动 ==========
const SPLIT_KEY = 'mazu_purchase_split_height'
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

// ========== 合计栏 ==========
function fmtMoney(v) {
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (n === null || n === undefined || isNaN(n)) return '¥0.00'
  return '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function orderSummary({ columns: cols, data }) {
  const sumCols = new Set(['total_amount', 'received_amount', 'unreceived_amount', 'invoiced_amount', 'uninvoiced_amount', 'paid_amount', 'unpaid_amount'])
  return cols.map((col, idx) => {
    if (idx === 0) return '合计'
    if (sumCols.has(col.property)) {
      const v = data.reduce((s, r) => s + (parseFloat(r[col.property]) || 0), 0)
      return fmtMoney(v)
    }
    return ''
  })
}

function itemSummary({ columns: cols, data }) {
  const sumCols = new Set(['quantity', 'total_amount', 'tax_amount', 'total_amount_excl_tax'])
  return cols.map((col, idx) => {
    if (idx === 0) return '合计'
    if (!sumCols.has(col.property)) return ''
    const v = data.reduce((s, r) => s + (parseFloat(r[col.property]) || 0), 0)
    return col.property === 'quantity' ? String(v) : fmtMoney(v)
  })
}

function onOrderSelect(row) {
  if (!row) return
  selectedOrder.value = row
  loadOrderDetail(row.id)
}

async function loadOrderDetail(orderId) {
  if (!orderId) { orderDetailList.value = []; return }
  itemLoading.value = true
  try {
    const res = await request.get(`/purchase/orders/${orderId}`)
    orderDetailList.value = res.items || []
  } catch {} finally {
    itemLoading.value = false
    nextTick(() => {
      initItemColumnDrag()
      fitTable(itemTableRef.value, itemColumns, orderDetailList)
    })
  }
}

// ========== 弹窗 ==========
const dialogVisible = ref(false)
const viewMode = ref(false)
const editMode = ref(false)
const dialogTitle = computed(() => {
  if (viewMode.value) return '订单详情'
  if (editMode.value) return '修改订单'
  return '新建采购订单'
})
const submitting = ref(false)
const supplierList = ref([])
const materialList = ref([])

const orderForm = reactive({
  id: null, supplier_id: null, supplier_name: '',
  total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
  tax_rate: 13, payment_terms: '', remark: '', items: [],
})

function newItem() {
  return { material_id: null, product_id: null, material_code: '', material_name: '', unit: '', quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 }
}

function addItem() { orderForm.items.push(newItem()) }
function removeItem(index) { orderForm.items.splice(index, 1); calcTotals() }

function calcItem(row) {
  if (!row) return
  const qty = parseFloat(row.quantity) || 0
  const price = parseFloat(row.unit_price) || 0
  const rate = parseFloat(row.tax_rate) || 0
  row.total_amount = qty * price
  row.total_amount_excl_tax = Math.round(row.total_amount / (1 + rate / 100) * 100) / 100
  row.tax_amount = Math.round((row.total_amount_excl_tax * rate / 100) * 100) / 100
  calcTotals()
}

function calcTotals() {
  orderForm.total_amount = orderForm.items.reduce((s, i) => s + (i.total_amount || 0), 0)
  orderForm.tax_amount = orderForm.items.reduce((s, i) => s + (i.tax_amount || 0), 0)
  orderForm.total_amount_excl_tax = orderForm.items.reduce((s, i) => s + (i.total_amount_excl_tax || 0), 0)
}

function statusType(status) {
  const map = {
    '待审核': 'warning', '已审核': 'success', '部分入库': 'warning',
    '待开票': 'info', '已开票': 'primary', '部分付款': 'warning', '已付款': 'success',
    '已完成': 'info', '已入库': 'success',
    pending: 'warning', approved: 'success', received: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = {
    '待审核': '待审核', '已审核': '已审核', '部分入库': '部分入库',
    '待开票': '待开票', '已开票': '已开票', '部分付款': '部分付款', '已付款': '已付款',
    '已完成': '已完成', '已入库': '已入库',
    pending: '待审核', approved: '已审核', received: '已入库',
  }
  return map[status] || status
}

// ========== 供应商选择弹窗 ==========
const supplierPickerVisible = ref(false)
const supplierSearch = ref('')
const pickerSupplierList = ref([])
const supplierTotal = ref(0)
const supplierPage = ref(1)
const supplierPageSize = ref(100)

async function searchSuppliers() {
  try {
    const params = { page: supplierPage.value, page_size: supplierPageSize.value }
    if (supplierSearch.value) params.keyword = supplierSearch.value
    const res = await request.get('/foundation/suppliers', { params })
    pickerSupplierList.value = res.items || []
    supplierTotal.value = res.total || 0
  } catch {}
}

function openSupplierPicker() {
  supplierSearch.value = ''
  supplierPage.value = 1
  searchSuppliers()
  supplierPickerVisible.value = true
}

function pickSupplier(s) {
  orderForm.supplier_id = s.id
  orderForm.supplier_name = s.name
  supplierPickerVisible.value = false
}

const supplierDisplayName = computed(() => {
  if (!orderForm.supplier_id) return ''
  const s = supplierList.value.find(x => x.id === orderForm.supplier_id)
  if (s) return `${s.code} - ${s.name}`
  return orderForm.supplier_name || ''
})

// ========== 材料/产品选择弹窗 ==========
const materialPickerVisible = ref(false)
const materialSearch = ref('')
const pickerTab = ref('material')
const pickerMaterialList = ref([])
const pickerProductList = ref([])
const materialTotal = ref(0)
const materialPage = ref(1)
const materialPageSize = ref(100)
const materialPickerTarget = ref(null)

async function searchPicker() {
  if (pickerTab.value === 'material') {
    try {
      const params = { page: materialPage.value, page_size: materialPageSize.value }
      if (materialSearch.value) params.keyword = materialSearch.value
      const res = await request.get('/foundation/materials', { params })
      pickerMaterialList.value = res.items || []
      materialTotal.value = res.total || 0
    } catch {}
  } else {
    try {
      const params = { page: materialPage.value, page_size: materialPageSize.value }
      if (materialSearch.value) params.keyword = materialSearch.value
      const res = await request.get('/foundation/products', { params })
      pickerProductList.value = res.items || []
      materialTotal.value = res.total || 0
    } catch {}
  }
}

function openMaterialPicker(row) {
  materialSearch.value = ''
  materialPage.value = 1
  searchPicker()
  materialPickerVisible.value = true
  materialPickerTarget.value = row
}

function pickMaterial(m) {
  const target = materialPickerTarget.value
  if (target) {
    target.material_id = m.id
    target.product_id = null
    target.material_code = m.code
    target.material_name = m.name
    target.unit = m.unit || ''
    target.unit_price = m.purchase_price || 0
    calcItem(target)
  }
  materialPickerVisible.value = false
}

function pickProduct(p) {
  const target = materialPickerTarget.value
  if (target) {
    target.product_id = p.id
    target.material_id = null
    target.material_code = p.code
    target.material_name = p.name_cn
    target.unit = p.unit || ''
    target.unit_price = p.estimated_cost || 0
    calcItem(target)
  }
  materialPickerVisible.value = false
}

function itemDisplayName(item) {
  if (item.product_id) return `${item.material_code || ''} ${item.material_name || ''}`
  return `${item.material_code || ''} ${item.material_name || ''}`
}

async function loadSuppliers() {
  try {
    const res = await request.get('/foundation/suppliers', { params: { page: 1, page_size: 100 } })
    supplierList.value = res.items || []
  } catch {}
}

// ========== 采购明细去向：转成品库入库 / 转原料库入库 ==========
const toStockInVisible = ref(false)
const toStockInForm = reactive({ item_id: null, product_id: null, linkType: 'link' })
const candidateStockIns = ref([])
const selectedCandidate = ref(null)

async function openToStockIn(row) {
  toStockInForm.item_id = row.id
  toStockInForm.product_id = row.product_id
  toStockInForm.linkType = 'link'
  selectedCandidate.value = null
  try {
    const res = await request.get('/stock-in', { params: { page: 1, page_size: 200 } })
    candidateStockIns.value = (res.items || []).filter(x =>
      x.product_id === row.product_id &&
      (x.status === '待入库' || x.status === '部分入库') &&
      !x.purchase_item_id
    )
  } catch { candidateStockIns.value = [] }
  toStockInVisible.value = true
}

function pickCandidate(row) { selectedCandidate.value = row }

async function handleToStockIn() {
  if (toStockInForm.linkType === 'link' && !selectedCandidate.value) { ElMessage.warning('请选择要关联的待入库单'); return }
  submitting.value = true
  try {
    const res = await request.post(`/purchase/orders/${orderForm.id}/items/${toStockInForm.item_id}/to-stock-in`, {
      stock_in_order_id: toStockInForm.linkType === 'link' ? selectedCandidate.value.id : 0,
    })
    ElMessage.success(res.message || '已转成品库入库')
    toStockInVisible.value = false
    await refreshOrderForm()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') } finally { submitting.value = false }
}

async function handleToMaterial(row) {
  await ElMessageBox.confirm('确定该明细转「原料库入库」？收货在采购入库模块进行。', '提示', { type: 'info' })
  try {
    const res = await request.post(`/purchase/orders/${orderForm.id}/items/${row.id}/to-material`)
    ElMessage.success(res.message || '已转原料库入库')
    await refreshOrderForm()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

async function refreshOrderForm() {
  try {
    const res = await request.get(`/purchase/orders/${orderForm.id}`)
    Object.assign(orderForm, { items: res.items || [], status: res.status })
  } catch {}
}

async function loadMaterials() {
  try {
    const res = await request.get('/foundation/materials', { params: { page: 1, page_size: 100 } })
    materialList.value = res.items || []
  } catch {}
}

// ========== 新建/编辑/详情 ==========
function openCreate() {
  viewMode.value = false
  editMode.value = false
  Object.assign(orderForm, {
    id: null, supplier_id: null, supplier_name: '',
    total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
    tax_rate: 13, payment_terms: '', remark: '', items: [newItem()],
  })
  dialogVisible.value = true
}

async function openEdit(row) {
  viewMode.value = false
  editMode.value = true
  try {
    const res = await request.get(`/purchase/orders/${row.id}`)
    Object.assign(orderForm, {
      id: res.id, supplier_id: res.supplier_id, supplier_name: res.supplier_name || '',
      total_amount: res.total_amount || 0, tax_amount: res.tax_amount || 0,
      total_amount_excl_tax: res.total_amount_excl_tax || 0,
      tax_rate: res.tax_rate || 13, payment_terms: res.payment_terms || '', remark: res.remark || '',
      items: res.items || [],
    })
  } catch {}
  dialogVisible.value = true
}

async function openDetail(row) {
  viewMode.value = true
  editMode.value = false
  try {
    const res = await request.get(`/purchase/orders/${row.id}`)
    Object.assign(orderForm, {
      id: res.id, supplier_id: res.supplier_id, supplier_name: res.supplier_name || '',
      status: res.status || '',
      total_amount: res.total_amount || 0, tax_amount: res.tax_amount || 0,
      total_amount_excl_tax: res.total_amount_excl_tax || 0,
      tax_rate: res.tax_rate || 13, payment_terms: res.payment_terms || '', remark: res.remark || '',
      items: res.items || [],
    })
  } catch {}
  dialogVisible.value = true
}

function buildItemsPayload() {
  return orderForm.items.map(item => ({
    material_id: item.material_id,
    product_id: item.product_id,
    quantity: parseFloat(item.quantity) || 0,
    unit_price: parseFloat(item.unit_price) || 0,
  }))
}

async function handleSubmit() {
  if (!orderForm.supplier_id) { ElMessage.warning('请选择供应商'); return }
  if (orderForm.items.length === 0) { ElMessage.warning('请添加至少一条物料明细'); return }
  submitting.value = true
  try {
    const payload = {
      supplier_id: orderForm.supplier_id,
      payment_terms: orderForm.payment_terms,
      remark: orderForm.remark,
      tax_rate: orderForm.tax_rate,
      items: buildItemsPayload(),
    }
    await purchaseApi.orders.create(payload)
    ElMessage.success('订单创建成功')
    dialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { submitting.value = false }
}

async function handleUpdate() {
  if (!orderForm.supplier_id) { ElMessage.warning('请选择供应商'); return }
  if (orderForm.items.length === 0) { ElMessage.warning('请添加至少一条物料明细'); return }
  submitting.value = true
  try {
    const payload = {
      supplier_id: orderForm.supplier_id,
      payment_terms: orderForm.payment_terms,
      remark: orderForm.remark,
      tax_rate: orderForm.tax_rate,
      items: buildItemsPayload(),
    }
    await request.put(`/purchase/orders/${orderForm.id}`, payload)
    ElMessage.success('修改成功')
    dialogVisible.value = false
    editMode.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { submitting.value = false }
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: queryParams.page, page_size: queryParams.page_size }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.dateRange) {
      params.date_from = searchForm.dateRange[0]
      params.date_to = searchForm.dateRange[1]
    }
    if (searchForm.amountMin) params.amount_min = parseFloat(searchForm.amountMin)
    if (searchForm.amountMax) params.amount_max = parseFloat(searchForm.amountMax)
    const res = await purchaseApi.orders.list(params)
    dataList.value = res.items || res.list || res.data || []
    total.value = res.total || dataList.value.length
    // 自动选中第一行，联动加载明细
    if (dataList.value.length) {
      selectedOrder.value = dataList.value[0]
      loadOrderDetail(selectedOrder.value.id)
      nextTick(() => { orderTableRef.value?.setCurrentRow(dataList.value[0]) })
    } else {
      selectedOrder.value = null
      orderDetailList.value = []
    }
  } catch (e) { ElMessage.error('加载数据失败') } finally {
    loading.value = false
    nextTick(() => {
      initColumnDrag()
      fitTable(orderTableRef.value, columns, dataList)
    })
  }
}

async function handleApprove(row) {
  await ElMessageBox.confirm('确定审核通过该订单？', '提示', { type: 'warning' })
  try { await purchaseApi.orders.approve(row.id); ElMessage.success('审核成功'); fetchData() } catch (e) {}
}

async function handleUnapprove(row) {
  await ElMessageBox.confirm('确定取消审核该订单？取消后可重新编辑。', '提示', { type: 'warning' })
  try { await request.post(`/purchase/orders/${row.id}/unapprove`); ElMessage.success('已取消审核'); fetchData() } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

function handleInStore(row) { router.push({ path: '/purchase/receipts', query: { oid: row.id } }) }

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除订单 ${row.order_no}？`, '提示', { type: 'warning' })
  try { await purchaseApi.orders.delete(row.id); ElMessage.success('删除成功'); fetchData() } catch (e) {}
}

onMounted(() => { fetchData(); loadSuppliers(); loadMaterials() })
</script>

<style scoped>
/* 单元格左右内边距收紧，列更紧凑 */
:deep(.el-table .cell) {
  padding: 0 8px;
}
</style>
