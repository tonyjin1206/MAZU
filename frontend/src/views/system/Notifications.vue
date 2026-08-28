<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="refresh">刷新</el-button>
        </div>
      </template>
    </el-card>

    <el-card>
      <el-tabs v-model="activeTab">
        <!-- 通知查询（管理端全量，D7 测试/管理） -->
        <el-tab-pane label="通知查询" name="notifications">
          <div style="display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap">
            <el-select v-model="filters.point_code" placeholder="提醒点" clearable filterable style="width: 200px">
              <el-option v-for="r in rules" :key="r.code" :label="`${r.code}（${r.name}）`" :value="r.code" />
            </el-select>
            <el-select v-model="filters.doc_type" placeholder="单据类型" clearable style="width: 150px">
              <el-option v-for="d in docTypes" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
            <el-select v-model="filters.role_code" placeholder="角色" clearable style="width: 150px">
              <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
            <el-select v-model="filters.read_status" placeholder="状态" clearable style="width: 120px">
              <el-option label="未读" :value="0" />
              <el-option label="已读" :value="1" />
            </el-select>
          </div>

          <el-table :data="notifications" v-loading="loading" stripe border size="small">
            <el-table-column prop="title" label="标题" min-width="240" />
            <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip />
            <el-table-column prop="user_name" label="收件人" width="110" />
            <el-table-column prop="role_name" label="角色" width="100" />
            <el-table-column prop="point_code" label="提醒点" width="170" />
            <el-table-column prop="doc_no" label="单据号" width="160" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.read_status === 0" type="warning" size="small">未读</el-tag>
                <el-tag v-else type="info" size="small">已读</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="120">
              <template #default="{ row }">{{ (row.created_at || '').slice(0, 16) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination style="margin-top: 12px" background layout="prev, pager, next, total" :total="total"
            :page-size="filters.page_size" v-model:current-page="filters.page"
            @current-change="fetchNotifications" />
        </el-tab-pane>

        <!-- 提醒规则（规则配置化 D8） -->
        <el-tab-pane label="提醒规则" name="rules">
          <div style="display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 12px">
            <el-button type="primary" @click="openRuleCreate">新增规则</el-button>
          </div>
          <el-table :data="rules" v-loading="ruleLoading" stripe border size="small">
            <el-table-column prop="code" label="编码" width="180" />
            <el-table-column prop="name" label="名称" width="170" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <el-tag :type="row.trigger_type === 'schedule' ? 'warning' : 'primary'" size="small">
                  {{ row.trigger_type === 'schedule' ? '定时' : '事件' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="70">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" @change="(v) => toggleRule(row, v)" />
              </template>
            </el-table-column>
            <el-table-column label="接收角色" min-width="200">
              <template #default="{ row }">{{ (row.target_roles || []).join('、') }}</template>
            </el-table-column>
            <el-table-column prop="advance_days" label="提前(天)" width="80" />
            <el-table-column prop="dedup_hours" label="去重(时)" width="80" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="editRule(row)">编辑</el-button>
                <el-button link type="danger" @click="removeRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 10px; font-size: 12px; color: #909399">
            提示：新增提醒点（触发逻辑）需后端埋点，配置界面只能控制“已有提醒点”的参数（D8）。
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增/编辑规则弹窗 -->
    <el-dialog v-model="ruleDialogVisible" :title="ruleForm.id ? '编辑规则' : '新增规则'" width="620px" destroy-on-close>
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="编码" required><el-input v-model="ruleForm.code" :disabled="!!ruleForm.id" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="ruleForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="ruleForm.trigger_type">
            <el-radio label="event">事件</el-radio>
            <el-radio label="schedule">定时</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题模板"><el-input v-model="ruleForm.title_template" placeholder="支持 {order_no}/{amount}/{due_date}" /></el-form-item>
        <el-form-item label="正文模板"><el-input v-model="ruleForm.content_template" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="接收角色">
          <el-select v-model="ruleForm.target_roles" multiple filterable style="width:100%">
            <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="提前天数" v-if="ruleForm.trigger_type === 'schedule'">
          <el-input-number v-model="ruleForm.advance_days" :min="0" :max="365" />
        </el-form-item>
        <el-form-item label="去重(时)"><el-input-number v-model="ruleForm.dedup_hours" :min="0" :max="240" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { notificationApi, reminderRuleApi } from '../../api/business'

const activeTab = ref('notifications')
const rules = ref([])
const loading = ref(false)
const ruleLoading = ref(false)
const notifications = ref([])
const total = ref(0)
const filters = ref({ page: 1, page_size: 20, point_code: undefined, doc_type: undefined, role_code: undefined, read_status: undefined })

const docTypes = [
  { value: 'so_order', label: '销售订单' },
  { value: 'so_delivery', label: '销售发货' },
  { value: 'ar_account', label: '应收账款' },
  { value: 'ap_account', label: '应付账款' },
]
const roleOptions = [
  { value: 'admin', label: '管理员' },
  { value: 'sales_manager', label: '销售经理' },
  { value: 'purchase_manager', label: '采购经理' },
  { value: 'production_manager', label: '生产经理' },
  { value: 'finance_manager', label: '财务经理' },
  { value: 'warehouse_keeper', label: '库管员' },
]

async function fetchNotifications() {
  loading.value = true
  try {
    const res = await notificationApi.adminQuery(filters.value)
    notifications.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

async function fetchRules() {
  ruleLoading.value = true
  try { rules.value = await reminderRuleApi.list() || [] } finally { ruleLoading.value = false }
}

async function refresh() {
  await Promise.all([fetchNotifications(), fetchRules()])
}

function toggleRule(row, v) {
  reminderRuleApi.update(row.id, { enabled: v ? 1 : 0 }).then((res) => {
    row.enabled = res.enabled
    ElMessage.success('已更新')
  })
}

const ruleDialogVisible = ref(false)
const ruleSaving = ref(false)
const ruleForm = ref({ id: null, code: '', name: '', trigger_type: 'event', title_template: '', content_template: '', target_roles: [], advance_days: 7, dedup_hours: 1 })

function openRuleCreate() {
  ruleForm.value = { id: null, code: '', name: '', trigger_type: 'event', title_template: '', content_template: '', target_roles: [], advance_days: 7, dedup_hours: 1 }
  ruleDialogVisible.value = true
}

function editRule(row) {
  ruleForm.value = { ...row, target_roles: [...(row.target_roles || [])] }
  ruleDialogVisible.value = true
}

async function saveRule() {
  if (!ruleForm.value.code || !ruleForm.value.name) { ElMessage.warning('编码与名称必填'); return }
  ruleSaving.value = true
  try {
    const payload = { ...ruleForm.value }
    if (payload.id) { await reminderRuleApi.update(payload.id, payload); ElMessage.success('已保存') }
    else { await reminderRuleApi.create(payload); ElMessage.success('已新增') }
    ruleDialogVisible.value = false
    fetchRules()
  } finally { ruleSaving.value = false }
}

async function removeRule(row) {
  await ElMessageBox.confirm(`确认删除提醒规则「${row.name}」？`, '删除确认', { type: 'warning' })
  await reminderRuleApi.remove(row.id)
  ElMessage.success('已删除')
  fetchRules()
}

onMounted(() => { refresh() })
</script>
