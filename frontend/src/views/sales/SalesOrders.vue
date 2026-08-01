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
        <el-form-item label="客户">
          <el-input v-model="searchForm.keyword" placeholder="客户名称/订单号" clearable style="width: 160px" @keyup.enter="fetchData" />
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

    <!-- ========== 销售订单列表（高度可拖） ========== -->
    <el-card :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column' }">
      <template #header>
        <div style="display: flex; align-items: center">
          <span>销售订单</span>
          <span style="margin-left: 10px; font-size: 12px; color: #909399">点击订单行，下方查看该订单明细</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openOrderSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="orderTableRef" class="drag-table-orders" :key="columnVersion" :data="dataList" v-loading="loading" stripe border size="small" highlight-current-row show-summary :summary-method="orderSummary" :height="topHeight - 92 + 'px'" @current-change="onOrderSelect">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <el-dropdown trigger="contextmenu" :hide-on-click="false">
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click.stop="openOrderSettings" style="color: #409eff">列设置...</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'total_amount' || col.prop === 'total_amount_excl_tax'" #default="{ row }">{{ $fm(row[col.prop]) }}</template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag v-if="row.status === '已发货'" type="success" size="small">已发货</el-tag>
            <el-tag v-else-if="row.status === '部分发货'" type="warning" size="small">部分发货</el-tag>
            <el-tag v-else-if="row.status === '生产中'" type="primary" size="small">生产中</el-tag>
            <el-tag v-else-if="row.status === '已审'" type="info" size="small">已审</el-tag>
            <el-tag v-else-if="row.status === '待审核'" type="info" size="small">待审核</el-tag>
            <el-tag v-else size="small">{{ row.status }}</el-tag>
          </template>
          <template v-else-if="col.prop === 'pending_count'" #default="{ row }">
            <el-tag :type="(row.pending_count || 0) > 0 ? 'warning' : 'success'" size="small">{{ (row.pending_count || 0) > 0 ? '待处理' : '已处理' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待审核'" link type="primary" @click="handleApprove(row)">审核</el-button>
            <el-button v-if="row.status === '待审核'" link type="primary" @click="openEdit(row)">修改</el-button>
            <el-button v-if="row.status === '待审核'" link type="danger" @click="handleDelete(row)">删除</el-button>
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
        <div style="display: flex; align-items: center">
          <span>订单明细</span>
          <span style="flex: 1" />
          <el-button size="small" @click="openItemSettings">⚙ 列设置</el-button>
        </div>
      </template>
      <el-table ref="itemTableRef" class="drag-table-items" :key="itemColumnVersion" :data="orderDetailList" v-loading="itemLoading" stripe border size="small" empty-text="点击上方订单行查看明细" show-summary :summary-method="itemSummary" :height="'max(calc(100vh - ' + (topHeight + 264) + 'px), 140px)'">
        <el-table-column v-for="col in visibleItemColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <el-dropdown trigger="contextmenu" :hide-on-click="false">
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click.stop="openItemSettings" style="color: #409eff">列设置...</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-if="col.prop === 'unit_price' || col.prop === 'total_amount' || col.prop === 'tax_amount' || col.prop === 'total_amount_excl_tax'" #default="{ row }">{{ $fm(row[col.prop]) }}</template>
          <template v-else-if="col.prop === 'production_status'" #default="{ row }">
            <el-tag :type="productionStatusType(row.production_status)" size="small">{{ productionStatusLabel(row.production_status) }}</el-tag>
          </template>
          <template v-else-if="col.prop === 'received_qty'" #default="{ row }">{{ row.received_qty || 0 }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="(row.production_status === '未生产' || !row.production_status) && selectedOrder?.status === '已审'" link type="primary" size="small" @click="handleStockIn(row)">转入库</el-button>
            <el-button v-if="(row.production_status === '未生产' || !row.production_status) && selectedOrder?.status === '已审'" link type="warning" size="small" @click="handleOutsource(row)">转外发</el-button>
            <el-button v-if="row.production_status !== '已停售'" link type="primary" size="small" @click="openChangeDialog(row)">变更</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑/详情弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1120px" destroy-on-close>
      <el-form :model="orderForm" label-width="90px" :disabled="viewMode">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer_id">
              <el-input v-if="viewMode" :model-value="customerDisplayName" readonly placeholder="-" />
              <el-input v-else :model-value="customerDisplayName" placeholder="点击选择客户" readonly @click="openCustomerPicker">
                <template #append>
                  <el-button @click="openCustomerPicker">选择</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="币种">
              <el-select v-model="orderForm.currency_id" placeholder="选择币种" style="width: 100%" :disabled="viewMode">
                <el-option v-for="c in currencyList" :key="c.id" :label="c.code" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="贸易术语">
              <el-select v-model="orderForm.trade_term_id" placeholder="选择" style="width: 100%" :disabled="viewMode">
                <el-option v-for="t in tradeTermList" :key="t.id" :label="t.code" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="付款条款">
              <el-input v-model="orderForm.payment_terms" placeholder="TT/LC" :disabled="viewMode" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="订单日期">
              <el-date-picker v-model="orderForm.order_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" :disabled="viewMode" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="交期">
              <el-date-picker v-model="orderForm.delivery_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" :disabled="viewMode" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="orderForm.remark" type="textarea" :rows="2" :disabled="viewMode" />
        </el-form-item>

        <!-- 订单明细 -->
        <el-form-item label="订单明细">
          <div style="width: 100%">
            <el-button v-if="!viewMode" size="small" @click="addItem">+ 添加产品</el-button>
            <el-table :data="orderForm.items" border size="small" style="width: 100%; margin-top: 4px">
              <el-table-column label="产品" width="220">
                <template #default="{ row }">
                  <template v-if="viewMode">{{ row.product_code }} {{ row.product_name }}</template>
                  <template v-else>
                    <el-input v-if="row.product_name" :model-value="`${row.product_code || ''} ${row.product_name}`" readonly size="small" @click="openProductPicker(row)">
                      <template #append>
                        <el-button size="small" @click.stop="openProductPicker(row)">换</el-button>
                      </template>
                    </el-input>
                    <el-button v-else size="small" style="width: 100%" @click="openProductPicker(row)">+ 选择产品</el-button>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="数量" width="80">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.quantity" :min="0" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="单价" width="100">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.unit_price" :min="0" :precision="2" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="税率%" width="65">
                <template #default="{ row }">
                  <el-input type="number" v-model="row.tax_rate" :min="0" :max="17" size="small" :disabled="viewMode" controls-position="right" @input="calcItem(row)" />
                </template>
              </el-table-column>
              <el-table-column label="含税金额" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.total_amount) }}</template>
              </el-table-column>
              <el-table-column label="税额" width="80" align="right">
                <template #default="{ row }">{{ $fm(row.tax_amount) }}</template>
              </el-table-column>
              <el-table-column label="不含税" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.total_amount_excl_tax) }}</template>
              </el-table-column>
              <el-table-column label="生产状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.production_status === '未生产' || !row.production_status" type="info" size="small">未生产</el-tag>
                  <el-tag v-else-if="row.production_status === '生产中'" type="warning" size="small">生产中</el-tag>
                  <el-tag v-else-if="row.production_status === '已生产'" type="success" size="small">✓已生产</el-tag>
                  <el-tag v-else size="small">{{ row.production_status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="!viewMode" width="50">
                <template #default="{ $index }">
                  <el-button link type="danger" size="small" @click="removeItem($index)">删</el-button>
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

    <!-- 变更明细行弹窗（改数量 / 停售） -->
    <el-dialog v-model="changeVisible" title="变更明细行" width="460px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="产品">
          <el-input :model-value="changeForm.product_name" readonly />
        </el-form-item>
        <el-form-item label="新数量">
          <el-input-number v-model="changeForm.quantity" :min="0" style="width: 100%" :disabled="changeForm.stop_sale" />
        </el-form-item>
        <el-form-item label="停售">
          <el-switch v-model="changeForm.stop_sale" active-text="停售此产品（整行作废）" />
        </el-form-item>
        <div v-if="changeForm.stop_sale" style="color: #e6a23c; font-size: 12px; padding-left: 80px">
          停售后该行金额将从订单中剔除，不能再恢复。若已有待入库单/委外订单，需先退回/删除才能停售。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="changeVisible = false">取消</el-button>
        <el-button type="primary" @click="handleChange">确定</el-button>
      </template>
    </el-dialog>

    <!-- 客户选择弹窗 -->
    <el-dialog v-model="customerPickerVisible" title="选择客户" width="760px" destroy-on-close>
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-input v-model="customerSearch" placeholder="输入编码/名称搜索，回车查询" clearable @keyup.enter="searchCustomers" @clear="searchCustomers" />
        <el-button type="primary" @click="searchCustomers">搜索</el-button>
      </div>
      <el-table :data="pickerCustomerList" height="420" border size="small" highlight-current-row @row-click="pickCustomer">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name_cn" label="名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="name_en" label="英文名" min-width="160" show-overflow-tooltip />
        <el-table-column prop="country" label="国家/地区" width="110" />
        <el-table-column prop="contact_person" label="联系人" width="100" />
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="customerPage" v-model:page-size="customerPageSize" :total="customerTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="searchCustomers" />
      </div>
    </el-dialog>

    <!-- 产品选择弹窗 -->
    <el-dialog v-model="productPickerVisible" title="选择产品" width="780px" destroy-on-close>
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-input v-model="productSearch" placeholder="输入编码/名称搜索，回车查询" clearable @keyup.enter="searchProducts" @clear="searchProducts" />
        <el-button type="primary" @click="searchProducts">搜索</el-button>
      </div>
      <el-table :data="pickerProductList" height="420" border size="small" highlight-current-row @row-click="pickProduct">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name_cn" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="130" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="sale_price" label="销售价" width="100" align="right" />
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination v-model:current-page="productPage" v-model:page-size="productPageSize" :total="productTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="searchProducts" />
      </div>
    </el-dialog>
    
    <!-- 列排序弹窗 -->
    <ColumnSettingsDialog v-model:visible="orderSettingsVisible" :columns="orderSettingsList" @confirm="confirmOrderSettings" @reset="resetOrderSettings" />
    <ColumnSettingsDialog v-model:visible="itemSettingsVisible" :columns="itemSettingsList" @confirm="confirmItemSettings" @reset="resetItemSettings" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'

const { fitTable } = useColumnAutoFit()

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_sales_order_columns'
const defaultColumns = [
  { prop: 'order_date', label: '订单日期', width: 100, sortable: true },
  { prop: 'order_no', label: '订单号', minWidth: 130, sortable: true },
  { prop: 'customer_name', label: '客户', width: 150, sortable: true },
  { prop: 'item_count', label: '明细', width: 70, align: 'center', sortable: true, fmt: 'qty' },
  { prop: 'pending_count', label: '待处理', width: 90, align: 'center', sortable: true, fmt: 'tag' },
  { prop: 'total_amount_excl_tax', label: '不含税', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'total_amount', label: '含税金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'currency_code', label: '币种', width: 80, sortable: true },
  { prop: 'trade_term', label: '贸易术语', width: 100, sortable: true },
  { prop: 'status', label: '状态', width: 90, align: 'center', sortable: true, fmt: 'tag' },
]
const { columns, columnVersion, initColumnDrag, settingsVisible: orderSettingsVisible, settingsList: orderSettingsList, openColumnSettings: openOrderSettingsRaw, confirmSettings, resetSettings: resetOrderSettings } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-orders .el-table__header-wrapper thead tr')

const ITEM_STORAGE_KEY = 'mazu_sales_order_item_columns'
const defaultItemColumns = [
  { prop: 'product_code', label: '产品编码', minWidth: 110, sortable: true },
  { prop: 'product_name', label: '产品名称', minWidth: 150, sortable: true },
  { prop: 'batch_no', label: '批次号', minWidth: 150, sortable: true },
  { prop: 'quantity', label: '数量', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'tax_rate', label: '税率%', width: 70, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'total_amount', label: '金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'tax_amount', label: '税额', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'total_amount_excl_tax', label: '不含税', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'received_qty', label: '已入库', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'production_status', label: '状态', width: 100, align: 'center', sortable: true, fmt: 'tag' },
]
const { columns: itemColumns, columnVersion: itemColumnVersion, initColumnDrag: initItemColumnDrag, settingsVisible: itemSettingsVisible, settingsList: itemSettingsList, openColumnSettings: openItemSettingsRaw, confirmSettings: confirmItemSettingsFn, resetSettings: resetItemSettings } = useColumnDrag(defaultItemColumns, ITEM_STORAGE_KEY, '.drag-table-items .el-table__header-wrapper thead tr')
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)
const { visibleColumns: visibleItemColumns, allColumns: allItemColumns, toggleColumn: toggleItemColumn, initColumnVisible: initItemVisible } = useColumnCustomize(itemColumns, ITEM_STORAGE_KEY)

// ===== 列设置弹窗（注入当前显隐状态）=====
function openOrderSettings() {
  const visMap = {}
  for (const c of allColumns.value) visMap[c.prop] = c.visible !== false
  openOrderSettingsRaw(visMap)
}
function openItemSettings() {
  const visMap = {}
  for (const c of allItemColumns.value) visMap[c.prop] = c.visible !== false
  openItemSettingsRaw(visMap)
}
// 确认后重同步显隐（localStorage 已由 confirmSettings 写入 _vis，这里重建 visibleColumns）
function confirmOrderSettings() {
  confirmSettings()
  nextTick(() => { initColumnVisible(); initColumnDrag(); if (dataList.value.length) fitTable(orderTableRef.value, visibleColumns, dataList) })
}
function confirmItemSettings() {
  confirmItemSettingsFn()
  nextTick(() => { initItemVisible(); initItemColumnDrag(); if (orderDetailList.value.length) fitTable(itemTableRef.value, visibleItemColumns, orderDetailList) })
}

// ========== 销售订单查询 ==========
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
const SPLIT_KEY = 'mazu_sales_split_height'
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
  const sumCols = new Set(['total_amount', 'total_amount_excl_tax'])
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
    const res = await request.get(`/sales/orders/${orderId}`)
    orderDetailList.value = res.items || []
  } catch {} finally {
    itemLoading.value = false
    nextTick(() => {
      initItemColumnDrag()
      fitTable(itemTableRef.value, itemColumns, orderDetailList)
    })
  }
}

function productionStatusType(status) {
  const map = {
    '未生产': 'info', '已通知入库': 'primary', '已通知外发': 'warning',
    '部分入库': 'warning', '已入库': 'success', '已停售': 'danger',
  }
  return map[status] || 'info'
}

function productionStatusLabel(status) {
  const map = {
    '未生产': '未生产', '已通知入库': '已通知入库', '已通知外发': '已通知外发',
    '部分入库': '部分入库', '已入库': '已入库', '已停售': '已停售',
  }
  return map[status] || status || '未生产'
}

// ========== 明细行：转入库 / 转外发 ==========
async function handleStockIn(row) {
  await ElMessageBox.confirm(`将「${row.product_name}」转入库？将生成待入库单，收货在「库存管理 → 成品入库」进行。`, '提示', { type: 'info' })
  try {
    const res = await request.post(`/sales/orders/${selectedOrder.value.id}/items/${row.id}/stock-in`)
    ElMessage.success(res.message || '已转入库')
    loadOrderDetail(selectedOrder.value.id)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

async function handleOutsource(row) {
  await ElMessageBox.confirm(`将「${row.product_name}」转外发？将生成委外订单（草稿），请在「委外管理 → 委外订单」维护委外商和加工单价。`, '提示', { type: 'info' })
  try {
    const res = await request.post(`/sales/orders/${selectedOrder.value.id}/items/${row.id}/outsource`)
    ElMessage.success(res.message || '已转外发')
    loadOrderDetail(selectedOrder.value.id)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

// ========== 明细行：变更（改数量 / 停售） ==========
const changeVisible = ref(false)
const changeForm = reactive({ id: null, product_name: '', quantity: 1, stop_sale: false })

function openChangeDialog(row) {
  changeForm.id = row.id
  changeForm.product_name = `${row.product_code || ''} ${row.product_name || ''}`
  changeForm.quantity = row.quantity
  changeForm.stop_sale = false
  changeVisible.value = true
}

async function handleChange() {
  const payload = {}
  if (changeForm.stop_sale) {
    payload.stop_sale = true
  } else {
    payload.quantity = parseFloat(changeForm.quantity) || 0
  }
  try {
    const res = await request.put(`/sales/orders/${selectedOrder.value.id}/items/${changeForm.id}`, payload)
    ElMessage.success(res.message || '变更成功')
    changeVisible.value = false
    loadOrderDetail(selectedOrder.value.id)
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '变更失败') }
}

// ========== 弹窗 ==========
const dialogVisible = ref(false)
const viewMode = ref(false)
const editMode = ref(false)
const dialogTitle = computed(() => {
  if (viewMode.value) return '订单详情'
  if (editMode.value) return '修改订单'
  return '新建订单'
})
const submitting = ref(false)
const customerList = ref([])
const currencyList = ref([])
const tradeTermList = ref([])
const productList = ref([])

const orderForm = reactive({
  id: null, customer_id: null, customer_name: '', currency_id: null, trade_term_id: null,
  payment_terms: 'TT', order_date: '', delivery_date: '', remark: '',
  total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
  exchange_rate: 1,
  items: [],
})

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
    const res = await request.get('/sales/orders', { params })
    dataList.value = res.items || []
    total.value = res.total || 0
    // 自动选中第一行，联动加载明细
    if (dataList.value.length) {
      selectedOrder.value = dataList.value[0]
      loadOrderDetail(selectedOrder.value.id)
      nextTick(() => { orderTableRef.value?.setCurrentRow(dataList.value[0]) })
    } else {
      selectedOrder.value = null
      orderDetailList.value = []
    }
  } catch {} finally {
    loading.value = false
    nextTick(() => {
      initColumnDrag()
      fitTable(orderTableRef.value, columns, dataList)
    })
  }
}

async function loadCustomers() {
  try { const res = await request.get('/foundation/customers', { params: { page: 1, page_size: 100 } }); customerList.value = res.items || [] } catch {}
}
async function loadCurrencies() {
  try { const res = await request.get('/foundation/currencies', { params: { page: 1, page_size: 100 } }); currencyList.value = res.items || [] } catch {}
}
async function loadTradeTerms() {
  try { const res = await request.get('/foundation/trade-terms', { params: { page: 1, page_size: 100 } }); tradeTermList.value = res.items || [] } catch {}
}
async function loadProducts() {
  try { const res = await request.get('/foundation/products', { params: { page: 1, page_size: 100 } }); productList.value = res.items || [] } catch {}
}

// ========== 客户选择弹窗 ==========
const customerPickerVisible = ref(false)
const customerSearch = ref('')
const pickerCustomerList = ref([])
const customerTotal = ref(0)
const customerPage = ref(1)
const customerPageSize = ref(100)

async function searchCustomers() {
  try {
    const params = { page: customerPage.value, page_size: customerPageSize.value }
    if (customerSearch.value) params.keyword = customerSearch.value
    const res = await request.get('/foundation/customers', { params })
    pickerCustomerList.value = res.items || []
    customerTotal.value = res.total || 0
  } catch {}
}

function openCustomerPicker() {
  customerSearch.value = ''
  customerPage.value = 1
  searchCustomers()
  customerPickerVisible.value = true
}

function pickCustomer(c) {
  orderForm.customer_id = c.id
  orderForm.customer_name = c.name_cn
  customerPickerVisible.value = false
}

const customerDisplayName = computed(() => {
  if (!orderForm.customer_id) return ''
  const c = customerList.value.find(x => x.id === orderForm.customer_id)
  if (c) return `${c.code} - ${c.name_cn}`
  return orderForm.customer_name || ''
})

// ========== 产品选择弹窗 ==========
const productPickerVisible = ref(false)
const productSearch = ref('')
const pickerProductList = ref([])
const productTotal = ref(0)
const productPage = ref(1)
const productPageSize = ref(100)
const productPickerTarget = ref(null)  // 要回填的明细行；null = 修改明细行弹窗

async function searchProducts() {
  try {
    const params = { page: productPage.value, page_size: productPageSize.value }
    if (productSearch.value) params.keyword = productSearch.value
    // 按订单客户过滤：只显示关联了该客户的产品（未关联客户的产品不会出现在销售单里）
    if (selectedOrder.value?.customer_id) params.customer_id = selectedOrder.value.customer_id
    const res = await request.get('/foundation/products', { params })
    pickerProductList.value = res.items || []
    productTotal.value = res.total || 0
  } catch {}
}

function openProductPicker(target) {
  productPickerTarget.value = target
  productSearch.value = ''
  productPage.value = 1
  searchProducts()
  productPickerVisible.value = true
}

function pickProduct(p) {
  const target = productPickerTarget.value
  if (target) {
    // 回填明细行
    target.product_id = p.id
    target.product_code = p.code
    target.product_name = p.name_cn
    target.unit_price = p.sale_price || 0
    calcItem(target)
  } else {
    // 回填修改明细行弹窗
    itemEditForm.product_id = p.id
    itemEditForm.product_code = p.code
    itemEditForm.product_name = p.name_cn
  }
  productPickerVisible.value = false
}

const itemEditProductName = computed(() => {
  if (!itemEditForm.product_id) return ''
  if (itemEditForm.product_name) return `${itemEditForm.product_code || ''} - ${itemEditForm.product_name}`
  const p = productList.value.find(x => x.id === itemEditForm.product_id)
  return p ? `${p.code} - ${p.name_cn}` : ''
})

function openCreate() {
  viewMode.value = false
  editMode.value = false
  Object.assign(orderForm, {
    id: null, customer_id: null, customer_name: '', currency_id: null, trade_term_id: null,
    payment_terms: 'TT', order_date: '', delivery_date: '', remark: '',
    total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
    items: [{ product_id: null, product_code: '', product_name: '', quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 }],
  })
  dialogVisible.value = true
}

async function openDialog(row) {
  viewMode.value = true
  editMode.value = false
  try {
    const res = await request.get(`/sales/orders/${row.id}`)
    Object.assign(orderForm, { ...res, items: res.items || [] })
    calcTotals()
  } catch {}
  dialogVisible.value = true
}

function addItem() {
  orderForm.items.push({ product_id: null, product_code: '', product_name: '', quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 })
}

function removeItem(idx) {
  orderForm.items.splice(idx, 1)
  calcTotals()
}

function onProductChange(row) {
  if (!row) return
  const p = productList.value.find(x => x.id === row.product_id)
  if (p) { row.unit_price = p.sale_price || 0; calcItem(row) }
}

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

async function handleSubmit() {
  if (!orderForm.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!orderForm.items.length) { ElMessage.warning('请添加明细'); return }
  submitting.value = true
  try {
    const items = orderForm.items.map(item => ({
      ...item,
      quantity: parseFloat(item.quantity) || 0,
      unit_price: parseFloat(item.unit_price) || 0,
      total_amount: parseFloat(item.total_amount) || 0,
      tax_amount: parseFloat(item.tax_amount) || 0,
      total_amount_excl_tax: parseFloat(item.total_amount_excl_tax) || 0,
      tax_rate: parseFloat(item.tax_rate) || 13,
    }))
    await request.post('/sales/orders', {
      customer_id: orderForm.customer_id, currency_id: orderForm.currency_id,
      trade_term_id: orderForm.trade_term_id, payment_terms: orderForm.payment_terms,
      order_date: orderForm.order_date, delivery_date: orderForm.delivery_date,
      remark: orderForm.remark, items,
    })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') } finally { submitting.value = false }
}

async function handleApprove(row) {
  await ElMessageBox.confirm(`审核订单 ${row.order_no}？审核后将生成生产订单。`, '提示', { type: 'info' })
  try {
    const res = await request.post(`/sales/orders/${row.id}/approve`)
    ElMessage.success(res.message || '审核成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审核失败') }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除订单 ${row.order_no}？`, '提示', { type: 'warning' })
  try {
    await request.delete(`/sales/orders/${row.id}`)
    ElMessage.success('删除成功')
    fetchData()
  } catch {}
}

async function openEdit(row) {
  editMode.value = true
  viewMode.value = false
  try {
    const res = await request.get(`/sales/orders/${row.id}`)
    Object.assign(orderForm, { ...res, items: res.items || [] })
    calcTotals()
  } catch {}
  dialogVisible.value = true
}

async function handleUpdate() {
  if (!orderForm.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!orderForm.items.length) { ElMessage.warning('请添加明细'); return }
  submitting.value = true
  try {
    const items = orderForm.items.map(item => ({
      id: item.id,
      product_id: item.product_id,
      quantity: parseFloat(item.quantity) || 0,
      unit_price: parseFloat(item.unit_price) || 0,
      total_amount: parseFloat(item.total_amount) || 0,
      tax_amount: parseFloat(item.tax_amount) || 0,
      total_amount_excl_tax: parseFloat(item.total_amount_excl_tax) || 0,
      tax_rate: parseFloat(item.tax_rate) || 13,
    }))
    await request.put(`/sales/orders/${orderForm.id}`, {
      customer_id: orderForm.customer_id, currency_id: orderForm.currency_id,
      trade_term_id: orderForm.trade_term_id, payment_terms: orderForm.payment_terms,
      order_date: orderForm.order_date, delivery_date: orderForm.delivery_date,
      remark: orderForm.remark, exchange_rate: orderForm.exchange_rate,
      items,
    })
    ElMessage.success('修改成功')
    dialogVisible.value = false
    editMode.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '修改失败') } finally { submitting.value = false }
}

// ========== 明细行独立修改 ==========
const itemEditVisible = ref(false)
const itemSubmitting = ref(false)
const itemEditForm = reactive({
  order_id: null, id: null, product_id: null, product_code: '', product_name: '',
  quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0,
})

watch(() => itemEditForm.quantity, () => calcItemTotal(), { immediate: false })
watch(() => itemEditForm.unit_price, () => calcItemTotal(), { immediate: false })
watch(() => itemEditForm.tax_rate, () => calcItemTotal(), { immediate: false })

function calcItemTotal() {
  const qty = parseFloat(itemEditForm.quantity) || 0
  const price = parseFloat(itemEditForm.unit_price) || 0
  itemEditForm.total_amount = qty * price
}

async function handleItemUpdate() {
  if (!itemEditForm.product_id) { ElMessage.warning('请选择产品'); return }
  itemSubmitting.value = true
  try {
    const qty = parseFloat(itemEditForm.quantity) || 0
    const price = parseFloat(itemEditForm.unit_price) || 0
    const rate = parseFloat(itemEditForm.tax_rate) || 13
    const total = qty * price
    await request.put(`/sales/orders/${itemEditForm.order_id}/items/${itemEditForm.id}`, {
      product_id: itemEditForm.product_id,
      quantity: qty,
      unit_price: price,
      tax_rate: rate,
      total_amount: total,
    })
    ElMessage.success('明细行已修改')
    itemEditVisible.value = false
    if (selectedOrder.value) loadOrderDetail(selectedOrder.value.id)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '修改失败') } finally { itemSubmitting.value = false }
}

watch(() => orderForm.items.length, () => {
  orderForm.items.forEach(item => calcItem(item))
})

// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => {
    initColumnVisible()
    initColumnDrag()
    if (dataList.value.length) fitTable(orderTableRef.value, columns, dataList)
  })
})
watch(itemColumnVersion, () => {
  nextTick(() => {
    initItemVisible()
    initItemColumnDrag()
    if (orderDetailList.value.length) fitTable(itemTableRef.value, itemColumns, orderDetailList)
  })
})

onMounted(() => { initColumnVisible(); initItemVisible(); fetchData(); loadCustomers(); loadCurrencies(); loadTradeTerms(); loadProducts() })</script>

<style scoped>
/* 单元格左右内边距收紧，列更紧凑 */
:deep(.el-table .cell) {
  padding: 0 8px;
}
</style>
