"""E2E 核心业务流程：浏览器真实操作
客户建档 → 产品建档 → 销售订单（多明细）→ 审核 → 生产订单自动生成

前置：E2E 独立库为空，先通过后端 API 预置基础档案（币种/仓库/供应商），
业务流程本身全部走 UI 操作。
"""

import httpx
import pytest


def _api_setup(services):
    """预置基础档案：币种/仓库/供应商（E2E 独立库为空）"""
    base = services["backend"]
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        c.post("/api/foundation/currencies", json={
            "code": "CNY", "name": "人民币", "symbol": "¥", "is_base": 1}, headers=h)
        c.post("/api/foundation/warehouses", json={
            "code": "WH", "name": "主仓", "wh_type": "原料仓"}, headers=h)
        c.post("/api/foundation/processes", json={
            "code": "PROC1", "name": "测试工序", "unit_price": 1}, headers=h)


def _pick_select(page, label, option_text):
    """Element Plus select：点击表单项的 select，选下拉选项"""
    page.locator(f".el-form-item:has-text('{label}') .el-select").click()
    page.locator(f".el-select-dropdown__item:has-text('{option_text}')").first.click()
    page.wait_for_timeout(200)


def _fill_form_item(page, label, value):
    """按 label 填表单项的 input（限定在可见弹窗内）"""
    page.locator(f".el-dialog:visible .el-form-item:has-text('{label}') input").first.fill(value)
    page.wait_for_timeout(100)


def _fill_creatable_select(page, label, value):
    """allow-create 下拉：点击 → 输入过滤 → 点击下拉选项（回车不触发 v-model）"""
    page.locator(f".el-dialog:visible .el-form-item:has-text('{label}') .el-select").click()
    page.wait_for_timeout(300)
    page.locator(f".el-dialog:visible .el-form-item:has-text('{label}') input").first.fill(value)
    page.wait_for_timeout(400)
    # 点击下拉中的匹配选项（allow-create 会显示"创建 xxx"或已有选项）
    page.locator(f".el-select-dropdown__item:has-text('{value}')").first.click()
    page.wait_for_timeout(300)


def test_core_business_flow(logged_in, services):
    page = logged_in
    _api_setup(services)
    page.errors["console"].clear()
    page.errors["http"].clear()
    page.errors["page"].clear()

    # ============ 1. 客户建档 ============
    page.goto("http://localhost:5174/foundation/customers", wait_until="networkidle")
    page.click("button:has-text('新增客户')")
    page.wait_for_selector(".el-dialog:visible", timeout=5000)
    _fill_form_item(page, "中文名", "E2E测试客户")
    _fill_form_item(page, "联系人", "王五")
    _fill_form_item(page, "电话", "13800001111")
    _fill_form_item(page, "税号", "91330000E2E")
    _fill_creatable_select(page, "国家", "中国")  # 必填
    page.locator(".el-dialog:visible button:has-text('保存')").click()
    page.wait_for_selector(".el-message--success", timeout=5000)
    print("✅ 1. 客户建档成功")

    # ============ 2. 产品建档 ============
    page.goto("http://localhost:5174/foundation/products", wait_until="networkidle")
    page.click("button:has-text('新增')")  # 产品页按钮为"新增"，弹窗标题才是"新增产品"
    page.wait_for_selector(".el-dialog:visible", timeout=5000)
    _fill_form_item(page, "中文名", "E2E测试产品")
    _fill_form_item(page, "规格", "标准")
    _fill_creatable_select(page, "单位", "件")  # 必填
    _fill_form_item(page, "销售价", "100")
    page.locator(".el-dialog:visible button:has-text('保存')").click()
    page.wait_for_selector(".el-message--success", timeout=5000)
    print("✅ 2. 产品建档成功")

    # ============ 3. 销售订单 ============
    page.goto("http://localhost:5174/sales/orders", wait_until="networkidle")
    page.click("button:has-text('新建订单')")
    page.wait_for_selector(".el-dialog:visible", timeout=5000)
    # 客户
    _pick_select(page, "客户", "E2E测试客户")
    # 币种
    _pick_select(page, "币种", "CNY")
    # 明细（弹窗初始化已含一行明细，直接填）
    dialog = page.locator(".el-dialog:visible")
    dialog.locator(".el-table .el-select").first.click()  # 明细产品下拉
    page.locator(".el-select-dropdown__item:has-text('E2E测试产品')").first.click()
    page.wait_for_timeout(200)
    # 数量/单价 input（明细行内：数量、单价、税率三个 number）
    table_inputs = dialog.locator(".el-table input[type='number']")
    table_inputs.nth(0).fill("100")  # 数量
    table_inputs.nth(1).fill("50")   # 单价
    page.wait_for_timeout(200)
    # 保存订单
    page.locator(".el-dialog:visible button:has-text('保存')").click()
    try:
        page.wait_for_selector(".el-message--success", timeout=5000)
    except Exception:
        page.wait_for_timeout(1500)
        msgs = page.locator(".el-message").all_text_contents()
        errors = page.locator(".el-dialog:visible .el-form-item__error").all_text_contents()
        http_err = [e for e in page.errors["http"] if "sales/orders" in e]
        page.screenshot(path="C:/Users/TonyJ/AppData/Local/Temp/e2e_so.png")
        raise AssertionError(
            f"订单保存失败: messages={msgs} 校验错误={errors} http错误={http_err}")
    print("✅ 3. 销售订单创建成功")

    # ============ 4. 审核订单（生成生产订单） ============
    page.wait_for_timeout(800)
    row = page.locator("tr:has-text('E2E测试客户')").first
    row.locator("button:has-text('审核')").click()
    page.wait_for_selector(".el-message-box", timeout=5000)
    page.locator(".el-message-box button:has-text('确定')").click()
    page.wait_for_selector(".el-message--success", timeout=5000)
    print("✅ 4. 销售订单审核成功")

    # ============ 5. 生产订单自动生成 ============
    page.goto("http://localhost:5174/production/orders", wait_until="networkidle")
    page.wait_for_timeout(800)
    assert page.locator("tr:has-text('E2E测试产品')").count() >= 1, "生产订单未生成"
    print("✅ 5. 生产订单已自动生成")

    # ============ 全程错误检查 ============
    problems = []
    if page.errors["console"]:
        problems.append(f"console: {page.errors['console']}")
    if page.errors["page"]:
        problems.append(f"pageerror: {page.errors['page']}")
    if page.errors["http"]:
        problems.append(f"http: {page.errors['http']}")
    assert not problems, "核心流程存在错误:\n" + "\n".join(problems)
    print("✅ 核心流程全程 0 错误")
