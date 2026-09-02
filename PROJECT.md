# Mazu Trade System (MTS) — 项目文档

> **v2.8.0** | A Lightweight Trade Management Platform

Python FastAPI + Vue 3 (Element Plus) + SQLite 的外贸企业 ERP 系统，覆盖采购、销售、委外、退税、库存等核心业务模块。
**支持 AI 智能助手（Matsu）自然语言对话式操作。**
**销售订单审核后两路分流：转直采（买成品，唯一关联采购订单的路线）/ 转外发（委外加工，不关联采购——材料独立采购入库、领料出库时成本挂销售单）。生产管理已下线（2026-09）。**

> 后端: FastAPI (端口 8788)
> 前端: Vue 3 + Vite (端口 5173)
> 数据库: SQLite (`backend/data/erp.db`)
> 认证: JWT (默认 admin / admin123)
> AI 引擎: Function Calling Agent (OpenAI / DeepSeek 兼容)
> API Key: Fernet 加密存储 (`backend/.encryption_key`)

## 运行时架构总览

> v2.8.0 统一展示入口。架构图见 `docs/erp-architecture.html`（Archify 生成，可浏览器打开查看运行时架构）。

```
┌────────────────────────────────────────────────────────────────┐
│                      前端 Vue 3 / Vite (5173)                   │
│  Layout(侧边菜单+顶部栏) · Matsu悬浮球 · 业务页面 · 列设置/主从   │
└───────────────────────────┬────────────────────────────────────┘
                            │ REST API (axios / request.js)
┌───────────────────────────▼────────────────────────────────────┐
│                      后端 FastAPI (8788)                        │
│  /api/auth  /api/foundation  /api/purchase  /api/sales         │
│  /api/production(批次追溯)  /api/outsource(委外)  /api/inventory  │
│  /api/tax-refund  /api/dashboard  /api/system  /api/chat       │
└───────────────────────────┬────────────────────────────────────┘
                            │ SQLAlchemy ORM
┌───────────────────────────▼────────────────────────────────────┐
│                     SQLite (backend/data/erp.db)               │
│  基础档案/采购/销售(两分支)/委外/库存/退税/系统/RBAC（mo_* 历史保留）│
└────────────────────────────────────────────────────────────────┘
```

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

### 采购需求 (`/requisitions`，**已停造**：推式入口随生产管理下线，仅存列表/关闭/转采购接口读存量)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/requisitions` | GET | 列表（按状态/关键词筛选）|
| `/requisitions/{id}` | GET | 详情 |
| `/requisitions/{id}/close` | POST | 关闭（仅待处理）|
| `/requisitions/{id}/to-purchase` | POST | 转采购订单（采购填供应商/单价/税率，数量可改）|

状态流程: 待处理 → 已转单 / 已关闭（新需求不再产生）

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
| `/orders/{id}` | GET/PUT/DELETE | 详情/修改/删除（仅待审核可改/删）|
| `/orders/{id}/approve` | POST | 审核（审核后明细行置「未生产」，**不再自动生成生产订单**，v2.8.0） |
| `/orders/{id}/items/{item_id}/stock-in` | POST | **转直采（买成品）**：推送至「销售订单转采购」，明细行→已通知入库 |
| `/orders/{id}/items/{item_id}/outsource` | POST | **转外发**：推送至「销售订单转委外」，明细行→已通知外发 |
| `/orders/{id}/items/{item_id}/re-produce` | POST | **转生产**：后端端点保留（前端入口已随生产管理下线移除），生成生产订单，明细行→生产中 |
| `/orders/{id}/items/{item_id}/claim-batch` / `unclaim-batch` | POST | 认领/解绑备货批次（场景2：货先进来，后期挂销售单） |
| `/orders/{id}/items/{item_id}` | PUT | 变更明细行（改数量/单价/停售） |
| `/order-items` | GET | 明细行列表（含生产状态筛选，独立视图） |

> **两路分流（转直采 / 转外发，互斥）**：销售订单审核后，明细行按业务实际选一条路线——**只有转直采行关联采购订单**（按成品采购，无视 BOM）；转外发行**不关联采购订单**，材料由采购员独立填写采购订单入库，委外领料出库时成本挂销售单。转生产入口已随生产管理下线从界面移除（后端 re-produce 端点保留）。

### 销售发货 (`/deliveries`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/deliveries` | GET/POST | 列表/创建（批次出库）|
| `/deliveries/notify` | POST | **通知发货**：只登记数量（待出库），不扣库存（两步化第一步）|
| `/deliveries/{id}/issue` | POST | **库管出库**：选批次数量扣库存，delivered_qty 累计（两步化第二步）|
| `/deliveries/outs` | GET | 成品出库列表（库管，带出库记录穿透）|
| `/deliveries/{id}/issue-return` | POST | 成品出库退回（库管红冲）|
| `/deliveries/return` | POST | 销售退货 |
| `/deliveries/{id}/return` | POST | 销售退货（按发货单）|
| `/deliveries/{id}` | GET/DELETE | 详情/取消出库 |

### 销售发票 (`/invoices`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/invoices` | GET/POST | 列表/创建（生成应收；支持红字，`red_of_invoice_id` 全额负数红冲，v2.6.0） |
| `/invoices/{id}` | GET/DELETE | 详情/删除（级联删除应收；红字票禁改禁删、已红冲蓝字票禁删，v2.6.0） |
| `/invoices/{id}` | PUT | 修改（**红字票禁改**，v2.6.0） |

### 收款 (`/collections`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/collections` | GET/POST | 列表/创建（收款并核销应收；`amount<0` = 退款登记核销红字应收，v2.6.0） |
| `/collections/{id}` | GET/DELETE | 详情/删除（回滚应收核销） |

### 应收账款 (`/ar`)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/ar` | GET | 列表（汇总+明细双视图；含 `is_red` 红字应收，v2.6.0） |
| `/ar/transfer` | POST | **核销转移**：红字应收(负)→同客户正余额应收，写 `ar_adjustment` 审计（v2.6.0） |
| `/ar/transfer/{adj_id}/cancel` | POST | **撤销核销转移**：回滚两端账务并删除调整记录（v2.6.0） |
| `/ar/{ar_id}/cancel-collection` | POST | 按应收 id 撤销收款 |
| `/ar/collection-detail` | GET | 应收账款收付款明细（应收×收款配对） |

> **v2.6.0 销售退货财务层**：发票红冲（全额负数红字票 + 自动生成红字应收 `is_red`）、退款（负数收款核销红字应收）、核销转移（红字→正余额账务清理）、退货联动（已开票提示红冲、已报税打标 `refund_declared`）、负数申报（已报税退货 → 次月申报冲减）。详见 CHANGELOG v2.6.0。

---

## 四、生产管理 (`/api/production`) — **已下线（2026-09）**

> **2026-09 生产管理下线**：生产订单/生产工作台/生产详情/加工费发票的页面与 `/productions*`、`/workspace`、`/processing-invoices*` 端点已全部删除；`menu:production:orders/workspace/invoices/receipts` 权限码挂 `DEPRECATED_PERMS` 启动时清理。仅保留**批次追溯**两个端点（菜单挪入库存管理，路由 `/inventory/batch-trace`）。`mo_*` 数据表与模型**完整保留**（历史数据可追溯）；`sales.py` 转直采/转外发中的活跃生产订单拦截逻辑保留（历史 MO 仍有效拦截）；`re-produce` 端点保留但前端入口已移除。

| 保留的路由 | 方法 | 说明 |
|------|------|------|
| `/inventory/batch` | GET | 批次库存查询（perm: menu:production:batch / menu:inventory）|
| `/inventory/trace` | GET | 批次追溯（按 batch_no 正反向追踪）|

已下线端点（原 `/productions*` 列表/详情/备货方式/展开BOM/派产/发料/完工/完工入库/关闭、`/workspace`、`/processing-invoices*`）不再可用。

---

## 五、委外管理 (`/api/outsource`)

> **v2.8.0 归口**：委外业务统一归口**转外发**（销售明细转外发）。委外订单分工序、每道工序可指定加工商（供应商类型=委外即委外商）。

| 路由 | 方法 | 说明 |
|------|------|------|
| `/orders` | GET | 委外订单列表 |
| `/orders/{id}` | GET/PUT | 委外订单详情/修改 |
| `/orders/{id}/approve` / `unapprove` | POST | 审核（生成应付+末道待入库单）/ 取消审核 |
| `/orders/{id}` | DELETE | 删除（材料自动退回原批次）|
| `/sales-to-outsource` | GET | 销售转外发列表 |
| `/sales-to-outsource/{item_id}` | GET | 转外发明细行详情 |
| `/sales-to-outsource/{item_id}/return` | POST | 转外发退回（明细行解锁）|
| `/sales-to-outsource/{item_id}/complete` / `uncomplete` | POST | 完成委外/取消完成 |
| `/orders/from-sales` | POST | 从销售转外发生成委外订单 |
| `/orders/from-sales-process` | POST | 从销售转外发按工序生成委外订单 |
| `/claims` | GET/POST | 领料列表/创建（订单级，按仓库总数量 FIFO 扣批次，出库流水挂销售单；原「认领原料」）|
| `/claims/{claim_id}` | DELETE | 删除领料（材料退回原批次）|

> **供料方式（`supply_type`）**：己方提供（需**领料**——领的是原料库库存，领料量按 委外数量×BOM用量×(1+损耗%)，出库流水挂销售单号归集成本；材料来自独立材料采购）/ 包工包料（加工厂提供，不领料、不出库）。委外订单审核后仅末道工序生成成品待入库单（中间工序只记加工成本）。委外路线**不关联采购订单**。

---

## 七、库存管理 (`/api/inventory`)

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

## 八、退税管理 (`/api/tax-refund`)

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
| `/declarations/{id}/rows` | POST | 添加明细行（自动编号+更新发票状态） |
| `/declarations/{id}/rows/{row_id}` | PUT/DELETE | 修改/删除明细行（回滚发票状态） |
| `/declarations/{id}/return-candidates` | GET | **负数申报候选**：已报税退货单清单（`refund_declared=1` 且关联报关单，v2.6.0） |
| `/declarations/{id}/return-adjustments` | POST | **添加退货冲减负数行**（出口货物退运，自动重算出口金额与免抵退结果，v2.6.0） |

状态流程: 待申报 → 已申报 → 已退税（支持取消申报/取消退税）

---

## 九、管理驾驶舱 (`/api/dashboard`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/dashboard` | GET | 仪表盘数据（现金收支/应收应付账龄/销售毛利）|
| `/dashboard/profit-detail/{product_id}` | GET | 销售毛利穿透明细 |
| `/dashboard/net-cash-detail/{month}` | GET | 净收支穿透明细（按月份）|

---

## 十、系统管理 (`/api/system`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/system/wecom` | GET/POST | 企微配置列表/创建 |
| `/system/wecom/{id}` | PUT/DELETE | 修改/删除企微配置 |
| `/system/bot` | GET/POST | AI模型配置列表/创建 |
| `/system/bot/{id}` | PUT/DELETE | 修改/删除AI配置 |
| `/system/bot/default-prompt` | GET | 默认提示词 |
| `/system/reminder-rules` | GET/POST | 预警提醒规则列表/创建（管理端，v2.7.0） |
| `/system/reminder-rules/{id}` | PUT/DELETE | 修改/删除提醒规则（管理端，v2.7.0） |

### 预警提醒与站内通知 (`/api/notifications`，v2.7.0)

> 站内为主（`sys_notification` 落库即视为已发）；规则配置化（`sys_reminder_rule`，D8）。企微通道为预留钩子（未启用）。

| 路由 | 方法 | 说明 |
|------|------|------|
| `/notifications` | GET | 当前用户通知列表（未读优先，分页） |
| `/notifications/unread-count` | GET | 未读数（铃铛红点） |
| `/notifications/latest` | GET | 最近 N 条（工作台/铃铛；`only_unread`） |
| `/notifications/{id}/read` | PUT | 标记已读（仅本人） |
| `/notifications/read-all` | PUT | 全部已读 |
| `/notifications/admin-query` | GET | 管理端全量查询（按 user_id/role_code/point_code/doc_type 筛选） |

**事件埋点（sales.py，v2.8.0 三分支）**：SO_APPROVED / SO_TO_PURCHASE / SO_TO_OUTSOURCE / SO_TO_PRODUCTION（转生产=自产）/ DELIVERY_NOTIFIED / DELIVERY_CONFIRMED / AR_CREATED（双收件人）
**定时预警（每日 09:00 + 启动补扫）**：AR_DUE_SOON / AR_OVERDUE / AP_DUE_SOON / AP_OVERDUE（红字应收不参与）

---

## 十一、AI 智能助手 (`/api/chat`) — v2.0.0 新增 | v2.3.0 悬浮常驻 + 权限 + 审核

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

### 可用工具（11 个）

| 工具 | 函数 | 参数 | 所需权限 | 说明 |
|------|------|------|----------|------|
| query_entities | `_execute_query_entities` | entity_type, keyword | 按实体对应菜单 | 查询客户/供应商/物料/产品/应收/应付/发票清单 |
| query_inventory | `_execute_query_inventory` | keyword, warehouse_name | `menu:inventory` | 查当前库存（按名称/仓库汇总）|
| query_pending_approvals | `_execute_query_pending_approvals` | order_type | 内部按权限过滤 | 列待审核单据 |
| approve_order | `_execute_approve_order` | order_type, order_no | 对应菜单 | 审核采购/销售订单（销售审核不自动生成生产订单，明细行走三分支，v2.8.0）|
| unapprove_order | `_execute_unapprove_order` | order_type, order_no | `menu:purchase:orders` | 反审核采购订单 |
| query_manual | `_execute_query_manual` | keyword | 所有登录用户 | 查操作手册章节（docs/operations-manual.md 切块检索）|
| create_order | `_execute_create_order` | order_type, items[], … | 对应菜单 | 创建采购/销售订单（多明细行）|
| create_collection | `_execute_create_collection` | customer_name, amount, … | `menu:sales:collections` | 收款单 + 自动核销应收 |
| create_payment | `_execute_create_payment` | supplier_name, amount, … | `menu:purchase:payments` | 付款单 + 自动核销应付 |
| create_purchase_invoice | `_execute_create_purchase_invoice` | order_no, invoice_no, amount, … | `menu:purchase:invoices` | 录入采购发票 |
| create_sales_invoice | `_execute_create_sales_invoice` | order_no, invoice_no, amount, … | `menu:sales:invoices` | 录入销售发票 |

> 原 `issue_materials`（生产领料/发料）、`production_receipt`（生产完工入库）两个工具已随生产管理下线删除（2026-09）。

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

## 十二、认证权限

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

## 十三、关键业务逻辑

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
材料采购 → 原料入库（零关联销售单）→ 委外领料出库（成本挂销售单）→ 成品入库 → 销售出库 → 毛利分析
成品直采：采购订单（挂销售明细）→ 成品入库 → 销售出库 → 毛利分析
```
全程自动核算，无需手工算账。采购入库即按订单单价记批次成本；委外领料按批次 FIFO 成本出库并归集到销售单。

---

## 十四、开发规范

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

## 十五、版本变更记录

### 2026-09-02 认领材料改造（Sales_Purchase → main 合并）
- **转直采无视 BOM**：销售订单转采购只列「转直采」行，按成品数量×(1+损耗) 采购成品本身（`_so_row_requirements` 恒返回成品），不再按 BOM 展开材料行
- **材料采购完全独立**：材料采购与原料入库零关联销售单（明细不挂 `sales_item_id`）；委外领料出库时才按 FIFO 挂销售单归集成本
- **「认领原料」改「领料」**：委外模块文案与语义统一（机制不变：FIFO 扣原料库存 + 出库流水挂销售单）
- **删生产管理**：前端删生产订单/工作台/详情/加工费发票 4 页面；后端 `production.py` 仅保留批次追溯端点；`schemas/production.py` 删除；`menu:production:orders/workspace/invoices/receipts` 挂 `DEPRECATED_PERMS`；销售订单页「转生产」入口与 AI 发料/完工入库工具删除；`mo_*` 表与模型保留
- **批次追溯挪库存管理**：`views/production/BatchInventory.vue → views/inventory/`，新路由 `/inventory/batch-trace`
- **测试对齐**：后端 221 用例（删 MO 状态机/生产收发存用例，重写转直采全流程用例）；e2e 冒烟页面清单更新；详见根目录 `CHANGES-20260901.md`

### v2.8.0 (2026-08-29)
- **销售订单三路分流（三分支）**：订单审核后明细行独立走转直采/转外发/转生产-自产，三者互斥；审核不再自动生成生产订单
- **生产模块去委外化**：生产订单（`mo_production`）= 纯自产，剥离委外商/委外工序/委外发料/委外加工费；`ProductionProcess` 移除 `outsourcer_id`；`production_type` 仅自产/外购
- **委外归口转外发**：新增 `/api/outsource` 委外管理模块（销售订单转委外/委外订单/认领原料/加工费发票）；供料方式（己方提供/包工包料）订单级
- **权限隔离**：三分支写端点按业务域授权（转直采=销售本域、转外发=销售+委外域、转生产=销售+生产自产域）；读端点「本域+业务引用域」授权（`require_any_permission`）
- **AI 助手**：销售审核不再自动生成生产订单，改为三分支引导；`issue_materials` 去委外语义
- **预警埋点**：新增 `SO_TO_PRODUCTION`；事件提醒点完整对齐三分支
- **数据库迁移**：`scripts/migrate_production_deoutsourcing.py`（去遗留 `outsourcer_id` 列，幂等/保数据/空库安全）
- **测试**：`test_three_branch.py`（10 用例）+ `test_migration_production.py`（4 用例）；`./test.sh` 259 passed / e2e 59 passed

### v2.7.0 (2026-08-27)
- **批4 预警提醒系统（按当前产品逻辑重校，销售订单下游走三分支）**：
  - **通知内核**：`sys_notification` 表 + `routers/notification.py`（列表/未读数/最新/标记已读/全部已读/管理端全量查询）；站内为主，落库即视为已发（D7）
  - **规则配置化**：`sys_reminder_rule` 表 + `services/reminder.py`（notify/渲染/角色收件人/去重）；`/api/system/reminder-rules` CRUD（D8）
  - **事件埋点 6 处（sales.py）**：SO_APPROVED / SO_TO_PURCHASE / SO_TO_OUTSOURCE / DELIVERY_NOTIFIED / DELIVERY_CONFIRMED / AR_CREATED（双收件人）；**以 SO_TO_PURCHASE / SO_TO_OUTSOURCE 替代原 MO_PLANNED / MO_OUTSOURCED**
  - **定时预警**：AR_DUE_SOON / AR_OVERDUE / AP_DUE_SOON / AP_OVERDUE，每日 09:00 扫描 + 启动补扫（D4）；红字应收不参与
  - **前端**：顶部铃铛（未读红点+消息弹层+跳转）；`system/Notifications.vue`（通知查询+提醒规则两页签）；系统管理菜单「通知管理」
  - **测试/基建**：`test_reminders.py` 6 场景；全量 113 passed；`test.sh` 隔离测试库（不复用陈旧 erp.db）；`reset_local_db` KEEP 补 `sys_reminder_rule`/`sys_notification`
- **模型**：新建 `sys_reminder_rule`、`sys_notification`；迁移脚本 `scripts/migrate_batch4_reminders.py`

### v2.6.0 (2026-08-27)
- **批1（AO→SP 基底适配 + SP 健壮性审计）**：登录背景换 AO 集装箱船图；菜单图标沿用 AO；AI 直连优先+代理兜底；AI 密钥防双加密；SP 健壮性审计修复（删除保护/校验/前端错误提示/传参）；SP 环境初始化修复（mo_outsourcing 外键/init 脚本/test.sh 平台自适应）；测试基线 test_config_secret_guard.py
- **批2（销售退货财务层补强）**：
  - **发票红冲**：蓝字开票上限校验（≤ 未开票金额，红字全额冲后额度返还）；红字手工录入（全额负数、原票标记已红冲）；红字票禁改禁删；已红冲蓝字票禁删；自动生成等额红字应收（`is_red`/`red_of_ar_id`）
  - **退款**：`create_collection` 支持 `amount<0` 退款登记，核销红字应收、负余额向 0 靠拢、退超拦截
  - **核销转移**：`POST /ar/transfer`（红字→同客户正余额，双向上限）+ `POST /ar/transfer/{id}/cancel`（撤销回滚），写 `ar_adjustment` 审计
  - **退货联动**：已开票提示红冲；关联报关单退税已申报打标 `refund_declared=1` 提示次月负数申报
  - **负数申报**：`GET /declarations/{id}/return-candidates` + `POST /declarations/{id}/return-adjustments`（出口货物退运负数行，自动重算出口金额/免抵退）
  - **前端 5 页**：SalesInvoices（红冲/红冲票号列/红字票删除隐藏/状态色）、AccountsReceivable（红负绿正/退款/核销转移弹窗）、Collections（负数标红+退款 tag）、SalesDeliveries（已开票提示）、TaxRefundDeclarations（退货冲减入口）+ api/business.js
  - **测试**：`backend/tests/test_sales_return_red.py` 6 场景；全量回归绿
- **模型**：`so_invoice`(+is_red/red_of_invoice_id)、`ar_account`(+is_red/red_of_ar_id)、`so_delivery`(+refund_declared)、新建 `ar_adjustment`；迁移脚本 `scripts/migrate_batch2_finance.py`

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

---

# 附录：开发现状速览（给接手开发者的上下文）

> 原 `DEVELOPMENT_STATUS.md`，已并入本文件。看完这节就能知道项目在做什么、做到哪、下一步是什么。

## 1. 业务模型（最重要，先懂这个）

公司**无工厂、无自产**（生产管理已于 2026-09 下线），业务线两类：

1. **纯贸易（买成品）**：买成品 → 卖成品 → **销售明细「转直采」**——唯一关联采购订单的路线
2. **委外加工**：单独采购材料入库 → 委托加工厂做成产品 → 卖产品 → **销售明细「转外发」**——不关联采购订单

**两路分流（互斥）+ 材料独立采购**：
```
销售订单明细行
 ├─ 点「转直采」(贸易型，买成品) → 采购管理 → 销售订单转采购页（只列转直采行）
 │    → 生成采购订单（按成品数量×(1+损耗) 采购成品本身，无视 BOM/按供应商拆单）→ 审核
 │    → 明细行「转成品库」→ 成品入库模块收货（成本=采购价，挂销售明细）
 ├─ 点「转外发」(委外型) → 委外线单线走，不关联采购订单：
 │    ├─ 材料先行：采购员单独填采购订单买材料 → 转原料库 → 原料入库收货（入库零关联销售单）
 │    ├─ 销售订单转委外页（工序卡片横向展开）→ 每道工序选加工商+加工单价
 │    │    → 按工序拆多张委外订单（一工序一供应商）→ 己方提供时先「领料」：
 │    │      按成品数×BOM用量×(1+损耗) FIFO 扣原料库存、出库流水挂销售单号（成本在此刻挂到销售单）
 │    │    → 审核 → 每张记加工费AP；只有末道工序生成成品待入库单
 │    └─ 成品入库模块收货（成品数量=产品数量）
 └─ （转生产入口已删除；后端 re-produce 端点保留但不再从界面触达）
```

**发货（两步化）**：
```
业务员「通知发货」(只填数量，不扣库存) → 库管在「成品出库」页按单选批次发货(扣库存) → 业务员判断「发货完成」(人工确认, 必须先有出库记录)
退货: 必须已有出库记录才能退（通知未出库不能退）
```

**原料出库**：库存管理→原料出库页 = 手动出库(MU单号)；委外领料的出库记录在委外管理（`os_claim_material`，出库流水挂销售单号）

## 2. 核心铁律（全 ERP 强制）

1. **上游禁止下游改，退下游才解锁**：下游有单据时，上游不能变更/删除/退回。想改上游 → 先把下游单据全部退回（在对应单据页退回）→ 上游解锁。
2. **状态颜色四档**（全 ERP 统一）：本环节完成=绿 / 进行中=橙 / 未开始=灰 / 终止=红。
3. **数量是参考，完成是人工点**：采购/委外的"完成"由业务员手动点（完成采购/完成委外），可"取消完成"再追加。
4. **损耗默认 10% 可改**：采购/委外数量上限 = 需求 × (1+损耗%)，超量拦截，要超就得改损耗比例。
5. **一步一步来**：销售订单只负责"推送"（转直采/转外发），单据在各自页面生成，不跳步。
6. **材料与销售单的关联只在出库（领料）时建立**：材料采购与原料入库零关联销售单；委外领料出库那一刻，成本按 FIFO 挂到销售单归集。

## 3. 主流程状态机

### 销售订单明细行（production_status）
未生产 → 已通知入库(显示"转直采") / 已通知外发(显示"转外发") → 部分入库 → 已入库 / 已停售（「生产中/已生产」为历史存量状态）

### 转采购页状态（人工完成）
- 未采购（灰）→ 部分采购（橙，可追加）→ 已转采购订单（绿，达上限 需求×1.1）
- 手动「完成采购」→ 采购完成（绿）→ 「取消完成」可回
- 操作：采购 / 完成采购 / 取消完成 / 退回（仅无采购单时显示，有单去采购订单页退）

### 转委外页状态
同上对称：未转委外 / 部分转委外 / 已转委外订单 / 委外完成

### 采购订单状态
待审核（灰）→ 已审核（绿）→ 已关闭（红）。入库/开票/付款进度不在主表（财务模块看）。

### 委外订单状态
待确认 → 已审核（生成应付+待入库单）→ 已入库（收货完成）。已审核可「取消审核」退回待确认。

## 4. 菜单结构

- **采购管理**：销售订单转采购（仅直采买成品）→ 采购订单 → 采购发票 → 应付账款 → 付款管理
- **库存管理**：库存查询 → 收发存 → 成品入库 → 原料入库 → 原料出库 → 成品出库 → 盘点管理 → 批次追溯（2026-09 从生产管理挪入）
- **委外管理**：销售订单转委外 → 委外订单
- **销售管理**：销售订单 → 销售发货 → 销售发票 → 报关管理 → 应收账款 → 收款管理
- **生产管理**：菜单已删（2026-09 下线）

## 5. 技术栈与环境

- 后端：FastAPI + SQLAlchemy + SQLite（`backend/data/erp.db`）
- 前端：Vue3 + Vite + Element Plus
- 登录：admin / admin123（测试）
- 测试：`./test.sh`（隔离测试库）+ `cd e2e && python -m pytest`
