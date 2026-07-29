"""系统配置 Schemas — 企微/AI Bot/提醒"""

from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 企业微信 ====================

class WecomConfigCreate(BaseModel):
    corp_id: str
    agent_id: str
    secret: str
    token: str = ""
    encoding_aes_key: str = ""
    is_active: int = 1


class WecomConfigUpdate(BaseModel):
    corp_id: str | None = None
    agent_id: str | None = None
    secret: str | None = None
    token: str | None = None
    encoding_aes_key: str | None = None
    is_active: int | None = None


class WecomConfigOut(BaseModel):
    id: int
    corp_id: str
    agent_id: str
    secret: str
    token: str | None
    encoding_aes_key: str | None
    callback_url: str | None
    is_active: int
    created_at: datetime | None

    class Config:
        from_attributes = True


# ==================== AI Bot ====================

DEFAULT_SYSTEM_PROMPT = """你是 MTS 系统的 ERP 助手，通过对话帮助用户完成工作。

## 可用工具

1. query_entities — 查客户/供应商/物料/产品/应收/应付/发票清单
2. create_order — 创建采购订单/销售订单
3. create_collection — 创建收款单（客户回款+自动核销应收）
4. create_payment — 创建付款单（向供应商付款+自动核销应付）
5. create_purchase_invoice — 录入采购发票（关联采购单）
6. create_sales_invoice — 录入销售发票（关联销售单）
7. create_outsourcing — 创建委外加工单（工序委外+发料）
8. issue_materials — 生产发料/领料
9. production_receipt — 生产完工入库

## 工作流程

### 查询
- 用户说「查xxx/找xxx/xxx清单」→ **必须立即调 query_entities**，不准只回复「好的」
- keyword 留空 = 列出全部；有 keyword = 模糊搜索
- 应收/应付会自动汇总余额
- **不要编造数据**，工具返回什么就展示什么

### 创建类操作（三步确认）
第一步：问清要做什么
  用户说模糊时反问：「您是要下单、收款、付款，还是做委外/发料/入库？」

第二步：收集必要字段
  逐一问，一次只问一个，用户回答了再问下一个
  - 采购单需要：供应商、物料、数量、单价
  - 销售单需要：客户、产品、数量、单价
  - 收款需要：客户、金额
  - 付款需要：供应商、金额
  - 采购发票需要：采购单号、发票号、金额
  - 销售发票需要：销售单号、发票号、金额
  - 委外需要：生产单号、工序、供应商、数量
  - 发料需要：生产单号、物料、数量
  - 入库需要：生产单号、数量

第三步：逐项核对后执行
  列出全部字段让用户确认，用户说「对/是/确认」再调工具
  如果工具返回错误，如实告诉用户原因

## 对话风格
- 中文，简短，像同事聊天
- 一次只问一件事
- 不懂就反问，不要瞎编
- 查询结果直接给"""


class BotConfigCreate(BaseModel):
    provider: str = "deepseek"
    api_key: str
    base_url: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 1024
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    is_active: int = 1


class BotConfigUpdate(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None
    is_active: int | None = None


class BotConfigOut(BaseModel):
    id: int
    provider: str
    api_key: str
    base_url: str | None
    model: str
    temperature: float
    max_tokens: int
    system_prompt: str | None
    is_active: int
    created_at: datetime | None

    class Config:
        from_attributes = True


# ==================== 提醒配置 ====================

REMINDER_TYPES = [
    ("daily_todo", "日待办"),
    ("expiry", "到期提醒"),
    ("overdue", "逾期告警"),
    ("weekly", "周报"),
    ("boss_report", "老板日报"),
]


class ReminderConfigCreate(BaseModel):
    user_id: int
    type: str
    enabled: int = 1
    push_time: str = "09:00"
    push_days: str = "MON"


class ReminderConfigUpdate(BaseModel):
    enabled: int | None = None
    push_time: str | None = None
    push_days: str | None = None


class ReminderConfigOut(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    type: str
    type_label: str | None = None
    enabled: int
    push_time: str
    push_days: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class ReminderLogOut(BaseModel):
    id: int
    user_id: int
    type: str
    title: str | None
    content: str | None
    status: str
    error_msg: str | None
    pushed_at: datetime | None

    class Config:
        from_attributes = True
