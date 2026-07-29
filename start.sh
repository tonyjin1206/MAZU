#!/bin/bash
# Mazu Trade System (MTS) — 启动脚本（依赖已安装时使用）
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 启动 ERP 系统..."

# 启动后端
cd "$ROOT_DIR/backend"
source venv/bin/activate 2>/dev/null || {
  echo "❌ 未检测到虚拟环境，请先运行 ./install.sh"
  exit 1
}
python3 run.py &
BACKEND_PID=$!
sleep 3

# 启动前端
cd "$ROOT_DIR/frontend"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "✅ 系统已启动！"
echo "  前端: http://localhost:5173"
echo "  后端: http://localhost:8788"
echo "  账户: admin / admin123"
echo ""
echo "按 Ctrl+C 停止服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '服务已停止'; exit 0" INT TERM
wait
