"""
functions that turn the last report + current time into
what users should see (status text for the laundry board).
call infer_inferred_status from
db.get_status when building GET /machines.
"""

from __future__ import annotations

from datetime import datetime, timedelta


# values stored when smbd submits a report
STATUS_FREE = "free"  # pragma: no mutate
STATUS_BUSY = "busy"  # pragma: no mutate
STATUS_UNAVAILABLE = "unavailable"  # pragma: no mutate

# values returned by GET /machines
# strings in GET /machines inferred_status
#  - use in api models / streamlit colours
INFERRED_FREE = "free"  # pragma: no mutate
INFERRED_BUSY = "busy"  # pragma: no mutate
INFERRED_PROBABLY_FREE = "probably_free"  # pragma: no mutate
INFERRED_UNAVAILABLE = "unavailable"  # pragma: no mutate

# when "busy" without deadline,
# use default (project requirement: 4 hours)
DEFAULT_BUSY_ASSUMPTION = timedelta(hours=4)  # pragma: no mutate


def _naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt  # pragma: no mutate
    return dt.replace(tzinfo=None)  # pragma: no mutate


def check_status(latest_status):
    if latest_status is None:
        return INFERRED_FREE

    if latest_status == STATUS_UNAVAILABLE:
        return INFERRED_UNAVAILABLE

    if latest_status == STATUS_FREE:
        return INFERRED_FREE

    if latest_status != STATUS_BUSY:
        # unknown label in db - fail safe
        return INFERRED_FREE  # pragma: no mutate
    else:
        return None


def infer_inferred_status(
    latest_status: str | None,
    report_time: datetime | None,
    time_remaining_minutes: int | None,
    now: datetime,
) -> str:
    """
    latest_status / report_time /
    time_remaining come from the newest report row.
    if there is no report yet, we treat the machine as free.
    """
    now_n = _naive(now)

    check = check_status(latest_status)

    if check is not None:
        return check

    if report_time is None:
        return INFERRED_FREE

    report_n = _naive(report_time)

    # busy + optional timer
    if time_remaining_minutes is not None:
        ends_at = report_n + timedelta(minutes=time_remaining_minutes)
        if now_n < ends_at:
            return INFERRED_BUSY
        return INFERRED_FREE

    assumed_busy_until = report_n + DEFAULT_BUSY_ASSUMPTION
    if now_n < assumed_busy_until:
        return INFERRED_BUSY
    return INFERRED_PROBABLY_FREE
