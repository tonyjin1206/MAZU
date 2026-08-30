/**
 * 统一列表页布局（前端设计规范单一来源）
 *
 * 规范：
 *  - 页面占满视窗（高度 calc(100vh - 92px)，不整页滚动）
 *  - 卡片 body 为 flex 容器，表格高度 = body 高度 − 分页高度（JS 动态计算）
 *  - 表体内部滚动、表头/合计行冻结、分页固定底部（flex:none）
 *  - 窗口 resize 自动重算
 *
 * 单页 / 上下页共用同一套高度算法，避免每页零散重复。
 */
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

export function useTablePageLayout() {
  const tableCardRef = ref(null)
  const tableHeight = ref(400)
  const cardBodyStyle = { flex: '1', minHeight: '0', display: 'flex', flexDirection: 'column', padding: '8px 16px' }

  function _calcCardTableHeight(card, pagElSelector) {
    if (!card) return 400
    const el = card.$el || card
    const body = el.querySelector('.el-card__body')
    const bodyRect = body ? body.getBoundingClientRect() : el.getBoundingClientRect()
    const pagEl = pagElSelector ? el.querySelector(pagElSelector) : null
    const pagH = pagEl ? pagEl.getBoundingClientRect().height : 0
    return Math.max(140, Math.round(bodyRect.height - pagH))
  }

  function calcHeight(cardRef = tableCardRef.value, pagSelector = '.el-pagination') {
    tableHeight.value = _calcCardTableHeight(cardRef, pagSelector)
  }

  // 任意卡片（如上下页的下卡）的高度 = body 实际高度（无分页）
  function calcCardBodyHeight(cardRef) {
    if (!cardRef) return 200
    const el = cardRef.$el || cardRef
    const body = el.querySelector('.el-card__body')
    return Math.max(120, Math.round((body || el).getBoundingClientRect().height - 16))
  }

  let resizeFn = null
  function bindResize(fn) {
    if (!fn) return
    if (resizeFn) window.removeEventListener('resize', resizeFn)
    resizeFn = fn
    window.addEventListener('resize', resizeFn)
  }

  onMounted(() => { nextTick(() => calcHeight()) })
  onUnmounted(() => { if (resizeFn) window.removeEventListener('resize', resizeFn) })

  return { tableCardRef, tableHeight, cardBodyStyle, calcHeight, calcCardBodyHeight, bindResize, _calcCardTableHeight }
}
