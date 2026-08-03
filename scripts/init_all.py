"""一键初始化 + 全流程演示数据（v2.5.2 对齐）

用途：清库后录入一套完整可操作数据（基础档案 + 全业务流程单据 + 新功能演示）
用法: python scripts/init_all.py [端口，默认 8788]
前置: 后端已启动（建议先 python scripts/reset_local_db.py 清库，或直接删 backend/data/erp.db*）

数据源: backend/tests/test_data.py 的 _realistic（纺织真实数据）——
  与 pytest 测试共用同一份配置（单一数据源，杜绝双份档案漂移）。

流程: 登录 → 基础档案(复用 build_foundation) → 销售订单→审核→生产
  (确认备货方式/BOM展开/派产) → 采购→入库 → 生产领料→工序完工→成品入库
  → 销售发货 → 发票→收款 → 报关 → 退税申报
  → 演示: 销售退货(10) + 发票全额红冲 + 退款（查看红字流程）
"""

import sys
from pathlib import Path

import requests

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

PORT = sys.argv[1] if len(sys.argv) > 1 else 8788
BASE = f"http://localhost:{PORT}/api"
H = {}

ok = 0
fail = 0


def api(method, path, data=None, params=None, quiet=False):
    """业务流程专用 API 调用（BASE 含 /api，path 不带 /api 前缀）"""
    global ok, fail
    r = requests.request(method, f"{BASE}{path}", headers=H, json=data, params=params, timeout=60)
    if r.status_code >= 400:
        fail += 1
        if not quiet:
            print(f"  ❌ {method} {path}: {r.status_code} {r.text[:200]}")
        return None
    ok += 1
    return r.json() if r.status_code < 300 else None


def main():
    global H
    # ===== 登录 =====
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    if r.status_code != 200:
        print("❌ 登录失败（后端是否启动？端口是否正确？）")
        sys.exit(1)
    T = r.json()["access_token"]
    H = {"Content-Type": "application/json", "Authorization": f"Bearer {T}"}
    print("✅ 登录成功\n")

    # ===== 基础档案（复用统一构建器 tests/test_data.build_foundation） =====
    print("═" * 50 + "\n  基础档案（纺织真实数据，来自 tests/test_data.py）\n" + "═" * 50)

    class _MockClient:
        """适配 build_foundation 的 TestClient 接口（路径自带 /api 前缀）"""
        def request(self, method, path, json=None, headers=None, params=None):
            hh = dict(H)
            hh.update(headers or {})
            return requests.request(method, f"http://localhost:{PORT}{path}",
                                    json=json, headers=hh, params=params, timeout=60)

    from tests.test_data import build_foundation
    f = build_foundation(_MockClient(), {"Authorization": f"Bearer {T}"})
    cny = f["cny"]
    wh_rm, wh_fg = f["wh_rm"], f["wh_fg"]
    sup = f["sup"]
    sup_os = f["sup_os"]
    cust = f["cust"][0]
    mats, procs, prods = f["mats"], f["procs"], f["prods"]
    print("✅ 基础档案完成（2仓 × 4材料 × 4工序 × 2供应商 × 2客户 × 2产品 × BOM × 工艺路线）\n")

    # ===== 销售订单 → 审核 → 生产订单 =====
    print("═" * 50 + "\n  销售订单 → 审核 → 生产\n" + "═" * 50)
    pid = prods["全棉色织布"]["id"]  # 含委外工序（染色→江苏阳光），覆盖发料拆类型
    unit_price = prods["全棉色织布"]["price"]
    so = api("POST", "/sales/orders", {
        "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
        "items": [{"product_id": pid, "quantity": 100, "unit_price": unit_price, "tax_rate": 13}],
    })
    if not so:
        print("❌ 销售订单创建失败"); sys.exit(1)
    so_id = so["id"]
    print(f"✅ 销售订单 {so['order_no']}（100 件 × ¥{unit_price}）")
    api("POST", f"/sales/orders/{so_id}/approve")
    mo = api("GET", "/production/productions?page_size=5")
    mo_id = mo["items"][0]["id"]
    print(f"✅ 审核完成 → 生产订单 {mo['items'][0]['order_no']}")

    # ===== 生产：确认备货方式 → BOM 展开 → 派产 =====
    print("\n═" * 50 + "\n  生产准备（备货方式 → BOM → 派产）\n" + "═" * 50)
    api("POST", f"/production/productions/{mo_id}/set-type", {"production_type": "自产"})
    api("POST", f"/production/productions/{mo_id}/expand-bom")
    api("POST", f"/production/productions/{mo_id}/release")
    md = api("GET", f"/production/productions/{mo_id}")
    print(f"✅ 备货方式=自产，BOM 展开 {len(md['materials'])} 项物料 / {len(md['processes'])} 道工序，已派产")

    # ===== 采购材料（BOM 需求 ×1.3 余量）→ 审核 → 入库 =====
    print("\n═" * 50 + "\n  采购 → 入库\n" + "═" * 50)
    from tests.test_data import _realistic
    boms = _realistic["boms"]["全棉色织布"]
    po = api("POST", "/purchase/orders", {
        "supplier_id": sup, "currency_id": cny["id"], "tax_rate": 13,
        "items": [{"material_id": mats[mname], "quantity": round(100 * qty * 1.3, 2),
                   "unit_price": 30.0} for mname, qty in boms],
    })
    po_id = po["id"]
    api("POST", f"/purchase/orders/{po_id}/approve")
    pod = api("GET", f"/purchase/orders/{po_id}")
    receipt_items = [{"order_item_id": i["id"], "material_id": i["material_id"],
                      "quantity": i["quantity"], "unit_price": i["unit_price"]}
                     for i in pod["items"]]
    rcp = api("POST", "/purchase/receipts", {
        "order_id": po_id, "warehouse_id": wh_rm, "items": receipt_items})
    print(f"✅ 采购订单 {po['order_no']} → 入库 {rcp.get('receipt_no', '')}（材料入库，批次已生成）")

    # 材料批次映射（发料用）
    bal = api("GET", "/inventory/balance?type=material&page_size=50")
    batch_of_material = {}
    for b in bal.get("items", []):
        batch_of_material.setdefault(b["material_id"], b["batch_no"])
    print(f"✅ 材料库存 {len(bal.get('items', []))} 条")

    # ===== 生产领料（自产工序） + 委外发料 =====
    print("\n═" * 50 + "\n  生产领料 / 委外发料\n" + "═" * 50)
    first_proc = sorted(md["processes"], key=lambda p: p["seq"])[0]
    os_proc = next((p for p in md["processes"] if p.get("outsourcer_id")), None)
    for pm in md["materials"]:
        bno = batch_of_material.get(pm["material_id"])
        if not bno:
            print(f"  ⚠️ 材料 {pm['material_id']} 无批次，跳过发料")
            continue
        r = api("POST",
                f"/production/productions/{mo_id}/processes/{first_proc['id']}/issue",
                {"material_id": pm["material_id"], "quantity": pm["planned_qty"],
                 "batch_no": bno, "warehouse_id": wh_rm}, quiet=True)
        if r:
            print(f"  ✅ 领料 {pm['material_name']} × {pm['planned_qty']}（material_issue_out）")
    if os_proc:
        first_mid = md["materials"][0]
        bno = batch_of_material.get(first_mid["material_id"])
        if bno:
            api("POST", f"/production/productions/{mo_id}/processes/{os_proc['id']}/issue",
                {"material_id": first_mid["material_id"], "quantity": 1,
                 "batch_no": bno, "warehouse_id": wh_rm}, quiet=True)
            print(f"  ✅ 委外发料（outsource_out）→ 染色工序")

    # ===== 工序完工 → 成品入库 =====
    print("\n═" * 50 + "\n  工序完工 → 成品入库\n" + "═" * 50)
    for proc in sorted(md["processes"], key=lambda p: p["seq"]):
        body = {"unit_price": proc.get("unit_price") or 0.5, "process_qty": 100}
        if proc.get("outsourcer_id"):
            body = {"unit_price": 2.0, "process_qty": 100}
        api("POST", f"/production/productions/{mo_id}/processes/{proc['id']}/finish", body)
    print(f"✅ {len(md['processes'])} 道工序完工")
    receipt = api("POST", f"/production/productions/{mo_id}/receipt", {
        "quantity": 100, "warehouse_id": wh_fg,
        "material_cost": None, "process_cost": None, "receipt_date": "2026-08-03"})
    batch_fg = receipt.get("batch_no", "")
    print(f"✅ 成品入库 → 批次 {batch_fg}（成本自动结转）")

    # ===== 销售发货 → 发票 → 收款 =====
    print("\n═" * 50 + "\n  销售发货 → 开票 → 收款\n" + "═" * 50)
    so_detail = api("GET", f"/sales/orders/{so_id}")
    oi_id = so_detail["items"][0]["id"]
    dv = api("POST", "/sales/deliveries", {
        "order_id": so_id, "order_item_id": oi_id,
        "batch_no": batch_fg, "quantity": 100, "warehouse_id": wh_fg,
        "delivery_date": "2026-08-03"})
    dv_id = dv["id"]
    print(f"✅ 销售发货 {dv['delivery_no']}（100 件，批次 {batch_fg}）")

    sa = round(100 * unit_price, 2)
    inv = api("POST", "/sales/invoices", {
        "invoice_no": "INV-20260803-001", "order_id": so_id, "invoice_date": "2026-08-03",
        "amount": round(sa / 1.13, 2), "amount_fc": round(sa / 1.13, 2),
        "tax_amount": round(sa * 0.13 / 1.13, 2), "total_amount": sa, "tax_rate": 13})
    print(f"✅ 销售发票 INV-20260803-001（价税合计 ¥{sa}）→ 应收已生成")

    ars = api("GET", "/sales/ar?page_size=50")["items"]
    ar = next((a for a in ars if a.get("source_id") == inv["id"]), None)
    coll_amt = round(sa * 0.4, 2)
    api("POST", "/sales/collections", {
        "customer_id": cust, "amount": coll_amt, "ar_account_id": ar["id"],
        "payment_method": "银行转账", "collection_date": "2026-08-03"})
    print(f"✅ 收款 ¥{coll_amt}（40%，部分收款）→ 应收余额 ¥{round(sa - coll_amt, 2)}")

    # ===== 报关 → 退税申报（待申报） =====
    print("\n═" * 50 + "\n  报关 → 退税申报\n" + "═" * 50)
    hss = api("GET", "/foundation/hs-codes?page_size=5")
    hs_id = hss["items"][0]["id"]
    api("POST", "/sales/customs", {
        "customs_no": "223320260803000001", "order_id": so_id, "delivery_id": dv_id,
        "hs_code_id": hs_id, "declare_amount": sa, "declare_currency": cny["id"],
        "declare_date": "2026-08-03"})
    decl = api("POST", "/tax-refund/declarations", {
        "declaration_no": "TD-202608-001", "declare_date": "2026-08-03",
        "period": "202608", "export_amount_fob": sa,
        "tax_rate": 13, "refund_rate": 13, "input_tax": round(sa * 0.13 / 1.13, 2)})
    print(f"✅ 报关单 223320260803000001 + 退税申报 {decl['declaration_no']}（待申报）")

    # ===== 演示：销售退货 + 发票全额红冲 + 退款（v2.5.2 新功能） =====
    print("\n═" * 50 + "\n  演示：销售退货(10) + 发票全额红冲 + 退款\n" + "═" * 50)
    ret = api("POST", f"/sales/deliveries/{dv_id}/return", {"quantity": 10, "remark": "演示: 质量退货"})
    print(f"✅ 退货 10 件 → 红字退货单 {ret['return_no']}，库存回库（订单已发回退为 90）")
    print(f"   ℹ️ 提示: {ret.get('message', '')[:60]}")

    red = api("POST", "/sales/invoices", {
        "invoice_no": "INV-RED-20260803-001", "order_id": so_id, "red_of_invoice_id": inv["id"],
        "invoice_date": "2026-08-03",
        "amount": round(-sa / 1.13, 2), "tax_amount": round(-sa * 0.13 / 1.13, 2),
        "total_amount": -sa, "tax_rate": 13})
    print(f"✅ 发票全额红冲 → 红字发票 INV-RED-20260803-001（原票已红冲，红字应收已生成）")

    ars2 = api("GET", "/sales/ar?page_size=50")["items"]
    red_ar = next((a for a in ars2 if a.get("is_red")), None)
    refund = api("POST", "/sales/collections", {
        "customer_id": cust, "amount": -coll_amt, "ar_account_id": red_ar["id"],
        "payment_method": "电汇退款", "collection_date": "2026-08-03"})
    print(f"✅ 退款 ¥{coll_amt}（负数收款单）→ 红字应收已核销（线下实际退钱）")
    print("   ℹ️ 可查看：发票列表红字行/红冲票号列、应收红字(红)/核销转移入口、收款单退款标签")

    # ===== 汇总 =====
    print("\n" + "═" * 50)
    print(f"  初始化完成 ✅ 成功={ok} 失败={fail}")
    print("  数据一览：销售订单1 / 生产订单1 / 采购订单1 / 发货单1(含退货) / 发票1(已红冲+红字1)")
    print(f"  应收（正1 红字1）/ 收款单2（收款+退款）/ 报关1 / 退税申报1（待申报）")
    print("═" * 50)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
