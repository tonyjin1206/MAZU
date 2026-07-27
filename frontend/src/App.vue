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
}
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
}
.el-card__header { padding: 8px 12px; }
.el-card__body { padding: 8px 12px; }
.el-table { font-size: 12px; }
.el-form-item { margin-bottom: 10px; }
.el-descriptions { font-size: 12px; }
.el-descriptions__label, .el-descriptions__content { font-size: 12px; padding: 4px 8px; }
.el-dialog { font-size: 12px; }
.el-dialog__header { padding: 10px 16px; }
.el-dialog__body { padding: 10px 16px; }
.el-dialog__footer { padding: 8px 16px; }
.el-menu-item { height: 36px; line-height: 36px; }
.el-sub-menu__title { height: 36px; line-height: 36px; font-size: 12px; }
.el-pagination { font-size: 12px; }
.el-tag { font-size: 11px; }
</style>
