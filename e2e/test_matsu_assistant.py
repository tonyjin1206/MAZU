"""AI 助手悬浮球 E2E 冒烟：入口可见、打开聊天窗、发送消息、新对话"""

import pytest


def _open_assistant(page):
    """点击右下角悬浮球，等待聊天窗出现"""
    page.locator(".matsu-ball").click()
    page.wait_for_selector(".matsu-window", timeout=5000)
    page.wait_for_timeout(300)


@pytest.mark.parametrize("path", ["/dashboard", "/sales/orders", "/inventory/management"])
def test_floating_ball_on_all_pages(logged_in, path):
    """悬浮球在所有业务页面可见（全局挂载）"""
    logged_in.goto(f"{logged_in.url.split('/dashboard')[0]}{path}", wait_until="networkidle")
    logged_in.wait_for_timeout(400)
    assert logged_in.locator(".matsu-ball").count() == 1, "悬浮球应全局可见"


def test_open_window_and_welcome(logged_in):
    """点击悬浮球弹出聊天窗，显示 Matsu 欢迎语"""
    _open_assistant(logged_in)
    assert logged_in.locator(".matsu-window").count() == 1
    assert "Matsu" in logged_in.locator(".matsu-msgs").inner_text()


def test_send_message_gets_reply(logged_in):
    """发送消息：AI 未配置时返回明确提示（链路通）"""
    _open_assistant(logged_in)
    logged_in.fill(".matsu-input input", "你好")
    logged_in.press(".matsu-input input", "Enter")
    logged_in.wait_for_timeout(2500)
    text = logged_in.locator(".matsu-msgs").inner_text()
    assert "AI" in text, f"应返回 AI 相关回复，实际: {text[:200]}"


def test_capability_hint_shows_admin_tools(logged_in):
    """管理员可用能力提示包含采购/销售/库存"""
    _open_assistant(logged_in)
    caps = logged_in.locator(".matsu-cap").all_inner_texts()
    joined = "".join(caps)
    assert "采购" in joined and "销售" in joined and "查库存" in joined


def test_reset_creates_new_conversation(logged_in):
    """新对话按钮恢复欢迎语"""
    _open_assistant(logged_in)
    logged_in.fill(".matsu-input input", "你好")
    logged_in.press(".matsu-input input", "Enter")
    logged_in.wait_for_timeout(2500)
    logged_in.locator(".matsu-header button:has-text('新对话')").click()
    logged_in.wait_for_timeout(800)
    text = logged_in.locator(".matsu-msgs").inner_text()
    assert "Matsu" in text and "你想做什么" in text


def test_no_console_errors(logged_in):
    """悬浮组件不应产生 console/page/4xx 错误"""
    _open_assistant(logged_in)
    logged_in.wait_for_timeout(800)
    errs = logged_in.errors
    problems = []
    if errs["console"]:
        problems.append(f"console: {errs['console']}")
    if errs["page"]:
        problems.append(f"pageerror: {errs['page']}")
    if errs["http"]:
        problems.append(f"http: {errs['http']}")
    assert not problems, "悬浮助手存在错误:\n" + "\n".join(problems)
