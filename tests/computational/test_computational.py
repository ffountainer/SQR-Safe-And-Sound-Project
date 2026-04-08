from datetime import datetime, timedelta, timezone

import pytest

from src.business_logic import (
    INFERRED_BUSY,
    INFERRED_FREE,
    INFERRED_PROBABLY_FREE,
    infer_inferred_status,
)
from src.external_api import _parse_first_point
from streamlit_app import (
    compute_remaining_minutes,
    extract_building,
    extract_floor,
    filter_and_sort_machines,
    get_display_status,
    normalize_status,
)


def test_infer_inferred_status_busy_with_timer_before_and_after_end():
    report_time = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)

    before_end = infer_inferred_status(
        "busy",
        report_time,
        15,
        report_time + timedelta(minutes=10),
    )
    after_end = infer_inferred_status(
        "busy",
        report_time,
        15,
        report_time + timedelta(minutes=16),
    )

    assert before_end == INFERRED_BUSY
    assert after_end == INFERRED_FREE


def test_infer_inferred_status_busy_without_timer_becomes_probably_free():
    report_time = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)

    still_busy = infer_inferred_status(
        "busy",
        report_time,
        None,
        report_time + timedelta(hours=2),
    )
    probably_free = infer_inferred_status(
        "busy",
        report_time,
        None,
        report_time + timedelta(hours=4, seconds=1),
    )

    assert still_busy == INFERRED_BUSY
    assert probably_free == INFERRED_PROBABLY_FREE


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("unavailable", "unavailable"),
        ("available", "free"),
        ("В процессе", "busy"),
        (None, "unknown"),
    ],
)
def test_normalize_status_examples(raw_status, expected):
    assert normalize_status(raw_status) == expected


def test_extract_floor_and_building_support_alternative_keys():
    machine = {
        "level": "not-a-number",
        "этаж": "3",
        "корпус": " 2 ",
    }

    assert extract_floor(machine) == 3
    assert extract_building(machine) == "2"


def test_compute_remaining_minutes_uses_estimated_free_at():
    now = datetime.now(timezone.utc)
    machine = {
        "estimated_free_at": (now + timedelta(minutes=12, seconds=5)).isoformat(),
        "last_report_at": (now - timedelta(minutes=50)).isoformat(),
        "time_remaining": 999,
    }

    remaining = compute_remaining_minutes(machine)

    assert remaining is not None
    assert 11 <= remaining <= 12


def test_get_display_status_turns_free_into_busy_when_time_left():
    now = datetime.now(timezone.utc)
    machine = {
        "reported_status": "free",
        "estimated_free_at": (now + timedelta(minutes=5, seconds=5)).isoformat(),
    }

    assert get_display_status(machine) == "busy"


def test_filter_and_sort_machines_filters_and_orders_by_status():
    now = datetime.now(timezone.utc)

    machines = [
        {
            "id": 2,
            "name": "Washer B",
            "building": "1",
            "floor": 2,
            "reported_status": "busy",
            "estimated_free_at": (now + timedelta(minutes=20)).isoformat(),
        },
        {
            "id": 1,
            "name": "Washer A",
            "building": "1",
            "floor": 2,
            "reported_status": "free",
        },
        {
            "id": 3,
            "name": "Dryer C",
            "building": "1",
            "floor": 2,
            "inferred_status": "unavailable",
        },
        {
            "id": 4,
            "name": "Other floor",
            "building": "1",
            "floor": 3,
            "reported_status": "free",
        },
    ]

    result = filter_and_sort_machines(
        machines,
        selected_building="1",
        selected_floor=2,
    )

    assert [machine["id"] for machine in result] == [1, 2, 3]


def test_parse_first_point_extracts_coordinates():
    data = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {
                        "GeoObject": {
                            "Point": {
                                "pos": "49.1221 55.7887"
                            }
                        }
                    }
                ]
            }
        }
    }

    assert _parse_first_point(data) == (49.1221, 55.7887)