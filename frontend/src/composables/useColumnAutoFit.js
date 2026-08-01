import { nextTick } from 'vue'

// canvas 文本测量（共享实例，避免重复创建）
let _canvas = null
function textWidth(text, bold = false) {
  if (!_canvas) _canvas = document.createElement('canvas')
  const ctx = _canvas.getContext('2d')
  ctx.font = (bold ? 'bold ' : '') + '12px -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif'
  return ctx.measureText(String(text ?? '')).width
}

function fmtMoney(v) {
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (n === null || n === undefined || isNaN(n)) return '¥0.00'
  return '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/**
 * 表格列宽按内容自适应 composable
 *
 * 用法：
 *   const { fitTable } = useColumnAutoFit()
 *   数据加载后：nextTick(() => fitTable(tableRef.value, columns, dataList))
 *
 * 原理：用 canvas 测量表头文字和数据单元格文字的真实宽度（不受当前列宽拉伸影响），
 * 加上固定开销（cell padding、排序箭头、tag 等），得到每列最小舒适宽度。
 * 列定义里可加 fmt 标记影响宽度估算：
 *   fmt: 'money' 金额（含 ¥ 前缀与千分位）
 *   fmt: 'qty'   数量
 *   fmt: 'tag'   状态标签（含标签内边距）
 * 默认按内容测量（不撑满屏）：所有列加起来不足表格宽度时右侧留白，
 * 内容放不下时才出现横向滚动；如需补足一屏可传 options.fitToContainer=true。
 *
 * @param {Ref} el        el-table 的 ref（组件实例或 DOM 均可，自动取 $el）
 * @param {Ref<Array>} columns  列配置 ref（[{ prop, label, width, fmt?, ... }]）
 * @param {Ref<Array>|Array} data  表格数据（用于测量单元格文本）
 * @param {Object}      options  { padding: 列宽余量(px), minWidth: 最小列宽(px), fitToContainer: 不足一屏时补足 }
 */
export function useColumnAutoFit() {
  function fitTable(el, columns, data, options = {}) {
    const { padding = 12, minWidth = 80, fitToContainer = false } = options
    nextTick(() => {
      const root = el?.$el || el
      if (!root || !columns?.value?.length) return
      const rows = data?.value || data || []
      const container = root.querySelector('.el-table__header-wrapper') || root
      const containerW = container.clientWidth
      const cols = columns.value.filter(c => !c.fixed)
      // 固定开销：单元格左右内边距 20 + 排序箭头 26 + 拖拽手柄 18 + 余量 padding
      const CELL_PAD = 20
      const CARET = 26
      const HANDLE = 18
      cols.forEach(col => {
        let maxW = textWidth(col.label, true) + CELL_PAD + CARET + HANDLE
        rows.forEach(row => {
          let v = null
          // 多字段回退：measureKeys 取所有非空值拼接测量（如 物料名 + 编码tag）
          if (col.measureKeys) {
            const parts = []
            for (const k of col.measureKeys) {
              const kv = row[k]
              if (kv !== null && kv !== undefined && kv !== '') parts.push(String(kv))
            }
            v = parts.join(' ')
          } else {
            v = row[col.prop]
          }
          let text = String(v ?? '')
          if (col.fmt === 'money') text = fmtMoney(v)
          else if (col.fmt === 'qty') text = String(v ?? '')
          let w = textWidth(text) + CELL_PAD + (col.fmt === 'tag' ? 24 : 6)
          if (w > maxW) maxW = w
        })
        col.width = Math.max(minWidth, maxW + padding)
        col.minWidth = undefined  // 以 fit 计算值为准，不再被原 minWidth 撑宽
      })
      // 一屏适配：总宽不足可用宽度时，按比例补足（需扣除 fixed 列占用的宽度）
      if (fitToContainer) {
        const fixedTh = root.querySelector('th.el-table-fixed-column--right')
        const fixedW = fixedTh ? fixedTh.offsetWidth : 0
        const availableW = containerW - fixedW
        const sumW = cols.reduce((s, c) => s + (c.width || 0), 0)
        if (sumW > 0 && sumW < availableW) {
          const diff = availableW - sumW
          cols.forEach(c => {
            c.width = Math.round(c.width + diff * (c.width / sumW))
          })
        }
      }
      // 🔴 直接更新 el-table 内部列宽（store 列 config 是响应式，改 width 触发重算）
      const store = el?.store
      if (store && store.states?.columns?.value?.length) {
        store.states.columns.value.forEach(sc => {
          const c = cols.find(x => x.prop === (sc.rawColumnKey || sc.property))
          if (c && c.width) sc.width = c.width
        })
      }
      requestAnimationFrame(() => el?.doLayout?.())
    })
  }
  return { fitTable }
}
