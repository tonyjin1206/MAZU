import { ref, computed } from 'vue'

/**
 * 表格列显隐控制（右键表头弹菜单，勾选显示/取消隐藏）
 *
 * 用法：
 *   const { visibleColumns, allColumns, toggleColumn, initColumnVisible } = useColumnCustomize(columns, STORAGE_KEY)
 *   模板表格 v-for="col in visibleColumns"
 *   表头包 el-dropdown trigger="contextmenu"，下拉里渲染 allColumns 的 checkbox：
 *     <template #header>
 *       <el-dropdown trigger="contextmenu" :hide-on-click="false" @contextmenu.prevent>
 *         <span class="col-header-wrap">⠿ {{ col.label }}</span>
 *         <template #dropdown>
 *           <el-dropdown-menu>
 *             <el-dropdown-item v-for="c in allColumns" :key="c.prop">
 *               <el-checkbox :model-value="c.visible !== false" @change="toggleColumn(c)">{{ c.label }}</el-checkbox>
 *             </el-dropdown-item>
 *           </el-dropdown-menu>
 *         </template>
 *       </el-dropdown>
 *     </template>
 *   onMounted 或数据加载后调用 initColumnVisible() 恢复记忆（每人浏览器 localStorage 独立，互不影响）
 *
 * 说明：只控制显示/隐藏，不影响后台数据；隐藏的列不参与渲染，宽度自适应依旧生效。
 */
export function useColumnCustomize(columnsRef, storageKey) {
  const allColumns = ref([])
  const visibleColumns = computed(() => allColumns.value.filter(c => c.visible !== false))

  function initColumnVisible() {
    allColumns.value = (columnsRef.value || []).map(c => ({ ...c, visible: c.visible !== false }))
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey + '_vis') || '{}')
      for (const c of allColumns.value) {
        if (saved[c.prop] !== undefined) c.visible = saved[c.prop] !== false
      }
    } catch { /* ignore */ }
  }

  function toggleColumn(col) {
    col.visible = col.visible !== false ? false : true
    try {
      const saved = {}
      for (const c of allColumns.value) saved[c.prop] = c.visible !== false
      localStorage.setItem(storageKey + '_vis', JSON.stringify(saved))
    } catch { /* ignore */ }
  }

  return { visibleColumns, allColumns, initColumnVisible, toggleColumn }
}
