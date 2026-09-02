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
    port = int(os.environ.get("PORT", "8788"))

    if getattr(sys, "frozen", False):
        # PyInstaller 打包版：直接传 app 对象（导入字符串在冻结环境不可用），
        # 只绑本机回环（由桌面壳窗口访问，不对外暴露）
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    else:
        uvicorn.run(
            "run:app",
            host="0.0.0.0",
            port=port,
            reload=not is_production,
            log_level="info",
        )
