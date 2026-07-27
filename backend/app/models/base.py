"""模型基类 — 公共字段"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String
from app.database import Base


class BaseMixin:
    """模型通用字段"""
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(64), default="系统")
    is_active = Column(Integer, default=1, comment="1=启用 0=停用")
