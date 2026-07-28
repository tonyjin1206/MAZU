"""认证与 RBAC 相关 Schemas"""

from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 登录 ====================

class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ==================== 用户 ====================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = ""
    email: str = ""
    role_id: int | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role_id: int | None = None
    is_active: int | None = None
    password: str | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    email: str | None
    role_id: int | None
    role_name: str | None = None
    role_code: str | None = None
    is_active: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ==================== 权限 ====================

class PermissionOut(BaseModel):
    code: str
    name: str
    module: str
    description: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ==================== 角色 ====================

class RoleCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    permission_codes: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_codes: list[str] | None = None


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    is_system: int
    permission_codes: list[str] = []
    user_count: int = 0
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class PermissionGroup(BaseModel):
    """按模块分组的权限"""
    module: str
    permissions: list[PermissionOut]
