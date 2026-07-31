"""MTS 测试数据 — 统一基础档案构建器（v2）

== 规范（项目文档见 README「测试数据规范」）==
1. 所有测试共用本模块构建基础档案，禁止在各自测试文件里另建档案
   （历史教训：各文件独立建仓库/供应商导致 RM990001、WH-BND、WH-BOT 等
   垃圾数据堆积，且仓库字段不全）
2. 新增测试需要新档案时，在本模块的 build_foundation 上扩展，不要另起炉灶
3. 数据走 API 正常创建（POST /foundation/...），不直接灌 SQL
4. 仓库档案必须字段完整（code/name/wh_type/address/manager）——
   出入库/盘点的 warehouse_id 后端会参照仓库档案校验（不存在或停用 → 400）

数据规模（少而真实）：2 供应商 / 2 客户 / 4 物料 / 2 产品 / 4 工序 / 2 仓库 / 2 BOM / 2 工艺路线
"""

# ======================== 纺织真实基础数据 ========================

_realistic = {
    "materials": [
        ("精梳棉纱32S", "RM001", "kg", 32.0, "纯棉精梳32支单纱"),
        ("纯棉经纱",    "RM002", "kg", 28.0, "纯棉普梳经纱40S"),
        ("纯棉纬纱",    "RM003", "kg", 26.0, "纯棉普梳纬纱32S"),
        ("活性染料套餐", "RM004", "kg", 15.0, "活性染色助剂套装"),
    ],
    "processes": [
        ("整经", "PROC01", 0.50), ("织造", "PROC02", 1.20),
        ("染色", "PROC03", 2.00), ("整理", "PROC04", 0.60),
    ],
    "suppliers": [
        ("华润纺织(山东)有限公司", "SDHR", "李国华", "0531-88886666",
         "91370100MA3C5NJR8X", "山东省济南市历下区工业南路66号", "原材料"),
        ("江苏阳光纺织科技有限公司", "JSYG", "张晓东", "0510-88223311",
         "91320200MA1N2WKH5A", "江苏省无锡市锡山区阳光工业园", "委外"),
    ],
    "customers": [
        ("上海进出口贸易有限公司", "SHJC", "021-68886600",
         "91310000MA1FL3WK67", "中国(上海)自由贸易试验区浦东大道1200号"),
        ("广州华衣集团股份有限公司", "GZHY", "020-83228811",
         "91440100MA59C5RN0R", "广东省广州市番禺区南村镇华衣路1号"),
    ],
    "products": [
        ("纯棉坯布",   "P001", 9.32, "C100 32S×32S 130×70 63\"", "52094200"),
        ("全棉色织布", "P002", 18.00, "C100 40S×40S 120×80 57/58\"", "52093100"),
    ],
    "hs_codes": {
        "52094200": ("牛仔布(棉≥85%)", "米", 13, 13),
        "52093100": ("纯棉色织平纹布", "米", 13, 13),
    },
    "warehouses": [
        ("RM", "原料仓", "原料仓", "浙江省绍兴市柯桥区轻纺城大道88号", "王建国"),
        ("FG", "成品仓", "成品仓", "浙江省绍兴市柯桥区滨海工业区1号", "刘芳"),
    ],
    "boms": {
        "纯棉坯布": [("精梳棉纱32S", 0.12), ("纯棉经纱", 0.05)],
        "全棉色织布": [("精梳棉纱32S", 0.10), ("纯棉纬纱", 0.04), ("活性染料套餐", 0.02)],
    },
    "routes": {
        "纯棉坯布": [("整经", 1, None), ("织造", 2, None)],
        "全棉色织布": [("整经", 1, None), ("织造", 2, None),
                      ("染色", 3, "江苏阳光纺织科技有限公司"), ("整理", 4, None)],
    },
}


# ======================== 统一构建器 ========================

def _api(client, method, path, json_data=None, headers=None):
    """发请求，>=400 时抛异常（构建器不允许静默失败）"""
    resp = client.request(method, path, json=json_data or {}, headers=headers)
    if resp.status_code >= 400:
        raise AssertionError(f"[构建档案] {method} {path} → {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def build_foundation(client, auth_headers):
    """通过 API 构建全套基础档案（幂等：同 session 多次调用会 409 冲突，仅供一次构建）

    返回 dict：
      cny / wh_rm / wh_fg（仓库 id）
      sup（原材料供应商 id）/ sup_os（委外供应商 id）
      cust（客户 id 列表）/ mats（材料名→id）/ procs（工序名→id）
      prods（产品名→{"id","price"}）
      hs 由产品创建时带出
    """
    h = auth_headers
    r = _realistic

    # 币种：main.py startup seed 已建默认币种（CNY 等），存在则复用
    currencies = _api(client, "GET", "/api/foundation/currencies?page_size=50", None, h)
    cny = next((c for c in currencies.get("items", []) if c["code"] == "CNY"), None)
    if not cny:
        cny = _api(client, "POST", "/api/foundation/currencies",
                   {"code": "CNY", "name": "人民币", "symbol": "¥", "is_base": 1}, h)

    # 仓库：完整字段（code/name/wh_type/address/manager）—— 出入库参照校验依赖档案
    wh_rm = _api(client, "POST", "/api/foundation/warehouses",
                 {"code": "RM", "name": "原料仓", "wh_type": "原料仓",
                  "address": r["warehouses"][0][3], "manager": r["warehouses"][0][4]}, h)["id"]
    wh_fg = _api(client, "POST", "/api/foundation/warehouses",
                 {"code": "FG", "name": "成品仓", "wh_type": "成品仓",
                  "address": r["warehouses"][1][3], "manager": r["warehouses"][1][4]}, h)["id"]

    # 供应商：原材料 1 + 委外 1（委外商 = supplier_type=委外，不单独建表）
    sup = {}
    for name, code, cp, phone, tax_id, addr, stype in r["suppliers"]:
        sup[name] = _api(client, "POST", "/api/foundation/suppliers",
                         {"name": name, "contact_person": cp, "phone": phone,
                          "tax_id": tax_id, "address": addr, "supplier_type": stype}, h)["id"]
    sup_os = sup["江苏阳光纺织科技有限公司"]  # 委外商

    # 客户
    cust = []
    for name, code, phone, tax_id, addr in r["customers"]:
        cust.append(_api(client, "POST", "/api/foundation/customers",
                         {"name_cn": name, "country": "中国", "contact_person": "联系人",
                          "phone": phone, "tax_id": tax_id, "address": addr}, h)["id"])

    # 物料
    mats = {}
    for name, code, unit, price, spec in r["materials"]:
        mats[name] = _api(client, "POST", "/api/foundation/materials",
                          {"name": name, "spec": spec, "unit": unit,
                           "category": "原材料", "purchase_price": price}, h)["id"]

    # 工序
    procs = {}
    for name, code, price in r["processes"]:
        procs[name] = _api(client, "POST", "/api/foundation/processes",
                           {"code": code, "name": name, "unit_price": price}, h)["id"]

    # 产品（含 HS 编码/退税率）
    prods = {}
    for name, code, price, spec, hsc in r["products"]:
        hs_info = r["hs_codes"][hsc]
        p = _api(client, "POST", "/api/foundation/products",
                 {"name_cn": name, "spec": spec, "unit": "米", "sale_price": price,
                  "hs_code": hsc, "refund_rate": hs_info[3], "tax_rate": hs_info[2]}, h)
        prods[name] = {"id": p["id"], "price": price}

    # BOM
    for pname, items in r["boms"].items():
        for mname, qty in items:
            _api(client, "POST", "/api/foundation/bom",
                 {"product_id": prods[pname]["id"], "material_id": mats[mname],
                  "quantity": qty, "bom_name": f"{pname}BOM"}, h)

    # 工艺路线（含委外工序）
    for pname, rts in r["routes"].items():
        _api(client, "PUT", f"/api/foundation/products/{prods[pname]['id']}/processes",
             [{"process_id": procs[n], "seq": s, "default_unit_price": 0.50,
               **( {"default_outsourcer_id": sup_os} if oid else {})}
              for n, s, oid in rts], h)

    return {
        "cny": cny, "wh_rm": wh_rm, "wh_fg": wh_fg,
        "sup": sup["华润纺织(山东)有限公司"], "sup_os": sup_os,
        "cust": cust, "mats": mats, "procs": procs, "prods": prods,
    }
