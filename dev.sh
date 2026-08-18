#!/bin/bash
# MTS 后端开发启动 — 自动清除 PYTHONPATH，ERP_DEV=1（uvicorn 热重载）
# 用法: ./dev.sh    Ctrl+C 停止
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR/backend"
exec env -u PYTHONPATH ERP_DEV=1 venv/Scripts/python.exe run.py
