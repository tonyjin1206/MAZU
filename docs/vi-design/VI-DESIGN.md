# MTS (Mazu Trade System) — 视觉识别系统 (VI) 设计规范

> **版本**: 1.0 | **最后更新**: 2026-07-29
> **用途**: 供前端开发 AI 重构整个系统 UI 的设计依据

---

## 目录

1. [品牌定义](#1-品牌定义)
2. [Logo 系统](#2-logo-系统)
3. [色彩系统](#3-色彩系统)
4. [排版系统](#4-排版系统)
5. [间距系统](#5-间距系统)
6. [圆角与阴影系统](#6-圆角与阴影系统)
7. [图标系统](#7-图标系统)
8. [组件设计规范](#8-组件设计规范)
9. [页面布局规范](#9-页面布局规范)
10. [状态与动效](#10-状态与动效)
11. [响应式规则](#11-响应式规则)
12. [SVG 素材清单](#12-svg-素材清单)
13. [CSS 变量引用](#13-css-变量引用)

---

## 1. 品牌定义

| 项目 | 内容 |
|------|------|
| **产品名称** | MTS — Mazu Trade System（妈祖贸易系统） |
| **产品类型** | 中小外贸企业 ERP（采购/销售/生产/库存/退税/财务） |
| **品牌调性** | 专业可靠 + 现代简洁 + 海洋/贸易意象 |
| **目标用户** | 外贸企业管理者、业务操作员（桌面端为主） |
| **技术栈** | Vue 3 + Element Plus + Vite |
| **品牌故事** | 妈祖是中国海神，护佑航海与贸易——象征**安全、通达、繁荣** |

### 关键词

```
海洋 · 贸易 · 专业 · 高效 · 安全 · 数字化
```

### 设计方向

- **主色**: 海洋蓝系（深蓝 → 亮蓝渐变），传达专业与信任
- **辅助色**: 青蓝/青色，代表海洋与国际化贸易
- **风格**: 简洁、信息密度高、数据驱动
- **对比**: 深色侧边栏 + 浅色内容区，清晰的视觉层级

---

## 2. Logo 系统

MTS 提供两套 Logo 版本，适应不同背景色场景。

### 2.1 深色底色版（用于浅色背景）

**文件**: `docs/vi-design/LOGO-dark.svg`

**设计说明**:
- 圆角方形图标（squircle），深蓝底（#163E64）
- 手写风格小写「m」，白色（#FFFFFF）
- 四芒星点缀，青绿色（#14B8A6）

### 2.2 白色底色版（用于深色背景）

**文件**: `docs/vi-design/LOGO-light.svg`

**设计说明**:
- 圆角方形图标（squircle），白底（#FFFFFF）
- 手写风格小写「m」，蓝灰色（#215F9A）
- 四芒星点缀，青绿色（#14B8A6）

### 2.3 使用规范

| 场景 | 使用版本 | 大小 |
|------|---------|------|
| 侧边栏顶部 | `LOGO-dark.svg` | 28×28px |
| 登录页 | `LOGO-dark.svg` | 64×64px |
| Favicon | `LOGO-dark.svg` | 16×16px |
| 浅色页面/白色背景页头 | `LOGO-dark.svg` | 32×32px |
| 深色背景/弹窗/打印 | `LOGO-light.svg` | 按需 |

### 2.4 文字标识

```
   MTS  ·  Mazu Trade System
```

**字体**: Inter / system-ui
**颜色**: 侧边栏用白色 #d8dce6，亮色背景用 #1e3a5f / #163E64

---

## 3. 色彩系统

### 3.1 品牌主色 (Primary)

| 色阶 | 色值 | 用途 |
|------|------|------|
| 50 | `#eff6ff` | 极浅蓝背景、hover 态 |
| 100 | `#dbeafe` | 选中态、浅色标签 |
| 200 | `#bfdbfe` | 边框、分割线 |
| 300 | `#93c5fd` | 禁用文字 |
| 400 | `#60a5fa` | 占位符 |
| **500** | **`#3b82f6`** | **基础色 — 按钮、链接、活动图标** |
| 600 | `#2563eb` | Hover 态（按钮悬浮） |
| 700 | `#1d4ed8` | 按下态（按钮激活） |
| 800 | `#1e40af` | 深色背景上标题 |
| 900 | `#1e3a5f` | 侧边栏底色、品牌深色 |

### 3.2 语义色 (Semantic)

| 名称 | 色值 | 用途 |
|------|------|------|
| **success** | `#22c55e` / `#67c23a` | 成功、已支付、已审核、正数 |
| **warning** | `#f59e0b` / `#e6a23c` | 警告、待处理、部分状态、逾期提醒 |
| **danger** | `#ef4444` / `#f56c6c` | 错误、删除、取消、负数、已逾期 |
| **info** | `#3b82f6` / `#409eff` | 信息提示、蓝色标签 |
| **cyan** | `#06b6d4` | 辅助色、贸易/船运相关、渐变端点 |

### 3.3 中性色 (Neutral / Gray)

| 色阶 | 色值 | 用途 |
|------|------|------|
| 50 | `#f9fafb` | **页面背景色** |
| 100 | `#f3f4f6` | 卡片背景、交替行 |
| 200 | `#e5e7eb` | 边框、分割线 |
| 300 | `#d1d5db` | 禁用元素 |
| 400 | `#9ca3af` | 占位符文字 |
| 500 | `#6b7280` | 次要文字、图标 |
| 600 | `#4b5563` | 正文文字 |
| 700 | `#374151` | 标题 |
| 800 | `#1f2937` | 主要文字 |
| 900 | `#111827` | 最高对比度文字 |

### 3.4 侧边栏色 (Sidebar)

| 名称 | 色值 | 用途 |
|------|------|------|
| sidebar-bg | `linear-gradient(180deg, #103B9C 0%, #1a4a9c 100%)` | 侧边栏背景 |
| sidebar-text | `rgba(255,255,255,0.55)` | 菜单文字默认态 |
| sidebar-active | `#ffffff` | 菜单文字激活态 |
| sidebar-hover | `rgba(255,255,255,0.05)` | 菜单 hover 背景 |
| sidebar-border | `rgba(255,255,255,0.06)` | 分割线 |
| sidebar-header-bg | `rgba(0,0,0,0.15)` | 顶部品牌区 |

### 3.5 功能模块配色 (区分模块)

系统 7 大模块使用不同的辅助色，增强视觉识别：

| 模块 | 色值 | 用途 |
|------|------|------|
| **基础档案** | `#6366f1` 靛蓝（Indigo） | 模块图标、标签 |
| **销售管理** | `#22c55e` 翠绿（Emerald） | 模块图标、标签 |
| **采购管理** | `#f59e0b` 琥珀（Amber） | 模块图标、标签 |
| **生产管理** | `#8b5cf6` 紫色（Violet） | 模块图标、标签 |
| **库存管理** | `#06b6d4` 青色（Cyan） | 模块图标、标签 |
| **退税管理** | `#ec4899` 粉色（Pink） | 模块图标、标签 |
| **系统管理** | `#6b7280` 灰色（Gray） | 模块图标、标签 |

### 3.6 驾驶舱图表配色

| 用途 | 色值 |
|------|------|
| 现金收入 | `#3b82f6` → `#60a5fa` 渐变 |
| 现金支付 | `#f59e0b` → `#fbbf24` 渐变 |
| 净收支正数 | `#22c55e` → `#4ade80` 渐变 |
| 净收支负数 | `#ef4444` → `#f87171` 渐变 |
| 毛利率 ≥ 30% | `success` (绿) |
| 毛利率 10-30% | `warning` (黄) |
| 毛利率 < 10% | `danger` (红) |

### 3.7 表格状态标签配色

| 业务状态 | Element Plus Tag Type | 规则 |
|---------|----------------------|------|
| 待审核/待排产/待确认 | `info` | 初始态 |
| 已审核/已确认/已排产 | `primary` | 中间确认态 |
| 部分入库/部分付款 | `warning` | 进行中 |
| 生产中/加工中 | `warning` | 进行中 |
| 已完成/已入库/已付款 | `success` | 终态 |
| 已关闭/已取消 | `danger` | 终止态 |
| 已逾期 | `danger` | 异常态 |

---

## 4. 排版系统

### 4.1 字体栈

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
             'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei',
             'Inter', sans-serif;
```

### 4.2 字号层级

| Token | 大小 | 行高 | 使用场景 |
|-------|------|------|---------|
| `--mts-font-xs` | 10px | 1.4 | 辅助信息、角标 |
| `--mts-font-sm` | 11px | 1.4 | 表格内容、标签、表单辅助文字 |
| `--mts-font-base` | **12px** | 1.5 | **正文、表格、表单标签（系统默认）** |
| `--mts-font-md` | 13px | 1.5 | 强调正文、弹窗内容 |
| `--mts-font-lg` | 14px | 1.5 | 卡片标题、侧边栏菜单 |
| `--mts-font-xl` | 16px | 1.4 | 页面标题、弹窗标题 |
| `--mts-font-2xl` | 20px | 1.3 | 大标题、统计数字 |

> **注意**: 因为本系统是桌面端 ERP（信息密度高），基础字号为 12px。
> 这不同于常规网页设计（16px），但符合企业管理软件行业惯例。

### 4.3 字重

| Token | 值 | 用途 |
|-------|------|------|
| `--mts-weight-normal` | 400 | 正文、表格内容 |
| `--mts-weight-medium` | 500 | 表单标签、按钮文字 |
| `--mts-weight-semibold` | 600 | 卡片标题、侧边栏菜单、表头 |
| `--mts-weight-bold` | 700 | 页面大标题、统计数字 |

---

## 5. 间距系统

基于 4px 基础单位。

| Token | 值 | 使用场景 |
|-------|------|---------|
| `--mts-space-1` | 4px | 内聚间距（图标+文字） |
| `--mts-space-2` | 8px | 相关项间距、卡片内边距小 |
| `--mts-space-3` | 12px | 表单字段内边距、表格单元格 |
| `--mts-space-4` | 16px | 卡片内边距标准、主区域边距 |
| `--mts-space-5` | 20px | 弹窗内边距、头部区域 |
| `--mts-space-6` | 24px | 区块间距、表单组间距 |
| `--mts-space-8` | 32px | 页面区域间距 |
| `--mts-space-10` | 40px | 大区块间距 |
| `--mts-space-12` | 48px | 页面上下边距 |

### 4-8-12 原则

```
组件内间距: 8-12px   (如按钮文字到边框)
组件间间距: 12-16px  (如表单项之间)
区块间间距: 16-24px  (如卡片之间)
页面边距:   16px     (主区域 padding)
```

---

## 6. 圆角与阴影系统

### 6.1 圆角

| Token | 值 | 使用场景 |
|-------|------|---------|
| `--mts-radius-none` | 0 | 表格、代码 |
| `--mts-radius-sm` | 2px | 标签、小徽章 |
| `--mts-radius-md` | 4px | 输入框、小按钮 |
| `--mts-radius-lg` | 6px | 卡片、弹窗 |
| `--mts-radius-xl` | 8px | 大卡片 |
| `--mts-radius-full` | 999px | 圆形头像、胶囊标签 |

### 6.2 阴影

| Token | 值 | 使用场景 |
|-------|------|---------|
| `--mts-shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | 卡片默认态 |
| `--mts-shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.1)` | 卡片悬浮、下拉框 |
| `--mts-shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.1)` | 弹窗、弹出层 |
| `--mts-shadow-xl` | `0 20px 25px -5px rgba(0,0,0,0.15)` | 对话框、通知 |

---

## 7. 图标系统

### 7.1 模块图标映射

系统使用 **自定义 SVG 图标**（MTS Icons）替换原有 Element Plus 默认图标。

**文件**: `docs/vi-design/mts-icons.svg`（SVG sprite 格式）

| 模块 | 图标 ID | 对应页面 |
|------|---------|---------|
| 工作台 | `#mts-dashboard` | 首页/驾驶舱 |
| 基础档案 | `#mts-foundation` | 侧边栏菜单 |
| 客户管理 | `#mts-customer` | 客户管理页 |
| 供应商管理 | `#mts-supplier` | 供应商管理页 |
| 物料管理 | `#mts-material` | 原辅材料页 |
| 产品档案 | `#mts-product` | 产品档案页 |
| BOM管理 | `#mts-bom` | BOM 管理页 |
| 工序管理 | `#mts-process` | 工序管理页 |
| HS编码 | `#mts-hs-code` | HS编码页 |
| 销售管理 | `#mts-sales` | 侧边栏菜单 |
| 订单 | `#mts-order` | 采购/销售订单列表 |
| 发票 | `#mts-invoice` | 采购/销售发票页 |
| 付款 | `#mts-payment` | 付款/收款管理 |
| 入库 | `#mts-receipt` | 采购入库/完工入库 |
| 出库 | `#mts-delivery` | 销售发货 |
| 生产管理 | `#mts-production` | 侧边栏菜单 |
| 采购管理 | `#mts-purchase` | 侧边栏菜单 |
| 库存管理 | `#mts-inventory` | 侧边栏菜单 |
| 退税管理 | `#mts-tax-refund` | 侧边栏菜单 |
| 系统管理 | `#mts-system` | 侧边栏菜单 |
| 财务 | `#mts-finance` | 财务相关页面 |
| 报表 | `#mts-report` | 统计分析 |
| 审批 | `#mts-approve` | 审批操作按钮 |
| 船运 | `#mts-shipping` | 报关/物流相关 |
| 驾驶舱 | `#mts-cockpit` | 驾驶舱页面 |

### 7.2 图标使用方式

```html
<!-- 在 Layout.vue 头部加载 sprite -->
<svg style="display:none">
  <use href="/mts-icons.svg#mts-dashboard" />
</svg>

<!-- 使用方式 -->
<svg class="mts-icon" width="18" height="18">
  <use href="#mts-dashboard" />
</svg>
```

### 7.3 图标尺寸

| 场景 | 大小 |
|------|------|
| 侧边栏菜单图标 | 16×16px |
| 按钮图标 | 14×14px |
| 页面空状态 | 48×48px |
| 表格操作图标 | 12×12px |

### 7.4 图标颜色

图标使用 `currentColor`，颜色由父容器 CSS 控制。

```css
.mts-icon { color: var(--mts-gray-500); }
.mts-icon.active { color: var(--mts-primary-500); }
```

### 7.5 Element Plus 图标准入

保留使用 Element Plus 图标库中通用操作类图标（如：Search, Edit, Delete, Plus, Download），
仅**模块/菜单图标**替换为自定义 SVG。

---

## 8. 组件设计规范

### 8.1 按钮系统

| 类型 | 样式 | 字体 | 内边距 | 圆角 |
|------|------|------|--------|------|
| **Primary** | 背景 `--mts-primary-500`，白色文字 | 12px/500 | 8px 16px | 4px |
| **Plain** | 边框 `--mts-gray-300`，文字 `--mts-gray-600` | 12px/400 | 8px 16px | 4px |
| **Text/Link** | 无背景，文字 `--mts-primary-500` | 12px/400 | 4px 8px | 2px |
| **Danger** | 背景 `--mts-danger`，白色文字 | 12px/500 | 8px 16px | 4px |
| **Small** | 同类型缩小版 | 11px | 4px 10px | 4px |

**状态**: default → hover(变暗/阴影) → active(压暗) → focus(ring) → disabled(0.5透明度)

### 8.2 表单规范

| 元素 | 样式 |
|------|------|
| 标签 | 12px/500，置于输入框上方，间距 4px |
| 输入框 | 高度 32px，边框 `--mts-gray-300`，聚焦态 `--mts-primary-500` ring |
| 错误提示 | 红色 11px 文字，输入框下方，与输入框间距 2px |
| 禁用态 | 背景 `--mts-gray-100`，文字 `--mts-gray-400` |
| 占位符 | `--mts-gray-400` |
| 表单项间距 | 12-16px（垂直） |
| 内联表单 | 表单项水平排列，label-width 由内容定 |

### 8.3 表格规范

| 属性 | 值 |
|------|-----|
| 表头背景 | `--mts-gray-100` (#f3f4f6) |
| 表头文字 | 12px/600，`--mts-gray-600` |
| 行高 | 32px（紧凑模式） |
| 交替色 | `stripe`（斑马纹） |
| 边框 | `border`（全边框） |
| 悬浮高亮 | `--mts-primary-50` |
| 文字对齐 | 数字右对齐、文本左对齐、状态居中 |
| 长文本 | `show-overflow-tooltip` |
| 分页 | 底部，layout: `total, sizes, prev, pager, next` |

### 8.4 卡片规范

| 属性 | 值 |
|------|-----|
| 背景 | `--mts-white` |
| 边框 | 1px solid `--mts-gray-200` |
| 圆角 | 6px |
| 内边距 | header: 8px 12px, body: 12px 16px |
| 阴影 | `--mts-shadow-sm` |

### 8.5 弹窗规范

| 属性 | 值 |
|------|-----|
| 标题 | 14px/600，水平居中或居左 |
| 内边距 | header: 12px 20px, body: 16px 20px, footer: 10px 20px |
| 宽度 | 500px(小) / 640px(中) / 800px(大) / 970px(超大) |
| 遮罩 | `rgba(0,0,0,0.4)` |
| 关闭 | 右上角 X 按钮 |

### 8.6 侧边栏导航

| 属性 | 值 |
|------|-----|
| 背景 | `--mts-sidebar-bg` (渐变) |
| 宽度 | 展开 220px / 折叠 64px |
| 菜单项高度 | 34px |
| 子菜单标题高度 | 38px |
| 菜单内边距 | padding-left: 20px / 子菜单 44px |
| 展开指示 | 默认箭头展开 |
| 折叠态 | 仅显示图标，悬浮显示 tooltip |
| 激活态 | 文字色 `--mts-sidebar-active`，无背景块 |

---

## 9. 页面布局规范

### 9.1 整体布局

```
┌──────────┬──────────────────────────────────┐
│          │  HEADER (50px)                    │
│  SIDEBAR │  [折叠按钮] [面包屑/页面标题] [用户信息] │
│          ├──────────────────────────────────┤
│  220px   │  MAIN (flex-1)                   │
│  展开    │  background: #f5f7fa             │
│  64px    │  padding: 16px                   │
│  折叠    │                                  │
└──────────┴──────────────────────────────────┘
```

### 9.2 列表页标准布局

```
┌─ Card (margin-bottom: 12px) ──────────────┐
│  [查询] [重置] [新建按钮]     (按钮靠右)      │
├─────────────────────────────────────────────┤
│  关键词[____]  日期[____~____]  状态[▼]      │
└─────────────────────────────────────────────┘
┌─ Card ─────────────────────────────────────┐
│  ┌ 表格 (border + stripe + small) ──────┐  │
│  │ 行1                                   │  │
│  │ 行2                                   │  │
│  └───────────────────────────────────────┘  │
│  共N条  20条/页  ◀ 1 2 3 ▶                │
└─────────────────────────────────────────────┘
```

### 9.3 搜索栏规则

- 按钮在 Card header 靠右排列
- 搜索条件在 Card body 用 `el-form inline`
- 不支持 wrap 换行（flex-wrap: nowrap）
- 按钮: 查询(Primary) / 重置(Plain) / 新建(Primary)

### 9.4 表格操作列规则

- 操作按钮用 `link` 类型，排成一列
- 根据状态条件显示（v-if）
- 顺序: 正向操作(审核/确认) → 编辑 → 逆向操作(取消审核) → 详情
- 颜色: 审核类=success / 编辑类=primary / 逆向类=warning / 删除类=danger

### 9.5 弹窗表单规则

- 搜索条件在左上角
- 编辑项按列排放
- 选择物料/供应商/客户时: 下拉框 + 自动填充
- 金额字段: 自动计算(含税=数量×单价, 不含税=含税/(1+税率))
- 明细行: 嵌入式 el-table 可编辑

---

## 10. 状态与动效

### 10.1 过渡时长

| 场景 | 时长 | 缓动 |
|------|------|------|
| 按钮 hover | 150ms | ease |
| 弹窗出现 | 200ms | ease-out |
| 页面切换 | 200ms | ease-in-out |
| 折叠菜单 | 250ms | ease-in-out |
| 表格加载 | 300ms | ease |
| 提示消失 | 300ms | ease-in |

### 10.2 交互反馈

| 交互 | 反馈 |
|------|------|
| 按钮悬浮 | 色值变暗/加深 |
| 按钮点击 | 无变换 |
| 表格行悬浮 | 浅蓝色背景 |
| 输入框聚焦 | 蓝色边框 + 外发光 ring |
| 加载中 | 骨架屏或 spinner |
| 操作成功 | 顶部绿色 success 提示 |
| 操作失败 | 顶部红色 error 提示 |

### 10.3 加载态

- **表格加载**: v-loading 指令（Element Plus 自带 spinner）
- **页面初始化**: 骨架屏效果
- **按钮加载**: 按钮内嵌 spinner，禁止重复点击
- **弹窗提交**: loading 状态，提交完成自动关闭

### 10.4 空状态

表格无数据时:
```
┌──────────────────────────────┐
│                              │
│       📋 (空状态图标)         │
│   暂无数据                    │
│   还没有相关记录，点击新建     │
│                              │
│      [ + 新建 ]               │
│                              │
└──────────────────────────────┘
```

---

## 11. 响应式规则

本系统为**桌面优先**的 ERP 系统，最低分辨率支持 1280×720。

| 断点 | 宽度 | 行为 |
|------|------|------|
| 桌面标准 | ≥1280px | 完整布局 |
| 小桌面 | 1024-1279px | 侧边栏自动折叠 |
| 平板 | 768-1023px | 侧边栏折叠 + 表格横滚 |
| 手机 | <768px | 不直接支持（提示使用桌面） |

注意：ERM 系统包含大量表格与复杂表单，不建议在手机上使用。
如必须使用，需做大幅简化（只读查看模式）。

---

## 12. SVG 素材清单

| 文件 | 路径 | 说明 |
|------|------|------|
| Logo 深色版 | `docs/vi-design/LOGO-dark.svg` | 深蓝底 + 白色 m + 青星（用于浅色背景） |
| Logo 浅色版 | `docs/vi-design/LOGO-light.svg` | 白底 + 蓝灰 m + 青星（用于深色背景） |
| 图标 Sprite | `docs/vi-design/mts-icons.svg` | 26 个自定义 SVG 图标的 Sprite 文件 |

### 图标列表速查

```
mts-dashboard    mts-foundation  mts-customer     mts-supplier
mts-material     mts-product     mts-bom          mts-process
mts-hs-code      mts-sales       mts-purchase     mts-production
mts-inventory    mts-tax-refund  mts-system       mts-order
mts-invoice      mts-payment     mts-receipt      mts-delivery
mts-finance      mts-report      mts-approve      mts-shipping
mts-cockpit      mts-admin
```

---

## 13. CSS 变量引用

完整的 CSS 自定义属性已在 `docs/vi-design/mts-variables.css` 中定义。

**前端集成方式**:

1. 在 `App.vue` 或 `main.js` 中引入 CSS 变量文件:
   ```js
   import './docs/vi-design/mts-variables.css'
   ```

2. 在组件中使用 CSS 变量:
   ```css
   .my-component {
     background: var(--mts-primary-500);
     color: var(--mts-gray-50);
     padding: var(--mts-space-4);
     border-radius: var(--mts-radius-lg);
   }
   ```

3. 模块图标使用:
   ```html
   <svg class="mts-icon" width="16" height="16">
     <use href="#mts-dashboard" />
   </svg>
   ```

---

## 附录：状态颜色对照表

### 业务状态 → Element Plus Tag Type

| 业务状态 | Tag Type | CSS 变量 |
|---------|----------|---------|
| 待审核/待排产/待确认/待开票 | `info` | `--mts-gray-500` |
| 已审核/已确认/已排产/已申报 | `primary` | `--mts-primary-500` |
| 部分入库/部分付款/部分发货/生产中等 | `warning` | `--mts-warning` |
| 已入库/已付款/已发货/已完工/已退税 | `success` | `--mts-success` |
| 已关闭/已取消/已逾期 | `danger` | `--mts-danger` |

### 金额/数值颜色

| 情况 | 颜色 |
|------|------|
| 未入库/未开票/未付款（正数） | `--mts-warning` (#e6a23c) |
| 已入库/已开票/已付款 | `--mts-gray-500` (#909399) |
| 已逾期 | `--mts-danger` (#f56c6c) |
| 未逾期 | `--mts-success` (#67c23a) |
| 毛利正数 | `--mts-success` |
| 毛利负数 | `--mts-danger` |
| 毛利率高(≥30%) | `success` tag |
| 毛利率中(10-30%) | `warning` tag |
| 毛利率低(<10%) | `danger` tag |

---

> **说明**: 本文档设计供 AI 前端开发 agent 直接使用。所有色值、间距、圆角、阴影都有 CSS 变量可引用。
> 前端开发 AI 可将此文档作为 style guide，逐页重构 UI，确保全局视觉统一。
