"""LTMP 后端 — 共享 fixtures"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.database import init_db, SessionLocal
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
    """初始化测试数据库表 + 默认管理员"""
    init_db()
    db = SessionLocal()
    try:
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
    # 测试完成后清理测试数据库
    import shutil
    from pathlib import Path
    from app.config import settings
    db_path = settings.DATA_DIR / "erp.db"
    if db_path.exists():
        db_path.unlink()
    for suffix in ["-wal", "-shm"]:
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()


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
