<template>
  <div>
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- ========== 页签1：按销售订单查询 ========== -->
      <el-tab-pane label="按销售订单查询" name="orders">
        <el-card style="margin-bottom: 12px">
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

        <el-card>
          <el-table :data="filteredList" v-loading="loading" stripe border size="small">
            <el-table-column prop="order_date" label="订单日期" width="100" sortable column-key="order_date" :filters="dateFilters" :filter-method="filterDate" />
            <el-table-column prop="order_no" label="订单号" min-width="140" sortable />
            <el-table-column prop="customer_name" label="客户" width="170" sortable column-key="customer_name" :filters="customerFilters" :filter-method="filterCustomer" />
            <el-table-column prop="item_count" label="明细" width="70" align="center" sortable />
              <el-table-column label="含税金额" align="right" width="100" sortable><template #default="{ row }">{{ $fm(row.total_amount) }}</template></el-table-column>
              <el-table-column label="已开票" align="right" width="100" sortable><template #default="{ row }">{{ $fm(row.invoiced_amount) }}</template></el-table-column>
              <el-table-column label="未开票" align="right" width="100" sortable>
                <template #default="{ row }">
                  <span :style="{ color: (row.total_amount - row.invoiced_amount) > 0 ? '#e6a23c' : '#909399' }">
                    {{ $fm((row.total_amount || 0) - (row.invoiced_amount || 0)) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="currency_code" label="币种" width="80" sortable />
              <el-table-column prop="trade_term" label="贸易术语" width="100" sortable />
              <el-table-column label="状态" align="center" width="90" sortable>
                <template #default="{ row }">
                  <el-tag v-if="row.status === '已发货'" type="success" size="small">已发货</el-tag>
                  <el-tag v-else-if="row.status === '部分发货'" type="warning" size="small">部分发货</el-tag>
                  <el-tag v-else-if="row.status === '生产中'" type="primary" size="small">生产中</el-tag>
                  <el-tag v-else-if="row.status === '已审'" type="info" size="small">已审</el-tag>
                  <el-tag v-else-if="row.status === '待审核'" type="info" size="small">待审核</el-tag>
                  <el-tag v-else size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="已发货" align="right" width="90" sortable><template #default="{ row }">{{ $fm(row.delivered_amount) }}</template></el-table-column>
              <el-table-column label="未发货" align="right" width="90" sortable>
                <template #default="{ row }">
                  <span :style="{ color: (row.undelivered_amount || 0) > 0 ? '#e6a23c' : '#909399' }">
                    {{ $fm(row.undelivered_amount) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="已收款" align="right" width="90" sortable><template #default="{ row }">{{ $fm(row.collected_amount) }}</template></el-table-column>
              <el-table-column label="未收款" align="right" width="90" sortable>
                <template #default="{ row }">
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
          <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size" :total="total" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchData" style="margin-top: 12px" />
        </el-card>
      </el-tab-pane>

      <!-- ========== 页签2：按销售明细查询 ========== -->
      <el-tab-pane label="按销售明细查询" name="items">
        <el-card style="margin-bottom: 12px">
          <template #header>
            <div style="display: flex; justify-content: flex-end; gap: 8px">
              <el-button type="primary" @click="fetchOrderItems">查询</el-button>
              <el-button @click="resetItemSearch">重置</el-button>
            </div>
          </template>
          <el-form :inline="true" :model="itemSearchForm" style="flex-wrap: nowrap">
            <el-form-item label="关键词">
              <el-input v-model="itemSearchForm.keyword" placeholder="订单号/客户/产品" clearable style="width: 180px" @keyup.enter="fetchOrderItems" />
            </el-form-item>
            <el-form-item label="生产状态">
              <el-select v-model="itemSearchForm.production_status" clearable placeholder="全部" style="width: 140px" @change="fetchOrderItems">
                <el-option label="未生产" value="未生产" />
                <el-option label="生产中" value="生产中" />
                <el-option label="已生产" value="已生产" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card>
          <el-table :data="filteredItemList" v-loading="itemLoading" stripe border size="small">
            <el-table-column prop="order_no" label="订单号" width="140" sortable show-overflow-tooltip />
            <el-table-column prop="order_date" label="订单日期" width="110" sortable column-key="order_date_i" :filters="itemDateFilters" :filter-method="filterItemDate" />
            <el-table-column prop="customer_name" label="客户" width="160" sortable show-overflow-tooltip column-key="customer_name_i" :filters="itemCustomerFilters" :filter-method="filterItemCustomer" />
            <el-table-column prop="product_code" label="产品编码" width="100" sortable column-key="product_code" :filters="prodCodeFilters" :filter-method="filterProdCode" />
            <el-table-column prop="product_name" label="产品名称" min-width="140" sortable show-overflow-tooltip column-key="product_name" :filters="prodNameFilters" :filter-method="filterProdName" />
            <el-table-column prop="quantity" label="数量" width="80" align="right" sortable />
            <el-table-column prop="unit_price" label="单价" width="100" align="right" sortable>
              <template #default="{ row }">{{ $fm(row.unit_price) }}</template>
            </el-table-column>
            <el-table-column prop="total_amount" label="金额" width="100" align="right" sortable>
              <template #default="{ row }">{{ $fm(row.total_amount) }}</template>
            </el-table-column>
            <el-table-column label="生产状态" width="100" align="center" sortable column-key="prod_status" :filters="prodStatusFilters" :filter-method="filterProdStatus">
              <template #default="{ row }">
                <el-tag v-if="row.production_status === '未生产'" type="info" size="small">未生产</el-tag>
                <el-tag v-else-if="row.production_status === '生产中'" type="warning" size="small">生产中</el-tag>
                <el-tag v-else-if="row.production_status === '已生产'" type="success" size="small">已生产</el-tag>
                <el-tag v-else size="small">{{ row.production_status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openProductionDialog(row)">查看生产订单</el-button>
                <el-button v-if="!row.has_active_mo" link type="primary" size="small" @click="editOrderItem(row)">修改</el-button>
                <el-button v-if="!row.has_active_mo" link type="primary" size="small" @click="reProduceItem(row)">重发生产</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="itemQueryParams.page" v-model:page-size="itemQueryParams.page_size" :total="itemTotal" :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next" @change="fetchOrderItems" style="margin-top: 12px" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建/编辑/详情弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
      <el-form :model="orderForm" label-width="90px" :disabled="viewMode">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer_id">
              <el-select v-model="orderForm.customer_id" placeholder="请选择客户" filterable style="width: 100%" :disabled="viewMode">
                <el-option v-for="c in customerList" :key="c.id" :label="`${c.code} - ${c.name_cn}`" :value="c.id" />
              </el-select>
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
              <el-select v-model="orderForm.payment_terms" placeholder="选择" style="width: 100%" :disabled="viewMode">
                <el-option label="TT 电汇" value="TT" />
                <el-option label="LC 信用证" value="LC" />
                <el-option label="DP 付款交单" value="DP" />
                <el-option label="DA 承兑交单" value="DA" />
                <el-option label="OA 赊销" value="OA" />
              </el-select>
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
              <el-table-column label="产品" width="200">
                <template #default="{ row }">
                  <el-select v-if="!viewMode" v-model="row.product_id" placeholder="选择" filterable size="small" style="width: 100%" @change="onProductChange(row)">
                    <el-option v-for="p in productList" :key="p.id" :label="`${p.code} - ${p.name_cn}`" :value="p.id" />
                  </el-select>
                  <span v-else>{{ row.product_name }}</span>
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
          <el-select v-model="itemEditForm.product_id" placeholder="选择产品" filterable style="width: 100%">
            <el-option v-for="p in productList" :key="p.id" :label="`${p.code} - ${p.name_cn}`" :value="p.id" />
          </el-select>
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

    <!-- 查看生产订单弹窗 -->
    <el-dialog v-model="productionDialogVisible" title="生产订单" width="800px" destroy-on-close>
      <el-empty v-if="productionList.length === 0" description="该销售订单暂无生产订单" />
      <el-table v-else :data="productionList" border size="small" style="width: 100%">
        <el-table-column prop="order_no" label="生产订单号" min-width="140" />
        <el-table-column prop="product_name" label="产品" min-width="140" />
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="received_qty" label="已入库" width="80" align="right" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === '已完成' || row.status === '已入库'" type="success" size="small">{{ row.status }}</el-tag>
            <el-tag v-else-if="row.status === '已关闭'" type="info" size="small">{{ row.status }}</el-tag>
            <el-tag v-else type="warning" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="计划完成日" width="110" />
        <el-table-column prop="created_at" label="创建日期" width="110" />
      </el-table>
      <template #footer>
        <el-button @click="productionDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { salesApi, productionApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

// ========== 页签 ==========
const activeTab = ref('orders')

// ========== 页签1：销售订单查询 ==========
const loading = ref(false)
const dataList = ref([])
const total = ref(0)
const queryParams = reactive({ page: 1, page_size: 100 })

const searchForm = reactive({
  keyword: '', dateRange: null, amountMin: '', amountMax: '',
})

const customerFilters = ref([])
const dateFilters = ref([])
const filterCustomerVal = ref('')
const filterDateVal = ref('')

const filteredList = computed(() => {
  let items = dataList.value
  if (filterDateVal.value) {
    items = items.filter(r => r.order_date === filterDateVal.value)
  }
  if (filterCustomerVal.value) {
    items = items.filter(r => r.customer_name === filterCustomerVal.value)
  }
  return items
})

function resetSearch() {
  searchForm.keyword = ''
  searchForm.dateRange = null
  searchForm.amountMin = ''
  searchForm.amountMax = ''
  filterCustomerVal.value = ''
  filterDateVal.value = ''
  queryParams.page = 1
  fetchData()
}

function filterDate(val, row) { filterDateVal.value = val; return true }
function filterCustomer(val, row) { filterCustomerVal.value = val; return true }

// ========== 页签2：明细行查询 ==========
const itemLoading = ref(false)
const orderItemList = ref([])
const itemTotal = ref(0)
const itemQueryParams = reactive({ page: 1, page_size: 100 })
const itemSearchForm = reactive({ keyword: '', production_status: '' })

// 明细列筛选
const itemDateFilters = ref([])
const itemCustomerFilters = ref([])
const prodCodeFilters = ref([])
const prodNameFilters = ref([])
const prodStatusFilters = ref([])
const filterItemDateVal = ref('')
const filterItemCustomerVal = ref('')
const filterProdCodeVal = ref('')
const filterProdNameVal = ref('')
const filterProdStatusVal = ref('')

const filteredItemList = computed(() => {
  let items = orderItemList.value
  if (filterItemDateVal.value) items = items.filter(r => r.order_date === filterItemDateVal.value)
  if (filterItemCustomerVal.value) items = items.filter(r => r.customer_name === filterItemCustomerVal.value)
  if (filterProdCodeVal.value) items = items.filter(r => r.product_code === filterProdCodeVal.value)
  if (filterProdNameVal.value) items = items.filter(r => r.product_name === filterProdNameVal.value)
  if (filterProdStatusVal.value) items = items.filter(r => r.production_status === filterProdStatusVal.value)
  return items
})
function filterItemDate(val, row) { filterItemDateVal.value = val; return true }
function filterItemCustomer(val, row) { filterItemCustomerVal.value = val; return true }
function filterProdCode(val, row) { filterProdCodeVal.value = val; return true }
function filterProdName(val, row) { filterProdNameVal.value = val; return true }
function filterProdStatus(val, row) { filterProdStatusVal.value = val; return true }

function resetItemSearch() {
  itemSearchForm.keyword = ''
  itemSearchForm.production_status = ''
  filterItemDateVal.value = ''; filterItemCustomerVal.value = ''
  filterProdCodeVal.value = ''; filterProdNameVal.value = ''; filterProdStatusVal.value = ''
  itemQueryParams.page = 1
  fetchOrderItems()
}

async function fetchOrderItems() {
  itemLoading.value = true
  try {
    const params = { page: itemQueryParams.page, page_size: itemQueryParams.page_size }
    if (itemSearchForm.keyword) params.keyword = itemSearchForm.keyword
    if (itemSearchForm.production_status) params.production_status = itemSearchForm.production_status
    const res = await salesApi.orders.listItems({ params })
    orderItemList.value = res.items || []
    itemTotal.value = res.total || 0
    // 更新列筛选
    itemDateFilters.value = [...new Set(orderItemList.value.map(r => r.order_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    itemCustomerFilters.value = [...new Set(orderItemList.value.map(r => r.customer_name).filter(Boolean))].map(v => ({ text: v, value: v }))
    prodCodeFilters.value = [...new Set(orderItemList.value.map(r => r.product_code).filter(Boolean))].map(v => ({ text: v, value: v }))
    prodNameFilters.value = [...new Set(orderItemList.value.map(r => r.product_name).filter(Boolean))].map(v => ({ text: v, value: v }))
    prodStatusFilters.value = [...new Set(orderItemList.value.map(r => r.production_status).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch {} finally { itemLoading.value = false }
}

function onTabChange(tab) {
  if (tab === 'items' && orderItemList.value.length === 0) {
    fetchOrderItems()
  }
}

function openOrderDialog(orderId) {
  // 切换到订单页签并加载数据
  activeTab.value = 'orders'
  const row = { id: orderId }
  openDialog(row)
}

// ========== 查看生产订单（按销售订单联查） ==========
const productionDialogVisible = ref(false)
const productionList = ref([])

async function openProductionDialog(row) {
  // 联查该明细行（row.id = sales_order_item_id）对应的生产订单
  if (!row?.id) { ElMessage.warning('缺少明细行ID'); return }
  productionDialogVisible.value = true
  productionList.value = []
  try {
    const res = await productionApi.productions.list({ sales_order_item_id: row.id, page_size: 50 })
    productionList.value = res.items || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '查询生产订单失败')
    productionDialogVisible.value = false
  }
}

async function editOrderItem(row) {
  // 实时获取最新状态
  try {
    const res = await salesApi.orders.get(row.order_id, row.order_id)
    const item = (res.items || []).find(i => i.id === row.id)
    if (!item) { ElMessage.warning('明细行不存在'); return }
    if (item.production_status !== '未生产') {
      ElMessage.warning(`该明细行当前生产状态为「${item.production_status}」，不允许修改`)
      return
    }
    // 填充到编辑表单
    itemEditForm.order_id = row.order_id
    itemEditForm.id = item.id
    itemEditForm.product_id = item.product_id
    itemEditForm.quantity = item.quantity
    itemEditForm.unit_price = item.unit_price
    itemEditForm.tax_rate = item.tax_rate
    itemEditForm.total_amount = item.total_amount
    itemEditVisible.value = true
  } catch { return }
}

async function reProduceItem(row) {
  // 实时获取最新状态
  try {
    const res = await salesApi.orders.get(row.order_id, row.order_id)
    const item = (res.items || []).find(i => i.id === row.id)
    if (!item) { ElMessage.warning('明细行不存在'); return }
    if (item.production_status !== '未生产') {
      ElMessage.warning(`该明细行当前生产状态为「${item.production_status}」，不允许重发生产`)
      return
    }
  } catch { return }
  await ElMessageBox.confirm(`确定对明细行「${row.product_name}」重发生产？`, '提示', { type: 'info' })
  try {
    const res = await salesApi.orders.reProduce(row.order_id, row.id, row.order_id)
    ElMessage.success(res.message || '重发生产成功')
    fetchOrderItems()
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
  id: null, customer_id: null, currency_id: null, trade_term_id: null,
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
    const res = await salesApi.orders.list({ params })
    dataList.value = res.items || []
    total.value = res.total || 0
    dateFilters.value = [...new Set(dataList.value.map(r => r.order_date).filter(Boolean))].sort().reverse().map(v => ({ text: v, value: v }))
    customerFilters.value = [...new Set(dataList.value.map(r => r.customer_name).filter(Boolean))].map(v => ({ text: v, value: v }))
  } catch {} finally { loading.value = false }
}

async function loadCustomers() {
  try { const res = await foundationApi.customers.list({ page: 1, page_size: 100 }); customerList.value = res.items || [] } catch {}
}
async function loadCurrencies() {
  try { const res = await foundationApi.currencies.list({ page: 1, page_size: 100 }); currencyList.value = res.items || [] } catch {}
}
async function loadTradeTerms() {
  try { const res = await foundationApi.tradeTerms.list({ page: 1, page_size: 100 }); tradeTermList.value = res.items || [] } catch {}
}
async function loadProducts() {
  try { const res = await foundationApi.products.list({ page: 1, page_size: 100 }); productList.value = res.items || [] } catch {}
}

function openCreate() {
  viewMode.value = false
  editMode.value = false
  Object.assign(orderForm, {
    id: null, customer_id: null, currency_id: null, trade_term_id: null,
    payment_terms: 'TT', order_date: '', delivery_date: '', remark: '',
    total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0,
    items: [{ product_id: null, quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 }],
  })
  dialogVisible.value = true
}

async function openDialog(row) {
  viewMode.value = true
  editMode.value = false
  try {
    const res = await salesApi.orders.get(row.id, row.id)
    Object.assign(orderForm, { ...res, items: res.items || [] })
    calcTotals()
  } catch {}
  dialogVisible.value = true
}

function addItem() {
  orderForm.items.push({ product_id: null, quantity: 1, unit_price: 0, tax_rate: 13, total_amount: 0, tax_amount: 0, total_amount_excl_tax: 0 })
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
    await salesApi.orders.create({
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
    const res = await salesApi.orders.approve(row.id, row.id)
    ElMessage.success(res.message || '审核成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审核失败') }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除订单 ${row.order_no}？`, '提示', { type: 'warning' })
  try {
    await salesApi.orders.delete(row.id, row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {}
}

async function openEdit(row) {
  editMode.value = true
  viewMode.value = false
  try {
    const res = await salesApi.orders.get(row.id, row.id)
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
    await salesApi.orders.update(orderForm.id, orderForm.id)
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
  order_id: null, id: null, product_id: null,
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
    await salesApi.orders.updateItem(itemEditForm.order_id, itemEditForm.id, itemEditForm.order_id)
    ElMessage.success('明细行已修改')
    itemEditVisible.value = false
    fetchOrderItems()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '修改失败') } finally { itemSubmitting.value = false }
}

watch(() => orderForm.items.length, () => {
  orderForm.items.forEach(item => calcItem(item))
})

onMounted(() => { fetchData(); loadCustomers(); loadCurrencies(); loadTradeTerms(); loadProducts() })
</script>
