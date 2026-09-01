<template>
  <div>
    <!-- 消息中心（工作台最上方，默认未读页签） -->
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600; font-size: 14px; color: #409eff">消息中心</span>
          <div style="display: flex; align-items: center; gap: 12px">
            <el-button v-if="msgTab === 'unread' && unreadTotal > 0" link type="primary" @click="markAllReadMsg">全部已读</el-button>
            <el-radio-group v-model="msgTab" size="small" @change="fetchMsgs">
              <el-radio-button value="unread">未读{{ unreadTotal > 0 ? ` (${unreadTotal})` : '' }}</el-radio-button>
              <el-radio-button value="read">已读</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      <div v-if="msgs.length === 0" style="text-align: center; color: #909399; padding: 14px 0">
        暂无{{ msgTab === 'unread' ? '未读' : '已读' }}消息
      </div>
      <div v-else>
        <div v-for="n in msgs" :key="n.id" @click="openMsg(n)"
             style="display: flex; align-items: center; gap: 10px; padding: 8px 6px; border-bottom: 1px solid #f0f0f0; cursor: pointer; border-radius: 4px"
             :style="{ background: n.read_status === 0 ? '#f5f7fa' : 'transparent' }">
          <el-tag v-if="n.read_status === 0" size="small" type="danger">新</el-tag>
          <div style="flex: 1; min-width: 0">
            <div style="font-size: 13px; font-weight: 600; color: #303133">{{ n.title }}</div>
            <div style="font-size: 12px; color: #606266; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{{ n.content }}</div>
          </div>
          <span style="font-size: 12px; color: #909399; white-space: nowrap">{{ n.created_at }}</span>
        </div>
      </div>
    </el-card>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card>
          <template #header><div style="display: flex; justify-content: flex-end; gap: 8px"><span style="flex: 1; font-weight: 600; font-size: 14px; color: #409eff">现金收入</span></div></template>
          <div v-if="cashIn.length" style="display: flex; align-items: flex-end; gap: 6px; height: 160px; padding: 0 8px">
            <div v-for="(item, i) in cashIn" :key="i" style="flex: 1; display: flex; flex-direction: column; align-items: center; cursor: pointer" @click="drillCollectionMonth(item.month)">
              <span style="font-size: 10px; color: #606266; margin-bottom: 2px; font-weight: 600">{{ $fm(item.amount) }}</span>
              <div :style="{ height: barHeight(item.amount, maxCashIn) + 'px', width: '100%', background: 'linear-gradient(180deg, #409eff, #79bbff)', borderRadius: '3px 3px 0 0', minHeight: '4px' }" />
              <span style="font-size: 10px; color: #909399; margin-top: 4px; white-space: nowrap">{{ item.month.slice(5) }}月</span>
            </div>
          </div>
          <div v-else style="text-align: center; color: #909399; padding: 20px">暂无数据</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header><div style="display: flex; justify-content: flex-end; gap: 8px"><span style="flex: 1; font-weight: 600; font-size: 14px; color: #e6a23c">现金支付</span></div></template>
          <div v-if="cashOut.length" style="display: flex; align-items: flex-end; gap: 6px; height: 160px; padding: 0 8px">
            <div v-for="(item, i) in cashOut" :key="i" style="flex: 1; display: flex; flex-direction: column; align-items: center; cursor: pointer" @click="drillPaymentMonth(item.month)">
              <span style="font-size: 10px; color: #606266; margin-bottom: 2px; font-weight: 600">{{ $fm(item.amount) }}</span>
              <div :style="{ height: barHeight(item.amount, maxCashOut) + 'px', width: '100%', background: 'linear-gradient(180deg, #e6a23c, #f0c78a)', borderRadius: '3px 3px 0 0', minHeight: '4px' }" />
              <span style="font-size: 10px; color: #909399; margin-top: 4px; white-space: nowrap">{{ item.month.slice(5) }}月</span>
            </div>
          </div>
          <div v-else style="text-align: center; color: #909399; padding: 20px">暂无数据</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header><div style="display: flex; justify-content: flex-end; gap: 8px"><span style="flex: 1; font-weight: 600; font-size: 14px; color: #67c23a">现金净收支</span></div></template>
          <div v-if="netCash.length" style="display: flex; align-items: flex-end; gap: 6px; height: 160px; padding: 0 8px">
            <div v-for="(item, i) in netCash" :key="i" style="flex: 1; display: flex; flex-direction: column; align-items: center; cursor: pointer" @click="drillNetCash(item.month)">
              <span style="font-size: 10px; margin-bottom: 2px; font-weight: 600; color: item.amount >= 0 ? '#67c23a' : '#f56c6c'">{{ $fm(item.amount) }}</span>
              <div :style="{ height: netBarHeight(item.amount, maxNetCash) + 'px', width: '100%', background: item.amount >= 0 ? 'linear-gradient(180deg, #67c23a, #95d475)' : 'linear-gradient(180deg, #f56c6c, #f89898)', borderRadius: '3px 3px 0 0', minHeight: '4px' }" />
              <span style="font-size: 10px; color: #909399; margin-top: 4px; white-space: nowrap">{{ item.month.slice(5) }}月</span>
            </div>
          </div>
          <div v-else style="text-align: center; color: #909399; padding: 20px">暂无数据</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 12px">
      <el-col :span="12">
        <el-card>
          <template #header><div style="display: flex; justify-content: flex-end; gap: 8px"><span style="flex: 1; font-weight: 600; font-size: 14px; color: #e6a23c">应收账款账龄</span></div></template>
          <el-table :data="arAging" stripe border size="small" style="width: 100%" max-height="240" @row-click="drillAR">
            <el-table-column prop="customer_name" label="客户" min-width="100" show-overflow-tooltip sortable />
            <el-table-column label="余额" width="100" align="right"><template #default="{ row }"><span :style="{ color: row.overdue_days > 0 ? '#f56c6c' : '#67c23a' }">{{ $fm(row.balance) }}</span></template></el-table-column>
            <el-table-column prop="due_date" label="到期日" width="90" sortable />
            <el-table-column label="逾期" width="60" align="center"><template #default="{ row }"><span :style="{ color: row.overdue_days > 0 ? '#f56c6c' : '#909399' }">{{ row.overdue_days > 0 ? row.overdue_days + '天' : '-' }}</span></template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><div style="display: flex; justify-content: flex-end; gap: 8px"><span style="flex: 1; font-weight: 600; font-size: 14px; color: #409eff">应付账款账龄</span></div></template>
          <el-table :data="apAging" stripe border size="small" style="width: 100%" max-height="240" @row-click="drillAP">
            <el-table-column prop="supplier_name" label="供应商" min-width="100" show-overflow-tooltip sortable />
            <el-table-column label="余额" width="100" align="right"><template #default="{ row }"><span :style="{ color: row.overdue_days > 0 ? '#f56c6c' : '#67c23a' }">{{ $fm(row.balance) }}</span></template></el-table-column>
            <el-table-column prop="due_date" label="到期日" width="90" sortable />
            <el-table-column label="逾期" width="60" align="center"><template #default="{ row }"><span :style="{ color: row.overdue_days > 0 ? '#f56c6c' : '#909399' }">{{ row.overdue_days > 0 ? row.overdue_days + '天' : '-' }}</span></template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 12px">
      <template #header><div style="display: flex; justify-content: flex-end; gap: 8px"><span style="flex: 1; font-weight: 600; font-size: 14px; color: #67c23a">销售毛利（按实际出库）</span></div></template>
      <el-table :data="profitList" stripe border size="small" style="width: 100%" @row-click="openProfitDetail">
        <el-table-column label="订单号" width="150"><template #default="{ row }"><el-button link type="primary" size="small" @click.stop="openOrderDetail(row.order_no)">{{ row.order_no }}</el-button></template></el-table-column>
        <el-table-column prop="customer_name" label="客户" min-width="100" show-overflow-tooltip sortable />
        <el-table-column prop="product_name" label="产品" min-width="120" sortable />
        <el-table-column label="数量" width="70" align="right"><template #default="{ row }">{{ $fq(row.qty) }}</template></el-table-column>
        <el-table-column label="收入" width="110" align="right"><template #default="{ row }">{{ $fm(row.revenue) }}</template></el-table-column>
        <el-table-column label="成本" width="110" align="right"><template #default="{ row }" :style="{ color: '#f56c6c' }">{{ $fm(row.cost) }}</template></el-table-column>
        <el-table-column label="毛利" width="110" align="right"><template #default="{ row }"><span :style="{ color: row.gross_profit >= 0 ? '#67c23a' : '#f56c6c' }">{{ $fm(row.gross_profit) }}</span></template></el-table-column>
        <el-table-column label="毛利率" width="80" align="right"><template #default="{ row }"><el-tag :type="row.margin >= 30 ? 'success' : row.margin >= 10 ? 'warning' : 'danger'" size="small">{{ row.margin }}%</el-tag></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="profitVisible" :title="'销售成本拆解 — ' + profitDetail.product_name" width="970px">
      <div v-if="profitDetail.product_name">
        <el-descriptions :column="4" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="产品">{{ profitDetail.product_name }}</el-descriptions-item>
          <el-descriptions-item label="总收入">{{ $fm(profitDetail.total_revenue) }}</el-descriptions-item>
          <el-descriptions-item label="总成本">{{ $fm(profitDetail.total_cost) }}</el-descriptions-item>
          <el-descriptions-item label="总毛利"><span :style="{ color: profitDetail.total_profit >= 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">{{ $fm(profitDetail.total_profit) }}</span></el-descriptions-item>
        </el-descriptions>
        <el-table :data="profitDetail.detail" border stripe size="small" style="width: 100%">
          <el-table-column label="销售订单" width="120"><template #default="{ row }"><el-button link type="primary" size="small" @click="openOrderDetail(row.order_no)">{{ row.order_no }}</el-button></template></el-table-column>
          <el-table-column prop="customer_name" label="客户" min-width="100" show-overflow-tooltip sortable />
          <el-table-column label="数量" width="70" align="right"><template #default="{ row }">{{ $fq(row.qty) }}</template></el-table-column>
          <el-table-column label="销售发票号" width="120"><template #default="{ row }"><el-button v-if="row.invoice_no" link type="primary" size="small" @click="openInvoiceDetail(row.invoice_no)">{{ row.invoice_no }}</el-button></template></el-table-column>
          <el-table-column label="销售单价" width="90" align="right"><template #default="{ row }">{{ $fm(row.unit_price) }}</template></el-table-column>
          <el-table-column label="销售金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.revenue) }}</template></el-table-column>
          <el-table-column label="出库单号" width="120"><template #default="{ row }"><el-button v-if="row.trans_no" link type="primary" size="small" @click="openTransDetail(row.trans_no)">{{ row.trans_no }}</el-button></template></el-table-column>
          <el-table-column label="成本单价" width="90" align="right"><template #default="{ row }">{{ $fm(row.unit_cost) }}</template></el-table-column>
          <el-table-column label="成本金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.cost) }}</template></el-table-column>
          <el-table-column label="毛利" width="100" align="right"><template #default="{ row }"><span :style="{ color: row.gross_profit >= 0 ? '#67c23a' : '#f56c6c' }">{{ $fm(row.gross_profit) }}</span></template></el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-dialog v-model="deliveryVisible" title="发货单详情" width="550px">
      <el-descriptions :column="2" border size="small" v-if="deliveryData">
        <el-descriptions-item label="发货单号" span="2">{{ deliveryData.delivery_no }}</el-descriptions-item>
        <el-descriptions-item label="关联订单">{{ deliveryData.order_no }}</el-descriptions-item>
        <el-descriptions-item label="产品">{{ deliveryData.product_name }}</el-descriptions-item>
        <el-descriptions-item label="批次号">{{ deliveryData.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ $fq(deliveryData.quantity) }}</el-descriptions-item>
        <el-descriptions-item label="含税单价">{{ $fm(deliveryData.unit_price) }}</el-descriptions-item>
        <el-descriptions-item label="含税金额" span="2"><span style="font-weight: bold">{{ $fm(deliveryData.amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="发货日期">{{ deliveryData.delivery_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ deliveryData.status }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ deliveryData.operator }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="orderVisible" title="销售订单详情" width="500px">
      <el-descriptions :column="2" border size="small" v-if="orderData">
        <el-descriptions-item label="订单号" span="2">{{ orderData.order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ orderData.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="订单日期">{{ orderData.order_date }}</el-descriptions-item>
        <el-descriptions-item label="含税金额"><span style="font-weight: bold">{{ $fm(orderData.total_amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="已开票">{{ $fm(orderData.invoiced_amount) }}</el-descriptions-item>
        <el-descriptions-item label="已发货">{{ $fm(orderData.delivered_amount) }}</el-descriptions-item>
        <el-descriptions-item label="已收款">{{ $fm(orderData.collected_amount) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="transVisible" title="库存流水详情" width="550px">
      <el-descriptions :column="2" border size="small" v-if="transData">
        <el-descriptions-item label="流水号" span="2">{{ transData.trans_no }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ { sale_out: '销售出库', production_in: '完工入库', purchase_in: '采购入库', issue_cancel: '取消发料', receipt_cancel: '取消入库' }[transData.trans_type] || transData.trans_type }}</el-descriptions-item>
        <el-descriptions-item label="批次号">{{ transData.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ $fq(Math.abs(transData.quantity)) }}</el-descriptions-item>
        <el-descriptions-item label="单位成本">{{ $fm(transData.unit_cost) }}</el-descriptions-item>
        <el-descriptions-item label="总金额" span="2"><span style="font-weight: bold">{{ $fm(Math.abs(transData.total_amount)) }}</span></el-descriptions-item>
        <el-descriptions-item label="来源单据">{{ transData.source_doc_type }}</el-descriptions-item>
        <el-descriptions-item label="来源单号">{{ transData.source_doc_no }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="invoiceVisible" title="销售发票详情" width="500px">
      <el-descriptions :column="2" border size="small" v-if="invoiceData">
        <el-descriptions-item label="发票号" span="2">{{ invoiceData.invoice_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ invoiceData.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="含税金额"><span style="font-weight: bold">{{ $fm(invoiceData.total_amount || invoiceData.amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="税率">{{ invoiceData.tax_rate }}%</el-descriptions-item>
        <el-descriptions-item label="税额">{{ $fm(invoiceData.tax_amount) }}</el-descriptions-item>
        <el-descriptions-item label="不含税金额">{{ $fm(invoiceData.amount_excl_tax || invoiceData.total_amount_excl_tax) }}</el-descriptions-item>
        <el-descriptions-item label="开票日期">{{ invoiceData.invoice_date }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="netCashVisible" :title="'现金净收支明细 — ' + netCashMonth" width="700px">
      <div>
        <el-descriptions :column="3" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="收款合计"><span style="color: #409eff; font-weight: bold">{{ $fm(netCashDetail.total_collection) }}</span></el-descriptions-item>
          <el-descriptions-item label="付款合计"><span style="color: #e6a23c; font-weight: bold">{{ $fm(netCashDetail.total_payment) }}</span></el-descriptions-item>
          <el-descriptions-item label="净收支"><span :style="{ color: netCashDetail.net >= 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">{{ $fm(netCashDetail.net) }}</span></el-descriptions-item>
        </el-descriptions>
        <div style="display: flex; gap: 12px; margin-bottom: 8px">
          <el-button :type="netCashActiveTab === 'collections' ? 'primary' : 'default'" size="small" @click="netCashActiveTab = 'collections'">收款明细</el-button>
          <el-button :type="netCashActiveTab === 'payments' ? 'primary' : 'default'" size="small" @click="netCashActiveTab = 'payments'">付款明细</el-button>
        </div>
        <el-table v-show="netCashActiveTab === 'collections'" :data="netCashDetail.collections" border stripe size="small" style="width: 100%">
          <el-table-column prop="doc_no" label="收款单号" width="180" sortable />
          <el-table-column label="金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
          <el-table-column prop="date" label="日期" width="100" sortable />
          <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip sortable />
        </el-table>
        <el-table v-show="netCashActiveTab === 'payments'" :data="netCashDetail.payments" border stripe size="small" style="width: 100%">
          <el-table-column prop="doc_no" label="付款单号" width="180" sortable />
          <el-table-column label="金额" width="120" align="right"><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
          <el-table-column prop="date" label="日期" width="100" sortable />
          <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip sortable />
        </el-table>
      </div>
    </el-dialog>

    <el-dialog v-model="arDetailVisible" :title="arDetailTitle" width="970px">
      <el-table :data="arDetailItems" border stripe size="small" style="width: 100%">
        <el-table-column prop="ar_no" label="应收单号" width="160" sortable />
        <el-table-column label="单据日期" width="100" prop="invoice_date" sortable />
        <el-table-column label="结算方式" width="80" prop="payment_terms" sortable />
        <el-table-column label="账期" width="60" prop="account_period" sortable />
        <el-table-column label="金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column label="已收" width="110" align="right"><template #default="{ row }">{{ $fm(row.collected_amount) }}</template></el-table-column>
        <el-table-column label="余额" width="110" align="right">
          <template #default="{ row }"><span style="color: #e6a23c; font-weight: bold">{{ $fm(row.balance) }}</span></template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日" width="100" sortable />
        <el-table-column prop="status" label="状态" width="80" align="center" sortable>
          <template #default="{ row }"><el-tag :type="row.status === '已收款' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="apDetailVisible" :title="apDetailTitle" width="970px">
      <el-table :data="apDetailItems" border stripe size="small" style="width: 100%">
        <el-table-column prop="ap_no" label="应付单号" width="160" sortable />
        <el-table-column label="单据日期" width="100" prop="invoice_date" sortable />
        <el-table-column label="结算方式" width="80" prop="payment_terms" sortable />
        <el-table-column label="账期" width="60" prop="account_period" sortable />
        <el-table-column label="金额" width="110" align="right"><template #default="{ row }">{{ $fm(row.amount) }}</template></el-table-column>
        <el-table-column label="已付" width="110" align="right"><template #default="{ row }">{{ $fm(row.paid_amount) }}</template></el-table-column>
        <el-table-column label="余额" width="110" align="right">
          <template #default="{ row }"><span style="color: #f56c6c; font-weight: bold">{{ $fm(row.balance) }}</span></template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日" width="100" sortable />
        <el-table-column prop="status" label="状态" width="80" align="center" sortable>
          <template #default="{ row }"><el-tag :type="row.status === '已付款' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dashboardApi, inventoryApi, purchaseApi, salesApi, notificationApi } from '../api/business'

const router = useRouter()

// ============ 消息中心（移植 AO 分支） ============
const msgTab = ref('unread')  // 默认未读页签
const msgs = ref([])
const unreadTotal = ref(0)
const MSG_DOC_ROUTES = {
  so_order: '/sales/orders',
  mo_production: '/production/orders',
  ar_account: '/sales/ar',
  ap_account: '/purchase/ap',
}

async function fetchUnreadCount() {
  try {
    const r = await notificationApi.unreadCount()
    unreadTotal.value = r.count || 0
  } catch {}
}

async function fetchMsgs() {
  try {
    msgs.value = await notificationApi.list({
      page: 1, page_size: 20,
      read_status: msgTab.value === 'unread' ? 0 : 1,
    }) || []
  } catch {}
  if (msgTab.value === 'unread') fetchUnreadCount()
}

async function openMsg(n) {
  if (n.read_status === 0) {
    try {
      await notificationApi.markRead(n.id)
      n.read_status = 1
      if (msgTab.value === 'unread') {
        msgs.value = msgs.value.filter(x => x.id !== n.id)
      }
      unreadTotal.value = Math.max(0, unreadTotal.value - 1)
    } catch {}
  }
  const target = MSG_DOC_ROUTES[n.doc_type]
  if (target) router.push(target)
}

async function markAllReadMsg() {
  try {
    await notificationApi.readAll()
    msgs.value = []
    unreadTotal.value = 0
    ElMessage.success('已全部标记为已读')
  } catch {}
}

const cashIn = ref([])
const cashOut = ref([])
const arAging = ref([])
const apAging = ref([])
const profitList = ref([])
const profitVisible = ref(false)
const profitDetail = ref({})
const deliveryVisible = ref(false)
const deliveryData = ref(null)
const orderVisible = ref(false)
const orderData = ref(null)
const transVisible = ref(false)
const transData = ref(null)
const invoiceVisible = ref(false)
const invoiceData = ref(null)
const netCashVisible = ref(false)
const netCashMonth = ref('')
const netCashDetail = ref({ collections: [], payments: [], total_collection: 0, total_payment: 0, net: 0 })
const netCashActiveTab = ref('collections')
const arDetailVisible = ref(false)
const arDetailTitle = ref('')
const arDetailItems = ref([])
const apDetailVisible = ref(false)
const apDetailTitle = ref('')
const apDetailItems = ref([])

const maxCashIn = computed(() => Math.max(...cashIn.value.map(i => i.amount), 1))
const maxCashOut = computed(() => Math.max(...cashOut.value.map(i => i.amount), 1))
const netCash = computed(() => {
  return cashIn.value.map((ci, i) => ({
    month: ci.month,
    amount: (ci.amount || 0) - ((cashOut.value[i] && cashOut.value[i].amount) || 0),
  }))
})
const maxNetCash = computed(() => Math.max(...netCash.value.map(i => Math.abs(i.amount)), 1))

function barHeight(amount, maxVal) { return Math.max(4, (amount / maxVal) * 130) }
function netBarHeight(amount, maxVal) { return Math.max(4, (Math.abs(amount) / maxVal) * 130) }

async function fetchData() {
  try {
    const res = await dashboardApi.summary()
    cashIn.value = res.cash_in || []; cashOut.value = res.cash_out || []
    arAging.value = res.ar_aging || []; apAging.value = res.ap_aging || []
    profitList.value = res.profit || []
  } catch (e) { ElMessage.error('加载驾驶舱数据失败') }
}

function drillCollection(month) { router.push({ path: '/sales/collections', query: { month } }) }
function drillPayment(month) { router.push({ path: '/purchase/payments', query: { month } }) }
async function drillAR(row) {
  arDetailTitle.value = `应收账款明细 — ${row.customer_name}`
  arDetailItems.value = []
  arDetailVisible.value = true
  try {
    const res = await salesApi.ar.list({ page_size: 100 })
    arDetailItems.value = (res.items || []).filter(a => a.customer_name === row.customer_name && a.balance > 0)
  } catch (e) {}
}
async function drillAP(row) {
  apDetailTitle.value = `应付账款明细 — ${row.supplier_name}`
  apDetailItems.value = []
  apDetailVisible.value = true
  try {
    const res = await purchaseApi.ap.list({ page_size: 100 })
    apDetailItems.value = (res.items || []).filter(a => a.supplier_name === row.supplier_name && a.balance > 0)
  } catch (e) {}
}

async function drillCollectionMonth(month) {
  netCashMonth.value = month; netCashActiveTab.value = 'collections'; netCashVisible.value = true
  try { netCashDetail.value = await dashboardApi.netCashDetail(month, month) } catch (e) {}
}
async function drillPaymentMonth(month) {
  netCashMonth.value = month; netCashActiveTab.value = 'payments'; netCashVisible.value = true
  try { netCashDetail.value = await dashboardApi.netCashDetail(month, month) } catch (e) {}
}
async function drillNetCash(month) {
  netCashMonth.value = month; netCashActiveTab.value = 'collections'; netCashVisible.value = true
  try { netCashDetail.value = await dashboardApi.netCashDetail(month, month) } catch (e) {}
}

function openProfitDetail(row) {
  profitDetail.value = { product_name: row.product_name }
  profitVisible.value = true
  dashboardApi.profitDetail(row.product_id, row.product_id).then(res => { profitDetail.value = res }).catch(() => {})
}

async function openDeliveryDetail(deliveryNo) {
  try {
    const res = await salesApi.deliveries.list({ keyword: deliveryNo, deliveryNo })
    deliveryData.value = (res.items || []).find(d => d.delivery_no === deliveryNo) || null
    deliveryVisible.value = true
  } catch (e) { ElMessage.error('加载发货单失败') }
}

async function openOrderDetail(orderNo) {
  try {
    const res = await salesApi.orders.list({ keyword: orderNo, orderNo })
    orderData.value = (res.items || []).find(d => d.order_no === orderNo) || null
    orderVisible.value = true
  } catch (e) { ElMessage.error('加载订单失败') }
}

async function openTransDetail(transNo) {
  try {
    const res = await inventoryApi.transactions({ keyword: transNo, transNo })
    transData.value = (res.items || []).find(d => d.trans_no === transNo) || null
    transVisible.value = true
  } catch (e) { ElMessage.error('加载流水失败') }
}

async function openInvoiceDetail(invoiceNo) {
  try {
    const res = await salesApi.invoices.list({ keyword: invoiceNo, invoiceNo })
    invoiceData.value = (res.items || []).find(d => d.invoice_no === invoiceNo) || null
    invoiceVisible.value = true
  } catch (e) { ElMessage.error('加载发票失败') }
}

onMounted(() => { fetchData(); fetchUnreadCount(); fetchMsgs() })
</script>
