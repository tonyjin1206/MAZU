"""迁移：清理委外残留（2026-07-31）

- DROP TABLE mo_outsourcing（委外工单，旧模型，无任何路由引用）
- DROP TABLE mo_outsource_receipt（委外入库，旧模型）
- mo_material_issue 去掉 outsource_id 列（旧路径，重建表）

幂等：表不存在则跳过。新环境无需执行（create_all 直接建新结构）。
用法: python scripts/migrate_remove_outsourcing.py [数据库路径，默认 backend/data/erp.db]
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

DDL_ISSUE_NEW = """
CREATE TABLE mo_material_issue_new (
    id INTEGER NOT NULL,
    issue_no VARCHAR(64) NOT NULL,
    production_id INTEGER,
    process_id INTEGER,
    material_id INTEGER NOT NULL,
    batch_no VARCHAR(64) NOT NULL,
    quantity FLOAT NOT NULL,
    unit_price FLOAT DEFAULT 0,
    issue_date DATE NOT NULL,
    warehouse_id INTEGER NOT NULL,
    remark TEXT,
    operator VARCHAR(32),
    created_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(production_id) REFERENCES mo_production (id),
    FOREIGN KEY(process_id) REFERENCES mo_production_process (id),
    FOREIGN KEY(material_id) REFERENCES fd_material (id),
    FOREIGN KEY(warehouse_id) REFERENCES fd_warehouse (id)
)
"""


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    changed = False
    try:
        cur.execute("PRAGMA foreign_keys=OFF")

        # 1. 删委外工单表
        if cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='mo_outsourcing'").fetchone()[0]:
            n = cur.execute("SELECT COUNT(*) FROM mo_outsourcing").fetchone()[0]
            cur.execute("DROP TABLE mo_outsourcing")
            print(f"DROP mo_outsourcing（{n} 行）")
            changed = True
        else:
            print("mo_outsourcing 不存在，跳过")

        # 2. 删委外入库表
        if cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='mo_outsource_receipt'").fetchone()[0]:
            n = cur.execute("SELECT COUNT(*) FROM mo_outsource_receipt").fetchone()[0]
            cur.execute("DROP TABLE mo_outsource_receipt")
            print(f"DROP mo_outsource_receipt（{n} 行）")
            changed = True
        else:
            print("mo_outsource_receipt 不存在，跳过")

        # 3. mo_material_issue 去 outsource_id（重建表）
        if cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='mo_material_issue'").fetchone()[0]:
            cols = [r[1] for r in cur.execute("PRAGMA table_info(mo_material_issue)").fetchall()]
            if "outsource_id" in cols:
                n = cur.execute("SELECT COUNT(*) FROM mo_material_issue").fetchone()[0]
                cur.execute(DDL_ISSUE_NEW)
                cur.execute("""
                    INSERT INTO mo_material_issue_new
                        (id, issue_no, production_id, process_id, material_id, batch_no,
                         quantity, unit_price, issue_date, warehouse_id, remark, operator, created_at)
                    SELECT id, issue_no, production_id, process_id, material_id, batch_no,
                           quantity, unit_price, issue_date, warehouse_id, remark, operator, created_at
                    FROM mo_material_issue
                """)
                cur.execute("DROP TABLE mo_material_issue")
                cur.execute("ALTER TABLE mo_material_issue_new RENAME TO mo_material_issue")
                print(f"mo_material_issue 重建（去 outsource_id，保留 {n} 行）")
                changed = True
            else:
                print("mo_material_issue 已无 outsource_id，跳过")
        else:
            print("mo_material_issue 不存在，跳过")

        cur.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        return changed
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        print(f"数据库不存在（新环境无需迁移）: {db}")
        sys.exit(0)
    migrate(db)
