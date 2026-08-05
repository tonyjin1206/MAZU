<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </div>
      </template>
      <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center">
        <el-select v-model="filters.role_code" placeholder="按角色" clearable style="width: 160px">
          <el-option v-for="r in roleList" :key="r.code" :label="r.name" :value="r.code" />
        </el-select>
        <el-select v-model="filters.user_id" placeholder="按用户" clearable filterable style="width: 160px">
          <el-option v-for="u in userList" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
        </el-select>
        <el-select v-model="filters.point_code" placeholder="按提醒点" clearable style="width: 180px">
          <el-option v-for="p in pointOptions" :key="p.code" :label="p.name" :value="p.code" />
        </el-select>
        <el-select v-model="filters.doc_type" placeholder="按单据类型" clearable style="width: 140px">
          <el-option v-for="t in docTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </div>
    </el-card>

    <el-card>
      <el-table :data="list" v-loading="loading" stripe border size="small">
        <el-table-column prop="created_at" label="时间" width="160" sortable />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" min-width="280" show-overflow-tooltip />
        <el-table-column label="收件人" width="130">
          <template #default="{ row }">
            {{ row.user_name }}<el-tag v-if="row.role_name" size="small" style="margin-left:4px">{{ row.role_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提醒点" width="140">
          <template #default="{ row }">
            <span>{{ pointName(row.point_code) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="doc_no" label="单据号" width="140" />
        <el-table-column label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.read_status ? 'info' : 'danger'" size="small">{{ row.read_status ? '已读' : '未读' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div style="display: flex; justify-content: flex-end; margin-top: 12px">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
                       layout="total, prev, pager, next" :page-sizes="[20, 50, 100]" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { systemConfigApi, authApi, notificationApi } from '../../api/foundation'

const POINT_OPTIONS = [
  { code: 'SO_APPROVED', name: '销售订单审核' },
  { code: 'MO_PLANNED', name: '排产备料' },
  { code: 'MO_OUTSOURCED', name: '生产转外购' },
  { code: 'AR_CREATED', name: '应收生成' },
  { code: 'AR_DUE', name: '应收到期预警' },
  { code: 'AP_DUE', name: '应付到期预警' },
]
const DOC_TYPES = [
  { value: 'so_order', label: '销售订单' },
  { value: 'mo_production', label: '生产订单' },
  { value: 'ar_account', label: '应收账款' },
  { value: 'ap_account', label: '应付账款' },
]

const list = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const roleList = ref([])
const userList = ref([])
const filters = reactive({ role_code: null, user_id: null, point_code: null, doc_type: null })
const pointOptions = POINT_OPTIONS
const docTypes = DOC_TYPES

function pointName(code) {
  const p = POINT_OPTIONS.find(x => x.code === code)
  return p ? p.name : (code || '')
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.role_code) params.role_code = filters.role_code
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.point_code) params.point_code = filters.point_code
    if (filters.doc_type) params.doc_type = filters.doc_type
    const data = await notificationApi.adminQuery(params)
    list.value = data ? (data.items || []) : []
    total.value = data ? (data.total || 0) : 0
  } catch { list.value = [] }
  loading.value = false
}

function resetFilter() {
  Object.assign(filters, { role_code: null, user_id: null, point_code: null, doc_type: null })
  page.value = 1
  fetchData()
}

async function fetchMeta() {
  try { roleList.value = await authApi.listRoles() || [] } catch {}
  try { userList.value = await authApi.listUsers() || [] } catch {}
}

onMounted(() => { fetchMeta(); fetchData() })
</script>
