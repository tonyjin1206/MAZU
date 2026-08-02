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
    _log_operation,
)

BASE = "/api"


# ==================== fixtures ====================

@pytest.fixture(scope="module")
def base_data(client, admin_token):
    """最小基础数据：货币/仓库/供应商/客户/物料/产品"""
    h = {"Authorization": f"Bearer {admin_token}"}
    cny = client.post(f"{BASE}/foundation/currencies", json={
        "code": "CNY-BOT", "name": "人民币-BOT", "symbol": "¥", "is_base": 1}, headers=h).json()["id"]
    wh = client.post(f"{BASE}/foundation/warehouses", json={
        "code": "WH-BOT", "name": "主仓-BOT", "wh_type": "原料仓",
        "address": "浙江省绍兴市柯桥区", "manager": "BOT测试员"}, headers=h).json()["id"]
    sup = client.post(f"{BASE}/foundation/suppliers", json={
        "name": "BOT测试供应商", "contact_person": "王", "phone": "13800000000",
        "tax_id": "91330100BOT", "address": "杭州", "supplier_type": "供应商"}, headers=h).json()["id"]
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

    def test_approve_so_generates_mo(self, db, users, base_data, client, admin_token):
        so_no = _mk_so(client, admin_token, base_data)
        r = _execute_approve_order({"order_type": "sales_order", "order_no": so_no}, db, _user(db, "admin"))
        assert "已审核" in r and "MO-" in r
        from app.models.production import ProductionOrder
        mos = db.query(ProductionOrder).filter(ProductionOrder.sales_order_id.isnot(None)).all()
        assert any(mo.order_no in r for mo in mos)


# ==================== 创建类执行器（含单号生成回归） ====================

class TestCreateExecutors:
    """创建类工具执行器：单号前缀与系统规范一致（generate_doc_no 带 model），
    防止再次出现 PO/SO 撞号（历史 Bug：AI 生成的 -001 与已有单据重复）。"""

    def test_create_order_po_no_prefix(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_create_order
        r = _execute_create_order({
            "order_type": "purchase_order", "supplier_name": "BOT测试供应商",
            "items": [{"material_name": "BOT测试材料", "quantity": 10, "unit_price": 10}],
        }, db, _user(db, "admin"))
        assert "✅" in r and "PO-" in r
        import re
        m = re.search(r"PO-\d{8}-\d{3}", r)
        assert m, f"采购单号格式不对: {r}"
        # 单号必须在 PurchaseOrder 表中唯一（防撞号）
        from app.models.purchase import PurchaseOrder
        assert db.query(PurchaseOrder).filter(PurchaseOrder.order_no == m.group(0)).count() == 1

    def test_create_order_so_no_prefix(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_create_order
        r = _execute_create_order({
            "order_type": "sales_order", "customer_name": "BOT测试客户",
            "items": [{"product_name": "BOT测试产品", "quantity": 5, "unit_price": 50}],
        }, db, _user(db, "admin"))
        assert "✅" in r and "SO-" in r
        import re
        m = re.search(r"SO-\d{8}-\d{3}", r)
        assert m, f"销售单号格式不对: {r}"
        from app.models.sales import SalesOrder
        assert db.query(SalesOrder).filter(SalesOrder.order_no == m.group(0)).count() == 1

    def test_create_order_bad_supplier(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_create_order
        r = _execute_create_order({
            "order_type": "purchase_order", "supplier_name": "不存在的供应商",
            "items": [{"material_name": "BOT测试材料", "quantity": 1, "unit_price": 1}],
        }, db, _user(db, "admin"))
        assert "未找到供应商" in r

    def test_create_collection_no_prefix(self, db, base_data):
        from app.utils.ai_chat import _execute_create_collection
        r = _execute_create_collection({
            "customer_name": "BOT测试客户", "amount": 100,
        }, db, _user(db, "admin"))
        # 收款单号必须是 CR- 前缀（系统规范），不能用旧的 RC-
        assert "✅" in r and "CR-" in r, f"收款单号前缀不对: {r}"
        from app.models.sales import Collection
        import re
        m = re.search(r"CR-\d{8}-\d{3}", r)
        assert m and db.query(Collection).filter(Collection.collection_no == m.group(0)).count() == 1

    def test_create_payment_no_prefix(self, db, base_data):
        from app.utils.ai_chat import _execute_create_payment
        r = _execute_create_payment({
            "supplier_name": "BOT测试供应商", "amount": 100,
        }, db, _user(db, "admin"))
        # 付款单号必须是 PM- 前缀（系统规范），不能用旧的 PAY-
        assert "✅" in r and "PM-" in r, f"付款单号前缀不对: {r}"
        from app.models.purchase import Payment
        import re
        m = re.search(r"PM-\d{8}-\d{3}", r)
        assert m and db.query(Payment).filter(Payment.payment_no == m.group(0)).count() == 1

    def test_create_purchase_invoice(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_create_purchase_invoice
        po_no = _mk_po(client, admin_token, base_data, remark="BOT发票")
        r = _execute_create_purchase_invoice({
            "order_no": po_no, "invoice_no": f"PI-BOT-{uuid.uuid4().hex[:6]}", "amount": 50,
        }, db, _user(db, "admin"))
        assert "✅" in r

    def test_create_sales_invoice(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_create_sales_invoice
        so_no = _mk_so(client, admin_token, base_data)
        r = _execute_create_sales_invoice({
            "order_no": so_no, "invoice_no": f"SI-BOT-{uuid.uuid4().hex[:6]}", "amount": 100,
        }, db, _user(db, "admin"))
        assert "✅" in r

    def test_create_collection_wrong_customer(self, db, base_data):
        from app.utils.ai_chat import _execute_create_collection
        r = _execute_create_collection({"customer_name": "不存在的客户", "amount": 1}, db, _user(db, "admin"))
        assert "未找到客户" in r


# ==================== 生产执行器（批次/库存回归） ====================

class TestProductionExecutors:
    """发料/完工入库执行器：必须走批次库存链路（扣库存 + 流水 + 状态机），
    防止回到 v2.1 的"只插一条记录、库存不变"旧行为。"""

    def _mk_mo_with_inventory(self, db, client, admin_token, base_data):
        """建销售单→审核生成 MO→原料仓入批次库存→返回 (mo_no, batch_no, mat_id, prod_id)"""
        from app.models.inventory import WarehouseInventory
        from app.models.foundation import Warehouse
        mat_id = base_data["mat"]
        prod_id = base_data["prod"]
        # 确保成品仓存在（BOT fixture 只建了原料仓；完工入库需要成品仓）
        fg = db.query(Warehouse).filter(Warehouse.wh_type == "成品仓").first()
        if not fg:
            # 通过 API 建成品仓（走真实创建，字段完整）
            resp = client.post(f"{BASE}/foundation/warehouses", json={
                "code": f"FG-BOT-{uuid.uuid4().hex[:4]}", "name": "成品仓-BOT", "wh_type": "成品仓",
                "address": "浙江省绍兴市柯桥区", "manager": "BOT测试员"},
                headers={"Authorization": f"Bearer {admin_token}"})
            assert resp.status_code == 200, f"成品仓创建失败: {resp.text[:200]}"
        # 原料仓放库存（批次）——先清掉该物料旧批次，保证执行器 FIFO 必然选中本测试批次
        db.query(WarehouseInventory).filter(WarehouseInventory.material_id == mat_id).delete()
        batch_no = f"B-ISSUE-{uuid.uuid4().hex[:6]}"
        db.add(WarehouseInventory(warehouse_id=base_data["wh"], material_id=mat_id,
                                  batch_no=batch_no, quantity=200,
                                  unit_cost=10, total_cost=2000, in_date=date.today()))
        db.commit()
        # 销售单审核生成 MO
        so_no = _mk_so(client, admin_token, base_data)
        from app.utils.ai_chat import _execute_approve_order
        r = _execute_approve_order({"order_type": "sales_order", "order_no": so_no}, db, _user(db, "admin"))
        import re
        mo_no = re.search(r"MO-\d{8}-\d{3}", r).group(0)
        return mo_no, batch_no, mat_id, prod_id

    def test_issue_materials_deducts_inventory(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_issue_materials
        from app.models.inventory import WarehouseInventory, StockTransaction
        mo_no, batch_no, mat_id, _ = self._mk_mo_with_inventory(db, client, admin_token, base_data)
        # 直接按唯一 batch_no 查（不按 quantity 匹配，避免多批次错位）
        inv_row = db.query(WarehouseInventory).filter(
            WarehouseInventory.material_id == mat_id, WarehouseInventory.batch_no == batch_no).first()
        assert inv_row is not None, f"批次 {batch_no} 未找到"
        before = inv_row.quantity
        r = _execute_issue_materials({"production_order_no": mo_no, "material_name": "BOT测试材料", "quantity": 50},
                                     db, _user(db, "admin"))
        assert "✅" in r and "批次" in r, f"发料失败: {r}"
        after = db.query(WarehouseInventory).filter(
            WarehouseInventory.material_id == mat_id, WarehouseInventory.batch_no == batch_no).first().quantity
        assert after == before - 50, f"库存未扣减: before={before} after={after}"
        # 必须有库存流水
        tx = db.query(StockTransaction).filter(StockTransaction.source_doc_type == "发料").order_by(StockTransaction.id.desc()).first()
        assert tx is not None and tx.quantity == -50

    def test_issue_materials_insufficient(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_issue_materials
        mo_no, _, _, _ = self._mk_mo_with_inventory(db, client, admin_token, base_data)
        r = _execute_issue_materials({"production_order_no": mo_no, "material_name": "BOT测试材料", "quantity": 99999},
                                     db, _user(db, "admin"))
        assert "库存不足" in r

    def test_production_receipt_creates_fg_batch(self, db, base_data, client, admin_token):
        from app.utils.ai_chat import _execute_production_receipt
        from app.models.inventory import WarehouseInventory, StockTransaction
        from app.models.production import ProductionReceipt, ProductionOrder
        mo_no, _, _, prod_id = self._mk_mo_with_inventory(db, client, admin_token, base_data)
        r = _execute_production_receipt({"production_order_no": mo_no, "quantity": 5}, db, _user(db, "admin"))
        assert "✅" in r and "FG-" in r, f"入库失败: {r}"
        import re
        m = re.search(r"FG-\d{8}-\d{3}", r)
        assert m
        # 成品库存存在（批次）
        inv = db.query(WarehouseInventory).filter(
            WarehouseInventory.product_id == prod_id, WarehouseInventory.batch_no == m.group(0)).first()
        assert inv is not None and inv.quantity == 5
        # 流水 + 生产单状态更新
        tx = db.query(StockTransaction).filter(StockTransaction.source_doc_type == "完工入库").order_by(StockTransaction.id.desc()).first()
        assert tx is not None and tx.quantity == 5
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no == mo_no).first()
        assert mo.status in ("部分入库", "已入库")


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
