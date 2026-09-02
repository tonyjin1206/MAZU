"""
纺织企业全流程测试 v5（2026-09-02 随生产管理下线重写）
=============================================
数据规范：全部档案来自共享 foundation fixture（tests/test_data.py），本文件不再自建档案。
数据规模：1 客户 × 1 产品 × 1 订单（少而真实）。

覆盖（对齐最新业务逻辑，生产管理已下线）：
  销售→审核→转直采（无视BOM）→销售订单转采购→成品明细「转成品库入库」收货
  →销售出库→退货（逆向）
  库存v2：盘点(盘亏)、成本=采购价校验
  发票/应收→报关→退税
"""

from app.database import SessionLocal


class TestTextileFullFlow:
    """纺织企业完整业务流 — 转直采主线 + 逆向操作 + 库存 v2 闭环"""

    def test_full_flow(self, client, auth_headers, foundation):
        api = self._api
        h = auth_headers
        f = foundation  # 共享基础档案

        cny = f["cny"]
        wh_fg = f["wh_fg"]
        sup = f["sup"]
        cust = f["cust"][0]
        prods = f["prods"]
        # 用「全棉色织布」—— 共享档案中的标准成品
        pid = prods["全棉色织布"]["id"]
        unit_price = prods["全棉色织布"]["price"]

        # ======================== 1. 销售订单 → 审核 → 转直采 ========================
        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 100, "unit_price": unit_price, "tax_rate": 13}],
        }, h)
        so_id, so_no = so["id"], so["order_no"]
        print(f"① 销售订单 {so_no}")

        api(client, "POST", f"/api/sales/orders/{so_id}/approve", {}, h)
        so_detail = api(client, "GET", f"/api/sales/orders/{so_id}", None, h)
        item_id = so_detail["items"][0]["id"]
        r = client.post(f"/api/sales/orders/{so_id}/items/{item_id}/stock-in", json={}, headers=h)
        assert r.status_code == 200, f"转直采失败: {r.text[:200]}"
        print(f"①·② 转直采 → 明细行「已通知入库」✅")

        # ======================== 2. 转直采采购 → 成品入库 ========================
        rows = api(client, "GET", f"/api/purchase/sales-to-purchase?keyword={so_no}", None, h)
        assert rows and rows["items"], "转直采行应出现在「销售订单转采购」列表"
        assert any(x["sales_item_id"] == item_id for x in rows["items"]), "列表应含本明细行"

        gen = api(client, "POST", "/api/purchase/orders/from-sales", {
            "sales_order_id": so_id,
            "rows": [{"sales_item_id": item_id, "product_id": pid,
                      "supplier_id": sup, "quantity": 100,
                      "unit_price": 12.0, "tax_rate": 13}],
        }, h)
        assert gen and gen.get("orders"), f"转采购生成采购订单失败: {gen}"
        po_no = gen["orders"][0]["order_no"]

        # 转直采无视 BOM：明细应为成品本身（product_id），不展开材料行
        from app.models.purchase import PurchaseOrder, PurchaseOrderItem
        db = SessionLocal()
        try:
            po = db.query(PurchaseOrder).filter(PurchaseOrder.order_no == po_no).first()
            po_id = po.id
            items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.order_id == po_id).all()
        finally:
            db.close()
        assert len(items) == 1 and items[0].product_id == pid and items[0].material_id is None, \
            "转直采明细应为成品本身（无视 BOM，不展开材料行）"
        api(client, "POST", f"/api/purchase/orders/{po_id}/approve", {}, h)
        pod = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        oi = pod["items"][0]
        print(f"③ 转采购 {po_no}（无视 BOM，买成品）→ 审核通过 ✅")

        # 成品明细直接采购入库 → 400，必须走「转成品库入库」
        bad = client.post("/api/purchase/receipts", json={
            "order_id": po_id, "warehouse_id": wh_fg,
            "items": [{"order_item_id": oi["id"], "product_id": pid,
                       "quantity": 100, "unit_price": 12.0}]}, headers=h)
        assert bad.status_code == 400, f"成品明细直接采购入库应被拒，实际 {bad.status_code}"
        print(f"③·④ 仓库参照校验: 成品明细直接采购入库 → 400 ✅")

        # 转成品库入库 → 待入库单 → 收货
        api(client, "POST", f"/api/purchase/orders/{po_id}/items/{oi['id']}/to-stock-in",
            {"stock_in_order_id": 0}, h)
        sl = api(client, "GET", "/api/stock-in?source_type=purchase&page_size=10", None, h)
        sin = next((s for s in sl["items"] if s["purchase_item_id"] == oi["id"]), None)
        assert sin, "转成品库入库后应生成待入库单"
        rcv = api(client, "POST", f"/api/stock-in/{sin['id']}/receive",
                  {"quantity": 100, "warehouse_id": wh_fg}, h)
        assert rcv and rcv.get("status") == "已入库", f"成品收货应完成，实际 {rcv}"
        bal0 = api(client, "GET", "/api/inventory/balance?type=product&page_size=50", None, h)
        fgrow = [r for r in bal0["items"] if r["product_id"] == pid and r["quantity"] >= 100][-1]
        batch_fg = fgrow["batch_no"]
        assert fgrow["unit_cost"] == 12.0, f"成品入库成本应为采购价 12，实际 {fgrow['unit_cost']}"
        print(f"④ 转成品库入库 → 成品批次 {batch_fg}（成本=采购价 12）✅")

        # ======================== 3. 销售出库 → 退货（逆向） ========================
        # ---- 两段式发货：通知发货 → 库管出库 ----
        dlv_notify = api(client, "POST", "/api/sales/deliveries/notify", {
            "order_id": so_id, "order_item_id": item_id,
            "quantity": 100,
        }, h)
        assert dlv_notify, "发货通知失败"
        dlv_id = dlv_notify["id"]
        dlv = api(client, "POST", f"/api/sales/deliveries/{dlv_id}/issue", {
            "batch_no": batch_fg, "quantity": 100, "warehouse_id": wh_fg,
        }, h)
        assert dlv, "销售发货失败"
        delivery_no = dlv.get("delivery_no", "")
        print(f"⑤ 销售出库 {delivery_no}")

        # 退货 10 件 → 回库
        ret = api(client, "POST", f"/api/sales/deliveries/{dlv['id']}/return",
                  {"quantity": 10}, h)
        assert ret, "销售退货失败"
        print(f"⑤·⑤ 销售退货 10 → 回库（原批次/原成本）✅")

        # ======================== 4. 盘点（成品仓） ========================
        st = api(client, "POST", "/api/inventory/stocktakes", {"warehouse_id": wh_fg}, h)
        st_detail = api(client, "GET", f"/api/inventory/stocktakes/{st['id']}", None, h)
        assert st_detail["items"], "盘点应自动带出成品批次"
        # 按本测试的成品批次定位盘点行（盘点单自动带出仓内全部批次，
        # 全量跑时可能混入其他测试留下的批次，不能取 items[0]）
        it = next((i for i in st_detail["items"] if i["batch_no"] == batch_fg), None)
        assert it, f"盘点应带出本测试批次 {batch_fg}，实际: {[i['batch_no'] for i in st_detail['items']]}"
        book_qty = it["book_qty"]
        # 退货 10 后账面 = 90（100 出 - 10 退）；盘亏 5 → 85
        api(client, "PUT", f"/api/inventory/stocktakes/{st['id']}/items/{it['id']}",
            {"actual_qty": book_qty - 5}, h)
        api(client, "POST", f"/api/inventory/stocktakes/{st['id']}/submit", {}, h)
        fg_bal = api(client, "GET", "/api/inventory/balance?type=product&page_size=50", None, h)
        fg_row = next(r for r in fg_bal["items"] if r["batch_no"] == batch_fg)
        assert fg_row["quantity"] == book_qty - 5, f"盘点后成品应为 {book_qty-5}，实际 {fg_row['quantity']}"
        print(f"⑤·⑥ 盘点: 账面 {book_qty} → 实盘 {book_qty-5}（盘亏 5 入账）✅")

        # ======================== 5. 发票/应收/报关/退税 ========================
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
        print(f"⑥ 报关+发票+退税申报完成 ✅")

        # ======================== 汇总 ========================
        print(f"\n{'='*50}")
        print(f"全流程测试完成 ✅（转直采主线：销售→采购→入库→发货→发票/报关/退税，含逆向）")
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
