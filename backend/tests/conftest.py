"""LTMP 后端 — 共享 fixtures"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.database import init_db, SessionLocal, engine, Base
from app.utils.auth import get_password_hash
from app.models.auth import User


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
    """清空所有表数据，重建表 + 默认管理员"""
    # 先初始化所有表
    init_db()
    # 清空所有表（保留表结构）
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
        # 创建默认管理员
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            db.add(User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                display_name="测试管理员",
                role="admin",
            ))
            db.commit()
    finally:
        db.close()
    yield
    # 不清理 — 保留数据供用户查看


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
