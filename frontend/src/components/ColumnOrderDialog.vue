<template>
  <el-dialog v-model="visible" title="调整列顺序" width="380px" destroy-on-close @opened="$emit('opened')">
    <div class="column-order-list" style="max-height: 420px; overflow-y: auto">
      <div v-for="col in columns" :key="col.prop" class="col-order-item" style="display: flex; align-items: center; gap: 8px; padding: 10px 12px; margin: 4px 0; border: 1px solid #e4e7ed; border-radius: 4px; background: #fff; cursor: default">
        <span class="col-order-handle" style="cursor: grab; color: #909399; font-size: 16px; user-select: none" title="拖动排序">⠿</span>
        <span style="font-size: 13px">{{ col.label }}</span>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="$emit('confirm')">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  columns: { type: Array, default: () => [] },
})
defineEmits(['confirm', 'opened'])
const visible = defineModel('visible', { type: Boolean, default: false })
</script>
