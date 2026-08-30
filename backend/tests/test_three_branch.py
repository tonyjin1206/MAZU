"""销售三分支状态机（v2.8.0 V4）— 转直采 / 转外发(委外) / 转生产(自产) 各自独立、互斥

产品逻辑（V4 固化的互斥铁律）：
- 销售订单审核后，明细行 production_status =「未生产」（不再自动生成 MO，SP 三分支）。
- 三条独立路线，同一明细行只能选其一：
  · 转直采  → stock-in    → production_status「已通知入库」→ 进「销售订单转采购」
  · 转外发  → outsource   → production_status「已通知外发」→ 进「委外管理→销售订单转委外」
  · 转生产  → re-produce  → production_status「生产中」（自产占位，生成纯自产 MO）
- 互斥：任一分支执行后，同一明细行其余两条路线必须被拒（400）。
  （V4 修复：re-produce 原未占位 production_status，导致转生产后可再转直采漏过；
   现 re-produce 生成 MO 后置「生产中」，与派产/完工/删MO 的流转一致。）

数据规范：档案全部来自共享 foundation fixture（tests/test_data.py），不自建档案。
"""

import pytest

from app.database import SessionLocal
from app.models.system_config import Notification


def _mk_so_item(client, h, f, qty=10):
    """建销售订单 → 审核，返回 (so_id, item_id)"""
    cust = f["cust"][0]
    cny = f["cny"]["id"]
    pid = f["prods"]["全棉色织布"]["id"]
    so = client.post("/api/sales/orders", json={
        "customer_id": cust, "currency_id": cny, "payment_terms": "TT",
        "items": [{"product_id": pid, "quantity": qty, "unit_price": 50, "tax_rate": 13}],
    }, headers=h).json()
    so_id = so["id"]
    assert client.post(f"/api/sales/orders/{so_id}/approve", json={}, headers=h).status_code == 200
    detail = client.get(f"/api/sales/orders/{so_id}", headers=h).json()
    return so_id, detail["items"][0]["id"]


def _status(client, h, so_id, item_id):
    d = client.get(f"/api/sales/orders/{so_id}", headers=h).json()
    it = next(i for i in d["items"] if i["id"] == item_id)
    return it["production_status"]


class TestThreeBranchMutualExclusion:
    """三分支互斥：同一明细行只能走一条路线，其余必须 400"""

    def test_three_branch_each_used_once(self, client, auth_headers, foundation):
        """三条路线各自独立可执行（各自用一张新订单）"""
        h = auth_headers
        # 转直采
        so1, i1 = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so1}/items/{i1}/stock-in",
                           json={}, headers=h).status_code == 200
        assert _status(client, h, so1, i1) == "已通知入库"

        # 转外发(委外)
        so2, i2 = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so2}/items/{i2}/outsource",
                           json={}, headers=h).status_code == 200
        assert _status(client, h, so2, i2) == "已通知外发"

        # 转生产(自产)
        so3, i3 = _mk_so_item(client, h, foundation)
        r = client.post(f"/api/sales/orders/{so3}/items/{i3}/re-produce", json={}, headers=h)
        assert r.status_code == 200
        assert _status(client, h, so3, i3) == "生产中"
        assert "order_no" in r.json()

    def test_produce_then_other_branches_blocked(self, client, auth_headers, foundation):
        """转生产后再转直采/转外发 → 400（V4 修复的互斥：re-produce 后占位「生产中」）"""
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/re-produce",
                           json={}, headers=h).status_code == 200
        # 转直采应被拒（修复前漏过 200）
        r = client.post(f"/api/sales/orders/{so_id}/items/{item_id}/stock-in", json={}, headers=h)
        assert r.status_code == 400, f"转生产后转直采应 400，实际 {r.status_code}: {r.text[:120]}"
        # 转外发应被拒
        r = client.post(f"/api/sales/orders/{so_id}/items/{item_id}/outsource", json={}, headers=h)
        assert r.status_code == 400, f"转生产后转外发应 400，实际 {r.status_code}: {r.text[:120]}"

    def test_stockin_then_other_branches_blocked(self, client, auth_headers, foundation):
        """转直采后再转生产/转外发 → 400"""
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/stock-in",
                           json={}, headers=h).status_code == 200
        for path in ("re-produce", "outsource"):
            r = client.post(f"/api/sales/orders/{so_id}/items/{item_id}/{path}", json={}, headers=h)
            assert r.status_code == 400, f"转直采后再 {path} 应 400，实际 {r.status_code}"

    def test_outsource_then_other_branches_blocked(self, client, auth_headers, foundation):
        """转外发后再转直采/转生产 → 400"""
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/outsource",
                           json={}, headers=h).status_code == 200
        for path in ("re-produce", "stock-in"):
            r = client.post(f"/api/sales/orders/{so_id}/items/{item_id}/{path}", json={}, headers=h)
            assert r.status_code == 400, f"转外发后再 {path} 应 400，实际 {r.status_code}"

    def test_unapproved_order_branch_blocked(self, client, auth_headers, foundation):
        """订单未审核：三条路线均 400"""
        h = auth_headers
        cust = foundation["cust"][0]
        cny = foundation["cny"]["id"]
        pid = foundation["prods"]["全棉色织布"]["id"]
        so = client.post("/api/sales/orders", json={
            "customer_id": cust, "currency_id": cny, "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 10, "unit_price": 50, "tax_rate": 13}],
        }, headers=h).json()
        so_id, item_id = so["id"], so["id"]  # item id 需 GET
        detail = client.get(f"/api/sales/orders/{so_id}", headers=h).json()
        item_id = detail["items"][0]["id"]
        for path in ("stock-in", "outsource", "re-produce"):
            r = client.post(f"/api/sales/orders/{so_id}/items/{item_id}/{path}", json={}, headers=h)
            assert r.status_code == 400, f"未审核订单 {path} 应 400，实际 {r.status_code}"


class TestOutsourceFlow:
    """转外发 = 委外流程：转外发(标记)→ 委外订单(from-sales)→维护委外商/单价→审核→应付+末道待入库单"""

    def test_outsource_full_flow(self, client, auth_headers, foundation):
        """转外发标记后，从-sales 生成委外订单 → 维护委外商/单价 → 审核生成应付 + 待入库单"""
        h = auth_headers
        sup_os = foundation["sup_os"]  # 委外商
        so_id, item_id = _mk_so_item(client, h, foundation)

        # 转外发：仅标记生产状态
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/outsource",
                           json={}, headers=h).status_code == 200
        assert _status(client, h, so_id, item_id) == "已通知外发"

        # 销售订单转委外：生成委外订单（草稿）
        r = client.post("/api/outsource/orders/from-sales", json={
            "sales_order_id": so_id,
            "rows": [{"sales_item_id": item_id, "quantity": 10}],
        }, headers=h)
        assert r.status_code == 200, r.text

        from app.models.production import OutsourceOrder
        db = SessionLocal()
        try:
            os_order = db.query(OutsourceOrder).filter(
                OutsourceOrder.sales_item_id == item_id).first()
            assert os_order is not None, "转外发应生成委外订单"
            assert os_order.status == "待确认"
            os_id = os_order.id
        finally:
            db.close()

        # 维护：选委外商 + 加工单价 → 审核
        r = client.put(f"/api/outsource/orders/{os_id}", json={
            "outsourcer_id": sup_os, "unit_price": 2.5}, headers=h)
        assert r.status_code == 200, r.text
        r = client.post(f"/api/outsource/orders/{os_id}/approve", json={}, headers=h)
        assert r.status_code == 200, r.text

        # 应付账款生成（加工费=10×2.5=25）
        from app.models.purchase import AccountsPayable
        db = SessionLocal()
        try:
            ap = db.query(AccountsPayable).filter(
                AccountsPayable.source_type == "outsource",
                AccountsPayable.source_id == os_id).first()
            assert ap is not None, "委外审核应生成应付账款"
            assert ap.amount == 25.0, f"加工费应付应为 10×2.5=25，实际 {ap.amount}"
            assert ap.supplier_id == sup_os, f"应付供应商应为委外商，实际 {ap.supplier_id}"
        finally:
            db.close()

    def test_outsource_require_outsourcer_to_approve(self, client, auth_headers, foundation):
        """委外订单未选委外商不能审核 → 400"""
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        client.post(f"/api/sales/orders/{so_id}/items/{item_id}/outsource", json={}, headers=h)
        client.post("/api/outsource/orders/from-sales", json={
            "sales_order_id": so_id, "rows": [{"sales_item_id": item_id, "quantity": 10}],
        }, headers=h)
        from app.models.production import OutsourceOrder
        db = SessionLocal()
        try:
            os_id = db.query(OutsourceOrder).filter(
                OutsourceOrder.sales_item_id == item_id).first().id
        finally:
            db.close()
        r = client.post(f"/api/outsource/orders/{os_id}/approve", json={}, headers=h)
        assert r.status_code == 400, f"未选委外商审核应 400，实际 {r.status_code}"


class TestThreeBranchReminders:
    """三分支预警埋点：SO_TO_PURCHASE / SO_TO_OUTSOURCE / SO_TO_PRODUCTION 各自触发"""

    @staticmethod
    def _ensure_role_user(role_code: str, username: str):
        """确保某业务角色的启用用户存在（收件人解析依赖角色用户落库）"""
        from app.models.auth import Role, User
        from app.utils.auth import get_password_hash
        db = SessionLocal()
        try:
            role = db.query(Role).filter(Role.code == role_code).first()
            assert role, f"角色 {role_code} 不存在"
            u = db.query(User).filter(User.username == username).first()
            if not u:
                u = User(username=username, display_name=f"{role.name}测试", role_id=role.id,
                         is_active=1, password_hash=get_password_hash("test123"))
                db.add(u)
                db.commit()
                db.refresh(u)
            return u.id
        finally:
            db.close()

    def _notify_count(self, point_code, doc_id):
        db = SessionLocal()
        try:
            return db.query(Notification).filter(
                Notification.point_code == point_code,
                Notification.doc_id == doc_id).count()
        finally:
            db.close()

    def test_so_to_production_reminder(self, client, auth_headers, foundation):
        """转生产 → 触发 SO_TO_PRODUCTION 提醒（V3 埋点，需验证）"""
        self._ensure_role_user("production_manager", "rm_pm3b")
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/re-produce",
                           json={}, headers=h).status_code == 200
        assert self._notify_count("SO_TO_PRODUCTION", so_id) >= 1, "转生产应触发 SO_TO_PRODUCTION"

    def test_so_to_purchase_reminder(self, client, auth_headers, foundation):
        """转直采 → 触发 SO_TO_PURCHASE 提醒"""
        self._ensure_role_user("purchase_manager", "rm_pur3b")
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/stock-in",
                           json={}, headers=h).status_code == 200
        assert self._notify_count("SO_TO_PURCHASE", so_id) >= 1, "转直采应触发 SO_TO_PURCHASE"

    def test_so_to_outsource_reminder(self, client, auth_headers, foundation):
        """转外发 → 触发 SO_TO_OUTSOURCE 提醒"""
        self._ensure_role_user("purchase_manager", "rm_pur3b2")
        h = auth_headers
        so_id, item_id = _mk_so_item(client, h, foundation)
        assert client.post(f"/api/sales/orders/{so_id}/items/{item_id}/outsource",
                           json={}, headers=h).status_code == 200
        assert self._notify_count("SO_TO_OUTSOURCE", so_id) >= 1, "转外发应触发 SO_TO_OUTSOURCE"
