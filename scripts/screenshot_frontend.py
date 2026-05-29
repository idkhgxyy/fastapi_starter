"""Take screenshots of the frontend SPA for README demo images."""
import os
from playwright.sync_api import sync_playwright

OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'images')
os.makedirs(OUTPUT, exist_ok=True)

BASE = 'http://localhost:5177'

MOCK_TOKEN = 'mock-jwt-token.demo.xxx'
MOCK_USER = '{"id":1,"username":"DemoUser","email":"demo@example.com","has_custom_llm_key":false}'


def screenshot(page, name, **kwargs):
    path = os.path.join(OUTPUT, name)
    page.screenshot(path=path, **kwargs)
    print(f'  ✓ {name}')
    return path


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            device_scale_factor=2,
        )

        # 1. Login page
        page = context.new_page()
        page.goto(f'{BASE}/auth/login')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(500)
        screenshot(page, 'login-page.png', full_page=True)
        page.close()

        # 2. Mock-authenticated browsing
        context.add_init_script(f"""
            localStorage.setItem('agent_token', '{MOCK_TOKEN}');
            localStorage.setItem('agent_user', '{MOCK_USER}');
        """)

        # Chat page
        page = context.new_page()
        page.goto(f'{BASE}/chat')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(800)
        screenshot(page, 'chat-empty.png', full_page=True)

        # Open sidebar
        sidebar_btn = page.locator('nav button').first
        if sidebar_btn:
            sidebar_btn.click()
            page.wait_for_timeout(400)

        # Chat with sidebar open
        screenshot(page, 'chat-with-sidebar.png', full_page=True)
        page.close()

        # Knowledge page
        page = context.new_page()
        page.goto(f'{BASE}/knowledge')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(600)
        screenshot(page, 'knowledge-page.png', full_page=True)
        page.close()

        # Tasks page
        page = context.new_page()
        page.goto(f'{BASE}/tasks')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(600)
        screenshot(page, 'tasks-page.png', full_page=True)
        page.close()

        # Observability page
        page = context.new_page()
        page.goto(f'{BASE}/observability')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        screenshot(page, 'observability-page.png', full_page=True)
        page.close()

        # Settings page
        page = context.new_page()
        page.goto(f'{BASE}/settings')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(600)
        screenshot(page, 'settings-page.png', full_page=True)
        page.close()

        # Health page
        page = context.new_page()
        page.goto(f'{BASE}/health')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(600)
        screenshot(page, 'health-page.png', full_page=True)
        page.close()

        browser.close()
        print(f'\nAll screenshots saved to {OUTPUT}/')


if __name__ == '__main__':
    main()
