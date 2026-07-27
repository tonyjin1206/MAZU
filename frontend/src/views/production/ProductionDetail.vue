<template>
  <div style="padding: 16px">
    <el-page-header @back="$router.back()" :content="`${order.order_no} - ${order.product_name}`" style="margin-bottom: 16px" />
    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="订单信息" name="info">
          <el-form label-width="120px" :model="order">
            <el-row :gutter="16">
              <el-col :span="8"><el-form-item label="订单号"><el-input :model-value="order.order_no" disabled /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="产品"><el-input :model-value="order.product_name" disabled /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="生产数量"><el-input type="number" v-model="order.quantity" :disabled="order.status !== '待排产'" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8"><el-form-item label="状态"><el-tag :type="statusType(order.status)">{{ order.status }}</el-tag></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="交期"><el-input :model-value="order.due_date" disabled /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="保存日期"><el-input :model-value="order.created_at" disabled /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8"><el-form-item label="物料成本"><el-input :model-value="$fm(order.total_material_cost)" disabled /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="加工费合计"><el-input :model-value="$fm(order.total_process_cost)" disabled /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="24"><el-form-item label="备注"><el-input v-model="order.remark" type="textarea" :rows="2" :disabled="order.status !== '待排产'" /></el-form-item></el-col>
            </el-row>
          </el-form>
          <div v-if="order.status === '待排产'" style="margin-top: 12px">
            <el-button type="primary" @click="expandBom" :loading="bomLoading">展开BOM</el-button>
            <el-button type="success" @click="releaseOrder" :loading="releaseLoading" style="margin-left: 12px">派产</el-button>
          </div>
          <div v-if="order.status === '已排产' || order.status === '生产中'" style="margin-top: 12px">
            <el-button type="warning" @click="unreleaseOrder" :loading="unreleaseLoading">反派产</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="物料清单" name="materials">
          <el-button v-if="order.status === '待排产'" size="small" @click="addMaterialRow" style="margin-bottom: 8px">+ 添加物料</el-button>
          <el-table :data="materials" border size="small" max-height="400" style="table-layout: auto">
            <el-table-column label="物料" min-width="180">
              <template #default="{ row }">
                <el-select v-model="row.material_id" placeholder="选择" filterable size="small" style="width: 100%" :disabled="order.status !== '待排产'">
                  <el-option v-for="m in materialOptions" :key="m.id" :label="`${m.code} - ${m.name}`" :value="m.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="计划用量" width="120" align="right">
              <template #default="{ row }">
                <el-input v-if="order.status === '待排产'" type="number" v-model="row.planned_qty" size="small" style="text-align: right" />
                <span v-else>{{ $fq(row.planned_qty) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已发" width="100" align="right">
              <template #default="{ row }">{{ $fq(row.actual_qty) }}</template>
            </el-table-column>
            <el-table-column label="已发金额" width="110" align="right">
              <template #default="{ row }">{{ $fm(row.issued_amount || 0) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="60">
              <template #default="{ row }">
                <el-button v-if="row.actual_qty > 0" link type="primary" size="small" @click="openMaterialDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button v-if="order.status === '待排产'" type="primary" size="small" @click="saveMaterials" :loading="matLoading" style="margin-top: 8px">保存物料清单</el-button>

          <!-- 物料发料明细弹窗 -->
          <el-dialog v-model="matDetailVisible" :title="matDetailTitle" width="750px" destroy-on-close>
            <el-table :data="matDetailItems" border size="small" max-height="300" style="table-layout: auto">
              <el-table-column label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.type === 'outsource_out' ? 'warning' : 'success'" size="small">{{ row.type_label }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="单号" min-width="140" prop="trans_no" />
              <el-table-column label="批次号" min-width="130" prop="batch_no" />
              <el-table-column label="数量" width="80" align="right" prop="quantity" />
              <el-table-column label="金额" width="100" align="right">
                <template #default="{ row }">{{ $fm(row.amount) }}</template>
              </el-table-column>
              <el-table-column label="日期" width="140" prop="date" />
              <el-table-column label="操作人" width="80" prop="operator" />
            </el-table>
            <div v-if="matDetailSummary" style="margin-top: 12px; padding: 12px; background: #f5f7fa; border-radius: 4px; display: flex; gap: 30px; font-size: 13px">
              <div>发料：<b>{{ $fq(matDetailSummary.out_qty) }}</b> / <b>{{ $fm(matDetailSummary.out_amount) }}</b></div>
              <div>退料：<b>{{ $fq(matDetailSummary.cancel_qty) }}</b> / <b>{{ $fm(matDetailSummary.cancel_amount) }}</b></div>
              <div style="font-weight: bold; color: #409eff">净发料：<b>{{ $fq(matDetailSummary.net_qty) }}</b> / <b>{{ $fm(matDetailSummary.net_amount) }}</b></div>
            </div>
          </el-dialog>
        </el-tab-pane>

        <el-tab-pane label="工艺路线" name="processes">
          <el-button v-if="order.status === '待排产'" size="small" @click="addProcessRow" style="margin-bottom: 8px">+ 添加工序</el-button>
          <el-table :data="processes" border size="small" max-height="400">
            <el-table-column label="序号" width="50" align="center" prop="seq" />
            <el-table-column label="工序" min-width="140">
              <template #default="{ row }">
                <el-select v-model="row.process_id" placeholder="选择" filterable size="small" style="width: 100%" :disabled="order.status !== '待排产'">
                  <el-option v-for="p in processOptions" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="委外商" min-width="140">
              <template #default="{ row }">
                <el-select v-model="row.outsourcer_id" placeholder="自产(留空)" clearable filterable size="small" style="width: 100%">
                  <el-option v-for="o in outsourcerOptions" :key="o.id" :label="o.name" :value="o.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="加工单价" width="100" align="right">
              <template #default="{ row }"><el-input type="number" v-model="row.unit_price" size="small" /></template>
            </el-table-column>
            <el-table-column label="加工数量" width="100" align="right">
              <template #default="{ row }"><el-input type="number" v-model="row.process_qty" size="small" /></template>
            </el-table-column>
            <el-table-column label="加工费" width="100" align="right">
              <template #default="{ row }">{{ $fm((row.process_qty || 0) * (row.unit_price || 0)) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }"><el-tag :type="procStatusType(row.status)" size="small">{{ row.status || '待排产' }}</el-tag></template>
            </el-table-column>
            <el-table-column v-if="order.status === '待排产'" width="50">
              <template #default="{ $index }"><el-button link type="danger" size="small" @click="processes.splice($index, 1)">删</el-button></template>
            </el-table-column>
          </el-table>
          <el-button v-if="order.status === '待排产'" type="primary" size="small" @click="saveProcesses" :loading="procLoading" style="margin-top: 8px">保存工艺路线</el-button>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

const route = useRoute()
const activeTab = ref('info')
const order = reactive({ id: null, order_no: '', product_name: '', quantity: 0, status: '', total_material_cost: 0, total_process_cost: 0, due_date: '', remark: '', created_at: '' })
const materials = ref([])
const processes = ref([])
const materialOptions = ref([])
const processOptions = ref([])
const outsourcerOptions = ref([])

const bomLoading = ref(false)
const releaseLoading = ref(false)
const unreleaseLoading = ref(false)
const matLoading = ref(false)
const procLoading = ref(false)
const matDetailVisible = ref(false)
const matDetailTitle = ref('')
const matDetailItems = ref([])
const matDetailSummary = ref(null)

function statusType(s) {
  return { '待排产': 'info', '已排产': 'warning', '生产中': 'primary', '已完成': 'success', '已入库': 'success', '已关闭': 'danger' }[s] || 'info'
}
function procStatusType(s) {
  return { '待排产': 'info', '待发料': '', '已发料': 'warning', '加工中': 'primary', '已完工': 'success' }[s] || 'info'
}

async function fetchDetail() {
  const id = route.params.id
  const res = await productionApi.productions.detail(id)
  Object.assign(order, res)
  materials.value = res.materials || []
  processes.value = res.processes || []
}

async function loadOptions() {
  try { materialOptions.value = (await foundationApi.materials.list({ page_size: 200 })).items || [] } catch {}
  try {
    const res = await foundationApi.processes.list({ page_size: 200 })
    processOptions.value = res.items || []
  } catch {}
  try { outsourcerOptions.value = (await foundationApi.outsourcers.select()) || [] } catch {}
}

async function expandBom() {
  bomLoading.value = true
  try {
    const res = await productionApi.productions.expandBom(order.id)
    ElMessage.success(res.message)
    fetchDetail()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '展开BOM失败') } finally { bomLoading.value = false }
}

async function releaseOrder() {
  await ElMessageBox.confirm('确认派产？派产后工艺路线将被锁定。', '提示', { type: 'info' })
  releaseLoading.value = true
  try {
    const res = await productionApi.productions.release(order.id)
    ElMessage.success(res.message)
    fetchDetail()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '派产失败') } finally { releaseLoading.value = false }
}

async function unreleaseOrder() {
  await ElMessageBox.confirm('确认反派产？', '提示', { type: 'warning' })
  unreleaseLoading.value = true
  try {
    const res = await productionApi.productions.unrelease(order.id)
    ElMessage.success(res.message)
    fetchDetail()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '反派产失败') } finally { unreleaseLoading.value = false }
}

async function openMaterialDetail(row) {
  matDetailTitle.value = `${row.material_name} - 发料明细`
  matDetailItems.value = []
  matDetailSummary.value = null
  matDetailVisible.value = true
  try {
    const res = await productionApi.productions.listMaterialIssues(order.id, row.material_id)
    matDetailItems.value = res.items || []
    matDetailSummary.value = res.summary || null
  } catch {}
}

function addMaterialRow() {
  materials.value.push({ material_id: null, planned_qty: 0, actual_qty: 0, unit_price: 0, sort_order: materials.value.length })
}

async function saveMaterials() {
  matLoading.value = true
  try {
    await productionApi.productions.saveMaterials(order.id, materials.value)
    ElMessage.success('物料清单已保存')
    fetchDetail()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { matLoading.value = false }
}

function addProcessRow() {
  processes.value.push({ process_id: null, seq: processes.value.length + 1, outsourcer_id: null, unit_price: 0, process_qty: order.quantity || 0, status: '待排产' })
}

async function saveProcesses() {
  procLoading.value = true
  try {
    await productionApi.productions.saveProcesses(order.id, processes.value)
    ElMessage.success('工艺路线已保存')
    fetchDetail()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') } finally { procLoading.value = false }
}

onMounted(() => { fetchDetail(); loadOptions() })
</script>
