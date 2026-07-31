"""补充采购侧流程：采购发票 → 应付 → 付款"""
import requests, sys

BASE = "http://localhost:8788/api"
r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
T = r.json()["access_token"]
H = {"Content-Type": "application/json", "Authorization": f"Bearer {T}"}

def api(method, path, data=None, quiet=False):
    r = requests.request(method, f"{BASE}{path}", headers=H, json=data)
    if r.status_code >= 400:
        if not quiet: print(f"  ❌ {r.status_code} {path}: {r.text[:200]}")
        return None
    return r.json()

# 找采购订单
pos = api("GET", "/purchase/orders?page_size=10")
if not pos or not pos.get("items"):
    print("❌ 无采购订单"); sys.exit(1)
po = pos["items"][0]
print(f"✅ 采购订单: {po['order_no']} (含税总额 ¥{po['total_amount']})")

# 创建采购发票（金额 = 订单含税额）
inv = api("POST", "/purchase/invoices", {
    "invoice_no": "PI-20260731-001",
    "order_id": po["id"],
    "supplier_id": po["supplier_id"],
    "amount": round(po["total_amount"] / 1.13, 2),
    "tax_amount": round(po["total_amount"] - po["total_amount"] / 1.13, 2),
    "invoice_date": "2026-07-31",
})
if not inv:
    print("⚠️ 直接创建失败，试别的方式")
    inv = api("POST", "/purchase/invoices", {
        "order_id": po["id"], "amount": po["total_amount"],
        "supplier_id": po["supplier_id"],
        "invoice_no": "PI-20260731-001", "invoice_date": "2026-07-31",
    })
print(f"✅ 采购发票: {inv.get('invoice_no') if inv else '?'}")

# 查应付
aps = api("GET", "/purchase/ap")
if aps and aps.get("items"):
    total = sum(x.get("balance", 0) or 0 for x in aps["items"])
    print(f"✅ 应付账款: {len(aps['items'])} 笔, 余额合计 ¥{total:,.2f}")
    for ap in aps["items"]:
        print(f"   {ap['ap_no']} 应付¥{ap['amount']} 余额¥{ap['balance']} 到期{ap['due_date']}")

    # 付款（全额付第一笔）
    ap1 = aps["items"][0]
    pay = api("POST", "/purchase/payments", {
        "supplier_id": ap1["supplier_id"],
        "amount": ap1["balance"],
        "payment_date": "2026-08-01",
        "payment_method": "TT",
        "ap_account_ids": ap1["id"],
    })
    if pay:
        print(f"✅ 付款单: {pay.get('payment_no')} ¥{ap1['balance']}")
    else:
        # 试不带 ap_account_id
        pay = api("POST", "/purchase/payments", {
            "supplier_id": ap1["supplier_id"],
            "amount": ap1["balance"],
            "payment_date": "2026-08-01",
            "payment_method": "TT",
        })
        print(f"✅ 付款单: {pay.get('payment_no') if pay else '?'}")

# 再验证
aps2 = api("GET", "/purchase/ap")
if aps2 and aps2.get("items"):
    total2 = sum(x.get("balance", 0) or 0 for x in aps2["items"])
    print(f"\n📊 应付余额合计: ¥{total2:,.2f} (原 ¥{total:,.2f})")

pays = api("GET", "/purchase/payments")
print(f"📋 付款单数: {len(pays.get('items', [])) if pays else 0}")
