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
        <span>销售订单</span>
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
          <template v-else-if="col.prop === 'invoiced_amount'" #default="{ row }">{{ $fm(row.invoiced_amount) }}</template>
          <template v-else-if="col.prop === 'uninvoiced_amount'" #default="{ row }">
            <span :style="{ color: (row.total_amount - row.invoiced_amount) > 0 ? '#e6a23c' : '#909399' }">
              {{ $fm((row.total_amount || 0) - (row.invoiced_amount || 0)) }}
            </span>
          </template>
          <template v-else-if="col.prop === 'status'" #default="{ row }">
            <el-tag v-if="row.status === '已发货'" type="success" size="small">已发货</el-tag>
            <el-tag v-else-if="row.status === '部分发货'" type="warning" size="small">部分发货</el-tag>
            <el-tag v-else-if="row.status === '生产中'" type="primary" size="small">生产中</el-tag>
            <el-tag v-else-if="row.status === '已审'" type="info" size="small">已审</el-tag>
            <el-tag v-else-if="row.status === '待审核'" type="info" size="small">待审核</el-tag>
            <el-tag v-else size="small">{{ row.status }}</el-tag>
          </template>
          <template v-else-if="col.prop === 'delivered_amount'" #default="{ row }">{{ $fm(row.delivered_amount) }}</template>
          <template v-else-if="col.prop === 'undelivered_amount'" #default="{ row }">
            <span :style="{ color: (row.undelivered_amount || 0) > 0 ? '#e6a23c' : '#909399' }">
              {{ $fm(row.undelivered_amount) }}
            </span>
          </template>
          <template v-else-if="col.prop === 'collected_amount'" #default="{ row }">{{ $fm(row.collected_amount) }}</template>
          <template v-else-if="col.prop === 'uncollected_amount'" #default="{ row }">
            <span :style="{ color: (row.uncollected_amount || 0) > 0 ? '#e6a23c' : '#909399' }">
              {{ $fm(row.uncollected_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === '待审核'" link type="primary" @click="handleApprove(row)">审核</el-button>
            <el-button v-if="row.status === '待审核'" link type="primary" @click="openEdit(row)">修改</el-button>
            <el-button v-if="row.status === '待审核'" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button link type="primary" @click="openDialog(row)">详情</el-button>
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
          {{ selectedOrder.order_no }} · {{ selectedOrder.customer_name }} · {{ $fm(selectedOrder.total_amount) }}
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
          <template v-else-if="col.prop === 'production_status'" #default="{ row }">
            <el-tag v-if="row.production_status === '未生产' || !row.production_status" type="info" size="small">未生产</el-tag>
            <el-tag v-else-if="row.production_status === '生产中'" type="warning" size="small">生产中</el-tag>
            <el-tag v-else-if="row.production_status === '已生产'" type="success" size="small">✓已生产</el-tag>
            <el-tag v-else size="small">{{ row.production_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.production_status === '未生产' || !row.production_status" link type="primary" size="small" @click="editOrderItem(row)">修改</el-button>
            <el-button v-if="row.production_status === '未生产' || !row.production_status" link type="primary" size="small" @click="reProduceItem(row)">重发生产</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑/详情弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
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

    <!-- 修改明细行弹窗 -->
    <el-dialog v-model="itemEditVisible" title="修改明细行" width="500px" destroy-on-close>
      <el-form :model="itemEditForm" label-width="80px">
        <el-form-item label="产品">
          <el-input :model-value="itemEditProductName" placeholder="点击选择产品" readonly @click="openProductPicker(null)">
            <template #append>
              <el-button @click="openProductPicker(null)">选择</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="数量">
              <el-input type="number" v-model="itemEditForm.quantity" :min="0" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="单价">
              <el-input type="number" v-model="itemEditForm.unit_price" :min="0" :precision="2" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="税率%">
              <el-input type="number" v-model="itemEditForm.tax_rate" :min="0" :max="17" controls-position="right" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="含税金额">
          <span style="color: #409eff; font-weight: bold">{{ $fm(itemEditForm.total_amount) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="itemSubmitting" @click="handleItemUpdate">保存</el-button>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import request from '../../api/request'

const { fitTable } = useColumnAutoFit()

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_sales_order_columns'
const defaultColumns = [
  { prop: 'order_date', label: '订单日期', width: 100, sortable: true },
  { prop: 'order_no', label: '订单号', minWidth: 140, sortable: true },
  { prop: 'customer_name', label: '客户', width: 170, sortable: true },
  { prop: 'item_count', label: '明细', width: 70, align: 'center', sortable: true, fmt: 'qty' },
  { prop: 'total_amount', label: '含税金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'invoiced_amount', label: '已开票', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'uninvoiced_amount', label: '未开票', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'currency_code', label: '币种', width: 80, sortable: true },
  { prop: 'trade_term', label: '贸易术语', width: 100, sortable: true },
  { prop: 'status', label: '状态', width: 90, align: 'center', sortable: true, fmt: 'tag' },
  { prop: 'delivered_amount', label: '已发货', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'undelivered_amount', label: '未发货', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'collected_amount', label: '已收款', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'uncollected_amount', label: '未收款', width: 90, align: 'right', sortable: true, fmt: 'money' },
]
const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, STORAGE_KEY, '.drag-table-orders .el-table__header-wrapper thead tr')

const ITEM_STORAGE_KEY = 'mazu_sales_order_item_columns'
const defaultItemColumns = [
  { prop: 'product_code', label: '产品编码', minWidth: 110, sortable: true },
  { prop: 'product_name', label: '产品名称', minWidth: 150, sortable: true },
  { prop: 'quantity', label: '数量', width: 80, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'unit_price', label: '单价', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'tax_rate', label: '税率%', width: 70, align: 'right', sortable: true, fmt: 'qty' },
  { prop: 'total_amount', label: '金额', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'tax_amount', label: '税额', width: 90, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'total_amount_excl_tax', label: '不含税', width: 100, align: 'right', sortable: true, fmt: 'money' },
  { prop: 'production_status', label: '生产状态', width: 100, align: 'center', sortable: true, fmt: 'tag' },
]
const { columns: itemColumns, columnVersion: itemColumnVersion, initColumnDrag: initItemColumnDrag } = useColumnDrag(defaultItemColumns, ITEM_STORAGE_KEY, '.drag-table-items .el-table__header-wrapper thead tr')

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
  const sumCols = new Set(['total_amount', 'invoiced_amount', 'uninvoiced_amount', 'delivered_amount', 'undelivered_amount', 'collected_amount', 'uncollected_amount'])
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

function editOrderItem(row) {
  if (row.production_status && row.production_status !== '未生产') {
    ElMessage.warning(`该明细行当前生产状态为「${row.production_status}」，不允许修改`)
    return
  }
  if (!selectedOrder.value) return
  // 填充到编辑表单
  itemEditForm.order_id = selectedOrder.value.id
  itemEditForm.id = row.id
  itemEditForm.product_id = row.product_id
  itemEditForm.product_code = row.product_code || ''
  itemEditForm.product_name = row.product_name || ''
  itemEditForm.quantity = row.quantity
  itemEditForm.unit_price = row.unit_price
  itemEditForm.tax_rate = row.tax_rate
  itemEditForm.total_amount = row.total_amount
  itemEditVisible.value = true
}

async function reProduceItem(row) {
  if (row.production_status && row.production_status !== '未生产') {
    ElMessage.warning(`该明细行当前生产状态为「${row.production_status}」，不允许重发生产`)
    return
  }
  if (!selectedOrder.value) return
  await ElMessageBox.confirm(`确定对明细行「${row.product_name}」重发生产？`, '提示', { type: 'info' })
  try {
    const res = await request.post(`/sales/orders/${selectedOrder.value.id}/items/${row.id}/re-produce`)
    ElMessage.success(res.message || '重发生产成功')
    loadOrderDetail(selectedOrder.value.id)
  } catch (e) { ElMessage.error(e.response?.data?.detail || '重发生产失败') }
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

onMounted(() => { fetchData(); loadCustomers(); loadCurrencies(); loadTradeTerms(); loadProducts() })</script>

<style scoped>
/* 单元格左右内边距收紧，列更紧凑 */
:deep(.el-table .cell) {
  padding: 0 8px;
}
</style>
