from datetime import datetime, timezone

from fastapi.testclient import TestClient

import src.api as api


client = TestClient(api.app)


def test_list_machines_returns_mocked_data(monkeypatch):
    monkeypatch.setattr(
        api,
        "get_status",
        lambda: [
            {
                "id": 1,
                "name": "Washer 1",
                "type": "wash",
                "floor": 2,
                "building": "1",
                "inferred_status": "free",
                "time_remaining": None,
                "reported_status": "free",
                "last_report_at": None,
                "estimated_free_at": None,
                "last_reporter_name": None,
            }
        ],
    )

    response = client.get("/machines")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["inferred_status"] == "free"


def test_post_report_success(monkeypatch):
    monkeypatch.setattr(
        api,
        "save_report",
        lambda machine_id, status, time_remaining, reporter_name: {
            "id": 10,
            "machine_id": machine_id,
            "timestamp": datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc).isoformat(),
            "status": status,
            "time_remaining": time_remaining,
            "reporter_name": reporter_name,
        },
    )

    response = client.post(
        "/report",
        json={
            "machine_id": 1,
            "status": "busy",
            "time_remaining": 15,
            "reporter_name": "Uljana",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["machine_id"] == 1
    assert data["status"] == "busy"
    assert data["time_remaining"] == 15
    assert data["reporter_name"] == "Uljana"


def test_post_report_unknown_machine_becomes_404(monkeypatch):
    def fake_save_report(*args, **kwargs):
        raise ValueError("machine_id does not exist")

    monkeypatch.setattr(api, "save_report", fake_save_report)

    response = client.post(
        "/report",
        json={"machine_id": 999, "status": "free"},
    )

    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_post_report_bad_input_becomes_400(monkeypatch):
    def fake_save_report(*args, **kwargs):
        raise ValueError("status must be one of: free, busy, unavailable")

    monkeypatch.setattr(api, "save_report", fake_save_report)

    response = client.post(
        "/report",
        json={"machine_id": 1, "status": "free"},
    )

    assert response.status_code == 400
    assert "status must be one of" in response.json()["detail"]


def test_machine_history_rejects_bad_limit():
    response = client.get("/machines/1/history?limit=0")

    assert response.status_code == 400
    assert "limit must be between 1 and 200" in response.json()["detail"]


def test_machine_history_unknown_machine_becomes_404(monkeypatch):
    def fake_history(machine_id, limit=20):
        raise ValueError("machine_id does not exist")

    monkeypatch.setattr(api, "get_machine_history", fake_history)

    response = client.get("/machines/999/history")

    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]