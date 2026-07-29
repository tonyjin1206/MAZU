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
        {"code": "menu:dashboard", "name": "驾驶舱", "module": "工作台", "description": ""},
        {"code": "menu:customers", "name": "客户管理", "module": "基础档案", "description": ""},
        {"code": "menu:suppliers", "name": "供应商管理", "module": "基础档案", "description": ""},
        {"code": "menu:materials", "name": "原辅材料", "module": "基础档案", "description": ""},
        {"code": "menu:products", "name": "产品档案", "module": "基础档案", "description": ""},
        {"code": "menu:bom", "name": "BOM管理", "module": "基础档案", "description": ""},
        {"code": "menu:processes", "name": "工序管理", "module": "基础档案", "description": ""},
        {"code": "menu:hs-codes", "name": "HS编码", "module": "基础档案", "description": ""},
        {"code": "menu:purchase:orders", "name": "采购订单", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:receipts", "name": "采购入库", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:invoices", "name": "采购发票", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:ap", "name": "应付账款", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:payments", "name": "付款管理", "module": "采购管理", "description": ""},
        {"code": "menu:sales:orders", "name": "销售订单", "module": "销售管理", "description": ""},
        {"code": "menu:sales:deliveries", "name": "销售发货", "module": "销售管理", "description": ""},
        {"code": "menu:sales:invoices", "name": "销售发票", "module": "销售管理", "description": ""},
        {"code": "menu:sales:customs", "name": "报关管理", "module": "销售管理", "description": ""},
        {"code": "menu:sales:ar", "name": "应收账款", "module": "销售管理", "description": ""},
        {"code": "menu:sales:collections", "name": "收款管理", "module": "销售管理", "description": ""},
        {"code": "menu:production:orders", "name": "生产订单", "module": "生产管理", "description": ""},
        {"code": "menu:production:workspace", "name": "生产工作台", "module": "生产管理", "description": ""},
        {"code": "menu:production:invoices", "name": "加工费发票", "module": "生产管理", "description": ""},
        {"code": "menu:production:batch", "name": "批次追溯", "module": "生产管理", "description": ""},
        {"code": "menu:inventory", "name": "库存收发存", "module": "库存管理", "description": ""},
        {"code": "menu:tax", "name": "退税申报", "module": "退税管理", "description": ""},
        {"code": "menu:system:users", "name": "用户管理", "module": "系统管理", "description": ""},
        {"code": "menu:system:roles", "name": "角色管理", "module": "系统管理", "description": ""},
    ]
    for pd in permission_defs:
        if not db.query(Permission).filter(Permission.code == pd["code"]).first():
            db.add(Permission(**pd))

    all_codes = [p["code"] for p in permission_defs]
    foundation = [c for c in all_codes if c.startswith("menu:customers") or c.startswith("menu:suppliers")
                  or c.startswith("menu:materials") or c.startswith("menu:products")
                  or c.startswith("menu:bom") or c.startswith("menu:processes")
                  or c.startswith("menu:hs-codes")]
    purchase_all = [c for c in all_codes if c.startswith("menu:purchase:")]
    purchase_finance = [c for c in purchase_all if c.endswith(("invoices", "ap", "payments"))]
    sales_all = [c for c in all_codes if c.startswith("menu:sales:")]
    sales_finance = [c for c in sales_all if c.endswith(("invoices", "ar", "collections"))]
    production = [c for c in all_codes if c.startswith("menu:production:")]
    inventory = ["menu:inventory", "menu:production:batch"]
    tax = ["menu:tax"]
    dashboard = ["menu:dashboard"]

    role_defs = [
        ("管理员", "admin", all_codes),
        ("销售经理", "sales_manager", dashboard + sales_all),
        ("采购经理", "purchase_manager", dashboard + purchase_all),
        ("生产经理", "production_manager", dashboard + foundation + production + inventory),
        ("财务经理", "finance_manager", dashboard + purchase_finance + sales_finance + inventory + tax),
        ("库管员", "warehouse_keeper", dashboard + inventory),
        ("只读", "readonly", dashboard),
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
