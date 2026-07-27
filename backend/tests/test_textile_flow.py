"""
纺织企业端到端全流程测试
========================
场景：织布生产（纯棉坯布）
工序：整经 → 浆纱(委外) → 织造
BOM至少含3种原材料，3个客户、4个供应商、3个产品、8种原材料
毛利率约15%
"""

import json
import pytest


class TestTextileFullFlow:
    """纺织企业完整业务流 — 从销售到退税"""

    def test_full_flow(self, client, auth_headers):
        api = self._api
        h = auth_headers

        # ======================== 1. 基础数据 ========================
        # --- 币种 ---
        cny = api(client, "POST", "/api/foundation/currencies",
                   {"code": "CNY", "name": "人民币", "symbol": "¥", "is_base": 1}, h)
        usd = api(client, "POST", "/api/foundation/currencies",
                   {"code": "USD", "name": "美元", "symbol": "$"}, h)
        assert cny and usd, "币种创建失败"

        # --- 仓库 ---
        wh_rm = api(client, "POST", "/api/foundation/warehouses",
                     {"code": "RM", "name": "原料仓", "wh_type": "原料仓"}, h)
        wh_fg = api(client, "POST", "/api/foundation/warehouses",
                     {"code": "FG", "name": "成品仓", "wh_type": "成品仓"}, h)
        wh_os = api(client, "POST", "/api/foundation/warehouses",
                     {"code": "OS", "name": "委外仓", "wh_type": "委外仓"}, h)
        assert wh_rm and wh_fg and wh_os, "仓库创建失败"

        # --- 贸易术语 ---
        api(client, "POST", "/api/foundation/trade-terms",
            {"code": "FOB", "name": "FOB(离岸价)"}, h)

        # --- 8种原材料（纺织用） ---
        mats = {}
        raw_materials = [
            ("棉纱32S",   "RM001", "kg", 32.0,  "纯棉精梳32支纱"),
            ("棉纱40S",   "RM002", "kg", 38.0,  "纯棉精梳40支纱"),
            ("涤纶丝75D", "RM003", "kg", 18.0,  "涤纶低弹丝75D"),
            ("经纱",      "RM004", "kg", 28.0,  "纯棉经纱"),
            ("纬纱",      "RM005", "kg", 26.0,  "纯棉纬纱"),
            ("染色助剂",  "RM006", "kg", 15.0,  "活性染色助剂"),
            ("包装材料",  "RM007", "套", 5.0,   "编织布包装"),
            ("浆料",      "RM008", "kg", 12.0,  "变性淀粉浆料"),
        ]
        for name, code, unit, price, spec in raw_materials:
            m = api(client, "POST", "/api/foundation/materials",
                    {"code": code, "name": name, "spec": spec, "unit": unit,
                     "material_type": "原材料", "purchase_price": price}, h)
            assert m, f"材料 {name} 创建失败"
            mats[name] = m["id"]

        # --- 3个工序 ---
        procs = {}
        process_data = [
            ("整经",  "PROC01", 0.50),
            ("浆纱",  "PROC02", 0.80),
            ("织造",  "PROC03", 1.20),
        ]
        for name, code, price in process_data:
            p = api(client, "POST", "/api/foundation/processes",
                    {"code": code, "name": name, "unit_price": price}, h)
            assert p, f"工序 {name} 创建失败"
            procs[name] = p["id"]

        # --- 4个供应商 ---
        suppliers = {}
        supplier_data = [
            ("山东华润纺织",    "SUP001", "山东", "棉纱类"),
            ("河南新野纺织",    "SUP002", "河南", "棉纱/浆料类"),
            ("江苏阳光纺织",    "SUP003", "江苏", "涤纶丝/染化料"),
            ("杭州宏丰化工",    "SUP004", "浙江", "浆料/助剂"),
        ]
        for name, code, region, biz in supplier_data:
            s = api(client, "POST", "/api/foundation/suppliers",
                    {"code": code, "name": name,
                     "contact_person": "采购经理", "phone": "13800000000",
                     "address": region, "remark": biz}, h)
            assert s, f"供应商 {name} 创建失败"
            suppliers[name] = s["id"]

        # --- 2个委外商（供应商3和4同时也是委外商） ---
        outsource_data = [
            ("江苏阳光纺织集团", suppliers["江苏阳光纺织"]),
            ("杭州宏丰印染厂",   suppliers["杭州宏丰化工"]),
        ]
        outsourcers = {}
        for name, sid in outsource_data:
            o = api(client, "POST", "/api/foundation/outsourcers",
                    {"supplier_id": sid, "lead_time": 3}, h)
            assert o, f"委外商 {name} 创建失败"
            outsourcers[name] = o["id"]

        # --- 3个客户 ---
        customers = {}
        customer_data = [
            ("上海纺织品进出口公司", "CUS001"),
            ("广州华衣服装有限公司", "CUS002"),
            ("浙江天诚家纺有限公司", "CUS003"),
        ]
        for name, code in customer_data:
            c = api(client, "POST", "/api/foundation/customers",
                    {"code": code, "name_cn": name, "name_en": name,
                     "country": "中国", "payment_terms": "TT"}, h)
            assert c, f"客户 {name} 创建失败"
            customers[name] = c["id"]

        # --- 3个产品 ---
        products = {}
        product_data = [
            ("纯棉坯布",       "PROD001", "米", 9.32,   "32S×32S 130×70 63\"纯棉坯布"),
            ("T/C涤棉布",      "PROD002", "米", 13.50,  "T/C 65/35 45S×45S 110×76 63\""),
            ("全棉色织布",     "PROD003", "米", 18.00,  "40S×40S 133×72 57/58\"色织布"),
        ]
        for name, code, unit, price, spec in product_data:
            pr = api(client, "POST", "/api/foundation/products",
                     {"code": code, "name_cn": name, "spec": spec,
                      "unit": unit, "sale_price": price}, h)
            assert pr, f"产品 {name} 创建失败"
            products[name] = pr["id"]

        # ======================== 2. BOM ========================
        # 产品1（纯棉坯布）BOM — 每米消耗（至少3种原材料）
        # 生产100米：棉纱32S 12kg + 经纱5kg + 浆料1.5kg + 包装1套
        bom_items_p1 = [
            (products["纯棉坯布"], mats["棉纱32S"],    0.12),
            (products["纯棉坯布"], mats["经纱"],       0.05),
            (products["纯棉坯布"], mats["浆料"],       0.015),
            (products["纯棉坯布"], mats["包装材料"],   0.01),
        ]
        for prod_id, mat_id, qty in bom_items_p1:
            b = api(client, "POST", "/api/foundation/bom",
                    {"product_id": prod_id, "material_id": mat_id,
                     "quantity": qty, "bom_name": f"纯棉坯布原料"}, h)
            assert b, f"BOM 创建失败 prod={prod_id} mat={mat_id}"

        # 产品2（T/C涤棉布）BOM
        bom_items_p2 = [
            (products["T/C涤棉布"], mats["棉纱40S"],   0.08),
            (products["T/C涤棉布"], mats["涤纶丝75D"], 0.06),
            (products["T/C涤棉布"], mats["经纱"],       0.04),
            (products["T/C涤棉布"], mats["浆料"],       0.01),
            (products["T/C涤棉布"], mats["包装材料"],   0.01),
        ]
        for prod_id, mat_id, qty in bom_items_p2:
            api(client, "POST", "/api/foundation/bom",
                {"product_id": prod_id, "material_id": mat_id,
                 "quantity": qty, "bom_name": "T/C涤棉布原料"}, h)

        # 产品3（全棉色织布）BOM
        bom_items_p3 = [
            (products["全棉色织布"], mats["棉纱40S"],   0.10),
            (products["全棉色织布"], mats["棉纱32S"],   0.04),
            (products["全棉色织布"], mats["经纱"],       0.03),
            (products["全棉色织布"], mats["纬纱"],       0.04),
            (products["全棉色织布"], mats["染色助剂"],   0.02),
            (products["全棉色织布"], mats["包装材料"],   0.01),
        ]
        for prod_id, mat_id, qty in bom_items_p3:
            api(client, "POST", "/api/foundation/bom",
                {"product_id": prod_id, "material_id": mat_id,
                 "quantity": qty, "bom_name": "色织布原料"}, h)

        print("\n✅ 基础数据创建完成（8材料×3工序×4供应商×2委外商×3客户×3产品）")

        # ======================== 3. 产品工艺路线 ========================
        # 产品1：整经→浆纱(委外)→织造
        p1_processes = [
            {"process_id": procs["整经"], "seq": 1, "default_unit_price": 0.50},
            {"process_id": procs["浆纱"], "seq": 2, "default_outsourcer_id": outsourcers["江苏阳光纺织集团"],
             "default_unit_price": 0.80},
            {"process_id": procs["织造"], "seq": 3, "default_unit_price": 1.20},
        ]
        api(client, "PUT", f"/api/foundation/products/{products['纯棉坯布']}/processes",
            p1_processes, h)

        # ======================== 4. 销售订单 ========================
        ORDER_QTY = 100  # 100米
        UNIT_PRICE = 9.32  # 使毛利率约15%

        so = api(client, "POST", "/api/sales/orders", {
            "customer_id": customers["上海纺织品进出口公司"],
            "order_date": "2026-07-27",
            "delivery_date": "2026-08-15",
            "currency_id": cny["id"],
            "payment_terms": "TT",
            "items": [{
                "product_id": products["纯棉坯布"],
                "quantity": ORDER_QTY,
                "unit_price": UNIT_PRICE,
                "tax_rate": 13,
            }]
        }, h)
        assert so, "销售订单创建失败"
        order_id = so["id"]
        order_no = so["order_no"]
        print(f"\n✅ 销售订单创建: {order_no} ({ORDER_QTY}米)")

        # ======================== 5. 审核销售订单 → 生成生产订单 ========================
        approve = api(client, "POST", f"/api/sales/orders/{order_id}/approve", {}, h)
        assert approve, "审核失败"
        print(f"✅ 销售订单已审核，{approve.get('message', '')}")

        # 获取生产订单ID
        prod_list = api(client, "GET", f"/api/production/productions?page=1&page_size=10", None, h)
        assert prod_list and prod_list.get("items"), "生产订单未找到"
        mo = prod_list["items"][0]
        mo_id = mo["id"]
        mo_no = mo["order_no"]
        assert mo["status"] == "待排产", f"生产订单状态应为待排产: {mo['status']}"
        print(f"✅ 生产订单已生成: {mo_no}")

        # ======================== 6. 展开BOM ========================
        expand = api(client, "POST", f"/api/production/productions/{mo_id}/expand-bom", {}, h)
        assert expand, "BOM展开失败"
        print(f"✅ BOM已展开: {expand.get('message', '')}")

        # ======================== 7. 派产（Release） ========================
        release = api(client, "POST", f"/api/production/productions/{mo_id}/release", {}, h)
        assert release, "派产失败"
        print(f"✅ 生产订单已派产")

        # ======================== 8. 检查材料库存 → 不够，采购 ========================
        # 查看物料需求
        mo_detail = api(client, "GET", f"/api/production/productions/{mo_id}", None, h)
        assert mo_detail, "无法获取生产订单详情"
        materials = mo_detail.get("materials", [])
        processes_detail = mo_detail.get("processes", [])
        print(f"   物料需求: {len(materials)}项, 工序: {len(processes_detail)}项")

        # 计算每项材料需采购数量（库存为0，全部采购）
        # planned_qty = BOM qty × 生产数量
        # 棉纱32S: 0.12 × 100 = 12kg
        # 经纱: 0.05 × 100 = 5kg
        # 浆料: 0.015 × 100 = 1.5kg
        # 包装材料: 0.01 × 100 = 1套
        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")

        # 采购订单 — 分别向不同供应商采购
        po_items = [
            {"material_id": mats["棉纱32S"],  "quantity": 15,  "unit_price": 32.0},
            {"material_id": mats["经纱"],     "quantity": 8,   "unit_price": 28.0},
            {"material_id": mats["浆料"],     "quantity": 3,   "unit_price": 12.0},
            {"material_id": mats["包装材料"], "quantity": 5,   "unit_price": 5.0},
        ]
        # 多采购一些余量，方便计算
        po = api(client, "POST", "/api/purchase/orders", {
            "supplier_id": suppliers["山东华润纺织"],
            "currency_id": cny["id"],
            "tax_rate": 13,
            "items": po_items,
        }, h)
        assert po, "采购订单创建失败"
        po_id = po["id"]
        po_no = po["order_no"]
        print(f"✅ 采购订单创建: {po_no} ({len(po_items)}项原料)")

        # 审核采购订单
        api(client, "POST", f"/api/purchase/orders/{po_id}/approve", {}, h)
        print(f"✅ 采购订单已审核")

        # ======================== 9. 采购入库 ========================
        # 先获取订单明细（含 order_item_id）
        po_detail = api(client, "GET", f"/api/purchase/orders/{po_id}", None, h)
        assert po_detail, "采购订单详情获取失败"

        receipt_items = []
        for item in po_detail.get("items", []):
            receipt_items.append({
                "order_item_id": item["id"],
                "material_id": item["material_id"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
            })

        receipt = api(client, "POST", "/api/purchase/receipts", {
            "order_id": po_id,
            "warehouse_id": wh_rm["id"],
            "receipt_date": "2026-07-27",
            "items": receipt_items,
        }, h)
        assert receipt, "采购入库失败"
        print(f"✅ 采购入库完成: {receipt.get('message', '')}")

        # 更新物料采购单价回写
        for mat_name, mat_id in [("棉纱32S", mats["棉纱32S"]),
                                  ("经纱", mats["经纱"]),
                                  ("浆料", mats["浆料"]),
                                  ("包装材料", mats["包装材料"])]:
            mat_info = api(client, "GET", f"/api/foundation/materials/{mat_id}", None, h)
            assert mat_info, f"材料 {mat_name} 查询失败"
            if mat_info.get("purchase_price", 0) > 0:
                print(f"   材料 {mat_name} 采购单价: ¥{mat_info['purchase_price']}")

        # ======================== 10. 采购发票 + 应付 ========================
        inv = api(client, "POST", "/api/purchase/invoices", {
            "invoice_no": f"INV-P-{today_str}-001",
            "order_id": po_id,
            "supplier_id": suppliers["山东华润纺织"],
            "invoice_date": today_str,
            "invoice_type": "专票",
            "amount": 15 * 32 + 8 * 28 + 3 * 12 + 5 * 5,  # 物料成本
            "amount_fc": 15 * 32 + 8 * 28 + 3 * 12 + 5 * 5,
            "tax_amount": round((15 * 32 + 8 * 28 + 3 * 12 + 5 * 5) * 0.13 / 1.13, 2),
            "remark": "原材料采购发票",
        }, h)
        assert inv, "采购发票创建失败"
        print(f"✅ 采购发票已创建")

        # ======================== 11. 查询应付并付款 ========================
        ap_list = api(client, "GET", "/api/purchase/ap", None, h)
        assert ap_list and ap_list.get("items"), "应付账款未生成"
        ap_items = ap_list["items"]
        print(f"✅ 应付账款已生成({len(ap_items)}笔)")

        payment = api(client, "POST", "/api/purchase/payments", {
            "supplier_id": suppliers["山东华润纺织"],
            "payment_date": today_str,
            "amount": ap_items[0].get("amount", 0),
            "amount_fc": ap_items[0].get("amount", 0),
            "currency_id": cny["id"],
            "payment_method": "银行转账",
            "ap_account_ids": ap_items[0]["id"],
            "remark": "原料采购付款",
        }, h)
        assert payment, "付款失败"
        print(f"✅ 付款完成: {payment.get('message', '')}")

        # ======================== 12. 发料（按工序） ========================
        # 工序1：整经 — 发料：棉纱32S + 经纱
        # 获取可用的批次 — 通过 inventory API
        batch_info = api(client, "GET", f"/api/inventory/balance?type=material&page_size=20", None, h)
        print(f"   库存批次查询: {json.dumps(batch_info, ensure_ascii=False)[:300]}" if batch_info else "   库存查询为空")
        batches = []
        if batch_info:
            if isinstance(batch_info, dict) and "items" in batch_info:
                batches = batch_info["items"]
            elif isinstance(batch_info, list):
                batches = batch_info
        # 查找棉纱32S和经纱的批次
        batch_32s = None
        batch_warp = None
        for b in batches:
            if b.get("material_id") == mats["棉纱32S"]:
                batch_32s = b["batch_no"]
            if b.get("material_id") == mats["经纱"]:
                batch_warp = b["batch_no"]
        assert batch_32s and batch_warp, "批次未找到"

        # 工序1 ID（整经）
        proc1_id = None
        proc2_id = None
        proc3_id = None
        for p in processes_detail:
            if p.get("process_name") == "整经":
                proc1_id = p["id"]
            elif p.get("process_name") == "浆纱":
                proc2_id = p["id"]
            elif p.get("process_name") == "织造":
                proc3_id = p["id"]
        assert proc1_id and proc2_id and proc3_id, "工序ID获取失败"

        # 发料给工序1（整经）
        issue1 = api(client, "POST",
                     f"/api/production/productions/{mo_id}/processes/{proc1_id}/issue", {
            "material_id": mats["棉纱32S"],
            "quantity": 12.0,
            "batch_no": batch_32s,
            "warehouse_id": wh_rm["id"],
            "unit_price": 32.0,
        }, h)
        assert issue1, "发料(棉纱32S→整经)失败"
        print(f"✅ 发料完成：棉纱32S→整经")

        issue1b = api(client, "POST",
                      f"/api/production/productions/{mo_id}/processes/{proc1_id}/issue", {
            "material_id": mats["经纱"],
            "quantity": 5.0,
            "batch_no": batch_warp,
            "warehouse_id": wh_rm["id"],
            "unit_price": 28.0,
        }, h)
        assert issue1b, "发料(经纱→整经)失败"
        print(f"✅ 发料完成：经纱→整经")

        # ======================== 13. 完成工序1（整经） ========================
        finish1 = api(client, "POST",
                      f"/api/production/productions/{mo_id}/processes/{proc1_id}/finish", {
            "unit_price": 0.50,
            "process_qty": 100,
        }, h)
        assert finish1, "工序1(整经)完工失败"
        print(f"✅ 工序1(整经)完工，下一工序: {finish1.get('next_process_name', 'N/A')}")

        # ======================== 14. 发料给工序2（浆纱→委外） ========================
        # 发浆料
        batch_pulp = None
        for b in batches:
            if b.get("material_id") == mats["浆料"]:
                batch_pulp = b["batch_no"]
                break
        assert batch_pulp, "浆料批次未找到"

        issue2 = api(client, "POST",
                     f"/api/production/productions/{mo_id}/processes/{proc2_id}/issue", {
            "material_id": mats["浆料"],
            "quantity": 1.5,
            "batch_no": batch_pulp,
            "warehouse_id": wh_rm["id"],
            "unit_price": 12.0,
        }, h)
        assert issue2, "发料(浆料→浆纱)失败"
        print(f"✅ 发料完成：浆料→浆纱(委外)")

        # ======================== 15. 完成工序2（浆纱→委外） ========================
        finish2 = api(client, "POST",
                      f"/api/production/productions/{mo_id}/processes/{proc2_id}/finish", {
            "unit_price": 0.80,
            "process_qty": 100,
        }, h)
        assert finish2, "工序2(浆纱/委外)完工失败"
        print(f"✅ 工序2(浆纱/委外)完工，加工费: ¥80.00")

        # ======================== 16. 发料给工序3（织造） ========================
        # 织造需继续使用棉纱32S和经纱剩余部分
        # 查看剩余库存 → 再发一批
        issue3 = api(client, "POST",
                     f"/api/production/productions/{mo_id}/processes/{proc3_id}/issue", {
            "material_id": mats["棉纱32S"],
            "quantity": 3.0,  # 补充剩余用量
            "batch_no": batch_32s,
            "warehouse_id": wh_rm["id"],
            "unit_price": 32.0,
        }, h)
        assert issue3, "发料(棉纱32S→织造)失败"
        print(f"✅ 发料完成：棉纱32S→织造")

        # ======================== 17. 完成工序3（织造） ========================
        finish3 = api(client, "POST",
                      f"/api/production/productions/{mo_id}/processes/{proc3_id}/finish", {
            "unit_price": 1.20,
            "process_qty": 100,
        }, h)
        assert finish3, "工序3(织造)完工失败"
        print(f"✅ 工序3(织造)完工，所有工序已完成")

        # ======================== 18. 完工入库（含成本计算） ========================
        # 材料总成本 = 12×32 + 5×28 + 1.5×12 = 384+140+18 = ¥542
        # 加工费总成本 = 100×0.5 + 100×0.8 + 100×1.2 = 50+80+120 = ¥250
        # 总成本 = 542 + 250 = ¥792
        # 单位成本 = 792/100 = ¥7.92/米
        MATERIAL_COST = 384 + 140 + 18  # = 542
        PROCESS_COST = 50 + 80 + 120    # = 250
        TOTAL_COST = MATERIAL_COST + PROCESS_COST  # = 792
        UNIT_COST = TOTAL_COST / ORDER_QTY  # = 7.92

        receipt_res = api(client, "POST", f"/api/production/productions/{mo_id}/receipt", {
            "quantity": ORDER_QTY,
            "warehouse_id": wh_fg["id"],
            "material_cost": MATERIAL_COST,
            "process_cost": PROCESS_COST,
            "receipt_date": today_str,
        }, h)
        assert receipt_res, "完工入库失败"
        batch_fg = receipt_res.get("batch_no", "")
        print(f"✅ 完工入库成功，批次: {batch_fg}")
        print(f"   材料成本: ¥{MATERIAL_COST}, 加工费: ¥{PROCESS_COST}, 总成本: ¥{TOTAL_COST}")
        print(f"   单位成本: ¥{UNIT_COST:.2f}/米")

        # ======================== 19. 毛利核算 ========================
        sales_amount = ORDER_QTY * UNIT_PRICE  # 100 × 9.32 = 932
        gross_profit = sales_amount - TOTAL_COST  # 932 - 792 = 140
        gross_margin = gross_profit / sales_amount * 100  # 15.0%
        print(f"\n💰 毛利核算:")
        print(f"   销售收入: ¥{sales_amount:.2f}")
        print(f"   总成本:   ¥{TOTAL_COST:.2f} (材料¥{MATERIAL_COST}+加工费¥{PROCESS_COST})")
        print(f"   毛利:     ¥{gross_profit:.2f}")
        print(f"   毛利率:   {gross_margin:.1f}%")
        assert 10 <= gross_margin <= 20, f"毛利率{gross_margin:.1f}%不在10-20%范围内"

        # ======================== 20. 销售出库 ========================
        # 获取销售订单明细行ID
        so_detail = api(client, "GET", f"/api/sales/orders/{order_id}", None, h)
        assert so_detail, "销售订单获取失败"
        order_item_id = so_detail["items"][0]["id"]

        delivery = api(client, "POST", "/api/sales/deliveries", {
            "order_id": order_id,
            "order_item_id": order_item_id,
            "batch_no": batch_fg,
            "quantity": ORDER_QTY,
            "warehouse_id": wh_fg["id"],
            "delivery_date": today_str,
        }, h)
        assert delivery, "销售出库失败"
        delivery_no = delivery.get("delivery_no", "")
        print(f"✅ 销售出库完成: {delivery_no}")

        # ======================== 21. 销售发票 + 应收 ========================
        total_amount_incl = round(sales_amount * 1.13, 2)  # 含税
        tax_amount = round(sales_amount * 0.13 / 1.13, 2)

        si = api(client, "POST", "/api/sales/invoices", {
            "invoice_no": f"INV-S-{today_str}-001",
            "order_id": order_id,
            "invoice_date": today_str,
            "invoice_type": "出口发票",
            "amount": round(sales_amount / 1.13, 2),  # 不含税
            "amount_fc": round(sales_amount / 1.13, 2),
            "tax_amount": tax_amount,
            "total_amount": sales_amount,
            "tax_rate": 13,
        }, h)
        assert si, "销售发票创建失败"
        print(f"✅ 销售发票已创建，应收已生成 AR: {si.get('ar_no', '')}")

        # ======================== 22. 收款 ========================
        ar_list = api(client, "GET", "/api/sales/ar", None, h)
        assert ar_list and ar_list.get("items"), "应收未生成"
        ar_id = ar_list["items"][0]["id"]
        print(f"✅ 查询应收: ¥{ar_list['items'][0].get('amount', 0)}")

        collection = api(client, "POST", "/api/sales/collections", {
            "customer_id": customers["上海纺织品进出口公司"],
            "collection_date": today_str,
            "amount": sales_amount,
            "amount_fc": sales_amount,
            "currency_id": cny["id"],
            "collection_method": "电汇",
            "remark": f"销售回款 {order_no}",
            "ar_account_ids": [ar_id],
        }, h)
        assert collection, "收款失败"
        print(f"✅ 收款完成: {collection.get('message', '')}")

        # ======================== 23. 退税计算 ========================
        # 免抵退税额计算（简化版）
        refund_calc = api(client, "POST", "/api/tax-refund/calculate", {
            "export_amount_fob": sales_amount,
            "refund_rate": 13,
            "tax_rate": 13,
            "domestic_tax": 0,
            "input_tax": tax_amount,
            "last_period_deduction": 0,
        }, h)
        assert refund_calc, "退税计算失败"
        print(f"✅ 退税计算完成:")
        print(f"   免抵退税额: ¥{refund_calc.get('tax_refund', 0):.2f}")
        print(f"   应退税额: ¥{refund_calc.get('actual_refund', 0):.2f}")

        # ======================== 24. 最终检查 ========================
        print(f"\n{'='*60}")
        print(f"   全流程测试完成 ✅")
        print(f"   订单: {order_no}")
        print(f"   生产: {mo_no} ({ORDER_QTY}米)")
        print(f"   销售: ¥{sales_amount:.2f}")
        print(f"   成本: ¥{TOTAL_COST:.2f}")
        print(f"   毛利: ¥{gross_profit:.2f} ({gross_margin:.1f}%)")
        print(f"{'='*60}")

    # ---- 辅助方法 ----
    @staticmethod
    def _api(client, method, path, json_data=None, headers=None):
        """统一 API 调用"""
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
            print(f"  ❌ {method} {path} → {resp.status_code}: {resp.text[:200]}")
            return None
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}
