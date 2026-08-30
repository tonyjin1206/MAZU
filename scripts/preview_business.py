"""核心业务操作交互测试：新建单据/档案、AI 助手。"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
SHOT = Path("/tmp/erp_biz")
SHOT.mkdir(parents=True, exist_ok=True)
FAILED = []


def check(name, cond, extra=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {extra}")
        FAILED.append(name)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:300]))
        pg.on("console", lambda m: print("CONSOLE:", m.type, m.text[:200]) if m.type == "error" else None)

        pg.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)
        pg.fill("input[placeholder='用户名']", "admin")
        pg.fill("input[placeholder='密码']", "admin123")
        pg.click("button:has-text('登 录')")
        pg.wait_for_url("**/dashboard", timeout=15000)
        pg.wait_for_timeout(800)

        # ===== 1. 新建销售订单 =====
        pg.goto(f"{BASE_URL}/sales/orders", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(600)
        pg.click("button:has-text('新建订单')")
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(SHOT / "so_form.png"))

        # 客户选择（通过“选择”按钮打开客户选择器）
        pick_btn = pg.locator("[data-testid='dialog-order'] button:has-text('选择')")
        if pick_btn.count():
            pick_btn.first.click(force=True)
            pg.wait_for_timeout(800)
            pg.screenshot(path=str(SHOT / "cust_picker.png"))
            # 找出标题含“选择客户”的对话框
            picker_dlg = None
            for d in pg.locator(".el-dialog").all():
                t = d.locator(".el-dialog__title").inner_text() if d.locator(".el-dialog__title").count() else ""
                print("可见对话框标题:", t)
                if "选择客户" in t:
                    picker_dlg = d
            if picker_dlg is None:
                picker_dlg = pg.locator(".el-dialog").last
            cust_rows = picker_dlg.locator(".el-table__body-wrapper tbody tr")
            print("客户选择器行数:", cust_rows.count())
            if cust_rows.count():
                cust_rows.first.click(force=True)
                pg.wait_for_timeout(300)
                ok_btn = picker_dlg.locator("button:has-text('确定')")
                if ok_btn.count():
                    ok_btn.first.click(force=True)
        pg.wait_for_timeout(500)

        # 币种选择
        cur_trigger = pg.locator(".el-dialog:visible .el-form-item:has-text('币种') .el-select")
        if cur_trigger.count():
            cur_trigger.first.click()
            pg.wait_for_timeout(500)
            opts = pg.locator(".el-select-dropdown:visible .el-select-dropdown__item")
            print("币种下拉选项:", opts.all_inner_texts()[:10])
            # 选择第一个正常币种（非拼接的脏数据）
            for i in range(opts.count()):
                txt = opts.nth(i).inner_text()
                if txt.strip() and len(txt.strip()) <= 4:
                    opts.nth(i).click()
                    break
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(SHOT / "so_form2.png"))

        # 明细行产品选择
        prod_trigger = pg.locator(".el-dialog:visible .el-form-item:has-text('产品') .el-select, .el-dialog:visible td:has-text('产品') .el-select")
        if prod_trigger.count():
            prod_trigger.first.click()
            pg.wait_for_timeout(500)
            opts = pg.locator(".el-select-dropdown:visible .el-select-dropdown__item")
            print("产品下拉选项:", opts.all_inner_texts()[:5])
            if opts.count():
                opts.first.click()
        pg.wait_for_timeout(300)

        # 数量/单价
        qty_input = pg.locator(".el-dialog:visible input[placeholder*='数量'], .el-dialog:visible .el-form-item:has-text('数量') input")
        price_input = pg.locator(".el-dialog:visible input[placeholder*='单价'], .el-dialog:visible .el-form-item:has-text('单价') input")
        print("数量输入框数:", qty_input.count(), "单价输入框数:", price_input.count())
        if qty_input.count():
            qty_input.first.fill("10")
        if price_input.count():
            price_input.first.fill("100")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(SHOT / "so_form3.png"))

        # 提交
        pg.locator(".el-dialog:visible button:has-text('保存'), .el-dialog:visible button:has-text('提交'), .el-dialog:visible button:has-text('确定')").first.click()
        pg.wait_for_timeout(1500)
        msgs = pg.locator(".el-message").all_inner_texts()
        print("消息:", msgs)
        check("新建销售订单无报错", not FAILED and all("失败" not in m and "错误" not in m for m in msgs), str(msgs))
        pg.screenshot(path=str(SHOT / "so_result.png"))

        # ===== 2. 新建客户 =====
        pg.goto(f"{BASE_URL}/foundation/customers", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(600)
        pg.click("button:has-text('新增客户')")
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(SHOT / "cust_form.png"))
        # 填必填项
        name_input = pg.locator(".el-dialog:visible input[data-testid='input-name-cn']")
        if not name_input.count():
            name_input = pg.locator(".el-dialog:visible .el-form-item:has-text('中文名') input")
        print("客户中文名输入框数:", name_input.count())
        if name_input.count():
            name_input.first.fill(f"测试客户{__import__('time').time_ns() % 10000}")
        pg.screenshot(path=str(SHOT / "cust_form2.png"))
        pg.locator(".el-dialog:visible button:has-text('保存'), .el-dialog:visible button:has-text('提交'), .el-dialog:visible button:has-text('确定')").first.click()
        pg.wait_for_timeout(1200)
        msgs = pg.locator(".el-message").all_inner_texts()
        print("新增客户消息:", msgs)
        check("新建客户无报错", all("失败" not in m and "错误" not in m for m in msgs), str(msgs))

        # ===== 3. 币种管理页 =====
        pg.goto(f"{BASE_URL}/foundation/currencies", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(600)
        rows = pg.locator(".el-table__body-wrapper tbody tr").all_inner_texts()
        print("\n币种列表行:")
        for r in rows:
            print(" ", r.strip().replace("\n", " | ")[:100])
        check("币种列表无脏数据", not any("CNY990" in r for r in rows), "存在 CNY990xxx 脏币种")
        pg.screenshot(path=str(SHOT / "currencies.png"))

        # ===== 4. AI 助手悬浮球 =====
        pg.goto(f"{BASE_URL}/dashboard", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(800)
        bot_btn = pg.locator("[class*='bot'], [class*='Bot'], [class*='assistant'], .ai-fab, .chat-fab")
        print("AI 悬浮球匹配数:", bot_btn.count())
        if bot_btn.count():
            bot_btn.first.click()
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(SHOT / "ai_panel.png"))
            panel = pg.locator("text=AI助手, text=智能助手, .chat-panel, [class*='chat']")
            print("AI 面板可见文本:", pg.locator("body").inner_text()[-300:][:300])

        browser.close()

    print("\n===== 测试结果 =====")
    print("失败项:", FAILED if FAILED else "无")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
