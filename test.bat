@echo off
chcp 65001 >nul
title MTS Tests
rem 自动清除 PYTHONPATH（避免 Hermes 终端污染导入），跑后端测试
rem 用法: test.bat [pytest 参数...]   例: test.bat -k 汇率
cd /d "%~dp0backend"
set PYTHONPATH=
set ERP_DEV=1
venv\Scripts\python.exe -m pytest tests/ -q %*
