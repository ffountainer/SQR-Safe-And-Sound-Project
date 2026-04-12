from datetime import datetime, timedelta, timezone

import pytest

import src.db as db


def test_ensure_db_ready_calls_init_and_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(db, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(db, "seed_machines_if_empty", lambda: calls.append("seed"))

    db._ensure_db_ready()

    assert calls == ["init", "seed"]


def test_to_utc_datetime_variants() -> None:
    assert db._to_utc_datetime(None) is None

    naive = datetime(2026, 1, 1, 10, 0, 0)
    converted_naive = db._to_utc_datetime(naive)
    assert converted_naive is not None
    assert converted_naive.tzinfo == timezone.utc

    aware = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert db._to_utc_datetime(aware) == aware

    as_str = "2026-01-01T10:00:00"
    converted_str = db._to_utc_datetime(as_str)
    assert converted_str is not None
    assert converted_str.tzinfo == timezone.utc


def test_check_status_paths() -> None:
    assert db.check_status(None, None) == ("free", None)
    assert db.check_status("unavailable", datetime.now(timezone.utc)) == ("unavailable", None)
    assert db.check_status("free", datetime.now(timezone.utc)) == ("free", None)
    assert db.check_status("broken", datetime.now(timezone.utc)) == ("free", None)
    assert db.check_status("busy", None) == ("free", None)
    assert db.check_status("busy", datetime.now(timezone.utc)) is None


def test_infer_status_busy_with_and_without_timer() -> None:
    now = datetime.now(timezone.utc)

    busy, eta_busy = db._infer_status("busy", now - timedelta(minutes=5), 15)
    free, eta_free = db._infer_status("busy", now - timedelta(minutes=30), 10)
    maybe_busy, eta_maybe_busy = db._infer_status("busy", now - timedelta(hours=1), None)
    probably_free, eta_probably = db._infer_status("busy", now - timedelta(hours=5), None)

    assert busy == "busy"
    assert eta_busy is not None
    assert free == "free"
    assert eta_free is not None
    assert maybe_busy == "busy"
    assert eta_maybe_busy is not None
    assert probably_free == "probably_free"
    assert eta_probably is not None


def test_get_status_transforms_machine_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": 1,
            "name": "W1",
            "type": "wash",
            "floor": 1,
            "building": "1",
            "report_timestamp": (now - timedelta(minutes=2)).isoformat(),
            "report_status": "busy",
            "report_time_remaining": 20,
            "report_reporter_name": "alice",
        }
    ]
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "fetch_machines", lambda: rows)

    out = db.get_status()

    assert len(out) == 1
    assert out[0]["id"] == 1
    assert out[0]["inferred_status"] == "busy"
    assert out[0]["last_reporter_name"] == "alice"


def test_get_machine_history_success_and_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda machine_id: machine_id == 1)
    monkeypatch.setattr(
        db,
        "fetch_machine_history",
        lambda machine_id, limit: [
            {
                "id": 10,
                "machine_id": machine_id,
                "timestamp": now,
                "status": "free",
                "time_remaining": None,
                "reporter_name": "bob",
            }
        ],
    )

    out = db.get_machine_history(1, limit=5)
    assert out[0]["machine_id"] == 1
    assert out[0]["reporter_name"] == "bob"

    with pytest.raises(ValueError, match="positive"):
        db.get_machine_history(0, limit=5)
    with pytest.raises(ValueError, match="positive"):
        db.get_machine_history(1, limit=0)
    with pytest.raises(ValueError, match="does not exist"):
        db.get_machine_history(2, limit=5)


@pytest.mark.parametrize("machine_id", [0, -1, "1"])
def test_isinstance_machine_rejects_bad_values(machine_id) -> None:
    with pytest.raises(ValueError, match="machine_id"):
        db.isinstance_machine(machine_id)


def test_is_valid_status_rejects_bad_value() -> None:
    with pytest.raises(ValueError, match="status"):
        db.is_valid_status("unknown")


def test_does_time_remain_rejects_bad_values() -> None:
    with pytest.raises(ValueError, match="time_remaining"):
        db.does_time_remain(-1)
    with pytest.raises(ValueError, match="time_remaining"):
        db.does_time_remain("10")


def test_is_reporter_name_valid_rejects_bad_value() -> None:
    with pytest.raises(ValueError, match="reporter_name"):
        db.is_reporter_name_valid(123)


def test_does_machine_exist_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "machine_exists", lambda _: False)
    with pytest.raises(ValueError, match="does not exist"):
        db.does_machine_exist(999)


def test_save_report_accepts_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda _: True)
    monkeypatch.setattr(
        db,
        "insert_report",
        lambda **_: {
            "id": 7,
            "machine_id": 1,
            "timestamp": now,
            "status": "busy",
            "time_remaining": 12,
            "reporter_name": "eve",
        },
    )

    out = db.save_report(
        {
            "machine_id": 1,
            "status": "busy",
            "time_remaining": 12,
            "reporter_name": "eve",
        }
    )

    assert out["id"] == 7
    assert out["status"] == "busy"


def test_save_report_accepts_positional_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda _: True)
    monkeypatch.setattr(
        db,
        "insert_report",
        lambda **_: {
            "id": 8,
            "machine_id": 2,
            "timestamp": now,
            "status": "free",
            "time_remaining": None,
            "reporter_name": None,
        },
    )

    out = db.save_report(2, "free", None, None)

    assert out["id"] == 8
    assert out["machine_id"] == 2


def test_check_notification_validators() -> None:
    with pytest.raises(ValueError, match="machine_id"):
        db.check_machine(0)
    with pytest.raises(ValueError, match="message"):
        db.check_message("   ")
    with pytest.raises(ValueError, match="level"):
        db.check_level("fatal")


def test_check_machine_exists_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "machine_exists", lambda _: False)
    with pytest.raises(ValueError, match="does not exist"):
        db.check_machine_exists(123)


def test_create_notification_success(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(db, "_ensure_db_ready", lambda: None)
    monkeypatch.setattr(db, "machine_exists", lambda _: True)
    monkeypatch.setattr(
        db,
        "insert_notification",
        lambda **_: {
            "id": 9,
            "machine_id": 1,
            "message": "hello",
            "level": "info",
            "created_at": now,
        },
    )

    out = db.create_notification({"machine_id": 1, "message": " hello "})

    assert out["id"] == 9
    assert out["message"] == "hello"
    assert out["level"] == "info"
