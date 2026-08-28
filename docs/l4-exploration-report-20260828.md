# L4 真人探索报告 — MTS 外贸 ERP（P4）

- 探索人：andy（Hermes 测试工程师 Agent，L4 真人探索层）
- 时间：2026-08-28 20:00–21:10 (CST)
- 测试对象：**运行中的开发系统**（非测试库）：backend uvicorn :8788（ERP_DATA_DIR=/tmp/p4-explore-data-79692），frontend vite :5173（代理→8788）
- 依据：docs/complete-test-plan.md 第五章 L4 真人探索层 + 第六章缺陷分级
- 驱动方式：Playwright Chromium（真实浏览器，替代 computer_use——cua-driver 未就绪且 browser_exec 无法访问 localhost）驱动前端 UI + httpx 直连后端 API；全程采集 console/page/http 错误与截图

---

## 0. 基线验证（验收要求）

| 项 | 结果 |
|---|---|
| ./test.sh（后端全量，隔离库） | ✅ **242 passed, 0 skipped**（5.53s） |
| cd e2e && python -m pytest -q（59 用例，独立 8789/5174） | ✅ **59 passed, 0 skipped**（188s） |
| 前端 43 个路由页面巡检 | ✅ 全部加载，console/page/http 错误 **0**（explore_phase1.json） |
| 登录 | admin/admin123 ✅ 进入 /dashboard |

---

## 1. 探索环境

- OS：macOS 26.5.2；后端 Python 3.11 (venv)，FastAPI+SQLAlchemy+SQLite；前端 Vue3 + Element Plus + Vite
- 数据：隔离开发库（1 个 admin 用户、7 个系统角色、基础档案若干、历史 SO/PO/MO 若干）
- 浏览器：Chromium headless 1600×1000，console/page/http 三类错误全采集

---

## 2. 核心业务路径（L4 清单第 1 条）— 全部走通

路径：建档 → 销售订单 → 审核 → 转直采 → 转采购(拆单) → PO 审核 → 转成品库 → 成品收货 → 发货两步化（通知→出库）→ 发货完成 → 开票 → 红冲 → 退款 → 核销转移 → 负数申报。

| 步骤 | 端点/页面 | 结果 |
|---|---|---|
| 建档（客户/产品/HS/币种/仓库/供应商/材料/BOM） | /foundation/* + UI 建档 | ✅ 成功，0 console error |
| 销售订单创建 | POST /api/sales/orders | ✅ SO-26082808 |
| 反例：未审就发货 | POST /api/sales/deliveries/notify | ✅ **拦截** 400「订单需已审批」 |
| SO 审核 | POST /api/sales/orders/{id}/approve | ✅ 已审 |
| 反例：审核后直接改单 | PUT /api/sales/orders/{id} | ✅ **拦截** 400「仅待审核状态的订单允许修改」 |
| 转直采 | POST /api/sales/orders/{id}/items/{iid}/stock-in | ✅ |
| 转采购（BOM 拆单/无 BOM 产品本身） | POST /api/purchase/orders/from-sales | ✅ 生成 PO-26082805 |
| 反例：PO 未审入库 | POST /api/purchase/receipts | ✅ **拦截** 400「订单状态待审核不允许入库」 |
| PO 审核 | POST /api/purchase/orders/{id}/approve | ✅ |
| 转成品库入库 | POST /api/purchase/orders/{id}/items/{iid}/to-stock-in | ✅ |
| 成品收货 | POST /api/stock-in/{id}/receive | ✅ 批次 SO-26082808-01 |
| 发货两步化：通知发货 | POST /api/sales/deliveries/notify | ✅ SD-26082803 待出库 |
| 发货两步化：库管出库 | POST /api/sales/deliveries/{id}/issue | ✅ 已出库，库存扣减 |
| 发货完成 | POST /api/sales/orders/{id}/items/{iid}/delivery-confirm | ✅ 订单→已发货 |
| 反例：重复发货完成 | 同端点 | ✅ **拦截** 400「该产品行已确认过发货完成」 |
| 开票 | POST /api/sales/invoices | ✅ INV-L4205332，AR 生成 |
| 开票额度（红冲返还后） | POST /api/sales/invoices | ✅ 红冲后额度自动返还，未超开 |
| 红冲 | POST /api/sales/invoices (red_of_invoice_id) | ✅ 红字票 + 红字应收（-5000） |
| 反例：重复红冲 | 同端点 | ✅ **拦截** 400「原发票已红冲，不能重复红冲」 |
| 反例：已红冲蓝字票删除 | DELETE /api/sales/invoices/{id} | ✅ **拦截** 400「需先删除对应红字发票」 |
| 反例：红字应收退超 | POST /api/sales/collections（退款 6000>可退5000） | ✅ **拦截** 400「退款金额超过可退余额」 |
| 正常退款 | POST /api/sales/collections（退款 3000） | ✅ 红字应收核销 |
| 收款核销（超额收款封顶） | POST /api/sales/collections（收6000/余额5000） | ✅ 按余额核销，不超收 |
| 核销转移 | POST /api/sales/ar/transfer | ✅ 业务校验（源/目标必填、源须红字） |
| 负数申报 | POST /api/tax-refund/declarations + return-candidates + submit | ✅ 申报创建/提交，候选列表可用 |

**反例结论：L4 清单第 2 条（5 个反例）全部按预期拦截，无放行。**

---

## 3. 角色/权限探索（L4 清单：admin、角色、提醒规则、币种）

| 项 | 结果 |
|---|---|
| 管理员 | 全权限 ✅ |
| 创建 库管员/只读 用户 + 登录 | ✅（/api/auth/users, role 6/7） |
| 只读用户（权限仅 menu:dashboard）UI 侧 | ✅ 菜单只有「工作台」；直接访问 /sales/orders 被前端路由守卫弹回 dashboard |
| 提醒规则列表（10 条，含事件/账期） | ✅ 200 |
| 币种列表（7 种）+ 删除未引用币种 | ✅ 200 |

---

## 4. 缺陷清单

### BUG-L4-01 【Critical】只读角色/库管员可通过 API 创建、修改、删除销售订单（后端权限校验缺失）

- **位置**：后端 `app/routers/sales.py` — `create_sales_order`(110)、`update_sales_order`(365)、`delete_sales_order`(337) 等**全部业务端点**仅依赖 `get_current_user`，仅 `approve`(449) 使用 `require_permission("menu:sales:orders")`；`foundation.py`/`inventory.py` 同样仅 `get_current_user`。
- **复现步骤**：
  1. admin 登录 → 创建「只读」角色用户 l4ro5625（权限仅 `menu:dashboard`）；
  2. 以 l4ro5625 登录，`GET /api/auth/me/permissions` → `["menu:dashboard"]`；
  3. `POST /api/sales/orders`（建单）→ **200** SO-26082810；
  4. `PUT /api/sales/orders/{id}`（改单）→ **200**「销售订单已更新」；
  5. `DELETE /api/sales/orders/{id}`（删单）→ **200**「销售订单已删除」；
  6. 对比：`POST /api/sales/orders/{id}/approve` → **403**「缺少权限: menu:sales:orders」（唯一有权限保护的端点）。
- **实际输出**：只读用户建/改/删全部 200；库管员（role 6）读供应商/产品/材料/销售订单均 200。
- **预期输出**：无 `menu:sales:orders` 权限的角色应 403。
- **影响**：任何已登录的低权限用户（只读、库管员）可通过 API 直接增删改业务单据；前端路由守卫只能挡菜单点击，挡不住接口调用。违反 RBAC 设计（BUG-03 同根因，且范围更大——不止基础档案，销售订单也全开放）。
- **环境**：macOS 26.5.2 / FastAPI / SQLite；复现日志 explore_phase9.json、explore_phase12.json、explore_phase11.json
- **来源层**：L4（自动化 test_rbac/test_boundary 仅断言了 wecom/采购审核等少数端点的 403，未覆盖 sales CRUD）
- **截图**：shots_role/只读_sales_orders.png、只读_dashboard.png、库管员_dashboard.png

### BUG-L4-02 【Major】库管员可读基础档案与销售数据（BUG-03 现场确认，且影响面大于登记描述）

- **位置**：`app/routers/foundation.py`、`app/routers/inventory.py`、`app/routers/sales.py`（全部 `get_current_user`，无 `require_permission`）
- **复现步骤**：以库管员（l4wh5624，权限=库存域）登录后 `GET /api/foundation/suppliers|products|materials`、`GET /api/sales/orders` 均 200 返回全量数据。
- **实际**：200（供应商/产品/材料/销售订单全部可见）。
- **预期**：403 或按角色裁剪。
- **影响**：与 docs/complete-test-plan.md 第九节 BUG-03 一致，本次确认为现场可复现，且新增「销售订单数据也全量可读」。
- **来源层**：L4。

### 观察项（非缺陷，按设计；含探针纠正）
- **探针纠正**：`GET /api/sales/deliveries/outs` 返回行含 `id`（=发货单 id，前端 `row.id` 精确定位），无字段缺失。初判的 BUG-L4-03 不成立，撤回。
- 发货完成确认后该产品行不能再发货（UI 有明确提示，剩余库存开放给其他订单）——符合设计。
- 锁定语义：出库 50 后批次剩余 50 locked=0 available=50，锁定随出库释放——正确。
- 负数申报 return-candidates 当前空列表（无退货数据）——符合现状，BUG-04 已知待办不在本次范围。

---

## 5. 回归与测试最终状态

- ./test.sh：**242 passed, 0 skipped**（日志：242 passed, 7 warnings in 5.53s）
- e2e：**59 passed, 0 skipped**（188s）
- 本次探索未修改任何业务代码，未提交任何测试（遵守禁碰项）。

## 6. 结论与建议

**结论：探索完成。核心业务路径 + 5 个反例全部按预期拦截；发现 1 个 Critical（低权限 API 越权 CRUD）、1 个 Major（BUG-03 现场确认+扩展）。**

建议：
1. BUG-L4-01/BUG-L4-02：给 sales/foundation/inventory 关键端点统一加 `require_permission`（与 approve 对齐），并补 test_rbac 的 sales CRUD 越权断言；
2. 修复后跑 ./test.sh + e2e 全量回归。
