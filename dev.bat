@echo off
chcp 65001 >nul
title MTS Backend Dev
rem 自动清除 PYTHONPATH，ERP_DEV=1（uvicorn 热重载），Ctrl+C 停止
cd /d "%~dp0backend"
set PYTHONPATH=
set ERP_DEV=1
venv\Scripts\python.exe run.py
