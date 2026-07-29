# MTS VI Design — 文件索引

```
docs/vi-design/
├── README.md              ← 本文件：文件索引与快速入门
├── VI-DESIGN.md           ← 完整 VI 设计规范文档（核心交付物）
├── mts-variables.css      ← CSS 自定义属性（可直接引入前端）
├── LOGO-dark.svg          ← 深色底色版 Logo（深蓝底 + 白色 m + 青星）
├── LOGO-light.svg         ← 白色底色版 Logo（白底 + 蓝灰 m + 青星）
└── mts-icons.svg          ← 26 个模块 SVG 图标 Sprite
```

## 前端开发 AI 工作流程

1. **阅读** `VI-DESIGN.md` — 了解品牌调性、色彩、排版、间距等完整设计系统
2. **引入** `mts-variables.css` — 在项目入口使用 CSS 变量
3. **使用图标** — 加载 `mts-icons.svg` sprite，用 `<use href="#mts-xxx">` 引用
4. **应用 Logo** — 侧边栏/登录页用 `LOGO-dark.svg`，深色背景用 `LOGO-light.svg`

## Logo 版本选择

| 场景 | 使用版本 |
|------|---------|
| 侧边栏顶部 | `LOGO-dark.svg` |
| 登录页 | `LOGO-dark.svg` |
| Favicon | `LOGO-dark.svg` |
| 浅色页面/白色背景页头 | `LOGO-dark.svg` |
| 深色背景/弹窗/打印 | `LOGO-light.svg` |

## 模块色速查

| 模块 | CSS 变量 | 色值 |
|------|---------|------|
| 基础档案 | `--mts-module-foundation` | #6366f1 |
| 销售管理 | `--mts-module-sales` | #22c55e |
| 采购管理 | `--mts-module-purchase` | #f59e0b |
| 生产管理 | `--mts-module-production` | #8b5cf6 |
| 库存管理 | `--mts-module-inventory` | #06b6d4 |
| 退税管理 | `--mts-module-tax-refund` | #ec4899 |
| 系统管理 | `--mts-module-system` | #6b7280 |
| 驾驶舱 | `--mts-module-dashboard` | #3b82f6 |

## 品牌色速查

| Token | 值 | 用途 |
|-------|------|------|
| `--mts-primary-500` | #3b82f6 | 主色（按钮、链接、激活态） |
| `--mts-primary-900` | #1e3a5f | 品牌深色 |
| `--mts-sidebar-bg` | #103B9C | 侧边栏底色 |
| `--mts-sidebar-bg-end` | #1a4a9c | 侧边栏渐变结束色 |
| `--mts-logo-dark-bg` | #163E64 | 深色 Logo 背景色 |
| `--mts-logo-light-m` | #215F9A | 浅色 Logo 文字色 |
| `--mts-logo-star` | #14B8A6 | Logo 星点缀色 |
| `--mts-page-bg` | #f5f7fa | 页面背景色 |

## 图标 ID 速查

```html
<svg class="mts-icon" width="16" height="16">
  <use href="#mts-dashboard" />
</svg>
```

全部 26 个 ID: `mts-dashboard`, `mts-foundation`, `mts-customer`, `mts-supplier`, `mts-material`, `mts-product`, `mts-bom`, `mts-process`, `mts-hs-code`, `mts-sales`, `mts-purchase`, `mts-production`, `mts-inventory`, `mts-tax-refund`, `mts-system`, `mts-order`, `mts-invoice`, `mts-payment`, `mts-receipt`, `mts-delivery`, `mts-finance`, `mts-report`, `mts-approve`, `mts-shipping`, `mts-cockpit`, `mts-admin`
```
