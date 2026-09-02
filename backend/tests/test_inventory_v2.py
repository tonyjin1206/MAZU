"""
库存收发存 v2 专项测试
======================
覆盖：采购红冲 / 销售退货 / 盘点闭环

- 采购红冲：批次消耗后红冲剩余、订单状态回退
- 成品采购明细：直接采购入库被拒，必须走「转成品库入库」→ 待入库单收货
- 销售退货：退回原批次原成本、订单状态回退
- 盘点：建单→录实盘→提交→盘盈盘亏入账、盘亏超账面拒绝

注（2026-09 生产管理下线）：发料拆类型 / 取消完工入库保护用例随生产端点删除而移除。
"""

import time


class TestInventoryV2:
    """收发存 v2 — 盘点/红冲/退货/拆类型"""

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
            print(f"   ❌ {method} {path} → {resp.status_code}: {resp.text[:300]}")
            return None
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    def _setup_base(self, client, h, tag):
        """最小基础数据：币种/2仓库/1材料/2工序/2供应商/1客户/1产品+工艺路线
        注意：code 用 6位补零数字（000001~000006），字符序最小 —
        不触发 _next_code 数字解析，也不会让 max() 锁定导致自动编码重复"""
        api = self._api
        n = f"{990000 + int(tag[1:]):06d}"  # A1→990001 ... A6→990006（大数字段，避开自动编码 000001 起）
        cny = api(client, "POST", "/api/foundation/currencies",
                  {"code": f"CN{n}", "name": "人民币", "symbol": "¥", "is_base": 1}, h)
        wh_rm = api(client, "POST", "/api/foundation/warehouses",
                    {"code": f"RM{n}", "name": "原料仓", "wh_type": "原料仓",
                     "address": "浙江省绍兴市柯桥区轻纺城大道88号", "manager": "王建国"}, h)["id"]
        wh_fg = api(client, "POST", "/api/foundation/warehouses",
                    {"code": f"FG{n}", "name": "成品仓", "wh_type": "成品仓",
                     "address": "浙江省绍兴市柯桥区滨海工业区1号", "manager": "刘芳"}, h)["id"]
        mat = api(client, "POST", "/api/foundation/materials",
                  {"name": f"棉纱{tag}", "code": f"MAT{n}", "spec": "32S", "unit": "吨",
                   "category": "原材料", "purchase_price": 32.0}, h)["id"]
        p_self = api(client, "POST", "/api/foundation/processes",
                     {"code": f"PZ{n}", "name": "织造", "unit_price": 0.5}, h)["id"]
        p_os = api(client, "POST", "/api/foundation/processes",
                   {"code": f"PO{n}", "name": "染色", "unit_price": 1.2}, h)["id"]
        sup = api(client, "POST", "/api/foundation/suppliers",
                  {"name": f"供应商{tag}", "code": f"SU{n}", "supplier_type": "供应商",
                   "contact_person": "张三", "phone": "13800000000", "tax_id": f"911{n}",
                   "address": "浙江省杭州市"}, h)["id"]
        sup_os = api(client, "POST", "/api/foundation/suppliers",
                     {"name": f"委外商{tag}", "code": f"OS{n}", "supplier_type": "委外",
                      "contact_person": "李四", "phone": "13900000000", "tax_id": f"922{n}",
                      "address": "江苏省无锡市"}, h)["id"]
        cust = api(client, "POST", "/api/foundation/customers",
                   {"name_cn": f"客户{tag}", "code": f"CU{n}",
                    "contact_person": "王五", "phone": "13700000000", "tax_id": f"933{n}",
                    "address": "上海市浦东新区", "country": "中国"}, h)["id"]
        prod = api(client, "POST", "/api/foundation/products",
                   {"name_cn": f"坯布{tag}", "code": f"PR{n}", "spec": "63\"",
                    "unit": "米", "estimated_cost": 9.0}, h)["id"]
        api(client, "PUT", f"/api/foundation/products/{prod}/processes", [
            {"process_id": p_self, "seq": 1, "default_unit_price": 0.5},
            {"process_id": p_os, "seq": 2, "default_unit_price": 1.2,
             "default_outsourcer_id": sup_os},
        ], h)
        # BOM：1米坯布耗 0.4 材料（单位用量）
        api(client, "POST", "/api/foundation/bom",
            {"product_id": prod, "material_id": mat, "quantity": 0.4,
             "bom_name": f"BOM{tag}"}, h)
        return {
            "cny": cny, "wh_rm": wh_rm, "wh_fg": wh_fg,
            "mat": mat, "mat_name": f"棉纱{tag}",
            "p_self": p_self, "p_os": p_os,
            "sup": sup, "sup_os": sup_os, "cust": cust, "prod": prod,
        }

    def _mat_balance(self, client, h, base, page_size=10):
        """查本测试材料的当前库存（按材料名定位，避免其他测试数据污染）"""
        api = self._api
        return api(client, "GET",
                   f"/api/inventory/balance?type=material&keyword={base['mat_name']}&page_size={page_size}",
                   None, h)

    def _po_receipt_material(self, client, h, base, qty=100, price=32.0):
        """采购订单→审核→入库材料，返回 (po_id, receipt_id, batch_no)"""
        api = self._api
        po = api(client, "POST", "/api/purchase/orders", {
            "supplier_id": base["sup"], "currency_id": base["cny"]["id"], "tax_rate": 13,
            "items": [{"material_id": base["mat"], "quantity": qty, "unit_price": price}],
        }, h)
        api(client, "POST", f"/api/purchase/orders/{po['id']}/approve", {}, h)
        detail = api(client, "GET", f"/api/purchase/orders/{po['id']}", None, h)
        oi = detail["items"][0]
        rcp = api(client, "POST", "/api/purchase/receipts", {
            "order_id": po["id"], "warehouse_id": base["wh_rm"],
            "items": [{"order_item_id": oi["id"], "material_id": oi["material_id"],
                       "quantity": qty, "unit_price": price}],
        }, h)
        return po["id"], rcp["id"], oi["batch_no"] if oi.get("batch_no") else None

    def _create_product_po(self, client, h, base, qty=60, price=12.0):
        """手填成品采购订单 → 审核，返回 (po_id, order_item_id)"""
        api = self._api
        po = api(client, "POST", "/api/purchase/orders", {
            "supplier_id": base["sup"], "currency_id": base["cny"]["id"], "tax_rate": 13,
            "items": [{"product_id": base["prod"], "quantity": qty, "unit_price": price}],
        }, h)
        assert po, "成品采购订单创建失败"
        po_id = po["id"]
        api(client, "POST", f"/api/purchase/orders/{po_id}/approve", {}, h)
        detail = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        return po_id, detail["items"][0]["id"]

    def _to_stock_in_and_receive(self, client, h, base, po_id, oi_id, qty, price=12.0):
        """采购成品明细 → 转成品库入库 → 待入库单收货，返回待入库单 id"""
        api = self._api
        api(client, "POST", f"/api/purchase/orders/{po_id}/items/{oi_id}/to-stock-in",
            {"stock_in_order_id": 0}, h)
        sl = api(client, "GET", "/api/stock-in?source_type=purchase&page_size=10", None, h)
        sin = next((s for s in sl["items"] if s["purchase_item_id"] == oi_id), None)
        assert sin, "采购明细转成品库入库后应生成待入库单"
        rcv = api(client, "POST", f"/api/stock-in/{sin['id']}/receive",
                  {"quantity": qty, "warehouse_id": base["wh_fg"]}, h)
        assert rcv and rcv.get("status") == "已入库", f"成品收货应完成，实际 {rcv}"
        return sin["id"]

    # ==================== 3. 采购红冲 ====================

    def test_purchase_red(self, client, auth_headers):
        api = self._api
        h = auth_headers
        base = self._setup_base(client, h, "A3")

        # 入库 70（留出红冲余量的非整额场景）
        po_id, rcp_id, _ = self._po_receipt_material(client, h, base, qty=70, price=32.0)

        # 批次 70，显式请求红冲 100 → 应被拒
        bal = self._mat_balance(client, h, base)
        batch_no = bal["items"][0]["batch_no"]
        rcp_detail0 = api(client, "GET", f"/api/purchase/receipts/{rcp_id}", None, h)
        ri0 = rcp_detail0["items"][0]["id"]
        resp = client.post(f"/api/purchase/receipts/{rcp_id}/red",
                           json={"items": [{"receipt_item_id": ri0, "quantity": 100}]}, headers=h)
        assert resp.status_code == 400, f"剩余不足时全冲应被拒，实际 {resp.status_code}"

        # 红冲 60 → 批次剩 10，订单 received_qty=40
        rcp_detail = api(client, "GET", f"/api/purchase/receipts/{rcp_id}", None, h)
        ri_id = rcp_detail["items"][0]["id"]
        red = api(client, "POST", f"/api/purchase/receipts/{rcp_id}/red",
                  {"items": [{"receipt_item_id": ri_id, "quantity": 60}]}, h)
        assert red, "部分红冲失败"
        red_id = red["id"]

        bal2 = self._mat_balance(client, h, base)
        row = next(r for r in bal2["items"] if r["batch_no"] == batch_no)
        assert row["quantity"] == 10, f"红冲60后批次应剩 10，实际 {row['quantity']}"

        # 红冲单存在且为负向
        rlist = api(client, "GET", "/api/purchase/receipts?page_size=50", None, h)
        red_row = next(r for r in rlist["items"] if r["id"] == red_id)
        assert red_row["is_red"] == 1 and red_row["red_of_no"], "红冲单应标记 is_red 并指向原单"

        # 订单状态回退 → 部分入库
        po_detail = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        assert po_detail["status"] == "部分入库", f"订单状态应为部分入库，实际 {po_detail['status']}"
        assert po_detail["items"][0]["received_qty"] == 10

        # 再冲剩余 10 → 批次清空，订单 received 30
        api(client, "POST", f"/api/purchase/receipts/{rcp_id}/red", {}, h)
        bal3 = self._mat_balance(client, h, base)
        assert all(r["batch_no"] != batch_no for r in bal3["items"]), "批次清空后不应出现在快照"

        # 继续红冲 → 400（批次已无剩余）
        resp = client.post(f"/api/purchase/receipts/{rcp_id}/red", json={}, headers=h)
        assert resp.status_code == 400, "批次已清空再冲应被拒"

    def test_purchase_red_mo_rollback(self, client, auth_headers):
        """成品采购明细：采购入库（转成品库入库）→ 库存/订单联动

        手填成品采购订单（生产/采购需求已随生产管理下线，改为直建成品 PO）→ 审核 →
        采购明细「转成品库入库」→ 成品入库模块收货。直接 POST /purchase/receipts
        对成品类采购明细已由后端拒绝（提示走转成品库入库）。
        """
        api = self._api
        h = auth_headers
        base = self._setup_base(client, h, "A4")

        # 手填成品采购订单 → 审核
        po_id, oi_id = self._create_product_po(client, h, base, qty=60, price=12.0)

        # 成品采购明细不能直接走采购入库（后端拒绝），必须「转成品库入库」
        resp = client.post("/api/purchase/receipts", json={
            "order_id": po_id, "warehouse_id": base["wh_fg"],
            "items": [{"order_item_id": oi_id, "product_id": base["prod"],
                       "quantity": 60, "unit_price": 12.0}],
        }, headers=h)
        assert resp.status_code == 400, "成品采购明细直接采购入库应被拒（走转成品库入库）"

        # 转成品库入库 → 待入库单 → 收货
        sin_id = self._to_stock_in_and_receive(client, h, base, po_id, oi_id, qty=60, price=12.0)

        # 订单明细已入数量回写
        detail2 = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        assert detail2["items"][0]["received_qty"] == 60, "采购明细 received_qty 应为 60"

        # 成品批次入库 → 台账可查
        bal = api(client, "GET", "/api/inventory/balance?type=product&page_size=10", None, h)
        assert bal["items"], "成品入库后应存在产品库存"

        # 收货退回（数量纠正）→ 批次扣减、订单明细回退
        ret = api(client, "POST", f"/api/stock-in/{sin_id}/return",
                  {"return_qty": 10}, h)
        assert ret, "收货退回失败"
        detail3 = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        assert detail3["items"][0]["received_qty"] == 50, "退回10后 received_qty 应为 50"

    # ==================== 4. 销售退货 ====================

    def test_sale_return(self, client, auth_headers):
        api = self._api
        h = auth_headers
        base = self._setup_base(client, h, "A5")

        # 销售订单 → 审核 → 转直采（挂上销售单，后续才能发货）
        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": base["cust"], "currency_id": base["cny"]["id"],
            "payment_terms": "TT",
            "items": [{"product_id": base["prod"], "quantity": 50, "unit_price": 15.0, "tax_rate": 13}],
        }, h)
        so_id = so["id"]
        api(client, "POST", f"/api/sales/orders/{so_id}/approve", {}, h)
        so_detail = api(client, "GET", f"/api/sales/orders/{so_id}", None, h)
        oi_id = so_detail["items"][0]["id"]
        api(client, "POST", f"/api/sales/orders/{so_id}/items/{oi_id}/stock-in", {}, h)

        # 成品采购（转直采链路）→ 转成品库入库 50 @12（采购价即入库成本）
        po_id, poi_id = self._create_product_po(client, h, base, qty=50, price=12.0)
        self._to_stock_in_and_receive(client, h, base, po_id, poi_id, qty=50)
        bal2 = api(client, "GET", "/api/inventory/balance?type=product&page_size=10", None, h)
        row = next(r for r in bal2["items"] if r["product_id"] == base["prod"])
        fg_batch = row["batch_no"]
        assert row["unit_cost"] == 12.0, f"成品入库成本应为采购价 12.0，实际 {row['unit_cost']}"

        # 发货 40 → 退货 15 → 批次 25 → 订单 部分发货
        # 两段式发货：通知发货 → 库管出库
        dlv_notify = api(client, "POST", "/api/sales/deliveries/notify", {
            "order_id": so_id, "order_item_id": oi_id,
            "quantity": 40,
        }, h)
        assert dlv_notify, "发货通知失败"
        dlv_id = dlv_notify["id"]
        dlv = api(client, "POST", f"/api/sales/deliveries/{dlv_id}/issue", {
            "batch_no": fg_batch, "quantity": 40, "warehouse_id": base["wh_fg"],
        }, h)
        assert dlv, "销售发货失败"
        ret = api(client, "POST", f"/api/sales/deliveries/{dlv['id']}/return",
                  {"quantity": 15}, h)
        assert ret, "部分退货失败"

        bal3 = api(client, "GET", "/api/inventory/balance?type=product&page_size=10", None, h)
        row3 = next(r for r in bal3["items"] if r["batch_no"] == fg_batch)
        assert row3["quantity"] == 25, f"退货15后批次应为 25，实际 {row3['quantity']}"

        # 退货单为负向
        dlist = api(client, "GET", "/api/sales/deliveries?page_size=50", None, h)
        ret_row = next(d for d in dlist["items"] if d["delivery_no"] == ret["return_no"])
        assert ret_row["is_return"] == 1 and ret_row["quantity"] == -15

        # 订单状态 → 部分发货（40-15=25 已发）
        so2 = api(client, "GET", f"/api/sales/orders/{so_id}", None, h)
        assert so2["status"] == "部分发货", f"订单应为部分发货，实际 {so2['status']}"
        assert so2["items"][0]["delivered_qty"] == 25

        # 退剩余 25 → 订单 已审（未发）→ 再退 → 400
        api(client, "POST", f"/api/sales/deliveries/{dlv['id']}/return", {"quantity": 25}, h)
        so3 = api(client, "GET", f"/api/sales/orders/{so_id}", None, h)
        assert so3["status"] == "已审", f"全退后订单应为已审，实际 {so3['status']}"
        resp = client.post(f"/api/sales/deliveries/{dlv['id']}/return", json={"quantity": 5}, headers=h)
        assert resp.status_code == 400, "超额退货应被拒"

        # 全部退回 → 批次恢复 50
        bal4 = api(client, "GET", "/api/inventory/balance?type=product&page_size=10", None, h)
        row4 = next(r for r in bal4["items"] if r["batch_no"] == fg_batch)
        assert row4["quantity"] == 50, f"全退后批次应恢复 50，实际 {row4['quantity']}"

    # ==================== 5. 盘点 ====================

    def test_stocktake_flow(self, client, auth_headers):
        api = self._api
        h = auth_headers
        base = self._setup_base(client, h, "A6")

        # 材料入库 100
        self._po_receipt_material(client, h, base, qty=100, price=32.0)
        bal = self._mat_balance(client, h, base)
        batch_no = bal["items"][0]["batch_no"]

        # 建盘点单（自动带出批次）
        st = api(client, "POST", "/api/inventory/stocktakes",
                 {"warehouse_id": base["wh_rm"], "remark": "月度盘点"}, h)
        assert st and st["item_count"] == 1, f"应带出1个批次，实际 {st}"
        st_id = st["id"]

        # 详情：账面 100
        detail = api(client, "GET", f"/api/inventory/stocktakes/{st_id}", None, h)
        item = detail["items"][0]
        assert item["book_qty"] == 100

        # 录实盘 85 → 提交 → 盘亏 15 入账
        api(client, "PUT", f"/api/inventory/stocktakes/{st_id}/items/{item['id']}",
            {"actual_qty": 85}, h)
        sub = api(client, "POST", f"/api/inventory/stocktakes/{st_id}/submit", {}, h)
        assert sub, "盘点提交失败"

        bal2 = self._mat_balance(client, h, base)
        row = next(r for r in bal2["items"] if r["batch_no"] == batch_no)
        assert row["quantity"] == 85, f"盘亏后批次应为 85，实际 {row['quantity']}"

        # 流水：盘亏 15（负）
        txns = api(client, "GET", "/api/inventory/transactions?type=material&page_size=50", None, h)
        stx = [t for t in txns["items"] if t["batch_no"] == batch_no and t["trans_type"] == "stocktake_out"]
        assert stx and stx[0]["quantity"] == -15, f"应有盘亏流水-15，实际 {stx}"

        # 盘盈：新建盘点 → 实盘 90 → 提交 → 批次 90
        st2 = api(client, "POST", "/api/inventory/stocktakes",
                  {"warehouse_id": base["wh_rm"]}, h)
        d2 = api(client, "GET", f"/api/inventory/stocktakes/{st2['id']}", None, h)
        it2 = d2["items"][0]
        api(client, "PUT", f"/api/inventory/stocktakes/{st2['id']}/items/{it2['id']}",
            {"actual_qty": 90}, h)
        api(client, "POST", f"/api/inventory/stocktakes/{st2['id']}/submit", {}, h)
        bal3 = self._mat_balance(client, h, base)
        row3 = next(r for r in bal3["items"] if r["batch_no"] == batch_no)
        assert row3["quantity"] == 90, f"盘盈后批次应为 90，实际 {row3['quantity']}"

        # 盘亏超账面 → 拒绝
        st3 = api(client, "POST", "/api/inventory/stocktakes",
                  {"warehouse_id": base["wh_rm"]}, h)
        d3 = api(client, "GET", f"/api/inventory/stocktakes/{st3['id']}", None, h)
        it3 = d3["items"][0]
        api(client, "PUT", f"/api/inventory/stocktakes/{st3['id']}/items/{it3['id']}",
            {"actual_qty": -5}, h)
        resp = client.post(f"/api/inventory/stocktakes/{st3['id']}/submit", json={}, headers=h)
        assert resp.status_code == 400, "实盘为负应被拒"

        # 已提交盘点单不可修改/删除
        resp = client.put(f"/api/inventory/stocktakes/{st_id}/items/{item['id']}",
                          json={"actual_qty": 80}, headers=h)
        assert resp.status_code == 400, "已提交盘点单不可修改"
        resp = client.delete(f"/api/inventory/stocktakes/{st_id}", headers=h)
        assert resp.status_code == 400, "已提交盘点单不可删除"

        # ===== 新增明细行（账外批次盘盈） =====
        st4 = api(client, "POST", "/api/inventory/stocktakes",
                  {"warehouse_id": base["wh_rm"]}, h)
        st4_id = st4["id"]
        # 新增一个账外批次（台账不存在）：账面自动 0
        add = api(client, "POST", f"/api/inventory/stocktakes/{st4_id}/items", {
            "material_id": base["mat"], "batch_no": "EXTRA-001",
            "actual_qty": 12, "unit_cost": 5.0,
        }, h)
        assert add and add["book_qty"] == 0, f"账外批次账面应为 0，实际 {add}"
        # 重复批次 → 拒绝
        resp = client.post(f"/api/inventory/stocktakes/{st4_id}/items", json={
            "material_id": base["mat"], "batch_no": "EXTRA-001", "actual_qty": 1}, headers=h)
        assert resp.status_code == 400, "同批次重复录入应被拒"
        # 删除该行
        resp = client.delete(f"/api/inventory/stocktakes/{st4_id}/items/{add['id']}", headers=h)
        assert resp.status_code == 200, "草稿行应可删除"
        # 再加回并提交 → 台账创建 + 盘盈入账
        add2 = api(client, "POST", f"/api/inventory/stocktakes/{st4_id}/items", {
            "material_id": base["mat"], "batch_no": "EXTRA-001",
            "actual_qty": 12, "unit_cost": 5.0,
        }, h)
        api(client, "POST", f"/api/inventory/stocktakes/{st4_id}/submit", {}, h)
        bal4 = api(client, "GET",
                   "/api/inventory/balance?type=material&keyword=棉纱&page_size=20", None, h)
        extra = next((r for r in bal4["items"] if r["batch_no"] == "EXTRA-001"), None)
        assert extra and extra["quantity"] == 12, f"账外批次应盘盈入账 12，实际 {extra}"
        assert extra["unit_cost"] == 5.0, f"账外批次成本应为 5，实际 {extra.get('unit_cost')}"
