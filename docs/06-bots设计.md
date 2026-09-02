# MTS AI Bot & 提醒系统 — 设计方案

> 版本 1.0 | 2026-07-29
>
> ⚠️ **2026-09 注**：本文为未实施功能的设计稿。生产管理模块已下线，文中涉及「生产订单/生产→入库」的流程（如意图路由到 production、生产订单对话流、生产待排产待办）在实施前需按现行业务（转直采买成品 + 材料独立采购 + 委外领料）重新设计。

---

## 一、背景与目标

### 1.1 现状问题

| 问题 | 说明 |
|------|------|
| 用户素质参差 | 小外贸公司员工不熟悉 ERP 操作，培训成本高 |
| 人员少 | 没有专门录单员，业务员自己填单效率低 |
| 录入滞后 | 线下发生业务后回到电脑前才补录，数据不及时 |
| 无主动提醒 | 应收到期、订单逾期全凭人工记忆 |

### 1.2 目标

- 员工通过**微信对话**完成采购 → 付款、销售 → 收款、生产 → 入库的全流程录单
- 系统主动推送**待办/到期/逾期/周报/老板日报**
- 不经过培训，零门槛上手

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| 确认前置 | 每次写入数据库前必须用户确认 |
| 渐进引导 | 一次只问一个字段，缺啥问啥 |
| 模糊宽容 | 名称/编码输入不精确也能匹配到正确的业务对象 |
| 可取消 | 任何一步都可以说"取消"回退 |

---

## 二、系统架构

```
┌─────────────────────────────────────────────┐
│               员工微信                       │
│  "下单 PCB板 100片 15块"                    │
└───────────────────┬─────────────────────────┘
                    │ 企微消息回调
                    ▼
┌─────────────────────────────────────────────┐
│              MTS Bot 引擎                    │
│                                              │
│  ┌──────────┐   ┌──────────────────────┐    │
│  │ 意图识别  │──→│   会话状态机         │    │
│  │ AI模型    │   │   IDLE → COLLECT     │    │
│  │           │   │   → CONFIRM → DONE   │    │
│  └────┬─────┘   └──────────┬───────────┘    │
│       │                    │                 │
│  ┌────▼────────────────────▼───────────┐    │
│  │    模糊匹配 + 实体校验               │    │
│  │    供应商/客户/物料/产品 DB 查询     │    │
│  └─────────────────────────────────────┘    │
└───────────────────┬─────────────────────────┘
                    │ 结构化 JSON
                    ▼
┌─────────────────────────────────────────────┐
│              MTS API                        │
│  创建采购订单 / 销售订单 / 生产订单          │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│          定时提醒引擎 (Cron Job)              │
│  日待办 / 到期 / 逾期 / 周报 / 老板日报       │
└─────────────────────────────────────────────┘
```

---

## 三、数据库设计

### 3.1 企业微信配置表 `sys_wecom_config`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| corp_id | varchar(64) | 企业ID |
| agent_id | varchar(32) | 应用AgentID |
| secret | varchar(256) | 应用Secret（加密存储） |
| token | varchar(64) | 回调验证Token |
| encoding_aes_key | varchar(256) | 回调加密密钥 |
| callback_url | varchar(256) | 回调URL（自动生成） |
| is_active | int | 1=启用 |
| created_at | datetime | |

### 3.2 AI 模型配置表 `sys_bot_config`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| provider | varchar(32) | deepseek / openai |
| api_key | varchar(256) | API Key（加密存储） |
| base_url | varchar(256) | API 地址（默认官方） |
| model | varchar(64) | 模型名，如 deepseek-chat |
| temperature | float | 0.0-1.0，默认 0.1 |
| max_tokens | int | 默认 1024 |
| system_prompt | text | 系统提示词模板（可编辑） |
| is_active | int | 1=启用 |
| created_at | datetime | |

### 3.3 会话表 `sys_bot_conversation`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| user_id | int FK | MTS 系统用户ID |
| wecom_userid | varchar(64) | 企微用户ID |
| session_id | varchar(64) | 会话唯一标识 |
| intent | varchar(32) | purchase/sales/production |
| state | varchar(16) | idle/collecting/confirm/done/cancelled |
| context_json | text | 已收集的字段（JSON） |
| created_at | datetime | |
| updated_at | datetime | |

### 3.4 提醒配置表 `sys_reminder_config`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| user_id | int FK | MTS 用户ID |
| type | varchar(32) | daily_todo / expiry / overdue / weekly / boss_report |
| enabled | int | 1=启用 |
| push_time | varchar(8) | 推送时间 HH:mm |
| push_days | varchar(32) | 推送日（周报用，如 MON） |
| created_at | datetime | |

### 3.5 提醒日志表 `sys_reminder_log`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| user_id | int FK | |
| type | varchar(32) | |
| title | varchar(128) | 推送标题 |
| content | text | 推送内容 |
| status | varchar(16) | success / fail |
| error_msg | varchar(256) | |
| pushed_at | datetime | |

---

## 四、Bot 对话引擎

### 4.1 状态机

```
                   用户发送消息
                        │
                        ▼
┌───── IDLE ──────────────────────────────┐
│  AI 判断用户意图：                       │
│  「下单」「采购」「进货」→ purchase      │
│  「销售」「出货」「卖」 → sales          │
│  「生产」「工单」「做」 → production     │
│  其他 → 回复帮助信息                    │
└──────────────┬──────────────────────────┘
               │ 确定 intent
               ▼
┌───── COLLECTING ─────────────────────────┐
│  遍历当前单据的必填字段：                │
│  purchase: supplier, items[], date       │
│  sales: customer, items[], date          │
│  production: product, qty, due_date      │
│                                          │
│  每轮检查缺失字段 → 主动提问             │
│  AI 从对话中抽取实体 → 填入上下文         │
│  模糊匹配 DB → 返回匹配结果让用户确认     │
└──────────────┬──────────────────────────┘
               │ 全部字段收集完毕
               ▼
┌───── CONFIRM ────────────────────────────┐
│  展示完整单据给用户确认：                 │
│  ┌──────────────────────────┐            │
│  │ 📋 采购订单确认：        │            │
│  │   供应商: 深圳电子       │            │
│  │   PCB板 x100 ¥15 = ¥1,500│            │
│  │   日期: 今天             │            │
│  ├──────────────────────────┤            │
│  │ 回复「确认」或「Y」提交  │            │
│  │ 回复「取消」放弃         │            │
│  │ 回复「改数量」修改字段   │            │
│  └──────────────────────────┘            │
└──────┬───────────────┬───────────────────┘
       │ 确认           │ 取消
       ▼                ▼
   ┌───────┐      ┌──────────┐
   │ DONE  │      │CANCELLED │
   │ 调API │      │ 清空会话 │
   │ 创建  │      └──────────┘
   │ 通知  │
   └───────┘
```

### 4.2 意图识别 Prompt 模板

默认系统提示词（可在配置页编辑）：

```
你是 MTS (Mazu Trade System) 的 AI 助手，用户通过微信聊天来创建业务单据。

## 支持的单据类型

1. 采购订单 purchase_order
   - 供应商 supplier（来自 fd_supplier 表）
   - 物料明细 items[]（来自 fd_material 表，每项含 material_id, quantity, unit_price）
   - 日期 date

2. 销售订单 sales_order  
   - 客户 customer（来自 fd_customer 表）
   - 产品明细 items[]（来自 fd_product 表，每项含 product_id, quantity, unit_price）
   - 日期 date

3. 生产订单 production_order
   - 产品 product（来自 fd_product 表）
   - 数量 quantity
   - 计划完成日 due_date

## 规则
- 逐步收集字段，每轮回复只问一个缺失的字段
- 如果用户一句话提供了多个字段，全部提取
- 供应商/客户/物料/产品名称用模糊匹配，返回 top 3 候选让用户选
- 用户说"确认"/"Y"/"对"/"提交"时设置 confirmed=true
- 用户说"取消"/"算了"/"不要了"时结束会话
- 日期默认为今天，如果用户没指定

## 输出格式
当你收集足够信息时，输出以下 JSON 让系统确认：
{"intent":"purchase_order","confirmed":false,"data":{...}}
当用户确认后输出：
{"intent":"purchase_order","confirmed":true,"data":{...}}
```

### 4.3 模糊匹配逻辑

供应商/客户/物料/产品的匹配流程：

```
用户输入: "深圳电子"
  │
  ├──→ 精确匹配 code="深圳电子" → 命中
  ├──→ LIKE "%深圳电子%" → 命中「深圳电子元件有限公司」
  └──→ AI 语义匹配（走 AI 模型判断哪个最像）
        │
        └──→ 返回 top 3 候选让用户选择
              "您说的是哪个？
               1. 深圳电子元件有限公司
               2. 深圳电子科技股份有限公司
               回复编号或全称"
```

---

## 五、配置页面

### 5.1 企业微信配置 `/system/wecom`

| 字段 | 控件 | 说明 |
|------|------|------|
| CorpID | input | 从企微后台复制 |
| AgentID | input | |
| Secret | password input | 加密存储，显示**** |
| Token | input | 回调验证 |
| EncodingAESKey | input | |
| 状态 | indicator | 绿色=已连接，红色=未配置 |
| [验证连接] | button | 测试 API 是否可用 |
| [保存] | button | |

### 5.2 AI 模型配置 `/system/bot`

| 字段 | 控件 | 说明 |
|------|------|------|
| 提供商 | select | DeepSeek / OpenAI |
| API 地址 | input | 默认官方地址 |
| API Key | password input | 加密存储 |
| 模型名 | select/input | gpt-4o-mini / deepseek-chat 等 |
| 温度 | slider | 0-1，推荐 0.1 保持稳定 |
| 系统提示词 | textarea (大) | 带行号、可编辑、monospace 字体 |
| [恢复默认] | button | 恢复出厂提示词 |
| [测试对话] | button | 发送测试消息看 AI 回复 |

### 5.3 提醒管理 `/system/reminders`

每个用户一张开关表：

| 用户 | 日待办 | 到期提醒 | 逾期告警 | 周报 | 老板日报 | 推送时间 |
|------|:------:|:--------:|:--------:|:---:|:--------:|---------|
| admin | ◉ | ◉ | ◉ | ◉ | ◉ | 09:00 |
| 张三 | ◉ | ◉ | ◯ | ◯ | ◯ | 09:00 |

老板日报指向特定用户（如 admin），推送当日经营汇总。

---

## 六、定时提醒任务

由 Cron Job 驱动，每个任务独立：

| 任务 | 调度 | SQL 查询 | 推送内容示例 |
|------|------|----------|-------------|
| 日待办 | 每天 push_time | 采购待入库 / 销售待发货 / 生产待排产 | "📋 今日待办：采购入库 2 单，销售发货 1 单" |
| 到期提醒 | 每天 push_time | 应收/应付 today <= due_date <= today+3 | "⚠️ 应收今日到期：客户A ¥6,000" |
| 逾期告警 | 每天 push_time | 应收/应付 due_date < today AND balance > 0 | "🚨 逾期应付：供应商C ¥5,000（逾期3天）" |
| 周报 | 每周一 push_time | 上周新增单据汇总 | "📊 上周新增销售5单¥86,000，采购3单¥12,500" |
| 老板日报 | 每天 18:00 | 今日新增/完成汇总 | "📈 今日经营日报：新增采购2单¥3,200，收款¥6,000" |

每个任务检查 `sys_reminder_config` 表中哪些用户开启了对应类型的提醒，推送到企微应用消息。

---

## 七、开发阶段

### Phase 1 — 核心后端 + 配置页面

| 内容 | 说明 |
|------|------|
| 6 张新数据库表 | wecom_config / bot_config / conversation / reminder_config / reminder_log / daily_report |
| 企微配置页 | CRUD + 加密存储 + 连接验证 |
| AI 模型配置页 | 提供商切换 + 提示词编辑器 + 测试对话 |
| 提醒管理页 | 用户开关 + 时间设置 |
| 企微回调端点 | 消息接收 + 验签 |

### Phase 2 — AI 对话引擎

| 内容 | 说明 |
|------|------|
| 会话状态机 | IDLE → COLLECT → CONFIRM → DONE |
| AI 调用封装 | 通用接口，支持 DeepSeek / OpenAI 切换 |
| 模糊匹配 | 供应商/客户/物料/产品 的 DB 模糊查询 + AI 辅助判断 |
| 采购单对话流 | 完整走通 |
| 销售单对话流 | 完整走通 |
| 生产单对话流 | 完整走通 |
| 确认/取消/修改 | 全状态处理 |

### Phase 3 — 提醒系统

| 内容 | 说明 |
|------|------|
| Cron 任务注册 | 5 个定时任务 |
| 企微消息推送 | 应用消息 API |
| 日报生成 | 数据聚合 + 格式化 |
| 推送日志 | 失败重试 + 记录 |

---

## 八、技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| AI API | DeepSeek 或 OpenAI | 通过配置页切换 |
| 企微 SDK | wechatpy 或自建 | 消息加解密 |
| 定时任务 | Hermes Cronjob | 已内建支持 |
| 加密存储 | cryptography.fernet | API Key/Secret 加密 |
| 前端 | 现有 Element Plus | 新增 3 个配置页面 |

---

## 九、风险与注意

| 风险 | 应对 |
|------|------|
| AI 幻觉产生不存在的供应商/物料 | 所有实体必须通过 DB 查询验证，AI 仅做意图和语义匹配 |
| 企微回调超时 | 异步处理：收到后立即返回 200，后台处理再推送结果 |
| 多轮对话丢失 | 会话有 updated_at，超过 1 小时无操作自动超时 |
| API Key 泄露 | 加密存储不在页面明文显示 |
