"""
LTMP 全流程测试脚本
走完：基础数据→采购→委外→完工→销售→报关→应收→退税
"""
import requests, json, sys

BASE = "http://localhost:8788/api"
OK = "✅"; FAIL = "❌"
step = 0
errs = []

def api(method, path, data=None, token=None):
    url = f"{BASE}{path}"
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r = requests.request(method, url, headers=h, json=data)
    if r.status_code >= 400:
        print(f"  {FAIL} {method} {path} → {r.status_code}: {r.text[:200]}")
        errs.append((method, path, r.status_code, r.text[:200]))
    return r.json() if r.status_code < 300 else None

# === 1. 登录 ===
print(f"\n{'='*60}")
print(f"   LTMP 全流程测试")
print(f"{'='*60}")

r = requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"admin123"})
assert r.status_code == 200, f"登录失败: {r.text}"
TOKEN = r.json()["access_token"]
user = r.json()["user"]
print(f"\n{OK} 登录成功: {user['display_name']} ({user['role']})")
step += 1

# === 2. 基础数据 ===
print(f"\n{'─'*40}\n  基础档案\n{'─'*40}")

# 币种
api("POST", "/foundation/currencies", {"code":"USD","name":"美元","symbol":"$"}, TOKEN)
api("POST", "/foundation/currencies", {"code":"CNY","name":"人民币","symbol":"¥","is_base":1}, TOKEN)
print(f"{OK} 币种: CNY, USD")

# 仓库
api("POST", "/foundation/warehouses", {"code":"RM","name":"原料仓","wh_type":"原料仓"}, TOKEN)
api("POST", "/foundation/warehouses", {"code":"FG","name":"成品仓","wh_type":"成品仓"}, TOKEN)
print(f"{OK} 仓库: 原料仓, 成品仓")

# 贸易术语
api("POST", "/foundation/trade-terms", {"code":"FOB","name":"FOB(离岸价)"}, TOKEN)
api("POST", "/foundation/trade-terms", {"code":"CIF","name":"CIF(到岸价)"}, TOKEN)
print(f"{OK} 贸易术语: FOB, CIF")

# HS编码 + 退税率
hs = api("POST", "/foundation/hs-codes", {"hs_code":"84713000","name":"便携式计算机","unit":"台","refund_rate":13,"tax_rate":13}, TOKEN)
print(f"{OK} HS编码: 84713000 退税率13%")

# 供应商
sup = api("POST", "/foundation/suppliers", {"code":"S001","name":"深圳电子材料有限公司","supplier_type":"原材料"}, TOKEN)
sup2 = api("POST", "/foundation/suppliers", {"code":"S002","name":"东莞精密加工厂","supplier_type":"委外"}, TOKEN)
print(f"{OK} 供应商: 深圳电子(S001), 东莞精密(S002)")

# 客户
cust = api("POST", "/foundation/customers", {"code":"C001","name_cn":"美国贸易公司","name_en":"US Trading Co.","country":"美国","payment_terms":"TT","account_period":30}, TOKEN)
print(f"{OK} 客户: C001 美国贸易公司")

# 材料
mat1 = api("POST", "/foundation/materials", {"code":"M001","name":"PCB电路板","unit":"片","category":"原材料","purchase_price":15}, TOKEN)
mat2 = api("POST", "/foundation/materials", {"code":"M002","name":"电阻套装","unit":"包","category":"原材料","purchase_price":5}, TOKEN)
mat3 = api("POST", "/foundation/materials", {"code":"M003","name":"塑料外壳","unit":"个","category":"辅料","purchase_price":3}, TOKEN)
print(f"{OK} 材料: PCB电路板(M001), 电阻套装(M002), 塑料外壳(M003)")

# 工序
proc = api("POST", "/foundation/processes", {"code":"P001","name":"SMT贴片","is_outsource":1,"unit_price":8,"standard_hours":2}, TOKEN)
print(f"{OK} 工序: SMT贴片(P001)")

# 产品
prod = api("POST", "/foundation/products", {"code":"PRD001","name_cn":"智能控制器","name_en":"Smart Controller","unit":"台","sale_price":120,"hs_code_id":hs["id"]}, TOKEN)
print(f"{OK} 产品: PRD001 智能控制器")

# BOM
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod["id"],"material_id":mat1["id"],"quantity":2,"process_id":proc["id"]}, TOKEN)
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod["id"],"material_id":mat2["id"],"quantity":10}, TOKEN)
api("POST", "/foundation/bom", {"bom_name":"默认BOM","product_id":prod["id"],"material_id":mat3["id"],"quantity":1}, TOKEN)
print(f"{OK} BOM: 智能控制器 → PCB×2 + 电阻×10 + 外壳×1")

# === 3. 采购流程 ===
print(f"\n{'─'*40}\n  采购订单 → 入库(批次) → 应付\n{'─'*40}")

po = api("POST", "/purchase/orders", {
    "supplier_id": sup["id"], "payment_terms": "TT", "tax_rate": 13,
    "items": [
        {"material_id": mat1["id"], "quantity": 100, "unit_price": 15},
        {"material_id": mat2["id"], "quantity": 500, "unit_price": 5},
        {"material_id": mat3["id"], "quantity": 50, "unit_price": 3},
    ]
}, TOKEN)
print(f"{OK} 采购订单: {po['order_no']}")

api("POST", f"/purchase/orders/{po['id']}/approve", token=TOKEN)
print(f"{OK} 采购订单已审核")

# 采购入库（批量入库）
pr = api("POST", "/purchase/receipts", {
    "order_id": po["id"], "warehouse_id": 1,
    "items": [
        {"material_id": mat1["id"], "quantity": 100, "order_item_id": 1},
        {"material_id": mat2["id"], "quantity": 500, "order_item_id": 2},
        {"material_id": mat3["id"], "quantity": 50, "order_item_id": 3},
    ]
}, TOKEN)
print(f"{OK} 采购入库: {pr['receipt_no']}")

# 采购发票
inv = api("POST", "/purchase/invoices", {
    "invoice_no": "INV-20260721-001", "order_id": po["id"],
    "supplier_id": sup["id"], "amount": 4300, "amount_fc": 4300,
    "invoice_date": "2026-07-21",
}, TOKEN)
print(f"{OK} 采购发票: INV-20260721-001 → 应付已生成")

# === 4. 销售订单 → 生产 ===
print(f"\n{'─'*40}\n  销售订单 → 生产订单 → 委外\n{'─'*40}")

so = api("POST", "/sales/orders", {
    "customer_id": cust["id"],
    "product_id": prod["id"],
    "quantity": 100,
    "unit_price": 120,
    "currency_id": 2,  # USD
    "exchange_rate": 7.2,
    "trade_term_id": 1,  # FOB
    "payment_terms": "TT",
    "order_date": "2026-07-21",
    "tax_rate": 13,
    "hs_code_id": hs["id"],
}, TOKEN)
print(f"{OK} 销售订单: {so['order_no']}")

# 审核 → 自动生成生产订单
aproval = api("POST", f"/sales/orders/{so['id']}/approve", token=TOKEN)
print(f"{OK} 销售订单已审核, 生产订单已生成")

# 获取生产订单
prods = api("GET", "/production/productions", token=TOKEN)
mo = prods["items"][0] if prods["items"] else None
print(f"{OK} 生产订单: {mo['order_no'] if mo else '—'}")

# 创建委外工单
os = api("POST", "/production/outsourcings", {
    "production_id": mo["id"],
    "supplier_id": sup2["id"],
    "product_id": prod["id"],
    "quantity": 100,
    "unit_price": 20,
    "process_id": proc["id"],
    "due_date": "2026-07-30",
}, TOKEN)
print(f"{OK} 委外工单: {os['outsource_no']}")

# === 5. 委外发料 ===
print(f"\n{'─'*40}\n  委外发料(批次)\n{'─'*40}")

# 获取材料批次
mat_batches = api("GET", "/production/inventory/batch?material_id=" + str(mat1["id"]), token=TOKEN)
batch_no = mat_batches["items"][0]["batch_no"] if mat_batches.get("items") else "?"
print(f"{OK} 原料批次: {batch_no}")

# 发料
api("POST", "/production/material-issues", {
    "outsource_id": os["id"],
    "material_id": mat1["id"],
    "batch_no": batch_no,
    "quantity": 200,
    "warehouse_id": 1,
}, TOKEN)
print(f"{OK} 委外发料: PCB×200 批次{batch_no} 出库")

# === 6. 完工人库 ===
print(f"\n{'─'*40}\n  完工入库(成品批次)\n{'─'*40}")

fr = api("POST", "/production/outsource-receipts", {
    "outsource_id": os["id"],
    "product_id": prod["id"],
    "quantity": 100,
    "warehouse_id": 2,
    "receipt_date": "2026-07-25",
}, TOKEN)
print(f"{OK} 完工入库: {fr['receipt_no']}, 成品批次: {fr['batch_no']}")

# === 7. 销售发货 → 报关 ===
print(f"\n{'─'*40}\n  销售发货(批次) → 报关\n{'─'*40}")

delivery = api("POST", "/sales/deliveries", {
    "order_id": so["id"],
    "batch_no": fr["batch_no"],
    "quantity": 100,
    "warehouse_id": 2,
    "delivery_date": "2026-07-25",
}, TOKEN)
print(f"{OK} 销售发货: {delivery['delivery_no']}, 批次{fr['batch_no']}出库")

customs = api("POST", "/sales/customs", {
    "customs_no": "CUS-20260725-001",
    "order_id": so["id"],
    "delivery_id": delivery["id"],
    "hs_code_id": hs["id"],
    "declare_amount": 12000,
    "declare_currency": 2,
    "declare_date": "2026-07-25",
    "customs_broker": "深圳报关行",
}, TOKEN)
print(f"{OK} 报关单: CUS-20260725-001")

# === 8. 开票 → 应收 ===
print(f"\n{'─'*40}\n  销售发票 → 应收\n{'─'*40}")

sinv = api("POST", "/sales/invoices", {
    "invoice_no": "SI-20260725-001",
    "order_id": so["id"],
    "amount": 12000,
    "amount_fc": 12000,
    "invoice_date": "2026-07-25",
}, TOKEN)
print(f"{OK} 销售发票: SI-20260725-001 → 应收已生成")

# 查看应收
ars = api("GET", "/sales/ar", token=TOKEN)
if ars["items"]:
    print(f"{OK} 应收账款: {len(ars['items'])} 笔, 余额 ¥{ars['items'][0]['balance']}")

# === 9. 收款 ===
print(f"\n{'─'*40}\n  收款核销\n{'─'*40}")

ar_id = ars["items"][0]["id"] if ars["items"] else None
coll = api("POST", "/sales/collections", {
    "customer_id": cust["id"],
    "amount": 12000,
    "amount_fc": 12000,
    "currency_id": 2,
    "exchange_rate": 7.2,
    "collection_date": "2026-07-28",
    "payment_method": "银行转账",
    "ar_account_id": ar_id,
}, TOKEN)
print(f"{OK} 收款登记: {coll['collection_no']}")

# === 10. 退税 ===
print(f"\n{'─'*40}\n  退税申报(生产企业免抵退)\n{'─'*40}")

calc = api("POST", "/tax-refund/calculate", {
    "export_amount_fob": 12000,
    "refund_rate": 13,
    "tax_rate": 13,
    "domestic_tax": 50000,
    "input_tax": 20000,
    "last_period_deduction": 0,
}, TOKEN)
if calc:
    print(f"{OK} 免抵退计算: 应退¥{calc['actual_refund']} / 免抵¥{calc['exemption_amount']}")

decl = api("POST", "/tax-refund/declarations", {
    "declaration_no": "TR-202607-001",
    "declare_date": "2026-07-28",
    "period": "202607",
    "export_amount_fob": 12000,
    "refund_rate": 13,
    "tax_rate": 13,
    "domestic_tax": 50000,
    "input_tax": 20000,
    "last_period_deduction": 0,
    "customs_ids": str(customs["id"]),
}, TOKEN)
if decl:
    print(f"{OK} 退税申报: {decl['declaration_no']}")

# === 汇总 ===
print(f"\n{'='*60}")
print(f"  测试完成")
print(f"{'='*60}")
if errs:
    print(f"\n{FAIL} {len(errs)} 个错误:")
    for e in errs:
        print(f"  {e[1]} → {e[2]}")
else:
    print(f"\n{OK} 全部流程通过！")
print(f"\n数据已写入数据库，可登录 http://localhost:5173 查看")
