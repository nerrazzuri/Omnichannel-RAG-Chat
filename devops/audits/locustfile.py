from locust import HttpUser, TaskSet, task, between
import os


class HealthTasks(TaskSet):
    @task(3)
    def health(self):
        self.client.get("/v1/health", name="GET /v1/health")

    @task(2)
    def ready(self):
        self.client.get("/v1/ready", name="GET /v1/ready")


class WebsiteUser(HttpUser):
    tasks = [HealthTasks]
    wait_time = between(0.1, 0.5)

    def on_start(self):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow overriding host via environment variable
        base = os.getenv("AI_CORE_URL")
        if base:
            self.host = base.rstrip("/")

