from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

import src.api as api


def test_raise_http_from_value_error_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        api._raise_http_from_value_error(
            ValueError("machine_id does not exist")
        )
    assert exc_info.value.status_code == 404


def test_raise_http_from_value_error_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        api._raise_http_from_value_error(ValueError("bad request"))
    assert exc_info.value.status_code == 400


def test_post_report_success(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(
        api,
        "save_report",
        lambda machine_id, status, time_remaining, reporter_name: {
            "id": 1,
            "machine_id": machine_id,
            "timestamp": now,
            "status": status,
            "time_remaining": time_remaining,
            "reporter_name": reporter_name,
        },
    )

    body = api.ReportIn(
        machine_id=1,
        status="busy",
        time_remaining=15,
        reporter_name="amy",
    )
    out = api.post_report(body)

    assert out.id == 1
    assert out.machine_id == 1
    assert out.status == "busy"


def test_post_report_handles_service_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api,
        "save_report",
        lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(ValueError("machine_id does not exist")),
    )

    body = api.ReportIn(machine_id=1, status="free")
    with pytest.raises(HTTPException) as exc_info:
        api.post_report(body)
    assert exc_info.value.status_code == 404


def test_list_machines_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api,
        "get_status",
        lambda: [
            {
                "id": 1,
                "name": "W1",
                "type": "wash",
                "inferred_status": "free",
            }
        ],
    )
    out = api.list_machines()
    assert out[0]["id"] == 1


def test_machine_history_limit_validation() -> None:
    with pytest.raises(HTTPException) as exc_info:
        api.machine_history(1, limit=0)
    assert exc_info.value.status_code == 400


def test_machine_history_value_error_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api,
        "get_machine_history",
        lambda machine_id, limit: (
            _ for _ in ()
        ).throw(ValueError("not found")),
    )

    with pytest.raises(HTTPException) as exc_info:
        api.machine_history(3, limit=10)
    assert exc_info.value.status_code == 404


def test_machine_history_success(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        api,
        "get_machine_history",
        lambda machine_id, limit: [
            {
                "id": 10,
                "machine_id": machine_id,
                "timestamp": now,
                "status": "free",
                "time_remaining": None,
                "reporter_name": None,
            }
        ],
    )

    out = api.machine_history(2, limit=5)
    assert out[0]["machine_id"] == 2
