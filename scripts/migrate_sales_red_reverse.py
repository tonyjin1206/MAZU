"""迁移：销售退货 · 发票红冲 · 负数申报（2026-08-03）

- so_delivery   新增 refund_declared（退货单标记：关联报关单已报税）
- so_invoice    新增 is_red / red_of_invoice_id（红字发票）
- ar_account    新增 is_red / red_of_ar_id（红字应收）
- 新增 ar_adjustment 表（核销转移：应收间余额调整）

幂等：已迁移则跳过。新环境无需执行（create_all 直接建新结构）。

用法: python scripts/migrate_sales_red_reverse.py [数据库路径，默认 backend/data/erp.db]
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

# 新增列: (表, 列, DDL)
ADD_COLUMNS = [
    ("so_delivery", "refund_declared", "INTEGER DEFAULT 0"),
    ("so_invoice", "is_red", "INTEGER DEFAULT 0"),
    ("so_invoice", "red_of_invoice_id", "INTEGER"),
    ("ar_account", "is_red", "INTEGER DEFAULT 0"),
    ("ar_account", "red_of_ar_id", "INTEGER"),
]

DDL_NEW_TABLE = """
CREATE TABLE IF NOT EXISTS ar_adjustment (
    id INTEGER NOT NULL,
    source_ar_id INTEGER NOT NULL,
    target_ar_id INTEGER NOT NULL,
    amount FLOAT DEFAULT 0,
    remark TEXT,
    operator VARCHAR(32),
    created_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(source_ar_id) REFERENCES ar_account (id),
    FOREIGN KEY(target_ar_id) REFERENCES ar_account (id)
)
"""


def migrate(db_path: Path) -> bool:
    if not db_path.exists():
        print(f"数据库不存在（新环境无需迁移）: {db_path}")
        return False
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        changed = False
        for table, col, ddl in ADD_COLUMNS:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            if col not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
                print(f"ALTER {table} ADD {col} {ddl}")
                changed = True
            else:
                print(f"{table}.{col} 已存在，跳过")
        cur.execute(DDL_NEW_TABLE)
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "ar_adjustment" in tables:
            print("ar_adjustment 表已存在")
        else:
            print("ar_adjustment 表已创建")
            changed = True
        conn.commit()
        if changed:
            print("迁移完成")
        else:
            print("无需迁移（已是最新结构）")
        return changed
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    migrate(db)
