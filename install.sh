#!/bin/bash
# Mazu Trade System (MTS) — 全自动安装脚本
# 自动检测并安装 Python、Node.js、项目依赖，一键部署
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_REQUIRED="3.10"
NODE_REQUIRED="18"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       MTS — 一键安装                          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ==================== 检测 Homebrew ====================
install_homebrew_if_needed() {
  if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}🔧 正在安装 Homebrew（macOS 包管理器）...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
      echo -e "${RED}❌ Homebrew 安装失败，请手动安装后重试${NC}"
      echo "   安装命令: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
      exit 1
    }
    echo -e "${GREEN}✅ Homebrew 安装完成${NC}"
  else
    echo -e "  ✅ Homebrew 已安装"
  fi
}

# ==================== Python ====================
check_python() {
  local found=false
  local version=""

  # 尝试 python3
  if command -v python3 &> /dev/null; then
    version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [ "$(echo -e "$version\n$PYTHON_REQUIRED" | sort -V | tail -1)" = "$version" ]; then
      found=true
      echo -e "  ✅ Python ${version} 已安装"
    fi
  fi

  if [ "$found" = false ]; then
    echo -e "${YELLOW}🔧 正在安装 Python ${PYTHON_REQUIRED}+...${NC}"
    install_homebrew_if_needed
    brew install python@3.11
    # 添加到 PATH
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
    if command -v python3 &> /dev/null; then
      echo -e "${GREEN}✅ Python $(python3 --version | cut -d' ' -f2) 安装完成${NC}"
    else
      echo -e "${RED}❌ Python 安装失败，请手动安装 https://www.python.org/downloads/${NC}"
      exit 1
    fi
  fi
}

# ==================== Node.js ====================
check_node() {
  if command -v node &> /dev/null; then
    local version=$(node --version | grep -oE '[0-9]+' | head -1)
    if [ "$version" -ge "$NODE_REQUIRED" ] 2>/dev/null; then
      echo -e "  ✅ Node.js $(node --version | cut -d'v' -f2) 已安装"
      return
    fi
  fi

  echo -e "${YELLOW}🔧 正在安装 Node.js ${NODE_REQUIRED}+...${NC}"
  install_homebrew_if_needed
  brew install node
  echo -e "${GREEN}✅ Node.js $(node --version | cut -d'v' -f2) 安装完成${NC}"
}

# ==================== 安装 ====================
install_deps() {
  echo ""
  echo -e "${CYAN}📦 第一步：安装系统依赖${NC}"
  check_python
  check_node

  echo ""
  echo -e "${CYAN}📦 第二步：安装后端依赖${NC}"
  cd "$ROOT_DIR/backend"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  source venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  echo -e "  ✅ 后端依赖安装完成"

  echo ""
  echo -e "${CYAN}📦 第三步：安装前端依赖${NC}"
  cd "$ROOT_DIR/frontend"
  if [ ! -d "node_modules" ]; then
    npm install --silent
  else
    npm install --silent
  fi
  echo -e "  ✅ 前端依赖安装完成"

  echo ""
  echo -e "${CYAN}🔨 第四步：构建前端${NC}"
  cd "$ROOT_DIR/frontend"
  npm run build --silent 2>/dev/null
  echo -e "  ✅ 前端构建完成"
}

# ==================== 启动 ====================
start_services() {
  echo ""
  echo -e "${CYAN}🚀 第五步：启动服务${NC}"

  # 启动后端
  cd "$ROOT_DIR/backend"
  source venv/bin/activate
  python3 run.py &
  BACKEND_PID=$!
  sleep 3

  # 启动前端（开发模式）
  cd "$ROOT_DIR/frontend"
  npx vite --host 0.0.0.0 &
  FRONTEND_PID=$!

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  ✅ 安装完成！系统已启动！                       ║${NC}"
  echo -e "${GREEN}║                                                ║${NC}"
  echo -e "║  前端地址: ${CYAN}http://localhost:5173${GREEN}              ║"
  echo -e "║  后端地址: ${CYAN}http://localhost:8788${GREEN}              ║"
  echo -e "║  默认账户: ${YELLOW}admin / admin123${GREEN}                 ║"
  echo -e "${GREEN}║                                                ║${NC}"
  echo -e "║  按 ${YELLOW}Ctrl+C${GREEN} 停止所有服务                      ║"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"

  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo -e '\n${YELLOW}服务已停止${NC}'; exit 0" INT TERM
  wait
}

# ==================== 主流程 ====================
install_deps
start_services
