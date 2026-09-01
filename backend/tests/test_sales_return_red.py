"""批2 销售退货财务层：发票红冲 · 红字应收 · 退款 · 核销转移 · 负数申报 专项测试

依赖：foundation fixture（tests/test_data.py 基础档案）+ 建销售订单→审批→开票 最小流程。
范围：销售发票红冲（蓝字上限校验/红字禁改禁删）、红字应收生成、退款（负数收款核销红字应收/退超拦截）、
     核销转移（红字→正余额、同客户、上限、审计留痕）、负数申报（return-candidates/return-adjustments）。
"""

import pytest


class TestSalesInvoiceRed:
    """发票红冲 + 红字应收 + 蓝字开票上限"""

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
        if resp.status_code >= 400:
            print(f"   ❌ {method} {path} → {resp.status_code}: {resp.text[:250]}")
        return resp

    def _create_order(self, client, h, f, qty=100, price=15.0):
        """建销售订单 → 审批，返回 (so_id, total_amount)"""
        cust = f["cust"][0]
        cny = f["cny"]
        pid = f["prods"]["全棉色织布"]["id"]
        r = self._api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": qty, "unit_price": price, "tax_rate": 13}],
        }, h)
        assert r.status_code == 200, f"建订单失败: {r.text}"
        so = r.json()
        self._api(client, "POST", f"/api/sales/orders/{so['id']}/approve", {}, h)
        total = round(qty * price, 2)
        return so["id"], total

    def _invoice(self, client, h, order_id, invoice_no, amount, tax_amount=0, total_amount=None, extra=None):
        """开票 """
        body = {
            "invoice_no": invoice_no, "order_id": order_id, "invoice_date": "2026-08-28",
            "amount": amount, "amount_fc": amount, "tax_amount": tax_amount,
            "total_amount": total_amount if total_amount is not None else round(amount + tax_amount, 2),
            "tax_rate": 13,
        }
        if extra:
            body.update(extra)
        return self._api(client, "POST", "/api/sales/invoices", body, h)

    def test_blue_invoice_and_limit(self, client, auth_headers, foundation):
        """蓝字开票成功 + 超未开票金额拒绝（上限校验）"""
        so_id, total = self._create_order(client, auth_headers, foundation)
        # 全额开票成功
        r = self._invoice(client, auth_headers, so_id, "INV-BLUE-001", round(total / 1.13, 2),
                          round(total * 0.13 / 1.13, 2), total)
        assert r.status_code == 200, f"全额开票失败: {r.text}"
        # 再开超上限 → 400
        r2 = self._invoice(client, auth_headers, so_id, "INV-BLUE-002", 100, 13, 113)
        assert r2.status_code == 400, f"超上限开票应拒绝，实际 {r2.status_code}: {r2.text}"
        assert "超过未开票金额" in r2.text

    def test_red_invoice_chain(self, client, auth_headers, foundation):
        """红字发票：全额红冲 → 红字应收生成 → 红字票禁改禁删 → 原票已红冲禁删 """
        so_id, total = self._create_order(client, auth_headers, foundation)
        # 蓝字全额开票
        amt = round(total / 1.13, 2)
        tax = round(total * 0.13 / 1.13, 2)
        r = self._invoice(client, auth_headers, so_id, "INV-RED-001", amt, tax, total)
        assert r.status_code == 200, f"蓝字开票失败: {r.text}"
        inv_id = r.json()["id"]
        ar_no = r.json()["ar_no"]

        # 红字全额红冲（金额需 = 原票负数）
        red = self._invoice(client, auth_headers, so_id, "INV-RED-R1", -amt, -tax, -total,
                            {"red_of_invoice_id": inv_id})
        assert red.status_code == 200, f"红冲失败: {red.text}"
        assert "已红冲" in red.json()["message"]
        red_inv_id = red.json()["id"]
        red_ar_no = red.json()["ar_no"]

        # 红字票禁改
        ru = self._api(client, "PUT", f"/api/sales/invoices/{red_inv_id}",
                        {"total_amount": -999}, auth_headers)
        assert ru.status_code == 400, f"红字票应禁改，实际 {ru.status_code}"
        assert "红字发票不可修改" in ru.text

        # 红字票禁删
        rd = self._api(client, "DELETE", f"/api/sales/invoices/{red_inv_id}", headers=auth_headers)
        assert rd.status_code == 400, f"红字票应禁删，实际 {rd.status_code}"
        assert "红字发票不可删除" in rd.text

        # 已红冲蓝字原票禁删
        rd2 = self._api(client, "DELETE", f"/api/sales/invoices/{inv_id}", headers=auth_headers)
        assert rd2.status_code == 400, f"已红冲蓝字票应禁删，实际 {rd2.status_code}"
        assert "已红冲" in rd2.text

        # 列表带红字字段
        lst = self._api(client, "GET", "/api/sales/invoices?page_size=50", headers=auth_headers)
        assert lst.status_code == 200
        items = lst.json()["items"]
        red_item = next((i for i in items if i["id"] == red_inv_id), None)
        assert red_item, "列表未找到红字票"
        assert red_item["is_red"] == 1, f"is_red 应为1，实际 {red_item['is_red']}"
        assert red_item["red_of_invoice_id"] == inv_id, "红字票应关联原票"

        # 红字应收存在（负数）
        ar_list = self._api(client, "GET", "/api/sales/ar?page_size=50", headers=auth_headers)
        assert ar_list.status_code == 200
        ars = ar_list.json()["items"]
        red_ar = next((a for a in ars if a["ar_no"] == red_ar_no), None)
        assert red_ar, "红字应收未找到"
        assert red_ar["is_red"] == 1, f"红字应收 is_red 应为1, 实际 {red_ar['is_red']}"
        assert red_ar["balance"] < 0, f"红字应收 balance 应为负，实际 {red_ar['balance']}"

    def test_red_duplicate_guard(self, client, auth_headers, foundation):
        """重复红冲/红冲红字 → 400"""
        so_id, total = self._create_order(client, auth_headers, foundation)
        amt = round(total / 1.13, 2)
        tax = round(total * 0.13 / 1.13, 2)
        r = self._invoice(client, auth_headers, so_id, "INV-RED-002", amt, tax, total)
        inv_id = r.json()["id"]
        # 第一次红冲成功
        self._invoice(client, auth_headers, so_id, "INV-RED-R2", -amt, -tax, -total,
                      {"red_of_invoice_id": inv_id})
        # 第二次红冲 → 400（原票已红冲）
        r2 = self._invoice(client, auth_headers, so_id, "INV-RED-R3", -amt, -tax, -total,
                           {"red_of_invoice_id": inv_id})
        assert r2.status_code == 400, f"重复红冲应拒绝，实际 {r2.status_code}"
        assert "已红冲" in r2.text


class TestReviewLock:
    """收款/付款单审核锁定（移植 AO 08f86b2：reviewed 字段 + review/unreview 端点）"""

    def test_collection_review_lock(self, client, auth_headers, foundation):
        """收款单审核后禁改禁删；取消审核后解锁"""
        h = auth_headers
        so_id, total = TestSalesInvoiceRed()._create_order(client, h, foundation, qty=10, price=100)
        amt = round(total / 1.13, 2)
        tax = round(total - amt, 2)
        r = TestSalesInvoiceRed._api(client, "POST", "/api/sales/invoices", {
            "invoice_no": f"INV-RVW-{so_id}", "order_id": so_id, "invoice_date": "2026-08-28",
            "amount": amt, "amount_fc": amt, "tax_amount": tax, "total_amount": total, "tax_rate": 13,
        }, h)
        assert r.status_code == 200, r.text
        r = TestSalesInvoiceRed._api(client, "POST", "/api/sales/collections", {
            "customer_id": foundation["cust"][0], "amount": total, "amount_fc": total,
        }, h)
        assert r.status_code == 200, r.text
        coll_id = r.json()["id"]

        # 审核 → 改/删锁定
        r = TestSalesInvoiceRed._api(client, "POST", f"/api/sales/collections/{coll_id}/review", {}, h)
        assert r.status_code == 200, r.text
        r = TestSalesInvoiceRed._api(client, "PUT", f"/api/sales/collections/{coll_id}", {"remark": "x"}, h)
        assert r.status_code == 400, f"已审核收款单应禁改，实际 {r.status_code}"
        r = TestSalesInvoiceRed._api(client, "DELETE", f"/api/sales/collections/{coll_id}", None, h)
        assert r.status_code == 400, f"已审核收款单应禁删，实际 {r.status_code}"

        # 取消审核 → 解锁可删
        r = TestSalesInvoiceRed._api(client, "POST", f"/api/sales/collections/{coll_id}/unreview", {}, h)
        assert r.status_code == 200, r.text
        r = TestSalesInvoiceRed._api(client, "DELETE", f"/api/sales/collections/{coll_id}", None, h)
        assert r.status_code == 200, f"取消审核后应可删除，实际 {r.status_code}: {r.text[:150]}"

    def test_payment_review_lock(self, client, auth_headers, foundation):
        """付款单审核后禁改禁删；取消审核后解锁"""
        h = auth_headers
        sup = foundation["sup"]
        mat = foundation["mats"]["精梳棉纱32S"]
        r = TestSalesInvoiceRed._api(client, "POST", "/api/purchase/orders", {
            "supplier_id": sup, "currency_id": foundation["cny"]["id"],
            "items": [{"material_id": mat, "quantity": 10, "unit_price": 32, "tax_rate": 13}],
        }, h)
        assert r.status_code == 200, r.text
        po_id = r.json()["id"]
        TestSalesInvoiceRed._api(client, "POST", f"/api/purchase/orders/{po_id}/approve", {}, h)
        total = round(10 * 32, 2)
        amt = round(total / 1.13, 2)
        tax = round(total - amt, 2)
        r = TestSalesInvoiceRed._api(client, "POST", "/api/purchase/invoices", {
            "invoice_no": f"INV-PRVW-{po_id}", "order_id": po_id, "supplier_id": sup,
            "invoice_date": "2026-08-28",
            "amount": amt, "amount_fc": amt, "tax_amount": tax, "tax_rate": 13,
        }, h)
        assert r.status_code == 200, r.text
        ap_list = TestSalesInvoiceRed._api(client, "GET", "/api/purchase/ap", None, h).json()["items"]
        ap = next(a for a in ap_list if a["source_id"] == r.json()["id"])
        r = TestSalesInvoiceRed._api(client, "POST", "/api/purchase/payments", {
            "supplier_id": sup, "amount": total, "amount_fc": total, "ap_account_ids": ap["id"],
        }, h)
        assert r.status_code == 200, r.text
        pay_id = r.json()["id"]

        # 审核 → 改/删锁定
        r = TestSalesInvoiceRed._api(client, "POST", f"/api/purchase/payments/{pay_id}/review", {}, h)
        assert r.status_code == 200, r.text
        r = TestSalesInvoiceRed._api(client, "PUT", f"/api/purchase/payments/{pay_id}", {"remark": "x"}, h)
        assert r.status_code == 400, f"已审核付款单应禁改，实际 {r.status_code}"
        r = TestSalesInvoiceRed._api(client, "DELETE", f"/api/purchase/payments/{pay_id}", None, h)
        assert r.status_code == 400, f"已审核付款单应禁删，实际 {r.status_code}"

        # 取消审核 → 解锁可删
        r = TestSalesInvoiceRed._api(client, "POST", f"/api/purchase/payments/{pay_id}/unreview", {}, h)
        assert r.status_code == 200, r.text
        r = TestSalesInvoiceRed._api(client, "DELETE", f"/api/purchase/payments/{pay_id}", None, h)
        assert r.status_code == 200, f"取消审核后应可删除，实际 {r.status_code}: {r.text[:150]}"


class TestSalesRefund:
    """退款（负数收款核销红字应收）"""

    @staticmethod
    def _api(client, method, path, json_data=None, headers=None):
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            resp = client.post(path, json=json_data or {}, headers=headers)
        elif method == "DELETE":
            resp = client.delete(path, headers=headers)
        else:
            raise ValueError(f"未知 method: {method}")
        if resp.status_code >= 400:
            print(f"   ❌ {method} {path} → {resp.status_code}: {resp.text[:250]}")
        return resp

    def _create_red_ar(self, client, h, f):
        """建订单→开票→红冲，返回红字应收 id & 可退额（abs(balance)）"""
        cust = f["cust"][0]
        cny = f["cny"]
        pid = f["prods"]["全棉色织布"]["id"]
        so = self._api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 100, "unit_price": 15.0, "tax_rate": 13}],
        }, h).json()
        self._api(client, "POST", f"/api/sales/orders/{so['id']}/approve", {}, h)
        total = 1500.0
        amt = round(total / 1.13, 2)
        tax = round(total * 0.13 / 1.13, 2)
        inv = self._api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RF-001", "order_id": so["id"], "invoice_date": "2026-08-28",
            "amount": amt, "amount_fc": amt, "tax_amount": tax, "total_amount": total, "tax_rate": 13,
        }, h).json()
        red = self._api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-RF-R1", "order_id": so["id"], "invoice_date": "2026-08-28",
            "amount": -amt, "amount_fc": -amt, "tax_amount": -tax, "total_amount": -total,
            "tax_rate": 13, "red_of_invoice_id": inv["id"],
        }, h).json()
        red_ar_no = red["ar_no"]
        ar_list = self._api(client, "GET", "/api/sales/ar?page_size=50", headers=h).json()["items"]
        red_ar = next(a for a in ar_list if a["ar_no"] == red_ar_no)
        return red_ar["id"], abs(red_ar["balance"])

    def test_refund_to_red_ar(self, client, auth_headers, foundation):
        """退款（负数收款）核销红字应收：balance 向 0 靠拢，退超拦截"""
        red_ar_id, red_amount = self._create_red_ar(client, auth_headers, foundation)
        cust = foundation["cust"][0]
        # 部分退款
        refund = self._api(client, "POST", "/api/sales/collections", {
            "customer_id": cust, "amount": -round(red_amount / 2, 2),
            "amount_fc": -round(red_amount / 2, 2), "ar_account_id": red_ar_id,
            "collection_date": "2026-08-28",
        }, auth_headers)
        assert refund.status_code == 200, f"退款失败: {refund.text}"
        assert "退款登记成功" in refund.json()["message"]

        # 退超 → 400
        over = self._api(client, "POST", "/api/sales/collections", {
            "customer_id": cust, "amount": -red_amount * 10, "amount_fc": -red_amount * 10,
            "ar_account_id": red_ar_id, "collection_date": "2026-08-28",
        }, auth_headers)
        assert over.status_code == 400, f"退超应拒绝，实际 {over.status_code}"
        assert "超过可退余额" in over.text


class TestArTransfer:
    """核销转移（红字→正余额，同客户，上限校验）"""

    @staticmethod
    def _api(client, method, path, json_data=None, headers=None):
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            resp = client.post(path, json=json_data or {}, headers=headers)
        else:
            raise ValueError(f"未知 method: {method}")
        if resp.status_code >= 400:
            print(f"   ❌ {method} {path} → {resp.status_code}: {resp.text[:250]}")
        return resp

    def _create_pair(self, client, h, f):
        """建两笔同客户应收：一笔红字（负），一笔正余额，返回 (source_ar_id, target_ar_id)"""
        cust = f["cust"][0]
        cny = f["cny"]
        pid = f["prods"]["全棉色织布"]["id"]

        # 正余额应收（蓝字开票，全额 1500）
        so1 = self._api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 100, "unit_price": 15.0, "tax_rate": 13}],
        }, h).json()
        self._api(client, "POST", f"/api/sales/orders/{so1['id']}/approve", {}, h)
        inv1 = self._api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-TR-001", "order_id": so1["id"], "invoice_date": "2026-08-28",
            "amount": round(1500 / 1.13, 2), "amount_fc": round(1500 / 1.13, 2),
            "tax_amount": round(1500 * 0.13 / 1.13, 2), "total_amount": 1500.0, "tax_rate": 13,
        }, h).json()
        ar1_no = inv1["ar_no"]

        # 红字应收（另一订单开票后红冲，负 1500）
        so2 = self._api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": pid, "quantity": 100, "unit_price": 15.0, "tax_rate": 13}],
        }, h).json()
        self._api(client, "POST", f"/api/sales/orders/{so2['id']}/approve", {}, h)
        inv2 = self._api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-TR-002", "order_id": so2["id"], "invoice_date": "2026-08-28",
            "amount": round(1500 / 1.13, 2), "amount_fc": round(1500 / 1.13, 2),
            "tax_amount": round(1500 * 0.13 / 1.13, 2), "total_amount": 1500.0, "tax_rate": 13,
        }, h).json()
        red = self._api(client, "POST", "/api/sales/invoices", {
            "invoice_no": "INV-TR-R1", "order_id": so2["id"], "invoice_date": "2026-08-28",
            "amount": -round(1500 / 1.13, 2), "amount_fc": -round(1500 / 1.13, 2),
            "tax_amount": -round(1500 * 0.13 / 1.13, 2), "total_amount": -1500.0,
            "tax_rate": 13, "red_of_invoice_id": inv2["id"],
        }, h).json()
        red_ar_no = red["ar_no"]

        ars = self._api(client, "GET", "/api/sales/ar?page_size=100", headers=h).json()["items"]
        target = next(a for a in ars if a["ar_no"] == ar1_no)
        source = next(a for a in ars if a["ar_no"] == red_ar_no)
        return source["id"], target["id"]

    def test_transfer(self, client, auth_headers, foundation):
        """核销转移：红字→正余额、上限校验、审计留痕"""
        src_id, tgt_id = self._create_pair(client, auth_headers, foundation)
        # 正常转移 800
        r = self._api(client, "POST", "/api/sales/ar/transfer", {
            "source_ar_id": src_id, "target_ar_id": tgt_id, "amount": 800, "remark": "清理",
        }, auth_headers)
        assert r.status_code == 200, f"核销转移失败: {r.text}"
        assert "核销转移成功" in r.json()["message"]

        # 超上限 → 400
        over = self._api(client, "POST", "/api/sales/ar/transfer", {
            "source_ar_id": src_id, "target_ar_id": tgt_id, "amount": 99999,
        }, auth_headers)
        assert over.status_code == 400, f"超上限应拒绝，实际 {over.status_code}"
        assert "超过可转移上限" in over.text
