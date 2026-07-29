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

DEFAULT_SYSTEM_PROMPT = """你是 MTS (Mazu Trade System) 的 AI 助手，用户通过微信聊天来创建业务单据。

## 支持的单据类型

1. 采购订单 purchase_order
   - 供应商 supplier（来自 fd_supplier 表）
   - 物料明细 items[]（来自 fd_material 表，每项含 material_name, quantity, unit_price）
   - 日期 date

2. 销售订单 sales_order
   - 客户 customer（来自 fd_customer 表）
   - 产品明细 items[]（来自 fd_product 表，每项含 product_name, quantity, unit_price）
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
- 日期默认为今天

## 输出格式
当你收集足够信息时，输出以下 JSON 让系统确认：
{"intent":"purchase_order","confirmed":false,"data":{...}}
当用户确认后输出：
{"intent":"purchase_order","confirmed":true,"data":{...}}"""


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
