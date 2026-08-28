# Changelog

## v2.7.0 (2026-08-27)

> 本版本为 **预警提醒系统**（SP 分支批4）。预警内容按当前产品逻辑**重校**：无「生产订单」模块（弃用），销售订单下游走转直采/转外发，故不设 MO_* 提醒点，改为销售/发货/应收真实链路。

### 批4：预警提醒系统（通知内核 · 事件埋点 · 规则配置化 · 定时账期预警 · 站内消息中心）

**模型（`scripts/migrate_batch4_reminders.py`，幂等）**

| 表 | 说明 |
|---|---|
| 新建 `sys_reminder_rule` | 预警提醒规则（code/name/trigger_type/title_template/content_template/target_roles/channel/schedule_cron/advance_days/dedup_hours）——**规则配置化 D8** |
| 新建 `sys_notification` | 站内通知（user_id/point_code/title/content/doc_type/doc_id/doc_no/dedup_key/read_status/is_active）——**落库即视为已发 D7** |

**后端**

- **`services/reminder.py`**：`notify()` 统一入口（查规则→渲染模板→解析收件人→去重→写通知）；`resolve_recipients`（按角色广播）；`render_template`（`{order_no}/{amount}/{due_date}` 占位符）；`run_scheduled_scan`（AR/AP 账期扫描）；`seed_reminder_rules`（10 条规则，幂等）
- **`routers/notification.py`**：`GET /api/notifications`（当前用户列表）、`unread-count`（未读红点）、`latest`（工作台/铃铛）、`PUT /{id}/read`（标记已读）、`PUT /read-all`（全部已读）、`GET /admin-query`（管理端全量查询，按用户/角色/提醒点/单据类型筛选）
- **`system_config`** 加提醒规则 CRUD（`GET/POST/PUT/DELETE /api/system/reminder-rules`，管理端）
- **事件埋点（sales.py 6 处，按当前产品逻辑重校）**

| 提醒点 | 触发 | 收件人 | 说明 |
|---|---|---|---|
| SO_APPROVED | 销售订单审核通过 | 销售经理 | 转直采/转委外+安排发货 |
| SO_TO_PURCHASE | 销售明细「转直采」 | 采购经理 | **替代原 MO_PLANNED** |
| SO_TO_OUTSOURCE | 销售明细「转外发」 | 生产/采购经理 | **替代原 MO_OUTSOURCED** |
| DELIVERY_NOTIFIED | 已通知发货（待出库） | 库管员 | 到「成品出库」出库 |
| DELIVERY_CONFIRMED | 明细行发货完成 | 销售经理 | 安排开票 |
| AR_CREATED | 应收生成 | 财务+销售 | **双收件人**（入账+催收）|

- **定时预警（main.py 后台任务：启动补扫一次 D4 + 每日 09:00 扫描）**

| 规则 | 条件 | 收件人 |
|---|---|---|
| AR_DUE_SOON | 应收 due_date∈[今+1,今+7] 且未收清 | 销售经理 |
| AR_OVERDUE | 应收 due_date<今天 且未收清 | 销售+财务 |
| AP_DUE_SOON | 应付 due_date∈[今+1,今+7] 且未付清 | 财务 |
| AP_OVERDUE | 应付 due_date<今天 且未付清 | 财务+采购 |

  - **红字应收（`is_red`）不参与账期提醒**；站内为主（企微为预留钩子，未启用）

**前端**

- **顶部铃铛（Layout.vue，所有登录用户）**：未读红点 + 消息弹层；点击标记已读并跳转关联单据；30s 轮询未读数
- **`system/Notifications.vue`（管理端，`menu:system:reminders` 权限）**：「通知查询」+「提醒规则」两页签；系统管理菜单新增「通知管理」
- **`api/business.js`**：`notificationApi`（list/unreadCount/latest/markRead/markAllRead/adminQuery）+ `reminderRuleApi`

**测试与基建**

- `backend/tests/test_reminders.py`：规则种子 / 事件埋点 / 去重 / 双收件人 / 定时扫描（含红字不参与）/ 通知 API，6 场景
- 全量测试 **113 passed**；`vite build` 通过
- **`test.sh` 隔离测试库**：每次全新临时库（不复用陈旧 `backend/data/erp.db`，避免 RBAC 迁移前旧 schema 导致登录失败）
- `reset_local_db.py` KEEP 补 `sys_reminder_rule` / `sys_notification`

## v2.6.0 (2026-08-27)

> 本版本为 **SP 为基底的 AO 功能移植 + 销售退货财务层补强**（SP 分支批次 1/2）。以下按批次记录。

### 批1：AO→SP 基底适配 + SP 健壮性审计

- **AO 高价值项移植**：登录背景换 AO 集装箱船图；登录后左侧菜单图标沿用 AO；AI 调用改**直连优先 + 代理兜底**（`all_proxy` 残留时 Clash 未开会 Connection refused 的坑）；AI API Key 防双重加密（`is_ciphertext` 判定 + system_config + 前端两处配置页）
- **SP 健壮性审计修复**：后端删除保护 + 数量/金额校验；前端错误提示透传后端 `detail`；前端传参正确性（API 第二参数误传 id 当 body 导致的 422）
- **SP 环境初始化修复**：`mo_outsourcing` 外键 `fd_outsourcer` 修正为 `fd_supplier`；初始化脚本与 SP 流程对齐；测试入口 `test.sh` 平台自适应
- **测试基线**：新增 `test_config_secret_guard.py`（密钥守卫）并接入现有套件

### 批2：销售退货财务层补强（发票红冲 · 红字应收 · 退款 · 核销转移 · 退货联动 · 负数申报）

**模型（迁移脚本 `scripts/migrate_batch2_finance.py`，幂等）**

| 表 | 新增字段 | 说明 |
|---|---|---|
| `so_invoice` | `is_red`(0/1)、`red_of_invoice_id`(FK→so_invoice.id, 可空) | 红字标记 + 原票引用；状态可取"已红冲" |
| `ar_account` | `is_red`(0/1)、`red_of_ar_id`(FK→ar_account.id, 可空) | 红字应收标记 + 原应收引用 |
| `so_delivery` | `refund_declared`(0/1, 默认0) | 已报税退货标记（负数申报用） |
| 新建 `ar_adjustment` | `source_ar_id`/`target_ar_id`/`amount`/`remark`/`operator`/`created_at` | 核销转移审计表（红字→正余额） |

**后端（`routers/sales.py`，只加不改 SP 现有分支）**

- **发票红冲（create_sales_invoice 支持 `red_of_invoice_id`）**
  - 蓝字开票上限校验：开票金额 ≤ 订单未开票金额（未开票 = 订单总额 − 已开票累计，红字全额冲后额度自动返还），超限 400"超过未开票金额"
  - 红字手工录入：票号手填，金额强制 = 原票**全额负数**（一次红冲，不允许手工干预金额）；原票标记"已红冲"
  - 红字票**禁改禁删**（PUT/DELETE 400）；已红冲蓝字票**禁删**
  - 自动生成**红字应收**（等额负数、`is_red=1`、`red_of_ar_id`=原应收）
- **收款 / 退款（create_collection 支持 `amount<0`）**
  - 负数 = **退款登记**：核销红字应收，负余额向 0 靠拢；退超拦截"超过可退余额"
  - 正常收款与 `cancel-collection`（按应收 id 撤销）保持 SP 现状不变
- **核销转移（新增 `POST /ar/transfer` + `POST /ar/transfer/{adj_id}/cancel`）**
  - 红字应收（负余额）→ 同客户正余额应收的账务清理，无收款单参与；写 `ar_adjustment` 留痕
  - 校验：同客户、源必须红字且负余额、目标余额必须为正、± 上限 = min(源负余额, 目标正余额)；撤销回滚两端账务
- **退货联动（销售退货端点自动检查）**
  - 关联报关单退税状态已申报/审核中/通过/已退税 → 退货单打标 `refund_declared=1` 并提示"次月申报自动带出负数申报"；待申报 → 提示同步更新申报明细
  - 已开票订单退货 → 提示"已开票需同步红冲发票"

**前端（5 页 + `api/business.js`，UI 以 SP 为准）**

| 页面 | 改动 |
|---|---|
| `SalesInvoices.vue` | 已开票蓝字行"红冲"按钮；红冲票号列；红字票删除按钮隐藏；状态列 待开票=info / 已开票=success / 已红冲=warning / 已作废=danger |
| `AccountsReceivable.vue` | 余额**红负绿正**（<0 红 / >0 绿）；红字应收行显示"退款""核销转移"按钮；退款弹窗（生成负数收款单）、核销转移弹窗（选同客户正余额应收） |
| `Collections.vue` | 负数金额标红 + "退款" tag |
| `SalesDeliveries.vue` | 退货弹窗加"已开票需同步红冲发票"提示 |
| `TaxRefundDeclarations.vue` | "＋添加退货冲减（负数申报）"入口 + 已报税退货选择弹窗 |

**负数申报（`routers/tax_refund.py`）**

- `GET /declarations/{id}/return-candidates`：已报税退货（`refund_declared=1` 且关联报关单）中未在本表添加过的清单
- `POST /declarations/{id}/return-adjustments`：添加"出口货物退运"负数明细行（`voucher_type=出口货物退运`、`voucher_no=退货单号`），自动重算申报表 `export_amount_fob` 与免抵退结果；同一退货单重复添加拦截 400

**测试**：`backend/tests/test_sales_return_red.py`（红字链路 / 蓝字上限 / 退款 / 核销转移+审计，6 场景）；全量回归保持绿。

## v2.5.0 (2026-07-31)

### 备货方式确认 + 外购直采（生产订单 `production_type`）
- **生产订单必须先确认备货方式**（自产/委外/外购）：MO 审核后状态=`待确认`，列表/详情页「确认备货方式」选择；未确认前 BOM 展开/排产/推采购全部禁止；自产/委外=`待排产`进工作台，**外购=`待采购`不进入工作台**，仅「推采购需求」
- **采购需求单** `po_requisition`（PR-YYYYMMDD-NNN，v2.5.0 新增）：来源 MO + 产品 + 数量，状态 待处理/已转单/已关闭
- **生产侧**：外购型 MO「推采购需求」只填数量+备注（不填供应商/单价/税率——生产人员不掌握采购价格）
- **采购侧**：新增「采购需求」菜单页 → 待处理列表 →「生成采购订单」填供应商/单价/税率/交期（数量预填可改）→ 自动生成 PO 带 `requisition_id` 来源标记
- **状态机**：MO(外购/待采购) → 推需求 → PR(待处理) → 采购转单 → PO(待审核) → 入库完成 → MO(已入库)；PR 待处理可关闭 → MO 回待采购可重新推；删除 PO → PR 回待处理、MO 回待采购
- **产品列锁定**：从 PR 转出的 PO 明细产品编码锁定不可改（只改金额数量）
- **采购订单支持成品采购**：`po_order_item.product_id`（与 material_id 互斥）+ 产品「是否可外购」标记（`Product.can_purchase`，MO 确认外购自动打勾）+ 选品下拉合并原材料与可外购成品（`/foundation/procurement-items-select`）；采购入库成品写成品库存并回写最新成本
- **委外商简化**：删除 `fd_outsourcer` 表及 Outsourcer 模型/接口——**供应商类型=委外 即委外商**（选择器直接查供应商）；工序/工艺模板 `outsourcer_id` 改指 `fd_supplier.id`；移除 POST/DELETE /outsourcers
- **金额修复**：推式/转单生成 PO 头部金额完整（含税/不含税/税额，此前缺失为 0）；PO 详情打开从明细行重新汇总

### 汇率自动获取与维护
- **币种/汇率独立菜单**：基础档案 → 币种/汇率（币种档案管理 + 汇率维护）
- **汇率自动获取（国内源）**：腾讯财经 `qt.gtimg.cn`（无 key、国内可达），手动按钮或**每日 09:00 定时任务**拉取全部非本位币种兑本位币汇率入库（`source=API`）；同币种+同日 upsert；JPY/KRW 腾讯无交叉盘 → 失败列表提示，手动维护兜底
- **汇率手工维护**：选币种 → 填兑本位币汇率 → 生效日期；同币种+同日查重；列表显示「1 USD = 7.10 CNY」语义；编辑/删除
- **汇率列表币种名称修复**：`ExchangeRateOut` 从 relationship 填充 `currency_code`（此前 register_crud 返回 null 导致前端币种列空白）
- **接口**：`GET /exchange-rates/latest`（业务单据换算用）、`POST /exchange-rates/fetch`（手动触发拉取）

### 本地 bug 收尾
- **仓库档案编辑 422**：`register_crud` 无 update_schema 时 PUT body 用 `dict = Body(...)` 兜底（一处修复覆盖 Warehouse/Department/Employee/Currency/TradeTerm 五实体）+ 回归测试
- **出入库仓库参照校验**：采购入库/完工入库/销售出库/盘点建单校验 `warehouse_id` 必须存在于仓库档案且启用（否则 400）—— 前端选择器与后端校验闭环
- **权限种子修复**：`_seed_rbac` admin 补权限前 `db.flush()`（SessionLocal `autoflush=False` 导致每次启动 admin 权限翻倍的 bug）+ 角色关联去重（production 前缀与 inventory 硬编码重叠）
- **管理员永远全权限**：`User.has_permission` 对 admin 角色恒真 + `permission_codes` 动态查全表（不依赖快照，新增权限码无需手动授权）；`_seed_rbac` 每次启动自动补齐 admin 权限关联；`scripts/migrate_role_permissions.py` 幂等修复其他角色快照过期（生产经理补完工入库/采购经理补采购需求）
- **测试权限断言动态化**：admin 权限数 = 全量码数动态对比，不再硬编码（加权限码不再连锁改断言）

### 盘点管理独立菜单 + 明细增强
- 盘点管理独立权限码 `menu:inventory:stocktake` + 独立页面（不再做页签）
- 盘点明细可新增/编辑/删除物料行（含**账外批次**：提交时自动创建台账行，成本用录入值）；同批次重复录入 400；已提交不可改/删
- 仓库档案前端维护界面（Warehouses.vue + `menu:warehouses` 权限闭环）

### 测试数据基建 v2（重构）
- **统一构建器**：`tests/test_data.py` 的 `build_foundation()` 通过 API 创建全套真实档案（2仓/2供应商/2客户/4物料/2产品/4工序 + BOM/工艺路线），共享 fixture `foundation`（session 级）；**禁止各测试文件自建档案**（消除 RM990001/WH-BND/WH-BOT 等垃圾数据）
- **权限种子单一数据源**：conftest 复用 `app/main.py` 的 `_seed_rbac`（删除双份定义，杜绝漂移）
- **textile 全流程 v4**：3 订单 → **1 订单**（单客户×单产品走完全流程 + 盘点/红冲/退货/拆类型/成本自动结转/仓库参照校验）
- **状态机矩阵文档池**：按 (单据, 动作) 复用文档，`_set_status` 重置状态 —— 单据量 112 → ~16，覆盖度不变
- **数据量**：跑完全量测试库内单据 97 → 22（-78%）；仓库档案全部字段完整（含 address/manager）
- **README 测试数据规范**：新测试必须复用/扩展统一构建器，禁止另建档案

## v2.4.0 (2026-07-31)

### 库存收发存 v2（重构）
- **盘点闭环**：盘点单（草稿/已提交）→ 自动带出仓库批次账面数 → 录实盘 → 提交按差异生成盘盈/盘亏流水（`stocktake_in`/`stocktake_out`）并更新台账；盘亏不可超账面；提交后不可改/删
- **采购红冲**：批次已被消耗时生成负向红冲单（`is_red`/`red_of_receipt_id`）+ 冲销流水（`purchase_return_out`）；红冲量 ≤ 批次当前剩余；回退订单 `received_qty`/状态 + 外购型 MO 状态；支持多次部分红冲
- **销售退货**：负向退货单（`is_return`/`return_of_delivery_id`）+ 回库流水（`sale_return_in`）；退回原批次、原发货成本，批次已清空则重建；回退订单 `delivered_qty`/状态；驾驶舱毛利自动冲减
- **发料类型拆分**：自产工序发料=`material_issue_out`，委外工序发料=`outsource_out`（原统一 `outsource_out`）；成本汇总/报表/前端标签同步；历史流水由 `scripts/migrate_inventory_v2.py` 迁移拆分
- **取消入库保护**：取消完工入库仅限批次无任何其他出入库（发货/盘点/退货等 → 禁止，走退货）；采购取消入库补冲销流水保留审计
- **完工入库成本自动结转**：留空 = 按「剩余投入 × 本次入库占比」自动结转（最后一次全转），可手改覆盖
- **收发存报表修复**：多批次合并时批次号按时间取最新；新流水类型（红冲/退货/盘点）自动纳入期初+收发+期末口径
- **迁移脚本**：`scripts/migrate_inventory_v2.py`（幂等：po_receipt/so_delivery 加列 + 历史发料流水拆分）

## v2.3.0 (2026-07-31)

### AI 助手全系统化（Matsu）
- **入口改造**：菜单页 → 全局右下角悬浮球（M 图标），任意业务页面随时对话
- **操作能力**：查档案/查库存/建单（采购/销售）/审核/收付款/发票/发料/完工入库等，自然语言操作
- **权限联动**：工具执行受菜单权限控制（无权限操作后端拒绝）；操作全程留痕（审计）
- **操作手册检索**：AI 助手可检索 `docs/operations-manual.md` 回答操作问题

### 菜单级权限前端落地
- Layout 菜单按权限过滤（32 菜单项 + 7 分组）+ 路由守卫 `meta.perm` 校验（直链访问无权限页 → 重定向工作台）
- 权限清单与真实菜单对齐：补 6 个缺失权限码（采购需求/完工入库/AI助手/AI配置/企业微信/提醒）+ 角色关联迁移（幂等）
- 用户/角色/权限管理接口仅管理员（后端 `require_permission`）

## v2.1.0 (2026-07-30)

### AI 多明细行一次创建（新增）
- `create_order` 工具参数从单行字段升级为 `items[]` 数组：一句话创建含多种物料/产品的订单（如「采购PCB板100片15块+电阻200个2块+外壳80个5块」）
- AI 逐项确认物料/产品存在性后一次性建单

### 基础档案页面重构
- 客户/供应商/物料/产品等档案页面布局重构（查询区/表格/分页统一风格）

### 文档
- README/操作手册/one-pager 更新至 v2.1.0（AI 多明细行新增版）

## v2.0.1 (2026-07-30)

### AI 助手修复与增强
- **查询字段扩展**：客户/供应商/物料/产品支持多字段模糊搜索（名称/编码/联系人等）
- **tool_calls 格式修正**：历史截断防止孤立 tool 消息（tool_calls↔tool 配对保留）；DeepSeek 兼容
- **改名 Matsu**：AI 助手由「MTS Bot」更名为 **Matsu**，蓝色渐变 M 字母 logo，欢迎语同步更新
- 初始化脚本重写（launcher/启动流程整理）

### 文档
- PROJECT.md 全面扩充至 12 章

## v2.0.0 (2026-07-29)

### AI 智能助手（全新）— Function Calling Agent
- **引擎重构**：由「意图识别+状态机+关键词规则」升级为 OpenAI 标准 **Function Calling Agent**（`tools` / `tool_choice: auto`）
- **9 个业务工具**：查档案（客户/供应商/物料/产品/应收/应付/发票）、建单（采购/销售）、收款、付款、发票录入、生产发料、完工入库、委外
- **三步确认流程**：AI 问清意图 → 逐字段收集（一次一个）→ 列表核对后执行；任何一步可「取消」
- **API Key 安全**：Fernet 加密入库、接口返回脱敏、运行期单独解密（修复重复解密）
- **前端配置页**：provider/模型/提示词可配置，提示词读 DB 实时生效（不再硬编码）
- Markdown 表格渲染（查询结果表格化）、欢迎语示例引导
- 设计约束：生产订单不支持 AI 手工创建（只能从销售订单流转）

### 提醒系统（框架）
- 5 种定时推送设计：日待办/应收应付到期/逾期/周报/老板日报（配置表 + 推送日志表）

## v2.2.0 (2026-07-31)

### 权限收紧
- 用户/角色/权限接口仅管理员可访问（GET /users、/roles、/permissions 等 403 拦截）
- 采购入库 BUG#1 修复：`po_receipt_item` 支持成品采购（`product_id` 列，`material_id` 改可空）
- 未审核采购订单禁止入库（状态校验）

## v1.2.0 (2026-07-29)

### RBAC 用户权限体系（新增）
- **新增 3 张数据库表**：`sys_role`（角色）、`sys_permission`（权限定义）、`sys_role_permission`（角色-权限关联）
- **User 模型升级**：新增 `role_id` 外键关联角色，替代原先的 `role` 字符串字段
- **预置 4 个角色**：管理员（全部权限）、经理（所有业务含审批）、操作员（读写无审批）、只读（仅查看）
- **预置 16 个权限码**：覆盖 8 个业务模块，每模块 `read/write/approve` 三级粒度
- **自动种子数据**：首次启动自动插入权限和角色，已有 admin 用户自动关联管理员角色

### 后端 API（新增）
- `GET /api/auth/permissions` — 按模块分组的权限列表
- `GET/POST /api/auth/roles` — 角色列表 / 新建
- `PUT/DELETE /api/auth/roles/{id}` — 编辑 / 删除角色（内置角色不可删）
- `PUT /api/auth/users/{id}` — 设置用户角色（支持密码修改）
- `DELETE /api/auth/users/{id}` — 删除用户
- `GET /api/auth/me/permissions` — 当前用户有效权限
- `require_permission(code)` — FastAPI 依赖工厂，声明式权限检查

### 前端新增
- **用户管理页** `/system/users`：用户 CRUD + 角色分配下拉框 + 启停用
- **角色管理页** `/system/roles`：角色 CRUD + 按模块分组权限勾选
- **全局权限方法** `$hasPermission(code)` — 菜单/按钮级权限控制
- **登录流程增强**：登录后自动拉取用户权限列表存入 localStorage
- **系统管理菜单**：侧边栏新增「系统管理」菜单组
- 401 拦截 / 退出登录自动清除权限缓存

### 代码质量
- 修复 `main.py` 重复初始化代码（移除冗余的 `@app.on_event("startup")`）
- 修复退出登录未清除权限缓存的遗漏

## v1.1.0 (2026-07-27)

### 功能新增
- **采购发票类型**：新增 `invoice_type` 字段（增值税专用发票/海关进口缴款书/农产品收购发票/普通发票/免税发票），仅可抵扣类型自动生成进项发票
- **产品+HS编码合并**：创建产品时可直接输入 HS 编码，自动创建/关联 `HsCode` 记录，无需独立维护 HS 编码管理页面
- **HS编码支持逻辑废弃**：`HsCode.hs_disabled` 字段用于标记作废的 HS 编码，不影响历史数据
- **报关单创建**：测试流程中接入海关报关环节（18位标准报关单号格式）
- **退税申报明细行**：改用新端点 `POST /declarations/{id}/rows`（标准税务格式），支持多行申报明细

### 改进优化
- **基础档案数据规范化**：公司名称使用全称（含 "有限公司"），联系人使用真实姓名，税号使用 18 位统一社会信用代码，电话号码带区号，供应商/客户地址完整
- **测试数据真实化**：纺织行业真实 HS 编码（52094200/52104100/52093100）、产品规格描述、宁波/广州/上海等真实贸易港口地址
- **委外商创建校验**：后端验证供应商类型必须为 "委外"，否则返回 400 提示
- **统一列表行高**：供应商管理表格添加 `size="small"`，与客户管理等页面统一
- **表单项间距调整**：从 10px → 22px，确保验证提示文字完整显示
- **弹窗宽度统一**：应收/应付明细弹窗调整为 970px，编码列收窄至 120px
- **缓存优化**：后端 `pool_pre_ping=True` + `Cache-Control: no-cache` 中间件 + 前端 axios `no-cache` 请求头，确保每次打开页面都是最新数据

### Bug 修复
- 供应商编辑弹窗税号字段不自动带入
- 工作台现金收支弹窗不立即显示明细（需点页签刷新才显示）
- 工作台应收/应付钻取弹窗 `page_size` 超限导致返回 0 条数据
- 生产订单详情页标题显示 "MTS" 而非 "生产订单详情"
- `ar_account_ids` 参数名错误（复数→单数）导致收款单无法核销应收账款
