# test_business_logic.py

from datetime import datetime, timedelta, timezone


from src.business_logic import (
    STATUS_FREE,
    STATUS_BUSY,
    STATUS_UNAVAILABLE,
    INFERRED_FREE,
    INFERRED_BUSY,
    INFERRED_PROBABLY_FREE,
    INFERRED_UNAVAILABLE,
    DEFAULT_BUSY_ASSUMPTION,
    check_status,
    infer_inferred_status,
)


def utc(y, m, d, h=0, min=0, s=0):
    return datetime(y, m, d, h, min, s, tzinfo=timezone.utc)


def test_check_status_none():
    assert check_status(None) == INFERRED_FREE


def test_check_status_free():
    assert check_status(STATUS_FREE) == INFERRED_FREE


def test_check_status_unavailable():
    assert check_status(STATUS_UNAVAILABLE) == INFERRED_UNAVAILABLE


def test_check_status_unknown():
    assert check_status("random") == INFERRED_FREE


def test_check_status_busy_returns_none():
    assert check_status(STATUS_BUSY) is None


def test_no_report_returns_free():
    now = utc(2026, 4, 1)
    assert infer_inferred_status(None, None, None, now) == INFERRED_FREE


def test_unavailable_passthrough():
    now = utc(2026, 4, 1)
    rt = utc(2026, 4, 1, 10)

    assert (
        infer_inferred_status(
            STATUS_UNAVAILABLE, rt, 10, now) == INFERRED_UNAVAILABLE
    )


def test_free_passthrough():
    now = utc(2026, 4, 1)
    rt = utc(2026, 4, 1, 10)

    assert infer_inferred_status(STATUS_FREE, rt, 10, now) == INFERRED_FREE


def test_unknown_status_defaults_to_free():
    now = utc(2026, 4, 1)
    rt = utc(2026, 4, 1, 10)

    assert infer_inferred_status("weird", rt, None, now) == INFERRED_FREE


def test_busy_before_timer_end():
    rt = utc(2026, 4, 1, 10)
    now = rt + timedelta(minutes=9)

    assert infer_inferred_status(STATUS_BUSY, rt, 10, now) == INFERRED_BUSY


def test_busy_exactly_at_end_is_free():
    rt = utc(2026, 4, 1, 10)
    now = rt + timedelta(minutes=10)

    assert infer_inferred_status(STATUS_BUSY, rt, 10, now) == INFERRED_FREE


def test_busy_after_end_is_free():
    rt = utc(2026, 4, 1, 10)
    now = rt + timedelta(minutes=11)

    assert infer_inferred_status(STATUS_BUSY, rt, 10, now) == INFERRED_FREE


def test_busy_without_timer_inside_window():
    rt = utc(2026, 4, 1, 10)
    now = rt + DEFAULT_BUSY_ASSUMPTION / 2

    assert infer_inferred_status(STATUS_BUSY, rt, None, now) == INFERRED_BUSY


def test_busy_without_timer_after_window():
    rt = utc(2026, 4, 1, 10)
    now = rt + DEFAULT_BUSY_ASSUMPTION + timedelta(seconds=1)
    assert infer_inferred_status(
        STATUS_BUSY, rt, None, now) == INFERRED_PROBABLY_FREE


def test_busy_without_timer_exact_cutoff_not_busy():
    rt = utc(2026, 4, 1, 10)
    now = rt + DEFAULT_BUSY_ASSUMPTION

    # boundary condition
    assert infer_inferred_status(STATUS_BUSY, rt, None, now) != INFERRED_BUSY


def test_busy_without_report_time_is_free():
    now = utc(2026, 4, 1)

    assert infer_inferred_status(STATUS_BUSY, None, 10, now) == INFERRED_FREE


def test_minutes_parameter_matters():
    rt = utc(2026, 4, 1, 10)
    now = rt + timedelta(minutes=20)

    with_timer = infer_inferred_status(STATUS_BUSY, rt, 5, now)
    without_timer = infer_inferred_status(STATUS_BUSY, rt, None, now)
    assert with_timer != without_timer


def test_naive_and_aware_datetimes_same_result():
    rt_naive = datetime(2026, 4, 1, 10, 0, 0)
    now_naive = datetime(2026, 4, 1, 11, 0, 0)

    rt_aware = rt_naive.replace(tzinfo=timezone.utc)
    now_aware = now_naive.replace(tzinfo=timezone.utc)

    r1 = infer_inferred_status(STATUS_BUSY, rt_naive, 30, now_naive)
    r2 = infer_inferred_status(STATUS_BUSY, rt_aware, 30, now_aware)

    assert r1 == r2


def test_timezone_is_removed_from_aware_datetime():
    from src.business_logic import _naive

    aware = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
    result = _naive(aware)

    # must remove tzinfo
    assert result.tzinfo is None


def test_same_input_same_output():
    rt = utc(2026, 4, 1, 10)
    now = utc(2026, 4, 1, 11)

    r1 = infer_inferred_status(STATUS_BUSY, rt, 10, now)
    r2 = infer_inferred_status(STATUS_BUSY, rt, 10, now)

    assert r1 == r2
