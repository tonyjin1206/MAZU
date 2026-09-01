"""状态机测试：单据状态 × 操作 合法性矩阵

逻辑：从后端代码提取每张单据的状态流转规则，参数化验证——
- 规则允许的状态 → 操作成功（2xx）
- 规则拒绝的状态 → 操作返回 4xx

测试方法：用 SQLAlchemy 直接把单据状态改成枚举中的每个值，再调用操作 API，
验证代码行为与规则表完全一致。这使隐式的状态校验逻辑显式化，
任何"该拒绝的没拒绝 / 该放行的被拦"都会立即暴露。

覆盖单据：采购需求(PR)、采购订单(PO)、销售订单(SO)、生产订单(MO)。

✅ 已按 SP 流程重写（2026-08-28）：销售审核不再自动生成 MO，改走 re-produce 端点。
"""
import pytest

from app.database import SessionLocal

BASE = "/api"

TABLE_MAP = {
    "mo": "mo_production",
    "po": "po_order",
    "pr": "po_requisition",
    "so": "so_order",
}


# ==================== 基础数据 ====================

@pytest.fixture(scope="module")
def base_data(foundation):
    """基础数据：复用共享 foundation（tests/test_data.py 统一构建器），不再自建档案"""
    return {
        "cny": foundation["cny"]["id"],
        "wh": foundation["wh_rm"],
        "sup": foundation["sup"],
        "cust": foundation["cust"][0],
        "mat": foundation["mats"]["精梳棉纱32S"],
        "prod": foundation["prods"]["纯棉坯布"]["id"],
        "proc": foundation["procs"]["整经"],
    }


def _set_status(doc_type: str, doc_id: int, status: str):
    """直接改数据库状态（绕过 API 校验，铺开状态矩阵）"""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text(f"UPDATE {TABLE_MAP[doc_type]} SET status=:s WHERE id=:i"),
                   {"s": status, "i": doc_id})
        db.commit()
    finally:
        db.close()


def _make_so(client, h, base):
    so = client.post(f"{BASE}/sales/orders", json={
        "customer_id": base["cust"], "currency_id": base["cny"], "payment_terms": "TT",
        "items": [{"product_id": base["prod"], "quantity": 100,
                   "unit_price": 50, "tax_rate": 13}]}, headers=h).json()
    return so["id"]


def _make_mo(client, h, base):
    """SP 流程：销售订单审核 → 重发生产 → 生成生产订单，返回 MO id"""
    so_id = _make_so(client, h, base)
    client.post(f"{BASE}/sales/orders/{so_id}/approve", json={}, headers=h)
    # SP 流程：审核后需调用 re-produce 生成 MO
    so_detail = client.get(f"{BASE}/sales/orders/{so_id}", headers=h).json()
    item_id = so_detail["items"][0]["id"]
    mo_resp = client.post(f"{BASE}/sales/orders/{so_id}/items/{item_id}/re-produce", json={}, headers=h).json()
    return mo_resp["id"]


def _make_po(client, h, base):
    po = client.post(f"{BASE}/purchase/orders", json={
        "supplier_id": base["sup"], "currency_id": base["cny"], "order_date": "2026-07-27",
        "items": [{"material_id": base["mat"], "quantity": 100,
                   "unit_price": 10, "tax_rate": 13}]}, headers=h).json()
    return po["id"]


def _make_pr(client, h, base):
    """外购生产订单 → 推采购需求，返回 PR id"""
    mo_id = _make_mo(client, h, base)
    client.post(f"{BASE}/production/productions/{mo_id}/set-type",
                json={"production_type": "外购"}, headers=h)
    r = client.post(f"{BASE}/production/productions/{mo_id}/to-requisition",
                    json={}, headers=h).json()
    return r["requisition_id"]


# ==================== 规则表 ====================
# 每个操作: {允许的状态集合}；其余状态必须 4xx

MO_ACTIONS = {
    "release": {"payload": {}, "allowed": {"待排产"}},
    "unrelease": {"payload": {}, "allowed": {"已排产", "生产中"}},
    "close": {"payload": {}, "allowed": {"已完成", "部分入库", "已入库"}},
    "unclose": {"payload": {}, "allowed": {"已关闭"}},
    "save_processes": {"payload": {"items": []}, "allowed": {"待排产", "已排产"}},
    "receipt": {"payload": {"quantity": 0.001, "material_cost": 0, "process_cost": 0},
                "allowed": {"已完成", "部分入库", "已入库"}, "need_wh": True},
}

PO_ACTIONS = {
    "update": {"payload": {}, "allowed": {"待审核"}},
    "delete": {"payload": None, "allowed": {"待审核"}},
    "approve": {"payload": {}, "allowed": {"待审核"}},
    "unapprove": {"payload": {}, "allowed": {"已审核"}},
    "receipt": {"payload": {"items": []}, "allowed": {"已审核", "部分入库", "已完成"},
                "need_wh": True},
}

SO_ACTIONS = {
    "update": {"payload": {}, "allowed": {"待审核"}},
    "delete": {"payload": None, "allowed": {"待审核"}},
    "approve": {"payload": {}, "allowed": {"待审核"}},
}

PR_ACTIONS = {
    "close": {"payload": {}, "allowed": {"待处理"}},
    "to-purchase": {"payload": {"supplier_id": None}, "allowed": {"待处理"}, "need_sup": True},
}

MO_STATUSES = ["待确认", "待排产", "已排产", "生产中", "已完成",
               "部分入库", "已入库", "待采购", "采购中", "已关闭"]
PO_STATUSES = ["待审核", "已审核", "部分入库", "已完成", "已关闭"]
SO_STATUSES = ["待审核", "已审", "生产中", "部分发货", "已发货", "已完成", "已关闭"]
PR_STATUSES = ["待处理", "已转单", "已关闭"]


# ==================== 测试 ====================

@pytest.mark.parametrize("status", MO_STATUSES)
@pytest.mark.parametrize("action", list(MO_ACTIONS))
def test_mo_state_machine(client, auth_headers, base_data, action, status):
    _run_matrix(client, auth_headers, base_data, "mo", action, status, MO_ACTIONS[action],
                _make_mo)


@pytest.mark.parametrize("status", PO_STATUSES)
@pytest.mark.parametrize("action", list(PO_ACTIONS))
def test_po_state_machine(client, auth_headers, base_data, action, status):
    _run_matrix(client, auth_headers, base_data, "po", action, status, PO_ACTIONS[action],
                _make_po)


@pytest.mark.parametrize("status", SO_STATUSES)
@pytest.mark.parametrize("action", list(SO_ACTIONS))
def test_so_state_machine(client, auth_headers, base_data, action, status):
    _run_matrix(client, auth_headers, base_data, "so", action, status, SO_ACTIONS[action],
                _make_so)


@pytest.mark.parametrize("status", PR_STATUSES)
@pytest.mark.parametrize("action", list(PR_ACTIONS))
def test_pr_state_machine(client, auth_headers, base_data, action, status):
    _run_matrix(client, auth_headers, base_data, "pr", action, status, PR_ACTIONS[action],
                _make_pr)


# 文档池：按 (doc_type, action) 复用同一张单据（每个用例 _set_status 重置状态）
# 单据量从 状态×动作 全量组合 降到 动作数（MO 60→6、PO 25→5、SO 21→3、PR 6→2）
_doc_pool = {}


def _get_doc(client, h, base, doc_type, action, maker):
    key = (doc_type, action)
    doc_id = _doc_pool.get(key)
    if doc_id is None:
        doc_id = maker(client, h, base)
        _doc_pool[key] = doc_id
    return doc_id


def _run_matrix(client, h, base, doc_type, action, status, rule, maker):
    doc_id = _get_doc(client, h, base, doc_type, action, maker)
    _set_status(doc_type, doc_id, status)

    # MO 派产要求先维护工艺路线
    if doc_type == "mo" and action == "release":
        client.put(f"{BASE}/production/productions/{doc_id}/processes",
                   json={"items": [{"process_id": base["proc"], "process_name": "测试工序",
                                    "seq": 1, "process_qty": 100, "unit_price": 1}]},
                   headers=h)

    payload = dict(rule["payload"] or {})
    if rule.get("need_wh"):
        payload["warehouse_id"] = base["wh"]
        payload["order_id"] = doc_id if doc_type == "po" else None
        if doc_type == "po" and action == "receipt":
            # 采购入库需要订单明细
            detail = client.get(f"{BASE}/purchase/orders/{doc_id}", headers=h).json()
            payload["items"] = [
                {"order_item_id": i["id"], "material_id": i.get("material_id"), "quantity": 0.001} 
                for i in detail.get("items", [])]
    if rule.get("need_sup"):
        payload["supplier_id"] = base["sup"]

    path = {
        "mo": {
            "release": f"{BASE}/production/productions/{doc_id}/release",
            "unrelease": f"{BASE}/production/productions/{doc_id}/unrelease",
            "close": f"{BASE}/production/productions/{doc_id}/close",
            "unclose": f"{BASE}/production/productions/{doc_id}/unclose",
            "save_processes": f"{BASE}/production/productions/{doc_id}/processes",
            "receipt": f"{BASE}/production/productions/{doc_id}/receipt",
        },
        "po": {
            "update": f"{BASE}/purchase/orders/{doc_id}",
            "delete": f"{BASE}/purchase/orders/{doc_id}",
            "approve": f"{BASE}/purchase/orders/{doc_id}/approve",
            "unapprove": f"{BASE}/purchase/orders/{doc_id}/unapprove",
            "receipt": f"{BASE}/purchase/receipts",
        },
        "so": {
            "update": f"{BASE}/sales/orders/{doc_id}",
            "delete": f"{BASE}/sales/orders/{doc_id}",
            "approve": f"{BASE}/sales/orders/{doc_id}/approve",
        },
        "pr": {
            "close": f"{BASE}/purchase/requisitions/{doc_id}/close",
            "to-purchase": f"{BASE}/purchase/requisitions/{doc_id}/to-purchase",
        },
    }[doc_type][action]

    try:
        if action == "delete":
            resp = client.delete(path, headers=h)
        elif payload is None:
            resp = client.post(path, json={}, headers=h)
        else:
            resp = (client.put if action == "update" or action == "save_processes"
                    else client.post)(path, json=payload, headers=h)
    except Exception as e:  # 后端 500 抛异常（TestClient raise_server_exceptions）
        if status in rule["allowed"] and rule.get("known_bug"):
            pytest.skip(f"已知缺陷: {rule['known_bug']} ({type(e).__name__}: {e})")
        raise

    expect_ok = status in rule["allowed"]
    if expect_ok:
        if rule.get("known_bug") and resp.status_code >= 500:
            pytest.skip(f"已知缺陷: {rule['known_bug']} (状态「{status}」返回 {resp.status_code})")
        assert resp.status_code < 400, (
            f"[{doc_type}.{action}] 状态「{status}」应允许但被拒: "
            f"{resp.status_code} {resp.text[:200]}")
        if action == "delete":
            # 删除成功 → 文档销毁，从池中移除（后续用例重建）
            _doc_pool.pop((doc_type, action), None)
    else:
        assert 400 <= resp.status_code < 500, (
            f"[{doc_type}.{action}] 状态「{status}」应拒绝但返回 {resp.status_code}: {resp.text[:200]}")


# ==================== 备货方式确认（生产类型字段规则） ====================

def test_mo_set_type_rules(client, auth_headers, base_data):
    """set-type：production_type 未确认时可设；已确认后不可再改（与状态无关）"""
    h = auth_headers
    mo_id = _make_mo(client, h, base_data)

    # 未确认 → 允许
    r1 = client.post(f"{BASE}/production/productions/{mo_id}/set-type",
                     json={"production_type": "自产"}, headers=h)
    assert r1.status_code == 200, r1.text

    # 已确认 → 任何状态都拒绝
    for status in ["待排产", "已排产", "生产中", "已完成", "已关闭"]:
        _set_status("mo", mo_id, status)
        r = client.post(f"{BASE}/production/productions/{mo_id}/set-type",
                        json={"production_type": "委外"}, headers=h)
        assert 400 <= r.status_code < 500, (
            f"set-type 在状态「{status}」已确认备货方式后应拒绝，返回 {r.status_code}")

    # 非法类型值
    mo2 = _make_mo(client, h, base_data)
    r = client.post(f"{BASE}/production/productions/{mo2}/set-type",
                    json={"production_type": "乱写的"}, headers=h)
    assert 400 <= r.status_code < 500, f"非法备货方式应拒绝: {r.status_code}"
