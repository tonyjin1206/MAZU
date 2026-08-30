"""迁移：生产模块去委外化（v2.8.0 V4）

背景：V1（t_fa4a52bf）已在**模型层**将生产模块改为纯自产——删除
`ProductionProcess.outsourcer_id`（委外商）与 `outsourcer` 关系，委外业务统一
归口「转外发（outsource=OutsourceOrder/os_order）」路线。但 SQLAlchemy
`create_all` 只建新表/新列，**不会删除已存在表中的旧列**。因此旧库（V1 之前创建）
的 `mo_production_process` 表仍物理残留 `outsourcer_id` 列。

本迁移脚本负责把**旧库中生产模块的遗留委外列**物理清理掉，去委外化，且：
- 既有数据兼容：重建表时完整保留其余列的数据（不丢失）；
- 可重复执行：列不存在则跳过（幂等）；
- 空库/新环境无需执行（create_all 直接建新结构，无残留列）。

处理清单：
1. `mo_production_process` 去 `outsourcer_id` 列（委外商，V1 模型已删 → 旧库物理删列）。

说明：
- `mo_material_issue` 的 `outsource_id` 列已由 `migrate_remove_outsourcing.py` 清理；
- `mo_outsourcing`（旧委外工单表）已由 `migrate_remove_outsourcing.py` DROP；
- `fd_process.is_outsource`、`fd_product_process.default_outsourcer_id/default_supplier_id`
  在模型层**仍保留**（工序默认自产、委外归口转外发 route，V2 前端已恒置 is_outsource=0），
  不属于"模型层已删需物理清理"范畴，本脚本不动。

用法: python scripts/migrate_production_deoutsourcing.py [数据库路径，默认 backend/data/erp.db]
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

# mo_production_process 重建 DDL（去 outsourcer_id 列，其余结构不变）
DDL_PROCESS_NEW = """
CREATE TABLE mo_production_process_new (
    id INTEGER NOT NULL,
    production_id INTEGER NOT NULL,
    process_id INTEGER NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,
    unit_price FLOAT DEFAULT 0,
    process_qty FLOAT DEFAULT 0,
    process_amount FLOAT DEFAULT 0,
    status VARCHAR(16) DEFAULT '待排产',
    PRIMARY KEY (id),
    FOREIGN KEY(production_id) REFERENCES mo_production (id),
    FOREIGN KEY(process_id) REFERENCES fd_process (id)
)
"""


def _table_exists(cur, table: str) -> bool:
    return bool(cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _column_names(cur, table: str) -> list[str]:
    return [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]


def _drop_column(cur, table: str, col: str, ddl_new: str, label: str) -> bool:
    """去列：物理删除 table.col（重建表保数据）。幂等：列不存在则跳过。"""
    if not _table_exists(cur, table):
        print(f"[跳过] 表 {table} 不存在")
        return False
    cols = _column_names(cur, table)
    if col not in cols:
        print(f"[跳过] {table}.{col} 已不存在（无需迁移）")
        return False
    n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    # 重建表（不带该列）
    cur.execute(ddl_new)
    keep_cols = [c for c in cols if c != col]
    cur.execute(f"INSERT INTO {table}_new ({', '.join(keep_cols)}) "
                f"SELECT {', '.join(keep_cols)} FROM {table}")
    cur.execute(f"DROP TABLE {table}")
    cur.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    print(f"[执行] {label}：重建 {table}（去 {col} 列，保留 {n} 行数据）")
    return True


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    changed = False
    try:
        cur.execute("PRAGMA foreign_keys=OFF")

        # 1. mo_production_process 去 outsourcer_id（委外商）→ 纯自产
        changed = _drop_column(
            cur, "mo_production_process", "outsourcer_id",
            DDL_PROCESS_NEW, "生产工序去委外化",
        ) or changed

        cur.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        print("\n迁移完成 ✅" if changed else "\n已是最新结构，无需迁移 ✅")
        return changed
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        print(f"数据库不存在（新环境由 create_all 自动建表，无需迁移）: {db}")
        sys.exit(0)
    migrate(db)
