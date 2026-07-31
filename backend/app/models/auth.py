"""用户、角色、权限模型 — RBAC 权限体系"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, func, Table
)
from sqlalchemy.orm import relationship
from app.database import Base


# ==================== 多对多关联表 ====================

class RolePermission(Base):
    """角色 ↔ 权限 关联"""
    __tablename__ = "sys_role_permission"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False)
    permission_code = Column(String(64), ForeignKey("sys_permission.code", ondelete="CASCADE"), nullable=False)

    def __repr__(self):
        return f"<RolePermission role={self.role_id} perm={self.permission_code}>"


# ==================== 权限 ====================

class Permission(Base):
    """系统权限定义"""
    __tablename__ = "sys_permission"

    code = Column(String(64), primary_key=True, comment="权限码: module:action")
    name = Column(String(64), nullable=False, comment="权限名称")
    module = Column(String(32), nullable=False, comment="所属模块")
    description = Column(String(256), comment="描述")
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Permission {self.code}>"


# ==================== 角色 ====================

class Role(Base):
    """角色定义"""
    __tablename__ = "sys_role"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment="角色名称")
    code = Column(String(64), unique=True, nullable=False, comment="角色编码")
    description = Column(String(256), comment="描述")
    is_system = Column(Integer, default=0, comment="1=系统内置不可删")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关联
    permissions = relationship("Permission", secondary="sys_role_permission",
                                viewonly=True)
    role_permissions = relationship("RolePermission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Role {self.code}>"


# ==================== 用户 ====================

class User(Base):
    """系统用户（支持 RBAC 角色）"""
    __tablename__ = "sys_user"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(256), nullable=False, comment="密码哈希")
    display_name = Column(String(64), comment="显示名称")
    email = Column(String(128), comment="邮箱")
    role_id = Column(Integer, ForeignKey("sys_role.id"), comment="角色ID")
    is_active = Column(Integer, default=1, comment="1=启用 0=停用")
    created_at = Column(DateTime, default=func.now())

    # 关联
    role = relationship("Role", foreign_keys=[role_id])

    @property
    def role_name(self) -> str | None:
        return self.role.name if self.role else None

    @property
    def role_code(self) -> str | None:
        return self.role.code if self.role else None

    @property
    def permission_codes(self) -> set:
        """获取用户有效权限码集合（admin 角色=全量权限，动态查询不依赖快照）"""
        if not self.role:
            return set()
        if self.role.code == "admin":
            from sqlalchemy.orm import object_session
            session = object_session(self)
            if session is None:
                from app.database import SessionLocal
                session = SessionLocal()
                close = True
            else:
                close = False
            try:
                return {p.code for p in session.query(Permission).all()}
            finally:
                if close:
                    session.close()
        return {rp.permission_code for rp in self.role.role_permissions}

    def has_permission(self, code: str) -> bool:
        """检查用户是否有指定权限（管理员永远全权限）"""
        if self.role and self.role.code == "admin":
            return True
        return code in self.permission_codes

    def __repr__(self):
        return f"<User {self.username}>"
