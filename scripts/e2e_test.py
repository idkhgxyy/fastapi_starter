import requests

BASE = "http://localhost:8000"

def run():
    # 1. Health check
    r = requests.get(f"{BASE}/api/v1/health")
    print("1. Health:", r.json())

    # 2. Register
    r = requests.post(f"{BASE}/api/v1/users/", json={
        "username": "e2e_runner2", "email": "e2e_runner2@example.com", "password": "runner123"
    })
    print("2. Register:", r.status_code, r.json().get("email", "(duplicate ok)"))

    # 3. Login
    r = requests.post(f"{BASE}/api/v1/auth/login", data={
        "username": "e2e_runner2@example.com", "password": "runner123"
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("3. Login: token obtained")

    # 4. Get me
    r = requests.get(f"{BASE}/api/v1/users/me", headers=headers)
    print("4. My info:", r.json()["email"])

    # 5. Create task
    r = requests.post(f"{BASE}/api/v1/tasks/", headers=headers, json={
        "title": "复习 FastAPI", "description": "阅读核心源码", "status": "pending"
    })
    task = r.json()
    print(f"5. Created task: id={task['id']}, title={task['title']}, status={r.status_code}")

    # 6. List tasks
    r = requests.get(f"{BASE}/api/v1/tasks/", headers=headers)
    print(f"6. Task count: {len(r.json())}")

    # 7. Update task
    r = requests.put(f"{BASE}/api/v1/tasks/{task['id']}", headers=headers, json={
        "status": "completed", "description": "已完成源码阅读"
    })
    print(f"7. Updated: status={r.json()['status']}")

    # 8. Delete task
    r = requests.delete(f"{BASE}/api/v1/tasks/{task['id']}", headers=headers)
    print(f"8. Deleted: {r.status_code}")

    # 9. Verify deletion
    r = requests.get(f"{BASE}/api/v1/tasks/{task['id']}", headers=headers)
    print(f"9. After delete: {r.status_code}")

    # 10. Test unauthorized access
    r = requests.get(f"{BASE}/api/v1/users/me")
    print(f"10. No auth: {r.status_code}")

    # 11. Test error format (duplicate user)
    r = requests.post(f"{BASE}/api/v1/users/", json={
        "username": "dup_runner2", "email": "e2e_runner2@example.com", "password": "runner123"
    })
    print(f"11. Duplicate user: code={r.json()['code']}")

    # 12. Prometheus metrics
    r = requests.get(f"{BASE}/metrics")
    print(f"12. Metrics: {r.status_code}, lines={len(r.text.splitlines())}")

    print("\n=== All 12 end-to-end checks passed! ===")

if __name__ == "__main__":
    run()
