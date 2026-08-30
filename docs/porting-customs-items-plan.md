# 报关单明细化移植方案（app-optimization c08dee7 → main）

> 状态：**✅ 已完成**（2026-08-30：模型/迁移/后端/前端/测试全部落地，282 后端测试全绿）
> 来源：app-optimization 分支 `c08dee7 feat: 报关单明细化 + 退税申报双端匹配 + 草稿模式（v2.6.0）`
> 目标：main 的报关单从「一单一 HS」升级为「一票多商品多 HS」，退税申报支持报关单商品行 ↔ 进项发票双端匹配。

## 一、main 现状（2026-08-30）

- `CustomsDeclaration`（so_customs）单表：`hs_code_id` NOT NULL、`declare_amount` 单值 —— **一票一商品一 HS**
- 退税申报明细 `TaxRefundDeclarationRow`：手动录入（选进项发票），不关联报关单商品行
- 负数申报（批2）：`return-candidates` / `return-adjustments` 走退货单维度

## 二、AO 实现要点（c08dee7）

### 1. 模型
- 新建 `so_customs_item`（CustomsDeclarationItem）：customs_id / product_id / hs_code_id / quantity / unit_price / amount / seq
- `CustomsDeclaration.hs_code_id` 改可空（表头不再必须）
- `TaxRefundDeclarationRow.customs_item_id`（出口端报关单商品行）+ `input_invoice_id`（采购端进项发票）双端匹配

### 2. 路由
- sales.py：创建/列表/详情/编辑/删除报关单全链路适配商品行；重复报关三重校验；已申报退税禁删
- tax_refund.py：`_recalc_declaration` 出口 FOB = 明细行汇总；仅已放行/已结关可报税；行增/改/删触发重算

### 3. 前端
- `CustomsDeclarations.vue`：商品行表格编辑 + 状态流转（已报关→已放行→已结关）
- `TaxRefundDeclarations.vue`：双端匹配选择（报关商品行 + 进项发票）

### 4. 迁移与测试
- `scripts/migrate_customs_items.py`（幂等：旧报关单自动回填商品行）
- `test_customs_items.py` 8 专项（商品行/去重/状态拦截/双端/表头重算）

## 三、移植步骤（建议顺序）

1. **模型 + 迁移**：建 `so_customs_item`、`hs_code_id` 改可空、`tr_declaration_row.customs_item_id`；迁移脚本回填旧数据
2. **后端 sales.py**：报关 CRUD 商品行适配（复用 AO 代码，注意 main 的 require_permission 已不同）
3. **后端 tax_refund.py**：双端匹配 + 重算（注意与批2 负数申报的 `return-adjustments` 共存）
4. **前端**：CustomsDeclarations.vue / TaxRefundDeclarations.vue 适配
5. **测试**：移植 test_customs_items.py 8 用例 + 回归 269 全量

## 四、风险与注意事项

- **与批2 负数申报交互**：`return-adjustments` 的负数行如何参与 export_amount_fob 重算，需与 AO 实现核对（AO 是在加明细化之前实现的负数申报，main 是之后）
- **权限**：main 报关/退税端点已补 require_permission（上轮完成），移植时保留
- **退税状态机**：main 的 declaration 状态（待申报/已申报/已退税）与 AO 一致，可复用
- **数据兼容**：已有报关单需迁移脚本回填商品行，否则详情页商品行为空

## 五、验收标准

- 一票多商品报关创建/编辑/删除全链路 200
- 已申报退税的报关单禁删（400）
- 退税申报行可同时选报关商品行 + 进项发票，出口 FOB 自动重算
- 迁移脚本幂等（旧数据回填、空库安全）
- 全量 269 后端 + E2E 59 保持全绿
