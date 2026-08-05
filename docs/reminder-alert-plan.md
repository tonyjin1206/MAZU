# 预警提醒方案（reminder-alert-plan）

> 状态：步骤 1-2（通知内核 + 4 个事件埋点 + 规则配置页）已实施完成（2026-08-05）；步骤 3-4 待实施
> 范围：上游→下游业务联动提醒 + 应收/应付账期预警
> 原则：小步增量，每步独立可验证随时可停；细节实施时研判

## 一、需求

**两类需求，两种机制：**

| 需求 | 机制 | 举例 |
|------|------|------|
| 1. 上下游联动提醒 | **事件驱动**（业务操作发生时即刻触发） | SO审核→提醒生产排产；排产备料→提醒采购备货；转外购→通知采购下单；应收生成→通知销售催收+财务入账 |
| 2. 账期预警 | **定时扫描**（每日定时扫描到期数据） | 应收/应付快到账期提醒、逾期告警 |

## 二、现状盘点

**已有（壳）：**
- `ReminderConfig`（sys_reminder_config）：用户×提醒类型开关（daily_todo/expiry/overdue/weekly/boss_report）
- `ReminderLog`（sys_reminder_log）：推送日志（success/fail）
- `WecomConfig`（sys_wecom_config）：企微配置 CRUD（corp_id/agent_id/secret）
- 前端 `Reminders.vue`：预警提醒设置页
- 权限 `menu:system:reminders`
- AR/AP 均有 `due_date`；客户/供应商有 `account_period`+`payment_terms`（账期预警数据齐）

**缺失（肉）：**
- ❌ 无任何定时调度（无 APScheduler/cron）
- ❌ 无业务事件触发点
- ❌ 无站内通知（无铃铛/工作台待办/通知表）
- ❌ 企微仅有配置壳，无 gettoken/message send 代码
- ❌ sys_user 无 wecom_userid 字段

## 三、已确认决策（2026-08-05）

| # | 决策 |
|---|------|
| D1 | 接收人路由：**先按岗位（角色）广播**；未来单据加业务员字段后改为"归属人优先，无则按角色兜底"（只改接收人解析函数，调用方不变） |
| D2 | 应收生成提醒：**通知销售员催收 + 通知财务入账**（两件事、两类收件人；收款操作权限在财务） |
| D3 | 排产备料提醒：**只做通知**（带单据跳转），缺料清单由采购自己核算，系统不算 |
| D4 | 定时预警：**启动时补扫一次**，弥补应用未运行期间错过的预警 |
| D5 | 去重：**同单据+同提醒点 1 小时内只推一次** |
| D6 | 渠道：**站内为主（承接全部），企微为辅（只推催办级）** |
| D7 | 验证：**"发没发"以 sys_notification 表有记录为准**，不依赖企微通道 |
| D8 | **规则配置化**：提醒内容/周期/方式/接收角色/去重窗口全部入库可配（sys_reminder_rule + 配置界面）；**新增提醒点（触发逻辑）需开发埋点，界面不可凭空造**——配置界面控制"已有提醒点的所有参数" |

## 四、通知内核设计

### 4.1 数据模型 `sys_notification`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| user_id | int FK sys_user | 收件人 |
| point_code | str | 提醒点编码（如 SO_APPROVED） |
| title | str | 标题（"销售订单 SO-xxx 已审核，待排产"） |
| content | text | 正文 |
| doc_type | str | 关联单据类型（so_order/mo_production/ar_account…） |
| doc_id | int | 关联单据ID（用于跳转） |
| doc_no | str | 单据号（冗余，列表展示用） |
| dedup_key | str | 幂等键：point_code+doc_type+doc_id（唯一索引） |
| read_status | int | 0=未读 1=已读 |
| is_active | int | 1=有效（业务单据删除/状态回退时软失效） |
| created_at | datetime | |

### 4.2 API

- `GET /api/notifications` — 当前用户通知列表（未读优先，分页）
- `GET /api/notifications/unread-count` — 未读数（铃铛红点）
- `PUT /api/notifications/{id}/read` — 标记已读
- `PUT /api/notifications/read-all` — 全部已读
- `GET /api/notifications/latest` — 工作台待办区拉取（limit=N）
- `GET /api/notifications/admin-query` — **管理端全量查询**（admin 权限）：按 user_id/role_code/point_code/doc_type/时间筛选，测试验证与管理查看用

### 4.3 前端两个入口（关键区分）

- **顶部铃铛**：所有用户可见，只显示**当前登录用户自己的**消息（未读红点+列表弹层）
- **管理端通知查询页**（系统管理-预警提醒设置旁，admin 权限）：按角色/用户/提醒点/时间筛选**全量消息**——**测试验证的必需入口**（admin 登录铃铛看不到发给其他角色的通知，人肉验证全靠此页）

## 五、事件驱动提醒（需求1）

### 5.1 规则配置模型 `sys_reminder_rule`（D8：规则配置化）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| code | str 唯一 | 提醒点编码（对应代码埋点，如 SO_APPROVED） |
| name | str | 提醒名称 |
| trigger_type | str | event（事件联动）/ schedule（定时扫描） |
| enabled | int | 1=启用 0=停用 |
| title_template | str | 标题模板（支持 {order_no}/{amount}/{due_date} 占位符） |
| content_template | text | 正文模板 |
| target_roles | JSON | 接收角色列表 ["production_manager", ...] |
| channel | JSON | 渠道 ["inapp"] 或 ["inapp","wecom"] |
| schedule_cron | str | 定时型：cron 表达式（默认 "0 9 * * *"） |
| advance_days | int | 定时型：提前天数（默认 7） |
| dedup_hours | int | 事件型：去重窗口小时（默认 1） |

埋点代码只传 `point_code + 单据数据`，标题/内容/收件人/渠道/去重全部由规则决定——**埋点与配置彻底解耦**。

### 5.2 接收人解析函数（未来扩展点）

```
resolve_recipients(rule, doc) -> [user_id]
    第一版：rule.target_roles 对应角色的全部用户
    第二版（加业务员字段后）：单据归属人优先，无则按角色兜底 —— 只改此函数
```

### 5.3 埋点位置（第一版 4 个点）

| 提醒点 | 触发动作 | 埋点位置 |
|--------|----------|----------|
| SO_APPROVED | 销售订单审核通过 | sales.py 审核接口尾部 |
| MO_PLANNED | 生产订单排产/创建 | production.py 排产接口尾部 |
| MO_OUTSOURCED | 创建委外工单（转外购） | production.py create_outsourcing 尾部 |
| AR_CREATED | 应收生成 | sales.py 应收联动生成处 |

### 5.4 去重

`dedup_key = f"{point_code}:{doc_type}:{doc_id}"`，写前查 1 小时内是否已有同 key 记录（唯一索引 + created_at 窗口），有则跳过。

## 六、定时预警（需求2）

### 6.1 调度

- 引入 APScheduler，随应用 lifespan 启动
- 每日定时扫描（默认 09:00，可配）
- **启动时补扫一次**（D4）：应用启动后立即执行当日扫描逻辑，弥补未运行期间错过的预警

### 6.2 预警规则（阈值可配置，默认值实施时定）

| 规则 | 条件 | 提醒对象 |
|------|------|----------|
| 应收将到期 | due_date 在 [今天+1, 今天+N] 内且未收清 | 销售经理（催收） |
| 应付将到期 | due_date 在 [今天+1, 今天+N] 内且未付清 | 财务（安排付款） |
| 应收逾期 | due_date < 今天 且未收清 | 销售经理（催收升级） |
| 应付逾期 | due_date < 今天 且未付清 | 财务 |

- N（提前天数）默认 7，可配置
- 同单据同规则 1 小时内不重复推（与 D5 一致；扫描本身每日一次天然满足）

## 七、渠道（D6）

### 7.1 站内（主）

- 顶部铃铛 + 未读红点 + 通知列表弹层
- 工作台待办区（未读通知列表，点击跳转单据）
- 承接全部提醒

### 7.2 企微（辅，催办级）

- `sys_user` 增加 `wecom_userid` 字段（用户管理页维护）
- 企微服务：gettoken（缓存）+ message/send（textcard 带链接跳转）
- 提醒点注册表增加 `push_wecom: true/false` 标记，仅催办级（MO_OUTSOURCED、AR_CREATED、账期预警）推送
- 推送结果写 sys_reminder_log

### 7.3 企微与 AI Bot（远期）

- **AI 助手 = 企微自建应用**（非群机器人）：自建应用天然支持用户单聊 → 回调 → 回复到同一会话（到人）；提醒推送调同一应用 message/send（touser=userid）——**一条通道两用**
- 现有 BotConfig/BotConversation 按此方向演进
- 用户需在企微工作台安装该应用才能收到应用消息

## 八、实施顺序

| 步骤 | 内容 | 依赖 | 验收 |
|------|------|------|------|
| 1. 通知内核 | sys_notification 表+API+铃铛+工作台待办区 | 无 | 手动发一条测试通知可见 |
| 2. 事件埋点 | 4 个提醒点接入 reminder service | 1 | pytest 断言表记录+去重 |
| 3. 定时预警 | APScheduler+应收应付扫描+启动补扫 | 1 | 造到期数据→扫描→出通知 |
| 4. 企微通道 | userid 字段+发送服务+催办级推送 | 1,2,3 | 企微收到 textcard |

## 九、测试验证（D7）

三层验证，核心 = **通知落库即视为已发**：

1. **自动化（pytest）**：触发业务 → 断言 sys_notification 记录、收件人角色、去重、双收件人（AR_CREATED）
2. **半自动**：`curl GET /api/notifications?user_id=x`；sqlite 直查 sys_notification/sys_reminder_log
3. **肉眼**：登录角色测试账号 → 铃铛红点 + 工作台待办区 → 点击跳转单据；**admin 登录管理端通知查询页**按角色/用户筛选验证全量消息（admin 铃铛看不到其他角色的通知）

## 十、开放问题（实施时研判）

- 预警提前天数 N 默认值、逾期是否升级提醒
- 通知保留/清理策略（如 90 天后自动清理已读）
- 单据删除/状态回退时通知失效处理（is_active 软失效）
- 企微 userid 的维护入口形态（用户管理页加列？批量导入？）
- 工作台待办区与现有 Dashboard 布局的整合方式
