# -*- coding: utf-8 -*-
"""收款单/付款单审核字段迁移（幂等）：
ar_collection + ap_payment 加 reviewed/reviewed_by/reviewed_at"""
import sqlite3
import os
import sys

DB = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "erp.db")
DB = os.path.abspath(DB)

if not os.path.exists(DB):
    print(f"DB not found: {DB}")
    sys.exit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()

for table in ["ar_collection", "ap_payment"]:
    cols = {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    added = []
    for name, ddl in [
        ("reviewed", f"ALTER TABLE {table} ADD COLUMN reviewed INTEGER DEFAULT 0"),
        ("reviewed_by", f"ALTER TABLE {table} ADD COLUMN reviewed_by VARCHAR(32)"),
        ("reviewed_at", f"ALTER TABLE {table} ADD COLUMN reviewed_at DATETIME"),
    ]:
        if name not in cols:
            cur.execute(ddl)
            added.append(name)
    print(f"{table}: added {added if added else '无（已存在）'}")
conn.commit()
conn.close()
