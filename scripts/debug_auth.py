"""调试脚本：处理 alert 对话框后的页面状态"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # 自动处理所有 alert 对话框
    page.on("dialog", lambda dialog: dialog.accept())

    page.goto(f"{BASE_URL}/demo.html")
    page.wait_for_load_state("networkidle")

    # 点击注册
    page.click("text=注册")
    page.wait_for_timeout(500)

    # 填写注册
    page.fill('input[id="register-username"]', "debug2")
    page.fill('input[id="register-email"]', "debug2@test.com")
    page.fill('input[id="register-password"]', "Debug123!")
    page.click('button:has-text("注册并登录")')

    page.wait_for_timeout(3000)
    page.screenshot(path="/tmp/debug_after_register2.png", full_page=True)

    # 检查页面
    for keyword in ["已登录", "未认证", "退出"]:
        visible = page.is_visible(f"text={keyword}", timeout=2000)
        print(f"'{keyword}' visible: {visible}")

    token = page.evaluate("localStorage.getItem('agent_token')")
    print(f"Token in localStorage: {'present' if token else 'absent'}")

    context.close()
    browser.close()
