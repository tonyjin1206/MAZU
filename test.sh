#!/bin/bash
# MTS 统一测试入口 — 自动清除 PYTHONPATH（避免 Hermes 终端污染导入），跑后端测试
# 用法:
#   ./test.sh                     # 全量后端测试
#   ./test.sh -k 关键字            # 按关键字分段
#   ./test.sh tests/test_xxx.py   # 指定测试文件
#   ./test.sh tests/test_xxx.py::TestXxx::test_y  # 指定单个用例
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

# 隔离测试库：每次全新建临时库（避免复用陈旧/含数据的 backend/data/erp.db，破坏性小）
TEST_DATA_DIR="$(mktemp -d /tmp/mts-test-XXXXXX)"
trap 'rm -rf "$TEST_DATA_DIR"' EXIT

exec env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u PYTHONPATH ERP_DEV=1 ERP_DATA_DIR="$TEST_DATA_DIR" "$PY" -m pytest tests/ -q "$@"
