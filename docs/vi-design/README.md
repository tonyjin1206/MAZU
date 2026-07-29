# MTS VI Design — 文件索引

```
docs/vi-design/
├── README.md              ← 本文件：文件索引与快速入门
├── VI-DESIGN.md           ← 完整 VI 设计规范文档（核心交付物）
├── mts-variables.css      ← CSS 自定义属性（可直接引入前端）
├── logo.svg               ← 产品 Logo（圆形徽章，240×240）
└── mts-icons.svg          ← 26 个模块 SVG 图标 Sprite
```

## 前端开发 AI 工作流程

1. **阅读** `VI-DESIGN.md` — 了解品牌调性、色彩、排版、间距等完整设计系统
2. **引入** `mts-variables.css` — 在项目入口使用 CSS 变量
3. **使用图标** — 加载 `mts-icons.svg` sprite，用 `<use href="#mts-xxx">` 引用
4. **应用 Logo** — `logo.svg` 用于侧边栏、登录页、Favicon

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
| `--mts-primary-900` | #1e3a5f | 侧边栏品牌色 |
| `--mts-sidebar-bg-start` | #0f2847 | 侧边栏起始色 |
| `--mts-sidebar-bg-end` | #1a3a6b | 侧边栏结束色 |
| `--mts-page-bg` | #f5f7fa | 页面背景色 |

## 图标 ID 速查

```html
<svg class="mts-icon" width="16" height="16">
  <use href="#mts-dashboard" />
</svg>
```

全部 26 个 ID: `mts-dashboard`, `mts-foundation`, `mts-customer`, `mts-supplier`, `mts-material`, `mts-product`, `mts-bom`, `mts-process`, `mts-hs-code`, `mts-sales`, `mts-purchase`, `mts-production`, `mts-inventory`, `mts-tax-refund`, `mts-system`, `mts-order`, `mts-invoice`, `mts-payment`, `mts-receipt`, `mts-delivery`, `mts-finance`, `mts-report`, `mts-approve`, `mts-shipping`, `mts-cockpit`, `mts-admin`
```
