"""管理驾驶舱销售毛利专项测试：

- 两段式发货（通知→库管出库）的库存成本必须计入毛利（此前只匹配「销售发货」流水，
  两段式「成品出库」流水被漏算 → 成本=0 毛利虚高）；
- 销售退货单（is_return=1）必须负向冲减毛利（此前退货 revenue 不减）。
"""

from datetime import date


def _mk_inventory(client, db, foundation, batch_no, product_id, qty=100, unit_cost=10.0):
    """直接构造成品库存批次（测试台账，聚焦 dashboard 毛利逻辑）"""
    from app.models.inventory import WarehouseInventory
    wh = foundation["wh_fg"]
    db.add(WarehouseInventory(
        warehouse_id=wh, product_id=product_id, batch_no=batch_no,
        quantity=qty, unit_cost=unit_cost, total_cost=round(qty * unit_cost, 2),
        in_date=date.today(), source_type="production",
    ))
    db.commit()


class TestDashboardProfit:
    def test_two_stage_delivery_cost_included(self, client, auth_headers, foundation):
        """两段式发货（通知→库管出库）的库存成本计入毛利"""
        from app.database import SessionLocal
        h = auth_headers
        f = foundation
        pid = f["prods"]["全棉色织布"]["id"]
        price = f["prods"]["全棉色织布"]["price"]
        batch = "FG-DASH-001"

        db = SessionLocal()
        try:
            _mk_inventory(client, db, f, batch, pid, qty=100, unit_cost=10.0)
            # 销售订单 → 审核 → 通知发货 → 库管出库
            so = client.post("/api/sales/orders", json={
                "customer_id": f["cust"][0], "currency_id": f["cny"]["id"],
                "items": [{"product_id": pid, "quantity": 20, "unit_price": price, "tax_rate": 13}],
            }, headers=h).json()
            client.post(f"/api/sales/orders/{so['id']}/approve", json={}, headers=h)
            item = client.get(f"/api/sales/orders/{so['id']}", headers=h).json()["items"][0]
            notify = client.post("/api/sales/deliveries/notify", json={
                "order_item_id": item["id"], "quantity": 10,
            }, headers=h)
            assert notify.status_code == 200, notify.text[:200]
            sd_id = notify.json()["id"]
            issue = client.post(f"/api/sales/deliveries/{sd_id}/issue", json={
                "batch_no": batch, "quantity": 10,
            }, headers=h)
            assert issue.status_code == 200, issue.text[:200]

            # dashboard 毛利：该产品应有一行（成本 = 10×10，收入 = 10×price）
            dash = client.get("/api/dashboard", headers=h).json()
            row = next((p for p in dash["profit"] if p["product_id"] == pid), None)
            assert row, "dashboard 毛利缺该产品行"
            assert row["cost"] == 100.0, f"两段式发货成本应=100，实际 {row['cost']}"
            assert row["revenue"] == round(10 * price, 2), f"收入应={10*price}，实际 {row['revenue']}"
        finally:
            db.close()

    def test_return_reduces_profit(self, client, auth_headers, foundation):
        """销售退货必须负向冲减毛利"""
        from app.database import SessionLocal
        h = auth_headers
        f = foundation
        pid = f["prods"]["全棉色织布"]["id"]
        price = f["prods"]["全棉色织布"]["price"]
        batch = "FG-DASH-002"

        db = SessionLocal()
        try:
            _mk_inventory(client, db, f, batch, pid, qty=100, unit_cost=10.0)
            so = client.post("/api/sales/orders", json={
                "customer_id": f["cust"][0], "currency_id": f["cny"]["id"],
                "items": [{"product_id": pid, "quantity": 20, "unit_price": price, "tax_rate": 13}],
            }, headers=h).json()
            client.post(f"/api/sales/orders/{so['id']}/approve", json={}, headers=h)
            item = client.get(f"/api/sales/orders/{so['id']}", headers=h).json()["items"][0]
            notify = client.post("/api/sales/deliveries/notify", json={
                "order_item_id": item["id"], "quantity": 10,
            }, headers=h).json()
            client.post(f"/api/sales/deliveries/{notify['id']}/issue", json={
                "batch_no": batch, "quantity": 10,
            }, headers=h)

            before = client.get("/api/dashboard", headers=h).json()
            before_row = next(p for p in before["profit"] if p["product_id"] == pid)

            # 退货 2 个
            ret = client.post("/api/sales/deliveries/return", json={
                "order_item_id": item["id"], "batch_no": batch, "quantity": 2,
            }, headers=h)
            assert ret.status_code == 200, ret.text[:250]

            after = client.get("/api/dashboard", headers=h).json()
            after_rows = [p for p in after["profit"] if p["product_id"] == pid]
            # 退货单为独立负行：收入 = -2×price
            ret_row = next((p for p in after_rows if p["revenue"] < 0), None)
            assert ret_row, "退货单未出现在毛利（应为负收入行）"
            assert ret_row["revenue"] == round(-2 * price, 2), \
                f"退货收入应={-2*price}，实际 {ret_row['revenue']}"
            # 毛利总额应小于退货前
            total_before = sum(p["gross_profit"] for p in before["profit"] if p["product_id"] == pid)
            total_after = sum(p["gross_profit"] for p in after_rows)
            assert total_after < total_before, f"退货后毛利应减少：{total_before} → {total_after}"
        finally:
            db.close()
