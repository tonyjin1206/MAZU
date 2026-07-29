@echo off
chcp 65001 >nul
title MTS — Mazu Trade System
cd /d "%~dp0"

echo =========================================
echo   MTS — Mazu Trade System
echo =========================================
echo.

:: 检测 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 未找到，请安装 Python 3.10+
    echo    下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检测 Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js 未找到，请安装 Node.js 18+
    echo    下载: https://nodejs.org/
    pause
    exit /b 1
)

:: 后端虚环境
if not exist "backend\venv\Scripts\python.exe" (
    echo [1/3] 创建后端虚环境...
    python -m venv backend\venv
)
echo [1/3] 安装后端依赖...
backend\venv\Scripts\python -m pip install -r backend\requirements.txt -q
echo   ✅ 后端依赖安装完成

:: 前端依赖
if not exist "frontend\node_modules" (
    echo [2/3] 安装前端依赖...
    cd frontend
    call npm install --silent
    cd ..
) else (
    echo [2/3] 前端依赖已存在
)
echo   ✅ 前端依赖就绪

:: 重置数据库
if exist "backend\data\erp.db" (
    echo [3/3] 清理旧数据库...
    del /q "backend\data\erp.db" 2>nul
    del /q "backend\data\erp.db-wal" 2>nul
    del /q "backend\data\erp.db-shm" 2>nul
)
echo   ✅ 数据库已重置

echo.
echo =========================================
echo   🚀 启动服务...
echo =========================================
echo.

:: 启动后端（新窗口）
start "MTS-Backend" /B backend\venv\Scripts\python backend\run.py

:: 等后端就绪
echo 等待后端就绪......
:wait_backend
timeout /t 1 /nobreak >nul
>nul 2>&1 curl -s http://127.0.0.1:8788/api/health && goto backend_ready
goto wait_backend
:backend_ready
echo   ✅ 后端已就绪 (端口 8788)

:: 启动前端（新窗口）
start "MTS-Frontend" /B cmd /c "cd frontend && npm run dev"

echo   ✅ 前端已启动 (端口 5173)
echo.
echo =========================================
echo   系统启动成功！
echo.
echo   前端: http://localhost:5173
echo   后端: http://localhost:8788
echo   账户: admin / admin123
echo.
echo   关闭所有窗口即可停止服务
echo =========================================

:: 保持窗口打开
pause
