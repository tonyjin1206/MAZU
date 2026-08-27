#!/usr/bin/env python3
"""
SP 移植线批 2 财务模块数据库迁移：发票红冲 / 红字应收 / 退款 / 核销转移 / 负数申报
用法: python scripts/migrate_batch2_finance.py [数据库路径，默认 backend/data/erp.db]

包含：
1. so_invoice 加 is_red / red_of_invoice_id（红冲标记 + 被红冲的原发票）
2. ar_account 加 is_red / red_of_ar_id（红字应收标记 + 被冲销的原应收）
3. so_delivery 加 refund_declared（退款已申报标记）
4. 新建 ar_adjustment（核销转移 / 调整明细表）
幂等：已存在的列/表自动跳过，可重复执行。
"""
import sqlite3
import sys
from pathlib import Path

# 加列清单：(表名, 列名, 列定义)
ALTERS = [
    ("so_invoice", "is_red", "INTEGER DEFAULT 0"),
    ("so_invoice", "red_of_invoice_id", "INTEGER"),
    ("ar_account", "is_red", "INTEGER DEFAULT 0"),
    ("ar_account", "red_of_ar_id", "INTEGER"),
    ("so_delivery", "refund_declared", "INTEGER DEFAULT 0"),
]

CREATE_AR_ADJUSTMENT = """
CREATE TABLE IF NOT EXISTS ar_adjustment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ar_id INTEGER NOT NULL,
    target_ar_id INTEGER NOT NULL,
    amount FLOAT DEFAULT 0,
    operator VARCHAR(32),
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_ar_id) REFERENCES ar_account(id),
    FOREIGN KEY (target_ar_id) REFERENCES ar_account(id)
)
"""


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "backend/data/erp.db"
    if not Path(db).exists():
        print(f"错误: 数据库文件不存在: {db}")
        sys.exit(1)

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    done = skipped = 0

    # ---- 1. 加列（幂等） ----
    for table, column, coldef in ALTERS:
        if column_exists(cur, table, column):
            print(f"[跳过] {table}.{column} 已存在")
            skipped += 1
        else:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
            print(f"[执行] ALTER TABLE {table} ADD COLUMN {column} {coldef}")
            done += 1

    # ---- 2. 建表（幂等 + 旧单字段版重建为双字段） ----
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ar_adjustment'")
    if cur.fetchone():
        # 检查是否为旧单字段结构（有 ar_id 列但无 source_ar_id）→ 重建为双字段
        cur.execute("PRAGMA table_info(ar_adjustment)")
        cols = [row[1] for row in cur.fetchall()]
        if "source_ar_id" not in cols:
            print("[重建] ar_adjustment 旧单字段结构 → 重建为双字段(source_ar_id/target_ar_id)")
            cur.execute("DROP TABLE ar_adjustment")
            cur.execute(CREATE_AR_ADJUSTMENT)
            done += 1
        else:
            print("[跳过] ar_adjustment 表已存在(双字段)")
            skipped += 1
    else:
        cur.execute(CREATE_AR_ADJUSTMENT)
        print("[执行] CREATE TABLE ar_adjustment")
        done += 1

    conn.commit()
    conn.close()
    print(f"\n完成: 执行 {done} 项, 跳过 {skipped} 项。")


if __name__ == "__main__":
    main()
