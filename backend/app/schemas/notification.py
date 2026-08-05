"""通知 Schemas — 站内通知中心"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    id: int
    user_id: int
    point_code: str | None
    title: str | None
    content: str | None
    doc_type: str | None
    doc_id: int | None
    doc_no: str | None
    read_status: int
    is_active: int
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationAdminOut(NotificationOut):
    """管理端全量查询 — 附收件人信息"""
    user_name: str | None = None
    role_name: str | None = None


class NotificationReadUpdate(BaseModel):
    read_status: int = 1
