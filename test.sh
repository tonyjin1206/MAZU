#!/bin/bash
# MTS 统一测试入口 — 自动清除 PYTHONPATH（避免 Hermes 终端污染导入），跑后端测试
# 用法:
#   ./test.sh                     # 全量后端测试
#   ./test.sh -k 退货              # 按关键字分段（例：只跑退货相关测试）
#   ./test.sh tests/test_sales_return_red.py   # 指定测试文件
#   ./test.sh tests/test_sales_return_red.py::TestSalesReturnRedReverse::test_scene1  # 指定单个用例
# Windows 可双击 test.bat
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR/backend"

# 平台自适应 venv 路径（macOS/Linux: bin/，Windows: Scripts/）
if [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
elif [ -x "venv/Scripts/python.exe" ]; then
  PY="venv/Scripts/python.exe"
else
  echo "❌ 未找到 venv（backend/venv/bin/python 或 venv/Scripts/python.exe）" >&2
  exit 1
fi

exec env -u PYTHONPATH ERP_DEV=1 "$PY" -m pytest tests/ -q "$@"
