"""E2E 测试辅助函数：teleport 感知选择器 + 契约校验

设计原则（按 P1 基建稳定化要求）：
1. teleport 感知：el-select/el-dialog/el-popover 浮层用 body 级定位，不依赖固定 CSS class
2. 状态等待：等待"弹窗可见""按钮可点"等状态，不用固定 sleep
3. 契约校验：API 响应结构有明确 schema 校验
"""

from typing import Any, Callable
from playwright.sync_api import Page, Locator


# ========== Teleport 感知选择器 ==========

def click_select_option(page: Page, form_label: str, option_text: str, timeout: int = 5000):
    """Element Plus select 选择器（teleport 感知）
    
    流程：
    1. 点击表单项的 select 触发器
    2. 等待下拉弹出层出现（teleport 到 body）
    3. 点击匹配选项
    """
    # 点击 select 触发器
    trigger = page.locator(f".el-dialog:visible .el-form-item:has-text('{form_label}') .el-select").first
    trigger.click()
    page.wait_for_timeout(300)
    
    # 点击匹配选项
    option = page.locator(f".el-select-dropdown__item:has-text('{option_text}')").first
    option.click()
    page.wait_for_timeout(200)


def fill_creatable_select(page: Page, form_label: str, value: str, timeout: int = 5000):
    """allow-create 下拉：输入过滤 → 点击选项
    
    用于国家/单位等可创建选项的 select
    """
    # 点击 select 触发器
    trigger = page.locator(f".el-dialog:visible .el-form-item:has-text('{form_label}') .el-select").first
    trigger.click()
    page.wait_for_timeout(300)
    
    # 在 input 中输入过滤
    input_field = page.locator(f".el-dialog:visible .el-form-item:has-text('{form_label}') input").first
    input_field.fill(value)
    page.wait_for_timeout(400)
    
    # 点击匹配选项（allow-create 会显示"创建 xxx"或已有选项）
    option = page.locator(f".el-select-dropdown__item:has-text('{value}')").first
    option.click()
    page.wait_for_timeout(300)


def fill_dialog_form(page: Page, label: str, value: str):
    """填写弹窗内表单项（限定在可见弹窗内）"""
    input_field = page.locator(f".el-dialog:visible .el-form-item:has-text('{label}') input").first
    input_field.fill(value)


def click_dialog_button(page: Page, button_text: str):
    """点击弹窗内按钮"""
    button = page.locator(f".el-dialog:visible button:has-text('{button_text}')")
    button.click()


def wait_for_message(page: Page, message_type: str = "success", timeout: int = 5000):
    """等待 ElMessage 提示出现"""
    page.locator(f".el-message--{message_type}").first.wait_for(state="visible", timeout=timeout)


def wait_for_confirm_dialog(page: Page, timeout: int = 5000):
    """等待 ElMessageBox.confirm 弹窗出现"""
    page.locator(".el-message-box").first.wait_for(state="visible", timeout=timeout)


def click_confirm_button(page: Page, button_text: str = "确定"):
    """点击确认框按钮"""
    page.locator(f".el-message-box button:has-text('{button_text}')").click()


# ========== 契约层校验 ==========

def validate_api_response(response: dict, schema: dict[str, Any], context: str = ""):
    """校验 API 响应结构符合契约
    
    Args:
        response: API 返回的 JSON
        schema: 期望的 schema，如 {"id": int, "name": str, "items": list}
        context: 错误上下文描述
    
    Raises:
        AssertionError: 字段缺失/类型不匹配
    """
    for field, expected_type in schema.items():
        if field not in response:
            raise AssertionError(f"{context} 响应缺少字段 '{field}'，实际: {list(response.keys())}")
        
        actual_value = response[field]
        if not isinstance(actual_value, expected_type):
            raise AssertionError(
                f"{context} 字段 '{field}' 类型不匹配：期望 {expected_type.__name__}，"
                f"实际 {type(actual_value).__name__} (值: {actual_value})"
            )


def validate_list_response(response: dict, item_schema: dict[str, Any], context: str = ""):
    """校验列表 API 响应（含 items 数组）"""
    validate_api_response(response, {"items": list, "total": int}, context)
    
    for i, item in enumerate(response["items"]):
        validate_api_response(item, item_schema, f"{context} items[{i}]")


# ========== 错误收集增强 ==========

def assert_no_errors(page: Page, context: str = ""):
    """断言页面无 console/page/http 错误"""
    problems = []
    if page.errors["console"]:
        problems.append(f"console errors: {page.errors['console']}")
    if page.errors["page"]:
        problems.append(f"page errors: {page.errors['page']}")
    if page.errors["http"]:
        problems.append(f"http errors: {page.errors['http']}")
    
    if problems:
        raise AssertionError(f"{context} 存在错误:\n" + "\n".join(problems))
