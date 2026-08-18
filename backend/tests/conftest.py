"""MTS 后端 — 共享 fixtures

测试数据规范（详见 README「测试数据规范」）：
- 种子数据单一数据源 = app/main.py 的 _seed_rbac/_seed_currencies（与生产完全一致），
  禁止在 conftest 里另写权限/角色定义（历史教训：双份定义漂移导致 test_rbac 断言反复失效）
- 基础档案统一由 tests/test_data.py 的 build_foundation 构建（foundation fixture），
  禁止各测试文件自建档案
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.database import init_db, SessionLocal, engine, Base


def _seed_rbac_test(db):
    """[已废弃] 历史自定义种子（双份定义漂移根因）— 已改为复用 app/main.py 的 _seed_rbac"""
    from app.main import _seed_rbac
    _seed_rbac(db)


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
    from app.main import _seed_rbac, _seed_currencies
    db = SessionLocal()
    try:
        _seed_currencies(db)
        _seed_rbac(db)
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


@pytest.fixture(scope="session")
def foundation(client, admin_token):
    """共享基础档案（全测试唯一构建器，见 tests/test_data.py 规范）

    所有测试复用同一套真实档案（2仓/2供应商/2客户/4物料/2产品/4工序+BOM+工艺路线），
    禁止在各自测试文件里另建档案。
    """
    from tests.test_data import build_foundation
    return build_foundation(client, {"Authorization": f"Bearer {admin_token}"})


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    """认证请求头"""
    return {"Authorization": f"Bearer {admin_token}"}
