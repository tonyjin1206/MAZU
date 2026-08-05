"""系统配置模型 — 企业微信、AI Bot、提醒、会话"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, func, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


class WecomConfig(Base):
    """企业微信连接配置"""
    __tablename__ = "sys_wecom_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    corp_id = Column(String(64), nullable=False, comment="企业ID")
    agent_id = Column(String(32), nullable=False, comment="应用AgentID")
    secret = Column(String(256), nullable=False, comment="应用Secret（加密存储）")
    token = Column(String(64), comment="回调验证Token")
    encoding_aes_key = Column(String(256), comment="回调加密密钥")
    callback_url = Column(String(256), comment="回调URL")
    is_active = Column(Integer, default=1, comment="1=启用")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BotConfig(Base):
    """Agent设置"""
    __tablename__ = "sys_bot_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False, default="deepseek", comment="deepseek / openai")
    api_key = Column(String(256), nullable=False, comment="API Key（加密存储）")
    base_url = Column(String(256), comment="API 地址，默认官方")
    model = Column(String(64), nullable=False, default="deepseek-chat", comment="模型名")
    temperature = Column(Float, default=0.1, comment="温度 0-1")
    max_tokens = Column(Integer, default=1024, comment="最大token数")
    system_prompt = Column(Text, comment="系统提示词模板")
    is_active = Column(Integer, default=1, comment="1=启用")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BotConversation(Base):
    """AI 对话会话"""
    __tablename__ = "sys_bot_conversation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="MTS用户ID")
    wecom_userid = Column(String(64), comment="企微用户ID")
    session_id = Column(String(64), nullable=False, comment="会话标识")
    intent = Column(String(32), comment="purchase / sales / production")
    state = Column(String(16), default="idle", comment="idle/collecting/confirm/done/cancelled")
    context_json = Column(Text, comment="已收集字段JSON")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ReminderConfig(Base):
    """用户提醒开关"""
    __tablename__ = "sys_reminder_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="用户ID")
    type = Column(String(32), nullable=False, comment="daily_todo/expiry/overdue/weekly/boss_report")
    enabled = Column(Integer, default=1, comment="1=启用")
    push_time = Column(String(8), default="09:00", comment="推送时间 HH:mm")
    push_days = Column(String(32), default="MON", comment="推送日（周报用）")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])


class OperationLog(Base):
    """AI 助手操作审计日志"""
    __tablename__ = "sys_operation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), comment="操作人ID")
    username = Column(String(64), nullable=False, comment="操作人用户名")
    role_code = Column(String(64), comment="操作人角色编码")
    instruction = Column(Text, comment="用户原始指令")
    tool_name = Column(String(64), nullable=False, comment="工具名")
    args_json = Column(Text, comment="工具参数JSON")
    result = Column(String(512), comment="执行结果摘要")
    doc_no = Column(String(64), comment="关联单据号")
    success = Column(Integer, default=1, comment="1=成功 0=失败")
    created_at = Column(DateTime, default=func.now())


class ReminderLog(Base):
    """推送日志"""
    __tablename__ = "sys_reminder_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False)
    type = Column(String(32), nullable=False)
    title = Column(String(128), comment="推送标题")
    content = Column(Text, comment="推送内容")
    status = Column(String(16), default="success", comment="success/fail")
    error_msg = Column(String(256))
    pushed_at = Column(DateTime, default=func.now())


class ReminderRule(Base):
    """提醒规则 — 提醒内容/周期/方式/触发方式/接收角色 全部可配置"""
    __tablename__ = "sys_reminder_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, comment="提醒点编码（对应代码埋点，如 SO_APPROVED）")
    name = Column(String(64), nullable=False, comment="提醒名称")
    trigger_type = Column(String(16), nullable=False, default="event", comment="event=事件联动 / schedule=定时扫描")
    enabled = Column(Integer, default=1, comment="1=启用 0=停用")
    title_template = Column(String(256), comment="标题模板（支持 {order_no}/{amount}/{due_date} 占位符）")
    content_template = Column(Text, comment="正文模板")
    target_roles = Column(JSON, comment='接收角色列表 ["production_manager", ...]')
    channel = Column(JSON, comment='渠道 ["inapp"] 或 ["inapp","wecom"]')
    schedule_cron = Column(String(32), default="0 9 * * *", comment="定时型：cron 表达式")
    advance_days = Column(Integer, default=7, comment="定时型：提前天数")
    dedup_hours = Column(Integer, default=1, comment="事件型：去重窗口小时")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Notification(Base):
    """站内通知 — 提醒落库即视为已发（D7）"""
    __tablename__ = "sys_notification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True, comment="收件人")
    point_code = Column(String(64), index=True, comment="提醒点编码")
    title = Column(String(256), comment="标题")
    content = Column(Text, comment="正文")
    doc_type = Column(String(32), comment="关联单据类型 so_order/mo_production/ar_account")
    doc_id = Column(Integer, comment="关联单据ID（跳转用）")
    doc_no = Column(String(64), comment="单据号（冗余展示）")
    dedup_key = Column(String(128), index=True, comment="幂等键 point_code:doc_type:doc_id")
    read_status = Column(Integer, default=0, comment="0=未读 1=已读")
    is_active = Column(Integer, default=1, comment="1=有效（单据删除/状态回退时软失效）")
    created_at = Column(DateTime, default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
