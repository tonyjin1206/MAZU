import { ref, nextTick, onBeforeUnmount } from 'vue'
import Sortable from 'sortablejs'

/**
 * 通用列拖拽 composable
 * 
 * 用法：
 *   const { columns, columnVersion, initColumnDrag } = useColumnDrag(defaultColumns, 'my_storage_key')
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

  function initColumnDrag() {
    clearTimeout(dragRetryTimer)
    const thead = document.querySelector(selector)
    if (!thead) {
      dragRetryTimer = setTimeout(initColumnDrag, 300)
      return
    }
    destroyColumnDrag()
    sortableInstance = Sortable.create(thead, {
      animation: 150,
      handle: '.col-drag-handle',
      forceFallback: true,
      ghostClass: 'sortable-ghost',
      dragClass: 'sortable-drag',
      filter: (evt, target) => {
        const cls = target ? target.classList : null
        return cls && (cls.contains('el-table-fixed-column--right') || cls.contains('gutter'))
      },
      onEnd: (evt) => {
        const { oldIndex, newIndex } = evt
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

  return { columns, columnVersion, initColumnDrag }
}
