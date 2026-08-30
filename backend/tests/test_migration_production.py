"""生产模块去委外化迁移脚本测试（v2.8.0 V4）

验证 scripts/migrate_production_deoutsourcing.py：
- 旧库（V1 前）mo_production_process 含 outsourcer_id 列 → 迁移后物理删除该列；
- 既有数据完整保留（其余列不丢失）；
- 幂等：第二次执行跳过（changed=False）；
- 空库/新结构（表不存在或已无该列）安全跳过。

迁移脚本作用于独立临时库文件，不污染测试库（ERP_DATA_DIR 隔离的 erp.db）。
"""

import sqlite3
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "migrate_production_deoutsourcing.py"

# 迁移前（V1 前旧结构）mo_production_process 的 DDL（含 outsourcer_id）
OLD_DDL = """
CREATE TABLE mo_production (
    id INTEGER PRIMARY KEY,
    order_no VARCHAR(64) UNIQUE NOT NULL,
    product_id INTEGER NOT NULL,
    quantity FLOAT NOT NULL,
    status VARCHAR(16) DEFAULT '待确认'
);
CREATE TABLE mo_production_process (
    id INTEGER PRIMARY KEY,
    production_id INTEGER NOT NULL,
    process_id INTEGER NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,
    outsourcer_id INTEGER,
    unit_price FLOAT DEFAULT 0,
    process_qty FLOAT DEFAULT 0,
    process_amount FLOAT DEFAULT 0,
    status VARCHAR(16) DEFAULT '待排产'
);
INSERT INTO mo_production (id, order_no, product_id, quantity, status) VALUES
    (1, 'MO-20260731-001', 101, 10, '已排产');
INSERT INTO mo_production_process (id, production_id, process_id, seq, outsourcer_id, unit_price, process_qty, status) VALUES
    (1, 1, 501, 1, 88, 0.50, 10, '已完工'),
    (2, 1, 502, 2, NULL, 1.20, 10, '待排产');
"""


def _load_migrate():
    spec = importlib.util.spec_from_file_location("mig_prod_deout", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def old_db(tmp_path):
    """构造含 outsourcer_id 遗留列的模拟旧库"""
    db_path = tmp_path / "old_erp.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(OLD_DDL)
    conn.commit()
    conn.close()
    return db_path


def _cols(db_path, table):
    conn = sqlite3.connect(str(db_path))
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    finally:
        conn.close()


def test_migrate_drops_outsourcer_id_column(old_db):
    """旧库 mo_production_process 含 outsourcer_id → 迁移后物理删除该列"""
    assert "outsourcer_id" in _cols(old_db, "mo_production_process")
    changed = _load_migrate().migrate(old_db)
    assert changed is True
    cols = _cols(old_db, "mo_production_process")
    assert "outsourcer_id" not in cols, f"outsourcer_id 列未删除: {cols}"


def test_migrate_preserves_existing_data(old_db):
    """迁移重建表后，其余列数据完整保留（不丢失）"""
    _load_migrate().migrate(old_db)
    conn = sqlite3.connect(str(old_db))
    try:
        rows = conn.execute(
            "SELECT id, production_id, process_id, seq, status FROM mo_production_process ORDER BY id").fetchall()
        assert rows == [(1, 1, 501, 1, '已完工'), (2, 1, 502, 2, '待排产')], f"数据丢失/错误: {rows}"
        # 关联表 mo_production 不受影响
        prods = conn.execute("SELECT * FROM mo_production").fetchall()
        assert prods == [(1, 'MO-20260731-001', 101, 10, '已排产')]
    finally:
        conn.close()


def test_migrate_idempotent(old_db):
    """幂等：第二次执行跳过，不再改库"""
    mig = _load_migrate()
    assert mig.migrate(old_db) is True
    assert mig.migrate(old_db) is False  # 第二次 changed=False
    # 列仍无 outsourcer_id
    assert "outsourcer_id" not in _cols(old_db, "mo_production_process")


def test_migrate_empty_db_safe(tmp_path):
    """空库 / 新结构（表不存在）安全跳过，不报错"""
    # 场景1：无表（完全空库）
    db1 = tmp_path / "empty.db"
    sqlite3.connect(str(db1)).close()
    assert _load_migrate().migrate(db1) is False

    # 场景2：有 mo_production 但无 mo_production_process
    db2 = tmp_path / "partial.db"
    conn = sqlite3.connect(str(db2))
    conn.execute("CREATE TABLE mo_production (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    assert _load_migrate().migrate(db2) is False
