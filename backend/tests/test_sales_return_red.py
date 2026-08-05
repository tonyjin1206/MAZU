"""
销售退货 · 发票红冲 · 退款 · 核销转移 · 负数申报 专项测试（2026-08-03）
=====================================================================
覆盖场景矩阵：
  (1) 已发货未开票退货：红字发货单 + 库存回库 + 订单回退（回归）
  (2) 已发货已开票退货：全额红冲发票（手工录入红字票）+ 红字应收等额联动
      + 开票额度校验（超限拒绝 / 红冲后额度返还可补开新票）
  (3) 已收款退货：负数收款单（退款）核销红字应收，退超拦截，删退款单回滚
  (4) 已报税退货：退货单 refund_declared=1 → 负数申报（候选 + 冲减行 + 出口额重算）
  核销转移：红字应收 → 同客户正应收；跨客户/超上限拒绝
  保护：红字发票禁改/禁删；已收款发票禁删

数据规范：基础档案全部来自共享 foundation fixture（tests/test_data.py）。
库存初始化走测试库 DB 直插（测试库隔离，不触碰开发库）。
"""

from datetime import date

from app.database import SessionLocal
from app.models.inventory import WarehouseInventory


def _seed_inventory(product_id, warehouse_id, batch_no, qty, unit_cost=9.0):
    """测试库直插台账行（盘盈/生产链路太重，仅测试用）"""
    db = SessionLocal()
    try:
        db.add(WarehouseInventory(
            warehouse_id=warehouse_id, product_id=product_id,
            batch_no=batch_no, quantity=qty,
            unit_cost=unit_cost, total_cost=round(qty * unit_cost, 2),
            in_date=date.today(), source_type="purchase_in",
        ))
        db.commit()
    finally:
        db.close()


class TestSalesReturnRedReverse:

    @staticmethod
    def _api(client, method, path, json_data=None, headers=None):
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            resp = client.post(path, json=json_data or {}, headers=headers)
        elif method == "PUT":
            resp = client.put(path, json=json_data or {}, headers=headers)
        elif method == "DELETE":
            resp = client.delete(path, headers=headers)
        else:
            raise ValueError(f"未知 method: {method}")
        return resp

    def _make_test_warehouse(self, client, h, tag):
        """独立测试仓库（避免污染共享 FG 仓，影响其他测试的盘点）"""
        return self._api(client, "POST", "/api/foundation/warehouses", {
            "code": f"TR{tag}", "name": f"测试仓{tag}", "wh_type": "成品仓",
            "address": "浙江省绍兴市柯桥区测试路1号", "manager": "测试员",
        }, h).json()["id"]

    def _make_order_and_delivery(self, client, h, f, tag, wh_id, qty=100):
        """建订单 → 审批 → 发货 qty 件，返回 (so_id, delivery_id, unit_price)"""
        api = self._api
        pid = f["prods"]["纯棉坯布"]["id"]
        unit_price = f["prods"]["纯棉坯布"]["price"]
        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": f["cust"][0], "currency_id": f["cny"]["id"],
            "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": qty, "unit_price": unit_price, "tax_rate": 13}],
        }, h).json()
        so_id = so["id"]
        api(client, "POST", f"/api/sales/orders/{so_id}/approve", {}, h)
        detail = api(client, "GET", f"/api/sales/orders/{so_id}", None, h).json()
        oi_id = detail["items"][0]["id"]
        dv = api(client, "POST", "/api/sales/deliveries", {
            "order_id": so_id, "order_item_id": oi_id,
            "batch_no": f"BATCH-{tag}", "quantity": qty,
            "warehouse_id": wh_id, "delivery_date": "2026-08-03",
        }, h).json()
        return so_id, dv["id"], unit_price

    def _make_invoice(self, client, h, so_id, total, no="INV-0"):
        """开蓝字发票（含税 total），返回发票对象"""
        api = self._api
        return api(client, "POST", "/api/sales/invoices", {
            "invoice_no": no, "order_id": so_id,
            "invoice_date": "2026-08-03",
            "amount": round(total / 1.13, 2),
            "amount_fc": round(total / 1.13, 2),
            "tax_amount": round(total * 0.13 / 1.13, 2),
            "total_amount": total, "tax_rate": 13,
        }, h).json()

    def _find_ar(self, client, h, invoice_id=None, is_red=None):
        """从应收列表找应收记录"""
        items = self._api(client, "GET", "/api/sales/ar?page_size=100", None, h).json()["items"]
        for ar in items:
            if invoice_id is not None and ar["source_id"] != invoice_id:
                continue
            if is_red is not None and (ar.get("is_red") or 0) != is_red:
                continue
            return ar
        return None

    # ======================== 场景(1) 未开票退货 ========================

    def test_scene1_no_invoice_return(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A1")
        _seed_inventory(pid, wh_id, "BATCH-A1", 100)
        so_id, dv_id, _ = self._make_order_and_delivery(client, h, f, "A1", wh_id)

        # 退货 40 → 未开票场景：只做红字发货单，无发票提示（invoiced=0）
        ret = api(client, "POST", f"/api/sales/deliveries/{dv_id}/return",
                  {"quantity": 40, "remark": "质量退货"}, h)
        assert ret.status_code == 200, ret.text
        body = ret.json()
        assert body["invoice_status"]["invoiced_amount"] == 0
        assert body["invoice_status"]["return_amount"] == round(40 * f["prods"]["纯棉坯布"]["price"], 2)

        # 红字发货单存在（is_return=1, 数量为负）
        items = api(client, "GET", "/api/sales/deliveries?page_size=100", None, h).json()["items"]
        red_dv = next((d for d in items if d.get("is_return") and d["return_of_delivery_id"] == dv_id), None)
        assert red_dv, "应生成红字退货单"
        assert red_dv["quantity"] == -40

        # 订单 delivered_qty 回退 60，状态 部分发货
        detail = api(client, "GET", f"/api/sales/orders/{so_id}", None, h).json()
        assert detail["items"][0]["delivered_qty"] == 60, detail["items"][0]
        assert detail["status"] == "部分发货", detail["status"]

        # 库存回库：100 出 - 40 退 = 回 40
        bal = api(client, "GET", "/api/inventory/balance?type=product&page_size=100", None, h).json()
        row = next((r for r in bal["items"] if r["batch_no"] == "BATCH-A1"), None)
        assert row and row["quantity"] == 40, f"库存应回库到 40，实际 {row}"

    # ======================== 场景(2) 已开票 → 全额红冲 ========================

    def test_scene2_red_reverse_invoice(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A2")
        _seed_inventory(pid, wh_id, "BATCH-A2", 100)
        so_id, dv_id, unit_price = self._make_order_and_delivery(client, h, f, "A2", wh_id)
        total = round(100 * unit_price, 2)

        # 开票 → 红冲（金额必须 = 原票全额负）
        inv = self._make_invoice(client, h, so_id, total, no="INV-A2")
        red = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RED-A2", "order_id": so_id,
            "invoice_date": "2026-08-03", "red_of_invoice_id": inv["id"],
            "amount": round(-total / 1.13, 2),
            "tax_amount": round(-total * 0.13 / 1.13, 2),
            "total_amount": -total, "tax_rate": 13,
        }, h)
        assert red.status_code == 200, red.text
        assert "红字应收" in red.json()["message"]

        # 原票已红冲；红字票 is_red=1 且 red_of_invoice_no=原票号
        invs = api(client, "GET", "/api/sales/invoices?page_size=100", None, h).json()["items"]
        orig = next(x for x in invs if x["id"] == inv["id"])
        red_inv = next(x for x in invs if x.get("is_red"))
        assert orig["status"] == "已红冲", orig["status"]
        assert red_inv["total_amount"] == -total
        assert red_inv["red_of_invoice_no"] == inv["invoice_no"]

        # 红字应收等额负，red_of_ar_no 指向原应收
        red_ar = self._find_ar(client, h, invoice_id=red_inv["id"], is_red=1)
        assert red_ar and red_ar["amount"] == -total, red_ar
        assert red_ar["red_of_ar_no"], "红字应收应关联原应收号"

        # 红字发票不能再红冲；金额不符拒绝
        r2 = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RED-A2-X", "order_id": so_id,
            "red_of_invoice_id": red_inv["id"],
            "amount": -10, "tax_amount": -1.3, "total_amount": -11.3, "tax_rate": 13,
        }, h)
        assert r2.status_code == 400 and "红字发票不能再次红冲" in r2.text, r2.text
        r3 = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RED-A2-Y", "order_id": so_id,
            "red_of_invoice_id": inv["id"],
            "amount": -10, "tax_amount": -1.3, "total_amount": -11.3, "tax_rate": 13,
        }, h)
        # 原票已被红冲 → 拦截（校验顺序：已红冲先于金额校验）
        assert r3.status_code == 400 and "已红冲" in r3.text, r3.text

        # 红字发票禁止修改 / 删除
        m = api(client, "PUT", f"/api/sales/invoices/{red_inv['id']}", {"total_amount": -50}, h)
        assert m.status_code == 400 and "红字发票禁止修改" in m.text, m.text
        d = api(client, "DELETE", f"/api/sales/invoices/{red_inv['id']}", None, h)
        assert d.status_code == 400 and "红字发票禁止删除" in d.text, d.text

        # 已红冲原票禁止删除
        d2 = api(client, "DELETE", f"/api/sales/invoices/{inv['id']}", None, h)
        assert d2.status_code == 400 and "已红冲" in d2.text, d2.text

    def test_invoice_limit_and_reopen(self, client, auth_headers, foundation):
        """开票额度：超限拒绝；全额红冲后额度返还 → 可补开新票"""
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A3")
        _seed_inventory(pid, wh_id, "BATCH-A3", 100)
        so_id, _, unit_price = self._make_order_and_delivery(client, h, f, "A3", wh_id)
        total = round(100 * unit_price, 2)

        inv = self._make_invoice(client, h, so_id, total, no="INV-A3")
        # 超限开票 → 400
        over = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-OVER", "order_id": so_id, "invoice_date": "2026-08-03",
            "amount": total, "total_amount": total + 1000, "tax_rate": 13,
        }, h)
        assert over.status_code == 400 and "未开票金额" in over.text, over.text

        # 全额红冲 → 额度返还 → 补开新票成功（部分金额）
        red = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RED-A3", "order_id": so_id, "red_of_invoice_id": inv["id"],
            "invoice_date": "2026-08-03",
            "amount": round(-total / 1.13, 2), "tax_amount": round(-total * 0.13 / 1.13, 2),
            "total_amount": -total, "tax_rate": 13,
        }, h)
        assert red.status_code == 200, red.text
        reopen = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-NEW-A3", "order_id": so_id, "invoice_date": "2026-08-03",
            "amount": round(total * 0.6 / 1.13, 2), "tax_amount": round(total * 0.6 * 0.13 / 1.13, 2),
            "total_amount": round(total * 0.6, 2), "tax_rate": 13,
        }, h)
        assert reopen.status_code == 200, f"红冲后应可补开新票: {reopen.text}"

    # ======================== 场景(3) 已收款 → 退款 ========================

    def test_scene3_refund_negative_collection(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A4")
        _seed_inventory(pid, wh_id, "BATCH-A4", 100)
        so_id, _, unit_price = self._make_order_and_delivery(client, h, f, "A4", wh_id)
        total = round(100 * unit_price, 2)
        cust = f["cust"][0]

        inv = self._make_invoice(client, h, so_id, total, no="INV-A4")
        ar = self._find_ar(client, h, invoice_id=inv["id"])
        # 收款 400（部分收款，≤ 应收余额 932）
        coll = api(client, "POST", "/api/sales/collections", {
            "customer_id": cust, "amount": 400, "ar_account_id": ar["id"],
            "payment_method": "银行转账", "collection_date": "2026-08-03",
        }, h)
        assert coll.status_code == 200, coll.text

        # 红冲发票 → 红字应收 -total
        red = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RED-A4", "order_id": so_id, "red_of_invoice_id": inv["id"],
            "invoice_date": "2026-08-03",
            "amount": round(-total / 1.13, 2), "tax_amount": round(-total * 0.13 / 1.13, 2),
            "total_amount": -total, "tax_rate": 13,
        }, h)
        assert red.status_code == 200, red.text
        red_ar = self._find_ar(client, h, is_red=1)

        # 已收款发票禁止删除（此处原票已红冲 → 同样被拦截禁止删除）
        dd = api(client, "DELETE", f"/api/sales/invoices/{inv['id']}", None, h)
        assert dd.status_code == 400 and "禁止删除" in dd.text, dd.text

        # 退款 400（负数收款单）→ 红字应收向 0 靠拢：-932 + 400 = -532
        refund = api(client, "POST", "/api/sales/collections", {
            "customer_id": cust, "amount": -400, "ar_account_id": red_ar["id"],
            "payment_method": "电汇退款", "collection_date": "2026-08-03",
        }, h)
        assert refund.status_code == 200, refund.text
        assert "退款" in refund.json()["message"]
        red_ar2 = self._find_ar(client, h, is_red=1)
        assert abs(red_ar2["balance"] - (-total + 400)) < 0.01, \
            f"红字应收应变为 {-total+400:.2f}，实际 {red_ar2['balance']}"

        # 退超拦截：已退 400，最多再退 532
        over = api(client, "POST", "/api/sales/collections", {
            "customer_id": cust, "amount": -700, "ar_account_id": red_ar2["id"],
            "collection_date": "2026-08-03",
        }, h)
        assert over.status_code == 400 and "超过可退余额" in over.text, over.text

        # 退款单删除 → 红字应收回滚
        colls = api(client, "GET", "/api/sales/collections?page_size=100", None, h).json()["items"]
        refund_coll = next(x for x in colls if x["amount"] < 0)
        dr = api(client, "DELETE", f"/api/sales/collections/{refund_coll['id']}", None, h)
        assert dr.status_code == 200, dr.text
        red_ar3 = self._find_ar(client, h, is_red=1)
        assert red_ar3["balance"] == -total, f"删除退款单后应回滚到 -{total}"

    # ======================== 核销转移 ========================

    def test_transfer_ar(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A5")
        _seed_inventory(pid, wh_id, "BATCH-A5", 100)
        so_id, _, unit_price = self._make_order_and_delivery(client, h, f, "A5", wh_id)
        total = round(100 * unit_price, 2)
        cust = f["cust"][0]

        # 红字应收 -total（红冲）
        inv = self._make_invoice(client, h, so_id, total, no="INV-A5")
        red = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RED-A5", "order_id": so_id, "red_of_invoice_id": inv["id"],
            "invoice_date": "2026-08-03",
            "amount": round(-total / 1.13, 2), "tax_amount": round(-total * 0.13 / 1.13, 2),
            "total_amount": -total, "tax_rate": 13,
        }, h)
        assert red.status_code == 200, red.text
        red_ar = self._find_ar(client, h, is_red=1)

        # 同客户第二张正应收（另一订单开票，不发货也能开票——未开票校验只看订单）
        pid2 = f["prods"]["全棉色织布"]["id"]
        so2 = api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": f["cny"]["id"], "payment_terms": "TT",
            "items": [{"product_id": pid2, "quantity": 10, "unit_price": f["prods"]["全棉色织布"]["price"], "tax_rate": 13}],
        }, h).json()
        api(client, "POST", f"/api/sales/orders/{so2['id']}/approve", {}, h)
        total2 = round(10 * f["prods"]["全棉色织布"]["price"], 2)
        inv2 = self._make_invoice(client, h, so2["id"], total2, no="INV-A5-2")
        ar2 = self._find_ar(client, h, invoice_id=inv2["id"])

        # 转移 min(总额, total2) 的一部分
        move_amt = 3000 if total2 > 3000 else round(total2 / 2, 2)
        tr = api(client, "POST", "/api/sales/ar/transfer", {
            "source_ar_id": red_ar["id"], "target_ar_id": ar2["id"], "amount": move_amt,
        }, h)
        assert tr.status_code == 200, tr.text
        red_ar2 = self._find_ar(client, h, is_red=1)
        ar2b = self._find_ar(client, h, invoice_id=inv2["id"])
        assert abs(red_ar2["balance"] - (-total + move_amt)) < 0.01, red_ar2["balance"]
        assert abs(ar2b["balance"] - (total2 - move_amt)) < 0.01, ar2b["balance"]

        # 超上限拦截
        over = api(client, "POST", "/api/sales/ar/transfer", {
            "source_ar_id": red_ar["id"], "target_ar_id": ar2["id"],
            "amount": abs(red_ar2["balance"]) + abs(ar2b["balance"]) + 1,
        }, h)
        assert over.status_code == 400 and "超过可转移上限" in over.text, over.text

        # 跨客户禁止
        other_cust = f["cust"][1]
        so3 = api(client, "POST", "/api/sales/orders", {
            "customer_id": other_cust, "currency_id": f["cny"]["id"], "payment_terms": "TT",
            "items": [{"product_id": pid2, "quantity": 5, "unit_price": f["prods"]["全棉色织布"]["price"], "tax_rate": 13}],
        }, h).json()
        api(client, "POST", f"/api/sales/orders/{so3['id']}/approve", {}, h)
        total3 = round(5 * f["prods"]["全棉色织布"]["price"], 2)
        inv3 = self._make_invoice(client, h, so3["id"], total3, no="INV-A5-3")
        ar3 = self._find_ar(client, h, invoice_id=inv3["id"])
        cross = api(client, "POST", "/api/sales/ar/transfer", {
            "source_ar_id": red_ar2["id"], "target_ar_id": ar3["id"], "amount": 100,
        }, h)
        assert cross.status_code == 400 and "跨客户" in cross.text, cross.text

        # ===== 明细子表（collection-detail）必须反映转移汇总与行级流水 =====
        cd_items = api(client, "GET", "/api/sales/ar/collection-detail", None, h).json()["items"]
        red_row = next(r for r in cd_items if r["ar_id"] == red_ar2["id"])
        tar_row = next(r for r in cd_items if r["ar_id"] == ar2b["id"])
        # 每行 = 一张应收单（汇总字段）
        assert abs(red_row["transfer_amount"] - (-move_amt)) < 0.01, red_row["transfer_amount"]
        assert abs(tar_row["transfer_amount"] - move_amt) < 0.01, tar_row["transfer_amount"]
        assert tar_row["transfer_count"] == 1 and red_row["transfer_count"] == 1
        # 两端都无真实收款核销（只有转移）→ 收款净额为 0
        assert abs(red_row["collection_amount"]) < 0.01 and abs(tar_row["collection_amount"]) < 0.01
        assert abs(red_row["ar_collected"] - (-move_amt)) < 0.01, red_row["ar_collected"]
        # 余额 = 应收 - 核销转移 - 收款 恒成立
        for row, ar in ((red_row, red_ar2), (tar_row, ar2b)):
            assert abs((row["ar_amount"] - row["transfer_amount"] - row["collection_amount"]) - ar["balance"]) < 0.01, row
        # 行级流水（详情弹窗用）：转移流水方向/金额/adj 关联
        adj_src = next(f for f in red_row["flows"] if f["flow_type"] == "核销转移")
        adj_tgt = next(f for f in tar_row["flows"] if f["flow_type"] == "核销转移")
        assert adj_src["collected_amount"] == -move_amt and adj_src["adj_direction"] == "source", adj_src
        assert adj_tgt["collected_amount"] == move_amt and adj_tgt["adj_direction"] == "target", adj_tgt
        assert adj_src["adj_id"] == adj_tgt["adj_id"] == tr.json()["id"], "转移流水应关联同一 adj"
        assert adj_tgt["other_ar_no"] == red_ar2["ar_no"], adj_tgt

        # ===== 撤销核销转移：账务回滚 + 流水消失 + 重复撤销 404 =====
        cc = api(client, "POST", f"/api/sales/ar/transfer/{tr.json()['id']}/cancel", None, h)
        assert cc.status_code == 200, cc.text
        red_ar3 = self._find_ar(client, h, is_red=1)
        ar2c = self._find_ar(client, h, invoice_id=inv2["id"])
        assert abs(red_ar3["balance"] - (-total)) < 0.01, red_ar3["balance"]
        assert abs(ar2c["balance"] - total2) < 0.01, ar2c["balance"]
        cd_items2 = api(client, "GET", "/api/sales/ar/collection-detail", None, h).json()["items"]
        assert not any(f.get("flow_type") == "核销转移" for r in cd_items2 for f in r.get("flows", [])), "撤销后转移流水应消失"
        assert next(r for r in cd_items2 if r["ar_id"] == red_ar2["id"])["transfer_count"] == 0
        cc2 = api(client, "POST", f"/api/sales/ar/transfer/{tr.json()['id']}/cancel", None, h)
        assert cc2.status_code == 404, cc2.text

    # ======================== 收款单审核锁定 ========================

    def test_collection_review_lock(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A7")
        _seed_inventory(pid, wh_id, "BATCH-A7", 100)
        so_id, _, unit_price = self._make_order_and_delivery(client, h, f, "A7", wh_id)
        total = round(100 * unit_price, 2)
        inv = self._make_invoice(client, h, so_id, total, no="INV-A7")
        ar = self._find_ar(client, h, invoice_id=inv["id"])

        # 收款 500 → 收款单
        cc = api(client, "POST", "/api/sales/collections", {
            "customer_id": f["cust"][0], "amount": 500, "amount_fc": 500,
            "collection_date": "2026-08-05", "payment_method": "银行转账",
            "remark": "审核锁定测试", "ar_account_id": ar["id"],
        }, h)
        assert cc.status_code == 200, cc.text
        col_id = cc.json()["id"]

        # 审核 → 列表标记 reviewed + 审核人；重复审核拦截
        rv = api(client, "POST", f"/api/sales/collections/{col_id}/review", None, h)
        assert rv.status_code == 200, rv.text
        items = api(client, "GET", "/api/sales/collections?page_size=100", None, h).json()["items"]
        row = next(c for c in items if c["id"] == col_id)
        assert row["reviewed"] == 1 and row["reviewed_by"], row
        rv2 = api(client, "POST", f"/api/sales/collections/{col_id}/review", None, h)
        assert rv2.status_code == 400, rv2.text

        # 审核后修改/删除 → 400（业务锁定）
        up = api(client, "PUT", f"/api/sales/collections/{col_id}", {"remark": "x"}, h)
        assert up.status_code == 400 and "已审核" in up.text, up.text
        dl = api(client, "DELETE", f"/api/sales/collections/{col_id}", None, h)
        assert dl.status_code == 400 and "已审核" in dl.text, dl.text

        # 取消审核 → 修改/删除放行；删除后应收回滚
        ur = api(client, "POST", f"/api/sales/collections/{col_id}/unreview", None, h)
        assert ur.status_code == 200, ur.text
        ur2 = api(client, "POST", f"/api/sales/collections/{col_id}/unreview", None, h)
        assert ur2.status_code == 400, ur2.text
        up2 = api(client, "PUT", f"/api/sales/collections/{col_id}", {"remark": "y"}, h)
        assert up2.status_code == 200, up2.text
        dl2 = api(client, "DELETE", f"/api/sales/collections/{col_id}", None, h)
        assert dl2.status_code == 200, dl2.text
        ar2 = self._find_ar(client, h, invoice_id=inv["id"])
        assert abs(ar2["collected_amount"] - 0) < 0.01, ar2
        assert abs(ar2["balance"] - total) < 0.01, ar2["balance"]

    # ======================== 付款单审核锁定 ========================

    def test_payment_review_lock(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        # 采购订单 → 审批 → 采购发票（生成应付）→ 付款
        po = api(client, "POST", "/api/purchase/orders", {
            "supplier_id": f["sup"], "remark": "审核锁定测试",
            "items": [{"material_id": f["mats"]["纯棉经纱"], "quantity": 10, "unit_price": 5}],
        }, h)
        assert po.status_code == 200, po.text
        po_id = po.json()["id"]
        api(client, "POST", f"/api/purchase/orders/{po_id}/approve", {}, h)
        inv = api(client, "POST", "/api/purchase/invoices", {
            "order_id": po_id, "supplier_id": f["sup"], "invoice_no": "PINV-A7",
            "invoice_date": "2026-08-05", "invoice_type": "增值税专用发票",
            "amount": 50, "amount_fc": 50, "tax_amount": 6.5, "remark": "",
        }, h)
        assert inv.status_code == 200, inv.text
        inv_id = inv.json()["id"]
        ap = next(a for a in api(client, "GET", "/api/purchase/ap?page_size=100", None, h).json()["items"]
                  if a["source_type"] == "purchase_invoice" and a["source_id"] == inv_id)

        pm = api(client, "POST", "/api/purchase/payments", {
            "supplier_id": f["sup"], "amount": 30, "amount_fc": 30,
            "payment_date": "2026-08-05", "payment_method": "银行转账",
            "remark": "审核锁定测试", "ap_account_ids": ap["id"],
        }, h)
        assert pm.status_code == 200, pm.text
        pm_id = pm.json()["id"]

        # 审核 → 列表标记 reviewed；重复审核拦截
        rv = api(client, "POST", f"/api/purchase/payments/{pm_id}/review", None, h)
        assert rv.status_code == 200, rv.text
        items = api(client, "GET", "/api/purchase/payments?page_size=100", None, h).json()["items"]
        row = next(p for p in items if p["id"] == pm_id)
        assert row["reviewed"] == 1 and row["reviewed_by"], row
        rv2 = api(client, "POST", f"/api/purchase/payments/{pm_id}/review", None, h)
        assert rv2.status_code == 400, rv2.text

        # 审核后修改/删除 → 400（业务锁定）
        up = api(client, "PUT", f"/api/purchase/payments/{pm_id}", {"remark": "x"}, h)
        assert up.status_code == 400 and "已审核" in up.text, up.text
        dl = api(client, "DELETE", f"/api/purchase/payments/{pm_id}", None, h)
        assert dl.status_code == 400 and "已审核" in dl.text, dl.text

        # 取消审核 → 修改/删除放行；删除后应付回滚
        ur = api(client, "POST", f"/api/purchase/payments/{pm_id}/unreview", None, h)
        assert ur.status_code == 200, ur.text
        up2 = api(client, "PUT", f"/api/purchase/payments/{pm_id}", {"remark": "y"}, h)
        assert up2.status_code == 200, up2.text
        dl2 = api(client, "DELETE", f"/api/purchase/payments/{pm_id}", None, h)
        assert dl2.status_code == 200, dl2.text
        ap2 = next(a for a in api(client, "GET", "/api/purchase/ap?page_size=100", None, h).json()["items"]
                   if a["source_type"] == "purchase_invoice" and a["source_id"] == inv_id)
        assert abs(ap2["paid_amount"] - 0) < 0.01, ap2
        assert abs(ap2["balance"] - 56.5) < 0.01, ap2["balance"]

    # ======================== 场景(4) 已报税退货 → 负数申报 ========================

    def test_scene4_declared_return_negative_declaration(self, client, auth_headers, foundation):
        api, h, f = self._api, auth_headers, foundation
        pid = f["prods"]["纯棉坯布"]["id"]
        wh_id = self._make_test_warehouse(client, h, "A6")
        _seed_inventory(pid, wh_id, "BATCH-A6", 100)
        so_id, dv_id, unit_price = self._make_order_and_delivery(client, h, f, "A6", wh_id)
        total = round(100 * unit_price, 2)

        # 报关 → 标记已申报（模拟税局申报完成）
        customs = api(client, "POST", "/api/sales/customs", {
            "customs_no": "223320260803000001", "order_id": so_id,
            "delivery_id": dv_id, "hs_code_id": 1, "declare_amount": total,
            "declare_currency": f["cny"]["id"], "declare_date": "2026-08-03",
        }, h).json()
        up = api(client, "PUT", f"/api/sales/customs/{customs['id']}",
                 {"refund_status": "已申报"}, h)
        assert up.status_code == 200, up.text

        # 退货 → refund_declared=1 + 提示已报税
        ret = api(client, "POST", f"/api/sales/deliveries/{dv_id}/return",
                  {"quantity": 40}, h)
        assert ret.status_code == 200, ret.text
        assert "负数申报" in ret.json()["message"], ret.json()["message"]

        from app.database import SessionLocal as _SL
        from app.models.sales import SalesDelivery
        db = _SL()
        try:
            rd = db.query(SalesDelivery).filter(
                SalesDelivery.return_of_delivery_id == dv_id).first()
            assert rd and rd.refund_declared == 1, "退货单应标记 refund_declared=1"
            return_qty_amt = rd.amount  # 负
        finally:
            db.close()

        # 次月申报表 → 负数申报候选 → 添加冲减行 → 出口额自动重算
        decl = api(client, "POST", "/api/tax-refund/declarations", {
            "declaration_no": "TD-202609-001", "declare_date": "2026-09-01",
            "period": "202609", "export_amount_fob": total,
            "tax_rate": 13, "refund_rate": 13,
            "input_tax": round(total * 0.13 / 1.13, 2),
        }, h).json()
        cands = api(client, "GET", f"/api/tax-refund/declarations/{decl['id']}/return-candidates", None, h)
        assert cands.status_code == 200, cands.text
        cand_items = cands.json()["items"]
        assert any(c["return_no"] == ret.json()["return_no"] for c in cand_items), cand_items
        target = next(c for c in cand_items if c["return_no"] == ret.json()["return_no"])
        assert target["taxable_amount"] == return_qty_amt, target

        adj = api(client, "POST", f"/api/tax-refund/declarations/{decl['id']}/return-adjustments",
                  {"delivery_id": target["delivery_id"]}, h)
        assert adj.status_code == 200, adj.text
        body = adj.json()
        assert body["export_amount_fob"] == round(total + return_qty_amt, 2), body

        # 明细行含负数行（voucher_no=退货单号，无进项发票）
        detail = api(client, "GET", f"/api/tax-refund/declarations/{decl['id']}", None, h).json()
        neg_rows = [r for r in detail["rows"] if r["voucher_no"] == ret.json()["return_no"]]
        assert neg_rows and neg_rows[0]["taxable_amount"] < 0, detail["rows"]

        # 已添加的退货单不再出现在候选
        cands2 = api(client, "GET", f"/api/tax-refund/declarations/{decl['id']}/return-candidates", None, h).json()
        assert all(c["return_no"] != ret.json()["return_no"] for c in cands2["items"])
