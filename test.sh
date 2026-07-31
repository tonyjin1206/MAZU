#!/bin/bash
# MTS 测试脚本 — 自动清除 PYTHONPATH（避免 Hermes 终端污染导入），跑后端测试
# 用法: ./test.sh [pytest 参数...]  例: ./test.sh -k 汇率
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR/backend"
exec env -u PYTHONPATH ERP_DEV=1 venv/Scripts/python.exe -m pytest tests/ -q "$@"
