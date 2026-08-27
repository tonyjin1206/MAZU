# 批 2 移植方案：销售退货财务层补强（发票红冲 · 红字应收 · 退款 · 核销转移 · 负数申报）

> 状态：**已定稿并确认（2026-08-27）**
> 基底：`sp-porting`（SP 流程为准）；来源：AO v2.5.2 + 审核锁定（08f86b2 部分）
> 原则：不 cherry-pick，按 SP 现状重写；UI 以 SP 为准；每步可独立验证
> **已确认的决策**（见 §七）：①ArAdjustment 用 AO 双字段（source_ar_id/target_ar_id）②红字应收 status 沿用 SP 枚举+is_red 区分 ③退款撤销走 delete_collection ④红字应收不触发 AR_CREATED ⑤退货按 SP 三端点命名加逻辑

---

## 一、现状 vs 目标

| 能力 | SP 现状 | 目标（AO v2.5.2 移植） |
|---|---|---|
| 发票 | 创建自动生成应收；删除有已收款拦截；无红字概念 | **发票红冲**（红字票=手工录入、金额=原票全额负数）；蓝字开票上限校验（≤订单未开票金额） |
| 应收 | 未收款/部分收款/已收款；无红字 | **红字应收**（红冲自动等额联动，is_red）；列表红负绿正 |
| 收款 | 正数核销 + cancel-collection 撤销；无负数 | **退款=负数收款单**（线下手工退款登记）；收款删除回滚方向适配红字 |
| 核销 | 无转移概念 | **核销转移**（同客户、双向上限校验、写 ar_adjustment 留审计） |
| 退货 | 发货层退货 3 端点（登记/出库红冲）；无发票联动 | 退货时**发票状态提示 + refund_declared 打标**；负数申报入口 |
| 申报 | 无负数行概念 | 申报明细支持**负数行**（退货冲减，voucher 手填）；return-candidates 端点 |

## 二、模型改动（迁移脚本：scripts/migrate_batch2_finance.py）

| 表 | 加字段 | 说明 |
|---|---|---|
| `so_invoice` | `is_red` (0/1)、`red_of_invoice_id` (FK→so_invoice.id, 可空) | 红字标记 + 原票引用 |
| `ar_account` | `is_red` (0/1)、`red_of_ar_id` (FK→ar_account.id, 可空) | 红字应收标记 |
| `so_delivery` | `refund_declared` (0/1, 默认0) | 已报税退货标记（负数申报用） |
| 新建 `ar_adjustment` | id/adjust_no/ar_id/customer_id/adjust_type/amount/old_value/new_value/operator/remark/created_at | 核销转移审计表 |

## 三、后端改动（routers/sales.py，按 SP 现状合并）

### 3.1 发票红冲（create_sales_invoice / PUT / DELETE）
1. **create_sales_invoice 支持红字**：`is_red=1` 时必填 `red_of_invoice_id`（原票必须存在、必须已开票蓝字、必须未红冲过、金额强制=原票全额负数）；生成**红字应收**（负数、is_red=1、red_of_ar_id=原应收）
2. **蓝字开票校验**：金额 ≤ 订单未开票金额（订单已开票金额累计 - 红冲金额累计）
3. **红字票禁改禁删**（PUT/DELETE 拦截）
4. 蓝字票删除：已红冲的禁删（需先删红字票）

### 3.2 收款/退款（create_collection / DELETE）
1. **create_collection 支持 amount<0 退款**：负数时核销**红字应收**（红字应收 balance<0，退款把它往 0 拉）；退超拦截（退款额 ≤ 红字应收未退余额）
2. **收款 DELETE 回滚方向适配**：正数收款删→应收 balance 加回；负数退款删→红字应收 balance 减回
3. 与 SP 已有 `cancel-collection` 并存：cancel-collection 撤销正数收款（SP 现状不动）；负数退款走 DELETE（AO 模式）或同样可 cancel——**待定：建议负数退款也走 cancel-collection 对称逻辑，前端统一**

### 3.3 核销转移（POST /ar/transfer，新增）
- 参数：`from_ar_id`、`to_ar_id`、`amount`；校验：同客户、from 余额够、to 未超额（to.balance 增加不超其总额？——AO 语义：转移核销金额，双向上限）
- 写 `ar_adjustment` 审计行；from.balance 增、to.balance 减（核销额移动）

### 3.4 退货联动（SP 3 个退货端点加逻辑）
- SP `deliveries/return`（登记）：检查该订单是否已开票（msg 提示"已开票，需同步红冲发票"）
- SP `issue-return`（库管红冲）：检查发货已报关 → 提示/打标 refund_declared
- 新端点：`GET /deliveries/return-candidates`（已报税退货清单，负数申报用）

### 3.5 负数申报（tax_refund.py）
- 明细行 add_row 支持负数（voucher_type=退货冲减、voucher_no 手填，无发票/报关单）
- `GET /declarations/{id}/return-candidates`：已报税退货候选
- 申报表 export_amount_fob 重算含负数行

## 四、前端改动（UI 以 SP 为准）

| 页面 | 改动 |
|---|---|
| `SalesInvoices.vue` | 红冲按钮（已开票蓝字行）、红冲票号列、红字票删除按钮隐藏、开票上限提示、红字票样式（红） |
| `AccountsReceivable.vue` | 红负绿正（balance<0 红 / >0 绿）、退款弹窗（负数收款登记）、核销转移弹窗 |
| `Collections.vue` | 负数金额标红、退款类型标签（"退款" tag） |
| `SalesDeliveries.vue` | 退货弹窗加"已开票需红冲发票"提示 |
| `TaxRefundDeclarations.vue` | 「添加退货冲减（负数申报）」入口 + 负数行标红 |
| `api/business.js` | `ar.transfer`、`deliveries.returnCandidates`、`declarations.returnCandidates` 定义 |

## 五、测试（tests/test_sales_return_red.py，按 SP 流程重写）

1. 蓝字开票 → 红冲（等额负数红字票+红字应收）→ 红字票禁改禁删
2. 蓝字开票上限校验（超订单未开票金额拒绝）
3. 退款登记（负数收款核销红字应收、退超拦截）
4. 核销转移（同客户、上限校验、ar_adjustment 审计）
5. 退货 refund_declared 打标 + return-candidates + 负数申报行
6. 收款删除回滚方向（正数/负数）

## 六、执行顺序（每步独立验证）

1. **迁移脚本**：建表加字段（幂等）+ 旧库执行
2. **后端红冲链路**：发票红冲 → 红字应收 → 退款 → 收款删除回滚（3.1+3.2）
3. **核销转移 + 退货联动 + 负数申报**（3.3+3.4+3.5）
4. **前端 6 页**（按 SP 样式）
5. **测试**（5 组专项）+ 全量回归（102 passed 基线保持）
6. **文档**：CHANGELOG/PROJECT/operations-manual

## 七、风险与待定点

1. **cancel-collection vs 退款删除**：SP 收款撤销是"标记取消"还是"删除"？——决定负数退款走哪条路（见 3.2 待定）
2. SP 发票有 invoice_type（出口发票/专票）→ 红字票继承类型
3. SP 应收 status 枚举（未收款/部分/已收款）→ 红字应收 status 用"已红冲"（AO 语义）还是沿用枚举？——建议沿用 SP 枚举 + is_red 区分
4. 负数申报依赖退货 refund_declared → 退货打标要先行
5. 核销转移与 cancel-collection 交互（转移后撤销收款？）——限制：已核销的收款不能 cancel

## 八、验收标准

- 全量测试 102+5 组专项全绿；vite build 通过
- 手工路径：建订单→发货→开票→红冲→红字应收→退款→核销转移→退货→负数申报 全链路可操作
