"""一键初始化 + 全流程测试（匹配新版 API v3）"""
import requests, sys

BASE = "http://localhost:8788/api"
ok = 0; fail = 0

def api(method, path, data=None, params=None, quiet=False):
    global ok, fail
    r = requests.request(method, f"{BASE}{path}", headers=H, json=data, params=params)
    if r.status_code >= 400:
        fail += 1
        if not quiet:
            print(f"  ❌ {method} {path}: {r.status_code} {r.text[:200]}")
        return None
    ok += 1
    return r.json() if r.status_code < 300 else None

# ===== 登录 =====
r = requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"admin123"})
if r.status_code != 200:
    print("❌ 登录失败"); sys.exit(1)
T = r.json()["access_token"]
H = {"Content-Type": "application/json", "Authorization": f"Bearer {T}"}
print(f"✅ 登录成功\n")

# ===== 基础档案 =====
print("═" * 50 + "\n  基础档案\n" + "═" * 50)

api("POST", "/foundation/currencies", {"code":"CNY","name":"人民币","symbol":"¥","is_base":1})
api("POST", "/foundation/currencies", {"code":"USD","name":"美元","symbol":"$"})
api("POST", "/foundation/trade-terms", {"code":"FOB","name":"FOB"})
api("POST", "/foundation/warehouses", {"code":"RM","name":"原料仓","wh_type":"原料仓"})
api("POST", "/foundation/warehouses", {"code":"FG","name":"成品仓","wh_type":"成品仓"})
api("POST", "/foundation/suppliers", {"code":"S001","name":"深圳电子材料","supplier_type":"原材料","contact_person":"张三","phone":"0755-12345678","tax_id":"91440300123456789X","address":"深圳市南山区科技园"})
api("POST", "/foundation/suppliers", {"code":"S002","name":"东莞精密加工","supplier_type":"委外","contact_person":"李四","phone":"0769-87654321","tax_id":"914419001234567890","address":"东莞市长安镇工业区"})
api("POST", "/foundation/customers", {"code":"C001","name_cn":"美国贸易公司","country":"美国","contact_person":"John Smith","phone":"+1-212-555-1234","tax_id":"US12-3456789","address":"123 Broadway, New York, NY 10007"})
api("POST", "/foundation/materials", {"code":"M001","name":"PCB电路板","spec":"FR-4 双面板 1.6mm","unit":"片","purchase_price":15})
api("POST", "/foundation/materials", {"code":"M002","name":"电阻套装","spec":"1/4W 0805 100种","unit":"包","purchase_price":5})
api("POST", "/foundation/materials", {"code":"M003","name":"塑料外壳","spec":"ABS 黑色 120×80×30","unit":"个","purchase_price":3})
hs = api("POST", "/foundation/hs-codes", {"hs_code":"8471","name":"计算机","unit":"台","refund_rate":13,"tax_rate":13})
proc_ent = api("POST", "/foundation/processes", {"code":"P001","name":"SMT贴片","unit_price":8})
prod1 = api("POST", "/foundation/products", {"code":"PRD001","name_cn":"智能控制器","spec":"工业级 48MHz","unit":"台","sale_price":120,"hs_code_id":hs["id"]})
prod2 = api("POST", "/foundation/products", {"code":"PRD002","name_cn":"传感器模块","spec":"I2C 温湿度","unit":"个","sale_price":80,"hs_code_id":hs["id"]})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod1["id"],"material_id":1,"quantity":2,"process_id":proc_ent["id"]})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod1["id"],"material_id":2,"quantity":10})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod1["id"],"material_id":3,"quantity":1})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod2["id"],"material_id":2,"quantity":5})
print("✅ 基础档案创建完成")

# ===== 销售订单 → 审核 → 生产 =====
print("\n" + "═" * 50 + "\n  销售订单（多产品）→ 审核 → 生产订单\n" + "═" * 50)

so = api("POST", "/sales/orders", {
    "customer_id": 1,
    "currency_id": 2, "exchange_rate": 7.2,
    "trade_term_id": 1, "payment_terms": "TT",
    "order_date": "2026-07-22", "delivery_date": "2026-08-15",
    "items": [
        {"product_id": prod1["id"], "quantity": 50, "unit_price": 120, "tax_rate": 13},
        {"product_id": prod2["id"], "quantity": 100, "unit_price": 80, "tax_rate": 13},
    ]
})
print(f"✅ 销售订单: {so['order_no']} (2个产品)")

appr = api("POST", f"/sales/orders/{so['id']}/approve")
print(f"✅ 审核完成 → {appr['production_order_nos']}")

prods = api("GET", "/production/productions")
print(f"✅ 生产订单: {prods['items'][0]['order_no']} & {prods['items'][1]['order_no']}")

# ===== 采购订单 → 审核 → 入库 =====
print("\n" + "═" * 50 + "\n  采购订单 → 审核 → 入库\n" + "═" * 50)

po = api("POST", "/purchase/orders", {
    "supplier_id": 1, "payment_terms": "TT", "tax_rate": 13,
    "items": [
        {"material_id": 1, "quantity": 200, "unit_price": 15},
        {"material_id": 2, "quantity": 1000, "unit_price": 5},
        {"material_id": 3, "quantity": 100, "unit_price": 3},
    ]
})
print(f"✅ 采购订单: {po['order_no']}")
api("POST", f"/purchase/orders/{po['id']}/approve")
pr = api("POST", "/purchase/receipts", {
    "order_id": po["id"], "warehouse_id": 1,
    "items": [{"material_id": 1, "quantity": 200},
              {"material_id": 2, "quantity": 1000},
              {"material_id": 3, "quantity": 100}]
})
print(f"✅ 采购入库: {pr['receipt_no']}")

# ===== 库存验证 =====
bal = api("GET", "/inventory/balance")
print(f"\n📊 原料库存: {bal['total']} 条")
for b in bal.get("items", []):
    print(f"  {b.get('material_name') or b.get('product_name','')} [{b['batch_no']}] 数量={b['quantity']} 金额=¥{b['total_cost']}")

# ===== 生产流程 =====
print("\n" + "═" * 50 + "\n  生产流程（展开BOM → 工艺路线 → 派产 → 发料 → 完工 → 入库）\n" + "═" * 50)

for p in prods.get("items", []):
    pid = p["id"]
    
    # 展开BOM
    exp = api("POST", f"/production/productions/{pid}/expand-bom")
    if not exp:
        continue
    print(f"  📦 {p['order_no']}: {exp['message']}")
    
    # 保存工艺路线
    routes = api("PUT", f"/production/productions/{pid}/processes", {
        "items": [{"process_id": proc_ent["id"], "process_qty": p["quantity"], "unit_price": 8}]
    })
    if not routes:
        continue
    print(f"  🛠️  工艺路线: {routes['message']}")
    
    # 派产
    rel = api("POST", f"/production/productions/{pid}/release")
    if not rel:
        continue
    print(f"  🚀 派产: {rel['message']}")
    
    # 获取生产详情（含物料清单、工艺路线）
    detail = api("GET", f"/production/productions/{pid}")
    if not detail:
        continue
    
    # 发料 — 按物料清单逐个发料
    for mat in detail.get("materials", []):
        mid = mat["material_id"]
        qty = mat["planned_qty"]
        if qty <= 0:
            continue
        # 查原料库存（query param）
        mat_bal = api("GET", "/inventory/balance", params={"material_id": mid})
        if mat_bal and mat_bal.get("items"):
            batch = mat_bal["items"][0]
            if batch["quantity"] >= qty and detail.get("processes"):
                first_proc = detail["processes"][0]
                iss = api("POST", f"/production/productions/{pid}/processes/{first_proc['id']}/issue", {
                    "material_id": mid,
                    "batch_no": batch["batch_no"],
                    "quantity": qty,
                    "warehouse_id": 1,
                })
                if iss:
                    print(f"  📤 发料: {mat['material_name']} × {qty}")
    
    # 完工工序
    detail2 = api("GET", f"/production/productions/{pid}")
    if detail2 and detail2.get("processes"):
        for pr in detail2["processes"]:
            fin = api("POST", f"/production/productions/{pid}/processes/{pr['id']}/finish", {
                "unit_price": pr.get("unit_price", 8),
                "process_qty": p["quantity"],
            })
            if fin:
                print(f"  ✅ 完工: {pr['process_name']}")
    
    # 完工入库
    rcpt = api("POST", f"/production/productions/{pid}/receipt", {
        "quantity": p["quantity"],
        "warehouse_id": 2,
        "material_cost": 0,
        "process_cost": 0,
        "receipt_date": "2026-08-10",
    })
    if rcpt:
        print(f"  📦 入库: {rcpt['message']}")

# ===== 销售发货 → 报关 → 发票 → 收款 =====
print("\n" + "═" * 50 + "\n  销售发货 → 报关 → 发票 → 应收 → 收款\n" + "═" * 50)

# 查询成品库存
fg_bal = api("GET", "/inventory/balance", params={"type": "product"})
fg_batch = fg_bal["items"][0] if fg_bal and fg_bal.get("items") else None

if fg_batch:
    deliv = api("POST", "/sales/deliveries", {
        "order_id": so["id"], "order_item_id": 1, "product_id": prod1["id"],
        "batch_no": fg_batch["batch_no"], "quantity": 50, "warehouse_id": 2,
        "delivery_date": "2026-08-15",
    })
    print(f"✅ 销售发货: {deliv['delivery_no']}" if deliv else "  ❌ 发货失败")
else:
    print("  ⚠️  无成品库存，跳过销售发货")
    deliv = None

if deliv:
    cus = api("POST", "/sales/customs", {
        "customs_no": "CUS-20260815-001", "order_id": so["id"],
        "delivery_id": deliv["id"], "hs_code_id": hs["id"],
        "declare_amount": 10000, "declare_currency": 2,
        "declare_date": "2026-08-15",
    })
    print(f"✅ 报关: {cus['customs_no']}" if cus else "  ❌ 报关失败")

    sinv = api("POST", "/sales/invoices", {
        "invoice_no": "SI-20260815-001", "order_id": so["id"],
        "amount": 6000, "tax_rate": 13, "total_amount": 6780,
        "invoice_date": "2026-08-15",
    })
    if sinv:
        print(f"✅ 发票 → {sinv['ar_no']}")

        ars = api("GET", "/sales/ar")
        if ars and ars.get("items"):
            ar_id = ars["items"][0]["id"]
            coll = api("POST", "/sales/collections", {
                "customer_id": 1, "amount": 6780, "amount_fc": 942.0,
                "currency_id": 2, "exchange_rate": 7.2,
                "collection_date": "2026-08-20",
                "payment_method": "TT",
                "ar_account_id": ar_id,
            })
            print(f"✅ 收款: {coll['collection_no']}" if coll else "  ❌ 收款失败")

# ===== 退税计算 =====
print("\n" + "═" * 50 + "\n  退税计算\n" + "═" * 50)

calc = api("POST", "/tax-refund/calculate", {
    "export_amount_fob": 10000, "refund_rate": 13, "tax_rate": 13,
    "domestic_tax": 50000, "input_tax": 20000, "last_period_deduction": 0,
})
if calc:
    print(f"✅ 应退¥{calc['actual_refund']}, 免抵¥{calc['exemption_amount']}")

print(f"\n{'═' * 50}")
print(f"  🎉 全流程测试完成! 成功={ok} 失败={fail}")
print(f"{'═' * 50}")
