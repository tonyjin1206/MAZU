# MTS 已知问题清单（Known Issues）

> 由 `scripts/test_robust.py` 健壮性测试 + 自动化测试套件（tests/）自动发现。
> 状态：`遗留` = 用户确认暂不修复；`已修复` = 已处理；`待修` = 排队修复。

## 数据完整性

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 1 | 负数数量订单被接受 | 200 创建成功 | 422 拒绝 | ✅ **已修复**（sales.py 数量校验） |
| 2 | 零数量订单被接受 | 200 创建成功 | 422 拒绝 | ✅ **已修复**（sales.py 数量校验） |
| 3 | 采购入库超量无校验 | PO订100，二次入50 仍接受(累计150) | 400 拒绝 | **遗留**（用户确认） |
| 4 | 生产完工入库超量被接受 | 重复入库仍 200 | 400 拒绝 | **遗留**（与#3同类） |
| 5 | 供应商/客户 code 无唯一约束 | 重复 code 允许创建 | 409 拒绝 | ✅ **已修复**（foundation.py 409 校验） |
| 15 | **取消完工入库删台账行导致账实不符（P0）** | 批次已发货仍可取消 → 流水累计≠台账（+100-60-100=-60） | 有出库禁止取消 | ✅ **已修复**（2026-07-31：production.py cancel_receipt 校验批次无其他出入库；配套新增 销售退货 通道） |
| 16 | **采购取消入库物理删除流水** | delete_receipt 删除原流水，无审计轨迹 | 保留原流水+补冲销流水 | ✅ **已修复**（2026-07-31：purchase.py 补 purchase_return_out 冲销流水；批次已消耗场景改走红冲） |
| 17 | **发料流水类型统一 outsource_out** | 自产领料与委外发料无法区分 | 拆 material_issue_out/outsource_out | ✅ **已修复**（2026-07-31：production.py 按工序 outsourcer_id 区分；scripts/migrate_inventory_v2.py 迁移历史流水） |

## 错误处理（500 崩溃）

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 6 | BOM 引用不存在材料 | 500 | 400/404 | ✅ **已修复**（foundation.py 外键校验） |
| 7 | 不存在客户下单 | 500（外键未校验） | 400/404 | ✅ **已修复**（sales.py 客户校验） |
| 8 | 重复发票号 | 500（唯一约束未捕获） | 409 | ✅ **已修复**（purchase.py 409 校验） |
| 9 | 数量传非数字字符串 | 500（类型转换未捕获） | 422 | ✅ **已修复**（sales.py try/except） |
| 10 | 重复供应商 code | 500（唯一约束未捕获） | 409 | ✅ **已修复**（foundation.py 409 校验） |
| 13 | **采购入库必 500（BUG#1）** | 任何入库崩溃：purchase.py 传 product_id 给无此字段的 PurchaseReceiptItem；且 material_id NOT NULL 挡成品 | 200 正常入库 | ✅ **已修复**（2026-07-31：模型加 product_id 列、material_id 改可空、delete_receipt 双路径回滚；迁移脚本 scripts/migrate_po_receipt_item.py；成品采购入库全链路验证通过） |

## 权限

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 14 | GET /auth/users 只认证不授权 | 任何登录用户可查看用户列表（仅 get_current_user） | 仅管理员可看 | ✅ **已修复**（2026-07-31：auth.py 的 GET /users、/users/{id}、/roles、/permissions 加 require_permission("menu:system:users")，低权限角色 403） |
| 18 | **业务单据写端点只认证不授权（BUG-L4-01）** | 只读/库管员可通过 API 对销售订单等增删改（仅 get_current_user，无 require_permission） | 低权限写 403 | ✅ **已修复**（2026-08-28：sales/foundation/inventory 62 个写端点统一补 require_permission，与 approve 端点对齐；只读角色对 POST/PUT/DELETE /api/sales/orders 现 403） |
| 20 | **采购/生产/委外/待入库/退税写端点只认证不授权（BUG-L4-01 扩展）** | 只读/库管员可通过 API 增删改采购订单、生产订单、委外订单、待入库收货、退税申报（purchase/production/outsource/stock_in/tax_refund 仅 get_current_user） | 低权限写 403 | ✅ **已修复**（2026-08-30：5 个模块 60+ 写端点统一补 require_permission / require_any_permission（按业务域）；读端点补 require_any_permission（本域+业务引用域）；新增 test_rbac_l4_extended.py 8 用例验证越权 403 + 合法角色 200） |
| 19 | **业务单据/基础档案读端点只认证不授权（BUG-L4-02）** | 库管员/只读可全量读取基础档案（供应商/产品/材料）与销售订单（仅 get_current_user，无 require_permission） | 低权限读 403 | ✅ **已修复**（2026-08-28：sales/foundation/inventory 读端点补 require_permission / require_any_permission（本域+业务引用域）；库管员读档案/订单 403、读库存仍 200；只读读 sales/foundation/inventory 全 403） |
| 21 | **采购/生产/委外/待入库/退税读端点只认证不授权（BUG-L4-02 扩展）** | 只读/库管员可全量读取采购/生产/委外/退税单据（仅登录校验） | 低权限读 403 | ✅ **已修复**（2026-08-30：与 #20 一并修复，读端点按「本域+业务引用域」授权；库管员读库存/入库页 200、读采购/生产/退税 403） |

## 驾驶舱/报表

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 22 | **两段式发货毛利漏算（P1）** | 通知→库管出库后发货单 status=已出库/部分出库、流水 source_doc_type=成品出库；dashboard 毛利只查「已发货/部分发货」状态 + 「销售发货」流水 → 两段式发货完全不进毛利（成本=0、收入=0） | 两段式发货计入毛利 | ✅ **已修复**（2026-08-30：dashboard.py 状态过滤加入 已出库/部分出库，成本流水加入 成品出库） |
| 23 | **销售退货不冲减毛利（P1）** | 退货单（is_return=1）revenue 按正数计算 → 毛利不冲减 | 退货负向冲减收入/成本 | ✅ **已修复**（2026-08-30：dashboard.py 毛利计算按 is_return 取负；配套 test_dashboard_profit.py 2 用例） |

## 边界场景

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 24 | **待入库单退回扣负库存（P2）** | 同一待入库单多次收货后（同批次多条台账记录），return_stock_in 只扣第一条记录且不校验足够性 → 退回量大于首条时库存变负 | FIFO 逐条扣减，库存不为负 | ✅ **已修复**（2026-08-30：stock_in.py 退回改为按 id 顺序逐条扣减+逐条流水，不足 400；配套 test_edge_cases.py） |
| 25 | **多次部分认领累计状态不更新（P2）** | claim_batch 只按本次认领量判断状态，多次部分认领累计达量后明细行仍「部分入库」 | 累计认领量 ≥ 订单量 → 已入库 | ✅ **已修复**（2026-08-30：sales.py 认领前统计历史认领量后累加判断） |
| 26 | **仓库类型两套取值致自动匹配失败（P2）** | Warehouses.vue 用「原料仓/成品仓」、SystemParams.vue 用「原辅料仓库/成品仓库」；stock_in 收货自动匹配只查「原辅料仓库/成品仓库」→ 用「成品仓」建仓时收货 400 | 兼容两套类型 | ✅ **已修复**（2026-08-30：stock_in.py 自动匹配 in_ 两套取值） |

## 架构规范遗留

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 27 | **前端散写 request 回退（规范）** | v2.2.0 曾清零散写，v2.8.0 三分支开发后 28 页面 190+ 处直接 `request.get/post/...`（未走 api/*.js 封装） | 统一走 api/*.js | ✅ **已修复**（2026-08-30：28 页面全部迁移至 api/*.js 封装；补 salesApi/purchaseApi/outsourceApi/inventoryApi/taxRefundApi 缺失方法 + foundationApi.params/productCustomers；架构检查散写清零；顺带修复 taxRefundApi.refund 缺 body 参数缺陷） |

## AI 助手

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 28 | **AI 录采购发票不生成应付/进项发票（P1）** | `_execute_create_purchase_invoice` 只插 PurchaseInvoice，不生成应付账款（AP）与进项发票（tr_input_invoice）→ 采购发票无法付款核销、退税无法关联 | 与人工 create_invoice 一致：生成 AP + 可抵扣类型同步进项发票 | ✅ **已修复**（2026-08-30：ai_chat.py 对齐 create_invoice 业务逻辑，含发票号唯一校验；配套 3 个测试） |
| 29 | **AI 录销售发票不生成应收账款（P1）** | `_execute_create_sales_invoice` 只插 SalesInvoice，不生成应收（AR）→ 无法收款核销 | 与人工 create_sales_invoice 一致：生成 AR（含到期日） | ✅ **已修复**（2026-08-30：同上） |
| 30 | **list_sales_orders 批量聚合变量名错误（P1）** | N+1 优化引入 `inv_ids` 未定义（应为 all_inv_ids），订单有发票时 GET /sales/orders 必 500 | 正常返回 | ✅ **已修复**（2026-08-30：sales.py 修正变量名；被新增 AI 发票测试暴露） |

## 数据完整性

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 31 | **采购双轨入库可重复（P2）** | 采购明细转待入库单（receive_type=成品库/原料库）后，采购入库页（po_receipt）仍可再次入库 → 库存/已收数量翻倍 | 已转待入库单的明细禁止走采购入库页 | ✅ **已修复**（2026-08-30：create_receipt 校验 receive_type；配套 test_edge_cases 用例） |

## 业务校验缺失

| # | 问题 | 现状 | 期望 | 状态 |
|---|------|------|------|------|
| 11 | 未审核采购订单可入库 | 200 | 400 拒绝（状态未校验） | ✅ **已修复**（purchase.py 状态校验） |

## 测试误报澄清

| # | 问题 | 澄清 | 状态 |
|---|------|------|------|
| 12 | 取消工序完工接口"缺失" | 实际已存在 `POST /processes/{id}/revert`，测试脚本路径写错（cancel-finish） | ✅ 测试已修正 |

---

## 复现方式

```bash
# 全量测试（已修复项自动转为 PASS）
python scripts/test_robust.py
```

退出码 0 = 无未知失败（已知问题以 ⚠️ 标记，不计入失败）。
