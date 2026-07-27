#!/usr/bin/env python3
"""
LTMP (Lightweight Trade Management Platform) — 后端入口
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
        log_level="info",
    )
