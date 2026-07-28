"""认证与 RBAC API 路由 — 用户/角色/权限管理"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.models.auth import User, Role, Permission, RolePermission
from app.schemas.auth import (
    LoginRequest, TokenResponse,
    UserCreate, UserUpdate, UserOut,
    RoleCreate, RoleUpdate, RoleOut,
    PermissionOut, PermissionGroup,
)
from app.utils.auth import (
    create_access_token,
    verify_password,
    get_password_hash,
    get_current_user,
    get_current_admin,
)

router = APIRouter()


# ==================== 登录 / 当前用户 ====================

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已停用")

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserOut.model_validate(current_user)


@router.get("/me/permissions")
def get_my_permissions(current_user: User = Depends(get_current_user)):
    """获取当前用户的有效权限码列表"""
    return {
        "permissions": list(current_user.permission_codes),
        "role_code": current_user.role.code if current_user.role else None,
    }


# ==================== 用户管理 ====================

@router.post("/users", response_model=UserOut)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """管理员：创建用户"""
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        display_name=data.display_name or data.username,
        email=data.email,
        role_id=data.role_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    keyword: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户列表"""
    query = db.query(User)
    if keyword:
        query = query.filter(
            User.username.like(f"%{keyword}%") |
            User.display_name.like(f"%{keyword}%")
        )
    users = query.order_by(User.id.desc()).all()
    return [UserOut.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserOut.model_validate(user)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """管理员：更新用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = data.model_dump(exclude_unset=True)
    # 密码单独处理
    if "password" in update_data and update_data["password"]:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    elif "password" in update_data:
        update_data.pop("password")

    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """管理员：删除用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    db.delete(user)
    db.commit()
    return {"message": "用户已删除"}


# ==================== 权限查询 ====================

# 预置权限定义（按模块分组）
PERMISSION_DEFS = [
    # 工作台
    {"code": "dashboard:read", "name": "查看驾驶舱", "module": "工作台", "description": "查看首页工作台数据"},

    # 基础档案
    {"code": "foundation:read", "name": "查看基础档案", "module": "基础档案", "description": "查看客户/供应商/物料/产品等基础数据"},
    {"code": "foundation:write", "name": "编辑基础档案", "module": "基础档案", "description": "增删改基础档案数据"},

    # 采购管理
    {"code": "purchase:read", "name": "查看采购", "module": "采购管理", "description": "查看采购订单/入库/发票/应付等"},
    {"code": "purchase:write", "name": "编辑采购", "module": "采购管理", "description": "增删改采购单据"},
    {"code": "purchase:approve", "name": "审批采购", "module": "采购管理", "description": "审核/反审核采购订单"},

    # 销售管理
    {"code": "sales:read", "name": "查看销售", "module": "销售管理", "description": "查看销售订单/发货/发票/应收等"},
    {"code": "sales:write", "name": "编辑销售", "module": "销售管理", "description": "增删改销售单据"},
    {"code": "sales:approve", "name": "审批销售", "module": "销售管理", "description": "审核/反审核销售订单"},

    # 生产管理
    {"code": "production:read", "name": "查看生产", "module": "生产管理", "description": "查看生产订单/工作台/加工费等"},
    {"code": "production:write", "name": "编辑生产", "module": "生产管理", "description": "增删改生产单据"},

    # 库存管理
    {"code": "inventory:read", "name": "查看库存", "module": "库存管理", "description": "查看库存收发存"},
    {"code": "inventory:write", "name": "编辑库存", "module": "库存管理", "description": "库存调整操作"},

    # 退税管理
    {"code": "tax:read", "name": "查看退税", "module": "退税管理", "description": "查看退税申报"},
    {"code": "tax:write", "name": "编辑退税", "module": "退税管理", "description": "增删改退税申报"},

    # 系统管理
    {"code": "system:admin", "name": "系统管理", "module": "系统管理", "description": "用户管理/角色管理/系统设置"},
]


@router.get("/permissions", response_model=list[PermissionGroup])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有权限（按模块分组）"""
    # 先从数据库查
    perms = db.query(Permission).order_by(Permission.code).all()
    if not perms:
        return []

    modules: dict[str, list[PermissionOut]] = {}
    for p in perms:
        mod = p.module
        if mod not in modules:
            modules[mod] = []
        modules[mod].append(PermissionOut.model_validate(p))

    # 按原始定义顺序排序
    module_order = [d["module"] for d in PERMISSION_DEFS]
    result = []
    seen = set()
    for mod in module_order:
        if mod in modules:
            result.append(PermissionGroup(module=mod, permissions=modules[mod]))
            seen.add(mod)
    # 补上不在顺序中的模块
    for mod, perms_list in modules.items():
        if mod not in seen:
            result.append(PermissionGroup(module=mod, permissions=perms_list))
    return result


# ==================== 角色管理 ====================

@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取角色列表"""
    roles = db.query(Role).order_by(Role.id).all()
    result = []
    for r in roles:
        perm_codes = [rp.permission_code for rp in r.role_permissions]
        user_count = db.query(sa_func.count(User.id)).filter(User.role_id == r.id).scalar() or 0
        result.append(RoleOut(
            id=r.id, name=r.name, code=r.code,
            description=r.description, is_system=r.is_system,
            permission_codes=perm_codes,
            user_count=user_count,
            created_at=r.created_at,
        ))
    return result


@router.post("/roles", response_model=RoleOut)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """创建角色"""
    existing = db.query(Role).filter(Role.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="角色编码已存在")

    role = Role(
        name=data.name,
        code=data.code,
        description=data.description,
        is_system=0,
    )
    db.add(role)
    db.flush()

    # 关联权限
    for code in data.permission_codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if perm:
            db.add(RolePermission(role_id=role.id, permission_code=code))

    db.commit()
    db.refresh(role)

    perm_codes = [rp.permission_code for rp in role.role_permissions]
    return RoleOut(
        id=role.id, name=role.name, code=role.code,
        description=role.description, is_system=role.is_system,
        permission_codes=perm_codes, user_count=0,
        created_at=role.created_at,
    )


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """更新角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description

    # 更新权限
    if data.permission_codes is not None:
        # 删除旧权限
        db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        # 添加新权限
        for code in data.permission_codes:
            perm = db.query(Permission).filter(Permission.code == code).first()
            if perm:
                db.add(RolePermission(role_id=role.id, permission_code=code))

    db.commit()
    db.refresh(role)

    perm_codes = [rp.permission_code for rp in role.role_permissions]
    user_count = db.query(sa_func.count(User.id)).filter(User.role_id == role.id).scalar() or 0
    return RoleOut(
        id=role.id, name=role.name, code=role.code,
        description=role.description, is_system=role.is_system,
        permission_codes=perm_codes, user_count=user_count,
        created_at=role.created_at,
    )


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """删除角色（内置角色不可删）"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    # 检查有无用户
    user_count = db.query(sa_func.count(User.id)).filter(User.role_id == role.id).scalar() or 0
    if user_count > 0:
        raise HTTPException(status_code=400, detail=f"该角色下还有 {user_count} 个用户，请先移除用户再删除")
    db.delete(role)
    db.commit()
    return {"message": "角色已删除"}
