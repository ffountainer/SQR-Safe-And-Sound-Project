import random

from locust import HttpUser, between, task


class LaundryApiUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(5)
    def list_machines(self) -> None:
        self.client.get("/machines", name="GET /machines")

    @task(3)
    def machine_history(self) -> None:
        machine_id = random.randint(1, 20)
        self.client.get(
            f"/machines/{machine_id}/history?limit=20",
            name="GET /machines/:id/history",
        )

    @task(1)
    def post_report(self) -> None:
        machine_id = random.randint(1, 20)
        status = random.choice(["busy", "free", "unavailable"])
        payload = {
            "machine_id": machine_id,
            "status": status,
            "time_remaining": random.randint(5, 60) if status == "busy" else None,
            "reporter_name": "locust",
        }
        self.client.post("/report", json=payload, name="POST /report")
