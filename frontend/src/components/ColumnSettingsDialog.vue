<template>
  <el-dialog v-model="visible" title="列设置" width="420px" destroy-on-close>
    <div class="column-settings-list" style="max-height: 420px; overflow-y: auto">
      <div v-for="(col, i) in columns" :key="col.prop" class="col-setting-item" :class="{ selected: i === selectedIdx }" style="display: flex; align-items: center; gap: 8px; padding: 8px 10px; margin: 3px 0; border: 1px solid #e4e7ed; border-radius: 4px; background: #fff; cursor: default" @click="selectedIdx = i">
        <el-checkbox :model-value="col.visible !== false" @change="col.visible = col.visible !== false ? false : true" @click.stop />
        <span style="font-size: 13px; flex: 1">{{ col.label }}</span>
        <el-button-group>
          <el-button size="small" :disabled="i === 0" title="上移" @click.stop="move(i, -1)">↑</el-button>
          <el-button size="small" :disabled="i === columns.length - 1" title="下移" @click.stop="move(i, 1)">↓</el-button>
        </el-button-group>
      </div>
    </div>
    <div style="color: #909399; font-size: 12px; margin-top: 6px">勾选 = 显示；选中一行后点 ↑/↓ 调整顺序</div>
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

function move(i, dir) {
  const j = i + dir
  if (j < 0 || j >= props.columns.length) return
  const arr = props.columns
  const tmp = arr[i]
  arr[i] = arr[j]
  arr[j] = tmp
  selectedIdx.value = j
}
</script>
