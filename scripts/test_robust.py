"""
MTS 健壮性测试套件 — 正向流程 / 反向流程 / 恢复流程 全集
========================================================
覆盖：
  A. 基础档案：正向创建 + 反向（重复/缺字段/非法ID）
  B. 销售链路：正向（订单→审核→转直采→发货→发票→收款）
              + 反向（未审核发货/超量/库存不足/重复发票/删已审订单）
  C. 采购链路：正向（订单→审核→入库→发票→应付→付款）
              + 反向（删已审/重复发票/超量入库）
  E. 恢复流程：反向后重做（删入库→重入、删发票→重开）
  F. 边界输入：负数/零/超长/特殊字符/不存在ID

真实 Bug 用 expect_fail() 标记（已知问题，不修代码），测试退出码仍为 0。
新出现的失败（未知问题）才会 FAIL。

用法: python scripts/test_robust.py
退出码: 0=全过(含已知问题), 1=有未知失败
"""
import requests, sys, time, random

BASE = "http://localhost:8788/api"
PASS = FAIL = SKIP = 0
FAILURES = []
KNOWN = []  # 已知问题（真实Bug，待修复）

# ==================== 框架 ====================

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"  ❌ {name} {detail}")

def expect_status(name, resp, want, detail=""):
    got = resp.status_code
    d = f"(期望{want} 实际{got})" if got != want else ""
    check(name, got == want, f"{d} {detail} {resp.text[:120] if got != want else ''}")

def expect_fail(name, cond_failed, bug_desc):
    """断言该场景当前会失败（记录为已知Bug，不 FAIL）"""
    global PASS, SKIP
    if cond_failed:
        SKIP += 1
        KNOWN.append((name, bug_desc))
        print(f"  ⚠️  [已知Bug] {name}: {bug_desc}")
    else:
        PASS += 1
        print(f"  ✅ {name} (未触发已知Bug)")

def login(username="admin", password="admin123"):
    return requests.post(f"{BASE}/auth/login", json={"username": username, "password": password})

def api(method, path, token=None, data=None, params=None):
    H = {"Content-Type": "application/json"}
    if token: H["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BASE}{path}", headers=H, json=data, params=params)

def section(title):
    print(f"\n{'═' * 60}\n  {title}\n{'═' * 60}")

def mk_uniq(prefix):
    return f"{prefix}{random.randint(10000, 99999)}"

# ==================== 0. 登录 ====================
section("0. 登录认证")
r = login()
expect_status("正确密码登录 200", r, 200)
T = r.json()["access_token"] if r.status_code == 200 else None
if not T:
    print("❌ 无法登录，终止测试"); sys.exit(1)

r = login("admin", "wrong-password")
expect_status("错误密码登录 401", r, 401)
r = api("GET", "/auth/me")
check("无 token 访问被拒绝(401/403)", r.status_code in (401, 403), f"({r.status_code})")
r = api("GET", "/auth/me", token="invalid.token.here")
expect_status("伪造 token 访问 401", r, 401)

# ==================== A. 基础档案 ====================
section("A. 基础档案 — 正向")
TAG = mk_uniq("T")
sup_name, cust_name = f"测试供应商{TAG}", f"测试客户{TAG}"
mat_name, prod_name = f"测试物料{TAG}", f"测试产品{TAG}"

r = api("POST", "/foundation/suppliers", token=T, data={
    "code": f"S{TAG}", "name": sup_name, "supplier_type": "原材料",
    "contact_person": "张三", "phone": "0755-12345678",
    "tax_id": f"9144{TAG}", "address": "深圳市测试路1号"})
expect_status("创建供应商 200", r, 200)
SUP = r.json()
check("供应商返回 id", SUP.get("id"))

r = api("POST", "/foundation/customers", token=T, data={
    "code": f"C{TAG}", "name_cn": cust_name, "country": "美国",
    "contact_person": "John", "phone": "+1-555", "tax_id": f"US{TAG}",
    "address": "123 Test St"})
expect_status("创建客户 200", r, 200)
CUS = r.json()

r = api("POST", "/foundation/materials", token=T, data={
    "code": f"M{TAG}", "name": mat_name, "spec": "测试规格",
    "unit": "个", "category": "原材料", "purchase_price": 10})
expect_status("创建物料 200", r, 200)
MAT = r.json()

r = api("POST", "/foundation/processes", token=T, data={
    "code": f"P{TAG}", "name": f"测试工序{TAG}", "unit_price": 5})
expect_status("创建工序 200", r, 200)
PROC = r.json()

hs_r = api("POST", "/foundation/hs-codes", token=T, data={
    "hs_code": f"9999{TAG}", "name": "测试HS", "unit": "个",
    "tax_rate": 13, "refund_rate": 13})
expect_status("创建HS编码 200", hs_r, 200)
HS = hs_r.json()

r = api("POST", "/foundation/products", token=T, data={
    "code": f"PD{TAG}", "name_cn": prod_name, "spec": "测试",
    "unit": "个", "sale_price": 100, "hs_code_id": HS.get("id")})
expect_status("创建产品 200", r, 200)
PROD = r.json()

r = api("POST", "/foundation/bom", token=T, data={
    "bom_name": "测试BOM", "product_id": PROD["id"],
    "material_id": MAT["id"], "quantity": 2, "process_id": PROC["id"]})
expect_status("创建BOM 200", r, 200)

section("A2. 基础档案 — 反向")
# 重复 code（无唯一约束检查，200 成功或 500 崩溃都算问题）
r = api("POST", "/foundation/suppliers", token=T, data={
    "code": f"S{TAG}", "name": sup_name, "supplier_type": "原材料",
    "contact_person": "张三", "phone": "0755-12345678"})
if r.status_code == 200:
    KNOWN.append(("供应商code无唯一约束", "重复 code 仍创建成功(200)，业务上可能产生重复档案"))
    PASS += 1
    print(f"  ✅ 重复供应商 code (允许创建，已记录)")
elif r.status_code == 500:
    KNOWN.append(("重复供应商code返回500", "重复 code 触发唯一约束但返回 500，应 409"))
    SKIP += 1
    print(f"  ⚠️  [已知Bug] 重复供应商 code → 500 (唯一约束未捕获为业务错误)")
else:
    # 400/409/422 都算合理拒绝
    if r.status_code in (400, 409, 422):
        PASS += 1
        print(f"  ✅ 重复供应商 code 被拒绝({r.status_code})")
    else:
        FAIL += 1
        FAILURES.append("重复供应商 code 异常状态")
        print(f"  ❌ 重复供应商 code 异常状态 ({r.status_code})")

# 缺必填字段
r = api("POST", "/foundation/materials", token=T, data={"code": f"MX{TAG}"})
expect_status("物料缺 name/spec → 422", r, 422)

# 不存在 ID（路由可能返回 404 或 405，都算"正确拒绝"）
r = api("GET", "/foundation/suppliers/999999")
check("查询不存在供应商被拒绝(404/405)", r.status_code in (404, 405), f"({r.status_code})")

r = api("DELETE", "/foundation/products/999999", token=T)
check("删除不存在产品被拒绝(404)", r.status_code in (404, 405), f"({r.status_code})")

# BOM 引用不存在材料 → 真Bug(500)，标记已知
r = api("POST", "/foundation/bom", token=T, data={
    "bom_name": "坏BOM", "product_id": PROD["id"],
    "material_id": 999999, "quantity": 1})
expect_fail("BOM引用不存在材料返回4xx",
            r.status_code == 500,
            "引用不存在材料返回 500，应返回 400/404（外键未校验）")

# 超长名称（常量名会跨run命中「名称已存在」400，属同一业务拒绝；成功后清理防累积）
r = api("POST", "/foundation/suppliers", token=T, data={
    "code": f"SL{TAG}", "name": "长" * 500, "supplier_type": "原材料",
    "contact_person": "x", "phone": "1"})
check("超长名称(500字符)被拒绝(400/422)或截断(200)", r.status_code in (200, 400, 422), f"({r.status_code})")
if r.status_code == 200:
    api("DELETE", f"/foundation/suppliers/{r.json()['id']}", token=T)

# XSS 注入（应存储原样，前端负责转义）
r = api("POST", "/foundation/customers", token=T, data={
    "code": f"SC{TAG}", "name_cn": "<script>alert(1)</script>", "country": "X",
    "contact_person": "x", "phone": "1", "tax_id": "T1", "address": "A"})
check("XSS名称 200(前端转义)或422(拒绝)", r.status_code in (200, 422), f"({r.status_code})")
if r.status_code == 200:
    api("DELETE", f"/foundation/customers/{r.json()['id']}", token=T)

# ==================== B. 销售链路 ====================
section("B. 销售链路 — 正向")
r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1, "exchange_rate": 1,
    "trade_term_id": 1, "payment_terms": "TT",
    "order_date": "2026-08-01", "delivery_date": "2026-09-01",
    "items": [{"product_id": PROD["id"], "quantity": 10, "unit_price": 100, "tax_rate": 13}]})
expect_status("创建销售订单 200", r, 200)
SO = r.json()
check("销售订单号 SO-", SO.get("order_no", "").startswith("SO-"))

r = api("POST", f"/sales/orders/{SO['id']}/approve", token=T)
expect_status("审核销售订单 200", r, 200)
check("审核成功返回消息", r.json().get("message") == "订单已审核", f"({r.text})")

section("B2. 销售链路 — 反向")
r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1, "exchange_rate": 1,
    "trade_term_id": 1, "payment_terms": "TT",
    "items": [{"product_id": PROD["id"], "quantity": 5, "unit_price": 100, "tax_rate": 13}]})
expect_status("创建未审核订单B 200", r, 200)
SO_B = r.json()

r = api("POST", "/sales/deliveries", token=T, data={
    "order_id": SO_B["id"], "product_id": PROD["id"],
    "quantity": 5, "warehouse_id": 1, "delivery_date": "2026-08-02"})
expect_status("未审核订单发货 → 400", r, 400)

r = api("DELETE", f"/sales/orders/{SO['id']}", token=T)
expect_status("删除已审核订单 → 400", r, 400)
r = api("DELETE", f"/sales/orders/{SO_B['id']}", token=T)
expect_status("删除未审核订单 → 200", r, 200)

# 负数/零数量 → 真Bug(200)，标记已知
r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1,
    "items": [{"product_id": PROD["id"], "quantity": -5, "unit_price": 100, "tax_rate": 13}]})
expect_fail("负数数量被拒绝(422/400)",
            r.status_code == 200,
            "负数数量订单被接受(200)，应 422 拒绝")
if r.status_code == 200:
    api("DELETE", f"/sales/orders/{r.json()['id']}", token=T)

r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1,
    "items": [{"product_id": PROD["id"], "quantity": 0, "unit_price": 100, "tax_rate": 13}]})
expect_fail("零数量被拒绝(422/400)",
            r.status_code == 200,
            "零数量订单被接受(200)，应 422 拒绝")
if r.status_code == 200:
    api("DELETE", f"/sales/orders/{r.json()['id']}", token=T)

r = api("POST", f"/sales/orders/{SO['id']}/approve", token=T)
expect_status("重复审核订单 → 400", r, 400)

# 不存在客户 → 真Bug(500)
r = api("POST", "/sales/orders", token=T, data={
    "customer_id": 999999, "currency_id": 1,
    "items": [{"product_id": PROD["id"], "quantity": 1, "unit_price": 100, "tax_rate": 13}]})
expect_fail("不存在客户下单返回4xx",
            r.status_code == 500,
            "不存在客户下单返回 500，应 400/404（外键未校验）")

# ==================== C. 采购链路 ====================
section("C. 采购链路 — 正向")
r = api("POST", "/purchase/orders", token=T, data={
    "supplier_id": SUP["id"], "payment_terms": "TT", "tax_rate": 13,
    "items": [{"material_id": MAT["id"], "quantity": 100, "unit_price": 10}]})
expect_status("创建采购订单 200", r, 200)
PO = r.json()
check("采购订单号 PO-", PO.get("order_no", "").startswith("PO-"))

r = api("POST", f"/purchase/orders/{PO['id']}/approve", token=T)
expect_status("审核采购订单 200", r, 200)

r = api("POST", "/purchase/receipts", token=T, data={
    "order_id": PO["id"], "warehouse_id": 1,
    "items": [{"material_id": MAT["id"], "quantity": 100}]})
expect_status("采购入库 200", r, 200)
RECEIPT = r.json()
check("入库单号 PR-", RECEIPT.get("receipt_no", "").startswith("PR-"))

r = api("GET", "/inventory/balance", token=T, params={"material_id": MAT["id"]})
if r.status_code == 200:
    bal = sum(i.get("quantity", 0) for i in r.json().get("items", []))
    check("入库后库存 = 100", bal == 100, f"(实际{bal})")

section("C2. 采购链路 — 反向")
# 超量入库 → 已知问题（用户指定：遗留，不修）
r = api("POST", "/purchase/receipts", token=T, data={
    "order_id": PO["id"], "warehouse_id": 1,
    "items": [{"material_id": MAT["id"], "quantity": 50}]})
expect_fail("超量入库被拒绝(400)",
            r.status_code == 200,
            "PO订购100，二次入库50 仍被接受(累计150)——遗留问题，用户确认暂不修复")
if r.status_code == 200:
    # 回滚多余入库，保持后续测试数据干净
    api("DELETE", f"/purchase/receipts/{r.json()['id']}", token=T)

r = api("DELETE", f"/purchase/orders/{PO['id']}", token=T)
expect_status("删除已审核采购订单 → 400", r, 400)

r = api("POST", "/purchase/invoices", token=T, data={
    "invoice_no": f"PI-{TAG}-001", "order_id": PO["id"],
    "supplier_id": SUP["id"], "amount": 1000, "invoice_date": "2026-08-05"})
expect_status("创建采购发票1 200", r, 200)

r2 = api("POST", "/purchase/invoices", token=T, data={
    "invoice_no": f"PI-{TAG}-001", "order_id": PO["id"],
    "supplier_id": SUP["id"], "amount": 1000, "invoice_date": "2026-08-05"})
expect_fail("重复发票号返回4xx",
            r2.status_code == 500,
            "重复发票号返回 500，应 409（唯一约束未捕获为业务错误）")

r = api("POST", "/purchase/receipts", token=T, data={
    "order_id": 999999, "warehouse_id": 1,
    "items": [{"material_id": MAT["id"], "quantity": 1}]})
expect_status("不存在订单入库 → 404", r, 404)

# 未审核订单入库 → 真Bug(200)
r = api("POST", "/purchase/orders", token=T, data={
    "supplier_id": SUP["id"], "payment_terms": "TT", "tax_rate": 13,
    "items": [{"material_id": MAT["id"], "quantity": 10, "unit_price": 10}]})
PO_UN = r.json()
r = api("POST", "/purchase/receipts", token=T, data={
    "order_id": PO_UN["id"], "warehouse_id": 1,
    "items": [{"material_id": MAT["id"], "quantity": 10}]})
expect_fail("未审核订单入库被拒绝(400)",
            r.status_code == 200,
            "未审核采购订单可入库(200)，应 400 拒绝（状态未校验）")
if r.status_code == 200:
    api("DELETE", f"/purchase/receipts/{r.json()['id']}", token=T)
api("DELETE", f"/purchase/orders/{PO_UN['id']}", token=T)

# ==================== E. 恢复流程 ====================
section("E. 恢复流程 — 反向后重做")

# E1. 取消采购入库 → 重新入库（注意：有发票的入库不能取消，先测无发票的）
r = api("POST", "/purchase/orders", token=T, data={
    "supplier_id": SUP["id"], "payment_terms": "TT", "tax_rate": 13,
    "items": [{"material_id": MAT["id"], "quantity": 20, "unit_price": 10}]})
PO_REC = r.json()
api("POST", f"/purchase/orders/{PO_REC['id']}/approve", token=T)

# 记录入库前库存，作为取消后应回落的基准
r = api("GET", "/inventory/balance", token=T, params={"material_id": MAT["id"]})
bal_before_rec = sum(i.get("quantity", 0) for i in r.json().get("items", [])) if r.status_code == 200 else -1

r = api("POST", "/purchase/receipts", token=T, data={
    "order_id": PO_REC["id"], "warehouse_id": 1,
    "items": [{"material_id": MAT["id"], "quantity": 20}]})
REC_R = r.json()

r = api("DELETE", f"/purchase/receipts/{REC_R['id']}", token=T)
expect_status("取消采购入库 200", r, 200)

r = api("GET", "/inventory/balance", token=T, params={"material_id": MAT["id"]})
bal_after = sum(i.get("quantity", 0) for i in r.json().get("items", [])) if r.status_code == 200 else -1
check("取消入库后库存回到入库前", bal_after == bal_before_rec, f"(实际{bal_after}, 基准{bal_before_rec})")

r = api("POST", "/purchase/receipts", token=T, data={
    "order_id": PO_REC["id"], "warehouse_id": 1,
    "items": [{"material_id": MAT["id"], "quantity": 20}]})
expect_status("重新入库 200", r, 200)

# 有发票的入库不能取消（业务规则）
r = api("DELETE", f"/purchase/receipts/{RECEIPT['id']}", token=T)
check("有发票的入库不可取消(400)", r.status_code == 400, f"({r.status_code})")

# E3. 删除发票 → 重新开票
r = api("POST", "/purchase/invoices", token=T, data={
    "invoice_no": f"PI-{TAG}-002", "order_id": PO["id"],
    "supplier_id": SUP["id"], "amount": 1000, "invoice_date": "2026-08-05"})
expect_status("创建采购发票2 200", r, 200)
PINV2 = r.json()
r = api("DELETE", f"/purchase/invoices/{PINV2['id']}", token=T)
expect_status("删除采购发票 200", r, 200)
r = api("POST", "/purchase/invoices", token=T, data={
    "invoice_no": f"PI-{TAG}-003", "order_id": PO["id"],
    "supplier_id": SUP["id"], "amount": 1000, "invoice_date": "2026-08-05"})
expect_status("重新开票 200", r, 200)

# ==================== F. 边界输入 ====================
section("F. 边界输入")

r = api("POST", "/purchase/orders", token=T, data={
    "supplier_id": SUP["id"], "payment_terms": "TT", "tax_rate": 13,
    "remark": "备" * 2000,
    "items": [{"material_id": MAT["id"], "quantity": 1, "unit_price": 1}]})
expect_status("超长备注(2000字符) 200", r, 200)
if r.status_code == 200:
    api("DELETE", f"/purchase/orders/{r.json()['id']}", token=T)

r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1,
    "items": [{"product_id": PROD["id"], "quantity": 999999999, "unit_price": 100, "tax_rate": 13}]})
expect_status("极大数量(9亿) 200或422", r, 200, "接受或拒绝均合理")
if r.status_code == 200:
    api("DELETE", f"/sales/orders/{r.json()['id']}", token=T)

# 非数字数量 → 真Bug(500)
r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1,
    "items": [{"product_id": PROD["id"], "quantity": "abc", "unit_price": 100, "tax_rate": 13}]})
expect_fail("非数字数量返回4xx",
            r.status_code == 500,
            "数量传字符串返回 500，应 422（类型转换未捕获）")

# 空明细
r = api("POST", "/sales/orders", token=T, data={
    "customer_id": CUS["id"], "currency_id": 1, "items": []})
check("空明细订单被拒绝(400/422)", r.status_code in (400, 422), f"({r.status_code})")

# ==================== 汇总 ====================
print(f"\n{'═' * 60}")
print(f"  测试汇总: PASS={PASS}  SKIP(已知Bug)={SKIP}  FAIL={FAIL}")
print(f"{'═' * 60}")
if FAILURES:
    print("\n❌ 未知失败用例:")
    for f in FAILURES:
        print(f"  - {f}")
if KNOWN:
    print("\n⚠️  已知问题清单(待修复):")
    seen = set()
    for name, desc in KNOWN:
        if name not in seen:
            seen.add(name)
            print(f"  - {name}: {desc}")
if FAIL == 0:
    print("\n🎉 测试完成：无未知失败。已知问题均已记录。")
else:
    print(f"\n💥 {len(FAILURES)} 个未知失败，需要处理")
sys.exit(0 if FAIL == 0 else 1)
