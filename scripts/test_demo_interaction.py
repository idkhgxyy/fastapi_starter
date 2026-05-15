import os
import time

from playwright.sync_api import sync_playwright


def main():
    print("开始自动化测试 Demo 页面...")
    os.makedirs("docs/images", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
        page = context.new_page()

        try:
            print("1. 访问 Demo 页面...")
            page.goto("http://localhost:8000/demo.html", wait_until="networkidle")
            time.sleep(1)

            # 截取初始状态
            page.screenshot(path="docs/images/demo_step1_initial.png")
            print("   -> 页面已加载，保存截图: docs/images/demo_step1_initial.png")

            print("2. 获取真实 Token...")
            import requests

            # 确保用户存在
            requests.post(
                "http://localhost:8000/api/v1/users/",
                json={
                    "username": "demouser",
                    "email": "demo@example.com",
                    "password": "password123",
                },
            )
            # 登录拿 token
            resp = requests.post(
                "http://localhost:8000/api/v1/auth/login",
                data={"username": "demo@example.com", "password": "password123"},
            )

            if resp.status_code == 200:
                token = resp.json().get("access_token")
                print("   -> 成功获取真实 Token")

                # 在浏览器中设置 localStorage 并刷新
                page.evaluate(f"localStorage.setItem('agent_token', '{token}');")
                page.reload(wait_until="networkidle")
                time.sleep(1)

                # 输入问题
                print("3. 尝试向 AI 提问并触发多工具调用...")
                page.fill("#chat-input", "帮我查一下北京今天的天气，顺便看看服务器内存负载高不高。")
                page.click("#send-btn")

                print("   -> 消息已发送，等待 AI 处理 (这可能需要几秒到十几秒)...")

                # 等待直到 "正在输入" 的指示器消失，并且出现了新的气泡
                page.wait_for_selector(".typing-indicator", state="hidden", timeout=60000)
                time.sleep(2)  # 等待渲染完成

                # 截图
                page.screenshot(path="docs/images/demo_step2_response.png")
                print("   -> AI 已回复，保存真实交互截图: docs/images/demo_step2_response.png")
            else:
                print("   -> 获取 Token 失败，无法进行真实交互演示。")

        except Exception as e:
            print(f"测试过程中出现错误: {e}")
        finally:
            browser.close()
            print("测试结束。")


if __name__ == "__main__":
    main()
