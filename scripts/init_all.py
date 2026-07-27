"""一键初始化 + 全流程测试（支持多产品销售订单）"""
import requests, sys

BASE = "http://localhost:8788/api"
ok = 0; fail = 0

def api(method, path, data=None, quiet=False):
    global ok, fail
    r = requests.request(method, f"{BASE}{path}", headers=H, json=data)
    if r.status_code >= 400:
        fail += 1
        if not quiet:
            print(f"  ❌ {method} {path}: {r.status_code} {r.text[:120]}")
        return None
    ok += 1
    result = r.json() if r.status_code < 300 else None
    return result

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
api("POST", "/foundation/suppliers", {"code":"S001","name":"深圳电子材料","supplier_type":"原材料"})
api("POST", "/foundation/suppliers", {"code":"S002","name":"东莞精密加工","supplier_type":"委外"})
api("POST", "/foundation/customers", {"code":"C001","name_cn":"美国贸易公司","country":"美国"})
api("POST", "/foundation/materials", {"code":"M001","name":"PCB电路板","unit":"片","purchase_price":15})
api("POST", "/foundation/materials", {"code":"M002","name":"电阻套装","unit":"包","purchase_price":5})
api("POST", "/foundation/materials", {"code":"M003","name":"塑料外壳","unit":"个","purchase_price":3})
hs = api("POST", "/foundation/hs-codes", {"hs_code":"8471","name":"计算机","refund_rate":13,"tax_rate":13})
proc = api("POST", "/foundation/processes", {"code":"P001","name":"SMT","is_outsource":1,"unit_price":8})
prod1 = api("POST", "/foundation/products", {"code":"PRD001","name_cn":"智能控制器","unit":"台","sale_price":120,"hs_code_id":hs["id"]})
prod2 = api("POST", "/foundation/products", {"code":"PRD002","name_cn":"传感器模块","unit":"个","sale_price":80,"hs_code_id":hs["id"]})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod1["id"],"material_id":1,"quantity":2,"process_id":proc["id"]})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod1["id"],"material_id":2,"quantity":10})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod1["id"],"material_id":3,"quantity":1})
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod2["id"],"material_id":2,"quantity":5})
print("✅ 基础档案创建完成")

# ===== 销售订单（多产品明细） =====
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
print(f"✅ 生产订单: {prods['total']} 条")

# ===== 采购订单 =====
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
for b in bal["items"]:
    print(f"  {b['material_name'] or b['product_name']} [{b['batch_no']}] 数量={b['quantity']} 金额=¥{b['total_cost']}")

# ===== 委外 → 发料 → 入库 =====
print("\n" + "═" * 50 + "\n  委外工单 → 发料 → 完工入库\n" + "═" * 50)

os_order = api("POST", "/production/outsourcings", {
    "production_id": 1, "supplier_id": 2, "product_id": prod1["id"],
    "quantity": 50, "unit_price": 20, "process_id": proc["id"], "due_date": "2026-08-10",
})
print(f"✅ 委外工单: {os_order['outsource_no']}")

batches = api("GET", "/production/inventory/batch")
batch_no = batches["items"][0]["batch_no"]
api("POST", "/production/material-issues", {
    "outsource_id": os_order["id"], "material_id": 1,
    "batch_no": batch_no, "quantity": 100, "warehouse_id": 1,
})
print(f"✅ 发料: PCB×100")

fr = api("POST", "/production/outsource-receipts", {
    "outsource_id": os_order["id"], "product_id": prod1["id"],
    "quantity": 50, "warehouse_id": 2, "receipt_date": "2026-08-10",
})
print(f"✅ 完工入库: {fr['receipt_no']} 批次{fr['batch_no']}")

# ===== 销售发货 =====
print("\n" + "═" * 50 + "\n  销售发货 → 报关 → 发票 → 应收 → 收款\n" + "═" * 50)

deliv = api("POST", "/sales/deliveries", {
    "order_id": so["id"], "order_item_id": 1, "product_id": prod1["id"],
    "batch_no": fr["batch_no"], "quantity": 50, "warehouse_id": 2,
    "delivery_date": "2026-08-15",
})
print(f"✅ 销售发货: {deliv['delivery_no']}")

cus = api("POST", "/sales/customs", {
    "customs_no": "CUS-20260815-001", "order_id": so["id"],
    "delivery_id": deliv["id"], "hs_code_id": hs["id"],
    "declare_amount": 10000, "declare_currency": 2,
    "declare_date": "2026-08-15",
})
print(f"✅ 报关完成")

sinv = api("POST", "/sales/invoices", {
    "invoice_no": "SI-20260815-001", "sales_order_id": so["id"],
    "amount": 8849.56, "tax_rate": 13, "invoice_date": "2026-08-15",
})
print(f"✅ 销售发票 → 应收已生成")

ars = api("GET", "/sales/ar")
ar_id = ars["items"][0]["id"] if ars.get("items") else None
coll = api("POST", "/sales/collections", {
    "customer_id": 1, "amount": 10000, "amount_fc": 10000,
    "currency_id": 2, "exchange_rate": 7.2, "collection_date": "2026-08-20",
    "ar_account_id": ar_id,
})
print(f"✅ 收款: {coll['collection_no']}")

# ===== 退税 =====
print("\n" + "═" * 50 + "\n  退税计算\n" + "═" * 50)

calc = api("POST", "/tax-refund/calculate", {
    "export_amount_fob": 10000, "refund_rate": 13, "tax_rate": 13,
    "domestic_tax": 50000, "input_tax": 20000, "last_period_deduction": 0,
})
print(f"✅ 退税计算: 应退¥{calc['actual_refund']}, 免抵¥{calc['exemption_amount']}")

print(f"\n{'═' * 50}")
print(f"  🎉 全流程测试完成! 成功={ok} 失败={fail}")
print(f"{'═' * 50}")
