"""RBAC 权限体系 — 用户/角色/权限 CRUD + 权限隔离测试"""

import pytest


class TestPermissions:
    """权限查询"""

    def test_list_permissions(self, client, auth_headers):
        resp = client.get("/api/auth/permissions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0  # 至少有一个模块组
        # 检查是否包含预期模块
        modules = [g["module"] for g in data]
        assert "采购管理" in modules
        assert "销售管理" in modules
        assert "系统管理" in modules
        # 检查权限总数
        all_codes = set()
        for g in data:
            for p in g["permissions"]:
                all_codes.add(p["code"])
        assert len(all_codes) == 16  # 预置 16 个权限

    def test_my_permissions(self, client, auth_headers):
        resp = client.get("/api/auth/me/permissions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "permissions" in data
        assert "role_code" in data
        assert data["role_code"] == "admin"
        assert "system:admin" in data["permissions"]


class TestUserCRUD:
    """用户管理 CRUD"""

    USERNAME = "rbac_test_user"
    PASSWORD = "test_pass_123"

    def test_list_users(self, client, auth_headers):
        resp = client.get("/api/auth/users", headers=auth_headers)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert any(u["username"] == "admin" for u in users)

    def test_create_user(self, client, auth_headers):
        # 获取操作员角色ID
        roles_resp = client.get("/api/auth/roles", headers=auth_headers)
        assert roles_resp.status_code == 200
        op_role = [r for r in roles_resp.json() if r["code"] == "operator"][0]

        resp = client.post("/api/auth/users", json={
            "username": self.USERNAME,
            "password": self.PASSWORD,
            "display_name": "RBAC测试用户",
            "role_id": op_role["id"],
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == self.USERNAME
        assert data["role_id"] == op_role["id"]
        assert data["role_code"] == "operator"
        assert data["is_active"] == 1

    def test_get_user(self, client, auth_headers):
        # 获取刚创建的用户
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME]
        assert len(target) == 1
        resp = client.get(f"/api/auth/users/{target[0]['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == self.USERNAME

    def test_update_user_role(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]

        # 获取只读角色ID
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        ro_role = [r for r in roles if r["code"] == "readonly"][0]

        resp = client.put(f"/api/auth/users/{target['id']}", json={
            "role_id": ro_role["id"],
            "display_name": "已切换只读",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["role_code"] == "readonly"

    def test_update_user_password(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]

        resp = client.put(f"/api/auth/users/{target['id']}", json={
            "password": "newpass456",
        }, headers=auth_headers)
        assert resp.status_code == 200

        # 验证新密码登录
        login_resp = client.post("/api/auth/login", json={
            "username": self.USERNAME,
            "password": "newpass456",
        })
        assert login_resp.status_code == 200

    def test_toggle_user_active(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]

        # 停用
        resp = client.put(f"/api/auth/users/{target['id']}", json={"is_active": 0},
                          headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] == 0

        # 停用后无法登录
        login_resp = client.post("/api/auth/login", json={
            "username": self.USERNAME,
            "password": "newpass456",
        })
        assert login_resp.status_code == 403

        # 恢复
        resp = client.put(f"/api/auth/users/{target['id']}", json={"is_active": 1},
                          headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] == 1

    def test_delete_user(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]
        resp = client.delete(f"/api/auth/users/{target['id']}", headers=auth_headers)
        assert resp.status_code == 200

        # 验证已删除
        users_after = client.get("/api/auth/users", headers=auth_headers).json()
        assert not any(u["username"] == self.USERNAME for u in users_after)

    def test_cannot_delete_self(self, client, auth_headers):
        me = client.get("/api/auth/me", headers=auth_headers).json()
        resp = client.delete(f"/api/auth/users/{me['id']}", headers=auth_headers)
        assert resp.status_code == 400


class TestRoleCRUD:
    """角色管理 CRUD"""

    def test_list_roles(self, client, auth_headers):
        resp = client.get("/api/auth/roles", headers=auth_headers)
        assert resp.status_code == 200
        roles = resp.json()
        assert len(roles) == 4  # 4 个预置角色
        codes = {r["code"] for r in roles}
        assert codes == {"admin", "manager", "operator", "readonly"}

    def test_admin_role_properties(self, client, auth_headers):
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        admin = [r for r in roles if r["code"] == "admin"][0]
        assert admin["is_system"] == 1
        assert admin["user_count"] >= 1  # admin 用户
        assert len(admin["permission_codes"]) == 16  # 全部权限

    def test_create_custom_role(self, client, auth_headers):
        resp = client.post("/api/auth/roles", json={
            "name": "自定义测试角色",
            "code": "test_custom",
            "description": "仅供测试",
            "permission_codes": ["dashboard:read", "foundation:read", "inventory:read"],
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "test_custom"
        assert data["is_system"] == 0
        assert len(data["permission_codes"]) == 3
        assert data["user_count"] == 0

    def test_update_role(self, client, auth_headers):
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        target = [r for r in roles if r["code"] == "test_custom"][0]

        resp = client.put(f"/api/auth/roles/{target['id']}", json={
            "name": "更新角色名",
            "permission_codes": ["dashboard:read", "foundation:read",
                                 "foundation:write", "inventory:read"],
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新角色名"
        assert len(resp.json()["permission_codes"]) == 4

    def test_delete_custom_role(self, client, auth_headers):
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        target = [r for r in roles if r["code"] == "test_custom"][0]
        resp = client.delete(f"/api/auth/roles/{target['id']}", headers=auth_headers)
        assert resp.status_code == 200

    def test_cannot_delete_system_role(self, client, auth_headers):
        resp = client.delete("/api/auth/roles/1", headers=auth_headers)
        assert resp.status_code == 400
        assert "内置" in resp.json()["detail"]


class TestPermissionIsolation:
    """权限隔离测试"""

    @pytest.fixture(scope="class")
    def operator_token(self, client, admin_token):
        """创建操作员并返回其 token"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        roles = client.get("/api/auth/roles", headers=headers).json()
        op_role = [r for r in roles if r["code"] == "operator"][0]

        client.post("/api/auth/users", json={
            "username": "iso_operator", "password": "test1234",
            "display_name": "隔离测试操作员", "role_id": op_role["id"],
        }, headers=headers)

        resp = client.post("/api/auth/login", json={
            "username": "iso_operator", "password": "test1234",
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    @pytest.fixture(scope="class")
    def readonly_token(self, client, admin_token):
        """创建只读用户并返回其 token"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        roles = client.get("/api/auth/roles", headers=headers).json()
        ro_role = [r for r in roles if r["code"] == "readonly"][0]

        client.post("/api/auth/users", json={
            "username": "iso_readonly", "password": "test1234",
            "display_name": "隔离测试只读", "role_id": ro_role["id"],
        }, headers=headers)

        resp = client.post("/api/auth/login", json={
            "username": "iso_readonly", "password": "test1234",
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    def test_operator_cannot_access_admin_api(self, client, operator_token):
        """操作员不能创建用户"""
        headers = {"Authorization": f"Bearer {operator_token}"}
        resp = client.post("/api/auth/users", json={
            "username": "should_fail", "password": "x",
        }, headers=headers)
        assert resp.status_code == 403

    def test_readonly_has_only_read_permissions(self, client, readonly_token):
        """只读角色的权限列表应仅有 read 权限"""
        headers = {"Authorization": f"Bearer {readonly_token}"}
        resp = client.get("/api/auth/me/permissions", headers=headers)
        assert resp.status_code == 200
        perms = resp.json()["permissions"]
        for p in perms:
            assert p.endswith(":read") or p == "dashboard:read"
        assert "dashboard:read" in perms
        assert "system:admin" not in perms

    def test_readonly_cannot_create_data(self, client, readonly_token):
        """只读用户不能创建数据"""
        headers = {"Authorization": f"Bearer {readonly_token}"}
        resp = client.post("/api/foundation/materials", json={
            "name": "should_fail", "spec": "X", "unit": "个",
        }, headers=headers)

    def test_operator_has_write_but_no_approve(self, client, operator_token):
        """操作员有 write 权限但没有 approve 权限"""
        headers = {"Authorization": f"Bearer {operator_token}"}
        resp = client.get("/api/auth/me/permissions", headers=headers)
        perms = resp.json()["permissions"]
        # 有 write
        assert "foundation:write" in perms
        assert "purchase:write" in perms
        # 无 approve
        assert "purchase:approve" not in perms
        assert "sales:approve" not in perms
        # 无系统管理
        assert "system:admin" not in perms
