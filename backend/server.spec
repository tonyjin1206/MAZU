# -*- mode: python ; coding: utf-8 -*-
# MTS 后端打包配置（PyInstaller onefile）
# 用法: cd backend && venv/bin/python -m PyInstaller --noconfirm --distpath run_dist server.spec
# 注意: 绝不打包 backend/data/（用户真实业务数据）——应用首次启动会在
#       用户数据目录自动建库 + 种子（init_db + _seed_rbac）
import sys

IS_WINDOWS = sys.platform.startswith("win")

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend_dist', 'frontend_dist')],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.lifespan.on',
        'passlib.handlers.bcrypt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Windows 发布版不弹黑色控制台窗口（macOS 保持控制台便于排查，
    # 且作为 Electron 子进程启动时本身不可见）
    console=not IS_WINDOWS,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
