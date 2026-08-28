"""边界数据测试：离谱输入杀不死系统

逻辑：对核心写接口注入离谱数据（负数/零/超大/超长/空值/类型错误/
非法枚举/XSS/SQL注入），验收标准：
- 4xx（被 Pydantic 或业务校验拒绝）或 2xx（安全处理）都可以
- 5xx = 测试失败（后端崩溃 = 漏洞）

另有越权测试：低权限角色调用管理接口必须 403。
"""

import pytest

BASE = "/api"

# ==================== 基础数据 ====================

@pytest.fixture(scope="module")
def base_data(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    cny = client.post(f"{BASE}/foundation/currencies", json={
        "code": "CNY-BND", "name": "人民币-边界", "symbol": "¥", "is_base": 1}, headers=h).json()["id"]
    wh = client.post(f"{BASE}/foundation/warehouses", json={
        "code": "WH-BND", "name": "主仓-边界", "wh_type": "原料仓",
        "address": "浙江省绍兴市柯桥区", "manager": "边界测试员"}, headers=h).json()["id"]
    sup = client.post(f"{BASE}/foundation/suppliers", json={
        "name": "边界供应商", "contact_person": "王", "phone": "13800000000",
        "tax_id": "91330100BND", "address": "杭州", "supplier_type": "供应商"}, headers=h).json()["id"]
    cust = client.post(f"{BASE}/foundation/customers", json={
        "name_cn": "边界客户", "country": "中国", "contact_person": "李",
        "phone": "13900000000", "tax_id": "91330000BND", "address": "上海"}, headers=h).json()["id"]
    mat = client.post(f"{BASE}/foundation/materials", json={
        "name": "边界材料", "spec": "A级", "unit": "KG",
        "category": "原材料", "purchase_price": 10}, headers=h).json()["id"]
    prod = client.post(f"{BASE}/foundation/products", json={
        "name_cn": "边界产品", "spec": "标准", "unit": "米",
        "sale_price": 50}, headers=h).json()["id"]
    return {"cny": cny, "wh": wh, "sup": sup, "cust": cust, "mat": mat, "prod": prod}


def _call(client, method, path, payload, h):
    """发请求；500 时 TestClient 会 raise，转成 (500, str(e))"""
    try:
        if method == "POST":
            resp = client.post(path, json=payload, headers=h)
        elif method == "PUT":
            resp = client.put(path, json=payload, headers=h)
        elif method == "GET":
            resp = client.get(path, headers=h)
        else:
            resp = client.delete(path, headers=h)
        return resp.status_code, (resp.text[:150] if resp.status_code >= 400 else "")
    except Exception as e:
        return 500, f"{type(e).__name__}: {e}"


# ==================== 离谱数据用例 ====================
# (用例名, 方法, 路径模板, 合法payload, 污染字段, 污染值)

XSS = "<script>alert('xss')</script>"
SQLI = "'; DROP TABLE fd_material;--"
LONG300 = "长" * 300
LONG5000 = "长" * 5000

FUZZ_CASES = [
    # ---- 基础档案 ----
    ("材料-数量负数", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "purchase_price", -5),
    ("材料-数量零", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "purchase_price", 0),
    ("材料-数量超大", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "purchase_price", 1e18),
    ("材料-数量字符串", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "purchase_price", "abc"),
    ("材料-名称超长", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "name", LONG5000),
    ("材料-名称纯空格", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "name", "   "),
    ("材料-名称XSS", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "name", XSS),
    ("材料-名称SQL注入", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "name", SQLI),
    ("材料-名称为空串", "POST", "/foundation/materials",
     {"name": "M", "spec": "S", "unit": "KG", "category": "原材料", "purchase_price": 10},
     "name", ""),
    # ---- 产品 ----
    ("产品-售价负数", "POST", "/foundation/products",
     {"name_cn": "P", "spec": "S", "unit": "米", "sale_price": 50},
     "sale_price", -1),
    ("产品-售价字符串", "POST", "/foundation/products",
     {"name_cn": "P", "spec": "S", "unit": "米", "sale_price": 50},
     "sale_price", "abc"),
    ("产品-退税率超大", "POST", "/foundation/products",
     {"name_cn": "P", "spec": "S", "unit": "米", "sale_price": 50},
     "refund_rate", 999),
    ("产品-名称XSS", "POST", "/foundation/products",
     {"name_cn": "P", "spec": "S", "unit": "米", "sale_price": 50},
     "name_cn", XSS),
    # ---- 客户/供应商 ----
    ("客户-名称超长", "POST", "/foundation/customers",
     {"name_cn": "C", "country": "中国", "contact_person": "王",
      "phone": "138", "tax_id": "T", "address": "A"},
     "name_cn", LONG300),
    ("供应商-税号SQL注入", "POST", "/foundation/suppliers",
     {"name": "S", "contact_person": "王", "phone": "138",
      "tax_id": "T", "address": "A", "supplier_type": "供应商"},
     "tax_id", SQLI),
    ("供应商-类型非法枚举", "POST", "/foundation/suppliers",
     {"name": "S", "contact_person": "王", "phone": "138",
      "tax_id": "T", "address": "A", "supplier_type": "供应商"},
     "supplier_type", "乱写的类型"),
    # ---- 工序/仓库 ----
    ("工序-单价负数", "POST", "/foundation/processes",
     {"code": "P", "name": "工序", "unit_price": 1},
     "unit_price", -99),
    ("仓库-类型非法枚举", "POST", "/foundation/warehouses",
     {"code": "W", "name": "仓库", "wh_type": "原料仓"},
     "wh_type", "乱写的类型"),
    ("仓库-编码XSS", "POST", "/foundation/warehouses",
     {"code": "W", "name": "仓库", "wh_type": "原料仓"},
     "code", XSS),
    # ---- BOM ----
    ("BOM-数量负数", "POST", "/foundation/bom",
     {"product_id": None, "material_id": None, "quantity": 0.1, "bom_name": "B"},
     "quantity", -1),
    ("BOM-数量零", "POST", "/foundation/bom",
     {"product_id": None, "material_id": None, "quantity": 0.1, "bom_name": "B"},
     "quantity", 0),
    ("BOM-数量字符串", "POST", "/foundation/bom",
     {"product_id": None, "material_id": None, "quantity": 0.1, "bom_name": "B"},
     "quantity", "abc"),
    ("BOM-产品不存在", "POST", "/foundation/bom",
     {"product_id": None, "material_id": None, "quantity": 0.1, "bom_name": "B"},
     "product_id", 999999),
    # ---- 销售订单 ----
    ("销售-数量负数", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", -5),
    ("销售-数量零", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", 0),
    ("销售-数量超大", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", 999999999),
    ("销售-数量字符串", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", "abc"),
    ("销售-单价负数", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.unit_price", -10),
    ("销售-客户不存在", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "customer_id", 999999),
    ("销售-备注XSS", "POST", "/sales/orders",
     {"customer_id": None, "currency_id": None,
      "items": [{"product_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "remark", XSS),
    # ---- 采购订单 ----
    ("采购-数量负数", "POST", "/purchase/orders",
     {"supplier_id": None, "currency_id": None,
      "items": [{"material_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", -3),
    ("采购-数量零", "POST", "/purchase/orders",
     {"supplier_id": None, "currency_id": None,
      "items": [{"material_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", 0),
    ("采购-数量字符串", "POST", "/purchase/orders",
     {"supplier_id": None, "currency_id": None,
      "items": [{"material_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.quantity", "abc"),
    ("采购-税率负数", "POST", "/purchase/orders",
     {"supplier_id": None, "currency_id": None,
      "items": [{"material_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "items.tax_rate", -13),
    ("采购-供应商不存在", "POST", "/purchase/orders",
     {"supplier_id": None, "currency_id": None,
      "items": [{"material_id": None, "quantity": 10, "unit_price": 5, "tax_rate": 13}]},
     "supplier_id", 999999),
    # ---- 单据操作 ----
    ("操作-审核不存在的订单", "POST", "/sales/orders/999999/approve",
     {}, None, None),
    ("操作-派产不存在的生产单", "POST", "/production/productions/999999/release",
     {}, None, None),
    ("操作-关闭不存在的采购需求", "POST", "/purchase/requisitions/999999/close",
     {}, None, None),
]


def _apply_fuzz(payload, field, value):
    """把 payload 按 'items.quantity' 风格路径污染字段"""
    if field is None:
        return payload
    parts = field.split(".")
    target = payload
    for p in parts[:-1]:
        if isinstance(target, list):
            target = target[0]
        target = target[p]
    if isinstance(target, list):
        target = target[0]
    target[parts[-1]] = value
    return payload


@pytest.mark.parametrize("case_name,method,path,payload,field,value",
                         [(c[0], c[1], c[2], c[3], c[4], c[5]) for c in FUZZ_CASES],
                         ids=[c[0] for c in FUZZ_CASES])
def test_fuzz_no_500(client, auth_headers, base_data, case_name, method, path, payload, field, value):
    """离谱数据：允许 2xx/4xx，绝不允许 5xx"""
    import copy
    h = auth_headers
    payload = copy.deepcopy(payload)
    # 注入基础数据 id（payload 键 → base_data 键）
    KEY_MAP = {"customer_id": "cust", "supplier_id": "sup", "currency_id": "cny",
               "product_id": "prod", "material_id": "mat", "warehouse_id": "wh"}

    def _fill(obj):
        for k, v in obj.items():
            if v is None and k in KEY_MAP:
                obj[k] = base_data[KEY_MAP[k]]
        return obj

    _fill(payload)
    if "items" in payload:
        for it in payload["items"]:
            _fill(it)
    payload = _apply_fuzz(payload, field, value)

    code, body = _call(client, method, path, payload, h)
    assert code < 500, (
        f"[{case_name}] 离谱输入导致 5xx: {code} {body}\npayload={payload}")


# ==================== 越权测试 ====================

def test_rbac_low_privilege_blocked(client, admin_token):
    """库管员（仅库存权限）调用管理接口必须 403

    SP 现状（2026-08）：权限控制已覆盖 auth 用户/角色、系统配置（admin 专属）、
    采购审核、销售审核；基础档案/库存等路由仅要求登录（get_current_user），
    低权限用户可读写 —— 记录为 docs/complete-test-plan.md 专项待办 BUG-03。
    """
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # 建库管员用户
    roles = client.get(f"{BASE}/auth/roles", headers=admin_h).json()
    keeper_role = next(r for r in roles if r["code"] == "warehouse_keeper")
    u = client.post(f"{BASE}/auth/users", json={
        "username": "keeper1", "password": "keeper123",
        "display_name": "库管员1", "role_id": keeper_role["id"]}, headers=admin_h)
    assert u.status_code < 400, u.text

    # 登录拿 token
    login = client.post(f"{BASE}/auth/login", json={
        "username": "keeper1", "password": "keeper123"})
    assert login.status_code == 200, login.text
    keeper_h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # 越权调用管理接口（这些接口有权限保护，必须拒绝）
    blocked = [
        ("POST", f"{BASE}/auth/users", {"username": "x", "password": "x", "display_name": "x"}),
        ("GET", f"{BASE}/auth/users", None),
        ("GET", f"{BASE}/auth/users/1", None),
        ("GET", f"{BASE}/auth/roles", None),
        ("POST", f"{BASE}/system/wecom", {}),
    ]
    for method, path, payload in blocked:
        code, _ = _call(client, method, path, payload, keeper_h)
        # 权限校验可能在 schema 校验之后（422 也算被拒）；核心是低权限调用不能成功
        assert code in (403, 422), (
            f"库管员调用 {method} {path} 应 403/422，实际 {code}")

    # 采购/销售审核同样受权限保护（无对应菜单权限 → 403）
    # 用管理员建一个采购订单，库管员审核必须被拒
    sup = client.post(f"{BASE}/foundation/suppliers", json={
        "name": "越权测试供应商", "contact_person": "王", "phone": "13800000001",
        "tax_id": "91330100YW", "address": "杭州", "supplier_type": "供应商"}, headers=admin_h).json()
    mat = client.post(f"{BASE}/foundation/materials", json={
        "name": "越权材料", "spec": "S", "unit": "KG", "category": "原材料",
        "purchase_price": 10}, headers=admin_h).json()
    po = client.post(f"{BASE}/purchase/orders", json={
        "supplier_id": sup["id"], "currency_id": 1, "items": [
            {"material_id": mat["id"], "quantity": 10, "unit_price": 12, "tax_rate": 13}],
    }, headers=admin_h)
    assert po.status_code < 400, po.text
    po_id = po.json()["id"]
    code, _ = _call(client, "POST", f"{BASE}/purchase/orders/{po_id}/approve", {}, keeper_h)
    assert code in (403, 422), f"库管员审核采购订单应 403/422，实际 {code}"

    # 正常权限内的接口可用（不误伤）
    code, _ = _call(client, "GET", f"{BASE}/inventory/balance", None, keeper_h)
    assert code < 500, f"库管员访问库存应可用，实际 {code}"


# ==================== 无 Update schema 实体的编辑回归 ====================

def test_crud_update_without_update_schema(client, auth_headers):
    """无 Update schema 的实体（Warehouse/Department/Currency/TradeTerm/Employee）
    编辑接口必须接受 body 且 200（回归：base_crud update_schema=None 曾导致
    PUT 422 "missing query data" —— data 被 FastAPI 当成 query 参数）"""
    h = auth_headers
    # 仓库：创建 → 编辑 → 校验字段更新
    wh = client.post(f"{BASE}/foundation/warehouses", json={
        "code": "WH-UPD1", "name": "编辑回归仓", "wh_type": "原料仓"}, headers=h)
    assert wh.status_code < 400, wh.text
    wh_id = wh.json()["id"]
    resp = client.put(f"{BASE}/foundation/warehouses/{wh_id}", json={
        "name": "编辑回归仓改", "address": "杭州", "manager": "张三"}, headers=h)
    assert resp.status_code == 200, f"仓库编辑应 200，实际 {resp.status_code}: {resp.text[:200]}"
    got = client.get(f"{BASE}/foundation/warehouses/{wh_id}", headers=h).json()
    assert got["name"] == "编辑回归仓改" and got["address"] == "杭州" and got["manager"] == "张三", got

    # 币种：创建 → 编辑
    cny = client.post(f"{BASE}/foundation/currencies", json={
        "code": "CUPD1", "name": "编辑回归币", "symbol": "$", "is_base": 0}, headers=h)
    assert cny.status_code < 400, cny.text
    resp = client.put(f"{BASE}/foundation/currencies/{cny.json()['id']}", json={
        "name": "编辑回归币改"}, headers=h)
    assert resp.status_code == 200, f"币种编辑应 200，实际 {resp.status_code}: {resp.text[:200]}"

    # 部门：创建 → 编辑
    dept = client.post(f"{BASE}/foundation/departments", json={
        "code": "DUPD1", "name": "编辑回归部"}, headers=h)
    assert dept.status_code < 400, dept.text
    resp = client.put(f"{BASE}/foundation/departments/{dept.json()['id']}", json={
        "name": "编辑回归部改"}, headers=h)
    assert resp.status_code == 200, f"部门编辑应 200，实际 {resp.status_code}: {resp.text[:200]}"
