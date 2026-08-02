# MTS AI 助手能力全量测试报告

**日期**: 2026-08-02
**系统**: MTS v2.5.0（app-optimization 分支，全新建库）
**测试方式**: 通过 `/api/chat/message` 真实对话调用，走完整 LLM Function Calling 链路
**测试账户**: admin（管理员，全权限）
**数据基础**: init_all.py 全流程种子 + 补充待审核单/发票/应收应付

---

## 一、结论摘要

| 项目 | 结果 |
|---|---|
| 工具总数 | 13 个 |
| 全部可用 | ✅ 13/13 |
| 测试对话 | 21 轮用例 |
| 发现 Bug | 5 个（均已修复） |
| 修复后复测 | 全部通过 |

---

## 二、工具清单与测试结果

| # | 工具 | 能力 | 测试结果 |
|---|---|---|---|
| 1 | `query_entities` | 查客户/供应商/物料/产品/应收/应付/发票 | ✅ 8 种实体全通过 |
| 2 | `query_inventory` | 查库存（名称/仓库/批次） | ✅ 通过 |
| 3 | `query_pending_approvals` | 列待审核单据 | ✅ 通过 |
| 4 | `approve_order` | 审核采购/销售订单 | ✅ 通过（含生成生产订单） |
| 5 | `unapprove_order` | 反审核采购订单 | ✅ 通过（有下游单据时正确拒绝） |
| 6 | `create_order` | 创建采购/销售订单（多明细行） | ✅ 通过（修复单号撞号后） |
| 7 | `create_collection` | 收款 + 自动核销应收 | ✅ 通过 |
| 8 | `create_payment` | 付款 + 自动核销应付 | ✅ 通过 |
| 9 | `create_purchase_invoice` | 录入采购发票 | ✅ 通过 |
| 10 | `create_sales_invoice` | 录入销售发票 | ✅ 通过 |
| 11 | `issue_materials` | 生产发料（批次扣库存） | ✅ 通过（修复批次逻辑后） |
| 12 | `production_receipt` | 完工入库（成品批次入库） | ✅ 通过（修复批次逻辑后） |
| 13 | `query_manual` | 查询操作手册 | ✅ 通过 |

---

## 三、发现并修复的 5 个 Bug

### Bug 1: AI 创建订单单号撞号（严重）
- **现象**: AI 创建采购/销售订单报"UNIQUE constraint failed"，`PO-20260802-001` 与已有单据重复
- **根因**: `_execute_create_order` 调用 `generate_doc_no(db, "PO")` 未传 model 参数 → 函数默认查询库存流水表 `StockTransaction.trans_no`（该表无 PO 记录）→ 永远返回 `-001` 撞号
- **修复**: 改为 `generate_doc_no(db, "PO", PurchaseOrder, "order_no")` / `generate_doc_no(db, "SO", SalesOrder, "order_no")`
- **对照**: UI 路由 purchase.py:141 / sales.py:82 均为正确写法，AI 工具漏了

### Bug 2: 收款单号前缀错误（潜在撞号）
- **现象**: AI 收款生成 `RC-20260802-001`，与系统规范前缀 `CR-`（Collection.collection_no）不一致，二次收款会撞号
- **修复**: `generate_doc_no(db, "RC")` → `generate_doc_no(db, "CR", Collection, "collection_no")`

### Bug 3: 付款单号前缀错误（潜在撞号）
- **现象**: AI 付款生成 `PAY-20260802-001`，系统规范前缀为 `PM-`（Payment.payment_no）
- **修复**: `generate_doc_no(db, "PAY")` → `generate_doc_no(db, "PM", Payment, "payment_no")`

### Bug 4: AI 发料不走批次库存（严重，数据不一致）
- **现象**: AI 发料只插一条 `MaterialIssueItem` 记录，**不扣库存、不生成批次、无库存流水**；且 v2.5 的 MaterialIssueItem 要求 batch_no 非空导致直接报错
- **修复**: 参照 UI 端点 production.py:577 重写——自动选库存充足的最早批次 → 扣库存 → 写 StockTransaction 流水 → 更新工序状态 → 单号带 model
- **验证**: PCB电路板 200→190，流水 `material_issue_out -10（MI-20260802-001）` ✅

### Bug 5: AI 完工入库不走成品批次（严重，数据不一致）
- **现象**: AI 入库不生成 FG 批次号、不入成品库存、无流水，且 batch_no 非空约束报错
- **修复**: 参照 UI 端点 production.py:963 重写——自动生成 `FG-YYYYMMDD-NNN` 批次 → 入成品仓 → 写流水 → 更新生产单 received_qty/status
- **验证**: 入库 5 台生成 `FG-20260802-002` 批次，生产单 MO-001 状态→部分入库 ✅

> 所有单号类修复均与 UI 路由完全对齐，杜绝"AI 建的号与系统规范不一致"。

---

## 四、数据一致性验证

| 检查项 | 结果 |
|---|---|
| 发料扣库存 PCB 200→190 | ✅ 库存流水 -10 |
| 完工入库成品 +5（FG 批次） | ✅ 成品库存 5 台 |
| 收款 ¥2000 核销 AR 6780→4780 | ✅ AR 状态"部分收款" |
| 付款 ¥1000 核销 AP 3000→2000 | ✅ AP 状态"部分付款" |
| 新采购单 PO-20260802-003 待审核 | ✅ |
| 新销售单 SO-20260802-003 待审核 | ✅ |

---

## 五、说明与建议

1. **权限过滤**: `_filter_tools_for_user` 按用户菜单权限裁剪工具 + `_capability_prompt` 动态注入当前用户可用工具清单，权限链路已验证正常（admin 全量）
2. **三步确认流程**: 所有写操作 AI 均先列字段让用户确认再执行（"对/是/确认"），符合系统设计
3. **遗留提示**: 建议在后续版本把 AI 工具的 `_execute_*` 系列改为直接复用 UI 路由的 service 层逻辑，避免双份实现漂移（本次已发现 5 处漂移）
