"""
property-based tests (Hypothesis) for laundry status inference.

goal: fuzz inputs and assert invariants / spec rules so anomalies surface as failing examples.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.business_logic import (
    DEFAULT_BUSY_ASSUMPTION,
    INFERRED_BUSY,
    INFERRED_FREE,
    INFERRED_PROBABLY_FREE,
    INFERRED_UNAVAILABLE,
    infer_inferred_status,
)

# every value the api can return for inferred_status
_INFERRED = {INFERRED_FREE, INFERRED_BUSY, INFERRED_PROBABLY_FREE, INFERRED_UNAVAILABLE}

# bounded naive datetimes; we normalize to UTC
_dt = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2035, 12, 31, 23, 59, 59),
)
_minutes = st.integers(min_value=0, max_value=7 * 24 * 60)  # up to one week

_hyp = settings(max_examples=200)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@_hyp
@given(_dt)
def test_no_report_always_free(now: datetime) -> None:
    out = infer_inferred_status(None, None, None, _utc(now))
    assert out == INFERRED_FREE
    assert out in _INFERRED


@_hyp
@given(_dt, _dt, st.one_of(st.none(), _minutes))
def test_unavailable_is_stable(report_time: datetime, now: datetime, minutes: int | None) -> None:
    rt = _utc(report_time)
    n = _utc(now)
    out = infer_inferred_status("unavailable", rt, minutes, n)
    assert out == INFERRED_UNAVAILABLE
    assert out in _INFERRED


@_hyp
@given(_dt, _dt, st.one_of(st.none(), _minutes))
def test_free_is_stable(report_time: datetime, now: datetime, minutes: int | None) -> None:
    rt = _utc(report_time)
    n = _utc(now)
    out = infer_inferred_status("free", rt, minutes, n)
    assert out == INFERRED_FREE


@_hyp
@given(_dt, _minutes)
def test_busy_with_timer_before_end_busy_after_free(report_time: datetime, minutes: int) -> None:
    assume(minutes > 0)
    rt = _utc(report_time)
    ends = rt + timedelta(minutes=minutes)
    before_n = rt + timedelta(minutes=minutes - 1)
    assume(before_n < ends)

    assert infer_inferred_status("busy", rt, minutes, before_n) == INFERRED_BUSY
    after_n = ends + timedelta(seconds=1)
    assert infer_inferred_status("busy", rt, minutes, after_n) == INFERRED_FREE


@_hyp
@given(_dt)
def test_busy_without_timer_four_hour_window(report_time: datetime) -> None:
    rt = _utc(report_time)
    cut = rt + DEFAULT_BUSY_ASSUMPTION
    inside = rt + (cut - rt) / 2
    outside = cut + timedelta(seconds=1)
    assert infer_inferred_status("busy", rt, None, inside) == INFERRED_BUSY
    assert infer_inferred_status("busy", rt, None, outside) == INFERRED_PROBABLY_FREE


@_hyp
@given(st.text(min_size=1, max_size=20))
def test_unknown_status_string_fails_safe_to_free(label: str) -> None:
    assume(label not in {"free", "busy", "unavailable"})
    now = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
    out = infer_inferred_status(label, now, None, now)
    assert out == INFERRED_FREE


@_hyp
@given(_dt, _dt, st.one_of(st.none(), _minutes))
def test_output_is_always_valid_enum(report_time: datetime, now: datetime, minutes: int | None) -> None:
    rt = _utc(report_time)
    n = _utc(now)
    for status in ("free", "busy", "unavailable", None):
        out = infer_inferred_status(status, rt, minutes, n)
        assert out in _INFERRED


@_hyp
@given(_dt)
def test_busy_without_report_time_is_free(now: datetime) -> None:
    n = _utc(now)
    assert infer_inferred_status("busy", None, 10, n) == INFERRED_FREE
