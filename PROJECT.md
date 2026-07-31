# Mazu Trade System (MTS) — 项目文档

> **v2.2.0** | A Lightweight Trade Management Platform

Python FastAPI + Vue 3 (Element Plus) + SQLite 的外贸企业 ERP 系统，覆盖采购、销售、生产、退税、库存等核心业务模块。
**支持 AI 智能助手（Matsu）自然语言对话式操作。**

- 后端: FastAPI (端口 8788)
- 前端: Vue 3 + Vite (端口 5173)
- 数据库: SQLite (`backend/data/erp.db`)
- 认证: JWT (默认 admin / admin123)
- AI 引擎: Function Calling Agent (OpenAI / DeepSeek 兼容)
- API Key: Fernet 加密存储 (`backend/.encryption_key`)

---

## 一、基础档案 (`/api/foundation`)

管理公司信息、物料、产品、BOM、客户、供应商、工序、HS编码。

| 路由 | 方法 | 说明 |
|------|------|------|
| `/company` | GET/POST | 公司信息（仅一条）|
| `/company/contacts` | GET/POST | 联系人列表 / 新增 |
| `/company/contacts/{id}` | PUT/DELETE | 修改/删除联系人 |
| `/customers` | GET/POST | 客户列表 / 新增 |
| `/customers/{id}` | GET/PUT/DELETE | 客户详情 / 修改 / 删除 |
| `/suppliers` | GET/POST | 供应商列表 / 新增 |
| `/suppliers/{id}` | GET/PUT/DELETE | 供应商详情 / 修改 / 删除 |
| `/materials` | GET/POST | 物料列表 / 新增 |
| `/materials/{id}` | GET/PUT/DELETE | 物料详情 / 修改 / 删除 |
| `/products` | GET/POST | 产品列表 / 新增 |
| `/products/{id}` | GET/PUT/DELETE | 产品详情 / 修改 / 删除 |
| `/boms` | GET/POST | BOM列表 / 新增（含明细行）|
| `/boms/{id}` | GET/PUT/DELETE | BOM详情 / 修改 / 删除 |
| `/processes` | GET/POST | 工序列表 / 新增 |
| `/processes/{id}` | PUT/DELETE | 修改/删除工序 |
| `/hscodes` | GET/POST | HS编码列表 / 新增 |
| `/hscodes/{id}` | PUT/DELETE | 修改/删除HS编码 |
| `/warehouses` | GET/POST | 仓库列表 / 新增 |
| `/warehouses/{id}` | GET/PUT/DELETE | 仓库详情 / 修改 / 删除 |
| `/currencies` | GET/POST | 币种列表 / 新增 |
| `/currencies/{id}` | GET/PUT/DELETE | 币种详情 / 修改 / 删除 |
| `/exchange-rates` | GET/POST | 汇率列表 / 新增（兑本位币）|
| `/exchange-rates/{id}` | GET/DELETE | 汇率详情 / 删除 |
| `/exchange-rates/latest` | GET | 各币种最新汇率（业务单据换算用）|

---

## 二、采购管理 (`/api/purchase`)

### 采购订单 (`/orders`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/orders` | GET | 列表（含动态状态计算）|
| `/orders` | POST | 创建（含明细行）|
| `/orders/{id}` | GET | 详情（含明细行）|
| `/orders/{id}` | PUT | 修改 |
| `/orders/{id}` | DELETE | 删除 |
| `/orders/{id}/status` | PUT | 更新状态（审批/关闭/恢复）|

关键字段: `received_amount`, `unreceived_amount`, `invoiced_amount`, `uninvoiced_amount`, `paid_amount`, `unpaid_amount`
状态流程: 待审核 → 已审核 → 部分入库 → 待开票 → 已开票 → 部分付款 → 已付款（**动态计算**，不依赖数据库状态字段）

### 采购入库 (`/receipts`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/receipts` | GET | 列表 |
| `/receipts` | POST | 入库（更新库存+批次+状态）|
| `/receipts/{id}` | GET | 详情 |
| `/receipts/{id}` | DELETE | 取消入库（回滚库存/批次/状态）|

### 采购发票 (`/invoices`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/invoices` | GET/POST | 列表/创建（自动生成应付+进项发票）|
| `/invoices/{id}` | GET/PUT/DELETE | 详情/修改/删除（级联删除进项发票和应付）|

### 付款 (`/payments`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/payments` | GET/POST | 列表/创建（付款并核销应付）|
| `/payments/{id}` | GET/PUT/DELETE | 详情/修改/删除（回滚应付核销）|

### 应付账款 (`/ap`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/ap` | GET | 列表（汇总+明细双视图，模糊搜索）|

---

## 三、销售管理 (`/api/sales`)

### 报价单 (`/quotes`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/quotes` | GET/POST | 列表/创建 |
| `/quotes/{id}` | GET/PUT/DELETE | 详情/修改/删除 |

### 销售订单 (`/orders`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/orders` | GET/POST | 列表/创建 |
| `/orders/{id}` | GET/PUT/DELETE | 详情/修改/删除 |
| `/orders/{id}/status` | PUT | 更新状态 |

### 销售发货 (`/shipments`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/shipments` | GET/POST | 列表/创建（批次出库）|
| `/shipments/{id}` | GET/DELETE | 详情/取消出库 |

### 销售发票 (`/invoices`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/invoices` | GET/POST | 列表/创建（生成应收）|
| `/invoices/{id}` | GET/DELETE | 详情/删除（级联删除应收）|

### 收款 (`/collections`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/collections` | GET/POST | 列表/创建（收款并核销应收）|
| `/collections/{id}` | GET/DELETE | 详情/删除（回滚应收核销）|

### 应收账款 (`/ar`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/ar` | GET | 列表（汇总+明细双视图）|

---

## 四、生产管理 (`/api/production`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/productions` | GET/POST | 生产订单列表/创建 |
| `/productions/{id}` | GET/PUT/DELETE | 生产订单详情/修改/删除 |
| `/productions/{id}/processes` | GET/POST | 工序列表/派产 |
| `/productions/{id}/materials` | GET | BOM展开物料需求 |
| `/material-issues` | GET/POST | 发料记录列表/创建 |
| `/material-issues/{id}` | DELETE | 取消发料 |
| `/receipts` | GET/POST | 完工入库列表/创建（成品入库）|
| `/receipts/{id}` | GET/DELETE | 详情/取消入库 |
| `/processing-invoices` | GET/POST | 加工费发票列表/创建 |
| `/processing-invoices/{id}` | GET/DELETE | 详情/删除 |

数据表: `ProductionOrder`, `ProductionProcess`, `OutsourcingOrder`, `MaterialIssueItem`, `ProductionReceipt`, `ProcessingInvoice`

---

## 五、库存管理 (`/api/inventory`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/balance` | GET | 库存余额（数量+金额；带日期=期初+期间收发+期末） |
| `/summary` | GET | 库存汇总（按仓库/物料） |
| `/transactions` | GET | 库存流水（来源单据可穿透，按 trans_type 筛选） |
| `/trace/{batch_no}` | GET | 批次追溯（正反向追踪） |
| `/available-batches` | GET | 可用批次列表 |
| `/stocktakes` | POST/GET | 创建盘点单（自动带出仓库批次账面数）/ 列表 |
| `/stocktakes/{id}` | GET/DELETE | 盘点详情 / 删除草稿 |
| `/stocktakes/{id}/items/{item_id}` | PUT | 录实盘数（仅草稿） |
| `/stocktakes/{id}/submit` | POST | 提交盘点 → 按差异生成盘盈/盘亏流水并更新台账 |

### 收发存 v2 记账模型（2026-07-31 重构）

```
单据层            记账层(流水 trans_type)         台账层(批次)        报表
采购入库单    ──→ purchase_in                ──→ 新建批次 ──┐
采购红冲单    ──→ purchase_return_out(负)     ──→ 扣批次   ──┤
完工入库单    ──→ production_in              ──→ 新建批次 ──┤ 收发存报表
生产领料      ──→ material_issue_out         ──→ 扣批次   ──┤ (期初+收-支=期末)
委外发料      ──→ outsource_out              ──→ 扣批次   ──┤ 批次追溯
销售发货      ──→ sale_out                   ──→ 扣批次   ──┤ 毛利计算
销售退货单    ──→ sale_return_in(正)          ──→ 还批次   ──┘
盘点单        ──→ stocktake_in / stocktake_out ──→ 调批次
取消类        ──→ issue_cancel / receipt_cancel（仅限批次无下游时）
```

**核心规则**：所有反向业务记负数流水、不做物理删除 → 收发存恒等式（期初+收−支=期末）永远成立。

| 规则 | 说明 |
|------|------|
| 取消完工入库 | 批次有**任何**其他出入库（发货/盘点/退货等）→ 禁止，走销售退货 |
| 采购取消 | 仅限批次未消耗；补一条 purchase_return_out 冲销流水（保留审计） |
| 采购红冲 | 批次已消耗场景：负向红冲单 + 冲销流水；红冲量 ≤ 批次当前剩余；回退订单 received_qty/状态 + 外购型 MO 状态 |
| 销售退货 | 退回原批次、原发货成本；批次已清空则重建；回退订单 delivered_qty/状态；dashboard 毛利自动冲减 |
| 盘点 | 差异=实盘−账面；盘盈 stocktake_in / 盘亏 stocktake_out（成本=批次当前成本）；盘亏不可超账面；提交后不可改/删 |
| 完工入库成本 | 留空 = 自动结转（剩余投入×本次入库占比，最后一次全转）；可手改覆盖 |
| 发料类型 | 自产工序=material_issue_out，委外工序=outsource_out（历史流水由 migrate_inventory_v2.py 拆分） |

库存变动自动触发：采购入库/取消/红冲、销售发货/退货、生产发料/取消发料/完工入库/取消入库、盘点。

---

## 六、退税管理 (`/api/tax-refund`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/calculate` | POST | 免抵退计算 |
| `/input-invoices` | GET/POST | 进项发票列表/创建 |
| `/input-invoices/{id}` | PUT/DELETE | 修改/删除 |
| `/declarations` | GET/POST | 申报期列表/创建 |
| `/declarations/{id}` | GET/DELETE | 详情/删除（回滚发票匹配）|
| `/declarations/{id}/submit` | PUT | 申报（状态→已申报）|
| `/declarations/{id}/cancel-submit` | PUT | 取消申报（状态→待申报）|
| `/declarations/{id}/refund` | PUT | 完成退税（输入实际金额）|
| `/declarations/{id}/cancel-refund` | PUT | 取消退税 |
| `/declarations/{id}/rows` | POST | 添加明细行（自动编号+更新发票状态）|
| `/declarations/{id}/rows/{row_id}` | PUT/DELETE | 修改/删除明细行（回滚发票状态）|

状态流程: 待申报 → 已申报 → 已退税（支持取消申报/取消退税）

---

## 七、管理驾驶舱 (`/api/dashboard`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/dashboard` | GET | 仪表盘数据（现金收支/应收应付账龄/销售毛利）|
| `/dashboard/profit-detail/{product_id}` | GET | 销售毛利穿透明细 |
| `/dashboard/net-cash-detail/{month}` | GET | 净收支穿透明细（按月份）|

---

## 八、系统管理 (`/api/system`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/system/wecom` | GET/POST | 企微配置列表/创建 |
| `/system/wecom/{id}` | PUT/DELETE | 修改/删除企微配置 |
| `/system/bot` | GET/POST | AI模型配置列表/创建 |
| `/system/bot/{id}` | PUT/DELETE | 修改/删除AI配置 |
| `/system/bot/default-prompt` | GET | 默认提示词 |

---

## 九、AI 智能助手 (`/api/chat`) — v2.0.0 新增 | v2.3.0 悬浮常驻 + 权限 + 审核

> 基于 Function Calling Agent 的自然语言对话式操作，无需手动操作菜单。
> AI 助手名称: **Matsu**，入口为页面右下角全局悬浮球（任何页面可用）。

### 核心文件
- `backend/app/routers/bot_chat.py` — 对话路由 + 轻量会话管理（~70行）
- `backend/app/utils/ai_chat.py` — AI Agent 引擎（工具定义 + 权限过滤 + 执行器 + 审计 + LLM 调用）
- `backend/app/utils/crypto.py` — API Key Fernet 加密/解密
- `backend/app/models/system_config.py` — `OperationLog` 操作审计日志
- `frontend/src/components/MatsuAssistant.vue` — 全局悬浮球聊天组件（挂 Layout.vue）
- `frontend/src/composables/useBotChat.js` — 对话逻辑（悬浮组件 + 全屏页 BotChat.vue 共用）
- `frontend/src/views/system/BotChat.vue` — 全屏聊天页（备用入口，路由保留）

### 可用工具（13 个）

| 工具 | 函数 | 参数 | 所需权限 | 说明 |
|------|------|------|----------|------|
| query_entities | `_execute_query_entities` | entity_type, keyword | 按实体对应菜单 | 查询客户/供应商/物料/产品/应收/应付/发票清单 |
| query_inventory | `_execute_query_inventory` | keyword, warehouse_name | `menu:inventory` | 查当前库存（按名称/仓库汇总）|
| query_pending_approvals | `_execute_query_pending_approvals` | order_type | 内部按权限过滤 | 列待审核单据 |
| approve_order | `_execute_approve_order` | order_type, order_no | 对应菜单 | 审核采购/销售订单（销售审核联动生成生产订单）|
| unapprove_order | `_execute_unapprove_order` | order_type, order_no | `menu:purchase:orders` | 反审核采购订单 |
| query_manual | `_execute_query_manual` | keyword | 所有登录用户 | 查操作手册章节（docs/operations-manual.md 切块检索）|
| create_order | `_execute_create_order` | order_type, items[], … | 对应菜单 | 创建采购/销售订单（多明细行）|
| create_collection | `_execute_create_collection` | customer_name, amount, … | `menu:sales:collections` | 收款单 + 自动核销应收 |
| create_payment | `_execute_create_payment` | supplier_name, amount, … | `menu:purchase:payments` | 付款单 + 自动核销应付 |
| create_purchase_invoice | `_execute_create_purchase_invoice` | order_no, invoice_no, amount, … | `menu:purchase:invoices` | 录入采购发票 |
| create_sales_invoice | `_execute_create_sales_invoice` | order_no, invoice_no, amount, … | `menu:sales:invoices` | 录入销售发票 |
| issue_materials | `_execute_issue_materials` | production_order_no, material_name, quantity, … | `menu:production:orders` | 生产领料/发料 |
| production_receipt | `_execute_production_receipt` | production_order_no, quantity, … | `menu:production:orders` | 生产完工入库 |

### 权限体系（v2.3.0，A 方案：菜单权限即操作权限）
- `TOOL_PERMS` 定义每个工具（或按 entity_type/order_type 子类型）所需菜单权限码
- **双层校验**：① 发给 LLM 的 `tools` 已按权限过滤（无权限工具模型根本看不到，enum 同步裁剪）；② 执行前 `_check_tool_perm` 再校验一次
- system prompt 动态注入当前用户角色 + 可用工具清单
- 写操作工具（create_*/issue/production_receipt/approve/unapprove）落 `sys_operation_log` 审计日志（操作人/指令原文/工具/参数/结果/单据号）
- AI 建单 `created_by`/`operator` 记真实用户名（原为 "AI"）
- 审核接口（PO/SO approve）后端补 `require_permission`，UI 与 AI 同规则

### 工作流程
1. **确认意图** — AI 问清用户要做什么（下单/收款/付款/发票/发料/入库/审核）
2. **收集字段** — 一次只问一个，用户回答了再问下一个
3. **核对执行** — 列出全部字段让用户确认，用户说「对/是/确认」再执行
4. **审核类** — 先列待审核清单 → 用户指定单号 → 确认后审核

### 技术实现
- 引擎: OpenAI `tools` / `tool_choice: "auto"` 标准 Function Calling
- 模型: DeepSeek / OpenAI 兼容（通过配置的 `base_url` 切换）
- 历史管理: 保留最近 12 条消息，超时 120s，max_tokens 8192
- DeepSeek 同时返回 `content` + `tool_calls`，优先处理 `tool_calls`

### 配置
- 路径: 系统管理 → Agent设置 → 新建/编辑
- 提示词支持自定义（写入 DB，实时生效，空时使用代码默认值 `SYSTEM_PROMPT`）
- API Key 使用 `_get_api_key()` 单独解密，不修改 SQLAlchemy 模型对象，避免重复解密

---

## 十、认证权限

| 路由 | 方法 | 说明 |
|------|------|------|
| `/auth/login` | POST | 登录（返回 JWT token）|
| `/auth/me` | GET | 当前用户信息 |
| `/auth/me/permissions` | GET | 当前用户权限列表 |
| `/auth/users` | GET/POST | 用户列表/创建（**仅管理员**，v2.2.0 起 GET 也校验权限）|
| `/auth/users/{id}` | GET/PUT/DELETE | 详情/修改/删除（**仅管理员**）|
| `/auth/roles` | GET/POST | 角色列表/创建（**仅管理员**，v2.2.0 起 GET 也校验权限）|
| `/auth/roles/{id}` | GET/PUT/DELETE | 详情/修改/删除（**仅管理员**）|
| `/auth/permissions` | GET | 权限定义列表（**仅管理员**，v2.2.0 起校验权限）|

权限模型: 基于角色的菜单级权限，角色按岗位配置（销售经理/采购经理/生产经理/财务经理/库管员），每个角色勾选可见菜单。

> **v2.2.0 权限收紧**：用户/角色/权限的 4 个查询接口（GET /users、/users/{id}、/roles、/permissions）从"仅登录"收紧为"仅管理员"（`require_permission("menu:system:users")`）。各业务角色（销售/采购/生产/财务/库管员/只读）不含系统管理权限，访问返回 403；前端菜单本身也不对非管理员显示系统管理入口。

> **v2.2.0 菜单级权限落地（前端）**：Layout 侧边栏 32 个菜单项 + 7 个分组按当前用户权限过滤（无权限的分组整组隐藏）；路由守卫校验 `meta.perm`，直接输 URL 访问无权限页面会被重定向回工作台并提示。权限清单与真实菜单已对齐（33 个权限码 = 32 菜单项 + 工作台）。

---

## 十一、关键业务逻辑

### 增值税计算
- 不含税金额 = 含税金额 / (1 + 税率/100)
- 税额 = 不含税金额 × 税率/100
- 含税金额 = 数量 × 单价

### 采购订单状态动态计算
```
待审核 → 已审核 → 部分入库 → 待开票 → 已开票 → 部分付款 → 已付款
```
在列表接口中实时计算，不依赖数据库状态字段。动态覆盖规则：
- 部分入库：部分收料且未全部收料
- 待开票：全部收料但未开票
- 已开票：已开票但未付款
- 部分付款：部分付款
- 已付款：全额付款

### 退税申报流程
```
待申报 → (申报) → 已申报 → (已退税) → 已退税
   ↑                          ↓
   └── (取消申报)      (取消退税)
```
- 待申报：可修改/删除/申报
- 已申报：可取消申报/已退税/查看详情
- 已退税：可取消退税/查看详情
- 实际退税金额在"已退税"时录入

### 采购发票同步
- 创建采购发票时自动：生成应付账款 + 进项发票（状态"未匹配"）
- 发票添加进申报详情时：进项发票→"已匹配"，采购发票→"已匹配(退税)"
- 删除申报/明细行时：回滚发票状态

### 成本流转
```
物料采购 → 生产领用 → 加工费用 → 成品入库 → 销售出库 → 毛利分析
```
全程自动核算，无需手工算账。入库时即计算单位成本 = (材料成本+加工费) / 数量。

---

## 十二、开发规范

### 字段命名
- 后端传输: snake_case
- 前端 `request.js` 拦截器: 不做响应键转换
- Pydantic schema `from_attributes = True`

### 前端金额/数量格式化
- `$fm(value)` — 金额 `¥1,234,567.89`
- `$fq(value)` — 数量 `1,234.5678`

### 版本管理
- 格式: x.x.x（z=小修改/bug修复，y=功能更新，x=大重构）
- 每次提交需更新 README、产品说明、操作手册、one-pager

### AI 引擎开发注意
- `tool_calls` 优先于 `content` 处理（DeepSeek 兼容）
- 重建 assistant 消息时保留原始 `content` 字段
- API Key 用 `_get_api_key()` 解密，不修改 SQLAlchemy 模型
- 历史截断保留最近 12 条
- 超时 120s，max_tokens 8192，`tool_choice: auto`

### 数据库重置
```
kill 后端进程 → rm backend/data/* → 重启后端 → 运行 init_all.py
```
⚠ 重置会清空 AI 配置中的 API Key，需重新配置

### 测试流程
1. 重置DB → 验证后端API → 验证前端页面 → 验证 AI 助手

---

## 十三、版本变更记录

### v2.2.0 (2026-07-31)
- **新功能**: 自动化测试体系（阶段 0-5）— 契约测试 / 状态机测试 / 边界数据测试 / 架构检查 / E2E（Playwright 真实浏览器）
- **新功能**: CI 持续集成（.github/workflows/ci.yml 三 job：后端 187 测试 + 前端构建 + E2E 34 测试）
- **修复**: BUG#1 采购入库 500（po_receipt_item 支持成品：加 product_id 列、material_id 可空、删除回滚双路径）
- **修复**: GET /auth/users 等 4 个接口加权限校验（仅管理员可访问用户/角色/权限）
- **清理**: 委外残留（Outsourcings/ProductionReceipts 页面、mo_outsourcing 表、AI 工具 create_outsourcing 9→8）
- **清理**: 12 个"定义了但后端没有"的 API（crudApi 方法子集对齐）
- **规范**: 17 页面 109 处散写 request 全部迁移到 api/*.js 封装（97 处迁移 + 散写清零）
- **规范**: Pydantic class Config → model_config = ConfigDict（44 处）
- **规范**: 删除库存盘点 2 个未开发表（inv_stock_check 等）
- **测试**: 测试报告 docs/test-report-1.md（最终版）+ docs/test-plan.md

### v2.1.0 (2026-07-30)
- **新功能**: AI 采购/销售订单支持多明细行一次创建 — `create_order` 工具参数从单行字段升级为 `items` 数组，AI 可一句指令创建含多种物料的采购单或含多种产品的销售单
- **架构**: `create_order` 函数参数从 `material_name`/`product_name`/`quantity`/`unit_price` 独立字段升级为 `items[]` 数组（每个元素含名称+数量+单价）
- **UI**: 无前端变更

### v2.0.1 (2026-07-29)
- **新功能**: AI 助手查询字段扩展（支持客户/供应商/物料/产品多字段模糊搜索）
- **修复**: DeepSeek `tool_calls` 格式兼容 + 历史截断防孤立 tool 消息
- **基础设施**: `seed_foundation.py` 重写 + `init_all.py` 优化

### v2.0.0 (2026-07-27)
- **新功能**: AI 智能助手 Matsu — 基于 Function Calling Agent 的自然语言对话式操作
- **新功能**: 支持 9 个工具（查询/创建订单/收款/付款/发票/委外/发料/入库）
- **UI**: 新增 BotChat.vue 聊天界面，支持 Markdown 表格渲染
- **UI**: 产品文档三件套（产品概述/操作手册/一页纸营销页）
- **基础设施**: API Key Fernet 加密存储，自定义提示词支持
