"""报关单明细化专项测试（移植 AO c08dee7，适配 main v2.8.0）：

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
    def _make_multi_order(client, h, f):
        """创建 2 明细订单（全棉色织布 + 纯棉坯布），返回订单 id"""
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
        so_id = self._make_multi_order(client, h, foundation)
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
        # 每个商品行的 HS = 对应产品档案 HS
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
        so_id = self._make_multi_order(client, h, foundation)
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
        so2 = self._make_multi_order(client, h, foundation)
        r3 = _api(client, "POST", "/api/sales/customs", {**body, "order_id": so2}, h)
        assert r3.status_code == 400 and "已存在" in r3.text, r3.text

    def test_customs_item_validate(self, client, auth_headers, foundation):
        """商品行校验：数量必须 > 0"""
        h = dict(auth_headers)
        so_id = self._make_multi_order(client, h, foundation)
        cny = foundation["cny"]
        pid = foundation["prods"]["全棉色织布"]["id"]

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
        so_id = self._make_multi_order(client, h, foundation)
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

    def test_declaration_row_from_customs_item(self, client, auth_headers, foundation):
        """双端匹配：申报行从报关单商品行添加（customs_item_id），出口FOB自动重算"""
        h = dict(auth_headers)
        so_id = self._make_multi_order(client, h, foundation)
        cny = foundation["cny"]
        # 已结关报关单
        cid = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-REF-001", "order_id": so_id,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试", "status": "已结关",
        }, h).json()["id"]
        item_rows = _api(client, "GET", f"/api/sales/customs/{cid}", None, h).json()["items"]
        assert len(item_rows) == 2

        # 建申报表（待申报）
        decl = _api(client, "POST", "/api/tax-refund/declarations", {
            "period": "202608", "batch": 1, "declare_date": "2026-08-03",
            "declaration_no": "TS-202608-01",
        }, h)
        assert decl.status_code == 200, decl.text
        decl_id = decl.json()["id"]

        # 从报关单商品行添加申报行（第一个商品行）
        ci = item_rows[0]
        r = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "customs_item_id": ci["id"],
            "refund_rate": ci["refund_rate"] or 13,
        }, h)
        assert r.status_code == 200, r.text

        # 重复添加同一商品行 → 400
        r2 = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "customs_item_id": ci["id"], "refund_rate": 13,
        }, h)
        assert r2.status_code == 400 and "不能重复选择" in r2.text, r2.text

        # 出口FOB = 商品行金额；申报行带出商品/HS信息
        d = _api(client, "GET", f"/api/tax-refund/declarations/{decl_id}", None, h).json()
        assert abs(d["export_amount_fob"] - ci["declare_amount"]) < 0.01, \
            f"出口FOB应={ci['declare_amount']}，实际 {d['export_amount_fob']}"
        rows = d["rows"]
        assert rows and rows[0]["customs_item_id"] == ci["id"], "申报行未关联报关单商品行"
        assert rows[0]["product_name"] and rows[0]["customs_no"] == "CST-REF-001", \
            f"申报行缺少出口端信息: {rows[0]}"

        # 未放行/未结关报关单商品行不可申报（新报关单默认已报关；用新订单避开同订单唯一）
        so2 = self._make_multi_order(client, h, foundation)
        cid2 = _api(client, "POST", "/api/sales/customs", {
            "customs_no": "CST-REF-002", "order_id": so2,
            "declare_currency": cny["id"], "declare_date": "2026-08-03",
            "customs_broker": "测试", "status": "已报关",
        }, h).json()["id"]
        ci2 = _api(client, "GET", f"/api/sales/customs/{cid2}", None, h).json()["items"][0]
        r3 = _api(client, "POST", f"/api/tax-refund/declarations/{decl_id}/rows", {
            "customs_item_id": ci2["id"], "refund_rate": 13,
        }, h)
        assert r3.status_code == 400 and "未放行/未结关" in r3.text, r3.text
