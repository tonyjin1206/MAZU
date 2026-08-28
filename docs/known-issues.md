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
