<template>
  <el-dialog v-model="visible" title="列设置" width="420px" destroy-on-close>
    <div class="column-settings-list" style="max-height: 420px; overflow-y: auto">
      <div
        v-for="(col, i) in columns"
        :key="col.prop"
        class="col-setting-item"
        :class="{ selected: i === selectedIdx, dragging: i === dragIndex, 'drag-over': i === overIndex }"
        style="display: flex; align-items: center; gap: 8px; padding: 8px 10px; margin: 3px 0; border: 1px solid #e4e7ed; border-radius: 4px; background: #fff; cursor: default"
        @click="selectedIdx = i"
        @dragstart="onDragStart(i, $event)"
        @dragover.prevent="onDragOver(i)"
        @drop.prevent="onDrop(i)"
        @dragend="onDragEnd"
      >
        <span class="drag-handle" title="拖动调整顺序" draggable="true">⠿</span>
        <el-checkbox :model-value="col.visible !== false" @change="col.visible = col.visible !== false ? false : true" @click.stop />
        <span style="font-size: 13px; flex: 1">{{ col.label }}</span>
      </div>
    </div>
    <div style="color: #909399; font-size: 12px; margin-top: 6px">勾选 = 显示；拖动 ⠿ 调整顺序</div>
    <template #footer>
      <el-button size="small" @click="$emit('reset')">恢复默认</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="$emit('confirm')">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  columns: { type: Array, default: () => [] },
})
defineEmits(['confirm', 'reset'])
const visible = defineModel('visible', { type: Boolean, default: false })
const selectedIdx = ref(-1)
const dragIndex = ref(-1)
const overIndex = ref(-1)

function onDragStart(i, evt) {
  dragIndex.value = i
  overIndex.value = i
  if (evt.dataTransfer) {
    evt.dataTransfer.effectAllowed = 'move'
    evt.dataTransfer.setData('text/plain', String(i))
  }
}

function onDragOver(i) {
  overIndex.value = i
}

function onDrop(i) {
  const from = dragIndex.value
  dragIndex.value = -1
  overIndex.value = -1
  if (from < 0 || from === i) return
  const arr = props.columns
  const [moved] = arr.splice(from, 1)
  arr.splice(from < i ? i - 1 : i, 0, moved)
}

function onDragEnd() {
  dragIndex.value = -1
  overIndex.value = -1
}
</script>

<style scoped>
.drag-handle {
  cursor: grab;
  color: #909399;
  font-size: 14px;
  user-select: none;
  padding: 2px 4px;
}
.drag-handle:active {
  cursor: grabbing;
}
.col-setting-item.dragging {
  opacity: 0.5;
}
.col-setting-item.drag-over {
  border-color: #409eff;
  background: #ecf5ff;
}
</style>
