"""提醒/通知测试 — 规则配置化 + 事件埋点 + 站内通知（D7：落库即视为已发）

覆盖：
- 默认规则种子（6 条）
- notify 服务：写通知/收件人角色/去重/停用规则/模板渲染
- 4 个事件埋点端到端（SO审核→生产、派产→采购、转外购→采购、开票→销售+财务）
- 通知 API：列表/未读数/已读/admin-query
"""
import pytest

BASE = "/api"

# ======================== 角色用户 fixture ========================

@pytest.fixture(scope="module")
def role_users(client, admin_token, foundation):
    """创建各岗位测试用户，返回 {role_code: (user_id, token)}"""
    h = {"Authorization": f"Bearer {admin_token}"}
    roles = {r["code"]: r["id"] for r in client.get(f"{BASE}/auth/roles", headers=h).json()}
    result = {}
    for code in ["sales_manager", "purchase_manager", "production_manager", "finance_manager"]:
        r = client.post(f"{BASE}/auth/users", json={
            "username": f"t_{code}", "password": "test123",
            "display_name": f"测试{code}", "role_id": roles[code],
        }, headers=h)
        assert r.status_code == 200, f"建用户失败: {r.text}"
        uid = r.json()["id"]
        login = client.post(f"{BASE}/auth/login", json={"username": f"t_{code}", "password": "test123"})
        result[code] = (uid, login.json()["access_token"])
    return result


def _notifs_of(client, token):
    """当前用户通知列表"""
    r = client.get(f"{BASE}/notifications?page_size=100",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


def _admin_query(client, admin_token, **params):
    r = client.get(f"{BASE}/notifications/admin-query", params=params,
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    return r.json()


# ======================== 规则种子 ========================

def test_reminder_rules_seeded(client, admin_token):
    """默认 6 条提醒规则已种子"""
    r = client.get(f"{BASE}/system/reminder-rules",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    codes = {x["code"] for x in r.json()}
    assert {"SO_APPROVED", "MO_PLANNED", "MO_OUTSOURCED", "AR_CREATED", "AR_DUE", "AP_DUE"} <= codes


def _make_so_payload(foundation, prod_id, qty=100, price=50):
    """构造销售订单请求体"""
    return {
        "customer_id": foundation["cust"][0],
        "currency_id": foundation["cny"]["id"],
        "payment_terms": "TT",
        "items": [{"product_id": prod_id, "quantity": qty, "unit_price": price, "tax_rate": 13}],
    }


# ======================== 事件埋点端到端 ========================

def test_so_approved_notifies_production(client, admin_token, foundation, role_users):
    """SO 审核 → production_manager 收到通知；1 小时内重复审核同单不再推"""
    h = {"Authorization": f"Bearer {admin_token}"}
    prod_id = foundation["prods"]["纯棉坯布"]["id"]
    so = client.post(f"{BASE}/sales/orders", json=_make_so_payload(foundation, prod_id), headers=h).json()
    so_id = so["id"]

    client.post(f"{BASE}/sales/orders/{so_id}/approve", json={}, headers=h)
    _, prod_token = role_users["production_manager"]
    items = _notifs_of(client, prod_token)
    hits = [n for n in items if n["point_code"] == "SO_APPROVED" and n["doc_id"] == so_id]
    assert len(hits) == 1, f"生产经理应收到 1 条 SO_APPROVED 通知, 实收 {len(hits)}"
    assert "已审核" in hits[0]["title"]
    assert hits[0]["doc_no"]

    # 去重：同单重复审核（先反派产/重审路径难造，直接再调一次审核会 400，
    # 改为直接调服务层验证去重 — 见 test_notify_dedup）
    # 收件人不应包含销售经理
    _, sale_token = role_users["sales_manager"]
    sale_hits = [n for n in _notifs_of(client, sale_token) if n["point_code"] == "SO_APPROVED"]
    assert sale_hits == [], "销售经理不应收到 SO_APPROVED"


def test_mo_planned_notifies_purchase(client, admin_token, foundation, role_users):
    """派产 → purchase_manager 收到通知"""
    h = {"Authorization": f"Bearer {admin_token}"}
    prod_id = foundation["prods"]["纯棉坯布"]["id"]
    so = client.post(f"{BASE}/sales/orders", json=_make_so_payload(foundation, prod_id), headers=h).json()
    so_id = so["id"]
    client.post(f"{BASE}/sales/orders/{so_id}/approve", json={}, headers=h)
    mos = client.get(f"{BASE}/production/productions?page_size=50", headers=h).json()["items"]
    mo = next(i for i in mos if i["sales_order_id"] == so_id)
    mo_id = mo["id"]

    # 确认备货方式自产 → 待排产
    client.post(f"{BASE}/production/productions/{mo_id}/set-type", json={"production_type": "自产"}, headers=h)
    # 维护工艺路线（整经+织造）
    procs = foundation["procs"]
    client.put(f"{BASE}/production/productions/{mo_id}/processes", json={"items": [
        {"process_id": procs["整经"], "process_qty": 100, "unit_price": 0.5},
        {"process_id": procs["织造"], "process_qty": 100, "unit_price": 1.2},
    ]}, headers=h)
    client.post(f"{BASE}/production/productions/{mo_id}/release", json={}, headers=h)

    _, pur_token = role_users["purchase_manager"]
    items = _notifs_of(client, pur_token)
    hits = [n for n in items if n["point_code"] == "MO_PLANNED" and n["doc_id"] == mo_id]
    assert len(hits) == 1, f"采购经理应收到 1 条 MO_PLANNED, 实收 {len(hits)}"
    assert "已排产" in hits[0]["title"]


def test_mo_outsourced_notifies_purchase(client, admin_token, foundation, role_users):
    """生产订单确认外购 → purchase_manager 收到通知"""
    h = {"Authorization": f"Bearer {admin_token}"}
    prod_id = foundation["prods"]["纯棉坯布"]["id"]
    so = client.post(f"{BASE}/sales/orders", json=_make_so_payload(foundation, prod_id, qty=50, price=60), headers=h).json()
    so_id = so["id"]
    client.post(f"{BASE}/sales/orders/{so_id}/approve", json={}, headers=h)
    mos = client.get(f"{BASE}/production/productions?page_size=50", headers=h).json()["items"]
    mo = next(i for i in mos if i["sales_order_id"] == so_id)
    mo_id = mo["id"]

    r = client.post(f"{BASE}/production/productions/{mo_id}/set-type",
                    json={"production_type": "外购"}, headers=h)
    assert r.status_code == 200, r.text

    _, pur_token = role_users["purchase_manager"]
    items = _notifs_of(client, pur_token)
    hits = [n for n in items if n["point_code"] == "MO_OUTSOURCED" and n["doc_id"] == mo_id]
    assert len(hits) == 1, f"采购经理应收到 1 条 MO_OUTSOURCED, 实收 {len(hits)}"
    assert "外购" in hits[0]["title"]


def test_ar_created_notifies_sales_and_finance(client, admin_token, foundation, role_users):
    """开票生成应收 → sales_manager + finance_manager 双收件人（D2）"""
    h = {"Authorization": f"Bearer {admin_token}"}
    prod_id = foundation["prods"]["纯棉坯布"]["id"]
    so = client.post(f"{BASE}/sales/orders", json=_make_so_payload(foundation, prod_id), headers=h).json()
    so_id = so["id"]

    inv = client.post(f"{BASE}/sales/invoices", json={
        "invoice_no": f"INV-RM-{so_id}", "order_id": so_id,
        "invoice_date": "2026-08-05", "amount": 4424.78, "amount_fc": 4424.78,
        "tax_amount": 575.22, "total_amount": 5000.0, "tax_rate": 13,
    }, headers=h)
    assert inv.status_code == 200, inv.text
    ar_no = inv.json()["ar_no"]

    _, sale_token = role_users["sales_manager"]
    _, fin_token = role_users["finance_manager"]
    sale_hits = [n for n in _notifs_of(client, sale_token)
                 if n["point_code"] == "AR_CREATED" and n["doc_no"] == ar_no]
    fin_hits = [n for n in _notifs_of(client, fin_token)
                if n["point_code"] == "AR_CREATED" and n["doc_no"] == ar_no]
    assert len(sale_hits) == 1, "销售经理应收到应收提醒（催收）"
    assert len(fin_hits) == 1, "财务经理应收到应收提醒（入账）"
    assert "应收" in sale_hits[0]["title"]


# ======================== notify 服务：去重/停用/模板 ========================

def test_notify_dedup_and_disable(client, admin_token):
    """服务层：同单据 1 小时内去重；停用规则不写"""
    from app.database import SessionLocal
    from app.services.reminder import notify
    from app.models.system_config import Notification, ReminderRule

    db = SessionLocal()
    try:
        # 用一个不存在的 doc_id 保证干净
        doc_id = 999999
        # 先删掉可能的历史
        db.query(Notification).filter(Notification.doc_id == doc_id).delete()
        db.commit()

        n1 = notify(db, "SO_APPROVED", "so_order", doc_id, "SO-DEDUP-TEST",
                    {"order_no": "SO-DEDUP-TEST", "customer_name": "测试", "mo_count": 1})
        assert n1 > 0, "第一次应写入通知"
        n2 = notify(db, "SO_APPROVED", "so_order", doc_id, "SO-DEDUP-TEST",
                    {"order_no": "SO-DEDUP-TEST", "customer_name": "测试", "mo_count": 1})
        assert n2 == 0, f"1 小时内去重应返回 0, 实际 {n2}"
        count = db.query(Notification).filter(Notification.doc_id == doc_id).count()
        assert count == n1, "去重后不应新增记录"

        # 停用规则 → 不写
        rule = db.query(ReminderRule).filter(ReminderRule.code == "SO_APPROVED").first()
        rule.enabled = 0
        db.commit()
        n3 = notify(db, "SO_APPROVED", "so_order", doc_id + 1, "SO-DISABLED",
                    {"order_no": "SO-DISABLED"})
        assert n3 == 0, "停用规则不应写通知"
        rule.enabled = 1
        db.commit()
    finally:
        db.close()


def test_template_render(client):
    """模板渲染：占位符替换 + 缺失占位符不报错"""
    from app.services.reminder import render_template
    assert render_template("应收 {ar_no} 金额 {amount}", {"ar_no": "AR001", "amount": "100.00"}) \
        == "应收 AR001 金额 100.00"
    # 缺失占位符保留原文
    assert render_template("订单 {order_no} 已审核", {}) == "订单 {order_no} 已审核"


# ======================== 通知 API ========================

def test_notification_api(client, admin_token, role_users):
    """未读数 → 已读 → 未读数归零；admin-query 全量筛选"""
    _, sale_token = role_users["sales_manager"]
    sale_uid, _ = role_users["sales_manager"]
    h_sale = {"Authorization": f"Bearer {sale_token}"}
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 自建一条通知（不依赖其他测试产生业务数据）
    from app.database import SessionLocal
    from app.models.system_config import Notification
    db = SessionLocal()
    try:
        db.add(Notification(user_id=sale_uid, point_code="TEST_API", title="测试通知",
                            content="API 测试", doc_type="test", doc_id=0, doc_no="T-1"))
        db.commit()
    finally:
        db.close()

    before = client.get(f"{BASE}/notifications/unread-count", headers=h_sale).json()["count"]
    assert before >= 1, "销售经理应有未读通知"

    # 标记第一条已读
    items = _notifs_of(client, sale_token)
    nid = items[0]["id"]
    r = client.put(f"{BASE}/notifications/{nid}/read", json={"read_status": 1}, headers=h_sale)
    assert r.status_code == 200
    after = client.get(f"{BASE}/notifications/unread-count", headers=h_sale).json()["count"]
    assert after == before - 1

    # 全部已读
    client.put(f"{BASE}/notifications/read-all", headers=h_sale)
    assert client.get(f"{BASE}/notifications/unread-count", headers=h_sale).json()["count"] == 0

    # admin-query：按角色筛选（sales_manager 用户）
    sale_uid, _ = role_users["sales_manager"]
    resp = _admin_query(client, admin_token, user_id=sale_uid, page_size=50)
    rows = resp["items"]
    assert rows, "admin-query 应查到销售经理的通知"
    assert all(x["user_id"] == sale_uid for x in rows)
    assert all(x["user_name"] for x in rows), "应带收件人姓名"

    # admin-query：按角色 code 筛选
    resp_role = _admin_query(client, admin_token, role_code="sales_manager", page_size=50)
    assert resp_role["items"], "按角色筛选应查到销售经理的通知"
    assert all(x["role_name"] == "销售经理" for x in resp_role["items"])

    # admin-query：按提醒点筛选
    resp_point = _admin_query(client, admin_token, point_code="TEST_API", page_size=50)
    assert resp_point["items"], "按提醒点筛选应查到 TEST_API 通知"
    assert all(x["point_code"] == "TEST_API" for x in resp_point["items"])

    # 非 admin 访问 admin-query 应 403
    r = client.get(f"{BASE}/notifications/admin-query", headers=h_sale)
    assert r.status_code == 403
