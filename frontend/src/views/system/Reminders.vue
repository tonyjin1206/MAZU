<template>
  <div>
    <el-tabs v-model="activeTab">
      <!-- ============ Tab1 提醒规则（D8：规则配置化） ============ -->
      <el-tab-pane label="提醒规则" name="rules">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: flex-end; gap: 8px">
              <el-button type="primary" @click="fetchRules">刷新</el-button>
              <el-button type="primary" @click="openRuleCreate">新建规则</el-button>
            </div>
          </template>
          <el-table :data="rules" v-loading="ruleLoading" stripe border size="small">
            <el-table-column prop="name" label="提醒名称" width="160" />
            <el-table-column label="触发方式" width="110" sortable>
              <template #default="{ row }">
                <el-tag :type="row.trigger_type === 'event' ? 'primary' : 'warning'" size="small">
                  {{ row.trigger_type === 'event' ? '事件联动' : '定时扫描' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="接收角色" min-width="180">
              <template #default="{ row }">
                <el-tag v-for="rc in (row.target_roles || [])" :key="rc" size="small"
                        style="margin-right: 4px">{{ roleName(rc) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提醒方式" width="130">
              <template #default="{ row }">
                <el-tag v-if="(row.channel || []).includes('inapp')" size="small" type="info" style="margin-right:4px">站内</el-tag>
                <el-tag v-if="(row.channel || []).includes('wecom')" size="small" type="success">企微</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="参数" min-width="150">
              <template #default="{ row }">
                <span v-if="row.trigger_type === 'event'">去重 {{ row.dedup_hours }} 小时</span>
                <span v-else>提前 {{ row.advance_days }} 天 / {{ row.schedule_cron }}</span>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="70" align="center">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" :active-value="1" :inactive-value="0"
                           @change="(v) => toggleRule(row, v)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openRuleEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="handleRuleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ============ Tab2 用户提醒开关（原有） ============ -->
      <el-tab-pane label="用户提醒开关" name="users">
        <el-card style="margin-bottom:12px">
          <template #header>
            <div style="display: flex; justify-content: flex-end; gap: 8px">
              <el-button type="primary" @click="fetchData">刷新</el-button>
              <el-button type="primary" @click="openCreate">新建提醒</el-button>
            </div>
          </template>
        </el-card>

        <el-card>
          <el-table :data="list" v-loading="loading" stripe border size="small">
            <el-table-column prop="user_name" label="用户" width="120" />
            <el-table-column label="提醒类型" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.type==='daily_todo'" size="small">日待办</el-tag>
                <el-tag v-else-if="row.type==='expiry'" type="warning" size="small">到期提醒</el-tag>
                <el-tag v-else-if="row.type==='overdue'" type="danger" size="small">逾期告警</el-tag>
                <el-tag v-else-if="row.type==='weekly'" type="success" size="small">周报</el-tag>
                <el-tag v-else-if="row.type==='boss_report'" type="primary" size="small">老板日报</el-tag>
                <span v-else>{{ row.type }}</span>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="70" align="center">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" :active-value="1" :inactive-value="0"
                           @change="(v) => toggleEnable(row, v)" />
              </template>
            </el-table-column>
            <el-table-column prop="push_time" label="推送时间" width="100" />
            <el-table-column prop="push_days" label="推送日" width="100" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- ============ 规则新建/编辑弹窗 ============ -->
    <el-dialog v-model="ruleDialogVisible" :title="ruleForm.id ? '编辑提醒规则' : '新建提醒规则'" width="640px" destroy-on-close>
      <el-form :model="ruleForm" label-width="100px" ref="ruleFormRef" :rules="ruleRules">
        <el-form-item label="提醒点" prop="code">
          <el-select v-model="ruleForm.code" :disabled="!!ruleForm.id" style="width:100%"
                     placeholder="选择已有提醒点（新增触发逻辑需开发）">
            <el-option v-for="p in pointOptions" :key="p.code" :label="`${p.name} (${p.code})`" :value="p.code" />
          </el-select>
          <div style="color:#909399;font-size:12px;line-height:1.4;margin-top:4px">
            提醒点 = 代码埋点的业务动作，配置界面只能调整已有提醒点的参数（D8 边界）
          </div>
        </el-form-item>
        <el-form-item label="提醒名称" prop="name">
          <el-input v-model="ruleForm.name" maxlength="64" />
        </el-form-item>
        <el-form-item label="触发方式">
          <el-radio-group v-model="ruleForm.trigger_type">
            <el-radio value="event">事件联动</el-radio>
            <el-radio value="schedule">定时扫描</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题模板" prop="title_template">
          <el-input v-model="ruleForm.title_template" placeholder="如：销售订单 {order_no} 已审核，请安排排产" />
        </el-form-item>
        <el-form-item label="正文模板">
          <el-input v-model="ruleForm.content_template" type="textarea" :rows="3"
                    placeholder="如：订单 {order_no}（客户 {customer_name}）已审核通过…" />
          <div style="color:#909399;font-size:12px;margin-top:4px">
            可用占位符：{order_no} {customer_name} {mo_count} {product_name} {quantity} {ar_no} {ap_no} {supplier_name} {amount} {balance} {due_date}
          </div>
        </el-form-item>
        <el-form-item label="接收角色" prop="target_roles">
          <el-select v-model="ruleForm.target_roles" multiple filterable style="width:100%" placeholder="选择接收岗位">
            <el-option v-for="r in roleList" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="提醒方式">
          <el-checkbox-group v-model="ruleForm.channel">
            <el-checkbox value="inapp">站内通知</el-checkbox>
            <el-checkbox value="wecom">企业微信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <template v-if="ruleForm.trigger_type === 'event'">
          <el-form-item label="去重窗口">
            <el-input-number v-model="ruleForm.dedup_hours" :min="0" :max="72" /> <span style="margin-left:8px">小时内同单据只推一次</span>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="提前天数">
            <el-input-number v-model="ruleForm.advance_days" :min="0" :max="90" /> <span style="margin-left:8px">天（到期前 N 天提醒）</span>
          </el-form-item>
          <el-form-item label="扫描时间">
            <el-input v-model="ruleForm.schedule_cron" style="width:200px" placeholder="0 9 * * *" />
            <span style="color:#909399;font-size:12px;margin-left:8px">cron 表达式，默认每日 09:00</span>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="handleRuleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemConfigApi, authApi } from '../../api/foundation'

const activeTab = ref('rules')

// ============ 提醒规则 ============
// 已有代码埋点的提醒点（新增触发逻辑需开发 — D8 边界）
const POINT_OPTIONS = [
  { code: 'SO_APPROVED', name: '销售订单审核' },
  { code: 'MO_PLANNED', name: '排产备料' },
  { code: 'MO_OUTSOURCED', name: '生产转外购' },
  { code: 'AR_CREATED', name: '应收生成' },
  { code: 'AR_DUE', name: '应收到期预警' },
  { code: 'AP_DUE', name: '应付到期预警' },
]

const rules = ref([])
const ruleLoading = ref(false)
const ruleDialogVisible = ref(false)
const ruleSaving = ref(false)
const ruleFormRef = ref(null)
const roleList = ref([])
const pointOptions = POINT_OPTIONS

const emptyRule = () => ({
  id: null, code: '', name: '', trigger_type: 'event', enabled: 1,
  title_template: '', content_template: '', target_roles: [],
  channel: ['inapp'], schedule_cron: '0 9 * * *', advance_days: 7, dedup_hours: 1,
})
const ruleForm = reactive(emptyRule())

const ruleRules = {
  code: [{ required: true, message: '必选提醒点', trigger: 'change' }],
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  target_roles: [{ required: true, type: 'array', min: 1, message: '至少选一个接收角色', trigger: 'change' }],
}

function roleName(code) {
  const r = roleList.value.find(x => x.code === code)
  return r ? r.name : code
}

async function fetchRules() {
  ruleLoading.value = true
  try { rules.value = await systemConfigApi.reminderRules.list() || [] } catch { rules.value = [] }
  ruleLoading.value = false
}

function openRuleCreate() {
  Object.assign(ruleForm, emptyRule())
  ruleDialogVisible.value = true
}

function openRuleEdit(row) {
  Object.assign(ruleForm, {
    id: row.id, code: row.code, name: row.name, trigger_type: row.trigger_type,
    enabled: row.enabled, title_template: row.title_template || '',
    content_template: row.content_template || '',
    target_roles: row.target_roles || [],
    channel: row.channel || ['inapp'],
    schedule_cron: row.schedule_cron || '0 9 * * *',
    advance_days: row.advance_days ?? 7,
    dedup_hours: row.dedup_hours ?? 1,
  })
  ruleDialogVisible.value = true
}

async function toggleRule(row, val) {
  try {
    await systemConfigApi.reminderRules.update(row.id, { enabled: val ? 1 : 0 })
    row.enabled = val ? 1 : 0
    ElMessage.success(val ? '已启用' : '已停用')
  } catch {}
}

async function handleRuleSave() {
  const valid = await ruleFormRef.value.validate().catch(() => false)
  if (!valid) return
  ruleSaving.value = true
  try {
    const payload = {
      code: ruleForm.code, name: ruleForm.name, trigger_type: ruleForm.trigger_type,
      enabled: ruleForm.enabled, title_template: ruleForm.title_template,
      content_template: ruleForm.content_template, target_roles: ruleForm.target_roles,
      channel: ruleForm.channel, schedule_cron: ruleForm.schedule_cron,
      advance_days: ruleForm.advance_days, dedup_hours: ruleForm.dedup_hours,
    }
    if (ruleForm.id) {
      await systemConfigApi.reminderRules.update(ruleForm.id, payload)
    } else {
      await systemConfigApi.reminderRules.create(payload)
    }
    ElMessage.success('已保存')
    ruleDialogVisible.value = false
    fetchRules()
  } catch {}
  ruleSaving.value = false
}

async function handleRuleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除规则「${row.name}」？删除后该提醒点不再发送`, '确认', { type: 'warning' })
    await systemConfigApi.reminderRules.delete(row.id)
    ElMessage.success('已删除')
    fetchRules()
  } catch {}
}

// ============ 用户提醒开关（原有） ============
const list = ref([])
const loading = ref(false)
const saving = ref(false)
const typeList = ref([])
const userList = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)

const form = reactive({ user_id: null, type: '', pushTime: '09:00' })
const rules2 = {
  user_id: [{ required: true, message: '必选', trigger: 'change' }],
  type: [{ required: true, message: '必选', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try { list.value = await systemConfigApi.reminders.list() || [] } catch { list.value = [] }
  loading.value = false
}

async function fetchMeta() {
  try { typeList.value = await systemConfigApi.reminders.types() || [] } catch {}
  try { userList.value = await authApi.listUsers() || [] } catch {}
  try { roleList.value = await authApi.listRoles() || [] } catch {}
}

function openCreate() {
  form.user_id = null; form.type = ''; form.pushTime = '09:00'
  dialogVisible.value = true
}

async function toggleEnable(row, val) {
  try {
    await systemConfigApi.reminders.update(row.id, { enabled: val ? 1 : 0 })
    row.enabled = val ? 1 : 0
    ElMessage.success(val ? '已启用' : '已停用')
  } catch {}
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await systemConfigApi.reminders.create({
      user_id: form.user_id,
      type: form.type,
      push_time: form.pushTime,
    })
    ElMessage.success('已创建')
    dialogVisible.value = false
    fetchData()
  } catch {}
  saving.value = false
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await systemConfigApi.reminders.delete(row.id)
    ElMessage.success('已删除')
    fetchData()
  } catch {}
}

onMounted(() => { fetchRules(); fetchData(); fetchMeta() })
</script>
