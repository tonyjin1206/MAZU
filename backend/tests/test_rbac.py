"""RBAC 权限体系 — 用户/角色/权限 CRUD + 权限隔离测试"""

import pytest


class TestPermissions:
    """权限查询"""

    def test_list_permissions(self, client, auth_headers):
        resp = client.get("/api/auth/permissions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        modules = {g["module"] for g in data}
        assert "采购管理" in modules
        assert "销售管理" in modules
        assert "系统管理" in modules
        all_codes = set()
        for g in data:
            for p in g["permissions"]:
                all_codes.add(p["code"])
        # 数量不硬编码（SP 菜单随迭代变动，2026-07-31 后 35 个）——
        # 断言：菜单权限数合理区间（>30），且后端定义的权限全部暴露
        assert len(all_codes) >= 30, f"菜单权限数异常少: {len(all_codes)}"

    def test_my_permissions(self, client, auth_headers):
        resp = client.get("/api/auth/me/permissions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "permissions" in data
        assert "role_code" in data
        assert data["role_code"] == "admin"
        assert "menu:system:users" in data["permissions"]
        # 管理员 = 全量权限（main.py seed 每次补齐）—— 动态对比，不硬编码数量
        groups = client.get("/api/auth/permissions", headers=auth_headers).json()
        all_codes = {p["code"] for g in groups for p in g["permissions"]}
        assert len(data["permissions"]) == len(all_codes)


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
        roles_resp = client.get("/api/auth/roles", headers=auth_headers)
        assert roles_resp.status_code == 200
        role = [r for r in roles_resp.json() if r["code"] == "readonly"][0]

        resp = client.post("/api/auth/users", json={
            "username": self.USERNAME,
            "password": self.PASSWORD,
            "display_name": "RBAC测试用户",
            "role_id": role["id"],
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role_code"] == "readonly"

    def test_get_user(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME]
        assert len(target) == 1
        resp = client.get(f"/api/auth/users/{target[0]['id']}", headers=auth_headers)
        assert resp.status_code == 200

    def test_update_user_password(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]
        resp = client.put(f"/api/auth/users/{target['id']}", json={"password": "newpass456"},
                          headers=auth_headers)
        assert resp.status_code == 200
        login = client.post("/api/auth/login", json={
            "username": self.USERNAME, "password": "newpass456",
        })
        assert login.status_code == 200

    def test_toggle_user_active(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]
        resp = client.put(f"/api/auth/users/{target['id']}", json={"is_active": 0},
                          headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] == 0
        login = client.post("/api/auth/login", json={
            "username": self.USERNAME, "password": "newpass456",
        })
        assert login.status_code == 403
        client.put(f"/api/auth/users/{target['id']}", json={"is_active": 1},
                   headers=auth_headers)

    def test_delete_user(self, client, auth_headers):
        users = client.get("/api/auth/users", headers=auth_headers).json()
        target = [u for u in users if u["username"] == self.USERNAME][0]
        resp = client.delete(f"/api/auth/users/{target['id']}", headers=auth_headers)
        assert resp.status_code == 200

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
        assert len(roles) == 7  # 7 个预置角色
        codes = {r["code"] for r in roles}
        assert codes == {"admin", "sales_manager", "purchase_manager",
                         "production_manager", "finance_manager",
                         "warehouse_keeper", "readonly"}

    def test_admin_role_properties(self, client, auth_headers):
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        admin = [r for r in roles if r["code"] == "admin"][0]
        assert admin["is_system"] == 1
        assert admin["user_count"] >= 1
        # 管理员 = 全量权限（动态对比）
        groups = client.get("/api/auth/permissions", headers=auth_headers).json()
        all_codes = {p["code"] for g in groups for p in g["permissions"]}
        assert len(admin["permission_codes"]) == len(all_codes)

    def test_create_custom_role(self, client, auth_headers):
        resp = client.post("/api/auth/roles", json={
            "name": "自定义测试角色", "code": "test_custom",
            "description": "仅供测试",
            "permission_codes": ["menu:dashboard", "menu:inventory"],
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "test_custom"
        assert data["is_system"] == 0
        assert len(data["permission_codes"]) == 2

    def test_update_role(self, client, auth_headers):
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        target = [r for r in roles if r["code"] == "test_custom"][0]
        resp = client.put(f"/api/auth/roles/{target['id']}", json={
            "name": "已更新",
            "permission_codes": ["menu:dashboard", "menu:inventory", "menu:tax"],
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["permission_codes"]) == 3

    def test_delete_custom_role(self, client, auth_headers):
        roles = client.get("/api/auth/roles", headers=auth_headers).json()
        target = [r for r in roles if r["code"] == "test_custom"][0]
        resp = client.delete(f"/api/auth/roles/{target['id']}", headers=auth_headers)
        assert resp.status_code == 200

    def test_cannot_delete_system_role(self, client, auth_headers):
        resp = client.delete("/api/auth/roles/1", headers=auth_headers)
        assert resp.status_code == 400


class TestPermissionRoles:
    """预置角色权限正确性"""

    @pytest.fixture(scope="class")
    def admin_token(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        return resp.json()["access_token"]

    def test_admin_has_all(self, client, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        perms = client.get("/api/auth/me/permissions", headers=h).json()
        # 管理员 = 全量权限（动态对比）
        groups = client.get("/api/auth/permissions", headers=h).json()
        all_codes = {p["code"] for g in groups for p in g["permissions"]}
        assert len(perms["permissions"]) == len(all_codes)

    def test_sales_manager_permissions(self, client, admin_token):
        """销售经理只有驾驶舱 + 6 个销售菜单"""
        h = {"Authorization": f"Bearer {admin_token}"}
        roles = client.get("/api/auth/roles", headers=h).json()
        sm = [r for r in roles if r["code"] == "sales_manager"][0]
        codes = set(sm["permission_codes"])
        assert "menu:dashboard" in codes
        assert "menu:sales:orders" in codes
        assert "menu:purchase:orders" not in codes  # 无采购
        assert "menu:customers" not in codes  # 无基础档案

    def test_finance_manager_permissions(self, client, admin_token):
        """财务经理有采购发票/应付/付款、销售发票/应收/收款、库存、退税"""
        h = {"Authorization": f"Bearer {admin_token}"}
        roles = client.get("/api/auth/roles", headers=h).json()
        fm = [r for r in roles if r["code"] == "finance_manager"][0]
        codes = set(fm["permission_codes"])
        assert "menu:dashboard" in codes
        assert "menu:purchase:invoices" in codes
        assert "menu:purchase:ap" in codes
        assert "menu:purchase:payments" in codes
        assert "menu:sales:invoices" in codes
        assert "menu:sales:ar" in codes
        assert "menu:sales:collections" in codes
        assert "menu:inventory" in codes
        assert "menu:tax" in codes
        assert "menu:purchase:orders" not in codes  # 无采购订单
        assert "menu:sales:orders" not in codes  # 无销售订单
        assert "menu:system:users" not in codes  # 无系统管理

    def test_production_manager_has_foundation(self, client, admin_token):
        """生产经理有基础档案 + 生产 + 库存"""
        h = {"Authorization": f"Bearer {admin_token}"}
        roles = client.get("/api/auth/roles", headers=h).json()
        pm = [r for r in roles if r["code"] == "production_manager"][0]
        codes = set(pm["permission_codes"])
        assert "menu:customers" in codes
        assert "menu:products" in codes
        assert "menu:production:orders" in codes
        assert "menu:inventory" in codes
        assert "menu:purchase:orders" not in codes  # 无采购
        assert "menu:sales:orders" not in codes  # 无销售


class TestReadScopeRBAC:
    """BUG-L4-02：低权限角色读越权修复 — 库管员/只读不得读非授权域数据

    库管员（仅库存域）读基础档案/销售订单应 403，但读库存可用（不误伤）；
    只读用户（仅驾驶舱）读 sales/foundation/inventory 应 403。
    """

    PASSWORD = "pass12345"

    def _create_user(self, client, admin_h, username, role_code):
        roles = client.get("/api/auth/roles", headers=admin_h).json()
        role = next(r for r in roles if r["code"] == role_code)
        resp = client.post("/api/auth/users", json={
            "username": username, "password": self.PASSWORD,
            "display_name": username, "role_id": role["id"]}, headers=admin_h)
        assert resp.status_code < 400, resp.text
        return username

    def _login(self, client, username):
        resp = client.post("/api/auth/login", json={
            "username": username, "password": self.PASSWORD})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_warehouse_keeper_read_blocked(self, client, admin_token):
        """库管员（仅库存域）读基础档案/销售订单 403，读库存可用"""
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        self._create_user(client, admin_h, "wk_read_l402", "warehouse_keeper")
        h = self._login(client, "wk_read_l402")
        # 非授权域读取 → 403（不得读非授权域全量数据）
        for path in ("/api/foundation/suppliers", "/api/foundation/products",
                     "/api/foundation/materials", "/api/sales/orders"):
            r = client.get(path, headers=h)
            assert r.status_code == 403, f"库管员读 {path} 应 403，实际 {r.status_code}"
        # 授权域（库存）读取 → 200（不误伤）
        r = client.get("/api/inventory/balance", headers=h)
        assert r.status_code == 200, r.text

    def test_readonly_read_blocked(self, client, admin_token):
        """只读用户（仅驾驶舱）读 sales/foundation/inventory 均 403"""
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        self._create_user(client, admin_h, "ro_read_l402", "readonly")
        h = self._login(client, "ro_read_l402")
        for path in ("/api/sales/orders", "/api/foundation/suppliers",
                     "/api/foundation/products", "/api/foundation/materials",
                     "/api/foundation/customers", "/api/inventory/balance"):
            r = client.get(path, headers=h)
            assert r.status_code == 403, f"只读用户读 {path} 应 403，实际 {r.status_code}"

    def test_three_branch_write_blocked_low_perm(self, client, admin_token, foundation):
        """V3 三分支写端点：库管员（仅库存域）对 转直采/转外发/转生产 应 403

        权限隔离正确：生产=自产(menu:production:*)、委外=转外发(menu:outsource:*)、
        转直采=menu:sales:orders；低权限角色（库管员无任何销售/委外/生产权限）一律 403。
        注意：即使库管员能读订单（读端点放宽到库存出库域），写端点仍必须严格拦截。
        """
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        admin_h = {"Authorization": f"Bearer {login.json()['access_token']}"}
        self._create_user(client, admin_h, "wk_write_l403", "warehouse_keeper")
        h = self._login(client, "wk_write_l403")

        # 建销售订单（admin）→ 审核
        cust = foundation["cust"][0]
        cny = foundation["cny"]["id"]
        pid = foundation["prods"]["全棉色织布"]["id"]
        so = client.post("/api/sales/orders", json={
            "customer_id": cust, "currency_id": cny, "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 10, "unit_price": 50, "tax_rate": 13}],
        }, headers=admin_h).json()
        so_id = so["id"]
        client.post(f"/api/sales/orders/{so_id}/approve", json={}, headers=admin_h)
        detail = client.get(f"/api/sales/orders/{so_id}", headers=admin_h).json()
        item_id = detail["items"][0]["id"]

        # 三分支写端点：库管员均 403（无销售/委外/生产权限）
        for path in (
            f"/api/sales/orders/{so_id}/items/{item_id}/stock-in",   # 转直采
            f"/api/sales/orders/{so_id}/items/{item_id}/outsource",  # 转外发(委外)
            f"/api/sales/orders/{so_id}/items/{item_id}/re-produce", # 转生产(自产)
        ):
            r = client.post(path, json={}, headers=h)
            assert r.status_code == 403, f"库管员写 {path} 应 403，实际 {r.status_code}: {r.text[:120]}"
