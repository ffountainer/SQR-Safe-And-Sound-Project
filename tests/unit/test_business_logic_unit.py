from datetime import datetime, timedelta, timezone

from src.business_logic import (
    INFERRED_BUSY,
    INFERRED_FREE,
    INFERRED_PROBABLY_FREE,
    INFERRED_UNAVAILABLE,
    _naive,
    check_status,
    infer_inferred_status,
)


def test_naive_leaves_naive_untouched() -> None:
    dt = datetime(2026, 1, 1, 10, 0, 0)
    assert _naive(dt) is dt


def test_naive_drops_timezone() -> None:
    aware = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert _naive(aware).tzinfo is None


def test_check_status_variants() -> None:
    assert check_status(None) == INFERRED_FREE
    assert check_status("unavailable") == INFERRED_UNAVAILABLE
    assert check_status("free") == INFERRED_FREE
    assert check_status("unexpected") == INFERRED_FREE
    assert check_status("busy") is None


def test_infer_inferred_status_without_report() -> None:
    now = datetime.now(timezone.utc)
    assert infer_inferred_status(None, None, None, now) == INFERRED_FREE


def test_infer_inferred_status_busy_with_timer() -> None:
    now = datetime.now(timezone.utc)
    report_time = now - timedelta(minutes=5)

    still_busy = infer_inferred_status("busy", report_time, 10, now)
    already_free = infer_inferred_status("busy", report_time, 2, now)

    assert still_busy == INFERRED_BUSY
    assert already_free == INFERRED_FREE


def test_infer_inferred_status_busy_without_timer() -> None:
    now = datetime.now(timezone.utc)
    recent_report = now - timedelta(hours=1)
    old_report = now - timedelta(hours=5)

    assert infer_inferred_status("busy", recent_report, None, now) == INFERRED_BUSY
    assert (
        infer_inferred_status("busy", old_report, None, now)
        == INFERRED_PROBABLY_FREE
    )
