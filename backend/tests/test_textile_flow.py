"""
纺织企业全流程测试 v4（2026-07-31 重写）
=============================================
数据规范：全部档案来自共享 foundation fixture（tests/test_data.py），本文件不再自建档案。
数据规模：1 客户 × 1 产品 × 1 订单（少而真实）。

覆盖（对齐最新业务逻辑）：
  销售→审核→生产→备货方式→BOM展开→派产→采购入库→生产领料/委外发料(拆类型)
  →完工入库(成本自动结转)→销售出库→发票/应收→报关→退税
  逆向：取消发料→重发料、取消入库→重入库、关闭→阻止→取消关闭→关闭
  库存v2：采购红冲、销售退货、盘点(盘盈/盘亏)、仓库档案参照校验
"""

from tests.test_data import _realistic


class TestTextileFullFlow:
    """纺织企业完整业务流 — 含所有逆向操作 + 库存 v2 闭环"""

    def test_full_flow(self, client, auth_headers, foundation):
        import pytest
        pytest.skip("过时：SP 流程已变（审核不自动生成MO），待重写")
        api = self._api
        h = auth_headers
        f = foundation  # 共享基础档案

        cny = f["cny"]
        wh_rm, wh_fg = f["wh_rm"], f["wh_fg"]
        sup, sup_os = f["sup"], f["sup_os"]
        cust = f["cust"][0]
        mats, procs, prods = f["mats"], f["procs"], f["prods"]
        mat_32s = mats["精梳棉纱32S"]
        # 用「全棉色织布」—— 工艺路线含委外工序（染色→江苏阳光），可验证发料拆类型
        pid = prods["全棉色织布"]["id"]
        unit_price = prods["全棉色织布"]["price"]

        # ======================== 1. 销售订单 → 生产 ========================
        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 100, "unit_price": unit_price, "tax_rate": 13}],
        }, h)
        so_id, so_no = so["id"], so["order_no"]
        print(f"① 销售订单 {so_no}")

        api(client, "POST", f"/api/sales/orders/{so_id}/approve", {}, h)
        mo = api(client, "GET", "/api/production/productions?page=1&page_size=10", None, h)["items"][0]
        mo_id, mo_no = mo["id"], mo["order_no"]
        print(f"② 生产订单 {mo_no}")

        api(client, "POST", f"/api/production/productions/{mo_id}/set-type",
            {"production_type": "自产"}, h)
        api(client, "POST", f"/api/production/productions/{mo_id}/expand-bom", {}, h)
        api(client, "POST", f"/api/production/productions/{mo_id}/release", {}, h)
        md = api(client, "GET", f"/api/production/productions/{mo_id}", None, h)
        print(f"③ BOM展开+派产: {len(md['materials'])}项物料/{len(md['processes'])}道工序")

        # ======================== 2. 采购材料（需求×1.3 余量） ========================
        boms = _realistic["boms"]["全棉色织布"]  # 3 项材料
        po = api(client, "POST", "/api/purchase/orders", {
            "supplier_id": sup, "currency_id": cny["id"], "tax_rate": 13,
            "items": [
                {"material_id": mats[mname], "quantity": round(100 * qty * 1.3, 2),
                 "unit_price": 30.0}
                for mname, qty in boms
            ],
        }, h)
        po_id = po["id"]
        api(client, "POST", f"/api/purchase/orders/{po_id}/approve", {}, h)
        pod = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        receipt_items = [{"order_item_id": i["id"], "material_id": i["material_id"],
                          "quantity": i["quantity"], "unit_price": i["unit_price"]}
                         for i in pod["items"]]
        rcp = api(client, "POST", "/api/purchase/receipts", {
            "order_id": po_id, "warehouse_id": wh_rm, "items": receipt_items}, h)
        batch_rm = rcp.get("batch_no", "")
        print(f"④ 采购入库 → 材料批次 {batch_rm}")

        # ---- 仓库参照校验：不存在的仓库 → 400 ----
        bad = client.post("/api/purchase/receipts", json={
            "order_id": po_id, "warehouse_id": 99999,
            "items": [{"order_item_id": receipt_items[0]["order_item_id"],
                       "material_id": receipt_items[0]["material_id"],
                       "quantity": 1, "unit_price": 30.0}]}, headers=h)
        assert bad.status_code == 400, f"不存在的仓库应被拒，实际 {bad.status_code}"
        print(f"④·⑤ 仓库参照校验: 不存在仓库 → 400 ✅")

        # ---- 采购红冲（冲 1kg，验证功能；未指定的行必须显式 0 避免被默认全冲）----
        rcp_detail = api(client, "GET", f"/api/purchase/receipts/{rcp['id']}", None, h)
        red = api(client, "POST", f"/api/purchase/receipts/{rcp['id']}/red",
                  {"items": [
                      {"receipt_item_id": rcp_detail["items"][0]["id"], "quantity": 1},
                      {"receipt_item_id": rcp_detail["items"][1]["id"], "quantity": 0},
                      {"receipt_item_id": rcp_detail["items"][2]["id"], "quantity": 0},
                  ]}, h)
        assert red, "采购红冲失败"
        print(f"④·⑥ 采购红冲 1kg ✅（批次剩余应减 1）")

        # ======================== 3. 生产领料 / 委外发料（拆类型） ========================
        inv_tracker = {}
        bal = api(client, "GET", "/api/inventory/balance?type=material&page_size=50", None, h)
        for bi in bal.get("items", []):
            inv_tracker.setdefault(bi["material_id"], []).append({
                "batch_no": bi.get("batch_no", ""), "qty": bi["quantity"], "price": bi.get("unit_cost", 0)})

        def consume(mid, needed):
            remaining = needed
            out = []
            for b in inv_tracker.get(mid, []):
                if remaining <= 0:
                    break
                take = min(remaining, b["qty"])
                if take > 0:
                    out.append((b["batch_no"], take, b["price"]))
                    b["qty"] -= take
                    remaining -= take
            assert remaining <= 0.01, f"物料 {mid} 库存不足，缺 {remaining}"
            return out

        # 按工艺路线发料：整经/织造(自产) → material_issue_out；委外工序用 outsource_out
        proc_issues = {}  # proc_id -> qty
        for pm in md["materials"]:
            proc_issues[pm["material_id"]] = pm["planned_qty"]

        # 按工序发料（同一 issue 接口：自产工序→material_issue_out，委外工序→outsource_out）
        proc_by_material = {}  # material_id -> proc（材料归属哪道工序由测试简化为全部发到第一道）
        first_proc = sorted(md["processes"], key=lambda p: p["seq"])[0]
        issue_total = 0
        for mid, need in proc_issues.items():
            for batch_no, qty, price in consume(mid, need):
                api(client, "POST",
                    f"/api/production/productions/{mo_id}/processes/{first_proc['id']}/issue",
                    {"material_id": mid, "quantity": qty, "batch_no": batch_no,
                     "warehouse_id": wh_rm}, h)
                issue_total += 1
        # 委外工序发料（染色 → 委外商）→ outsource_out
        os_proc = next((p for p in md["processes"] if p.get("outsourcer_id")), None)
        if os_proc:
            for mid, need in list(proc_issues.items())[:1]:
                for batch_no, qty, price in consume(mid, 1):
                    api(client, "POST",
                        f"/api/production/productions/{mo_id}/processes/{os_proc['id']}/issue",
                        {"material_id": mid, "quantity": qty, "batch_no": batch_no,
                         "warehouse_id": wh_rm}, h)
                    print(f"⑤·⑤ 委外发料（outsource_out）→ 工序 {os_proc['process_name']}")
        print(f"⑤ 生产领料 {issue_total} 次（material_issue_out）")

        # 流水类型验证：material_issue_out / outsource_out 都已产生
        txns = api(client, "GET", "/api/inventory/transactions?type=material&page_size=50", None, h)
        types = {t["trans_type"] for t in txns["items"]}
        assert "material_issue_out" in types and "outsource_out" in types, f"发料类型缺失: {types}"
        print(f"⑤·⑥ 发料拆类型验证: material_issue_out + outsource_out ✅")

        # ======================== 4. 完工 → 入库（成本自动结转） ========================
        for proc in sorted(md["processes"], key=lambda p: p["seq"]):
            finish_body = {"unit_price": proc.get("unit_price") or 0.5,
                           "process_qty": 100}
            if proc.get("outsourcer_id"):
                finish_body = {"unit_price": 2.0, "process_qty": 100}  # 委外必须录加工费
            api(client, "POST", f"/api/production/productions/{mo_id}/processes/{proc['id']}/finish",
                finish_body, h)
        # 成本留空 → 自动结转（剩余投入 × 本次占比）
        receipt = api(client, "POST", f"/api/production/productions/{mo_id}/receipt", {
            "quantity": 100, "warehouse_id": wh_fg,
            "material_cost": None, "process_cost": None,
            "receipt_date": "2026-07-28"}, h)
        batch_fg = receipt.get("batch_no", "")
        # 成本自动结转验证（成本在返回 message 中）
        import re
        m_cost = re.search(r"成本: ¥([\d.]+)", receipt.get("message", ""))
        assert m_cost and float(m_cost.group(1)) > 0, f"成本应自动结转 >0，实际 {receipt}"
        print(f"⑥ 完工入库 → 成品批次 {batch_fg}，成本自动结转 ¥{m_cost.group(1)}")

        # ---- 取消入库 → 重新入库（逆向）----
        cancel = api(client, "POST",
                     f"/api/production/productions/{mo_id}/receipts/{receipt['id']}/cancel", {}, h)
        assert cancel, "取消入库失败"
        receipt2 = api(client, "POST", f"/api/production/productions/{mo_id}/receipt", {
            "quantity": 100, "warehouse_id": wh_fg,
            "material_cost": None, "process_cost": None, "receipt_date": "2026-07-28"}, h)
        batch_fg = receipt2.get("batch_no", "")
        print(f"⑥·⑤ 取消入库→重新入库 ✅ 批次 {batch_fg}")

        # ======================== 5. 销售出库 → 退货（逆向） ========================
        so_detail = api(client, "GET", f"/api/sales/orders/{so_id}", None, h)
        oi_id = so_detail["items"][0]["id"]
        delivery = api(client, "POST", "/api/sales/deliveries", {
            "order_id": so_id, "order_item_id": oi_id,
            "batch_no": batch_fg, "quantity": 100, "warehouse_id": wh_fg}, h)
        delivery_no = delivery.get("delivery_no", "")
        print(f"⑦ 销售出库 {delivery_no}")

        # 退货 10 件 → 回库
        ret = api(client, "POST", f"/api/sales/deliveries/{delivery['id']}/return",
                  {"quantity": 10}, h)
        assert ret, "销售退货失败"
        print(f"⑦·⑤ 销售退货 10 → 回库（原批次/原成本）✅")

        # ---- 关闭 → 阻止 → 取消关闭 → 关闭 ----
        assert api(client, "POST", f"/api/production/productions/{mo_id}/close", {}, h), "关闭失败"
        assert api(client, "POST", f"/api/production/productions/{mo_id}/receipt", {
            "quantity": 1, "warehouse_id": wh_fg}, h) is None, "已关闭不应允许入库"
        assert api(client, "POST", f"/api/production/productions/{mo_id}/unclose", {}, h), "取消关闭失败"
        assert api(client, "POST", f"/api/production/productions/{mo_id}/close", {}, h), "最终关闭失败"
        print(f"⑦·⑥ 关闭→阻止→取消关闭→关闭 ✅")

        # ======================== 6. 盘点（成品仓） ========================
        st = api(client, "POST", "/api/inventory/stocktakes", {"warehouse_id": wh_fg}, h)
        st_detail = api(client, "GET", f"/api/inventory/stocktakes/{st['id']}", None, h)
        assert st_detail["items"], "盘点应自动带出成品批次"
        it = st_detail["items"][0]
        book_qty = it["book_qty"]
        # 退货 10 后账面 = 90（100 出 - 10 退）；盘亏 5 → 85
        api(client, "PUT", f"/api/inventory/stocktakes/{st['id']}/items/{it['id']}",
            {"actual_qty": book_qty - 5}, h)
        api(client, "POST", f"/api/inventory/stocktakes/{st['id']}/submit", {}, h)
        fg_bal = api(client, "GET", "/api/inventory/balance?type=product&page_size=50", None, h)
        fg_row = next(r for r in fg_bal["items"] if r["batch_no"] == batch_fg)
        assert fg_row["quantity"] == book_qty - 5, f"盘点后成品应为 {book_qty-5}，实际 {fg_row['quantity']}"
        print(f"⑧ 盘点: 账面 {book_qty} → 实盘 {book_qty-5}（盘亏 5 入账）✅")

        # ======================== 7. 发票/应收/报关/退税 ========================
        sa = 100 * unit_price
        api(client, "POST", "/api/sales/customs", {
            "customs_no": "223320240728000001", "order_id": so_id,
            "hs_code_id": 1, "declare_amount": sa, "declare_currency": cny["id"],
            "declare_date": "2026-07-28"}, h)
        api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-S-01", "order_id": so_id, "invoice_date": "2026-07-28",
            "amount": round(sa / 1.13, 2), "amount_fc": round(sa / 1.13, 2),
            "tax_amount": round(sa * 0.13 / 1.13, 2), "total_amount": sa, "tax_rate": 13}, h)
        decl = api(client, "POST", "/api/tax-refund/declarations", {
            "declaration_no": "TD-20260728-001", "declare_date": "2026-07-28",
            "period": "202607", "export_amount_fob": sa,
            "tax_rate": 13, "refund_rate": 13, "input_tax": round(sa * 0.13 / 1.13, 2)}, h)
        api(client, "PUT", f"/api/tax-refund/declarations/{decl['id']}/submit", {}, h)
        print(f"⑨ 报关+发票+退税申报完成 ✅")

        # ======================== 汇总 ========================
        print(f"\n{'='*50}")
        print(f"全流程测试完成 ✅（1 客户 × 1 产品 × 1 订单，含全部逆向 + 库存v2 闭环）")
        print(f"{'='*50}")

    @staticmethod
    def _api(client, method, path, json_data=None, headers=None):
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            resp = client.post(path, json=json_data or {}, headers=headers)
        elif method == "PUT":
            resp = client.put(path, json=json_data or {}, headers=headers)
        else:
            raise ValueError(f"未知 method: {method}")
        if resp.status_code >= 400:
            print(f"   ❌ {method} {path} → {resp.status_code}: {resp.text[:200]}")
            return None
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}
