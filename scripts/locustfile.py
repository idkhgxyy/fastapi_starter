import os

from locust import HttpUser, between, task

API_V1 = "/api/v1"
TEST_USER_EMAIL = os.getenv("LOCUST_USER_EMAIL", "locust@example.com")
TEST_USER_PASSWORD = os.getenv("LOCUST_USER_PASSWORD", "locustpass123")


class FastAPIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        resp = self.client.post(
            f"{API_V1}/auth/login",
            data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        )
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}

    @task(3)
    def health_check(self):
        self.client.get(f"{API_V1}/health")

    @task(2)
    def get_me(self):
        if self.token:
            self.client.get(f"{API_V1}/users/me", headers=self.headers)

    @task(1)
    def chat_basic(self):
        if self.token:
            self.client.post(
                f"{API_V1}/chat/",
                json={"message": "你好，简单介绍一下你自己", "stream": False},
                headers=self.headers,
            )

    @task(1)
    def list_tasks(self):
        if self.token:
            self.client.get(f"{API_V1}/tasks/", headers=self.headers)
