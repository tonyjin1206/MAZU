"""
MTS 后端 — 共享 fixtures

⚠️ 测试库隔离（必须先于任何 app 导入执行）：
config.py 通过 ERP_DATA_DIR 环境变量决定数据目录；不设置 = backend/data/（开发/生产库）。
本文件在导入 app 前设置 ERP_DATA_DIR 指向独立临时目录，确保：
  - pytest 的 setup_db 清空/重建的是【测试库】，绝不触碰开发库 backend/data/erp.db
  - 开发库数据（含 AI 配置 sys_bot_config、手工录入档案）跑完测试保持完全不变
  - 后端 uvicorn 开着时跑测试也不会再出现 ASGI 异常（表被清/锁冲突）

测试数据规范（详见 README「测试数据规范」）：
- 种子数据单一数据源 = app/main.py 的 _seed_rbac/_seed_currencies（与生产完全一致），
  禁止在 conftest 里另写权限/角色定义（历史教训：双份定义漂移导致 test_rbac 断言反复失效）
- 基础档案统一由 tests/test_data.py 的 build_foundation 构建（foundation fixture），
  禁止各测试文件自建档案
"""

import os
import tempfile
from pathlib import Path

# ===== 测试库隔离：必须在 import app.* 之前设置 =====
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="mts_test_data_"))
os.environ["ERP_DATA_DIR"] = str(_TEST_DATA_DIR)

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
    """清空所有表数据，重建表 + RBAC 种子数据 + 默认管理员

    注意：操作的是【测试库】（ERP_DATA_DIR 已隔离），不会影响开发库 backend/data/erp.db
    """
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
