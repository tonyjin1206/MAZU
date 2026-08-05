#!/usr/bin/env python3
"""
MTS (Mazu Trade System) — 后端入口
FastAPI + SQLAlchemy + SQLite
"""
from pathlib import Path
import sys

# Ensure backend package is importable
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import uvicorn
from app.main import create_app

app = create_app()

if __name__ == "__main__":
    import os
    is_production = not os.environ.get("ERP_DEV")
    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=8788,
        reload=not is_production,
        # dev 排除 DB/缓存文件，避免每次写库（SQLite wal）触发全量 reload
        reload_excludes=["data/*", "*.db", "*.db-wal", "*.db-shm", ".pytest_cache/*"] if not is_production else None,
        log_level="info",
    )
