"""MTS 后端 — 共享 fixtures（含 RBAC 种子数据）"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.database import init_db, SessionLocal, engine, Base
from app.utils.auth import get_password_hash
from app.models.auth import User, Role, Permission, RolePermission


def _seed_rbac_test(db):
    """测试用 RBAC 种子数据（与 main.py _seed_rbac 一致）"""
    permission_defs = [
        {"code": "dashboard:read",    "name": "查看驾驶舱",   "module": "工作台",   "description": ""},
        {"code": "foundation:read",   "name": "查看基础档案",  "module": "基础档案",   "description": ""},
        {"code": "foundation:write",  "name": "编辑基础档案",  "module": "基础档案",   "description": ""},
        {"code": "purchase:read",     "name": "查看采购",     "module": "采购管理",   "description": ""},
        {"code": "purchase:write",    "name": "编辑采购",     "module": "采购管理",   "description": ""},
        {"code": "purchase:approve",  "name": "审批采购",     "module": "采购管理",   "description": ""},
        {"code": "sales:read",        "name": "查看销售",     "module": "销售管理",   "description": ""},
        {"code": "sales:write",       "name": "编辑销售",     "module": "销售管理",   "description": ""},
        {"code": "sales:approve",     "name": "审批销售",     "module": "销售管理",   "description": ""},
        {"code": "production:read",   "name": "查看生产",     "module": "生产管理",   "description": ""},
        {"code": "production:write",  "name": "编辑生产",     "module": "生产管理",   "description": ""},
        {"code": "inventory:read",    "name": "查看库存",     "module": "库存管理",   "description": ""},
        {"code": "inventory:write",   "name": "编辑库存",     "module": "库存管理",   "description": ""},
        {"code": "tax:read",          "name": "查看退税",     "module": "退税管理",   "description": ""},
        {"code": "tax:write",         "name": "编辑退税",     "module": "退税管理",   "description": ""},
        {"code": "system:admin",      "name": "系统管理",     "module": "系统管理",   "description": ""},
    ]
    for pd in permission_defs:
        if not db.query(Permission).filter(Permission.code == pd["code"]).first():
            db.add(Permission(**pd))

    all_codes = [p["code"] for p in permission_defs]
    biz_codes = [c for c in all_codes if c != "system:admin"]
    no_approve = [c for c in biz_codes if not c.endswith(":approve")]
    read_codes = [c for c in all_codes if c.endswith(":read")]

    role_defs = [
        ("管理员", "admin", all_codes),
        ("经理", "manager", biz_codes),
        ("操作员", "operator", no_approve),
        ("只读", "readonly", read_codes),
    ]
    for name, code, perms in role_defs:
        role = db.query(Role).filter(Role.code == code).first()
        if not role:
            role = Role(name=name, code=code, description="", is_system=1)
            db.add(role)
            db.flush()
            for pc in perms:
                perm = db.query(Permission).filter(Permission.code == pc).first()
                if perm:
                    db.add(RolePermission(role_id=role.id, permission_code=pc))

    # 确保 admin 用户关联管理员角色
    admin_role = db.query(Role).filter(Role.code == "admin").first()
    if admin_role:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin and not admin.role_id:
            admin.role_id = admin_role.id

    db.commit()


@pytest.fixture(scope="session")
def app():
    """创建 FastAPI 应用实例"""
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """TestClient for HTTP testing"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """清空所有表数据，重建表 + RBAC 种子数据 + 默认管理员"""
    init_db()
    from sqlalchemy import text
    meta = Base.metadata
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(meta.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()
    db = SessionLocal()
    try:
        _seed_rbac_test(db)
    finally:
        db.close()
    yield


@pytest.fixture(scope="session")
def admin_token(client):
    """获取管理员登录 Token"""
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    """认证请求头"""
    return {"Authorization": f"Bearer {admin_token}"}
