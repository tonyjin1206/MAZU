"""报关单明细化迁移（v2.6.0）：so_customs.hs_code_id 可空 + 新增 so_customs_item 商品行 + 旧数据回填

- so_customs.hs_code_id 改为可空（表头不再强制单 HS，按商品行报 HS）
- 新建 so_customs_item（报关单商品行：product_id/hs_code_id/quantity/declare_amount/unit_price）
- tr_declaration_detail 加 customs_item_id（精确追溯商品行，可空）
- 旧数据回填：已有报关单 → 自动生成 1 个商品行（取订单首个明细产品 + 表头 HS + 表头金额）

用法: python scripts/migrate_customs_items.py [数据库路径，默认 backend/data/erp.db]
幂等：可重复执行。
"""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "backend" / "data" / "erp.db"


def migrate(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) so_customs_item 建表（幂等）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS so_customs_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customs_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            hs_code_id INTEGER NOT NULL,
            quantity FLOAT DEFAULT 0,
            declare_amount FLOAT DEFAULT 0,
            unit_price FLOAT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customs_id) REFERENCES so_customs (id),
            FOREIGN KEY (product_id) REFERENCES fd_product (id),
            FOREIGN KEY (hs_code_id) REFERENCES fd_hs_code (id)
        )
    """)
    print("✅ so_customs_item 表就绪")

    # 2) so_customs.hs_code_id 改可空（SQLite 重建表）
    cols = {r["name"]: r for r in cur.execute("PRAGMA table_info(so_customs)").fetchall()}
    if cols["hs_code_id"]["notnull"] == 1:
        cur.execute("BEGIN")
        cur.execute("""CREATE TABLE so_customs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customs_no VARCHAR(64) NOT NULL UNIQUE,
            order_id INTEGER NOT NULL,
            delivery_id INTEGER,
            hs_code_id INTEGER,
            declare_amount FLOAT DEFAULT 0,
            declare_currency INTEGER,
            declare_date DATE NOT NULL,
            customs_broker VARCHAR(128),
            status VARCHAR(16) DEFAULT '已报关',
            refund_status VARCHAR(16) DEFAULT '待申报',
            remark TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )""")
        cols_list = [c["name"] for c in cur.execute("PRAGMA table_info(so_customs)").fetchall()]
        cur.execute(f"INSERT INTO so_customs_new ({', '.join(cols_list)}) SELECT {', '.join(cols_list)} FROM so_customs")
        cur.execute("DROP TABLE so_customs")
        cur.execute("ALTER TABLE so_customs_new RENAME TO so_customs")
        cur.execute("COMMIT")
        print("✅ so_customs.hs_code_id 已改为可空（重建表）")
    else:
        print("ℹ️ so_customs.hs_code_id 已是可空，跳过")

    # 3) tr_declaration_detail 加 customs_item_id（幂等）
    dcols = [r["name"] for r in cur.execute("PRAGMA table_info(tr_declaration_detail)").fetchall()]
    if "customs_item_id" not in dcols:
        cur.execute("ALTER TABLE tr_declaration_detail ADD COLUMN customs_item_id INTEGER")
        print("✅ tr_declaration_detail.customs_item_id 已添加")
    else:
        print("ℹ️ tr_declaration_detail.customs_item_id 已存在，跳过")

    # 3b) tr_declaration_row 加 customs_item_id（申报行出口端关联，v2.6.0 双端匹配）
    rcols = [r["name"] for r in cur.execute("PRAGMA table_info(tr_declaration_row)").fetchall()]
    if "customs_item_id" not in rcols:
        cur.execute("ALTER TABLE tr_declaration_row ADD COLUMN customs_item_id INTEGER")
        print("✅ tr_declaration_row.customs_item_id 已添加")
    else:
        print("ℹ️ tr_declaration_row.customs_item_id 已存在，跳过")

    # 4) 旧数据回填：每张无商品行的报关单生成 1 个商品行
    customs_rows = cur.execute("""
        SELECT c.id, c.hs_code_id, c.declare_amount, c.order_id
        FROM so_customs c
        WHERE NOT EXISTS (SELECT 1 FROM so_customs_item i WHERE i.customs_id = c.id)
    """).fetchall()
    backfilled = 0
    for c in customs_rows:
        # 取订单首个明细产品（优先级：明细行；无则空跳过）
        oi = cur.execute("""
            SELECT product_id, quantity, unit_price FROM so_order_item
            WHERE order_id = ? ORDER BY id LIMIT 1
        """, (c["order_id"],)).fetchone()
        if not oi:
            continue
        hs = c["hs_code_id"]
        if not hs:
            hs = cur.execute("SELECT hs_code_id FROM fd_product WHERE id = ?", (oi["product_id"],)).fetchone()
            hs = hs["hs_code_id"] if hs else None
        if not hs:
            continue
        cur.execute("""
            INSERT INTO so_customs_item (customs_id, product_id, hs_code_id, quantity, declare_amount, unit_price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (c["id"], oi["product_id"], hs, oi["quantity"] or 0, c["declare_amount"] or 0, oi["unit_price"] or 0))
        backfilled += 1
    conn.commit()
    print(f"✅ 旧报关单回填商品行：{backfilled} 张")
    conn.close()
    print("🎉 迁移完成")


if __name__ == "__main__":
    migrate(DB)
