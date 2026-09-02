"""BUG-L4-01/02 扩展测试：purchase/production/outsource/stock_in/tax_refund 权限隔离

背景：v2.8.0 BUG-L4-01/02 修复只覆盖 sales/foundation/inventory 三个模块；
采购/生产/委外/待入库/退税模块的写端点此前仅校验登录（get_current_user），
任何低权限角色（只读/库管员）均可通过 API 增删改业务单据。
本测试验证上述模块的读写端点已统一补权限：
- 只读用户（仅 dashboard）→ 所有业务模块读写一律 403
- 库管员（仅库存域）→ 采购/委外/退税写 403；库存域读 200
- 合法角色（采购经理/生产经理/财务经理）→ 各自业务域操作 200

注（2026-09 生产管理下线）：生产写端点已删除无法再测，只读读用例改用
存活的批次追溯端点 /api/production/inventory/batch（perm=menu:production:batch）。
"""

import pytest


def _create_user(client, admin_h, username, role_code, password="pass_123456"):
    """建低权限用户并返回请求头"""
    roles = client.get("/api/auth/roles", headers=admin_h).json()
    role = next(r for r in roles if r["code"] == role_code)
    r = client.post("/api/auth/users", json={
        "username": username, "password": password,
        "display_name": username, "role_id": role["id"],
    }, headers=admin_h)
    assert r.status_code < 400, r.text
    login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


class TestLowPrivilegeBlocked:
    """只读 / 库管员对业务模块读写必须 403（本域外）"""

    @pytest.fixture(scope="class")
    def readonly_h(self, client, admin_token):
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        return _create_user(client, admin_h, "ro_l4_ext", "readonly")

    @pytest.fixture(scope="class")
    def keeper_h(self, client, admin_token):
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        return _create_user(client, admin_h, "wk_l4_ext", "warehouse_keeper")

    def test_readonly_write_blocked_all_modules(self, client, readonly_h):
        """只读用户写采购/委外/待入库/退税 → 403（生产写端点已随生产管理下线）"""
        blocked = [
            ("POST", "/api/purchase/orders", {"supplier_id": 1, "items": []}),
            ("POST", "/api/purchase/invoices", {"order_id": 1}),
            ("POST", "/api/purchase/payments", {"supplier_id": 1, "amount": 100}),
            ("POST", "/api/outsource/orders/1/approve", {}),
            ("POST", "/api/outsource/claims", {}),
            ("POST", "/api/stock-in/1/receive", {"quantity": 1}),
            ("POST", "/api/tax-refund/declarations", {}),
            ("POST", "/api/tax-refund/input-invoices", {}),
        ]
        for method, path, payload in blocked:
            r = getattr(client, method.lower())(path, json=payload, headers=readonly_h)
            assert r.status_code == 403, (
                f"只读用户 {method} {path} 应 403，实际 {r.status_code}: {r.text[:150]}")

    def test_readonly_read_blocked_all_modules(self, client, readonly_h):
        """只读用户读采购/生产(批次追溯)/委外/待入库/退税 → 403"""
        blocked = [
            ("GET", "/api/purchase/orders"),
            ("GET", "/api/purchase/ap"),
            ("GET", "/api/production/inventory/batch"),
            ("GET", "/api/outsource/orders"),
            ("GET", "/api/stock-in"),
            ("GET", "/api/tax-refund/declarations"),
            ("GET", "/api/tax-refund/input-invoices"),
        ]
        for method, path in blocked:
            r = getattr(client, method.lower())(path, headers=readonly_h)
            assert r.status_code == 403, (
                f"只读用户 {method} {path} 应 403，实际 {r.status_code}: {r.text[:150]}")

    def test_warehouse_keeper_write_blocked(self, client, keeper_h):
        """库管员（仅库存域）写采购/委外/退税 → 403（生产写端点已随生产管理下线）"""
        blocked = [
            ("POST", "/api/purchase/orders", {"supplier_id": 1, "items": []}),
            ("POST", "/api/outsource/orders/1/approve", {}),
            ("POST", "/api/tax-refund/declarations", {}),
        ]
        for method, path, payload in blocked:
            r = getattr(client, method.lower())(path, json=payload, headers=keeper_h)
            assert r.status_code == 403, (
                f"库管员 {method} {path} 应 403，实际 {r.status_code}: {r.text[:150]}")

    def test_warehouse_keeper_inventory_read_ok(self, client, keeper_h):
        """库管员读库存域 → 200（不误伤）"""
        r = client.get("/api/inventory/balance", headers=keeper_h)
        assert r.status_code == 200, f"库管员读库存应 200，实际 {r.status_code}: {r.text[:150]}"


class TestLegitRolesOk:
    """合法角色业务域操作 200（权限域不过严）"""

    def test_purchase_manager_create_order(self, client, admin_token, foundation):
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        pm_h = _create_user(client, admin_h, "pm_l4_ext", "purchase_manager")
        sup_id = foundation["sup"]
        mat_id = foundation["mats"]["精梳棉纱32S"]
        r = client.post("/api/purchase/orders", json={
            "supplier_id": sup_id, "currency_id": foundation["cny"]["id"],
            "items": [{"material_id": mat_id, "quantity": 10, "unit_price": 32, "tax_rate": 13}],
        }, headers=pm_h)
        assert r.status_code == 200, f"采购经理建采购单应 200，实际 {r.status_code}: {r.text[:200]}"

    def test_purchase_manager_requisition_read(self, client, admin_token):
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        pm_h = _create_user(client, admin_h, "pm_l4_ext2", "purchase_manager")
        r = client.get("/api/purchase/requisitions", headers=pm_h)
        assert r.status_code == 200, f"采购经理读采购需求应 200，实际 {r.status_code}: {r.text[:150]}"

    def test_finance_manager_tax_refund(self, client, admin_token):
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        fm_h = _create_user(client, admin_h, "fm_l4_ext", "finance_manager")
        r = client.get("/api/tax-refund/input-invoices", headers=fm_h)
        assert r.status_code == 200, f"财务经理读进项发票应 200，实际 {r.status_code}: {r.text[:150]}"

    def test_sales_manager_read_orders(self, client, admin_token, foundation):
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        sm_h = _create_user(client, admin_h, "sm_l4_ext", "sales_manager")
        # 建一个销售订单（admin）后销售经理可读
        cust = foundation["cust"][0]
        pid = foundation["prods"]["全棉色织布"]["id"]
        so = client.post("/api/sales/orders", json={
            "customer_id": cust, "currency_id": foundation["cny"]["id"],
            "items": [{"product_id": pid, "quantity": 5, "unit_price": 18, "tax_rate": 13}],
        }, headers=admin_h).json()
        r = client.get(f"/api/sales/orders/{so['id']}", headers=sm_h)
        assert r.status_code == 200, f"销售经理读订单应 200，实际 {r.status_code}: {r.text[:150]}"
