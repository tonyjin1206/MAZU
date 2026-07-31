"""E2E：菜单级权限落地验证（v2.2.0 前端权限过滤）
1. 库管员（warehouse_keeper）登录 → 系统管理菜单不可见、库存管理可见
2. 库管员直接访问 /system/users → 被重定向回工作台
3. 库管员访问有权限页面（/inventory/management）→ 正常打开
"""

import httpx
import pytest


def _create_warehouse_keeper(services):
    """API 建一个库管员用户（E2E 独立库）"""
    base = services["backend"]
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        roles = c.get("/api/auth/roles", headers=admin_h).json()
        keeper_role = next(x["id"] for x in roles if x["code"] == "warehouse_keeper")
        c.post("/api/auth/users", headers=admin_h, json={
            "username": "e2e_keeper", "password": "keeper123",
            "display_name": "E2E库管员", "role_id": keeper_role,
        })


def test_menu_permission_filter(page, services):
    """库管员：系统管理菜单隐藏，库存管理可见"""
    _create_warehouse_keeper(services)
    page.goto(f"{services['base']}/login", wait_until="networkidle")
    page.fill("input[placeholder='用户名']", "e2e_keeper")
    page.fill("input[placeholder='密码']", "keeper123")
    page.click("button:has-text('登 录')")
    page.wait_for_url("**/dashboard", timeout=15000)
    page.wait_for_timeout(800)

    # 系统管理菜单不可见
    assert page.locator(".el-menu-item:has-text('用户管理')").count() == 0
    assert page.locator(".el-sub-menu:has-text('系统管理')").count() == 0
    # 库存管理可见
    assert page.locator(".el-sub-menu:has-text('库存管理')").count() == 1
    # 基础档案不可见（库管员无基础档案权限）
    assert page.locator(".el-sub-menu:has-text('基础档案')").count() == 0


def test_route_guard_blocks_unauthorized(page, services):
    """库管员直接访问 /system/users → 重定向工作台"""
    _create_warehouse_keeper(services)
    page.goto(f"{services['base']}/login", wait_until="networkidle")
    page.fill("input[placeholder='用户名']", "e2e_keeper")
    page.fill("input[placeholder='密码']", "keeper123")
    page.click("button:has-text('登 录')")
    page.wait_for_url("**/dashboard", timeout=15000)

    # 直接输 URL 访问无权限页面
    page.goto(f"{services['base']}/system/users", wait_until="networkidle")
    page.wait_for_timeout(1000)
    assert page.url.endswith("/dashboard"), f"应被重定向回工作台，实际: {page.url}"

    # 有权限页面正常打开
    page.goto(f"{services['base']}/inventory/management", wait_until="networkidle")
    page.wait_for_timeout(800)
    assert page.locator(".el-main").count() == 1
    # 无 4xx/5xx
    http_ok = [e for e in page.errors["http"] if e.startswith("4") or e.startswith("5")]
    assert not http_ok, f"有权限页面出现 HTTP 错误: {http_ok}"
