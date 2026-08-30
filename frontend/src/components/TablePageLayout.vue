<!-- 单页列表布局（设计规范壳）：
  占满视窗 + 卡片 body flex + 表体滚动(表头/合计冻结) + 分页固定底部 -->
<template>
  <div style="height: calc(100vh - 92px); display: flex; flex-direction: column; overflow: hidden">
    <!-- 搜索区（可选，flex:none） -->
    <slot name="search" />
    <!-- 列表卡 -->
    <el-card ref="cardRef" :body-style="cardBodyStyle" style="flex: 1; min-height: 0; display: flex; flexDirection: column; overflow: hidden">
      <slot name="header" />
      <div style="flex: 1; min-height: 0; display: flex; flexDirection: column">
        <!-- 表格：height 由组件计算（=body 高 − 分页高），表体内部滚动 -->
        <slot :height="tableHeight" :cardRef="cardRef" />
      </div>
      <!-- 分页（可选，需自行加 flex:none） -->
      <slot name="footer" />
    </el-card>
    <!-- 弹窗/附属内容（不占布局流） -->
    <slot name="dialog" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useTablePageLayout } from '../composables/useTablePageLayout'

const { calcHeight, cardBodyStyle } = useTablePageLayout()
const cardRef = ref(null)
const localHeight = ref(400)

function recalc() {
  // 用组件自身 cardRef 计算表格高度
  localHeight.value = (card => {
    if (!card) return 400
    const el = card.$el || card
    const body = el.querySelector('.el-card__body')
    const bodyRect = body ? body.getBoundingClientRect() : el.getBoundingClientRect()
    const pagEl = el.querySelector('.el-pagination')
    const pagH = pagEl ? pagEl.getBoundingClientRect().height : 0
    return Math.max(140, Math.round(bodyRect.height - pagH))
  })(cardRef.value)
}

onMounted(() => { nextTick(recalc); window.addEventListener('resize', recalc) })
onUnmounted(() => window.removeEventListener('resize', recalc))

const tableHeight = localHeight
</script>
