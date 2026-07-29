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
  /* Element Plus 品牌色覆盖 — MTS VI */
  --el-color-primary: #3b82f6;
  --el-color-primary-light-3: #60a5fa;
  --el-color-primary-light-5: #93c5fd;
  --el-color-primary-light-7: #bfdbfe;
  --el-color-primary-light-8: #dbeafe;
  --el-color-primary-light-9: #eff6ff;
  --el-color-primary-dark-2: #2563eb;
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
</style>
