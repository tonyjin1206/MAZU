#!/bin/bash
# LTMP macOS 打包脚本
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
ELECTRON_DIR="$PROJECT_DIR/electron"

echo "=============================="
echo "   LTMP macOS 打包"
echo "=============================="

# Step 1: 构建前端
echo ""
echo "[1/4] 构建前端..."
cd "$PROJECT_DIR/frontend"
npm run build

# Step 2: 复制前端到 backend/frontend_dist
echo ""
echo "[2/4] 复制前端产物..."
rm -rf "$BACKEND_DIR/frontend_dist"
mkdir -p "$BACKEND_DIR/frontend_dist"
cp -r "$PROJECT_DIR/frontend/dist/"* "$BACKEND_DIR/frontend_dist/"

# Step 3: PyInstaller 打包后端
echo ""
echo "[3/4] 打包后端..."
cd "$BACKEND_DIR"
source venv/bin/activate
pip install pyinstaller -q
pyinstaller --onefile \
  --name server \
  --distpath run_dist \
  --add-data "frontend_dist:frontend_dist" \
  --add-data "data:../data_template" \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  run.py
# 去掉 .spec 文件
rm -f server.spec

# Step 4: Electron 打包
echo ""
echo "[4/4] 打包 Electron 应用..."
cd "$ELECTRON_DIR"
npm install
npx electron-builder --mac

echo ""
echo "=============================="
echo "  打包完成！"
echo "  安装包在: $ELECTRON_DIR/dist/"
echo "=============================="
