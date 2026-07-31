<template>
  <router-view />
</template>

<script setup>
</script>

<style>
:root {
  --el-font-size-base: 12px;
  --el-font-size-small: 11px;
  --el-font-size-extra-small: 10px;
  --el-font-size-medium: 13px;
  --el-font-size-large: 14px;
  /* Element Plus 品牌色覆盖 — MTS VI (暗色版) */
  --el-color-primary: #1d4ed8;
  --el-color-primary-light-3: #3b82f6;
  --el-color-primary-light-5: #60a5fa;
  --el-color-primary-light-7: #93c5fd;
  --el-color-primary-light-8: #bfdbfe;
  --el-color-primary-light-9: #dbeafe;
  --el-color-primary-dark-2: #1e40af;
  --el-color-success: #67c23a;
  --el-color-warning: #e6a23c;
  --el-color-danger: #f56c6c;
  --el-color-info: #909399;
  --el-border-radius-base: 4px;
  --el-border-radius-small: 2px;
}
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
}
.el-card__header { padding: 8px 12px; }
.el-card__body { padding: 8px 12px; }
.el-table { font-size: 12px; }
.el-form-item { margin-bottom: 22px; }
.el-form-item--small { margin-bottom: 18px; }
.el-form-item__error { font-size: 11px; padding-top: 2px; }
.el-descriptions { font-size: 12px; }
.el-descriptions__label, .el-descriptions__content { font-size: 12px; padding: 4px 8px; }
.el-dialog { font-size: 12px; }
.el-dialog__header { padding: 12px 20px; }
.el-dialog__body { padding: 16px 20px; }
.el-dialog__footer { padding: 10px 20px; }
.el-menu-item { height: 36px; line-height: 36px; }
.el-sub-menu__title { height: 36px; line-height: 36px; font-size: 12px; }
.el-pagination { font-size: 12px; }
.el-tag { font-size: 11px; }

/* === 列拖拽通用样式 === */
.col-header-wrap {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.col-drag-handle {
  cursor: grab;
  color: #909399;
  font-size: 13px;
  user-select: none;
  padding: 0 2px;
  border-radius: 3px;
}
.col-drag-handle:hover {
  color: #409eff;
  background: #ecf5ff;
}
.col-drag-handle:active {
  cursor: grabbing;
}
.sortable-ghost {
  opacity: 0.4;
  background: #ecf5ff;
}
.sortable-drag {
  opacity: 0.8;
}
</style>
