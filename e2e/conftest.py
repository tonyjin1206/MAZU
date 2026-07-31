"""E2E fixtures：独立后端（临时测试库）+ 前端 dev server + Playwright 浏览器

架构：
- 后端：uvicorn run:app --port 8789，ERP_DATA_DIR=临时目录（不污染开发库）
- 前端：vite dev --port 5174 --strictPort，VITE_PROXY_TARGET 指向 8789
- 浏览器：Chromium headless，收集 console/page/网络 三类错误
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO / "backend"
FRONTEND_DIR = REPO / "frontend"

BACKEND_PORT = 8789  # 避开开发端口 8788
FRONTEND_PORT = 5174  # 避开开发端口 5173
BASE_URL = f"http://localhost:{FRONTEND_PORT}"
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"


def _wait_http(url: str, timeout: int = 90) -> bool:
    """轮询 HTTP 就绪。vite 只监听 IPv6 [::1]，localhost 解析失败时自动尝试 [::1]"""
    candidates = [url]
    if "localhost" in url:
        candidates.append(url.replace("localhost", "[::1]"))
    deadline = time.time() + timeout
    while time.time() < deadline:
        for u in candidates:
            try:
                urllib.request.urlopen(u, timeout=2)
                return True
            except Exception:
                continue
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def services():
    """启动独立后端 + 前端，测试结束关闭并清理临时库（启动失败也清理）"""
    data_dir = tempfile.mkdtemp(prefix="erp_e2e_")
    backend_env = {**os.environ, "ERP_DATA_DIR": data_dir}
    frontend_env = {**os.environ, "VITE_PROXY_TARGET": BACKEND_URL}
    backend = frontend = None
    try:
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "run:app",
             "--port", str(BACKEND_PORT), "--log-level", "warning"],
            cwd=BACKEND_DIR, env=backend_env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        assert _wait_http(f"{BACKEND_URL}/docs", 120), "后端启动超时"

        frontend = subprocess.Popen(
            ["node", "node_modules/vite/bin/vite.js", "--port", str(FRONTEND_PORT), "--strictPort"],
            cwd=FRONTEND_DIR, env=frontend_env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        assert _wait_http(BASE_URL, 120), "前端启动超时"

        yield {"base": BASE_URL, "backend": BACKEND_URL}
    finally:
        for proc in (frontend, backend):
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    pass
                finally:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    """每个测试独立页面 + 错误收集器"""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    pg = ctx.new_page()
    errors = {"console": [], "page": [], "http": []}

    def on_console(msg):
        if msg.type == "error":
            errors["console"].append(msg.text)

    def on_pageerror(exc):
        errors["page"].append(str(exc))

    def on_response(resp):
        if resp.status >= 400:
            errors["http"].append(f"{resp.status} {resp.request.method} {resp.url}")

    pg.on("console", on_console)
    pg.on("pageerror", on_pageerror)
    pg.on("response", on_response)
    pg.errors = errors
    yield pg
    ctx.close()


@pytest.fixture()
def logged_in(page, services):
    """登录 admin（E2E 独立库，admin/admin123 种子）"""
    page.goto(f"{services['base']}/login", wait_until="networkidle")
    page.fill("input[placeholder='用户名']", "admin")
    page.fill("input[placeholder='密码']", "admin123")
    page.click("button:has-text('登 录')")
    page.wait_for_url("**/dashboard", timeout=15000)
    page.wait_for_timeout(500)
    return page
