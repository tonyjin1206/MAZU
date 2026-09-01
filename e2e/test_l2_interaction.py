"""L2 前端交互级测试：行为断言 + 0 console/page/http 错误

覆盖（docs/complete-test-plan.md P2 要求）：
- 基础档案：产品/供应商 新增弹窗、表单校验文案、删除后列表刷新
- 销售：订单审核/删除确认框真的出现、金额 $fm 格式渲染（抓 script setup ReferenceError 静默坏）
- 采购：审核/取消审核状态流转
- 库存/提醒：页面加载 0 错误
- 横切：多页导航累计 0 错误、弹窗取消关闭

稳定化约定（P1 基建）：
- 每测独立数据：uuid 唯一名称；API 预置业务数据（避免复杂 UI 表单做 setup）
- 状态等待：wait_for_selector/wait_for 带超时，无固定长 sleep
- 每测开头清空错误收集器、结尾 assert_no_errors
"""

import uuid
from contextlib import contextmanager

import httpx
import pytest
from playwright.sync_api import expect
from helpers import (
    fill_creatable_select,
    fill_dialog_form,
    click_dialog_button,
    wait_for_message,
    wait_for_confirm_dialog,
    click_confirm_button,
    assert_no_errors,
)

BASE = "http://localhost:5174"


# ========== 工具函数 ==========

def _uniq(prefix: str) -> str:
    """唯一名称：前缀 + 8 位随机 hex（每测独立数据）"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _clear_errors(page):
    page.errors["console"].clear()
    page.errors["page"].clear()
    page.errors["http"].clear()


def _find_row(page, text):
    """按文本定位表格行（配合关键词搜索后只有一行命中）"""
    return page.locator(f"tr:has-text('{text}')").first


def _search_products(page, name):
    page.fill("input[placeholder='名称']", name)
    page.click("button:has-text('搜索')")


def _search_suppliers(page, name):
    page.fill("input[placeholder='名称']", name)
    page.click("button:has-text('查询')")


def _search_sales_orders(page, order_no):
    page.fill("input[placeholder='客户名称/订单号']", order_no)
    page.click("button:has-text('查询')")


def _search_purchase_orders(page, order_no):
    page.fill("input[placeholder='订单号/供应商']", order_no)
    page.click("button:has-text('查询')")


# ========== API 预置数据（幂等 + 唯一）==========

@contextmanager
def _api_client(services):
    base = services["backend"]
    c = httpx.Client(base_url=base, timeout=10)
    try:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        r.raise_for_status()
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield c
    finally:
        c.close()


def _ensure_currency(c) -> int:
    """CNY 币种存在则复用，否则创建（E2E 独立库仅种子 RBAC）"""
    items = c.get("/api/foundation/currencies", params={"page": 1, "page_size": 100}).json().get("items", [])
    for it in items:
        if it.get("code") == "CNY":
            return it["id"]
    r = c.post("/api/foundation/currencies", json={"code": "CNY", "name": "人民币", "symbol": "¥", "is_base": 1})
    r.raise_for_status()
    return r.json()["id"]


def _api_create_customer(c, name: str) -> int:
    r = c.post("/api/foundation/customers", json={"name_cn": name, "contact_person": "E2E"})
    r.raise_for_status()
    return r.json()["id"]


def _api_create_product(c, name: str) -> int:
    r = c.post("/api/foundation/products", json={
        "name_cn": name, "spec": "L2", "unit": "件", "sale_price": 100})
    r.raise_for_status()
    return r.json()["id"]


def _api_create_supplier(c, name: str) -> int:
    r = c.post("/api/foundation/suppliers", json={"name": name, "contact_person": "E2E"})
    r.raise_for_status()
    return r.json()["id"]


def _api_create_sales_order(c, customer_id, product_id, currency_id, quantity=100, unit_price=50) -> str:
    r = c.post("/api/sales/orders", json={
        "customer_id": customer_id,
        "currency_id": currency_id,
        "items": [{"product_id": product_id, "quantity": quantity, "unit_price": unit_price, "tax_rate": 13}],
    })
    r.raise_for_status()
    return r.json()["order_no"]


def _api_create_purchase_order(c, supplier_id, product_id, currency_id, quantity=10, unit_price=20) -> dict:
    r = c.post("/api/purchase/orders", json={
        "supplier_id": supplier_id,
        "currency_id": currency_id,
        "items": [{"product_id": product_id, "quantity": quantity, "unit_price": unit_price}],
    })
    r.raise_for_status()
    return r.json()


# ========== 基础档案交互 ==========

def test_foundation_product_create_shows_dialog(logged_in):
    """新增产品：点击新增 → 弹窗出现 → 填表保存 → 成功提示 → 弹窗关闭 → 列表刷新出现新行"""
    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/foundation/products", wait_until="networkidle")
    page.click("[data-testid='btn-create-product']")
    page.wait_for_selector("[data-testid='dialog-product']", state="visible", timeout=5000)

    pname = _uniq("E2E产品")
    fill_dialog_form(page, "品名（公司）", pname)
    fill_dialog_form(page, "规格", "L2标准")
    fill_creatable_select(page, "单位", "件")
    fill_dialog_form(page, "销售价", "100")

    page.click("[data-testid='btn-save']")
    wait_for_message(page, "success")
    # 保存成功后弹窗自动关闭
    page.wait_for_selector("[data-testid='dialog-product']", state="hidden", timeout=5000)
    # 列表已刷新：搜索能看到新行
    _search_products(page, pname)
    _find_row(page, pname).wait_for(state="visible", timeout=5000)
    assert_no_errors(page, "产品新增")


def test_foundation_product_delete_refreshes_list(logged_in, services):
    """删除产品：API 建数据 → UI 删除 → 确认框出现 → 确认 → 列表刷新行消失"""
    with _api_client(services) as c:
        _ensure_currency(c)
        pname = _uniq("E2E产品删除")
        _api_create_product(c, pname)

    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/foundation/products", wait_until="networkidle")
    _search_products(page, pname)
    row = _find_row(page, pname)
    row.wait_for(state="visible", timeout=5000)

    row.locator("button:has-text('删除')").click()
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    # 删除后列表刷新：行消失
    expect(row).to_have_count(0, timeout=5000)
    assert_no_errors(page, "产品删除")


def test_foundation_product_form_validation(logged_in):
    """表单校验：空表单点保存 → 必填错误文案出现、弹窗保持打开"""
    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/foundation/products", wait_until="networkidle")
    page.click("[data-testid='btn-create-product']")
    page.wait_for_selector("[data-testid='dialog-product']", state="visible", timeout=5000)

    page.click("[data-testid='btn-save']")
    page.locator(".el-form-item__error:has-text('请输入品名（公司）')").wait_for(state="visible", timeout=5000)
    page.locator(".el-form-item__error:has-text('请输入单位')").wait_for(state="visible", timeout=5000)
    # 校验失败不关闭弹窗
    assert page.locator("[data-testid='dialog-product']").is_visible()
    assert_no_errors(page, "产品表单校验")


def test_foundation_supplier_create_and_delete(logged_in):
    """供应商：新增弹窗 → 保存成功 → 搜索可见 → 删除确认 → 行消失"""
    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/foundation/suppliers", wait_until="networkidle")
    page.click("[data-testid='btn-create-supplier']")
    page.wait_for_selector("[data-testid='dialog-supplier']", state="visible", timeout=5000)

    sname = _uniq("E2E供应商")
    fill_dialog_form(page, "名称", sname)
    fill_dialog_form(page, "联系人", "张三")
    fill_dialog_form(page, "电话", "13800002222")

    page.click("[data-testid='btn-save']")
    wait_for_message(page, "success")
    page.wait_for_selector("[data-testid='dialog-supplier']", state="hidden", timeout=5000)

    _search_suppliers(page, sname)
    row = _find_row(page, sname)
    row.wait_for(state="visible", timeout=5000)
    row.locator("button:has-text('删除')").click()
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    expect(row).to_have_count(0, timeout=5000)
    assert_no_errors(page, "供应商新增删除")


# ========== 销售交互 ==========

def test_sales_order_approve_shows_confirm(logged_in, services):
    """销售订单审核：点审核 → ElMessageBox.confirm 真的出现 → 确定 → 状态变已审（审核按钮消失）"""
    with _api_client(services) as c:
        cur = _ensure_currency(c)
        cust = _api_create_customer(c, _uniq("E2E客户"))
        prod = _api_create_product(c, _uniq("E2E产品"))
        order_no = _api_create_sales_order(c, cust, prod, cur, 100, 50)

    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/sales/orders", wait_until="networkidle")
    _search_sales_orders(page, order_no)
    row = _find_row(page, order_no)
    row.wait_for(state="visible", timeout=5000)

    row.locator("[data-testid='btn-approve']").click()
    wait_for_confirm_dialog(page)  # 确认框真的出现（不是只点了按钮）
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    # 状态流转：状态标签变 已审，审核按钮消失
    row.locator("text=已审").wait_for(state="visible", timeout=5000)
    expect(row.locator("[data-testid='btn-approve']")).to_have_count(0, timeout=5000)
    assert_no_errors(page, "销售订单审核")


def test_sales_order_delete_shows_confirm(logged_in, services):
    """销售订单删除：API 建单 → UI 删除 → 确认框出现 → 确定 → 成功提示 → 行消失"""
    with _api_client(services) as c:
        cur = _ensure_currency(c)
        cust = _api_create_customer(c, _uniq("E2E客户"))
        prod = _api_create_product(c, _uniq("E2E产品"))
        order_no = _api_create_sales_order(c, cust, prod, cur, 10, 30)

    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/sales/orders", wait_until="networkidle")
    _search_sales_orders(page, order_no)
    row = _find_row(page, order_no)
    row.wait_for(state="visible", timeout=5000)

    row.locator("[data-testid='btn-delete']").click()
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    expect(row).to_have_count(0, timeout=5000)
    assert_no_errors(page, "销售订单删除")


def test_sales_order_amount_format(logged_in, services):
    """金额格式：列表金额列按 $fm 渲染为 ¥x,xxx.xx（抓 $fm 在 script setup 的 ReferenceError 静默坏）"""
    with _api_client(services) as c:
        cur = _ensure_currency(c)
        cust = _api_create_customer(c, _uniq("E2E客户"))
        prod = _api_create_product(c, _uniq("E2E产品"))
        order_no = _api_create_sales_order(c, cust, prod, cur, 100, 50)
        # 从 API 读回实际含税总金额（100 × 50 × 1.13 = 5650）
        items = c.get("/api/sales/orders", params={"keyword": order_no, "page": 1, "page_size": 100}).json()["items"]
        total = items[0]["total_amount"]
    expected = "¥" + f"{total:,.2f}"

    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/sales/orders", wait_until="networkidle")
    _search_sales_orders(page, order_no)
    row = _find_row(page, order_no)
    row.wait_for(state="visible", timeout=5000)

    row.locator(f"text={expected}").wait_for(state="visible", timeout=5000)
    assert "¥" in row.inner_text()
    assert_no_errors(page, "销售订单金额格式")


# ========== 采购交互 ==========

def test_purchase_order_approve_flow(logged_in, services):
    """采购订单审核：确认框出现 → 确定 → 状态变已审核（审核按钮消失、取消审核出现）"""
    with _api_client(services) as c:
        cur = _ensure_currency(c)
        sup = _api_create_supplier(c, _uniq("E2E供应商"))
        prod = _api_create_product(c, _uniq("E2E产品"))
        order_no = _api_create_purchase_order(c, sup, prod, cur, 10, 20)["order_no"]

    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/purchase/orders", wait_until="networkidle")
    _search_purchase_orders(page, order_no)
    row = _find_row(page, order_no)
    row.wait_for(state="visible", timeout=5000)

    row.locator("[data-testid='btn-approve']").click()
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    row.locator("text=已审核").wait_for(state="visible", timeout=5000)
    expect(row.locator("[data-testid='btn-approve']")).to_have_count(0, timeout=5000)
    expect(row.locator("[data-testid='btn-unapprove']")).to_have_count(1, timeout=5000)
    assert_no_errors(page, "采购订单审核")


def test_purchase_order_cancel_approve(logged_in, services):
    """采购订单取消审核：API 审核后 → UI 点取消审核 → 确认 → 状态回到待审核（取消审核按钮消失、审核按钮回来）"""
    with _api_client(services) as c:
        cur = _ensure_currency(c)
        sup = _api_create_supplier(c, _uniq("E2E供应商"))
        prod = _api_create_product(c, _uniq("E2E产品"))
        po = _api_create_purchase_order(c, sup, prod, cur, 5, 40)
        r = c.post(f"/api/purchase/orders/{po['id']}/approve")
        r.raise_for_status()
        order_no = po["order_no"]

    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/purchase/orders", wait_until="networkidle")
    _search_purchase_orders(page, order_no)
    row = _find_row(page, order_no)
    row.wait_for(state="visible", timeout=5000)

    row.locator("[data-testid='btn-unapprove']").click()
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    # 状态回退：状态标签回待审核，取消审核按钮消失、审核按钮重新出现
    row.locator("text=待审核").wait_for(state="visible", timeout=5000)
    expect(row.locator("[data-testid='btn-unapprove']")).to_have_count(0, timeout=5000)
    expect(row.locator("[data-testid='btn-approve']")).to_have_count(1, timeout=5000)
    assert_no_errors(page, "采购订单取消审核")


# ========== 库存 / 提醒 ==========

def test_inventory_page_loads_clean(logged_in):
    """库存管理页：打开 0 console/page/http 错误"""
    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/inventory/management", wait_until="networkidle")
    page.wait_for_timeout(500)
    assert_no_errors(page, "库存管理页")


def test_reminders_page_loads_clean(logged_in):
    """提醒设置页：打开 0 console/page/http 错误"""
    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/system/reminders", wait_until="networkidle")
    page.wait_for_timeout(500)
    assert_no_errors(page, "提醒设置页")


# ========== 横切 ==========

NAV_PAGES = [
    "/dashboard",
    "/foundation/products",
    "/foundation/suppliers",
    "/sales/orders",
    "/purchase/orders",
    "/inventory/management",
    "/system/reminders",
]


def test_no_console_errors_on_navigation(logged_in):
    """多页导航：依次打开 7 个核心页，累计 0 console/page/http 错误"""
    page = logged_in
    _clear_errors(page)
    for path in NAV_PAGES:
        page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(400)
    assert_no_errors(page, "多页导航")


def test_dialog_cancel_closes(logged_in):
    """弹窗取消：打开弹窗 → 点取消 → 弹窗消失"""
    page = logged_in
    _clear_errors(page)
    page.goto(f"{BASE}/foundation/products", wait_until="networkidle")
    page.click("[data-testid='btn-create-product']")
    page.wait_for_selector("[data-testid='dialog-product']", state="visible", timeout=5000)

    click_dialog_button(page, "取消")
    page.wait_for_selector("[data-testid='dialog-product']", state="hidden", timeout=5000)
    assert_no_errors(page, "弹窗取消关闭")
