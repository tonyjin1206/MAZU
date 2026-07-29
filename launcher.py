#!/usr/bin/env python3
"""
LTMP 跨平台启动器
==================
统一管理 macOS / Windows 上的安装、启动、重置数据库。

用法:
    python launcher.py          # 安装依赖 + 启动服务
    python launcher.py start    # 仅启动服务
    python launcher.py install  # 仅安装依赖
    python launcher.py reset-db # 重置数据库（清空所有数据）
    python launcher.py --help   # 帮助
"""

import os
import sys
import platform
import subprocess
import time
import signal
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

# ==================== 平台检测 ====================

IS_WINDOWS = platform.system() == "Windows"

def py() -> str:
    """获取 Python 可执行文件名"""
    return "python" if IS_WINDOWS else "python3"

def npm() -> str:
    """获取 npm 可执行文件名"""
    return "npm.cmd" if IS_WINDOWS else "npm"

def venv_python() -> Path:
    """虚拟环境中的 Python 路径"""
    if IS_WINDOWS:
        return BACKEND / "venv" / "Scripts" / "python.exe"
    return BACKEND / "venv" / "bin" / "python"

def venv_activate() -> str:
    """虚拟环境激活命令（给 shell 用）"""
    if IS_WINDOWS:
        return str(BACKEND / "venv" / "Scripts" / "activate")
    return f"source {BACKEND / 'venv' / 'bin' / 'activate'}"

# ==================== 颜色输出 ====================

def green(text): return f"\033[92m{text}\033[0m" if sys.stdout.isatty() else text
def cyan(text):  return f"\033[96m{text}\033[0m" if sys.stdout.isatty() else text
def yellow(text):return f"\033[93m{text}\033[0m" if sys.stdout.isatty() else text
def red(text):   return f"\033[91m{text}\033[0m" if sys.stdout.isatty() else text


# ==================== 命令 ====================

def cmd_run(args, cwd=None, capture=False, **kwargs):
    """运行命令并实时输出"""
    print(f"  $ {' '.join(args)}")
    return subprocess.run(args, cwd=cwd or str(ROOT), **kwargs)


def check_dependencies():
    """检查 Python 和 Node.js 是否可用"""
    missing = []

    # Python
    try:
        result = subprocess.run([py(), "--version"], capture_output=True, text=True)
        ver = result.stdout.strip() or result.stderr.strip()
        print(f"  ✅ Python: {ver}")
    except FileNotFoundError:
        print(f"  {red('❌')} Python 未找到，请安装 Python 3.10+")
        missing.append("Python")

    # Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        ver = result.stdout.strip()
        print(f"  ✅ Node.js: {ver}")
    except FileNotFoundError:
        print(f"  {red('❌')} Node.js 未找到，请安装 Node.js 18+")
        missing.append("Node.js")

    if missing:
        print(f"\n{red('请先安装:')} {', '.join(missing)}")
        if IS_WINDOWS:
            print("  Python: https://www.python.org/downloads/")
            print("  Node:   https://nodejs.org/")
        else:
            print("  brew install python@3.11 node")
        sys.exit(1)


def install():
    """安装所有依赖"""
    print(f"\n{cyan('📦 LTMP — 安装依赖')}")
    print("=" * 50)

    check_dependencies()

    # 后端 venv
    print(f"\n{cyan('📦 后端依赖')}")
    venv_path = BACKEND / "venv"
    if not venv_path.exists():
        print(f"  创建虚拟环境...")
        cmd_run([py(), "-m", "venv", str(venv_path)], cwd=BACKEND)
    else:
        print(f"  虚拟环境已存在")

    print(f"  安装 pip 依赖...")
    pip = str(venv_python())
    cmd_run([pip, "-m", "pip", "install", "--upgrade", "pip", "-q"], cwd=BACKEND)
    cmd_run([pip, "-m", "pip", "install", "-r", "requirements.txt", "-q"], cwd=BACKEND)
    print(f"  {green('✅ 后端依赖安装完成')}")

    # 前端
    print(f"\n{cyan('📦 前端依赖')}")
    if not (FRONTEND / "node_modules").exists():
        cmd_run([npm(), "install", "--silent"], cwd=FRONTEND)
    else:
        cmd_run([npm(), "install", "--silent"], cwd=FRONTEND)
    print(f"  {green('✅ 前端依赖安装完成')}")

    print(f"\n{green('✅ 安装完成！')} 运行 {cyan('python launcher.py start')} 启动服务")


def start():
    """启动后端和前端"""
    print(f"\n{cyan('🚀 LTMP — 启动服务')}")
    print("=" * 50)

    # 检查依赖是否已安装
    if not venv_python().exists():
        print(f"  {yellow('⚠️  虚拟环境不存在，先运行 install')}")
        install()

    processes = []

    try:
        # 启动后端
        print(f"\n  {cyan('启动后端...')} (端口 8788)")
        backend_cmd = [str(venv_python()), "run.py"]
        if IS_WINDOWS:
            backend_proc = subprocess.Popen(
                backend_cmd, cwd=str(BACKEND),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            backend_proc = subprocess.Popen(
                backend_cmd, cwd=str(BACKEND),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
        processes.append(("backend", backend_proc))

        # 等待后端就绪
        print(f"  等待后端就绪", end="", flush=True)
        import http.client
        ready = False
        for _ in range(20):
            time.sleep(0.5)
            print(".", end="", flush=True)
            try:
                conn = http.client.HTTPConnection("127.0.0.1", 8788, timeout=2)
                conn.request("GET", "/api/health")
                resp = conn.getresponse()
                if resp.status == 200:
                    ready = True
                    break
            except:
                pass
        print()

        if not ready:
            # 显示后端日志
            output = backend_proc.stdout.read(1024).decode(errors="replace") if backend_proc.stdout else ""
            print(f"  {red('❌ 后端启动失败')}")
            print(f"  {output[:500]}")
            cleanup(processes)
            sys.exit(1)

        print(f"  {green('✅ 后端已就绪')}")

        # 启动前端（开发模式）
        print(f"\n  {cyan('启动前端...')} (端口 5173)")
        if IS_WINDOWS:
            frontend_proc = subprocess.Popen(
                [npm(), "run", "dev"], cwd=str(FRONTEND),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            frontend_proc = subprocess.Popen(
                [npm(), "run", "dev"], cwd=str(FRONTEND),
            )
        processes.append(("frontend", frontend_proc))

        print(f"\n{'=' * 50}")
        print(f"  {green('✅ 系统启动成功！')}")
        print(f"")
        print(f"  前端: {cyan('http://localhost:5173')}")
        print(f"  后端: {cyan('http://localhost:8788')}")
        print(f"  账户: {yellow('admin / admin123')}")
        print(f"")
        print(f"  按 {yellow('Ctrl+C')} 停止所有服务")
        print(f"{'=' * 50}")

        # 等待任一进程退出
        while all(p.poll() is None for _, p in processes):
            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n  {yellow('正在停止服务...')}")
    finally:
        cleanup(processes)


def reset_db():
    """重置数据库"""
    db_path = BACKEND / "data" / "erp.db"
    if db_path.exists():
        db_path.unlink()
        # 清理 WAL/SHM 文件
        for ext in [".db-wal", ".db-shm"]:
            p = db_path.with_suffix(ext)
            if p.exists():
                p.unlink()
        print(f"  {green('✅ 数据库已重置')}")
    else:
        print(f"  数据库不存在，无需重置")


def cleanup(processes):
    """停止所有子进程"""
    for name, proc in processes:
        if proc.poll() is None:
            print(f"  停止 {name}...")
            if IS_WINDOWS:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print(f"  {green('✅ 服务已停止')}")


# ==================== CLI ====================

def print_help():
    print(f"""
{cyan('LTMP 跨平台启动器')}
{'=' * 40}

用法:
    python launcher.py             安装 + 启动
    python launcher.py start       仅启动服务
    python launcher.py install     仅安装依赖
    python launcher.py reset-db    重置数据库
    python launcher.py --help      帮助
""")


def main():
    if len(sys.argv) == 1:
        install()
        start()
    elif sys.argv[1] in ("start",):
        start()
    elif sys.argv[1] in ("install",):
        install()
    elif sys.argv[1] in ("reset-db", "reset_db"):
        reset_db()
    else:
        print_help()


if __name__ == "__main__":
    main()
