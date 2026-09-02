"""针对当前开发服务（5173/8788）的前端预览测试。

登录 admin → 遍历全部业务页面 → 收集 console/page/http 错误 → 截图。
用法: backend/venv/bin/python scripts/preview_test.py
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
SHOT_DIR = Path("/tmp/erp_preview")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    "/dashboard",
    "/foundation/materials",
    "/foundation/products",
    "/foundation/bom",
    "/foundation/customers",
    "/foundation/suppliers",
    "/foundation/hs-codes",
    "/foundation/processes",
    "/foundation/warehouses",
    "/foundation/currencies",
    "/purchase/requisitions",
    "/purchase/orders",
    "/purchase/receipts",
    "/purchase/invoices",
    "/purchase/ap",
    "/purchase/payments",
    "/sales/orders",
    "/sales/deliveries",
    "/sales/invoices",
    "/sales/customs",
    "/sales/ar",
    "/sales/collections",
    "/inventory/management",
    "/inventory/batch-trace",
    "/tax-refund/declarations",
    "/system/users",
    "/system/roles",
    "/system/wecom",
    "/system/bot",
    "/system/bot-chat",
    "/system/reminders",
]

NOISE = [
    "[vite] connected.",
    "[vite] hot updated",
    "[vite] hmr update",
    "[vite] page reload",
    "optimized dependencies changed",
    "Vue Devtools extension",
    "devtools detection",
    "favicon",
]


def is_noise(text: str) -> bool:
    lowered = text.lower()
    return any(p.lower() in lowered for p in NOISE)


def main():
    report = {"console": [], "page": [], "http": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        pg = ctx.new_page()

        def on_console(msg):
            if msg.type == "error" and not is_noise(msg.text):
                report["console"].append(msg.text)

        def on_pageerror(exc):
            report["page"].append(str(exc))

        def on_response(resp):
            if resp.status >= 400 and not is_noise(resp.url):
                report["http"].append(f"{resp.status} {resp.request.method} {resp.url}")

        pg.on("console", on_console)
        pg.on("pageerror", on_pageerror)
        pg.on("response", on_response)

        # 登录
        pg.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)
        pg.fill("input[placeholder='用户名']", "admin")
        pg.fill("input[placeholder='密码']", "admin123")
        pg.click("button:has-text('登 录')")
        pg.wait_for_url("**/dashboard", timeout=15000)
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(SHOT_DIR / "00_dashboard.png"))

        # 遍历页面
        for path in PAGES:
            name = path.strip("/").replace("/", "_")
            try:
                pg.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=30000)
                pg.wait_for_timeout(500)
                pg.screenshot(path=str(SHOT_DIR / f"{name}.png"))
                print(f"OK  {path}")
            except Exception as e:
                print(f"ERR {path}: {e}")
                report["page"].append(f"{path}: {e}")

        # 侧边栏菜单遍历（验证菜单渲染）
        pg.goto(f"{BASE_URL}/dashboard", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(800)
        menu_texts = pg.locator(".el-menu-item, .el-sub-menu__title").all_inner_texts()
        print("\n=== 侧边栏菜单 ===")
        for t in menu_texts:
            t = t.strip().replace("\n", " ")
            if t:
                print(" ", t)

        pg.screenshot(path=str(SHOT_DIR / "99_sidebar.png"))
        browser.close()

    print("\n=== 错误汇总 ===")
    print("console 错误:", len(report["console"]))
    for e in report["console"]:
        print("  ", e[:300])
    print("page 错误:", len(report["page"]))
    for e in report["page"]:
        print("  ", e[:300])
    print("http 错误:", len(report["http"]))
    for e in report["http"]:
        print("  ", e[:300])

    (SHOT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    failed = bool(report["console"] or report["page"] or report["http"])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
