"""
报关单明细化专项测试（v2.6.0）：一票报关单报多个商品/多个HS编码
=====================================================================
- 多明细订单 → 报关单自动带出商品行（每明细一行，HS 取产品档案）
- 商品行金额汇总 = 表头报关金额
- 重复校验：报关单号唯一 / 同一发货单唯一 / 同订单唯一
- customs-for-refund 按商品行粒度返回
- 删除保护：已申报退税的报关单禁止删除
"""


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
        raise ValueError(method)
    return resp


class TestCustomsItems:
    """报关单商品行（多明细订单 → 一票多商品多 HS）"""

    @staticmethod
    def _make_multi_order(client, h, f, tag):
        """创建 2 明细订单（全棉色织布 + 纯棉坯布），返回订单 id + 明细"""
        api = _api
        cny = f["cny"]
        cust = f["cust"][0]
        prods = f["prods"]
        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [
                {"product_id": prods["全棉色织布"]["id"], "quantity": 50,
                 "unit_price": prods["全棉色织布"]["price"], "tax_rate": 13},
                {"product_id": prods["纯棉坯布"]["id"], "quantity": 100,
                 "unit_price": prods["纯棉坯布"]["price"], "tax_rate": 13},
            ]}, h)
        assert so.status_code == 200, so.text
        return so.json()["id"]

    def test_multi_item_customs_auto_items(self, client, auth_headers, foundation):
        """不传 items → 自动按订单明细带出商品行（每明细一行 + HS 从产品档案带出）"""
        h = dict(auth_headers)
        so_id = self._make_multi_order(client, h, foundation, "C1")
        prods = foundation["prods"]
        total = round(50 * prods["全棉色织布"]["price"] + 100 * prods["纯棉坯布"]["price"], 2)

        r = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-MULTI-001", "order_id": so_id,
            "declare_currency": foundation["cny"]["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试报关行",
        }, h)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        detail = _api(client, "GET", f"/api/sales/customs/{cid}", None, h)
        assert detail.status_code == 200, detail.text
        d = detail.json()
        items = d["items"]
        assert len(items) == 2, f"应带出 2 个商品行，实际 {len(items)}"
        # 每个商品行的 HS = 对应产品档案 HS（从后端产品详情取）
        by_pid = {i["product_id"]: i for i in items}
        for pname, pid in [("全棉色织布", prods["全棉色织布"]["id"]),
                           ("纯棉坯布", prods["纯棉坯布"]["id"])]:
            pd = _api(client, "GET", f"/api/foundation/products/{pid}", None, h).json()
            assert by_pid[pid]["hs_code_id"] == pd["hs_code_id"], \
                f"{pname} HS 未从产品档案带出"
        # 表头金额 = 商品行合计
        assert abs(d["declare_amount"] - total) < 0.01, f"表头金额 {d['declare_amount']} ≠ 合计 {total}"
        # 列表 hs_codes 摘要含两个 HS
        lst = _api(client, "GET", "/api/sales/customs?page_size=10", None, h).json()
        row = next(x for x in lst["items"] if x["id"] == cid)
        assert row["items_count"] == 2
        hs_codes = set(row["hs_codes"].split(","))
        assert len(hs_codes) == 2 and all(hs_codes), f"应展示 2 个 HS 编码: {row['hs_codes']}"

    def test_customs_dup_checks(self, client, auth_headers, foundation):
        """重复校验：单号唯一 / 同订单唯一"""
        h = dict(auth_headers)
        so_id = self._make_multi_order(client, h, foundation, "C2")
        cny = foundation["cny"]
        body = {"customs_no": "CST-DUP-001", "order_id": so_id,
                "declare_currency": cny["id"], "declare_date": "2026-08-03",
                "customs_broker": "测试"}
        r1 = _api(client, "POST", "/api/sales/customs", body, h)
        assert r1.status_code == 200, r1.text

        # 同订单重复报关（不挂发货单）→ 400
        r2 = _api(client, "POST", "/api/sales/customs", {
            **body, "customs_no": "CST-DUP-002"}, h)
        assert r2.status_code == 400 and "已有关联报关单" in r2.text, r2.text

        # 重复报关单号（换订单）→ 400
        so2 = self._make_multi_order(client, h, foundation, "C2b")
        r3 = _api(client, "POST", "/api/sales/customs", {**body, "order_id": so2}, h)
        assert r3.status_code == 400 and "已存在" in r3.text, r3.text

    def test_customs_item_validate(self, client, auth_headers, foundation):
        """商品行校验：数量必须 > 0 / 产品必须属于订单"""
        h = dict(auth_headers)
        so_id = self._make_multi_order(client, h, foundation, "C3")
        cny = foundation["cny"]
        pid = foundation["prods"]["全棉色织布"]["id"]

        # 数量 0 → 400
        r = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-VAL-001", "order_id": so_id,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试",
            "items": [{"product_id": pid, "quantity": 0}],
        }, h)
        assert r.status_code == 400 and "报关数量必须大于 0" in r.text, r.text

    def test_delete_guard_and_customs_for_refund(self, client, auth_headers, foundation):
        """删除保护（已申报禁删）+ customs-for-refund 按商品行返回"""
        h = dict(auth_headers)
        so_id = self._make_multi_order(client, h, foundation, "C4")
        cny = foundation["cny"]
        r = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-GUARD-001", "order_id": so_id,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试", "status": "已结关",
        }, h)
        cid = r.json()["id"]
        # 标已申报 → 删除被拦截
        _api(client, "PUT", f"/api/sales/customs/{cid}",
             {"refund_status": "已申报"}, h)
        rd = _api(client, "DELETE", f"/api/sales/customs/{cid}", None, h)
        assert rd.status_code == 400 and "禁止删除" in rd.text, rd.text
        # 回退待申报 → 可删
        _api(client, "PUT", f"/api/sales/customs/{cid}",
             {"refund_status": "待申报"}, h)
        rd2 = _api(client, "DELETE", f"/api/sales/customs/{cid}", None, h)
        assert rd2.status_code == 200, rd2.text

        # customs-for-refund：已结关报关单商品行可被选（2 商品行）
        cid2 = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-GUARD-002", "order_id": so_id,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试", "status": "已结关"}, h).json()["id"]
        rf = _api(client, "GET", "/api/tax-refund/customs-for-refund?page_size=20", None, h).json()
        rows = [x for x in rf["items"] if x["customs_id"] == cid2]
        assert len(rows) == 2, f"customs-for-refund 应返回 2 个商品行，实际 {len(rows)}"
        assert rows[0]["product_name"] and rows[0]["hs_code"], "商品行缺少商品/HS 信息"


class TestDeclarationDualEnd:
    """退税申报双端匹配：进项发票（采购端）+ 报关单商品行（出口端）"""

    @staticmethod
    def _make_closed_customs(client, h, foundation, tag):
        """建 2 明细订单 + 已结关报关单，返回 (so_id, customs_id)"""
        api = _api
        cny = foundation["cny"]
        cust = foundation["cust"][0]
        prods = foundation["prods"]
        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [
                {"product_id": prods["全棉色织布"]["id"], "quantity": 50,
                 "unit_price": prods["全棉色织布"]["price"], "tax_rate": 13},
                {"product_id": prods["纯棉坯布"]["id"], "quantity": 100,
                 "unit_price": prods["纯棉坯布"]["price"], "tax_rate": 13},
            ]}, h)
        so_id = so.json()["id"]
        c = api(client, "POST", "/api/sales/customs", {
            "customs_no": f"CST-DE-{tag}", "order_id": so_id,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试", "status": "已结关"}, h)
        return so_id, c.json()["id"]

    @staticmethod
    def _make_input_invoice(client, h, foundation, no):
        api = _api
        r = api(client, "POST", "/api/tax-refund/input-invoices", {
            "invoice_no": no,
            "supplier_id": foundation["sup"],
            "invoice_date": "2026-07-20",
            "amount": 1000.0, "tax_amount": 130.0, "total_amount": 1130.0,
        }, h)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_dual_end_row(self, client, auth_headers, foundation):
        """双端行：发票+商品行 → 商品/HS/FOB/退税率带出 + 退税额=FOB×退税率 + 出口额重算"""
        h = dict(auth_headers)
        so_id, cid = self._make_closed_customs(client, h, foundation, "1")
        inv_id = self._make_input_invoice(client, h, foundation, "PI-DE-001")

        decl = _api(client, "POST", "/api/tax-refund/declarations", {
            "declaration_no": "TD-DE-001", "declare_date": "2026-08-03",
            "period": "202608", "batch": 1, "tax_rate": 13, "refund_rate": 13,
            "input_tax": 130.0}, h)
        decl_id = decl.json()["id"]

        # 报关单商品行候选（出口端）
        cf = _api(client, "GET", "/api/tax-refund/customs-for-refund?page_size=20", None, h).json()
        item = next(x for x in cf["items"] if x["customs_id"] == cid)
        fob = item["declare_amount"]
        rate = item["refund_rate"]

        # 添加双端行
        r = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "input_invoice_id": inv_id, "customs_item_id": item["id"]}, h)
        assert r.status_code == 200, r.text

        d = _api(client, "GET", f"/api/tax-refund/declarations/{decl_id}", None, h).json()
        row = d["rows"][0]
        # 出口端带出
        assert row["customs_item_id"] == item["id"]
        assert row["customs_no"] == item["customs_no"], "报关单号未带出"
        assert row["product_name"] == item["product_name"]
        assert abs(row["taxable_amount"] - fob) < 0.01, "计税金额应=报关单商品行FOB"
        assert row["refund_rate"] == rate
        # 退税额 = FOB × 退税率
        expect_refund = round(fob * rate / 100, 2)
        assert abs(row["refundable_amount"] - expect_refund) < 0.01
        # 申报表出口FOB重算 = 行汇总
        assert abs(d["export_amount_fob"] - fob) < 0.01, f"出口FOB应重算为 {fob}"

    def test_dual_end_dup_checks(self, client, auth_headers, foundation):
        """已选过的发票/报关单商品行不可重复选"""
        h = dict(auth_headers)
        so_id, cid = self._make_closed_customs(client, h, foundation, "2")
        inv_id = self._make_input_invoice(client, h, foundation, "PI-DE-002")
        decl = _api(client, "POST", "/api/tax-refund/declarations", {
            "declaration_no": "TD-DE-002", "declare_date": "2026-08-03",
            "period": "202608", "batch": 2, "tax_rate": 13, "refund_rate": 13, "input_tax": 130.0}, h)
        decl_id = decl.json()["id"]
        cf = _api(client, "GET", "/api/tax-refund/customs-for-refund?page_size=20", None, h).json()
        item = next(x for x in cf["items"] if x["customs_id"] == cid)

        r1 = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "input_invoice_id": inv_id, "customs_item_id": item["id"]}, h)
        assert r1.status_code == 200, r1.text

        # 同一商品行重复选 → 400
        inv2 = self._make_input_invoice(client, h, foundation, "PI-DE-002b")
        r2 = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "input_invoice_id": inv2, "customs_item_id": item["id"]}, h)
        assert r2.status_code == 400 and "不能重复选择" in r2.text, r2.text

        # 同一发票重复选（换商品行）→ 400
        item2 = next(x for x in cf["items"] if x["customs_id"] == cid and x["id"] != item["id"])
        r3 = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "input_invoice_id": inv_id, "customs_item_id": item2["id"]}, h)
        assert r3.status_code == 400 and "不能重复选择" in r3.text, r3.text

    def test_customs_status_guard(self, client, auth_headers, foundation):
        """未放行/未结关的报关单商品行不能申报退税"""
        h = dict(auth_headers)
        cny = foundation["cny"]
        prods = foundation["prods"]
        cust = foundation["cust"][0]
        so = _api(client, "POST", "/api/sales/orders", {
            "customer_id": cust, "currency_id": cny["id"], "payment_terms": "TT",
            "items": [{"product_id": prods["全棉色织布"]["id"], "quantity": 10,
                       "unit_price": prods["全棉色织布"]["price"], "tax_rate": 13}]}, h)
        so_id = so.json()["id"]
        # 默认状态=已报关（未放行）
        c = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-DE-GUARD", "order_id": so_id,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试"}, h)
        cid = c.json()["id"]
        inv_id = self._make_input_invoice(client, h, foundation, "PI-DE-003")
        decl = _api(client, "POST", "/api/tax-refund/declarations", {
            "declaration_no": "TD-DE-003", "declare_date": "2026-08-03",
            "period": "202608", "batch": 3, "tax_rate": 13, "refund_rate": 13, "input_tax": 130.0}, h)
        decl_id = decl.json()["id"]
        # 未放行商品行不在候选（customs-for-refund 只列已放行/已结关）
        cf = _api(client, "GET", "/api/tax-refund/customs-for-refund?page_size=20", None, h).json()
        assert not any(x["customs_id"] == cid for x in cf["items"]), "未放行报关单不应出现在候选"
        # 直接调接口也拒绝
        item_id = _api(client, "GET", f"/api/sales/customs/{cid}", None, h).json()["items"][0]["id"]
        r = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "input_invoice_id": inv_id, "customs_item_id": item_id}, h)
        assert r.status_code == 400 and "未放行" in r.text, r.text

    def test_update_declaration_recalc(self, client, auth_headers, foundation):
        """更新表头（进项税额）→ 免抵退重算：实际应退 = min(留抵, 免抵退税额)"""
        h = dict(auth_headers)
        so_id, cid = self._make_closed_customs(client, h, foundation, "4")
        inv_id = self._make_input_invoice(client, h, foundation, "PI-DE-004")
        decl = _api(client, "POST", "/api/tax-refund/declarations", {
            "declaration_no": "TD-DE-004", "declare_date": "2026-08-03",
            "period": "202608", "batch": 4, "tax_rate": 13, "refund_rate": 13, "input_tax": 130.0}, h)
        decl_id = decl.json()["id"]
        cf = _api(client, "GET", "/api/tax-refund/customs-for-refund?page_size=20", None, h).json()
        item = next(x for x in cf["items"] if x["customs_id"] == cid)
        fob = item["declare_amount"]
        _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "input_invoice_id": inv_id, "customs_item_id": item["id"]}, h)

        d = _api(client, "GET", f"/api/tax-refund/declarations/{decl_id}", None, h).json()
        refundable = round(fob * 13 / 100, 2)          # 免抵退税额（理论上限）
        assert abs(d["refundable_amount"] - refundable) < 0.01
        # 进项税 130 > 免抵退 121.16 → 实际应退 = 免抵退税额（进项充足，出口额封顶）
        assert abs(d["actual_refund"] - refundable) < 0.01, f"实际应退应=免抵退税额 {refundable}"

        # 改小进项税额 → 留抵不足 → 实际应退 = 留抵
        _api(client, "PUT", f"/api/tax-refund/declarations/{decl_id}", {"input_tax": 50.0}, h)
        d2 = _api(client, "GET", f"/api/tax-refund/declarations/{decl_id}", None, h).json()
        assert abs(d2["actual_refund"] - 50.0) < 0.01, f"实际应退应为留抵 50，实际 {d2['actual_refund']}"
        assert abs(d2["exemption_amount"] - (refundable - 50.0)) < 0.01, "免抵税额=免抵退-实退"

        # 已申报后禁止修改
        _api(client, "PUT", f"/api/tax-refund/declarations/{decl_id}/submit", None, h)
        r = _api(client, "PUT", f"/api/tax-refund/declarations/{decl_id}", {"input_tax": 99.0}, h)
        assert r.status_code == 400, r.text
