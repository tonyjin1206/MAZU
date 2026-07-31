<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="query" style="flex-wrap: nowrap">
        <el-form-item label="批次号">
          <el-input v-model="query.batch_no" placeholder="模糊搜索" clearable style="width: 160px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="物料名称">
          <el-input v-model="query.keyword" placeholder="名称/编码" clearable style="width: 160px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="query.warehouse_id" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="w in warehouseList" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="batchList" border stripe v-loading="loading" size="small" style="width: 100%">
        <el-table-column prop="batch_no" label="批次号" width="160" />
        <el-table-column label="物料/产品" min-width="140">
          <template #default="{ row }">{{ row.material_name || row.product_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="warehouse" label="仓库" width="120" />
        <el-table-column label="库存数量" width="100" align="right"><template #default="{ row }">{{ $fq(row.quantity) }}</template></el-table-column>
        <el-table-column prop="in_date" label="入库日期" width="110" />
        <el-table-column prop="source_type" label="来源" width="120">
          <template #default="{ row }">{{ { purchase: '采购入库', production: '完工入库', transfer: '调拨' }[row.source_type] || row.source_type }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }"><el-button type="primary" link @click="trace(row.batch_no)">追溯</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 追溯结果 -->
    <el-card v-if="traceData.length > 0" style="margin-top: 12px">
      <template #header><span>批次追溯 — {{ traceBatchNo }}<span v-if="traceItemName" style="color: #909399; margin-left: 8px">{{ traceItemName }}</span></span></template>
      <el-timeline>
        <el-timeline-item v-for="t in traceData" :key="t.id" :timestamp="t.date" :color="t.quantity > 0 ? '#67c23a' : '#e6a23c'">
          {{ { purchase_in: '采购入库', production_in: '完工入库', sale_out: '销售出库', outsource_out: '委外发料' }[t.type] || t.type }}
          数量: {{ t.quantity > 0 ? '+' : '' }}{{ t.quantity }}
          <span style="color: #909399; margin-left: 8px">单据: {{ t.doc_type }} {{ t.doc_no }}</span>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { productionApi } from '../../api/business'
import { foundationApi } from '../../api/foundation'

const warehouseList = ref([])
const batchList = ref([])
const traceData = ref([])
const traceBatchNo = ref('')
const traceItemName = ref('')
const loading = ref(false)
const query = reactive({ batch_no: '', keyword: '', warehouse_id: null })

onMounted(async () => {
  try { warehouseList.value = (await foundationApi.warehouses.list({ page_size: 200 })).items || [] } catch {}
  search()
})

async function search() {
  loading.value = true
  try {
    const params = {}
    if (query.batch_no) params.batch_no = query.batch_no
    if (query.keyword) params.keyword = query.keyword
    if (query.warehouse_id) params.warehouse_id = query.warehouse_id
    const res = await productionApi.batch.query(params)
    batchList.value = res.items || []
  } finally { loading.value = false }
}

async function trace(batchNo) {
  traceBatchNo.value = batchNo
  const res = await productionApi.batch.trace(batchNo)
  traceItemName.value = res.item_name || ''
  traceData.value = res.trace || []
}

function reset() {
  query.batch_no = ''; query.keyword = ''; query.warehouse_id = null
  search()
}
</script>
