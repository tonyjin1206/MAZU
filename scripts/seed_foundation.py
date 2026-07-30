"""
基础数据初始化 — 纺织外贸企业真实场景
数据源自 tests/test_data.py 的纺织品行业配置
"""
import requests, sys

BASE = "http://localhost:8788/api"

r = requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"admin123"})
if r.status_code != 200:
    print("❌ 登录失败"); sys.exit(1)
T = r.json()["access_token"]
H = {"Content-Type": "application/json", "Authorization": f"Bearer {T}"}
print("✅ 登录成功\n")

ok=0; fail=0
def api(method, path, data=None, quiet=False):
    global ok, fail
    r = requests.request(method, f"{BASE}{path}", headers=H, json=data)
    if r.status_code >= 400:
        fail += 1
        if not quiet: print(f"  ❌ {r.status_code} {path}: {r.text[:150]}")
        return None
    ok += 1
    return r.json()

# ============================
#  真实纺织品基础数据
# ============================
print("═══ 基础配置 ═══")
cny = api("POST", "/foundation/currencies", {"code":"CNY","name":"人民币","symbol":"¥","is_base":1})
api("POST", "/foundation/currencies", {"code":"USD","name":"美元","symbol":"$"})
api("POST", "/foundation/trade-terms", {"code":"FOB","name":"FOB(离岸价)"})
api("POST", "/foundation/trade-terms", {"code":"CIF","name":"CIF(到岸价)"})
wh_rm = api("POST", "/foundation/warehouses", {"code":"RM","name":"原料仓","wh_type":"原料仓"})
wh_fg = api("POST", "/foundation/warehouses", {"code":"FG","name":"成品仓","wh_type":"成品仓"})
print(f"✅ 币种(2) 贸易术语(2) 仓库(2)")

# ============================
#  8种原材料
# ============================
print("\n═══ 原材料(8) ═══")
materials_data = [
    ("精梳棉纱32S",  "RM001", "kg", 32.0,  "纯棉精梳32支单纱"),
    ("精梳棉纱40S",  "RM002", "kg", 38.0,  "纯棉精梳40支单纱"),
    ("涤纶低弹丝75D","RM003", "kg", 18.0,  "涤纶低弹丝75D/72F"),
    ("纯棉经纱",     "RM004", "kg", 28.0,  "纯棉普梳经纱40S"),
    ("纯棉纬纱",     "RM005", "kg", 26.0,  "纯棉普梳纬纱32S"),
    ("活性染料套餐",  "RM006", "kg", 15.0,  "活性染色助剂套装"),
    ("编织布包装卷",  "RM007", "套", 5.0,   "编织布包装卷(1.2m×200m)"),
    ("变性淀粉浆料",  "RM008", "kg", 12.0,  "变性淀粉浆料(纺织专用)"),
]
mat_ids = {}
for name, code, unit, price, spec in materials_data:
    m = api("POST", "/foundation/materials", {
        "name": name, "code": code, "spec": spec,
        "unit": unit, "category": "原材料", "purchase_price": price,
    })
    mat_ids[name] = m["id"]
    print(f"  ✅ {name} [{code}]")

# ============================
#  6个工序
# ============================
print("\n═══ 工序(6) ═══")
processes_data = [
    ("整经", "PROC01", 0.50),
    ("浆纱", "PROC02", 0.80),
    ("织造", "PROC03", 1.20),
    ("染色", "PROC04", 2.00),
    ("整理", "PROC05", 0.60),
    ("后整理", "PROC06", 1.00),
]
proc_ids = {}
for name, code, price in processes_data:
    p = api("POST", "/foundation/processes", {"code": code, "name": name, "unit_price": price})
    proc_ids[name] = p["id"]
    print(f"  ✅ {name} [{code}]  ¥{price}")

# ============================
#  4个供应商
# ============================
print("\n═══ 供应商(4) ═══")
suppliers_data = [
    ("华润纺织(山东)有限公司",  "SDHR", "李国华", "0531-88886666", "91370100MA3C5NJR8X",
     "山东省济南市历下区工业南路66号", "原材料"),
    ("新野纺织集团股份有限公司","HNXY", "王建设", "0377-66223388", "91411300MA3XDGJ37B",
     "河南省南阳市新野县纺织路88号", "原材料"),
    ("江苏阳光纺织科技有限公司","JSYG", "张晓东", "0510-88223311", "91320200MA1N2WKH5A",
     "江苏省无锡市锡山区阳光工业园", "委外"),
    ("杭州宏丰化工有限公司",    "HZHF", "陈志华", "0571-87229900", "91330100MA27WAKG8F",
     "浙江省杭州市萧山区临江化工园区", "委外"),
]
sup_ids = {}
for name, code, cp, phone, tax_id, addr, stype in suppliers_data:
    s = api("POST", "/foundation/suppliers", {
        "name": name, "contact_person": cp, "phone": phone,
        "tax_id": tax_id, "address": addr, "supplier_type": stype,
    })
    sup_ids[name] = s["id"]
    print(f"  ✅ {name}")

# ============================
#  2个委外商
# ============================
print("\n═══ 委外商(2) ═══")
os_sun = api("POST", "/foundation/outsourcers",
    {"supplier_id": sup_ids["江苏阳光纺织科技有限公司"], "lead_time": 3})
os_hong = api("POST", "/foundation/outsourcers",
    {"supplier_id": sup_ids["杭州宏丰化工有限公司"], "lead_time": 5})
print(f"  ✅ 江苏阳光(lead_time=3) 杭州宏丰(lead_time=5)")

# ============================
#  3个客户
# ============================
print("\n═══ 客户(3) ═══")
customers_data = [
    ("上海进出口贸易有限公司",  "SHJC", "021-68886600", "91310000MA1FL3WK67",
     "中国(上海)自由贸易试验区浦东大道1200号", "上海"),
    ("广州华衣集团股份有限公司", "GZHY", "020-83228811", "91440100MA59C5RN0R",
     "广东省广州市番禺区南村镇华衣路1号", "中国"),
    ("浙江天诚纺织进出口公司",   "ZJTC", "0574-88002233", "91330200MA2CH9CJ1K",
     "浙江省宁波市海曙区段塘西路88号", "中国"),
]
cust_ids = {}
for name, code, phone, tax_id, addr, country in customers_data:
    c = api("POST", "/foundation/customers", {
        "name_cn": name, "country": country,
        "contact_person": "联系人", "phone": phone,
        "tax_id": tax_id, "address": addr,
    })
    cust_ids[name] = c["id"]
    print(f"  ✅ {name}")

# ============================
#  HS编码 + 3个产品
# ============================
print("\n═══ HS编码 & 产品(3) ═══")
hs_info = {
    "52094200": ("牛仔布(棉≥85%)", "米", 13, 13),
    "52104100": ("涤棉平纹布(棉<85%)", "米", 13, 11),
    "52093100": ("纯棉色织平纹布", "米", 13, 13),
}
hs_ids = {}
for hsc, (hname, unit, tax_rate, refund_rate) in hs_info.items():
    h = api("POST", "/foundation/hs-codes", {
        "hs_code": hsc, "name": hname, "unit": unit,
        "tax_rate": tax_rate, "refund_rate": refund_rate,
    })
    hs_ids[hsc] = h["id"]

products_data = [
    ("纯棉坯布",   "P001", 9.32,  "C100 32S×32S 130×70 63\"", "52094200"),
    ("T/C涤棉布",  "P002", 13.50, "T/C 65/35 45S×45S 133×72 63\"", "52104100"),
    ("全棉色织布", "P003", 18.00, "C100 40S×40S 120×80 57/58\"", "52093100"),
]
prod_ids = {}
for name, code, price, spec, hsc in products_data:
    p = api("POST", "/foundation/products", {
        "name_cn": name, "code": code, "spec": spec,
        "unit": "米", "sale_price": price,
        "hs_code": hsc, "refund_rate": hs_info[hsc][3], "tax_rate": hs_info[hsc][2],
    })
    prod_ids[name] = {"id": p["id"], "price": price}
    print(f"  ✅ {name} ¥{price}/米")

# ============================
#  BOM（3产品 × 材料清单）
# ============================
print("\n═══ BOM ═══")
boms = {
    "纯棉坯布":  [
        (mat_ids["精梳棉纱32S"], 0.12),
        (mat_ids["纯棉经纱"], 0.05),
        (mat_ids["变性淀粉浆料"], 0.015),
    ],
    "T/C涤棉布": [
        (mat_ids["精梳棉纱40S"], 0.08),
        (mat_ids["涤纶低弹丝75D"], 0.06),
        (mat_ids["纯棉经纱"], 0.04),
        (mat_ids["变性淀粉浆料"], 0.01),
        (mat_ids["编织布包装卷"], 0.01),
    ],
    "全棉色织布": [
        (mat_ids["精梳棉纱40S"], 0.10),
        (mat_ids["精梳棉纱32S"], 0.04),
        (mat_ids["纯棉经纱"], 0.03),
        (mat_ids["纯棉纬纱"], 0.04),
        (mat_ids["活性染料套餐"], 0.02),
        (mat_ids["编织布包装卷"], 0.01),
    ],
}
for pname, items in boms.items():
    for mid, qty in items:
        api("POST", "/foundation/bom", {
            "product_id": prod_ids[pname]["id"],
            "material_id": mid, "quantity": qty,
            "bom_name": f"{pname}BOM",
        })
    print(f"  ✅ {pname}: {len(items)}项材料")

# ============================
#  工艺路线（产品工艺模板）
# ============================
print("\n═══ 工艺路线模板 ═══")
routes = {
    "纯棉坯布":  [
        {"process_id": proc_ids["整经"], "seq": 1},
        {"process_id": proc_ids["浆纱"], "seq": 2, "default_outsourcer_id": os_sun["id"], "default_unit_price": 0.50},
        {"process_id": proc_ids["织造"], "seq": 3},
    ],
    "T/C涤棉布": [
        {"process_id": proc_ids["整经"], "seq": 1},
        {"process_id": proc_ids["浆纱"], "seq": 2, "default_outsourcer_id": os_sun["id"], "default_unit_price": 0.50},
        {"process_id": proc_ids["织造"], "seq": 3},
        {"process_id": proc_ids["染色"], "seq": 4, "default_outsourcer_id": os_hong["id"], "default_unit_price": 2.00},
        {"process_id": proc_ids["整理"], "seq": 5},
    ],
    "全棉色织布": [
        {"process_id": proc_ids["整经"], "seq": 1},
        {"process_id": proc_ids["浆纱"], "seq": 2, "default_outsourcer_id": os_sun["id"], "default_unit_price": 0.50},
        {"process_id": proc_ids["织造"], "seq": 3},
        {"process_id": proc_ids["染色"], "seq": 4, "default_outsourcer_id": os_hong["id"], "default_unit_price": 2.00},
        {"process_id": proc_ids["后整理"], "seq": 5, "default_outsourcer_id": os_sun["id"], "default_unit_price": 1.00},
    ],
}
for pname, rts in routes.items():
    api("PUT", f"/foundation/products/{prod_ids[pname]['id']}/processes", rts)
    print(f"  ✅ {pname}: {len(rts)}道工序")

print(f"\n{'═' * 50}")
print(f"  🎉 基础数据初始化完成! 成功={ok} 失败={fail}")
print(f"  📦 8材料 × 6工序 × 4供应商 × 2委外商 × 3客户 × 3产品 × 3BOM × 3工艺路线")
print(f"{'═' * 50}")
