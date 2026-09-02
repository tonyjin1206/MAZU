"""E2E 冒烟测试：所有页面打开无 console/页面/网络错误

用户目标：自动化测试完成后，浏览器人工操作基本不报错——
本套件逐个打开全部业务页面，任何 JS 报错、4xx/5xx 请求都会被捕获。
"""

import pytest

# 登录后可访问的所有页面（router/index.js 业务路由）
PAGES = [
    "/dashboard",
    # 基础档案
    "/foundation/materials",
    "/foundation/products",
    "/foundation/bom",
    "/foundation/customers",
    "/foundation/suppliers",
    "/foundation/hs-codes",
    "/foundation/processes",
    "/foundation/warehouses",
    "/foundation/currencies",
    # 采购
    "/purchase/requisitions",
    "/purchase/orders",
    "/purchase/receipts",
    "/purchase/invoices",
    "/purchase/ap",
    "/purchase/payments",
    # 销售
    "/sales/orders",
    "/sales/deliveries",
    "/sales/invoices",
    "/sales/customs",
    "/sales/ar",
    "/sales/collections",
    # 生产管理已下线（2026-09）；批次追溯挪至库存管理
    # 库存
    "/inventory/management",
    "/inventory/batch-trace",
    # 退税
    "/tax-refund/declarations",
    # 系统
    "/system/users",
    "/system/roles",
    "/system/wecom",
    "/system/bot",
    "/system/bot-chat",
    "/system/reminders",
]


@pytest.mark.parametrize("path", PAGES)
def test_page_opens_clean(logged_in, path):
    """页面打开：0 console 错误、0 页面异常、0 4xx/5xx 请求"""
    logged_in.goto(f"http://localhost:5174{path}", wait_until="networkidle", timeout=30000)
    logged_in.wait_for_timeout(600)  # 等异步请求收尾

    errs = logged_in.errors
    problems = []
    if errs["console"]:
        problems.append(f"console: {errs['console']}")
    if errs["page"]:
        problems.append(f"pageerror: {errs['page']}")
    if errs["http"]:
        problems.append(f"http: {errs['http']}")
    assert not problems, f"{path} 页面存在错误:\n" + "\n".join(problems)


def test_login_page(browser, services):
    """登录页可达（浏览器 fixture 复用，避免 sync API 嵌套）"""
    pg = browser.new_page()
    pg.goto(f"{services['base']}/login", wait_until="networkidle")
    assert pg.locator("input[placeholder='用户名']").count() == 1
    assert pg.locator("input[placeholder='密码']").count() == 1
    pg.close()
