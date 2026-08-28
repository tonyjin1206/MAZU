# MAZU 外贸 ERP 完整测试方案设计（v3.0）

> 目标：**让"脚本测过了"≈"真实浏览器用没问题"**。针对本仓库已实证的盲区——前端脚本测不到交互层、真实浏览器常出 bug——本方案按**分级补位**设计，每一层抓一类问题，层级间不互相替代。
> 基底：`main`（SP 产品逻辑，销售订单下游走转直采/转委外，无生产订单模块）。覆盖批1-4 全部功能。
> 维护：本档为**设计+覆盖矩阵**权威文档；`docs/test-plan.md` 保留为按批次同步的索引，`docs/test-report-1.md` 为历史报告。

---

## 一、设计原则（本方案的灵魂）

### 1.1 核心信条：测"行为"，不测"存在"
- **反例**：断言"`<el-dialog>` 存在 / 接口返回 200 / 页面打开" → 按钮点了确认框不弹（`ReferenceError`），脚本照样判过。
- **正例**：点击 → 断言**确认框真的出现**、`$fm(value)` 渲染为 `¥1,234.57`、按钮**显隐符合状态机**、**0 console error / 0 pageerror、0 网络 4xx-5xx** 才判过。

### 1.2 分级补位：每一层只负责一类问题
| 层 | 抓什么 | 为什么这层必须有 |
|---|---|---|
| L0 静态/静态检查 | 编译、lint、架构违规、前后端 API 路径契约 | 最便宜，先挡"接口对不上/编译不过" |
| L1 后端单元/业务 | 金额/状态机/边界/删除保护/权限 | 后端规则的可验证单元，快、稳 |
| L2 前端交互级 | **行为 + console 错误 + 传参语义** | 抓 `$fm`/确认框/吞错/传参——**纯后端测不到** |
| L3 E2E 全链路 | 真实浏览器走一条完整业务 | 跨模块串起来的集成正确性 |
| L4 真人探索 | `computer_use` 驱动真实浏览器做**不可预测操作序列** | 脚本想不到的组合（反退/改完再点/双击/切页签）兜底 |

### 1.3 稳定化三条铁规（治 flaky）
1. **每测独立数据**：E2E 用隔离库 + 唯一单号/批次（杜绝"单跑过、全量挂"）。
2. **teleport 感知选择器**：对 `el-select`/`el-dialog`/`el-popover` 用浮层定位，按**元素状态**等待（如"弹窗可见""按钮可点"），不用固定 sleep。
3. **前后端分离契约 + 参数语义校验**：不只比对 path，还要校验**第二参数是 params/body/id**、响应结构符合 schema。

---

## 二、现状盘点（设计输入）

| 项 | 现状 |
|---|---|
| 后端测试 | `backend/tests/` 13 文件；全量跑 **113 passed / 122 skipped**（那批 skip 是引用旧「审核→自动生成 MO」流程的过时用例）|
| E2E | `e2e/` 5 文件（conftest/core_flow/matsu_assistant/rbac_menu/smoke_pages）——**全是 AO 时代**，断言旧流程 |
| 已接入专项 | 批2 红冲财务：`test_sales_return_red.py`；批4 提醒：`test_reminders.py` |
| 基建 | `test.sh` 已改**隔离测试库**（`mktemp` 新库）；`conftest.setup_db` 复用生产种子（rbac/币种/参数/提醒规则）|
| 已知缺陷类（memory 实证）| `$fm`/`$hasPermission` 仅模板可用，script setup 调用 → ReferenceError → 确认框不弹/按钮无反应；`api.get(id,id)` 把 id 当 body → 422；`catch {` 吞 detail → 报错无提示；`el-switch` 需 active-value=1/0；`func.now()` UTC 前端按本地比；删除后列表不刷新 |

---

## 三、覆盖矩阵（模块 × 层 × 用例文件 × 状态）

状态图例：✅已覆盖｜🟡待补｜♻️需按 SP 流程重写｜🗒️废弃（旧流程不存在）

### 基础档案（foundation）
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| 客户/供应商/物料/产品/BOM/工序/HS/仓库/币种/汇率 CRUD+校验 | ✅ | 🟡 | `test_foundation.py` | ✅ |
| 搜索/分页/唯一性/外键删除保护 | ✅ | 🟡 | `test_foundation.py` + 边界 | 🟡 |

### 采购（purchase）
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| 采购需求 PR（转单/关闭/联动 MO 回退） | 🟡 | 🟡 | `test_purchase.py`（待建）| 🟡 |
| 采购订单（审核/入库/开票/付款/状态动态计算） | ✅ | 🟡 | `test_state_machine.py`/`test_textile_flow.py` | ♻️ |
| 采购入库（批次/取消/红冲） | ✅ | 🟡 | `test_inventory_v2.py` | ✅ |
| 应付 AP（账龄/到期） | ✅ | 🟡 | `test_reminders.py`(账期) | 🟡 |

### 销售（sales）
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| SO 审核 → 明细行转直采/转外发（**SP 流程，无自动 MO**）| ♻️ | ♻️ | `test_textile_flow.py`（重写）| ♻️ |
| 两段式发货：通知发货→库管出库→发货完成 | ♻️ | ♻️ | `test_textile_flow.py`（重写）| ♻️ |
| 报关（商品行/状态流转 已报关→放行→结关）| 🟡 | 🟡 | `test_customs_items.py`（待建）| 🟡 |
| 发票/应收/收款 | ✅ | 🟡 | `test_textile_flow.py` | ♻️ |
| **批2 红冲/红字应收/退款/核销转移/退货联动/负数申报** | ✅ | 🟡 | `test_sales_return_red.py` | ✅ |
| SO 发货工作台/认领批次/重发 | 🟡 | 🟡 | `test_sales_workbench.py`（待建）| 🟡 |

### 生产/委外（production/outsource）
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| 委外订单（工序/发料/完工/收料/加工费 AP）| 🟡 | 🟡 | `test_outsource.py`（待建）| 🟡 |
| 工序卡片/自由删/恢复 | 🟡 | 🟡 | 待建 | 🟡 |
| 转委外（销售订单→委外）| ♻️ | ♻️ | `test_textile_flow.py`（重写）| ♻️ |

### 库存（inventory）
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| 收发存 v2（批次/流水/恒等式 期初+收-支=期末）| ✅ | 🟡 | `test_inventory_v2.py` | ✅ |
| 盘点（盘盈/盘亏/账外批次）| ✅ | 🟡 | `test_inventory_v2.py` | ✅ |
| 批次追溯/锁定/认领 | 🟡 | 🟡 | 待建 | 🟡 |
| 原料/成品入库出库 | 🟡 | 🟡 | 待建 | 🟡 |

### 退税（tax-refund）
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| 申报/明细行/状态流转/免抵退计算 | 🟡 | 🟡 | `test_refund.py`（待建）| 🟡 |
| 批2 负数申报（return-candidates/return-adjustments）| ✅ | 🟡 | `test_sales_return_red.py` | ✅ |

### 系统/提醒/AI
| 功能点 | L1 | L2 | 用例文件 | 状态 |
|---|---|---|---|---|
| RBAC（角色/权限/越权 403/管理员全权）| ✅ | 🟡 | `test_rbac.py` + `e2e/test_rbac_menu.py` | ✅ |
| **批4 提醒（事件埋点/规则/去重/账期扫描）** | ✅ | 🟡 | `test_reminders.py` | ✅ |
| AI 助手 Matsu（功能调用/权限/审计）| ✅ | 🟡 | `test_bot_agent.py` + `e2e/test_matsu_assistant.py` | ✅ |
| AI 密钥守卫（防双重加密/脱敏）| ✅ | — | `test_config_secret_guard.py` | ✅ |
| 站内通知（铃铛/管理端查询）| ✅ | 🟡 | `test_reminders.py` + `test_notifications.py`（待建）| 🟡 |

---

## 四、L2 前端交互级（本方案新增核心层——治"脚本测不出真实 bug"）

**目标**：把"确认框不弹/按钮无反应/参数传错/吞错"这类**纯前端运行时**问题，用断言抓出来。

### 4.1 断言集（每页核心交互）
- **0 console error / 0 pageerror**（监听 `console`/`pageerror`，出现即 fail）。
- **0 网络 4xx-5xx**（监听 `requestfailed`/`response` 状态码）。
- **行为断言**：
  - 点击"删除/确认/审核" → 断言 `ElMessageBox.confirm` 弹窗**真的出现**（不是只点按钮）。
  - 金额/数量列渲染值 = `$fm`/`$fq` 格式（`¥1,234.57`/数量 4 位小数），捕捉 `script setup` 里 `$fm` → ReferenceError 的静默坏。
  - 按钮显隐符合状态机（如：仅 `production_status=未生产` 显示"重发生产"；红字票隐藏删除按钮）。
  - 表单校验：必填/金额>0/数量>0/税率，error message 文案断言。

### 4.2 专项用例（把 memory 已实证的坑写成断言）
| 坑 | 断言 |
|---|---|
| `$fm`/`$hasPermission` 在 script setup | 打开含弹窗的页 → 触发一次弹窗 → **0 ReferenceError** |
| `api.xx(id, id)` 第二参数误传 | 对每 api.*.get/put 检查**第二参数语义**（契约层做）|
| `catch {` 吞 detail | 触发一个会被后端 4xx 的操作 → 前端**有错误提示文案**（非静默）|
| `el-switch` 数字态 | 开关值 = 1/0 且后端收到整数 |
| 删除后不刷新 | 删一条 → 列表**立即缩短/刷新** |
| 日期比较 | 用 `UTC naive` 惯例断言到期/逾期判断正确 |

### 4.3 稳定化 E2E 基建（代码侧）
- teleport 感知：`el-select` 下拉用弹出层 selector；等待"弹窗可见/按钮可点"状态。
- 每测独立数据：唯一单号/批次前缀（如 `T-{runid}-{seq}`），隔离测试库。
- 按 SP 流程重写 `e2e/`：删除"审核→生成生产订单"旧断言，替换为"转直采/转委外 + 通知发货→出库→发货完成"。

---

## 五、L4 真人探索层（`computer_use`——兜底不可预测操作）

脚本想不到的操作序列，由**真人驱动的浏览器探索**覆盖。每轮任务做一组探索清单：
- 建档→销售→转直采/转委外→采购→入库→发货两步化→开票→红冲→退款→核销转移→负数申报。
- **穿插反例**：审核后直接改单（应拦）、订单未审就发货（应拦）、已红冲蓝字票删除（应拦）、红字应收退超（应拦）、删除后刷新（应即时）。
- 记录：`vision_analyze` 截图 + console 错误 + 实际行为 vs 预期。

---

## 六、执行规范

### 6.1 测试入口与数据源
- 统一 `./test.sh`（已隔离测试库）；仅后端单测；`cd e2e && ERP_DEV=1 python -m pytest` 跑 E2E。
- 数据源单一：复用 `tests/test_data.py` 的 `build_foundation`，禁止测试自建档案。
- 种子：`conftest.setup_db` 复用生产 `_seed_rbac/_seed_currencies/_seed_params/seed_reminder_rules`。

### 6.2 缺陷分级（记录格式）
| 级别 | 定义 | 处理 |
|---|---|---|
| Critical | 登录/主流程/金额/删库等错误 | 立即停发 |
| Major | 功能不可用/明确错误 | 本批修复 |
| Minor | 文案/样式/体验 | 记录，批量处理 |

Bug 记录：复现步骤 / 实际输出 / 预期输出 / 环境（OS/版本）/ 来源层（L0-L4）。

### 6.3 CI
- 建议接入：backend-test job（flake8 + pytest 全量 + 架构检查）+ frontend-build（vite build）+ e2e（隔离库）。

---

## 七、落地路径（建议分阶段，每阶段独立可验证）
| 阶段 | 内容 | 验收 |
|---|---|---|
| P1 基建稳定化 | e2e 隔离库 + teleport 选择器 + 按 SP 重写 e2e；契约层升级（参数语义）| `./test.sh` 全绿 + e2e 重跑通过 |
| P2 L2 交互级 | 每核心页加"0 console error + 行为断言"专项 | 交互用例 0 错误 |
| P3 全量重设 | 把 122 skip 按 SP 流程重写/废弃；补采购/委外/报关/退税/通知专项 | 全量绿，skip 仅剩真废弃 |
| P4 L4 真人探索 | 每轮任务附探索清单 + 缺陷入库 | 探索发现 → 分级转修复 |

---

*本方案为设计+覆盖矩阵。落地时把 P1-P4 拆成 codex 原子任务（带验收标准），andy 跑 `./test.sh`/e2e 验证后合并。*
