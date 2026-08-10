# MAZU ERP 代码合并分析报告 v2

> task_id: merge-analysis-20260810-v2  
> **对比基准（修正）**: `origin/app-optimization` (3d66375, v2.7.0) — 用户日常开发线  
> 合作者分支: `Sales_Purchase` (HEAD=8ac065b, 2026-08-09)  
> 工作副本: `/tmp/merge-analysis`（当前检出 `Sales_Purchase`）  
> 分析方式: 只读 git diff + 代码/路由/模型比对，不执行任何代码修改  
> v1 报告基准: `origin/main` (a081018, v2.5.0 快照) — **已废弃，本版修正**

---

## v2 修正摘要（与 v1 对比）

| # | v1 结论（基准 main） | v2 修正（基准 app-optimization） | 变化 |
|---|---|---|---|
| 1 | SP 独有 80 提交，AO 独有 13 提交 | SP 独有 **81** 提交，AO 独有 **29** 提交 | ⬆ AO 提交数翻倍（含 v2.5.2~v2.7.0 共 17 个功能提交 + 文档/修复） |
| 2 | 冲突面 43 个交集文件 | 交集 **47** 个文件（AO 变更面从 110→143 文件） | ⬆ 冲突面略增 |
| 3 | 销售退货/红冲/退款"主线缺失，值得移植" | app-optimization **已有 v2.5.2 完整实现**（`ArAdjustment` 模型 + 退货+红冲+退款+核销转移） | 🟢 → 已覆盖 |
| 4 | 报关/退税"主线缺失" | app-optimization **已有 v2.6.0**（`CustomsDeclarationItem` 明细化 + `tax_refund.py` 双端匹配） | 🟢 → 已覆盖 |
| 5 | 应收应付明细/审核锁定"主线缺失" | app-optimization **已有 v2.6.1**（AR/AP 单据为行+详情弹窗+核销转移撤销+收款/付款审核锁定） | 🟢 → 已覆盖 |
| 6 | 预警提醒"主线缺失" | app-optimization **已有 v2.7.0**（`ReminderRule` + `Notification` 模型 + `reminder.py` 事件埋点 + `Reminders.vue`） | 🟢 → 已覆盖 |
| 7 | 委外模块"主线已删旧模型" | AO 无独立委外路由/模型，但 SP 新建了完整委外模块（`OutsourceOrder` + `Outsourcer` + 独立路由） | 🔴 真正的方向冲突 |
| 8 | 数字精度冲突仍存在 | 确认：AO 全量 `round(...,2)`，SP 部分改为 `round(...,6)` | 🔴 冲突维持 |

**核心修正**：v1 把 v2.5.2~v2.7.0 的 4 大功能模块误判为"主线缺失、值得移植"；实际上 app-optimization 已完整覆盖。**真正值得从 SP 移植到 AO 的功能范围大幅缩小**，主要集中在：统一入库模型（StockInOrder）、委外独立模块、参数设置、列设置/拖拽、采购线 UI 改造。

---

## 1. 分支概览（以 app-optimization 为基准）

### 1.1 基本信息

| 项目 | 值 |
|---|---|
| **merge-base** | `7b0e92d`（`fix: 健壮性测试发现的 10 个问题修复`，2026-07-31） |
| **app-optimization HEAD** | `3d66375`（v2.7.0，2026-08-10，`docs: 并入合作者 08-09 增量`） |
| **Sales_Purchase HEAD** | `8ac065b`（2026-08-09，`feat: 数字精度调整`） |

### 1.2 提交数统计

| 方向 | 数量 | 说明 |
|---|---|---|
| `git rev-list --count origin/app-optimization..HEAD` | **81** | Sales_Purchase 独有提交（7/31~8/9，前端重构+入库链路改造） |
| `git rev-list --count HEAD..origin/app-optimization` | **29** | app-optimization 独有提交（v2.5.1~v2.7.0 + 文档/修复） |

### 1.3 文件面统计

| 指标 | 数量 |
|---|---|
| `git diff --name-only origin/app-optimization...HEAD`（SP 改动文件） | **71** |
| `git diff --name-only HEAD...origin/app-optimization`（AO 改动文件） | **143** |
| 两端都改过的文件（交集） | **47** |

### 1.4 时间线

- **merge-base**: 2026-07-31（`7b0e92d`）
- **Sales_Purchase 提交跨度**: 2026-07-31 → 2026-08-09（81 提交，10 天高密度前端改造）
- **app-optimization 提交跨度**: 2026-07-31 → 2026-08-10（29 提交，含 v2.5.1~v2.7.0 四个版本发布）

---

## 2. 冲突面分析

### 2.1 47 个交集文件

`git diff --name-only origin/app-optimization...HEAD` 与 `git diff --name-only HEAD...origin/app-optimization` 的交集：

**后端核心（13 个）：**
- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/foundation.py`
- `backend/app/models/inventory.py`
- `backend/app/models/production.py`
- `backend/app/models/purchase.py`
- `backend/app/models/sales.py`
- `backend/app/routers/base_crud.py`
- `backend/app/routers/foundation.py`
- `backend/app/routers/inventory.py`
- `backend/app/routers/purchase.py`
- `backend/app/routers/sales.py`
- `backend/app/schemas/foundation.py` / `backend/app/schemas/purchase.py`

**前端核心（34 个）：**
- `frontend/src/components/Layout.vue`
- `frontend/src/router/index.js`
- `frontend/src/api/foundation.js`
- `frontend/src/views/sales/SalesOrders.vue`、`SalesDeliveries.vue`、`SalesInvoices.vue`、`AccountsReceivable.vue`、`Collections.vue`、`CustomsDeclarations.vue`
- `frontend/src/views/purchase/PurchaseOrders.vue`、`PurchaseReceipts.vue`、`PurchaseInvoices.vue`、`AccountsPayable.vue`、`Payments.vue`
- `frontend/src/views/production/ProductionOrders.vue`、`ProductionReceipts.vue`、`Outsourcings.vue`、`ProcessingInvoices.vue`、`BatchInventory.vue`
- `frontend/src/views/inventory/InventoryManagement.vue`
- `frontend/src/views/foundation/Bom.vue`、`Customers.vue`、`HsCodes.vue`、`Materials.vue`、`Processes.vue`、`Products.vue`、`Suppliers.vue`
- `frontend/src/views/system/BotConfig.vue`、`Reminders.vue`、`WecomConfig.vue`
- `frontend/src/views/taxRefund/TaxRefundDeclarations.vue`

### 2.2 冲突性质判断

**结论：结构性冲突，不可直接 git merge。**

两端对同一组核心文件（`sales.py`、`purchase.py`、`inventory.py`、`production.py`、`Layout.vue`、`router/index.js`）做了**语义层面的重构**，不是简单的行级冲突：

1. **SP** 把采购入库链路从 `PurchaseReceipt` 改为 `StockInOrder` 统一入库模型
2. **SP** 新建独立委外模块（`OutsourceOrder` + `Outsourcer` + 独立路由/页面）
3. **SP** 销售明细行状态机增加"已通知入库(转直采)"和"已通知外发(转外发)"两个状态
4. **AO** 保留 `PurchaseReceipt` + `PurchaseRequisition`（PR 驱动）链路
5. **AO** 在 `production.py` 中通过 `outsourcer_id` 字段处理委外（非独立模块）
6. **AO** 销售明细行状态机为"未生产→生产中→已生产"三态

---

## 3. 重点议题验证（对照 app-optimization 代码）

### 3.1 统一入库模型 StockInOrder（🔴 方向冲突）

| 维度 | Sales_Purchase | app-optimization |
|---|---|---|
| 入库模型 | `StockInOrder`（表 `inv_stock_in`），统一成品/原料入库 | `PurchaseReceipt` + `PurchaseReceiptItem`（采购入库） |
| 入库路由 | `backend/app/routers/stock_in.py`（新增） | 无（采购入库由 `purchase.py` 处理） |
| 入库页面 | `StockIns.vue`（成品入库）+ `MaterialIns.vue`（原料入库） | `PurchaseReceipts.vue`（采购入库） |
| 菜单入口 | 库存管理→成品入库/原料入库 | 采购管理→采购入库 |
| `WarehouseInventory` 扩展 | 新增 `receipt_no`、`claimed_from_batch` 字段 | 无此字段 |

**冲突点**：SP 用 `StockInOrder` 统一管理所有入库（销售来源、采购来源、委外来源），AO 保留传统的采购入库/完工入库分离模式。合并时必须二选一或做适配层。

### 3.2 转直采/转委外 vs PR 驱动（🔴 流程冲突）

| 维度 | Sales_Purchase | app-optimization |
|---|---|---|
| 采购触发 | 销售明细→"转直采"→推送到"销售订单转采购"页→手动生成采购单 | 生产订单→`PurchaseRequisition`（采购需求）→"采购需求转采购单" |
| 委外触发 | 销售明细→"转外发"→自动生成委外订单草稿 | 生产订单工序→`outsourcer_id` 字段→在生产模块内处理 |
| 采购需求页 | 无（SP 删了 `PurchaseRequisitions.vue`） | 有（`PurchaseRequisitions.vue` + `/purchase/requisitions` 路由） |
| 转采购页 | `PurchaseFromSales.vue`（新增） | 无 |

**冲突点**：SP 把采购触发从"生产驱动的 PR"改为"销售明细直驱"，AO 保留 PR 驱动。这是业务流程层面的根本差异。

### 3.3 委外模块（🔴 模型/路由冲突）

| 维度 | Sales_Purchase | app-optimization |
|---|---|---|
| 委外模型 | `OutsourceOrder`（`mo_outsourcing`）+ `OutsourceReceiptItem` + `Outsourcer`（`fd_outsourcer`）独立模型 | 无独立委外模型，通过 `ProductionProcess.outsourcer_id` 关联 `Supplier` |
| 委外路由 | `backend/app/routers/outsource.py`（独立路由） | 无（委外在 `production.py` 中处理） |
| 委外页面 | `OutsourceFromSales.vue` + `OutsourceOrders.vue` | 无 |
| 菜单入口 | 委外管理（一级菜单）→销售订单转委外/委外订单 | 无独立委外菜单 |

**冲突点**：SP 新建了完整的独立委外模块（模型+路由+页面+菜单），AO 没有独立委外模块（委外是生产工序的一个属性）。合并时需要决定委外的架构方向。

### 3.4 参数设置/列拖拽/列设置（🟡 SP 独有，AO 无）

| 维度 | Sales_Purchase | app-optimization |
|---|---|---|
| 参数设置 | `SystemParams.vue` + `/foundation/params` 路由 | 无 |
| 列设置弹窗 | `ColumnSettingsDialog.vue`（勾选显隐+上下移动+恢复默认） | 无 |
| 列拖拽 | `useColumnDrag.js` + `useColumnCustomize.js` + `useColumnAutoFit.js` composables | 无（固定列定义） |
| 列排序弹窗 | `ColumnOrderDialog.vue` | 无 |
| 影响范围 | 全 ERP 表格铺开（销售订单、采购订单等所有列表页） | 仅 `sortable` 属性排序 |

**判断**：v1 报告已确认"主线认可移植"，本次维持。这些是纯前端 UI 增强，不涉及后端模型冲突，移植风险低。

### 3.5 数字精度（08-09）（🔴 冲突维持）

| 维度 | Sales_Purchase (8ac065b) | app-optimization (3d66375) |
|---|---|---|
| 汇率/本币换算 | `round(..., 6)` 中间精度 | `round(..., 2)` |
| 不含税价计算 | `round(..., 6)` | `round(..., 2)` |
| 数量格式化 `$fq` | 2 位小数 | 4 位小数（`main.js` 中 `$fq` 未改） |
| 前端 `$fm` 显示 | 2 位 | 2 位（一致） |

**冲突点**：两端都在改 `backend/app/routers/sales.py` 的订单创建/重算函数和 `frontend/src/main.js` 的全局格式化。AO 仍用 `round(...,2)` 全量，SP 改为 `round(...,6)` 中间精度。

---

## 4. 功能差距矩阵（以 app-optimization 为基准）

### 4.1 Sales_Purchase 有 / app-optimization 无

| 功能模块 | SP 文件证据 | 状态 | 说明 |
|---|---|---|---|
| **统一入库模型 StockInOrder** | `models/inventory.py:StockInOrder`、`routers/stock_in.py`、`StockIns.vue`、`MaterialIns.vue` | 🔴 值得移植 | SP 的核心架构改造，统一成品/原料/委外入库入口 |
| **独立委外模块** | `models/production.py:OutsourceOrder`、`routers/outsource.py`、`OutsourceFromSales.vue`、`OutsourceOrders.vue` | 🔴 值得移植（需评估） | 完整独立委外模块 vs AO 的"委外作为生产工序属性"，需架构决策 |
| **销售明细直驱采购** | `routers/sales.py` 转直采/转外发端点、`PurchaseFromSales.vue` | ⛔ 与 AO PR 驱动冲突 | 流程层面冲突，需业务方决策 |
| **参数设置页** | `SystemParams.vue`、`/foundation/params` 路由 | 🔴 值得移植 | 纯前端，低风险 |
| **列设置/拖拽** | `ColumnSettingsDialog.vue`、`ColumnOrderDialog.vue`、`useColumn*.js` composables | 🔴 值得移植 | 纯前端 UI 增强，低风险 |
| **采购订单主表瘦身** | `PurchaseOrders.vue` 删 7 个金额列、新增采购员列 | 🟡 部分移植 | UI 调整，可按需采纳 |
| **采购明细转成品库/原料库** | `routers/purchase.py` 转库端点 | ⛔ 依赖 StockInOrder | 与 AO 采购入库链路冲突 |
| **委外订单主表加销售订单号列** | `OutsourceOrders.vue` | 🟡 依赖委外模块 | 若采用独立委外模块则可移植 |
| **销售发货工作台 UI 改造** | `SalesDeliveries.vue` 上下主从联动 | 🟡 部分移植 | UI 改造，需适配 AO 的发货模型 |
| **仓库自动匹配** | `stock_in.py` 收货时按 `wh_type` 自动匹配仓库 | 🟡 依赖 StockInOrder | 逻辑可参考，实现需适配 |
| **`WarehouseInventory.receipt_no`** | `models/inventory.py:26` | 🟡 部分移植 | 可独立添加字段 |
| **`Outsourcer` 基础档案模型** | `models/foundation.py:Outsourcer` | 🟡 依赖委外模块决策 | AO 用 `Supplier` 代替 |
| **`StockCheck`/`StockCheckItem`（盘点模型重命名）** | `models/inventory.py:StockCheck/StockCheckItem` | 🟢 AO 已有等价物 | AO 用 `Stocktake`/`StocktakeItem`，功能等价 |
| **`frontend/src/App.vue` 改动** | SP 改了 App.vue | 🟡 需对比 | 需检查具体改动 |
| **`batch_no.py` 工具** | `backend/app/utils/batch_no.py` | 🟡 需对比 | 批次号生成工具 |

### 4.2 app-optimization 有 / Sales_Purchase 无

| 功能模块 | AO 文件证据 | SP 状态 | 说明 |
|---|---|---|---|
| **v2.5.2 销售退货全链路** | `routers/sales.py:581` return_delivery + `ArAdjustment` 模型 + 红冲+退款+核销转移 | 🟢 SP 有基础退货 | SP 有 `create_delivery_return`（L958），但缺少 AO 的：红字发票全额红冲、退款端点、`ArAdjustment` 核销转移、负数申报联动 |
| **v2.6.0 报关单明细化** | `models/sales.py:CustomsDeclarationItem`、`routers/sales.py:752` create_customs | 🟢 SP 有报关基础 | SP 有报关功能，但需核实是否有 `CustomsDeclarationItem` 明细化 |
| **v2.6.0 退税双端匹配** | `routers/tax_refund.py`、`models/tax_refund.py:TaxRefundDeclarationRow` | 🟢 两端都有 | SP 也有 `tax_refund.py` 路由和相同模型 |
| **v2.6.1 应收应付明细重构** | `AccountsReceivable.vue` 单据为行+汇总+详情弹窗+核销转移撤销 | 🟢 SP 有基础 AR/AP | SP 有 AR/AP 页面，但缺少 AO 的：核销转移、撤销转移、收款审核锁定 |
| **v2.6.1 收款/付款审核锁定** | `Collections.vue:29` 审核按钮+锁定逻辑 | 🔴 SP 缺失 | SP 的 `Collections.vue` 无审核功能 |
| **v2.7.0 预警提醒系统** | `services/reminder.py`、`models/system_config.py:ReminderRule+Notification`、`Reminders.vue` | 🟡 SP 部分有 | SP 有 `ReminderConfig`+`ReminderLog` 但**无 `ReminderRule` 和 `Notification` 模型**，也无 `reminder.py` 事件埋点服务和 `notification.py` 路由 |
| **v2.5.1 AI 助手工具执行器修复** | `routers/bot_chat.py` 工具执行器 | 🟢 两端都有 | SP 也有 `bot_chat.py` |
| **PR 驱动采购需求** | `models/purchase.py:PurchaseRequisition`、`routers/purchase.py` 需求转单 | ⛔ SP 有意删除 | SP 用"销售明细直驱"替代，这是流程冲突 |
| **采购入库页面** | `PurchaseReceipts.vue` + `purchase.py` 采购入库端点 | ⛔ SP 用 StockInOrder 替代 | SP 删了采购入库菜单 |
| **汇率自动获取服务** | `services/exchange_rate_fetcher.py`（腾讯财经接口+定时任务） | 🔴 SP 缺失 | 完整的汇率自动获取能力 |
| **完整测试体系** | `backend/tests/` 16 个测试文件（187+ 后端测试 + E2E） | 🔴 SP 缺失 | SP 仅有 6 个测试文件 |
| **CI/CD 流水线** | `.github/workflows/ci.yml` | 🟢 两端都有 | — |
| **菜单级权限前端** | `Layout.vue` 按 `hasPerm()` 过滤菜单 | 🟢 两端都有 | SP 也有权限过滤 |
| **仓库/币种管理** | `Warehouses.vue`、`CurrencyRates.vue` | 🟢 两端都有 | — |
| **收发存 v2** | `inventory.py` 盘点闭环/采购红冲/销售退货/发料拆类型/成本自动结转 | 🟡 SP 有基础收发存 | SP 有 `InventoryManagement.vue` 但可能缺少 v2 增强 |
| **生产订单确认备货方式** | `production.py:set_production_type`（自产/委外/外购） | 🟢 SP 也有 | SP 的 `production.py` 也有此端点 |

### 4.3 两端都有但实现不同的模块

| 模块 | 差异点 | 风险 |
|---|---|---|
| **销售明细状态机** | AO: 未生产→生产中→已生产（三态）<br>SP: 未生产→已通知入库(转直采)/已通知外发(转外发)→部分入库→已入库 | 🔴 状态机冲突 |
| **委外处理** | AO: 生产工序 `outsourcer_id` 属性<br>SP: 独立 `OutsourceOrder` 模型 | 🔴 架构冲突 |
| **采购入库** | AO: `PurchaseReceipt` 模型<br>SP: `StockInOrder` 模型 | 🔴 模型冲突 |
| **盘点模型** | AO: `Stocktake`/`StocktakeItem`<br>SP: `StockCheck`/`StockCheckItem` | 🟡 功能等价，命名不同 |
| **数字精度** | AO: `round(...,2)` 全量<br>SP: `round(...,6)` 中间精度 | 🔴 精度口径冲突 |

---

## 5. 合并策略建议（基于修正后差距矩阵）

### 5.1 核心结论

**v2 修正后，真正值得从 SP 移植到 AO 的功能范围大幅缩小**。v1 误判的 4 大功能（退货红冲、报关退税、应收应付、预警提醒）在 AO 中已完整实现。

### 5.2 P0 / P1 / P2 分批清单

#### P0：低风险、高价值移植（纯前端/独立功能）

| # | 功能 | 风险 | 预估工作量 |
|---|---|---|---|
| 1 | 列设置弹窗（`ColumnSettingsDialog.vue`） + 列拖拽 composables | 低（纯前端） | 1~2 天 |
| 2 | 参数设置页（`SystemParams.vue`） | 低（纯前端+基础后端） | 0.5 天 |
| 3 | `WarehouseInventory.receipt_no`/`claimed_from_batch` 字段 | 低（仅加字段） | 0.5 天 |
| 4 | 采购订单主表瘦身 UI | 低（仅 UI 调整） | 0.5 天 |

#### P1：中风险、需架构决策

| # | 功能 | 风险 | 预估工作量 |
|---|---|---|---|
| 5 | 统一入库模型（`StockInOrder`） | 中~高（需适配 AO 的采购入库/完工入库链路） | 3~5 天 |
| 6 | 独立委外模块 | 中~高（需决定架构方向：独立模块 vs 生产工序属性） | 3~5 天 |
| 7 | 预警提醒补强（`ReminderRule`+`Notification`+事件埋点） | 中（AO 已有基础，SP 补充规则引擎+通知内核） | 2~3 天 |
| 8 | 汇率自动获取服务 | 低（独立服务，不影响现有逻辑） | 1 天 |

#### P2：高风险、需业务方决策

| # | 功能 | 风险 | 预估工作量 |
|---|---|---|---|
| 9 | 销售明细直驱采购流程（替代 PR 驱动） | 高（业务流程根本冲突） | 需业务方评估 |
| 10 | 数字精度统一（6 位中间精度 vs 2 位） | 高（影响财务口径） | 需财务确认 |
| 11 | 销售发货工作台 UI 改造 | 中（需适配 AO 发货模型） | 2~3 天 |

### 5.3 不建议移植（AO 已覆盖或方向冲突）

| 功能 | 原因 |
|---|---|
| 销售退货/红冲/退款/核销转移 | AO v2.5.2 已完整实现 |
| 报关单明细化 | AO v2.6.0 已完整实现 |
| 应收应付明细重构 | AO v2.6.1 已完整实现 |
| 退税双端匹配 | AO v2.6.0 已完整实现 |
| 采购入库页面删除 | SP 用 StockInOrder 替代，但 AO 保留 PurchaseReceipt 链路 |
| 采购需求页面删除 | SP 删了 PR 驱动，但 AO 保留 |

---

## 6. 风险清单

### 6.1 高风险（🔴）

| # | 风险 | 影响范围 | 缓解建议 |
|---|---|---|---|
| 1 | **入库模型双轨冲突**（StockInOrder vs PurchaseReceipt） | `models/inventory.py`、`routers/purchase.py`、`routers/stock_in.py`、`Layout.vue`、`router/index.js` | 二选一：采用 StockInOrder 则需迁移 AO 采购入库数据；保留 PurchaseReceipt 则放弃 SP 统一入库 |
| 2 | **委外模块架构冲突**（独立模块 vs 生产工序属性） | `models/production.py`、`routers/outsource.py`、`Layout.vue`、`router/index.js` | 需架构决策：若采用独立模块，AO 的 `outsourcer_id` 字段需迁移 |
| 3 | **销售明细状态机冲突**（三态 vs 五态） | `routers/sales.py`、`SalesOrders.vue`、`production.py` | 状态机合并需统一定义，建议以 SP 的五态为准（更细粒度） |
| 4 | **数字精度口径冲突**（round 2 vs round 6） | `routers/sales.py`、`main.js` | 建议统一精度规范（计算 6 位，持久化/返回 2 位），引入精度工具函数 |
| 5 | **采购流程冲突**（PR 驱动 vs 销售明细直驱） | `routers/purchase.py`、`PurchaseRequisitions.vue`、`PurchaseFromSales.vue` | 需业务方决策，不可技术层面解决 |

### 6.2 中风险（🟡）

| # | 风险 | 影响 | 缓解建议 |
|---|---|---|---|
| 6 | SP 有 47 个交集文件，git merge 会产生大量语义冲突 | 合并成本高 | 按功能簇 cherry-pick/移植，不要直接 merge |
| 7 | SP 未覆盖 AO 的测试体系（6 vs 16 个测试文件） | 移植后回归风险 | 每个功能簇移植后跑 AO 现有测试 |
| 8 | SP 缺少 AO 的 `ArAdjustment` 核销转移能力 | 若未来需要核销转移功能 | 可独立移植 `ArAdjustment` 模型+端点 |
| 9 | SP 缺少 AO 的收款/付款审核锁定 | 财务确认流程缺失 | 可独立移植审核锁定逻辑 |

### 6.3 低风险（🟢）

| # | 风险 | 说明 |
|---|---|---|
| 10 | 列设置/拖拽移植 | 纯前端，不涉及后端模型 |
| 11 | 参数设置页移植 | 独立页面，不影响现有功能 |
| 12 | 盘点模型命名差异（Stocktake vs StockCheck） | 功能等价，合并时统一命名即可 |

---

## 7. 08-09 数字精度冲突专项

### 7.1 已验证的精度差异

**Sales_Purchase (8ac065b) — 08-09 精度调整提交：**
- `backend/app/routers/sales.py`：
  - `tax_amount_local += round(..., 6)`（L130）
  - `total_excl_tax_fc = round(..., 6)`（L131）
  - `total_excl_tax_local = round(..., 6)`（L132）
  - `unit_price_local = round(..., 6)`（L170）
  - `total_amount_local = round(..., 6)`（L172）
  - `total_amount_excl_tax_local = round(..., 6)`（L174）
- `frontend/src/main.js`：
  - `$fq(...)` 全局数量显示从 4 位改为 2 位

**app-optimization (3d66375) — 同一文件：**
- `backend/app/routers/sales.py`：
  - 同一组计算全部使用 `round(..., 2)`（L130~L174）
- `frontend/src/main.js`：
  - `$fq(...)` 仍为 4 位小数

### 7.2 冲突性质

**是同一文件、同一函数的冲突**。两端都在改 `sales.py` 的订单创建/重算函数和 `main.js` 的全局格式化。属于"同一业务场景、同一代码位置、两种精度口径"。

### 7.3 合并风险

- 6 位中间精度 vs 2 位：汇率换算/不含税价在不同精度下结果不同
- 数量格式化 4 位 vs 2 位：历史数据展示精度变化
- 财务模块（应收/应付/发票）按金额聚合时，精度差异会导致"差几分"问题

### 7.4 建议方案

**方案 A（推荐）：统一精度规范 + 引入精度工具**
- 中间计算：汇率/本币换算/不含税价保留 6 位
- 持久化与接口返回：金额统一 2 位，数量统一 2 位（或按业务需要 4 位）
- 前端展示：`$fm` 2 位，`$fq` 2 位
- 实现：增加 `precision_utils.py`（`round_money`/`round_qty`），替换裸 `round(..., 2/6)`

**方案 B（保守）：暂不改精度，维持 AO 的 round(...,2)**
- 适合"先稳后改"阶段

---

## 附录：分析使用的只读命令

```bash
# 分支与分叉点
git merge-base origin/app-optimization HEAD          # 7b0e92d
git rev-parse --short origin/app-optimization         # 3d66375
git rev-parse --short HEAD                            # 8ac065b

# 提交数
git rev-list --count origin/app-optimization..HEAD    # 81 (SP unique)
git rev-list --count HEAD..origin/app-optimization    # 29 (AO unique)

# 文件面
git diff --name-only origin/app-optimization...HEAD | wc -l   # 71
git diff --name-only HEAD...origin/app-optimization | wc -l   # 143
comm -12 <(sort sp_files.txt) <(sort ao_files.txt) | wc -l    # 47

# 关键代码检查
git show origin/app-optimization:backend/app/models/inventory.py
git show origin/app-optimization:backend/app/routers/sales.py | grep "round("
git show origin/app-optimization:backend/app/models/system_config.py | grep "class "
git show HEAD:backend/app/models/production.py | grep "class.*Outsource"
git show HEAD:backend/app/routers/stock_in.py
```

---

## 附录：最关键 3 个合并风险（总结）

1. **入库模型双轨冲突**（`StockInOrder` vs `PurchaseReceipt`）— 两端对"采购入库"的架构设计完全不同，合并时必须二选一
2. **委外模块架构冲突**（独立模块 vs 生产工序属性）— SP 新建完整独立委外模块，AO 无此模块，方向性冲突
3. **采购流程/销售明细状态机冲突**（PR 驱动 vs 销售明细直驱）— 业务流程根本差异，需业务方决策

> **最终建议**：以 `origin/app-optimization` (v2.7.0) 为唯一主干，采用"功能簇 cherry-pick"方式整合 Sales_Purchase。v2 修正后，真正值得移植的功能范围缩小为：列设置/拖拽、参数设置、统一入库模型（需架构决策）、独立委外模块（需架构决策）。v1 误判的退货红冲/报关退税/应收应付/预警提醒已由 AO 覆盖，无需移植。
