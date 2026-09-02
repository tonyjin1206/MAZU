"""AI 助手 Agent 测试：工具权限过滤、审核权限、审计日志、新工具执行器

- 权限：工具按用户菜单权限过滤 + 执行前校验（A 方案：能进菜单=能操作）
- 审核：PO/SO 审核接口要求对应菜单权限（403）
- 审计：写操作工具落 sys_operation_log
"""

import uuid
from datetime import date

import pytest

from app.database import SessionLocal
from app.models.auth import User
from app.models.system_config import OperationLog
from app.utils.ai_chat import (
    TOOL_PERMS,
    _filter_tools_for_user,
    _check_tool_perm,
    _execute_query_inventory,
    _execute_query_pending_approvals,
    _execute_approve_order,
    _execute_query_manual,
    _execute_create_order,
    _execute_create_purchase_invoice,
    _execute_create_sales_invoice,
    _log_operation,
)

BASE = "/api"


# ==================== fixtures ====================

@pytest.fixture(scope="module")
def base_data(client, admin_token):
    """最小基础数据：货币/仓库/供应商/客户/物料/产品"""
    h = {"Authorization": f"Bearer {admin_token}"}
    cny = client.post(f"{BASE}/foundation/currencies", json={
        "code": "BOTC", "name": "人民币-BOT", "symbol": "¥", "is_base": 1}, headers=h).json()["id"]
    wh = client.post(f"{BASE}/foundation/warehouses", json={
        "code": "WH-BOT", "name": "主仓-BOT", "wh_type": "原料仓",
        "address": "浙江省绍兴市柯桥区", "manager": "BOT测试员"}, headers=h).json()["id"]
    sup = client.post(f"{BASE}/foundation/suppliers", json={
        "name": "BOT测试供应商", "contact_person": "王", "phone": "13800000000",
        "tax_id": "91330100BOT", "address": "杭州", "supplier_type": "原材料"}, headers=h).json()["id"]
    cust = client.post(f"{BASE}/foundation/customers", json={
        "name_cn": "BOT测试客户", "country": "中国", "contact_person": "李",
        "phone": "13900000000", "tax_id": "91330000BOT", "address": "上海"}, headers=h).json()["id"]
    mat = client.post(f"{BASE}/foundation/materials", json={
        "name": "BOT测试材料", "spec": "A级", "unit": "KG",
        "category": "原材料", "purchase_price": 10}, headers=h).json()["id"]
    prod = client.post(f"{BASE}/foundation/products", json={
        "name_cn": "BOT测试产品", "spec": "标准", "unit": "米",
        "sale_price": 50}, headers=h).json()["id"]
    return {"cny": cny, "wh": wh, "sup": sup, "cust": cust, "mat": mat, "prod": prod}


@pytest.fixture(scope="module")
def users(client, admin_token):
    """采购经理 / 只读 两个测试用户 + token"""
    h = {"Authorization": f"Bearer {admin_token}"}
    roles = {r["code"]: r["id"] for r in client.get(f"{BASE}/auth/roles", headers=h).json()}
    out = {}
    for uname, role_code in [("bot_pm", "purchase_manager"), ("bot_ro", "readonly")]:
        client.post(f"{BASE}/auth/users", json={
            "username": uname, "password": "test123456",
            "display_name": uname, "role_id": roles[role_code]}, headers=h)
        tk = client.post(f"{BASE}/auth/login", json={"username": uname, "password": "test123456"}).json()["access_token"]
        out[uname] = {"token": tk, "headers": {"Authorization": f"Bearer {tk}"}}
    return out


@pytest.fixture()
def db():
    """单测用 DB 会话"""
    session = SessionLocal()
    yield session
    session.close()


def _user(db, username):
    return db.query(User).filter(User.username == username).first()


def _mk_po(client, admin_token, base_data, remark="BOT"):
    """通过 API 建一张待审核采购订单，返回 order_no"""
    h = {"Authorization": f"Bearer {admin_token}"}
    resp = client.post(f"{BASE}/purchase/orders", json={
        "supplier_id": base_data["sup"], "remark": remark,
        "items": [{"material_id": base_data["mat"], "quantity": 10, "unit_price": 5}],
    }, headers=h)
    assert resp.status_code == 200, f"PO 创建失败: {resp.text[:300]}"
    return resp.json()["order_no"]


def _mk_so(client, admin_token, base_data):
    """通过 API 建一张待审核销售订单，返回 order_no"""
    h = {"Authorization": f"Bearer {admin_token}"}
    resp = client.post(f"{BASE}/sales/orders", json={
        "customer_id": base_data["cust"],
        "items": [{"product_id": base_data["prod"], "quantity": 5, "unit_price": 20, "tax_rate": 13}],
    }, headers=h)
    assert resp.status_code == 200, f"SO 创建失败: {resp.text[:300]}"
    return resp.json()["order_no"]


# ==================== 工具权限过滤 ====================

class TestToolFilter:
    def test_admin_gets_all_tools(self, db):
        tools = _filter_tools_for_user(_user(db, "admin"))
        names = {t["function"]["name"] for t in tools}
        assert names == set(TOOL_PERMS)

    def test_readonly_gets_only_open_tools(self, db, users):
        """只读角色：只有无需权限的手册/待审清单"""
        tools = _filter_tools_for_user(_user(db, "bot_ro"))
        names = {t["function"]["name"] for t in tools}
        assert names == {"query_manual", "query_pending_approvals"}

    def test_purchase_manager_order_enum_subset(self, db, users):
        """采购经理：create_order 的 order_type 枚举只剩采购单"""
        tools = _filter_tools_for_user(_user(db, "bot_pm"))
        names = {t["function"]["name"] for t in tools}
        assert "create_order" in names
        assert "query_inventory" not in names  # 无库存权限
        create = next(t for t in tools if t["function"]["name"] == "create_order")
        enum = create["function"]["parameters"]["properties"]["order_type"]["enum"]
        assert enum == ["purchase_order"]

    def test_purchase_manager_query_entities_enum(self, db, users):
        """采购经理：query_entities 只剩应付/采购发票（supplier 是基础档案权限）"""
        tools = _filter_tools_for_user(_user(db, "bot_pm"))
        qe = next(t for t in tools if t["function"]["name"] == "query_entities")
        enum = qe["function"]["parameters"]["properties"]["entity_type"]["enum"]
        assert set(enum) == {"payable", "purchase_invoice"}


# ==================== 执行前权限校验 ====================

class TestPermCheck:
    def test_deny_no_perm(self, db, users):
        ro = _user(db, "bot_ro")
        assert not _check_tool_perm(ro, "create_order", {"order_type": "purchase_order"})
        assert not _check_tool_perm(ro, "query_inventory", {})
        assert _check_tool_perm(ro, "query_manual", {"keyword": "采购"})

    def test_allow_with_perm(self, db, users):
        pm = _user(db, "bot_pm")
        assert _check_tool_perm(pm, "create_order", {"order_type": "purchase_order"})
        assert not _check_tool_perm(pm, "create_order", {"order_type": "sales_order"})
        assert not _check_tool_perm(pm, "query_inventory", {})
        admin = _user(db, "admin")
        assert _check_tool_perm(admin, "query_inventory", {})
        assert _check_tool_perm(admin, "approve_order", {"order_type": "sales_order"})


# ==================== 新工具执行器 ====================

class TestExecutors:
    def test_query_inventory(self, db, base_data):
        from app.models.inventory import WarehouseInventory
        db.add(WarehouseInventory(warehouse_id=base_data["wh"], material_id=base_data["mat"],
                                  batch_no="B-BOT-001", quantity=100, in_date=date.today()))
        db.commit()
        r = _execute_query_inventory({"keyword": "BOT测试材料"}, db)
        assert "BOT测试材料" in r and "100" in r

    def test_query_inventory_no_warehouse(self, db, base_data):
        r = _execute_query_inventory({"keyword": "不存在的物料XYZ"}, db)
        assert "没有找到库存记录" in r

    def test_query_manual(self):
        r = _execute_query_manual({"keyword": "采购入库"}, db=None)
        assert "操作手册" in r and "采购入库" in r

    def test_pending_approvals_no_perm(self, db, users):
        r = _execute_query_pending_approvals({}, db, _user(db, "bot_ro"))
        assert "没有待审核单据的查看权限" in r

    def test_pending_approvals_ok(self, db, users, base_data, client, admin_token):
        po_no = _mk_po(client, admin_token, base_data, remark="BOT待审")
        r = _execute_query_pending_approvals({}, db, _user(db, "bot_pm"))
        assert "📋 待审核单据" in r and po_no in r

    def test_approve_po(self, db, users, base_data, client, admin_token):
        po_no = _mk_po(client, admin_token, base_data, remark="BOT审核")
        pm = _user(db, "bot_pm")
        r = _execute_approve_order({"order_type": "purchase_order", "order_no": po_no}, db, pm)
        assert "已审核" in r
        from app.models.purchase import PurchaseOrder
        po = db.query(PurchaseOrder).filter(PurchaseOrder.order_no == po_no).first()
        assert po.status == "已审核"

    def test_approve_so_no_auto_mo(self, db, users, base_data, client, admin_token):
        """SP 流程：销售审核不再自动生成生产订单，明细行置「未生产」，提示走三分支。

        v2.8.0 三分支：审核通过后明细行待用户选择 转直采/转外发(委外)/转生产(自产)。
        """
        so_no = _mk_so(client, admin_token, base_data)
        r = _execute_approve_order({"order_type": "sales_order", "order_no": so_no}, db, _user(db, "admin"))
        assert "已审核" in r and "转直采" in r and "转外发" in r and "转生产" in r
        from app.models.sales import SalesOrder, SalesOrderItem
        from app.models.production import ProductionOrder
        so = db.query(SalesOrder).filter(SalesOrder.order_no == so_no).first()
        assert so.status == "已审"
        # 不自动生成生产订单（三分支由用户后续触发）
        mos = db.query(ProductionOrder).filter(ProductionOrder.sales_order_id == so.id).all()
        assert len(mos) == 0, "审核不应自动生成生产订单（三分支后由 re-produce 触发转生产）"
        # 明细行生产状态初始化为「未生产」
        for item in so.items:
            assert item.production_status in (None, "", "未生产")

    def test_ai_create_order_no_collision(self, db, users, base_data, client, admin_token):
        """AI 建单单号必须与业务表序列一致（不查错表导致撞号 500）"""
        # 先人工建一张 PO（占用当天序号），AI 再建必须得到不同单号
        manual_no = _mk_po(client, admin_token, base_data, remark="BOT撞号")
        from app.models.purchase import PurchaseOrder
        from app.models.sales import SalesOrder
        r = _execute_create_order({
            "order_type": "purchase_order", "supplier_name": "BOT测试供应商",
            "items": [{"material_name": "BOT测试材料", "quantity": 3, "unit_price": 8}],
        }, db, _user(db, "admin"))
        assert "✅ 采购订单" in r, f"AI 建 PO 失败: {r}"
        ai_no = r.split(" ")[2]
        assert ai_no != manual_no, f"AI 单号与人工单号撞号: {ai_no} == {manual_no}"
        assert db.query(PurchaseOrder).filter(PurchaseOrder.order_no == ai_no).first(), "AI 单号未落库"

    def test_ai_create_sales_order_no_collision(self, db, users, base_data, client, admin_token):
        """AI 建销售订单单号不撞号"""
        manual_no = _mk_so(client, admin_token, base_data)
        from app.models.sales import SalesOrder
        r = _execute_create_order({
            "order_type": "sales_order", "customer_name": "BOT测试客户",
            "items": [{"product_name": "BOT测试产品", "quantity": 2, "unit_price": 30}],
        }, db, _user(db, "admin"))
        assert "✅ 销售订单" in r, f"AI 建 SO 失败: {r}"
        ai_no = r.split(" ")[2]
        assert ai_no != manual_no, f"AI 单号与人工单号撞号: {ai_no} == {manual_no}"

    def test_ai_purchase_invoice_creates_ap_and_input(self, db, users, base_data, client, admin_token):
        """AI 录采购发票必须生成应付账款 + 进项发票（原实现只插发票，无法付款核销/退税关联）"""
        from app.models.purchase import PurchaseInvoice, AccountsPayable
        from app.models.tax_refund import TaxRefundInputInvoice
        po_no = _mk_po(client, admin_token, base_data, remark="BOT发票")
        r = _execute_create_purchase_invoice({
            "order_no": po_no, "invoice_no": "INV-AI-P-001",
            "amount": 320, "tax_amount": 41.6,
        }, db, _user(db, "admin"))
        assert "✅" in r, f"AI 录采购发票失败: {r}"
        inv = db.query(PurchaseInvoice).filter(PurchaseInvoice.invoice_no == "INV-AI-P-001").first()
        assert inv, "采购发票未落库"
        ap = db.query(AccountsPayable).filter(
            AccountsPayable.source_type == "purchase_invoice",
            AccountsPayable.source_id == inv.id).first()
        assert ap and ap.balance == 361.6, f"应付账款未生成或金额错误: {ap and ap.balance}"
        tri = db.query(TaxRefundInputInvoice).filter(
            TaxRefundInputInvoice.invoice_no == "INV-AI-P-001").first()
        assert tri, "进项发票未生成（可抵扣类型应同步创建）"

    def test_ai_sales_invoice_creates_ar(self, db, users, base_data, client, admin_token):
        """AI 录销售发票必须生成应收账款（原实现只插发票，无法收款核销）"""
        from app.models.sales import SalesInvoice, AccountsReceivable
        so_no = _mk_so(client, admin_token, base_data)
        r = _execute_create_sales_invoice({
            "order_no": so_no, "invoice_no": "INV-AI-S-001", "amount": 113,
        }, db, _user(db, "admin"))
        assert "✅" in r, f"AI 录销售发票失败: {r}"
        inv = db.query(SalesInvoice).filter(SalesInvoice.invoice_no == "INV-AI-S-001").first()
        assert inv, "销售发票未落库"
        ar = db.query(AccountsReceivable).filter(
            AccountsReceivable.source_type == "sales_invoice",
            AccountsReceivable.source_id == inv.id).first()
        assert ar and ar.balance == 113, f"应收账款未生成或金额错误: {ar and ar.balance}"

    def test_ai_invoice_dup_no_rejected(self, db, users, base_data, client, admin_token):
        """AI 发票号重复 → 拒绝（唯一性校验）"""
        po_no = _mk_po(client, admin_token, base_data, remark="BOT发票2")
        r1 = _execute_create_purchase_invoice({
            "order_no": po_no, "invoice_no": "INV-AI-DUP", "amount": 100,
        }, db, _user(db, "admin"))
        assert "✅" in r1
        r2 = _execute_create_purchase_invoice({
            "order_no": po_no, "invoice_no": "INV-AI-DUP", "amount": 100,
        }, db, _user(db, "admin"))
        assert "发票号已存在" in r2, f"重复发票号应被拒绝: {r2}"


# ==================== 审计日志 ====================

class TestAuditLog:
    def test_log_operation(self, db, users):
        pm = _user(db, "bot_pm")
        _log_operation(db, pm, "采购PCB板100片", "create_order",
                       {"order_type": "purchase_order"}, "✅ 采购订单 PO-TEST-001 已创建")
        log = db.query(OperationLog).filter(OperationLog.username == "bot_pm").order_by(OperationLog.id.desc()).first()
        assert log is not None
        assert log.tool_name == "create_order"
        assert log.doc_no == "PO-TEST-001"
        assert log.success == 1
        assert "采购PCB板" in log.instruction

    def test_log_failure(self, db, users):
        pm = _user(db, "bot_pm")
        _log_operation(db, pm, "审核", "approve_order",
                       {"order_type": "purchase_order"}, "❌ 订单 PO-X 当前状态「已审核」，不能审核")
        log = db.query(OperationLog).filter(OperationLog.username == "bot_pm").order_by(OperationLog.id.desc()).first()
        assert log.success == 0


# ==================== 审核接口权限（HTTP） ====================

class TestApproveEndpoint:
    def test_po_approve_403_readonly(self, client, users, base_data, admin_token):
        po_no = _mk_po(client, admin_token, base_data, remark="BOT403")
        pos = client.get(f"{BASE}/purchase/orders", headers={"Authorization": f"Bearer {admin_token}"}).json()["items"]
        po = next(p for p in pos if p["order_no"] == po_no)
        resp = client.post(f"{BASE}/purchase/orders/{po['id']}/approve", headers=users["bot_ro"]["headers"])
        assert resp.status_code == 403

    def test_po_approve_200_admin(self, client, users, base_data, admin_token):
        po_no = _mk_po(client, admin_token, base_data, remark="BOT200")
        pos = client.get(f"{BASE}/purchase/orders", headers={"Authorization": f"Bearer {admin_token}"}).json()["items"]
        po = next(p for p in pos if p["order_no"] == po_no)
        resp = client.post(f"{BASE}/purchase/orders/{po['id']}/approve",
                           headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200

    def test_so_approve_403_readonly(self, client, users, base_data, admin_token):
        so_no = _mk_so(client, admin_token, base_data)
        sos = client.get(f"{BASE}/sales/orders", headers={"Authorization": f"Bearer {admin_token}"}).json()["items"]
        so = next(s for s in sos if s["order_no"] == so_no)
        resp = client.post(f"{BASE}/sales/orders/{so['id']}/approve", headers=users["bot_ro"]["headers"])
        assert resp.status_code == 403

    def test_so_approve_200_admin(self, client, users, base_data, admin_token):
        so_no = _mk_so(client, admin_token, base_data)
        sos = client.get(f"{BASE}/sales/orders", headers={"Authorization": f"Bearer {admin_token}"}).json()["items"]
        so = next(s for s in sos if s["order_no"] == so_no)
        resp = client.post(f"{BASE}/sales/orders/{so['id']}/approve",
                           headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
