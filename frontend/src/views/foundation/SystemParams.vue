<template>
  <div>
    <el-card style="margin-bottom: 12px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="font-weight: 600">参数设置</div>
          <el-button type="primary" @click="openCreate">{{ activeGroup === 'process' ? '新增工序' : (activeGroup === 'material_category' ? '新增大类' : (activeGroup === 'warehouse' ? '新增仓库' : '新增参数')) }}</el-button>
        </div>
      </template>
      <el-tabs v-model="activeGroup" @tab-change="onTabChange">
        <el-tab-pane v-for="g in groupOptions" :key="g" :label="groupLabel(g)" :name="g" />
      </el-tabs>
      <div style="color: #909399; font-size: 12px; margin-bottom: 8px">
        在这里维护好选项后，新增供应商/材料/收付款单时，下拉框会自动出现这些选项。停用的选项不再出现在下拉里（历史数据不受影响）。
      </div>
    </el-card>

    <el-card>
      <!-- 材料类别：大类 + 小类 两级树 -->
            <div style="display: flex; justify-content: flex-end; margin-bottom: 4px">
        <el-button size="small" @click="openColumnSettings">⚙ 列设置</el-button>
      </div>
<el-table ref="tableRef"
        v-if="activeGroup === 'material_category'"
        :data="materialTree" row-key="key" default-expand-all
        v-loading="loading" stripe border size="small" style="width: 100%"
      >
        <el-table-column label="大类 / 小类" min-width="220">
          <template #default="{ row }">
            <span v-if="row.is_sub" style="color: #606266">{{ row.label }}</span>
            <span v-else style="font-weight: 600">{{ row.label }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="param_key" label="编号" width="90" align="center" sortable />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">{{ row.is_active === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="290" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_sub" link type="primary" size="small" @click="openCreateSub(row)">+ 新增小类</el-button>
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            <el-button link :type="row.is_active === 1 ? 'warning' : 'success'" size="small" @click="toggleActiveButton(row)">{{ row.is_active === 1 ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 仓库：预编号维护（成品入库收货时从这里选） -->
      <el-table
        v-else-if="activeGroup === 'warehouse'"
        :data="warehouseList" v-loading="loading" stripe border size="small" style="width: 100%"
      >
        <el-table-column prop="code" label="编码" width="100" align="center" sortable />
        <el-table-column prop="name" label="仓库名称" min-width="160" sortable />
        <el-table-column prop="wh_type" label="类型" width="120" align="center" sortable>
          <template #default="{ row }">
            <el-tag :type="row.wh_type === '成品仓库' ? 'primary' : 'warning'" size="small">{{ row.wh_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">{{ row.is_active === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openWarehouseEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleWarehouseDelete(row)">删除</el-button>
            <el-button link :type="row.is_active === 1 ? 'warning' : 'success'" size="small" @click="toggleWarehouse(row)">{{ row.is_active === 1 ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 加工工序：生产加工工序维护（坯布/染色/底布复合等） -->
      <el-table
        v-else-if="activeGroup === 'process'"
        :data="processList" v-loading="loading" stripe border size="small" style="width: 100%"
      >
        <el-table-column prop="code" label="编码" width="110" align="center" sortable />
        <el-table-column prop="name" label="工序名称" min-width="160" sortable />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">{{ row.is_active === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openProcessEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleProcessDelete(row)">删除</el-button>
            <el-button link :type="row.is_active === 1 ? 'warning' : 'success'" size="small" @click="toggleProcess(row)">{{ row.is_active === 1 ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 其他参数组：通用表格（可拖拽列） -->
      <el-table ref="tableRef" v-else :key="columnVersion" :data="list" v-loading="loading" stripe border size="small" style="width: 100%">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth" :sortable="col.sortable" :align="col.align">
          <template #header>
            <el-dropdown trigger="contextmenu" :hide-on-click="false">
              <span class="col-header-wrap">
                <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
                {{ col.label }}
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="c in allColumns" :key="c.prop">
                    <el-checkbox :model-value="c.visible !== false" @change="toggleColumn(c)">{{ c.label }}</el-checkbox>
                  </el-dropdown-item>
                  <el-dropdown-item @click.stop="openColumnSettings" style="color: #409eff">列设置...</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">{{ row.is_active === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            <el-button link :type="row.is_active === 1 ? 'warning' : 'success'" size="small" @click="toggleActiveButton(row)">{{ row.is_active === 1 ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editId ? '编辑参数' : (activeGroup === 'material_category' ? (isSubForm ? '新增小类' : '新增大类') : '新增参数')" width="480px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item v-if="!inMaterialCategory" label="参数组" prop="group_name">
          <el-select v-model="form.group_name" style="width: 100%" :disabled="!!editId">
            <el-option v-for="g in groupOptions" :key="g" :label="groupLabel(g)" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isSubForm" label="所属大类" prop="parent_key">
          <el-select v-model="form.parent_key" style="width: 100%" placeholder="选择该小类属于哪个大类" :disabled="!!editId">
            <el-option v-for="o in mainCategoryOptions" :key="o.key" :label="o.label" :value="o.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称" prop="param_label">
          <el-input v-model="form.param_label" :placeholder="inMaterialCategory ? (isSubForm ? '如：面布、底布、拉链' : '如：主材、辅材、包装材料') : '下拉框里看到的文字'" />
        </el-form-item>
        <el-form-item label="参数值">
          <el-input :model-value="form.param_key" disabled style="width: 150px">
            <template #append>
              <el-button v-if="!editId" style="padding: 0 10px" @click="regenerateKey">重编号</el-button>
            </template>
          </el-input>
          <div style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px">
            系统自动编号（01、02、03…），不用手动填。下拉选中后存入数据的是显示名称，编号仅作内部标识。
          </div>
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="选填，备注用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑仓库弹窗 -->
    <el-dialog v-model="warehouseDialogVisible" :title="warehouseEditId ? '编辑仓库' : '新增仓库'" width="420px" destroy-on-close>
      <el-form :model="warehouseForm" label-width="80px" ref="warehouseFormRef" :rules="warehouseRules">
        <el-form-item label="仓库名称" prop="name">
          <el-input v-model="warehouseForm.name" placeholder="如：原辅料仓库、成品仓库" />
        </el-form-item>
        <el-form-item label="类型" prop="wh_type">
          <el-select v-model="warehouseForm.wh_type" style="width: 100%">
            <el-option label="原辅料仓库" value="原辅料仓库" />
            <el-option label="成品仓库" value="成品仓库" />
          </el-select>
        </el-form-item>
        <div style="color: #909399; font-size: 12px; line-height: 1.5">编码自动生成（WH001、WH002…），成品入库收货时从仓库列表里选择。</div>
      </el-form>
      <template #footer>
        <el-button @click="warehouseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleWarehouseSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑工序弹窗 -->
    <el-dialog v-model="processDialogVisible" :title="processEditId ? '编辑工序' : '新增工序'" width="420px" destroy-on-close>
      <el-form :model="processForm" label-width="110px" ref="processFormRef" :rules="processRules">
        <el-form-item label="工序名称" prop="name">
          <el-input v-model="processForm.name" placeholder="如：坯布、染色、底布复合" />
        </el-form-item>
        <div style="color: #909399; font-size: 12px; line-height: 1.5">编码自动生成（GX000001、GX000002…），自产加工时从工序列表里选择。</div>
      </el-form>
      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleProcessSave">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 列排序弹窗 -->
    <ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useColumnDrag } from '../../composables/useColumnDrag'
import { useColumnAutoFit } from '../../composables/useColumnAutoFit'
import { useColumnCustomize } from '../../composables/useColumnCustomize'
import ColumnSettingsDialog from '../../components/ColumnSettingsDialog.vue'
import request from '../../api/request'; import { foundationApi } from '../../api/foundation'

// ===== 列配置（可拖拽排序）=====
const STORAGE_KEY = 'mazu_system_param_columns'
const defaultColumns = [
  { prop: 'sort_order', label: '排序', width: 70, align: 'center' , sortable: true },
  { prop: 'param_label', label: '显示名称', minWidth: 160 , sortable: true },
  { prop: 'param_key', label: '参数值', minWidth: 140 , sortable: true },
  { prop: 'remark', label: '说明', minWidth: 180 , sortable: true },
]
const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, STORAGE_KEY)
const { fitTable } = useColumnAutoFit()
const tableRef = ref(null)
const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)

const GROUP_LABELS = {
  supplier_type: '供应商类型',
  material_category: '材料类别',
  unit: '计量单位',
  payment_method: '付款方式',
  country: '国家',
  warehouse: '仓库',
  process: '加工工序',
}

function groupLabel(g) { return GROUP_LABELS[g] || g }

const groups = ref([])
const activeGroup = ref('')
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref(null)
const formRef = ref(null)

const form = reactive({ group_name: '', param_label: '', param_key: '', parent_key: '', sort_order: 0, remark: '' })
const rules = {
  group_name: [{ required: true, message: '请选择参数组', trigger: 'change' }],
  param_label: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  param_key: [{ required: true, message: '请输入参数值', trigger: 'blur' }],
  parent_key: [{ required: true, message: '请选择所属大类', trigger: 'change' }],
}

// 这两个组并入「材料类别」tab 内管理，不单独显示
const HIDDEN_GROUPS = ['material_main_category', 'material_sub_category']

const groupOptions = computed(() => {
  const all = [...new Set([...groups.value, ...Object.keys(GROUP_LABELS)])]
  return all.filter(g => !HIDDEN_GROUPS.includes(g))
})

const inMaterialCategory = computed(() => activeGroup.value === 'material_category')
const isSubForm = computed(() => form.group_name === 'material_sub_category')
const mainCategoryOptions = ref([])

// ===== 材料类别树（大类 + 小类）=====
const materialTree = ref([])

async function loadMaterialTree() {
  loading.value = true
  try {
    const [mainRes, subRes] = await Promise.all([
      foundationApi.params.getGroup('material_main_category').catch(() => ({ items: [] })),
      foundationApi.params.getGroup('material_sub_category').catch(() => ({ items: [] })),
    ])
    const mains = mainRes.items || []
    const subs = subRes.items || []
    materialTree.value = mains.map(m => ({
      key: m.param_key, label: m.param_label, param_key: m.param_key, id: m.id,
      sort_order: m.sort_order, remark: m.remark || '',
      is_active: m.is_active, is_sub: false,
      children: subs.filter(s => s.parent_key === m.param_key).map(s => ({
        key: s.param_key, label: s.param_label, param_key: s.param_key,
        parent_key: s.parent_key, is_active: s.is_active, is_sub: true, id: s.id,
        sort_order: s.sort_order, remark: s.remark || '',
      })),
    }))
  } catch (e) { materialTree.value = [] } finally { loading.value = false }
}

async function loadGroup() {
  if (!activeGroup.value) return
  if (activeGroup.value === 'material_category') { loadMaterialTree(); return }
  if (activeGroup.value === 'warehouse') { loadWarehouses(); return }
  if (activeGroup.value === 'process') { loadProcesses(); return }
  loading.value = true
  try {
    const res = await foundationApi.params.getGroup(activeGroup.value)
    list.value = res.items || []
  } catch (e) { list.value = [] } finally { loading.value = false; nextTick(() => { initColumnDrag(); fitTable(tableRef.value, columns, list) }) }
}

// ===== 仓库（参数设置内维护，编码自动 WH+流水）=====
const warehouseList = ref([])
const warehouseDialogVisible = ref(false)
const warehouseEditId = ref(null)
const warehouseFormRef = ref(null)
const warehouseForm = reactive({ code: '', name: '', wh_type: '原辅料仓库' })
const warehouseRules = { name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }] }

async function loadWarehouses() {
  loading.value = true
  try {
    const res = await foundationApi.warehouses.list({ page: 1, page_size: 100 })
    warehouseList.value = res.items || []
  } catch (e) { warehouseList.value = [] } finally { loading.value = false }
}

function nextWarehouseCode() {
  let max = 0
  for (const w of warehouseList.value) {
    const m = String(w.code || '').match(/^WH(\d+)$/)
    if (m) max = Math.max(max, parseInt(m[1], 10))
  }
  return 'WH' + String(max + 1).padStart(3, '0')
}

function openWarehouseCreate() {
  warehouseEditId.value = null
  Object.assign(warehouseForm, { code: '', name: '', wh_type: '原辅料仓库' })
  warehouseDialogVisible.value = true
}

function openWarehouseEdit(row) {
  warehouseEditId.value = row.id
  Object.assign(warehouseForm, { code: row.code || '', name: row.name, wh_type: row.wh_type || '原辅料仓库' })
  warehouseDialogVisible.value = true
}

async function handleWarehouseSave() {
  const valid = await warehouseFormRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (warehouseEditId.value) {
      await foundationApi.warehouses.update(warehouseEditId.value, { ...warehouseForm })
      ElMessage.success('已保存')
    } else {
      await foundationApi.warehouses.create({ ...warehouseForm, code: nextWarehouseCode() })
      ElMessage.success('已新增')
    }
    warehouseDialogVisible.value = false
    loadWarehouses()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

async function toggleWarehouse(row) {
  const next = row.is_active === 1 ? 0 : 1
  try {
    await foundationApi.warehouses.update(row.id, { is_active: next })
    row.is_active = next
    ElMessage.success(next ? '已启用' : '已停用')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleWarehouseDelete(row) {
  await ElMessageBox.confirm(`确定删除仓库「${row.name}」？<br><span style="color:#e6a23c;font-size:12px">有单据使用的仓库不能删除，只能停用。</span>`, '提示', { type: 'warning', dangerouslyUseHTMLString: true })
  try {
    await foundationApi.warehouses.remove(row.id)
    ElMessage.success('已删除')
    loadWarehouses()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// ===== 加工工序（参数设置内维护，编码自动 GX+6位流水）=====
const processList = ref([])
const processDialogVisible = ref(false)
const processEditId = ref(null)
const processFormRef = ref(null)
const processForm = reactive({ code: '', name: '' })
const processRules = { name: [{ required: true, message: '请输入工序名称', trigger: 'blur' }] }

async function loadProcesses() {
  loading.value = true
  try {
    const res = await foundationApi.processes.list({ page: 1, page_size: 100 })
    processList.value = res.items || []
  } catch (e) { processList.value = [] } finally { loading.value = false }
}

function nextProcessCode() {
  let max = 0
  for (const p of processList.value) {
    const m = String(p.code || '').match(/^GX(\d+)$/)
    if (m) max = Math.max(max, parseInt(m[1], 10))
  }
  return 'GX' + String(max + 1).padStart(6, '0')
}

function openProcessCreate() {
  processEditId.value = null
  Object.assign(processForm, { code: '', name: '' })
  processDialogVisible.value = true
}

function openProcessEdit(row) {
  processEditId.value = row.id
  Object.assign(processForm, { code: row.code || '', name: row.name })
  processDialogVisible.value = true
}

async function handleProcessSave() {
  const valid = await processFormRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload = { ...processForm }
    if (processEditId.value) {
      await foundationApi.processes.update(processEditId.value, payload)
      ElMessage.success('已保存')
    } else {
      await foundationApi.processes.create({ ...payload, code: nextProcessCode() })
      ElMessage.success('已新增')
    }
    processDialogVisible.value = false
    loadProcesses()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

async function toggleProcess(row) {
  const next = row.is_active === 1 ? 0 : 1
  try {
    await foundationApi.processes.update(row.id, { is_active: next })
    row.is_active = next
    ElMessage.success(next ? '已启用' : '已停用')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleProcessDelete(row) {
  await ElMessageBox.confirm(`确定删除工序「${row.name}」？<br><span style="color:#e6a23c;font-size:12px">有产品工艺引用该工序时不能删除，只能停用。</span>`, '提示', { type: 'warning', dangerouslyUseHTMLString: true })
  try {
    await foundationApi.processes.remove(row.id)
    ElMessage.success('已删除')
    loadProcesses()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function loadGroups() {
  try { groups.value = await foundationApi.params.groups() || [] } catch (e) { groups.value = [] }
  if (!activeGroup.value && groups.value.length) {
    activeGroup.value = groups.value[0]
    loadGroup()
  }
}

async function loadMainCategories() {
  try { mainCategoryOptions.value = await foundationApi.params.options({ group: 'material_main_category' }) || [] } catch (e) { mainCategoryOptions.value = [] }
}

async function onTabChange() {
  loadGroup()
}

function nextParamKey() {
  // 组内下一个编号：取现有两位数字编号最大值 +1
  let max = 0
  const src = activeGroup.value === 'material_category' ? materialTree.value : list.value
  for (const r of src) {
    const n = parseInt(r.param_key, 10)
    if (!isNaN(n) && n > max) max = n
  }
  return String(max + 1).padStart(2, '0')
}

function regenerateKey() {
  form.param_key = nextParamKey()
}

function openCreate() {
  editId.value = null
  if (activeGroup.value === 'warehouse') { openWarehouseCreate(); return }
  if (activeGroup.value === 'process') { openProcessCreate(); return }
  if (activeGroup.value === 'material_category') {
    Object.assign(form, { group_name: 'material_main_category', param_label: '', param_key: nextParamKey(), parent_key: '', sort_order: (materialTree.value.length || 0) + 1, remark: '' })
    loadMainCategories()
  } else {
    Object.assign(form, { group_name: activeGroup.value || groups.value[0] || '', param_label: '', param_key: nextParamKey(), parent_key: '', sort_order: (list.value.length || 0) + 1, remark: '' })
  }
  dialogVisible.value = true
}

function openCreateSub(mainRow) {
  editId.value = null
  Object.assign(form, {
    group_name: 'material_sub_category',
    param_label: '',
    param_key: nextSubKey(),
    parent_key: mainRow.param_key,
    sort_order: (mainRow.children?.length || 0) + 1,
    remark: '',
  })
  dialogVisible.value = true
}

function nextSubKey() {
  // 小类编号全组唯一：取所有小类里最大编号 +1（避免与已有小类冲突）
  let max = 0
  for (const m of materialTree.value) {
    for (const s of m.children || []) {
      const n = parseInt(s.param_key, 10)
      if (!isNaN(n) && n > max) max = n
    }
  }
  return String(max + 1).padStart(2, '0')
}

function openEdit(row) {
  editId.value = row.id
  if (activeGroup.value === 'material_category') {
    Object.assign(form, {
      group_name: row.is_sub ? 'material_sub_category' : 'material_main_category',
      param_label: row.label, param_key: row.param_key, parent_key: row.parent_key || '',
      sort_order: row.sort_order || 0, remark: row.remark || '',
    })
    if (row.is_sub) loadMainCategories()
  } else {
    Object.assign(form, { group_name: row.group_name, param_label: row.param_label, param_key: row.param_key, parent_key: row.parent_key || '', sort_order: row.sort_order, remark: row.remark || '' })
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editId.value) {
      await foundationApi.params.update(editId.value, { ...form })
      ElMessage.success('已保存')
    } else {
      await foundationApi.params.create({ ...form })
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    loadGroup()
    loadGroups()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

async function toggleActive(row, v) {
  try {
    await foundationApi.params.update(row.id, { is_active: v ? 1 : 0 })
    row.is_active = v ? 1 : 0
    ElMessage.success(v ? '已启用' : '已停用')
  } catch (e) { }
}

function toggleActiveButton(row) {
  toggleActive(row, row.is_active === 1 ? 0 : 1)
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除「${row.label || row.param_label}」？<br><span style="color:#e6a23c;font-size:12px">注意：有业务数据正在使用的参数不能删除，只能停用（停用后下拉不再出现，历史数据不受影响）。</span>`, '提示', { type: 'warning', dangerouslyUseHTMLString: true })
  try {
    await foundationApi.params.remove(row.id)
    ElMessage.success('已删除')
    loadGroup()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => { initColumnVisible(); loadGroups(); loadMainCategories() })

// 列顺序变化时重同步（表头拖拽 + 弹窗排序都会触发）
watch(columnVersion, () => {
  nextTick(() => { initColumnVisible(); initColumnDrag() })
})
</script>
