"""
End-to-End tests for the Laundry Status API.

These tests simulate real user interactions with the API,
testing the full request-response cycle.
"""

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.db_middleware import init_db, seed_machines_if_empty


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Initialize and seed the database before running tests."""
    init_db()
    seed_machines_if_empty()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_get_machines_returns_list(client):
    """Test that GET /machines returns a list of machines."""
    response = client.get("/machines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:  # If there are machines
        machine = data[0]
        assert "id" in machine
        assert "name" in machine
        assert "inferred_status" in machine


def test_post_report_valid_data(client):
    """Test posting a valid report."""
    payload = {
        "machine_id": 1,
        "status": "busy",
        "time_remaining": 30,
        "reporter_name": "test_user"
    }
    response = client.post("/report", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["machine_id"] == 1
    assert data["status"] == "busy"


def test_post_report_invalid_machine_id(client):
    """Test posting a report with invalid machine_id."""
    payload = {
        "machine_id": 99999,  # Assuming this doesn't exist
        "status": "busy",
        "time_remaining": 30
    }
    response = client.post("/report", json=payload)
    # Depending on implementation, might be 404 or 400
    assert response.status_code in [400, 404]


def test_post_report_invalid_status(client):
    """Test posting a report with invalid status."""
    payload = {
        "machine_id": 1,
        "status": "invalid_status",
        "time_remaining": 30
    }
    response = client.post("/report", json=payload)
    assert response.status_code == 422  # Validation error


def test_get_machine_history(client):
    """Test getting history for a machine."""
    # First post a report to have some history
    payload = {
        "machine_id": 1,
        "status": "free",
        "reporter_name": "test_user"
    }
    client.post("/report", json=payload)

    response = client.get("/machines/1/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        history_item = data[0]
        assert "status" in history_item
        assert "timestamp" in history_item


def test_full_workflow(client):
    """Test a full workflow: report busy, check status, report free."""
    # Report machine as busy
    payload_busy = {
        "machine_id": 1,
        "status": "busy",
        "time_remaining": 10,
        "reporter_name": "test_user"
    }
    response = client.post("/report", json=payload_busy)
    assert response.status_code == 201

    # Get machines and check status
    response = client.get("/machines")
    assert response.status_code == 200
    machines = response.json()
    machine = next((m for m in machines if m["id"] == 1), None)
    assert machine is not None
    assert machine["inferred_status"] == "busy"

    # Report as free
    payload_free = {
        "machine_id": 1,
        "status": "free",
        "reporter_name": "test_user"
    }
    response = client.post("/report", json=payload_free)
    assert response.status_code == 201

    # Check status again
    response = client.get("/machines")
    assert response.status_code == 200
    machines = response.json()
    machine = next((m for m in machines if m["id"] == 1), None)
    assert machine is not None
    assert machine["inferred_status"] == "free"