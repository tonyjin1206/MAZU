"""E2E 核心业务流程：SP 流程（审核→转直采/转委外）

测试策略：
- 使用 API 创建销售订单（避免复杂的 UI 表单操作）
- 使用 UI 测试 SP 特有的流程：审核→转直采/转委外
- 这样测试更稳定，专注于 SP 流程而非通用 UI 操作
"""

import httpx
import pytest
from helpers import (
    click_select_option,
    fill_creatable_select,
    fill_dialog_form,
    click_dialog_button,
    wait_for_message,
    wait_for_confirm_dialog,
    click_confirm_button,
    validate_api_response,
    assert_no_errors,
)


def _api_setup(services):
    """预置基础档案：币种/仓库/供应商/国家参数（E2E 独立库为空）"""
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
        # 国家参数（用于客户/供应商下拉）
        c.post("/api/foundation/params", json={
            "group_name": "country", "param_key": "CN", "param_label": "中国", "sort_order": 1, "remark": "国家"}, headers=h)
        c.post("/api/foundation/params", json={
            "group_name": "country", "param_key": "US", "param_label": "美国", "sort_order": 2, "remark": "国家"}, headers=h)


def _api_create_sales_order(services, customer_name, product_name, quantity, unit_price):
    """使用 API 创建销售订单（避免复杂的 UI 表单）"""
    base = services["backend"]
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        
        # 查询客户 ID
        customers = c.get("/api/foundation/customers", params={"page": 1, "page_size": 100}, headers=h).json()
        customer = next((x for x in customers["items"] if x["name_cn"] == customer_name), None)
        assert customer, f"客户 {customer_name} 不存在"
        
        # 查询产品 ID
        products = c.get("/api/foundation/products", params={"page": 1, "page_size": 100}, headers=h).json()
        product = next((x for x in products["items"] if x["name_cn"] == product_name), None)
        assert product, f"产品 {product_name} 不存在"
        
        # 查询币种 ID
        currencies = c.get("/api/foundation/currencies", params={"page": 1, "page_size": 100}, headers=h).json()
        currency = next((x for x in currencies["items"] if x["code"] == "CNY"), None)
        assert currency, "币种 CNY 不存在"
        
        # 创建销售订单
        order_data = {
            "customer_id": customer["id"],
            "currency_id": currency["id"],
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "tax_rate": 13,
                }
            ]
        }
        resp = c.post("/api/sales/orders", json=order_data, headers=h)
        validate_api_response(resp.json(), {"id": int, "order_no": str}, "创建销售订单")
        return resp.json()


def test_core_business_flow_sp(logged_in, services):
    """SP 核心流程：客户→产品→销售订单(API)→审核(UI)→转直采(UI)"""
    page = logged_in
    _api_setup(services)
    page.errors["console"].clear()
    page.errors["http"].clear()
    page.errors["page"].clear()

    # ============ 1. 客户建档 ============
    page.goto("http://localhost:5174/foundation/customers", wait_until="networkidle")
    page.click("[data-testid='btn-create-customer']")
    page.wait_for_selector("[data-testid='dialog-customer']", timeout=5000)
    
    fill_dialog_form(page, "中文名", "E2E测试客户")
    fill_dialog_form(page, "联系人", "王五")
    fill_dialog_form(page, "电话", "13800001111")
    fill_dialog_form(page, "税号", "91330000E2E")
    fill_creatable_select(page, "国家", "中国")
    
    page.click("[data-testid='btn-save']")
    wait_for_message(page, "success")
    print("✅ 1. 客户建档成功")

    # ============ 2. 产品建档 ============
    page.goto("http://localhost:5174/foundation/products", wait_until="networkidle")
    page.click("button:has-text('新增')")
    page.wait_for_selector(".el-dialog:visible", timeout=5000)
    
    fill_dialog_form(page, "品名（公司）", "E2E测试产品")
    fill_dialog_form(page, "规格", "标准")
    fill_creatable_select(page, "单位", "件")
    fill_dialog_form(page, "销售价", "100")
    
    click_dialog_button(page, "保存")
    wait_for_message(page, "success")
    print("✅ 2. 产品建档成功")

    # ============ 3. 销售订单（使用 API 创建，避免复杂 UI） ============
    order = _api_create_sales_order(services, "E2E测试客户", "E2E测试产品", 100, 50)
    print(f"✅ 3. 销售订单创建成功（API）: {order['order_no']}")

    # ============ 4. 审核订单（UI 操作） ============
    page.goto("http://localhost:5174/sales/orders", wait_until="networkidle")
    page.wait_for_timeout(500)
    
    # 找到刚创建的订单行
    row = page.locator(f"tr:has-text('{order['order_no']}')").first
    row.locator("button:has-text('审核')").click()
    
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    wait_for_message(page, "success")
    print("✅ 4. 销售订单审核成功（UI）")

    # ============ 5. 转直采（SP 流程：UI 操作） ============
    page.wait_for_timeout(800)
    
    # 双击订单行展开明细（两层交互：单击选中、双击进入明细）
    row.dblclick()
    page.wait_for_timeout(500)
    
    # 找到"转直采"按钮并点击
    stock_in_btn = page.locator("button:has-text('转直采')").first
    stock_in_btn.scroll_into_view_if_needed()
    stock_in_btn.click()
    
    # 等待确认框
    wait_for_confirm_dialog(page)
    click_confirm_button(page, "确定")
    
    # 等待成功提示
    wait_for_message(page, "success")
    print("✅ 5. 转直采成功（SP 流程，UI）")

    # ============ 全程错误检查 ============
    assert_no_errors(page, "核心流程")
    print("✅ 核心流程全程 0 错误")
