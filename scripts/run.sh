#!/bin/bash
# Mazu Trade System (MTS) 一键启动脚本
# 用法: sh run.sh [port]

PORT=${1:-8788}
DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$DIR/backend"

echo "========================================="
echo "   LTMP v1.0"
echo "  http://localhost:${PORT}"
echo "========================================="

cd "$BACKEND_DIR"

# 启动虚拟环境
if [ ! -d "venv" ]; then
    echo "首次运行：创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "✅ 后端服务启动中..."
python3 run.py
