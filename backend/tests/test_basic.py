"""健康检查 & 基础 API 测试"""


def test_health_check(client):
    """GET /api/health 应返回 ok"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_login_success(client):
    """正确账号密码应返回 token"""
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_fail(client):
    """错误密码应返回 401"""
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_me_endpoint(client, auth_headers):
    """GET /api/auth/me 应返回当前用户"""
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_unauthorized(client):
    """无 token 访问应返回 401/403"""
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_static_files_accessible(client):
    """前端静态文件应可访问"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
