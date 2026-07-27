"""用户与角色模型"""

from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class User(Base):
    """系统用户"""
    __tablename__ = "sys_user"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(256), nullable=False, comment="密码哈希")
    display_name = Column(String(64), comment="显示名称")
    email = Column(String(128), comment="邮箱")
    role = Column(String(32), default="operator", comment="admin=管理员, operator=操作员, readonly=只读")
    is_active = Column(Integer, default=1, comment="1=启用 0=停用")
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<User {self.username}>"
