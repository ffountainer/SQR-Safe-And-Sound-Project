from datetime import datetime, timedelta, timezone

import pytest

import src.db as db


def test_to_utc_datetime_from_naive_iso_string():
    result = db._to_utc_datetime("2026-04-12T10:00:00")

    assert result is not None
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_check_status_for_simple_cases():
    assert db.check_status(None, datetime.now(timezone.utc)) == ("free", None)
    assert db.check_status("unavailable", datetime.now(timezone.utc)) == ("unavailable", None)
    assert db.check_status("free", datetime.now(timezone.utc)) == ("free", None)


def test_infer_status_busy_with_time_remaining():
    report_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    status, estimated = db._infer_status("busy", report_time, 20)

    assert status == "busy"
    assert estimated is not None


def test_get_status_maps_rows_from_fetch_machines(monkeypatch):
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(
        db,
        "fetch_machines",
        lambda: [
            {
                "id": 1,
                "name": "B1 F2 Washer 1",
                "type": "wash",
                "floor": 2,
                "building": "1",
                "report_timestamp": datetime.now(timezone.utc).isoformat(),
                "report_status": "busy",
                "report_time_remaining": 10,
                "report_reporter_name": "Alice",
            }
        ],
    )

    result = db.get_status()

    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["inferred_status"] == "busy"
    assert result[0]["reported_status"] == "busy"
    assert result[0]["last_reporter_name"] == "Alice"


def test_get_machine_history_valid_row_mapping(monkeypatch):
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda machine_id: True)
    monkeypatch.setattr(
        db,
        "fetch_machine_history",
        lambda machine_id, limit=10: [
            {
                "id": 5,
                "machine_id": machine_id,
                "timestamp": datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc).isoformat(),
                "status": "free",
                "time_remaining": None,
                "reporter_name": "Bob",
            }
        ],
    )

    result = db.get_machine_history(1, limit=1)

    assert len(result) == 1
    assert result[0]["machine_id"] == 1
    assert result[0]["status"] == "free"
    assert result[0]["reporter_name"] == "Bob"


def test_save_report_accepts_dict_input(monkeypatch):
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda machine_id: True)

    captured = {}

    def fake_insert_report(machine_id, status, time_remaining=None, reporter_name=None):
        captured["machine_id"] = machine_id
        captured["status"] = status
        captured["time_remaining"] = time_remaining
        captured["reporter_name"] = reporter_name
        return {
            "id": 11,
            "machine_id": machine_id,
            "timestamp": datetime(2026, 4, 12, 13, 0, tzinfo=timezone.utc).isoformat(),
            "status": status,
            "time_remaining": time_remaining,
            "reporter_name": reporter_name,
        }

    monkeypatch.setattr(db, "insert_report", fake_insert_report)

    result = db.save_report(
        {
            "machine_id": 1,
            "status": "busy",
            "time_remaining": 25,
            "reporter_name": "Uljana",
        }
    )

    assert captured["machine_id"] == 1
    assert captured["status"] == "busy"
    assert captured["time_remaining"] == 25
    assert result["status"] == "busy"
    assert result["reporter_name"] == "Uljana"


def test_save_report_rejects_invalid_status(monkeypatch):
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)

    with pytest.raises(ValueError, match="status must be one of"):
        db.save_report(1, "wrong-status")


def test_create_notification_trims_message(monkeypatch):
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda machine_id: True)

    captured = {}

    def fake_insert_notification(machine_id, message, level="info"):
        captured["machine_id"] = machine_id
        captured["message"] = message
        captured["level"] = level
        return {
            "id": 7,
            "machine_id": machine_id,
            "message": message,
            "level": level,
            "created_at": datetime(2026, 4, 12, 14, 0, tzinfo=timezone.utc).isoformat(),
        }

    monkeypatch.setattr(db, "insert_notification", fake_insert_notification)

    result = db.create_notification(
        {"machine_id": 1, "message": "  check machine  ", "level": "warning"}
    )

    assert captured["message"] == "check machine"
    assert captured["level"] == "warning"
    assert result["message"] == "check machine"


def test_create_notification_rejects_bad_level(monkeypatch):
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda machine_id: True)

    with pytest.raises(ValueError, match="level must be one of"):
        db.create_notification(
            {"machine_id": 1, "message": "hello", "level": "fatal"}
        )