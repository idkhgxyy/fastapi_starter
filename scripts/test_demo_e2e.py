"""端到端 Demo 测试"""
import random
import sys
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"

suffix = random.randint(1000, 9999)
TEST_USER = {
    "username": f"tester{suffix}",
    "email": f"tester{suffix}@test.com",
    "password": "Test123!@#",
}


def run_e2e():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("dialog", lambda dialog: dialog.accept())

        print(f"\n使用测试用户: {TEST_USER['username']} / {TEST_USER['email']}")

        # Step 1: 首页
        print("\n=== Step 1: 首页 ===")
        page.goto(f"{BASE_URL}/demo.html")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/demo_01_homepage.png", full_page=True)
        assert "FastAPI AI Agent" in page.title()
        assert page.is_visible("text=未认证")
        print("  ✅ 首页加载成功")

        # Step 2: 注册
        print("\n=== Step 2: 注册 ===")
        page.click("text=注册")
        page.wait_for_timeout(500)
        page.fill('input[id="register-username"]', TEST_USER["username"])
        page.fill('input[id="register-email"]', TEST_USER["email"])
        page.fill('input[id="register-password"]', TEST_USER["password"])
        page.click('button:has-text("注册并登录")')
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/demo_02_registered.png", full_page=True)

        # 验证登录 - 用户名应该出现在 navbar 的绿色标签中
        nav_text = page.inner_text("header")
        print(f"  Header 文本: {nav_text[:80]}...")
        assert TEST_USER["username"] in nav_text, f"用户名 '{TEST_USER['username']}' 未出现在 header 中"
        assert "退出" in nav_text
        print(f"  ✅ 注册/登录成功，显示用户: '{TEST_USER['username']}'")

        # Step 3: 聊天
        print("\n=== Step 3: 聊天 ===")
        page.wait_for_timeout(500)
        page.fill('textarea[id="chat-input"]', "你好！今天天气怎么样？")
        page.press('textarea[id="chat-input"]', "Enter")
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/demo_03_chat.png", full_page=True)
        body = page.text_content("body")
        assert any(kw in (body or "") for kw in ["Mock", "演示", "回复", "模式"])
        print("  ✅ Mock 聊天回复正常")

        # Step 4: 任务
        print("\n=== Step 4: 任务面板 ===")
        page.click("text=📋 任务")
        page.wait_for_timeout(500)
        page.screenshot(path="/tmp/demo_04_tasks.png", full_page=True)
        print("  ✅ 任务面板切换成功")

        # Step 5: 知识库
        print("\n=== Step 5: 知识库面板 ===")
        page.click("text=📚 知识库")
        page.wait_for_timeout(500)
        page.screenshot(path="/tmp/demo_05_knowledge.png", full_page=True)
        print("  ✅ 知识库面板切换成功")

        # Step 6: 退出
        print("\n=== Step 6: 退出 ===")
        page.click("text=退出")
        page.wait_for_timeout(1000)
        assert page.is_visible("text=未认证")
        page.screenshot(path="/tmp/demo_06_logout.png", full_page=True)
        print("  ✅ 退出成功")

        context.close()
        browser.close()

        print("\n" + "=" * 50)
        print("🎉 全部 E2E 测试通过！")
        print("=" * 50)


if __name__ == "__main__":
    run_e2e()
