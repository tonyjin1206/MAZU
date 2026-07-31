"""迁移：po_receipt_item 支持成品采购入库（BUG#1 修复）

- 新增 product_id 列（可空，FK fd_product.id）
- material_id 改可空（材料/成品互斥）
- 幂等：已迁移则跳过。新环境无需执行（create_all 直接建新结构）。

用法: python scripts/migrate_po_receipt_item.py [数据库路径，默认 backend/data/erp.db]
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

DDL_NEW_TABLE = """
CREATE TABLE po_receipt_item_new (
    id INTEGER NOT NULL,
    receipt_id INTEGER NOT NULL,
    order_item_id INTEGER,
    material_id INTEGER,
    product_id INTEGER,
    quantity FLOAT NOT NULL,
    unit_price FLOAT DEFAULT 0,
    batch_no VARCHAR(64) NOT NULL,
    remark TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(receipt_id) REFERENCES po_receipt (id),
    FOREIGN KEY(order_item_id) REFERENCES po_order_item (id),
    FOREIGN KEY(material_id) REFERENCES fd_material (id),
    FOREIGN KEY(product_id) REFERENCES fd_product (id)
)
"""


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(po_receipt_item)").fetchall()]
        if "product_id" in cols and "material_id" in cols:
            # PRAGMA table_info 第4列 notnull：0=可空，1=NOT NULL
            mat_notnull = [r for r in cur.execute("PRAGMA table_info(po_receipt_item)").fetchall()
                           if r[1] == "material_id"][0][3]
            if not mat_notnull:
                print("已是最新结构，跳过")
                return False
            print("material_id 仍为 NOT NULL，需要重建")
        print("重建 po_receipt_item 表（加 product_id 列，material_id 改可空）...")
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute(DDL_NEW_TABLE)
        cur.execute("""
            INSERT INTO po_receipt_item_new
                (id, receipt_id, order_item_id, material_id, quantity, unit_price, batch_no, remark)
            SELECT id, receipt_id, order_item_id, material_id, quantity, unit_price, batch_no, remark
            FROM po_receipt_item
        """)
        cur.execute("DROP TABLE po_receipt_item")
        cur.execute("ALTER TABLE po_receipt_item_new RENAME TO po_receipt_item")
        cur.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        n = cur.execute("SELECT COUNT(*) FROM po_receipt_item").fetchone()[0]
        print(f"迁移完成，保留 {n} 行数据")
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        print(f"数据库不存在（新环境无需迁移）: {db}")
        sys.exit(0)
    migrate(db)
