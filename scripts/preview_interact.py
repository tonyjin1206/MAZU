"""针对当前开发服务的交互测试：检查页面渲染内容 + 核心业务操作。"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUT = Path("/tmp/erp_interact")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: print("PAGEERROR:", e))

        pg.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)
        pg.fill("input[placeholder='用户名']", "admin")
        pg.fill("input[placeholder='密码']", "admin123")
        pg.click("button:has-text('登 录')")
        pg.wait_for_url("**/dashboard", timeout=15000)
        pg.wait_for_timeout(1000)

        # 1. Dashboard 统计卡片
        cards = pg.locator(".el-card").all_inner_texts()
        print("=== Dashboard 卡片 ===")
        for c in cards[:8]:
            print(repr(c.strip()[:200]))

        # 2. 关键业务页面渲染文本
        pages = {
            "/purchase/orders": "采购订单",
            "/sales/orders": "销售订单",
            "/foundation/customers": "客户",
            "/foundation/suppliers": "供应商",
            "/inventory/management": "库存",
            "/system/reminders": "提醒",
        }
        for path, label in pages.items():
            pg.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=30000)
            pg.wait_for_timeout(600)
            body = pg.locator(".app-container, .el-main, main").first.inner_text() if pg.locator(
                ".app-container, .el-main, main").count() else pg.locator("body").inner_text()
            print(f"\n=== {label} ({path}) 页面文本前 500 字 ===")
            print(body.strip()[:500].replace("\n", " | "))

            # 检查空状态
            empty = pg.locator(".el-empty, .el-table__empty-text, .el-table__empty-block")
            if empty.count():
                print(f"[空状态] {empty.first.inner_text().strip()[:80]}")

        # 3. 销售订单页面按钮可用性
        pg.goto(f"{BASE_URL}/sales/orders", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(600)
        btns = pg.locator("button").all_inner_texts()
        print("\n=== 销售订单页按钮 ===")
        print([b.strip() for b in btns if b.strip()][:20])

        # 4. 表格行数
        rows = pg.locator(".el-table__body-wrapper tbody tr").count()
        print(f"销售订单表格行数: {rows}")

        browser.close()


if __name__ == "__main__":
    main()
