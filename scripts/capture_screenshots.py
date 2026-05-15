import os
import time

from playwright.sync_api import sync_playwright


def main():
    os.makedirs("docs/images", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
        page = context.new_page()

        print("Capturing Swagger UI...")
        try:
            page.goto("http://localhost:8000/docs", wait_until="networkidle")
            page.wait_for_selector(".swagger-ui")
            time.sleep(2)  # wait for animations
            page.screenshot(path="docs/images/swagger-overview.png")
            print("Saved docs/images/swagger-overview.png")
        except Exception as e:
            print(f"Failed to capture Swagger: {e}")

        print("Capturing Demo Interface with mock data...")
        try:
            page.goto("http://localhost:8000/demo.html", wait_until="networkidle")
            time.sleep(1)
            # Inject fake data to make it look like a RAG session
            page.evaluate("""() => {
                document.getElementById('auth-status').innerHTML = '<span class="w-2 h-2 rounded-full bg-green-500"></span> <span class="text-green-400">已认证</span>';
                document.getElementById('docs-list').innerHTML = `
                    <li class="bg-gray-800 p-3 rounded-lg border border-gray-700 flex justify-between items-center">
                        <div class="truncate pr-2">
                            <p class="text-sm truncate text-gray-200" title="qwen_docs.txt">qwen_docs.txt</p>
                            <p class="text-xs text-gray-500 mt-1 flex items-center gap-1">
                                <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span> ready
                            </p>
                        </div>
                    </li>
                    <li class="bg-gray-800 p-3 rounded-lg border border-gray-700 flex justify-between items-center">
                        <div class="truncate pr-2">
                            <p class="text-sm truncate text-gray-200" title="system_architecture.txt">system_architecture.txt</p>
                            <p class="text-xs text-gray-500 mt-1 flex items-center gap-1">
                                <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span> ready
                            </p>
                        </div>
                    </li>
                `;
                appendMessage('user', '请根据知识库总结一下 Qwen2.5 的核心优势。');
                appendMessage('ai', '根据知识库 `qwen_docs.txt` 的内容，Qwen2.5 的核心优势包括：\\n1. **强大的语言理解能力**：支持多语言，中文表现尤为出色。\\n2. **Tool Calling 与 Agent 能力**：内置了工具调用微调，极大提升了作为 Agent 的可靠性。\\n3. **长文本支持**：支持长达 128k 的上下文。');
            }""")
            time.sleep(1)
            page.screenshot(path="docs/images/rag-query-demo.png")
            print("Saved docs/images/rag-query-demo.png")
        except Exception as e:
            print(f"Failed to capture Demo UI: {e}")

        print("Capturing Grafana Dashboard...")
        try:
            page.goto(
                "http://localhost:3000/d/fastapi-observability",
                wait_until="networkidle",
                timeout=5000,
            )
            time.sleep(2)
            page.screenshot(path="docs/images/grafana-dashboard.png")
            print("Saved docs/images/grafana-dashboard.png")
        except Exception as e:
            print(f"Grafana not reachable or dashboard missing: {e}")
            # Try just the login page if dashboard not found
            try:
                page.goto("http://localhost:3000", wait_until="networkidle", timeout=5000)
                time.sleep(2)
                page.screenshot(path="docs/images/grafana-dashboard.png")
                print("Saved docs/images/grafana-dashboard.png (Login page)")
            except:
                pass

        browser.close()


if __name__ == "__main__":
    main()
