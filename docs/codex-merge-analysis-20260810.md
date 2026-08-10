# MAZU ERP 合并分析报告

> task_id: merge-analysis-20260810  
> 分析范围: `origin/main` (a081018) vs `Sales_Purchase` (HEAD=8ac065b)  
> 工作副本目录: `/tmp/merge-analysis`（当前检出 `Sales_Purchase`）  
> 分析方式: 只读 git 分析 + 代码/路由/模型比对，不执行任何代码修改

---

## 1. 分支概览

- **merge-base**: `d2724bf`（`merge: app-optimization -> main v2.1.0 + 健壮性修复`，2026-07-31）
- **main 最新**: `a081018`（2026-08-01，`Merge remote-tracking branch 'origin/app-optimization'`）
- **Sales_Purchase 最新**: `8ac065b`（2026-08-09，数字精度调整）

### 差异规模（基于 git 统计）

- `Sales_Purchase` 相对 `origin/main`：**80 个独有提交**，涉及 **71 个文件**，新增 **9536 行**、删除 **1992 行**
- `origin/main` 相对 `Sales_Purchase`：**13 个独有提交**，涉及 **110 个文件**，新增 **8794 行**、删除 **2374 行**
- 两端都改过的文件（按 3-dot diff 文件名交集）：**43 个**

### 时间线（git log 验证）

- `Sales_Purchase` 提交跨度：`2026-07-31` → `2026-08-09`
- `origin/main` 提交跨度：`2026-07-31` → `2026-08-01`
- 说明：main 在 8/1 之后已不再新增提交（当前快照），而合作者分支持续演进到 8/9，跨度约 10 天、80 个提交，属于高密度前端改造分支。

---

## 2. 冲突面分析

### 2.1 高风险文件面

`git diff --name-only origin/main...HEAD` 共 **71 个变更文件**；  
`git diff --name-only HEAD...origin/main` 共 **110 个变更文件**；  
两者交集（**双方都改**）**43 个文件**。

**高风险 43 个交集文件（截取核心后端+关键前端）：**

- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/inventory.py`
- `backend/app/models/production.py`
- `backend/app/models/purchase.py`
- `backend/app/routers/inventory.py`
- `backend/app/routers/purchase.py`
- `backend/app/routers/sales.py`
- `backend/app/schemas/purchase.py`
- `frontend/src/components/Layout.vue`
- `frontend/src/router/index.js`
- `frontend/src/views/inventory/InventoryManagement.vue`
- `frontend/src/views/sales/SalesOrders.vue`
- `frontend/src/views/purchase/PurchaseReceipts.vue`
- `frontend/src/views/production/ProductionReceipts.vue`（主线上已从路由删页面，但该文件仍进入 diff）

**结论：**  
这不是“表面冲突”，而是**结构性冲突**：合作者把销售→采购→入库链路从“生产订单/PR驱动”改成“销售明细直驱 + StockInOrder 统一入库单”；主线则保留/强化 `po_receipt/mo_receipt` + PR 驱动 + 权限/盘点/汇率等基建。  
因此，**不建议直接 `git merge`**，否则会有大量代码语义冲突和功能回归。

---

## 3. 重点议题验证（按文件证据）

### 3.1 统一入库模型 StockInOrder（合作者删主线功能？）

**结论：是。合作者用 `StockInOrder` + 新路由/菜单，直接替代主线保留的采购入库/完工入库链路；属于“主线功能被替代+入口被移除”。**

**证据：**

1) 合作者新增库存模型：`backend/app/models/inventory.py`
   - 新增 `StockInOrder`（表 `inv_stock_in`），字段包含：
     - `source_type`：`sales/purchase/outsource`
     - `sales_order_id/sales_item_id/purchase_order_id/purchase_item_id/outsource_order_id`
     - `product_id/material_id`
     - `quantity/received_qty/status/warehouse_id`
   - 同时新增 `WarehouseInventory.receipt_no/claimed_from_batch` 字段

2) 合作者新增入库路由：`backend/app/routers/stock_in.py`
   - 完整实现：
     - `GET /api/stock-in`：待入库单列表（支持 `kind=product/material`）
     - `POST /{stock_in_id}/receive`：收货入库
     - `POST /{stock_in_id}/complete`：确认完成
     - `POST /{stock_in_id}/cancel`
     - `POST /{stock_in_id}/return`：退回（含库存/流水联动）

3) 合作者路由注册：`backend/app/main.py`
   - Sales_Purchase 增加：
     - `app.include_router(stock_in.router, prefix="/api/stock-in", tags=["库存管理"])`
     - `app.include_router(outsource.router, prefix="/api/outsource", tags=["委外管理"])`

4) 合作者删除“采购入库”入口：`frontend/src/components/Layout.vue`
   - Sales_Purchase 在采购管理子菜单中删除：
     - `<el-menu-item index="/purchase/receipts">采购入库</el-menu-item>`
   - 改为库存管理新入口：
     - `/inventory/stock-ins`（成品入库）
     - `/inventory/material-ins`（原料入库）

5) 主线保留/强化采购入库链路（未删除）：
   - `backend/app/models/purchase.py` 保留 `PurchaseReceipt/PurchaseReceiptItem` 模型
   - `backend/app/routers/purchase.py` 仍实现采购入库相关接口（并扩展 `PurchaseRequisition`）
   - `frontend/src/router/index.js` 主线保留路由：
     - `purchase/receipts -> PurchaseReceipts`
   - `frontend/src/components/Layout.vue` 主线保留菜单：
     - `purchase/receipts -> 采购入库`

**合并影响：**  
若直接 merge，会同时存在：
- 主线：`po_receipt` + `PurchaseReceipts.vue` + `purchase/receipts`
- 合作者：`StockInOrder` + `StockIns/MaterialIns` + `inventory/stock-ins|material-ins`

并导致：
- 同一业务“采购入库/收货”有两套入口、两套模型、两套状态口径；
- `backend/app/models/__init__.py`、`backend/app/main.py`、`Layout.vue`、`router/index.js` 几乎必冲突。

---

### 3.2 转直采/转委外流程（销售明细直驱 vs PR 驱动）

**结论：两套流程口径直接冲突。**

**合作者方向（销售明细直驱）：**
- 销售明细行操作改为：`转直采/转外发`
- 采购侧增加 `sales_item_id/sales_order_no/from_sales` 用于关联
- 路由新增：
  - `backend/app/routers/purchase.py`：`GET /purchase/sales-to-purchase`
- 前端新增工作页：
  - `frontend/src/views/purchase/PurchaseFromSales.vue`
  - `frontend/src/views/outsource/OutsourceFromSales.vue`
- `frontend/src/views/sales/SalesOrders.vue` 把操作改为“转直采/转外发”入口

**主线方向（PR 驱动）：**
- `backend/app/models/purchase.py` 新增 `PurchaseRequisition`
- `backend/app/models/production.py` 新增：
  - `ProductionOrder.production_type`（自产/委外/外购）
  - `ProductionOrder.requisition_id`
- `backend/app/routers/production.py` 新增：
  - `/productions/{prod_id}/set-production-type`
  - `/productions/{prod_id}/to-requisition`
- `backend/app/routers/purchase.py` 新增：
  - `/requisitions/...`、`to-purchase`、`close`
- `frontend/src/views/purchase/PurchaseRequisitions.vue`（主线独有页面）

**合并影响：**
- 销售明细状态机不同：
  - 合作者：`已通知入库` 展示为“转直采”、`已通知外发` 展示为“转外发”
  - 主线：生产订单维护备货方式后再驱动采购需求
- 采购订单来源字段口径不同：
  - 合作者：`sales_item_id/sales_order_no`
  - 主线：`requisition_id/product_id`（并支持按 PR 回写生产订单状态）
- 合并后会形成“双轨采购入口 + 双口径状态流转”，极易数据错乱。

---

### 3.3 委外模块（主线删 vs 合作者复活）

**结论：高冲突，且主线有“删旧模型”迁移脚本。**

**主线侧：**
- `scripts/migrate_remove_outsourcing.py`：
  - `DROP TABLE mo_outsourcing`
  - `DROP TABLE mo_outsource_receipt`
  - `mo_material_issue` 重建去掉 `outsource_id`
- `backend/app/models/production.py`：
  - 删除 `OutsourcingOrder/OutsourceReceiptItem`
- `backend/app/models/__init__.py`：
  - 移除上述旧模型导出

**合作者侧：**
- `backend/app/models/production.py` 新增新模型：
  - `OutsourceOrder`（表 `os_order`），关联 `sales_order_id/sales_item_id/product_id/outsourcer_id`
- `backend/app/routers/outsource.py` 新增完整委外模块：
  - 审核->生成应付 + 生成待入库单
  - 取消审核/删除/转委外状态计算
- `frontend/src/views/outsource/OutsourceFromSales.vue/OutsourceOrders.vue` 新增页面
- `Layout.vue` 新增“委外管理”菜单组

**合并影响：**
- 若直接合并，会同时出现：
  - 主线删旧委外脚本/代码（且可能已在某些环境执行）
  - 合作者新增 `os_order` 与新委外业务模型
- 若迁移脚本与代码顺序不一致，容易造成：
  - 表不存在/字段缺失
  - 生产发料/委外发料状态链不一致

---

### 3.4 参数设置/列拖拽/列设置弹窗（合作者独有，主线已认可移植）

**结论：合作者独有，但属于低冲突高收益移植项。**

**合作者独有：**
- `backend/app/main.py`：增加 `_seed_params(db)`
- `backend/app/routers/foundation.py`：增加 `SystemParam` CRUD/选项查询/删除守卫
- `frontend/src/views/foundation/SystemParams.vue`
- 列拖拽/列设置基础能力：
  - `frontend/src/composables/useColumnDrag.js`
  - `frontend/src/composables/useColumnCustomize.js`
  - `frontend/src/composables/useColumnAutoFit.js`
  - `frontend/src/components/ColumnOrderDialog.vue/ColumnSettingsDialog.vue`
  - `frontend/src/assets/drag-fix.css`
- 大量页面接入列拖拽（SalesOrders/PurchaseOrders/InventoryManagement/ProductionOrders 等）

**主线侧：**
- `backend/app/routers/foundation.py` 主线也有仓库/汇率等改造，但未见 `SystemParam`
- 主线页面多处保留静态列结构，未见拖拽组件体系

**合并影响：**
- 直接合并不会与主线发生“删除/替代式冲突”，但需要在主线新增基础组件 + 路由/菜单。
- 属于“先接基础能力，再逐页接入”的可控移植。

---

## 4. 功能差距矩阵（按模块）

> 说明：  
> 🔴 值得移植（高价值/决策已确认）  
> 🟡 需评审（有业务口径差异或冲突风险）  
> 🟢 已覆盖（主线已有相似能力）  
> ⛔ 废弃/冲突（不建议原样合并）

### 4.1 基础档案 / 系统设置

| 功能 | Sales_Purchase | main | 判定 |
|---|---:|---:|---|
| 参数设置模块（SystemParam CRUD + 菜单） | ✅ | ❌ | 🔴 值得移植（P0） |
| 列拖拽/列设置弹窗（通用能力） | ✅ | ❌ | 🔴 值得移植 |
| 列宽自适应（useColumnAutoFit） | ✅ | ❌ | 🔴 值得移植（最后做） |
| 仓库维护/停用按钮（基础档案） | ✅ | ✅（Warehouses.vue） | 🟢 已覆盖（实现差异需对比） |
| 客户/供应商扩展字段 + 删除守卫 | ✅ | 🟢（main 也有部分） | 🟢 已覆盖（按代码差异择优） |

### 4.2 采购线

| 功能 | Sales_Purchase | main | 判定 |
|---|---:|---:|---|
| 采购订单主从布局 + 合计栏 | ✅ | ❌ | 🔴 值得移植 |
| 销售订单转采购（PurchaseFromSales） | ✅ | ❌ | 🔴 值得移植（但需定义口径） |
| 采购订单主表瘦身（删财务列） | ✅ | ❌ | 🔴 值得移植（UI） |
| 采购订单关联 `sales_order_no/from_sales` | ✅ | ❌ | 🟡 需评审（与 PR 口径冲突） |
| 采购需求（PR）模块 | ❌ | ✅ | 🟢 已覆盖（主线独有） |
| 采购入库链路（po_receipt） | 合作者弱化 | 主线保留/强化 | ⛔ 冲突（不能原样并存） |

### 4.3 销售线 / 发货工作台

| 功能 | Sales_Purchase | main | 判定 |
|---|---:|---:|---|
| 销售订单主从联动 + 列设置 | ✅ | ❌ | 🔴 值得移植 |
| 发货工作台核心后端/双栏 UI | ✅ | ❌ | 🔴 值得移植 |
| 销售退货红冲明细（main 已做） | ❌ | ✅ | 🟢 已覆盖 |
| 待处理标记列（pending_count） | ✅ | ❌ | 🟡 需评审 |

### 4.4 生产线 / 委外线

| 功能 | Sales_Purchase | main | 判定 |
|---|---:|---:|---|
| 委外订单模型（OutsourceOrder/os_order） | ✅ | ❌（主线删旧模型） | 🟡 需评审（不建议直接 merge） |
| 生产订单备货方式（自产/委外/外购） | ❌ | ✅ | 🟢 已覆盖 |
| 生产订单 → PR → PO 链路 | ❌ | ✅ | 🟢 已覆盖 |
| 完工入库/生产工作台（main 改造） | 部分 | ✅ | 🟢 已覆盖 |

### 4.5 库存线

| 功能 | Sales_Purchase | main | 判定 |
|---|---:|---:|---|
| 统一入库单（StockInOrder） | ✅ | ❌ | 🟡 需评审（替掉采购入库链路） |
| 收发存独立页 StockSummary | ✅ | ❌ | 🔴 值得移植 |
| 盘点模块（Stocktake） | ❌ | ✅ | 🟢 已覆盖 |
| 单据号/批次号统一规则（短号+flush） | ✅ | ❌ | 🔴 值得移植（按合作者规则） |
| 自动编码（产品FG/材料RM等） | ✅ | 部分 | 🔴 值得移植 |

### 4.6 财务/报关/退税

| 功能 | Sales_Purchase | main | 判定 |
|---|---:|---:|---|
| 报关明细化/退税双端（main） | ❌ | ✅ | 🟢 已覆盖 |
| 应收/应付页面列拖拽等 UI 改造 | ✅ | ❌ | 🔴 值得移植（UI层） |

---

## 5. 合并策略建议

### 结论：**不要整体 merge；推荐“以 main 为基准，按功能簇 cherry-pick 移植 Sales_Purchase”**（两条主线并行后再汇入）。

### 理由（代码级）

1. **业务主链冲突过大**  
   - 合作者把“销售->采购->入库”改成销售明细直驱 + StockInOrder；
   - 主线保留/强化 `PR -> PO -> po_receipt -> mo_receipt` 链路。
   - 两者在同一组文件（`purchase.py/sales.py/inventory.py/main.py/Layout.vue/router/index.js`）形成结构性冲突。

2. **委外模型方向相反**  
   - 主线执行过 `scripts/migrate_remove_outsourcing.py` 删旧模型；
   - 合作者新增 `OutsourceOrder(os_order)` 复活整套委外。
   - 若直接 merge，迁移历史与代码目标不一致。

3. **权限/路由/菜单体系不一致**  
   - 主线已全面加 `meta.perm + hasPerm + require_permission`；
   - Sales_Purchase 页面大量未挂 perm。
   - 直接合并会破坏主线权限闭环。

4. **数字精度口径双轨**  
   - Sales_Purchase 把汇率/本币/不含税相关改为 `round(...,6)`；
   - 主线这些位置仍为 `round(...,2)`。
   - 直接合并会形成同接口两种精度口径，财务对账风险高。

---

### 建议移植路径（分三批）

#### P0：低冲突高价值（先做）
- 参数设置模块（`SystemParam` + 菜单 + 路由）
- 列拖拽/列设置基础组件（composables/dialog/css）
- 收发存独立页 `StockSummary.vue`
- 自动编码/单据号规则统一（`batch_no.py` 改短号 + flush）
- 表格合计栏/列宽自适应能力接入（先接 2-3 个代表页验证）

#### P1：中冲突但业务价值高（需要业务口径收敛）
- 发货工作台核心后端 + 双栏 UI（需确认与主线销售退货红冲并存方案）
- 采购订单主从布局升级 + 销售单号列展示
- 基础档案增强（产品关联客户/扩展字段/删除守卫）

#### P2：高冲突模块（必须业务评审/改造后再接）
- 统一入库模型 `StockInOrder`（或做“兼容层”：SP 生成 StockInOrder，同步写 `po_receipt/mo_receipt`）
- 转直采/转委外流程（需与 PR 驱动流程统一状态机定义）
- 委外模块复活（需决定：保留主线删旧模型路径，还是正式以 `OutsourceOrder` 新模型替代）

---

## 6. 风险清单

### R1. 菜单/路由消失或重复
- **现象**：`Layout.vue/router/index.js` 两端差异大；若整体 merge，极易出现菜单项丢失或重复
- **缓解**：不整体 merge；按模块接菜单，并做菜单全量 diff 对照表

### R2. 权限体系回归
- **现象**：主线所有页面已接 `meta.perm`，Sales_Purchase 多数页面未接；合并后无权限页面可能裸露
- **缓解**：移植页面时必须补齐 `meta.perm` + 菜单 `v-if="hasPerm(...)"`；后端操作接口补 `require_permission`

### R3. 数据模型/迁移冲突
- **现象**：主线有多个迁移脚本（删委外表、盘点表、po_receipt_item 重建等）；合作者新增 `StockInOrder/OutsourceOrder/SystemParam`
- **缓解**：所有模型变更走统一迁移脚本；迁移脚本必须幂等；合并前盘点 DB schema diff

### R4. 采购入库链路断裂
- **现象**：Sales_Purchase 删除“采购入库”入口并弱化采购入库流程；主线保留
- **缓解**：短期保留主线采购入库；SP 能力以“增强视图/兼容接口”方式接入，不做删链

### R5. 财务口径漂移（金额/税额精度）
- **现象**：两端汇率/不含税价精度不一致
- **缓解**：统一精度规范（建议：计算 6 位，持久化/返回 2 位；或引入精度常量/工具函数）

---

## 7. 08-09 数字精度冲突专项（重点）

### 7.1 已验证到的“精度撞车点”

**Sales_Purchase（2026-08-09，8ac065b）改为 6 位中间精度：**
- `backend/app/routers/sales.py`（Sales_Purchase）：
  - `order.total_amount_local/tax_amount/excl_tax/excl_tax_local` 改为 `round(...,6)`
  - 创建订单时：
    - `tax_amount_local += round(...,6)`
    - `total_excl_tax_fc/local = round(...,6)`
    - `unit_price_local/total_amount_local/excl_tax_local` 改为 `round(...,6)`
- `frontend/src/main.js`（Sales_Purchase）：
  - `$fq(...)` 全局数量显示从 `4 位` 改为 `2 位`

**origin/main（2026-08-01）仍保留 2 位：**
- `backend/app/routers/sales.py`（main）：
  - 同一组计算仍使用 `round(...,2)`（如 `tax_amount_local/total_excl_tax_fc/local` 等）
- `frontend/src/main.js`（main）：
  - `$fq(...)` 仍为 `4 位`

### 7.2 这是“同一批代码”的冲突吗？
**是。**  
两边都在改 `backend/app/routers/sales.py` 的订单创建/重算函数和 `frontend/src/main.js` 的全局格式化。  
且都落在 8/1-8/9 这个窗口，属于“同一业务场景、同一文件、两种精度口径”。

### 7.3 为什么直接合并会出问题？
- 同一接口返回金额精度不一致，前端汇总/合计栏会与后端对不上；
- 财务模块（应收/应付/发票）按金额聚合时，6 位与 2 位舍入路径会导致“差几分”问题；
- 数量精度若从 4 位突然变 2 位，历史数据展示/校验阈值可能回退。

### 7.4 建议解决方案（推荐方案 A）

#### 方案 A（推荐）：统一精度规范 + 引入精度工具
- **中间计算**：汇率/本币换算/不含税价保留 `6 位`
- **持久化与接口返回**：金额字段统一 `2 位`，数量字段统一 `2 位`（若业务需要可保留 4 位）
- **前端展示**：
  - 金额 `$fm`：2 位
  - 数量 `$fq`：2 位（或按场景 2/4 位可配置）

#### 方案 B：保留主线 2 位（保守）
- 暂不引入 6 位中间精度，避免财务口径变化；
- 适合“先稳后改”阶段。

### 7.5 执行建议
1) 在 main 增加 `precision policy` 文档（明确：计算精度、存储精度、展示精度）
2) 在后端增加统一工具（如 `round_money/round_qty`）
3) 在合并 PR 中逐文件替换裸 `round(...,2/6)`，避免散落逻辑
4) 增加金额精度回归用例（订单创建、发货、退货、发票、汇率换算）

---

## 8. 合并执行建议（给验收方）

1) **不要** `git merge Sales_Purchase into main`（或反向）。  
2) 建立“主线 main 为集成主干”，从 Sales_Purchase **按功能簇 cherry-pick/移植**：
   - 先基础能力（参数设置 + 列拖拽 + 编码规则）
   - 再 UI 改造（订单主从、发货工作台 UI）
   - 最后业务链路重构（StockInOrder/转直采转委外/委外模块）  
3) 每个功能簇：
   - 先列影响文件清单（backend model/router/schema + frontend view/router/layout）
   - 再做“移植后权限补齐 + 菜单补齐 + 精度统一”
   - 最后跑主线测试（后端契约/状态机 + E2E 冒烟）  
4) 重点盯 43 个交集文件的变更，尤其是：
   - `backend/app/main.py`
   - `backend/app/models/inventory.py/purchase.py/production.py`
   - `backend/app/routers/inventory.py/purchase.py/sales.py`
   - `frontend/src/components/Layout.vue`
   - `frontend/src/router/index.js`
   - `frontend/src/views/inventory/InventoryManagement.vue`

---

## 附录：本次分析使用的关键只读命令（可复核）

```bash
# 分支与分叉点
git rev-parse --short origin/main
git rev-parse --short HEAD
git merge-base origin/main HEAD
git rev-list --left-right --count origin/main...HEAD

# 时间线
git log --oneline --decorate origin/main...HEAD
git log --format="%ad %s" --date=short origin/main..HEAD
git log --format="%ad %s" --date=short HEAD..origin/main

# 文件面
git diff --name-only origin/main...HEAD
git diff --name-only HEAD...origin/main
comm -12 /tmp/_files_sp_from_main.txt /tmp/_files_main_from_sp.txt

# 关键代码差异
git diff origin/main...HEAD -- backend/app/main.py
git diff origin/main...HEAD -- backend/app/models/inventory.py
git diff origin/main...HEAD -- backend/app/routers/inventory.py
git diff origin/main...HEAD -- backend/app/routers/sales.py
git diff HEAD...origin/main -- backend/app/routers/sales.py
```

---

## 附录：最关键 3 个风险（总结）

1. **采购入库/收货主链双轨冲突**（StockInOrder vs po_receipt + PR 驱动）  
2. **委外模块方向冲突**（主线删旧模型 + 合作者复活新模型）  
3. **数字精度口径冲突**（同一批计算代码：6 位 vs 2 位）

> 最终建议：  
> 以 `main` 为唯一主干，采用“功能簇 cherry-pick + 口径收敛 + 权限补齐”方式整合 Sales_Purchase，避免整体 merge 带来结构性回归。
