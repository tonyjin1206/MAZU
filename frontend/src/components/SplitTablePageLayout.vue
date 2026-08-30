<!-- 上下两栏列表布局（设计规范壳）：
  上列表(可拖高度) + 分隔条 + 下明细；均表体滚动、表头/合计冻结、分页固定 -->
<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <slot name="search" />
    <!-- 上区 -->
    <el-card ref="topCardRef" :body-style="cardBodyStyle" :style="{ height: topHeight + 'px', flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <slot name="topHeader" />
      <slot name="top" :height="topTableHeight" :cardRef="topCardRef" />
    </el-card>
    <!-- 分隔条 -->
    <div class="split-bar" style="flex: none; height: 8px; cursor: row-resize; background: transparent; display: flex; align-items: center; justify-content: center; user-select: none" @mousedown="onSplitterDown">
      <span style="width: 60px; height: 4px; border-radius: 2px; background: #c0c4cc"></span>
    </div>
    <!-- 下区 -->
    <el-card ref="bottomCardRef" :body-style="cardBodyStyle" style="flex: 1; min-height: 140px; display: flex; flexDirection: column; overflow: hidden">
      <slot name="bottomHeader" />
      <slot name="bottom" :height="bottomTableHeight" :cardRef="bottomCardRef" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useTablePageLayout } from '../composables/useTablePageLayout'

const { _calcCardTableHeight, cardBodyStyle } = useTablePageLayout()
const topHeight = ref(parseInt(localStorage.getItem(localStorageKey()) || '400') || 400)
const topCardRef = ref(null)
const bottomCardRef = ref(null)
const topTableHeight = ref(200)
const bottomTableHeight = ref(200)

function localStorageKey() { return 'mts_split_page_' + (location.pathname.replace(/\//g, '_')) }

function recalc() {
  topTableHeight.value = _calcCardTableHeight(topCardRef.value, '.el-pagination')
  bottomTableHeight.value = Math.max(120, (() => {
    const el = bottomCardRef.value && (bottomCardRef.value.$el || bottomCardRef.value)
    if (!el) return 200
    const body = el.querySelector('.el-card__body')
    return Math.round((body || el).getBoundingClientRect().height - 16)
  })())
}

function onSplitterDown(e) {
  const startY = e.clientY
  const startH = topHeight.value
  const onMove = (ev) => {
    topHeight.value = Math.min(Math.max(startH + (ev.clientY - startY), 180), window.innerHeight - 360)
    localStorage.setItem(localStorageKey(), String(topHeight.value))
    nextTick(recalc)
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''; document.body.style.userSelect = ''
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.body.style.cursor = 'row-resize'; document.body.style.userSelect = 'none'
  e.preventDefault()
}

onMounted(() => { nextTick(recalc); window.addEventListener('resize', recalc) })
onUnmounted(() => window.removeEventListener('resize', recalc))
</script>
