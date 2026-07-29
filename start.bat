@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title MTS

echo =========================================
echo   MTS - Mazu Trade System
echo =========================================
echo.

:: Detect Python (try multiple methods)
set PYTHON=
:: 1. Try py launcher (Windows Python Launcher)
py --version >nul 2>&1
if not errorlevel 1 set PYTHON=py

:: 2. Try python
if "%PYTHON%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON=python
)

:: 3. Try common install locations
if "%PYTHON%"=="" (
    if exist "C:\Python311\python.exe" set PYTHON=C:\Python311\python.exe
)
if "%PYTHON%"=="" (
    if exist "C:\Program Files\Python311\python.exe" set PYTHON=C:\Program Files\Python311\python.exe
)
if "%PYTHON%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
)
if "%PYTHON%"=="" (
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe
)

:: 4. Try Hermes agent venv (user's known setup)
if "%PYTHON%"=="" (
    if exist "%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
)

if "%PYTHON%"=="" (
    echo [FAIL] Python not found after trying all locations.
    echo.
    echo        Install Python 3.10+ from:
    echo        https://www.python.org/downloads/
    echo.
    echo        Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('%PYTHON% --version 2^>^&1') do set pyver=%%i
echo [OK] Python %pyver% (using: %PYTHON%)

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Node.js not found. Install Node.js 18+ from:
    echo        https://nodejs.org/
    pause
    exit /b 1
)

:: Backend venv
if not exist "backend\venv\Scripts\python.exe" (
    echo.
    echo [1/3] Creating virtual environment...
    %PYTHON% -m venv backend\venv
)
echo [1/3] Installing backend dependencies...
backend\venv\Scripts\python -m pip install -r backend\requirements.txt -q
echo   [OK] Backend ready

:: Frontend deps
if not exist "frontend\node_modules" (
    echo.
    echo [2/3] Installing frontend dependencies...
    pushd frontend
    call npm install
    popd
) else (
    echo [2/3] Frontend dependencies already installed
)

:: Reset DB
echo.
echo [3/3] Resetting database...
if exist "backend\data\erp.db" del "backend\data\erp.db"
if exist "backend\data\erp.db-wal" del "backend\data\erp.db-wal"
if exist "backend\data\erp.db-shm" del "backend\data\erp.db-shm"
echo   [OK] Database reset

:: Start backend
echo.
echo =========================================
echo   Starting services...
echo =========================================
echo.
echo Starting backend (port 8788)...
start "" /B backend\venv\Scripts\python backend\run.py >nul 2>&1

:: Wait for backend
set retries=0
:wait_loop
set /a retries+=1
if !retries! gtr 30 (
    echo [FAIL] Backend did not start in time
    pause
    exit /b 1
)
>nul 2>&1 curl -s http://127.0.0.1:8788/api/health && goto backend_ok
timeout /t 1 /nobreak >nul
goto wait_loop

:backend_ok
echo   [OK] Backend ready

:: Start frontend
echo Starting frontend (port 5173)...
start "" /B cmd /c "cd /d %cd%\frontend && npm run dev" >nul 2>&1
echo   [OK] Frontend started

echo.
echo =========================================
echo   System is running!
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8788
echo   Account:  admin / admin123
echo.
echo   Close this window to stop all services.
echo =========================================
echo.
pause
