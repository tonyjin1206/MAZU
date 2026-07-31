"""迁移：库存收发存 v2（盘点/红冲/退货/发料拆类型）

1. po_receipt 加 is_red / red_of_receipt_id（采购红冲）
2. so_delivery 加 is_return / return_of_delivery_id（销售退货）
3. 历史流水拆类型：发料流水 trans_type 原统一为 outsource_out，
   按发料单关联工序是否有委外商(outsourcer_id)拆分：
   - 委外工序 → 保持 outsource_out
   - 自产工序 → 改为 material_issue_out
   （无发料单关联或工序无法判断的流水保持原样不动）

盘点新表 inv_stocktake / inv_stocktake_item 由 create_all 自动创建，无需迁移。

幂等：已迁移则跳过。新环境无需执行（create_all 直接建新结构）。

用法: python scripts/migrate_inventory_v2.py [数据库路径，默认 backend/data/erp.db]
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

ALTERS = [
    # (表, 列, DDL)
    ("po_receipt", "is_red", "ALTER TABLE po_receipt ADD COLUMN is_red INTEGER DEFAULT 0"),
    ("po_receipt", "red_of_receipt_id", "ALTER TABLE po_receipt ADD COLUMN red_of_receipt_id INTEGER"),
    ("so_delivery", "is_return", "ALTER TABLE so_delivery ADD COLUMN is_return INTEGER DEFAULT 0"),
    ("so_delivery", "return_of_delivery_id", "ALTER TABLE so_delivery ADD COLUMN return_of_delivery_id INTEGER"),
]


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    changed = False
    try:
        # ========== 1. 加列 ==========
        for table, col, ddl in ALTERS:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            if col in cols:
                print(f"[跳过] {table}.{col} 已存在")
                continue
            print(f"[执行] {ddl}")
            cur.execute(ddl)
            changed = True

        # ========== 2. 历史发料流水拆类型 ==========
        # 自产工序的发料：outsource_out → material_issue_out
        cur.execute("""
            UPDATE inv_transaction
            SET trans_type = 'material_issue_out'
            WHERE trans_type = 'outsource_out'
              AND source_doc_no IN (
                  SELECT mi.issue_no
                  FROM mo_material_issue mi
                  JOIN mo_production_process mp ON mi.process_id = mp.id
                  WHERE mp.outsourcer_id IS NULL
              )
        """)
        n = cur.rowcount
        if n:
            print(f"[执行] 历史发料流水拆分：{n} 条 自产发料 outsource_out → material_issue_out")
            changed = True
        else:
            print("[跳过] 无需要拆分的自产发料流水")

        conn.commit()
        if changed:
            print("\n迁移完成 ✅")
        else:
            print("\n已是最新结构，无需迁移 ✅")
        return changed
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        print(f"数据库不存在: {db}（新环境由 create_all 自动建表，无需迁移）")
        sys.exit(0)
    migrate(db)
