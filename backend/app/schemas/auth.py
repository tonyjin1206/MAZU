"""认证相关 Schemas"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = ""
    email: str = ""
    role: str = "operator"


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: int | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    email: str | None
    role: str
    is_active: int

    class Config:
        from_attributes = True
