import { ref, nextTick, onBeforeUnmount } from 'vue'
import Sortable from 'sortablejs'

/**
 * 通用列管理 composable（表头拖拽 + 列设置弹窗）
 * 
 * 用法：
 *   const { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings } = useColumnDrag(defaultColumns, 'my_storage_key')
 * 
 *   模板中：
 *   <el-table :key="columnVersion" ...>
 *     <el-table-column v-for="col in columns" :key="col.prop" ...>
 *       <template #header>
 *         <span class="col-header-wrap">
 *           <span class="col-drag-handle" title="拖动调整列顺序">⠿</span>
 *           {{ col.label }}
 *         </span>
 *       </template>
 *     </el-table-column>
 *   </el-table>
 * 
 *   表格上方加"列设置"按钮 → openColumnSettings()
 *   弹窗：<ColumnSettingsDialog v-model:visible="settingsVisible" :columns="settingsList" @confirm="confirmSettings" @reset="resetSettings" />
 *   右键菜单"列设置..."→ openColumnSettings()
 *   fetchData 后调用 nextTick(initColumnDrag)
 * 
 * @param {Array} defaultColumns  默认列定义 [{ prop, label, width?, minWidth?, sortable?, align?, ... }]
 * @param {string} storageKey     localStorage 存储键
 * @param {string} selector       表头选择器（默认第一个表格；多表格页面传 '.my-class .el-table__header-wrapper thead tr'）
 */
export function useColumnDrag(defaultColumns, storageKey, selector = '.el-table__header-wrapper thead tr') {
  function loadColumnOrder() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '[]')
      if (saved.length) {
        const savedSet = new Set(saved)
        const others = defaultColumns.filter(c => !savedSet.has(c.prop))
        return [...saved.map(prop => defaultColumns.find(c => c.prop === prop)).filter(Boolean), ...others]
      }
    } catch (e) { /* 忽略损坏的存储 */ }
    return [...defaultColumns]
  }

  const columns = ref(loadColumnOrder())
  const columnVersion = ref(0)
  let sortableInstance = null
  let dragRetryTimer = null

  // fixed 列/gutter 在 thead 里占 index，但不在 columns 逻辑顺序里 → 拖拽 index 需要换算
  function toLogicalIndex(thIndex) {
    const thead = document.querySelector(selector)
    if (!thead || !thead.children.length) return thIndex
    let logical = 0
    for (let i = 0; i < thIndex; i++) {
      const cls = thead.children[i].classList
      if (cls.contains('el-table-fixed-column--right') || cls.contains('gutter')) continue
      logical++
    }
    return logical
  }

  function initColumnDrag() {
    clearTimeout(dragRetryTimer)
    const thead = document.querySelector(selector)
    if (!thead) {
      dragRetryTimer = setTimeout(initColumnDrag, 300)
      return
    }
    destroyColumnDrag()
    sortableInstance = Sortable.create(thead, {
      animation: 200,
      direction: 'horizontal',
      handle: '.col-drag-handle',
      forceFallback: true,
      ghostClass: 'sortable-ghost',
      dragClass: 'sortable-drag',
      swapThreshold: 0.65,
      filter: (evt, target) => {
        const cls = target ? target.classList : null
        return cls && (cls.contains('el-table-fixed-column--right') || cls.contains('gutter'))
      },
      onEnd: (evt) => {
        const oldIndex = toLogicalIndex(evt.oldIndex)
        const newIndex = toLogicalIndex(evt.newIndex)
        if (oldIndex === newIndex) return
        const cols = [...columns.value]
        const [moved] = cols.splice(oldIndex, 1)
        cols.splice(newIndex, 0, moved)
        columns.value = cols
        localStorage.setItem(storageKey, JSON.stringify(cols.map(c => c.prop)))
        columnVersion.value++
        nextTick(initColumnDrag)
      },
    })
  }

  function destroyColumnDrag() {
    sortableInstance?.destroy()
    sortableInstance = null
    clearTimeout(dragRetryTimer)
  }

  onBeforeUnmount(destroyColumnDrag)

  // ===== 列设置弹窗（显隐 checkbox + ↑↓ 移动 + 恢复默认）=====
  const settingsVisible = ref(false)
  const settingsList = ref([])
  // 页面侧传入当前显隐状态（来自 useColumnCustomize），合并进列表
  function openColumnSettings(visibleMap = {}) {
    settingsList.value = columns.value.map(c => ({
      ...c,
      visible: visibleMap[c.prop] !== undefined ? visibleMap[c.prop] : c.visible !== false,
    }))
    settingsVisible.value = true
  }

  function confirmSettings() {
    const list = settingsList.value
    columns.value = list.map(c => ({ ...c }))
    localStorage.setItem(storageKey, JSON.stringify(list.map(c => c.prop)))
    // 显隐状态写回（由页面侧接收并应用/存储）
    const vis = {}
    for (const c of list) vis[c.prop] = c.visible !== false
    localStorage.setItem(storageKey + '_vis', JSON.stringify(vis))
    columnVersion.value++
    settingsVisible.value = false
  }

  function resetSettings() {
    settingsList.value = defaultColumns.map(c => ({ ...c, visible: true }))
  }

  return { columns, columnVersion, initColumnDrag, settingsVisible, settingsList, openColumnSettings, confirmSettings, resetSettings }
}
