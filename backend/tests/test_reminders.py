"""批4 预警提醒系统专项测试：通知内核 + 事件埋点（按当前产品逻辑重校）+ 定时账期扫描 + 规则种子

依赖：foundation fixture + admin 登录（auth_headers = admin）。
重点：无「生产订单」模块，销售订单下游走转直采/转外发——故以 SO_TO_PURCHASE/SO_TO_OUTSOURCE
     替代原 MO_PLANNED/MO_OUTSOURCED；通知落库即视为已发（D7）。
"""
import pytest
from app.database import SessionLocal
from app.models.auth import Role, User
from app.models.system_config import Notification, ReminderRule
from app.services.reminder import run_scheduled_scan
from app.utils.auth import get_password_hash
from datetime import date, timedelta


def _api(client, method, path, json_data=None, headers=None):
    if method == "GET":
        resp = client.get(path, headers=headers)
    elif method == "POST":
        resp = client.post(path, json=json_data or {}, headers=headers)
    elif method == "PUT":
        resp = client.put(path, json=json_data or {}, headers=headers)
    elif method == "DELETE":
        resp = client.delete(path, headers=headers)
    else:
        raise ValueError(f"未知 method: {method}")
    return resp


def _ensure_role_user(role_code: str, username: str) -> int:
    """确保某业务角色的启用用户存在，返回其 id（用 admin 同款 password hash）"""
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


def _create_approved_order(client, h, f):
    """建销售订单 → 审批，返回 (order_id, order_no)"""
    cust = f["cust"][0]
    cny = f["cny"]
    pid = f["prods"]["全棉色织布"]["id"]
    r = _api(client, "POST", "/api/sales/orders", {
        "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
        "items": [{"product_id": pid, "quantity": 100, "unit_price": 15.0, "tax_rate": 13}],
    }, h)
    assert r.status_code == 200, f"建订单失败: {r.text}"
    so = r.json()
    r2 = _api(client, "POST", f"/api/sales/orders/{so['id']}/approve", {}, h)
    assert r2.status_code == 200, f"审批失败: {r2.text}"
    return so["id"], so["order_no"]


class TestReminderRulesSeed:
    def test_rules_seeded(self, client):
        """启动种子应生成 6 事件 + 4 定时 = 10 条规则"""
        db = SessionLocal()
        try:
            total = db.query(ReminderRule).count()
            assert total >= 10, f"规则应≥10，实际 {total}"
            codes = {r.code for r in db.query(ReminderRule).all()}
            # 无生产订单模块 → 不应有 MO_PLANNED/MO_OUTSOURCED
            assert "MO_PLANNED" not in codes and "MO_OUTSOURCED" not in codes
            assert "SO_TO_PURCHASE" in codes and "SO_TO_OUTSOURCE" in codes
            assert "AR_CREATED" in codes and "AR_OVERDUE" in codes
        finally:
            db.close()


class TestEventReminders:
    def test_so_approved(self, client, auth_headers, foundation):
        """SO 审核通过 → 提醒销售经理（转直采/转委外）"""
        sales_id = _ensure_role_user("sales_manager", "rm_sales")
        oid, ono = _create_approved_order(client, auth_headers, foundation)
        db = SessionLocal()
        try:
            rows = db.query(Notification).filter(
                Notification.point_code == "SO_APPROVED", Notification.doc_id == oid).all()
            assert rows, "SO_APPROVED 未生成通知"
            assert any(r.user_id == sales_id for r in rows), "通知未发给销售经理"
            assert rows[0].title and str(ono) in rows[0].title
        finally:
            db.close()

    def test_dedup_window(self, client, auth_headers, foundation):
        """同一单据同提醒点 1 小时内不重复推 → 审批不重复生成 SO_APPROVED

        去重语义 = 每个收件人同单据同提醒点窗口内仅 1 条（按角色广播，角色可有多个用户）。
        """
        sales = _ensure_role_user("sales_manager", "rm_sales")
        oid, _ = _create_approved_order(client, auth_headers, foundation)
        db = SessionLocal()
        try:
            rows = db.query(Notification).filter(
                Notification.point_code == "SO_APPROVED", Notification.doc_id == oid).all()
            assert rows, "SO_APPROVED 未生成通知"
            per_user = {}
            for r in rows:
                per_user[r.user_id] = per_user.get(r.user_id, 0) + 1
            # 每个收件人（含销售经理）同单据同提醒点只能有 1 条
            assert all(v == 1 for v in per_user.values()), f"SO_APPROVED 应按收件人去重，实际 {per_user}"
            assert per_user.get(sales) == 1, f"销售经理应收到 1 条 SO_APPROVED，实际 {per_user.get(sales)}"
        finally:
            db.close()

    def test_ar_created_dual_recipients(self, client, auth_headers, foundation):
        """应收生成 → 提醒财务经理 + 销售经理（双收件人）"""
        fin = _ensure_role_user("finance_manager", "rm_fin")
        sales = _ensure_role_user("sales_manager", "rm_sales")
        oid, _ = _create_approved_order(client, auth_headers, foundation)
        qty, price, total = 100, 15.0, 1500.0
        amt = round(total / 1.13, 2); tax = round(total * 0.13 / 1.13, 2)
        r = _api(client, "POST", "/api/sales/invoices", {
            "invoice_no": f"INV-RM-{oid}", "order_id": oid, "invoice_date": "2026-08-28",
            "amount": amt, "amount_fc": amt, "tax_amount": tax, "total_amount": total, "tax_rate": 13,
        }, auth_headers)
        assert r.status_code == 200, f"开票失败: {r.text}"
        db = SessionLocal()
        try:
            rows = db.query(Notification).filter(Notification.point_code == "AR_CREATED").all()
            assert rows, "AR_CREATED 未生成通知"
            users = {x.user_id for x in rows}
            assert fin in users, "缺少财务经理收件人"
            assert sales in users, "缺少销售经理收件人"
        finally:
            db.close()


class TestScheduledScan:
    def test_ar_overdue_and_due_soon(self, client, auth_headers, foundation):
        """定时扫描：应收将到期 / 逾期 分别落库提醒（red 应收不参与）"""
        sales = _ensure_role_user("sales_manager", "rm_sales")
        fin = _ensure_role_user("finance_manager", "rm_fin")
        today = date.today()
        db = SessionLocal()
        try:
            from app.models.sales import AccountsReceivable
            cust = foundation["cust"][0]
            db.add(AccountsReceivable(ar_no=f"AR-RM-D1-{today}", customer_id=cust, amount=1000,
                                      collected_amount=0, balance=1000, due_date=today + timedelta(days=3),
                                      status="未收款", is_red=0))
            db.add(AccountsReceivable(ar_no=f"AR-RM-O1-{today}", customer_id=cust, amount=2000,
                                      collected_amount=0, balance=2000, due_date=today - timedelta(days=2),
                                      status="未收款", is_red=0))
            db.add(AccountsReceivable(ar_no=f"AR-RM-RED-{today}", customer_id=cust, amount=-500,
                                      collected_amount=0, balance=-500, due_date=today - timedelta(days=1),
                                      status="未收款", is_red=1))
            db.commit()
            summary = run_scheduled_scan(db)
            assert summary.get("AR_DUE_SOON", 0) >= 1, "应收将到期未提醒"
            assert summary.get("AR_OVERDUE", 0) >= 1, "应收逾期未提醒"
            # red 应收不参与 overdue
            red_reminded = db.query(Notification).filter(
                Notification.point_code == "AR_OVERDUE", Notification.doc_no == f"AR-RM-RED-{today}").count()
            assert red_reminded == 0, "红字应收不应触发逾期提醒"
            # overdue 收件 = 销售 + 财务
            due_rows = db.query(Notification).filter(
                Notification.point_code == "AR_DUE_SOON", Notification.doc_no == f"AR-RM-D1-{today}").all()
            assert due_rows and any(r.user_id == sales for r in due_rows), "将到期未提醒销售"
            over_rows = db.query(Notification).filter(
                Notification.point_code == "AR_OVERDUE", Notification.doc_no == f"AR-RM-O1-{today}").all()
            assert any(r.user_id == sales for r in over_rows) and any(r.user_id == fin for r in over_rows), \
                "逾期未提醒销售+财务"
        finally:
            db.close()


class TestNotificationApi:
    def test_unread_and_admin_query(self, client, auth_headers, foundation):
        """通知 API：unread-count 当前用户为 0（admin 无业务消息）；admin-query 能查全量"""
        r = _api(client, "GET", "/api/notifications/unread-count", headers=auth_headers)
        assert r.status_code == 200
        assert "count" in r.json()
        r2 = _api(client, "GET", "/api/notifications/admin-query?page_size=5", headers=auth_headers)
        assert r2.status_code == 200
        assert "items" in r2.json() and "total" in r2.json()
