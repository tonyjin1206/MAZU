"""边界场景专项测试：

- return_stock_in 多次收货后退回：FIFO 逐条扣减，不产生负库存；
- claim_batch 多次部分认领：累计认领量达订单量后明细行状态必须更新为「已入库」。
"""

from datetime import date


class TestStockInReturnFifo:
    """待入库单多次收货后退回（原实现只扣第一条记录 → 负库存）"""

    def test_return_after_multiple_receives(self, client, auth_headers, foundation):
        h = auth_headers
        f = foundation
        pid = f["prods"]["全棉色织布"]["id"]
        # 采购订单（成品）→ 审核 → 转成品库待入库单 → 收货 10 → 收货 5
        po = client.post("/api/purchase/orders", json={
            "supplier_id": f["sup"], "currency_id": f["cny"]["id"],
            "items": [{"product_id": pid, "quantity": 100, "unit_price": 20, "tax_rate": 13}],
        }, headers=h).json()
        client.post(f"/api/purchase/orders/{po['id']}/approve", json={}, headers=h)
        po_detail = client.get(f"/api/purchase/orders/{po['id']}", headers=h).json()
        poi = po_detail["items"][0]
        r = client.post(f"/api/purchase/orders/{po['id']}/items/{poi['id']}/to-stock-in",
                        json={"stock_in_order_id": 0}, headers=h)
        assert r.status_code == 200, r.text[:200]
        sin_id = client.get("/api/stock-in?source_type=purchase&page_size=50", headers=h).json()["items"][0]["id"]
        r1 = client.post(f"/api/stock-in/{sin_id}/receive", json={"quantity": 10}, headers=h)
        assert r1.status_code == 200, r1.text[:200]
        r2 = client.post(f"/api/stock-in/{sin_id}/receive", json={"quantity": 5}, headers=h)
        assert r2.status_code == 200, r2.text[:200]

        # 退回 12（> 第一条收货 10）→ 不能负库存，FIFO 逐条扣
        r3 = client.post(f"/api/stock-in/{sin_id}/return", json={"return_qty": 12}, headers=h)
        assert r3.status_code == 200, f"退回失败: {r3.text[:250]}"
        from app.database import SessionLocal
        from app.models.inventory import WarehouseInventory
        db = SessionLocal()
        try:
            rows = db.query(WarehouseInventory).filter(
                WarehouseInventory.source_doc_id == sin_id,
                WarehouseInventory.source_type == "stock_in",
            ).all()
            assert rows, "待入库单无库存记录"
            assert all(r.quantity >= -0.001 for r in rows), \
                f"退回后出现负库存: {[(x.batch_no, x.quantity) for x in rows]}"
            total = sum(x.quantity or 0 for x in rows)
            assert abs(total - 3.0) < 0.01, f"退回后库存应剩 3，实际 {total}"
        finally:
            db.close()

    def test_purchase_receipt_blocked_after_to_stock_in(self, client, auth_headers, foundation):
        """双轨防重复：采购明细转待入库单后，采购入库页（po_receipt）必须拒绝再次入库"""
        h = auth_headers
        f = foundation
        pid = f["prods"]["全棉色织布"]["id"]
        po = client.post("/api/purchase/orders", json={
            "supplier_id": f["sup"], "currency_id": f["cny"]["id"],
            "items": [{"product_id": pid, "quantity": 100, "unit_price": 20, "tax_rate": 13}],
        }, headers=h).json()
        client.post(f"/api/purchase/orders/{po['id']}/approve", json={}, headers=h)
        po_detail = client.get(f"/api/purchase/orders/{po['id']}", headers=h).json()
        poi = po_detail["items"][0]
        # 转成品库待入库单
        r = client.post(f"/api/purchase/orders/{po['id']}/items/{poi['id']}/to-stock-in",
                        json={"stock_in_order_id": 0}, headers=h)
        assert r.status_code == 200, r.text[:200]
        # 采购入库页再入库 → 400（防重复）
        r2 = client.post("/api/purchase/receipts", json={
            "order_id": po["id"], "warehouse_id": f["wh_fg"],
            "items": [{"order_item_id": poi["id"], "product_id": pid, "quantity": 10, "unit_price": 20}],
        }, headers=h)
        # 产品类被「请使用转成品库」拦截（优先），材料类被「已转待入库单」拦截——两者都防重复
        assert r2.status_code == 400 and "转成品库" in r2.text, \
            f"转待入库单后采购入库页应拒绝，实际 {r2.status_code}: {r2.text[:200]}"


class TestClaimBatchCumulative:
    """多次部分认领累计达量 → 明细行状态更新为已入库"""

    def test_claim_cumulative_reaches_quantity(self, client, auth_headers, foundation):
        from app.database import SessionLocal
        from app.models.inventory import WarehouseInventory
        h = auth_headers
        f = foundation
        pid = f["prods"]["全棉色织布"]["id"]
        price = f["prods"]["全棉色织布"]["price"]

        # 备货批次库存（无归属）
        db = SessionLocal()
        try:
            db.add(WarehouseInventory(
                warehouse_id=f["wh_fg"], product_id=pid, batch_no="FG-CLAIM-001",
                quantity=100, unit_cost=10.0, total_cost=1000.0,
                in_date=date.today(), source_type="production",
            ))
            db.commit()
        finally:
            db.close()

        so = client.post("/api/sales/orders", json={
            "customer_id": f["cust"][0], "currency_id": f["cny"]["id"],
            "items": [{"product_id": pid, "quantity": 50, "unit_price": price, "tax_rate": 13}],
        }, headers=h).json()
        client.post(f"/api/sales/orders/{so['id']}/approve", json={}, headers=h)
        item = client.get(f"/api/sales/orders/{so['id']}", headers=h).json()["items"][0]
        assert item["production_status"] == "未生产"

        # 第一次认领 30 → 部分入库
        r1 = client.post(f"/api/sales/orders/{so['id']}/items/{item['id']}/claim-batch",
                         json={"batch_no": "FG-CLAIM-001", "quantity": 30}, headers=h)
        assert r1.status_code == 200, r1.text[:200]
        # 第二次认领 30（累计 60 ≥ 50）→ 已入库
        r2 = client.post(f"/api/sales/orders/{so['id']}/items/{item['id']}/claim-batch",
                         json={"batch_no": "FG-CLAIM-001", "quantity": 30}, headers=h)
        assert r2.status_code == 200, r2.text[:200]
        detail = client.get(f"/api/sales/orders/{so['id']}", headers=h).json()
        item2 = detail["items"][0]
        assert item2["production_status"] == "已入库", \
            f"累计认领达量后应已入库，实际 {item2['production_status']}"
