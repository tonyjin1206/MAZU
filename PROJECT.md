# Mazu Trade System (MTS) — 项目文档

> **v2.5.0** | A Lightweight Trade Management Platform

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

### 采购需求 (`/requisitions`，v2.5.0 外购直采流程)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/requisitions` | GET | 列表（按状态/关键词筛选）|
| `/requisitions/{id}` | GET | 详情 |
| `/requisitions/{id}/close` | POST | 关闭（仅待处理）→ MO 回待采购可重推 |
| `/requisitions/{id}/to-purchase` | POST | 转采购订单（采购填供应商/单价/税率，数量可改）|

状态流程: 待处理 → 已转单 → 采购入库完成 → MO 已入库；待处理可关闭 → MO 回待采购

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
| `/productions/{id}/set-type` | POST | 确认备货方式（自产/委外/外购，v2.5.0）|
| `/productions/{id}/to-requisition` | POST | 外购型推采购需求（v2.5.0）|

数据表: `ProductionOrder`（含 `production_type` 备货方式）, `ProductionProcess`, `OutsourcingOrder`, `MaterialIssueItem`, `ProductionReceipt`, `ProcessingInvoice`

备货方式（v2.5.0）: MO 审核后状态=`待确认`，必须先确认备货方式 → 自产/委外=`待排产`（进工作台）｜外购=`待采购`（推采购需求 → 采购转单 → 入库联动）

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
| 销售退货 | 退回原批次、原发货成本；批次已清空则重建；回退订单 delivered_qty/状态；dashboard 毛利自动冲减；已开票→提示全额红冲发票（红字发票+红字应收等额联动）；已收款→负数收款单（退款）核销红字应收；已报税→打标 refund_declared、退税冻结、次月负数申报冲减 |
| 发票红冲 | 全额红冲（不可部分/不可干预金额）：红字发票手工录入（票号来自开票系统），原票标已红冲，自动生成等额红字应收；红字发票禁改/禁删；开票校验 ≤ 未开票金额（SUM 含红字负数，红冲后额度自动返还 → 补开新票） |
| 核销转移 | 红字应收负余额 → 同客户正余额应收（`ar_adjustment` 表，无收款单参与）；跨客户/超上限拒绝；收款↔应收核销关系表保持纯语义不动；可撤销（`POST /ar/transfer/{id}/cancel` 回滚两端账务并删除调整记录，目标已收不足时拦截） |
| 退款（负数收款单） | 金额为负=退款；核销红字应收负余额向 0 靠拢；退超拦截；删除退款单自动回滚；不自动生成退款（线下办理） |
| 收款/付款单审核 | `reviewed` 字段（ar_collection/ap_payment）；审核=财务确认标记+审核人/时间；审核后 PUT/DELETE 全锁（仅可取消审核）；`POST /collections/{id}/review|unreview`、`POST /payments/{id}/review|unreview` |
| 应收/应付明细 | 以单据为行（`/ar/collection-detail`、`/ap/payment-detail`）：核销/收款/转移汇总金额 + flows 行级流水；应收余额=应收−核销转移−收款、应付余额=应付−付款 |
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
| `/declarations/{id}/rows` | POST | 添加明细行（自动编号+更新发票状态；`input_invoice_id` 可空 → 支持负数行）|
| `/declarations/{id}/rows/{row_id}` | PUT/DELETE | 修改/删除明细行（回滚发票状态）|
| `/declarations/{id}/return-candidates` | GET | 已报税退货单候选（负数申报取数，未添加过）|
| `/declarations/{id}/return-adjustments` | POST | 添加退货冲减负数行（自动重算出口FOB金额+免抵退结果）|
| `/customs-for-refund` | GET | 待退税报关单**商品行**（v2.6.0 按商品行粒度，一票多商品多HS）|
| `/declaration-details` | POST | 添加申报明细（`customs_item_id` 从报关单商品行带出商品/HS/数量/金额）|
| `/declarations/{id}/rows` | POST/PUT/DELETE | 申报明细行**双端匹配**（`input_invoice_id` 进项发票 + `customs_item_id` 报关单商品行，各自去重；出口FOB自动重算=行汇总）|

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

## 十二·五、合作分支现状与合并规划（2026-08-02 记录）

> 状态：合作者（woiszxf）单独开发线路，未完工前**不做代码合并**。本文档记录分支现状、
> 功能差距评估与合并建议，供后续版本更新与合并时参考。

### 分支全景

| 分支 | 更新时间 | 版本 | 状态 |
|---|---|---|---|
| `main` | 2026-08-01 | v2.5.0 | 主干 |
| `app-optimization` | 2026-08-02 | **v2.5.1** | 当前开发线（AI 修复 + 测试库隔离） |
| `Sales_Purchase` | 2026-08-02 | v2.1.0 | **合作者分支**（44 提交、65 文件、+6417 行，几乎全前端） |
| `cost-calculation` | 2026-07-27 | — | 已合入 main，本地残留可删 |
| `sale_order_update` | — | — | 远程已删（gone），本地残留可删 |

拓扑：`d2724bf(v2.1.0)` → `main(v2.5.0)` → `app-optimization(v2.5.1)`；`Sales_Purchase` 从 v2.1.0 分出，独立走 44 提交。

### Sales_Purchase 内容（前端改造为主）

- **可复用资产**：`ColumnSettingsDialog.vue`（列设置弹窗）、`ColumnOrderDialog.vue`、`useColumnCustomize.js`（列显隐记忆）、`useColumnDrag.js`（表头拖拽，依赖 sortablejs）、`useColumnAutoFit.js`（列宽自适应）；后端 `SystemParam` 模型（fd_system_param 表）+ 5 个 /params/* 路由 + SystemParams.vue（参数设置模块）
- **业务改造**：订单页主从联动布局（08f1249/bb270b7）、业务模型"无工厂双业务"（de59a16）、委外页面改造（7 提交）

### 功能差距评估结论

| 分类 | 功能 | 结论 |
|---|---|---|
| 🟢 已覆盖 | 自动编码(CU/SU/RM/PR)、列排序、列头筛选、合计栏、单据号/批次规范 | v2.5.1 已有，不移植 |
| 🔴 值得移植 | **参数设置模块**（SystemParam 表+路由+SystemParams.vue，v2.5.1 完全缺失，下拉硬编码） | P0 |
| 🔴 值得移植 | **列设置弹窗**（勾选显隐+顺序+恢复默认，v2.5.1 无） | P1（试点 2-3 页） |
| 🟡 可选 | 列宽自适应（useColumnAutoFit） | P2 |
| ⛔ 不移植 | 列拖拽（依赖 sortablejs+动态列，与 v2.5 静态列冲突）、委外页面（v2.4 已删）、无工厂双业务模型（与备货方式冲突） | — |

### 合并建议（待合作者完工后执行）

1. **不建议整体 merge**：Sales_Purchase 基线 v2.1.0 过旧，65 文件冲突 + 委外废弃代码复活 + 业务模型方向冲突
2. **推荐方案**：功能移植（cherry-pick）——P0 参数设置模块 → P1 列设置弹窗试点 → P2 列宽自适应
3. 移植时注意 v2.5 前端为**静态列**架构，列设置类功能需先列定义数组化

---

## 十三、版本变更记录

### v2.5.1 (2026-08-02)
- **修复**: AI 助手工具执行器对齐 v2.5 业务 — ① 单据单号撞号（create_order 的 generate_doc_no 补 model 参数，PO/SO 不再与已有单据重复）② 收款单号 RC→CR、付款单号 PAY→PM 与系统规范对齐 ③ AI 发料走批次库存（扣库存+流水+工序状态，此前只插记录库存不变）④ AI 完工入库走成品批次（FG 批次号+成品仓+流水+状态更新）
- **修复**: Agent 提示词与工具同步 — DB `sys_bot_config.system_prompt` + schemas `DEFAULT_SYSTEM_PROMPT` 补齐 13 工具清单与权限规则，移除已删除的 create_outsourcing 委外残留；BotChat 欢迎语去委外示例改查库存；chat/reset 请求体补空对象修复 422
- **规范**: 测试库隔离（强制）— conftest.py 导入前设 ERP_DATA_DIR=临时目录，pytest 不再触碰开发库（历史踩坑：测试曾清空开发库致 AI 配置丢失）；README「测试数据规范」+ product-overview「14.4 数据存储与测试库隔离」新增规范章节
- **测试**: test_bot_agent.py 新增 15 个 AI 执行器回归测试（单号前缀/收付款/发票/发料扣库存/完工入库/库存不足/错误供应商），全套后端 224 测试全绿
- **UI**: AI 悬浮球对话框加宽 380→440px、加高 62vh→70vh、消息字体 12.5→11.5px
- **基础设施**: 新增 scripts/sync_bot_prompt.py（DB 提示词同步最新版）；docs/ai-capability-test-report.md（AI 能力全量测试报告）

### v2.5.0 (2026-07-31)
- **新功能**: 备货方式确认（生产订单 `production_type`: 自产/委外/外购）— MO 审核后先确认备货方式才能继续；外购型不进入生产工作台，仅推采购需求
- **新功能**: 外购直采流程 — 生产推采购需求（PR，只填数量）→ 采购「采购需求」页转采购订单（填供应商/单价/税率）→ 入库联动 MO 状态；PR 可关闭、MO 可重推；删除 PO 联动 PR/MO 状态回退
- **新功能**: 采购订单支持成品采购（`po_order_item.product_id` 与 material_id 互斥）+ 产品「是否可外购」标记（can_purchase，MO 确认外购自动打勾）+ 选品下拉合并原材料与可外购成品
- **新功能**: 委外商简化 — 删除独立委外商表（fd_outsourcer），供应商类型=委外 即委外商；工序 outsourcer_id 改指 fd_supplier.id
- **新功能**: 汇率自动获取与维护 — 币种/汇率独立菜单；腾讯财经 qt.gtimg.cn 国内源自动拉取（无 key）+ 每日 09:00 定时任务 + 手动按钮；JPY/KRW 无交叉盘手动兜底；`GET /exchange-rates/latest` 供业务单据换算
- **新功能**: 盘点管理独立菜单 + 独立权限码（menu:inventory:stocktake）— 盘点明细可新增/编辑/删除物料行（含账外批次），同批次重复 400，已提交锁定
- **新功能**: 仓库维护界面（Warehouses.vue + menu:warehouses 权限闭环）
- **修复**: 出入库仓库参照校验（采购入库/完工入库/销售出库/盘点建单校验 warehouse_id 存在且启用）
- **修复**: 仓库/部门/员工/币种/贸易术语编辑 422（register_crud 无 update_schema 时 PUT body 兜底）
- **修复**: _seed_rbac admin 权限翻倍 bug（autoflush=False 下补权限前 db.flush）+ 角色关联去重
- **重构**: 测试数据基建 v2 — build_foundation 统一构建器（API 建真实档案）+ conftest 复用 _seed_rbac 单一数据源 + 状态机文档池 + 数据量 -78%

### v2.4.0 (2026-07-31)
- **新功能**: 库存收发存 v2 — 盘点闭环（盘盈/盘亏流水）/ 采购红冲（负向红冲单 + 冲销流水）/ 销售退货（回库流水）/ 发料类型拆分（material_issue_out vs outsource_out）/ 完工入库成本自动结转
- **新功能**: 采购红冲量 ≤ 批次当前剩余；回退订单 received_qty/状态 + 外购型 MO 状态联动
- **修复**: 取消完工入库保护（批次有后续出入库 → 禁止，走退货）；采购取消入库补冲销流水
- **修复**: 收发存报表多批次合并取最新批次号；新流水类型（红冲/退货/盘点）纳入期初+收发+期末口径
- **基础设施**: scripts/migrate_inventory_v2.py 迁移脚本（幂等）

### v2.3.0 (2026-07-31)
- **新功能**: AI 助手全系统化 — 菜单页改全局右下角悬浮球（M 图标），任意业务页面对话；操作能力扩展（查档案/查库存/建单/审核/收付款/发票/发料/完工入库）；工具执行受菜单权限控制 + 操作全程留痕
- **新功能**: AI 助手可检索 docs/operations-manual.md 回答操作问题
- **新功能**: 菜单级权限前端落地 — Layout 菜单按权限过滤（32 菜单项 + 7 分组）+ 路由守卫 meta.perm 校验；权限清单与真实菜单对齐（补 6 缺失权限码）；用户/角色/权限管理接口仅管理员

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
