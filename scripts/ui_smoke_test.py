"""浏览器层真实 UI 冒烟。

需要本机已安装 Playwright（项目脚本用 /usr/bin/python3）：

    UI_SMOKE_BASE_URL=http://127.0.0.1:18081 /usr/bin/python3 scripts/ui_smoke_test.py

覆盖：登录页登录、侧栏上传并等待“就绪”、知识库搜索命中、对话框提问并看到
带验收码的回答、清理临时文档。任何一步失败返回非 0，并保存失败截图。
服务器前端只监听 127.0.0.1 时，先建隧道：
    ssh -N -L 18081:127.0.0.1:8000 ubuntu@YOUR_SERVER
"""

import os
import sys
import time
import uuid
from typing import Optional

import httpx
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("UI_SMOKE_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.getenv("SMOKE_EMAIL", "smoke@example.com")
PASSWORD = os.getenv("SMOKE_PASSWORD", "smoke-test-password-2026")
USERNAME = os.getenv("SMOKE_USERNAME", "smoke-tester")
SCREENSHOT = os.getenv(
    "UI_SMOKE_SCREENSHOT", "evaluation/artifacts/ui_smoke_failure.png"
)
SUCCESS_SCREENSHOT = os.getenv(
    "UI_SMOKE_SUCCESS_SCREENSHOT", "evaluation/artifacts/ui_smoke_success.png"
)
QA_SCREENSHOT = os.getenv(
    "UI_SMOKE_QA_SCREENSHOT", "evaluation/artifacts/ui_smoke_qa_success.png"
)
TIMEOUT = int(os.getenv("UI_SMOKE_TIMEOUT_MS", "180000"))


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _login_or_register() -> str:
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        login = client.post(
            "/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD}
        )
        if login.status_code == 200:
            return login.json()["access_token"]
        if login.status_code != 401:
            raise RuntimeError(f"登录失败: HTTP {login.status_code} {login.text[:200]}")
        created = client.post(
            "/api/v1/users/",
            json={
                "username": USERNAME,
                "email": EMAIL,
                "password": PASSWORD,
                "full_name": "Smoke Tester",
            },
        )
        if created.status_code not in (200, 201):
            raise RuntimeError(
                "验收账号不存在且注册失败: "
                f"HTTP {created.status_code} {created.text[:200]}"
            )
        login = client.post(
            "/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD}
        )
        _check(login.status_code == 200, f"注册后登录失败: HTTP {login.status_code}")
        return login.json()["access_token"]


def _delete_document(token: str, filename: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        docs = client.get("/api/v1/rag/documents", headers=headers)
        if docs.status_code != 200:
            print(f"[WARN] 查询文档失败: HTTP {docs.status_code}")
            return
        matches = [doc["id"] for doc in docs.json() if doc["filename"] == filename]
        for document_id in matches:
            response = client.delete(
                f"/api/v1/rag/documents/{document_id}", headers=headers
            )
            if response.status_code == 200:
                print(f"[CLEAN] 已删除临时文档 id={document_id}")
            else:
                print(
                    f"[WARN] 删除文档 {document_id} 失败: HTTP {response.status_code}",
                    file=sys.stderr,
                )


def main() -> int:
    run_id = uuid.uuid4().hex[:8]
    code = f"UI-{run_id.upper()}"
    filename = f"ui-smoke-{run_id}.md"
    content = (
        f"# UI Smoke {run_id}\n\n"
        f"部署验收码：{code}\n\n"
        "这份文件用于浏览器层冒烟，验证侧栏上传、知识库搜索和对话框问答。\n"
    )
    temp_path = f"/tmp/{filename}"
    with open(temp_path, "w", encoding="utf-8") as file:
        file.write(content)

    token: Optional[str] = None
    page = None
    browser = None
    playwright = None
    try:
        print(f"== UI smoke {BASE_URL} account={EMAIL} run={run_id}")
        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            health = client.get("/api/v1/health/")
            _check(health.status_code == 200, f"健康检查失败: HTTP {health.status_code}")
        print("[PASS] 1/7 健康检查")
        token = _login_or_register()

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.set_default_timeout(TIMEOUT)
        page.set_default_navigation_timeout(TIMEOUT)
        page_errors = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        page.goto(f"{BASE_URL}/auth/login", wait_until="domcontentloaded")
        page.fill("#email", EMAIL)
        page.fill("#password", PASSWORD)
        page.locator("button[type='submit']").click()
        page.wait_for_url("**/chat", timeout=TIMEOUT)
        page.wait_for_selector("textarea[placeholder='输入消息，按 Enter 发送...']")
        print("[PASS] 2/7 登录页登录并进入 /chat")

        page.locator("nav button").first.click()
        page.wait_for_selector("aside")
        page.locator("aside button").filter(has_text="知识库").first.click()
        page.locator("aside input[type='file']").set_input_files(temp_path)
        page.locator("aside").get_by_text(filename).first.wait_for(state="visible")
        page.locator("aside").get_by_text("就绪").first.wait_for(
            state="visible", timeout=180000
        )
        print(f"[PASS] 3/7 侧栏上传并等到就绪（{filename}）")

        search = page.locator("aside input[placeholder='搜索知识库...']").first
        search.fill("部署验收码")
        search.press("Enter")
        page.locator("aside").get_by_text("搜索结果").first.wait_for(
            state="visible", timeout=60000
        )
        page.locator("aside").get_by_text(code).first.wait_for(
            state="visible", timeout=60000
        )
        print("[PASS] 4/7 知识库搜索命中验收码")

        page.locator("aside").get_by_text("打开完整知识库 / 问答 →").first.click()
        page.wait_for_url("**/knowledge", timeout=TIMEOUT)
        qa_input = page.locator("input[placeholder^='问知识库']").first
        qa_input.fill("部署验收码是什么？")
        qa_input.press("Enter")
        page.locator(".prose").filter(has_text=code).last.wait_for(
            state="visible", timeout=180000
        )
        page.locator("summary").filter(has_text="来源片段").first.wait_for(
            state="visible", timeout=60000
        )
        page.locator("details").filter(has_text=code).first.wait_for(
            state="visible", timeout=60000
        )
        os.makedirs(os.path.dirname(QA_SCREENSHOT), exist_ok=True)
        page.screenshot(path=QA_SCREENSHOT, full_page=True)
        print(f"[PASS] 5/7 知识库问答返回答案和来源片段（截图 {QA_SCREENSHOT}）")

        page.locator("button").filter(has_text="返回").first.click()
        page.wait_for_url("**/chat", timeout=TIMEOUT)
        chat_input = page.locator(
            "textarea[placeholder='输入消息，按 Enter 发送...']"
        ).first
        chat_input.fill("部署验收码是什么？")
        chat_input.press("Enter")
        page.locator(".prose").filter(has_text=code).last.wait_for(
            state="visible", timeout=180000
        )
        # 答案出现不代表流式结束：等输入框恢复可用、思考提示消失
        page.wait_for_function(
            """() => {
                const el = document.querySelector(
                    "textarea[placeholder='输入消息，按 Enter 发送...']"
                );
                return el && !el.disabled;
            }""",
            timeout=TIMEOUT,
        )
        page.get_by_text("正在思考...").first.wait_for(state="hidden", timeout=5000)
        print("[PASS] 6/7 对话框提问、流式结束并看到带验收码的回答")

        os.makedirs(os.path.dirname(SUCCESS_SCREENSHOT), exist_ok=True)
        page.screenshot(path=SUCCESS_SCREENSHOT, full_page=True)
        _check(not page_errors, f"页面有未捕获异常: {page_errors[:3]}")
        print(f"[PASS] 7/7 无未捕获前端异常（截图 {SUCCESS_SCREENSHOT}）")
        return 0
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        if page is not None:
            try:
                os.makedirs(os.path.dirname(SCREENSHOT), exist_ok=True)
                page.screenshot(path=SCREENSHOT, full_page=True)
                print(f"[FAIL] 截图: {SCREENSHOT}", file=sys.stderr)
            except Exception:
                pass
        return 1
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
        if token:
            _delete_document(token, filename)
        try:
            os.remove(temp_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
