# 以 SP 为基底的 AO 功能移植方案（详细版·修订）

> 状态：方案稿（待确认）
> 基底：`sp-porting`（= origin/Sales_Purchase @ 995a95c）
> 来源：AO（origin/app-optimization @ b2994a4，20 提交独有）
> 原则：
> 1. **UI/交互以 SP 为基准**（业务逻辑/操作方式完全以 SP 为准）；仅两处例外：登录背景用 AO 的（集装箱船图）、登录后左侧菜单图标用 AO 的
> 2. **代码规范/统一/健壮性不以 AO 为参照**——直接在 SP 上做独立健壮性审计与修复（SP 已自带操作列 link 统一等规范，实证无需移植）
> 3. 只移植 AO 的高价值**业务功能**；不 cherry-pick，按 SP 现状适配重写

---

## 〇、SP 已自带（无需移植）

- 操作列 link 纯文字统一（SP 已 20+ 处，实证）
- 发货层退货/红冲（红字发货单/库管出库红冲/客户退货）
- 退税申报基础版（declarations/rows/customs-for-refund）
- 转直采/转委外/原料入库/库存主从/精度 6 位 等 SP 独有

## 一、SP 独立健壮性审计（替代 AO 规范移植）

在 SP 上直接做一轮系统审计并修复（复用 erp-robustness-audit 方法论）：
1. 状态机一致性：销售/采购/生产/库存各状态流转是否可撤销、回退一致
2. 删除保护：有下游引用的单据删除是否拦截（SP 已有部分，补齐）
3. 数量/金额校验：全 ERP 数量>0、金额>0、类型转换（前端字符串 vs 后端 float）
4. 前端传参正确性：API 第二参数误传 id 当 body（AO 踩过 3 次的坑，SP 逐一排查）
5. 错误提示：catch 是否吞掉后端 detail（SP 排查）
6. 列表删除/变更后刷新实时性
7. 迁移/启动健壮性：外键引用（SP 已发现 mo_outsourcing 崩）、依赖完整

产出：SP 健壮性问题清单 + 修复（每项独立验证）

## 二、AO 高价值功能移植清单（按序）

### 批 1：低风险独立项
| # | 功能 | 来源 | 动作 |
|---|---|---|---|
| 1.1 | 登录背景换 AO 集装箱船图 | AO 4d96261 | 拷贝 login-bg.jpg + Login.vue 背景样式（SP 布局不动） |
| 1.2 | 左侧菜单图标用 AO | — | diff 两边菜单定义，替换图标配置 |
| 1.3 | AI 调用直连兜底 | AO b2994a4 | ai_chat.py 同步（10 行 diff，后端独立逻辑） |
| 1.4 | AI 密钥防双重加密 | AO b0bcd43 | crypto.py is_ciphertext + system_config + 2 前端 + 测试 |
| 1.5 | SP 健壮性审计（上文） | 独立 | 全仓审计 + 修复 |

### 批 2：销售退货财务层补强（核心）
- 模型：`so_invoice.is_red/red_of_invoice_id/status(已红冲)`、`ar_account.is_red/red_of_ar_id`、`so_delivery.refund_declared`、`ArAdjustment` 表 + 迁移脚本
- 路由（sales.py 只加不改 SP 独有分支）：
  - 发票：红字录入（全额负数）/ PUT·DELETE 保护 / 列表红冲字段
  - 退货端点（SP 1200 行 `deliveries/return`）：refund_declared 打标 + 已报关提示
  - 收款：负数退款分支（amount<0 核销红字应收、balance 向 0 靠拢、退超拦截）——**以 SP 现有收款流程（含 cancel-collection）为基底加分支**
  - 新增 `POST /ar/transfer` 核销转移（同客户、双向上限、写 ArAdjustment）
  - 新增 return-candidates / return-adjustments（负数申报，进 tax_refund.py）
- 前端 6 页：SalesInvoices（红冲/红冲票号列）、AccountsReceivable（红负绿正/退款/核销转移）、Collections（负数标红）、SalesDeliveries（退货提示）、Dashboard（红冲标记）、TaxRefundDeclarations（负数申报入口）——**页面布局/交互按 SP 现有样式实现**
- 测试：test_sales_return_red.py 按 SP 流程重写 6 场景

### 批 3：报关单明细化 + 退税双端/草稿
- 报关单：`so_customs_item` 子表 + hs_code_id 可空 + 5 端点商品行化 + 前端商品行表格/状态流转
- 退税：`tr_declaration_row.customs_item_id` + 双端去重校验 + FOB 重算 + `PUT /declarations/{id}` 表头更新 + 草稿模式前端 + 免抵退实时预览
- 测试：test_customs_items.py 适配 SP

### 批 4：预警提醒系统 v2.7.0
- 后端整体移植 AO 独有 3 文件：routers/notification.py、schemas/notification.py、services/reminder.py + 4 事件埋点
- 前端：system/Notifications.vue + 消息铃铛（按 SP 布局集成）
- SP reset 脚本 KEEP 已预留 sys_reminder_* 表名 ✓
- 测试：新写

### 已从清单移除（按你的原则）
- ❌ 操作列 link 统一（SP 已有）
- ❌ script 内 $fm 修复、错误提示 detail、删除本地移除（AO 特有页面 bug，SP 走独立审计）
- ❌ 应收/应付明细重构（交互，以 SP 为准）；仅保留其中的"审核锁定"业务规则（并入批 2 收款流程）
- ❌ 人肉测试修复 6 项（AO 特有代码路径）

## 三、依赖关系

```
批 1（独立）→ 批 2（依赖批 1 审计基线）→ 批 3（依赖批 2 的 refund_declared）
→ 批 4（独立，可与 2/3 并行）
```

每批完成标准：SP 全量测试绿 + vite build 过 + 对应功能 API 验证

## 四、风险清单

1. SP sales.py 2227 行（AO 1789）——财务逻辑只加不改 SP 转直采/转委外分支
2. SP 无自动生成 MO——退货/退税测试数据流重写
3. SP 收款有 cancel-collection——负数退款与之交互
4. 精度：SP 6 位精度/2 位显示，断言 round
5. 审计修复要小步增量（不违反 SP 主线逻辑）

## 五、待确认

1. 批 1.5 健壮性审计范围是否认可（7 项检查）？
2. 批 2 现在开始（工作量最大）还是先批 1？
3. 应收应付的"审核锁定"并入批 2 是否 OK？
