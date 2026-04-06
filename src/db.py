"""Service-layer DB logic used by API and frontend endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from src.db_middleware import (
	fetch_machine_history,
	fetch_machines,
	init_db,
	insert_notification,
	insert_report,
	machine_exists,
	seed_machines_if_empty,
)

VALID_STATUSES = {"free", "busy", "unavailable"}
VALID_NOTIFICATION_LEVELS = {"info", "warning", "error"}
BUSY_NO_END_FALLBACK = timedelta(hours=4)


def _ensure_db_ready() -> None:
	init_db()
	seed_machines_if_empty()


def _to_utc_datetime(value: Any) -> datetime | None:
	if value is None:
		return None
	if isinstance(value, datetime):
		dt = value
	else:
		# sqlite commonly returns naive string timestamps.
		parsed = datetime.fromisoformat(str(value))
		dt = parsed

	if dt.tzinfo is None:
		return dt.replace(tzinfo=timezone.utc)
	return dt.astimezone(timezone.utc)


def _infer_status(
	latest_status: str | None,
	report_timestamp: datetime | None,
	time_remaining: int | None,
) -> tuple[str, datetime | None]:
	"""Infer displayed machine status from latest report and current time."""
	if latest_status is None:
		# No report yet: show as free to keep API response model stable.
		return "free", None

	now = datetime.now(timezone.utc)
	if latest_status == "unavailable":
		return "unavailable", None

	if latest_status == "free":
		return "free", None

	if latest_status != "busy" or report_timestamp is None:
		# Unknown labels or malformed rows fail safe to free.
		return "free", None

	if time_remaining is not None:
		available_at = report_timestamp + timedelta(minutes=time_remaining)
		if now < available_at:
			return "busy", available_at
		return "free", available_at

	maybe_free_at = report_timestamp + BUSY_NO_END_FALLBACK
	if now < maybe_free_at:
		return "busy", maybe_free_at
	return "probably_free", maybe_free_at


def get_status() -> list[dict[str, Any]]:
	"""Return all machines with inferred current status."""
	_ensure_db_ready()

	machines = fetch_machines()
	response: list[dict[str, Any]] = []
	for machine in machines:
		reported_at = _to_utc_datetime(machine.get("report_timestamp"))
		report_status = machine.get("report_status")
		time_remaining = machine.get("report_time_remaining")

		inferred_status, estimated_free_at = _infer_status(
			latest_status=report_status,
			report_timestamp=reported_at,
			time_remaining=time_remaining,
		)

		response.append(
			{
				"id": machine["id"],
				"name": machine["name"],
				"type": machine["type"],
				"inferred_status": inferred_status,
				"reported_status": report_status,
				"last_report_at": reported_at.isoformat() if reported_at else None,
				"time_remaining": time_remaining,
				"estimated_free_at": (
					estimated_free_at.isoformat() if estimated_free_at else None
				),
				"last_reporter_name": machine.get("report_reporter_name"),
			}
		)

	return response


def get_machine_history(machine_id: int, limit: int = 10) -> list[dict[str, Any]]:
	"""Return latest reports for one machine."""
	_ensure_db_ready()

	if machine_id <= 0:
		raise ValueError("machine_id must be a positive integer")
	if limit <= 0:
		raise ValueError("limit must be a positive integer")
	if not machine_exists(machine_id):
		raise ValueError("machine_id does not exist")

	reports = fetch_machine_history(machine_id=machine_id, limit=limit)
	history: list[dict[str, Any]] = []
	for report in reports:
		report_time = _to_utc_datetime(report.get("timestamp"))
		history.append(
			{
				"id": report["id"],
				"machine_id": report["machine_id"],
				"timestamp": report_time.isoformat() if report_time else None,
				"status": report["status"],
				"time_remaining": report.get("time_remaining"),
				"reporter_name": report.get("reporter_name"),
			}
		)
	return history


def save_report(
	report_or_machine_id: dict[str, Any] | int,
	status: str | None = None,
	time_remaining: int | None = None,
	reporter_name: str | None = None,
) -> dict[str, Any]:
	"""Validate and persist one machine report.

	Supports both call styles:
	- save_report({"machine_id": 1, "status": "busy", ...})
	- save_report(1, "busy", 20)
	"""
	_ensure_db_ready()

	if isinstance(report_or_machine_id, dict):
		report = report_or_machine_id
		machine_id = report.get("machine_id")
		incoming_status = report.get("status")
		incoming_time_remaining = report.get("time_remaining")
		incoming_reporter_name = report.get("reporter_name")
	else:
		machine_id = report_or_machine_id
		incoming_status = status
		incoming_time_remaining = time_remaining
		incoming_reporter_name = reporter_name

	if not isinstance(machine_id, int) or machine_id <= 0:
		raise ValueError("machine_id must be a positive integer")
	if incoming_status not in VALID_STATUSES:
		raise ValueError("status must be one of: free, busy, unavailable")
	if incoming_time_remaining is not None:
		if not isinstance(incoming_time_remaining, int) or incoming_time_remaining < 0:
			raise ValueError("time_remaining must be a non-negative integer or null")
	if incoming_reporter_name is not None and not isinstance(incoming_reporter_name, str):
		raise ValueError("reporter_name must be a string or null")
	if not machine_exists(machine_id):
		raise ValueError("machine_id does not exist")

	inserted = insert_report(
		machine_id=machine_id,
		status=incoming_status,
		time_remaining=incoming_time_remaining,
		reporter_name=incoming_reporter_name,
	)

	inserted_time = _to_utc_datetime(inserted.get("timestamp"))
	return {
		"id": inserted["id"],
		"machine_id": inserted["machine_id"],
		"timestamp": inserted_time.isoformat() if inserted_time else None,
		"status": inserted["status"],
		"time_remaining": inserted.get("time_remaining"),
		"reporter_name": inserted.get("reporter_name"),
	}


def create_notification(notification: dict[str, Any]) -> dict[str, Any]:
	"""Validate and persist one notification row."""
	_ensure_db_ready()

	machine_id = notification.get("machine_id")
	message = notification.get("message")
	level = notification.get("level", "info")

	if not isinstance(machine_id, int) or machine_id <= 0:
		raise ValueError("machine_id must be a positive integer")
	if not isinstance(message, str) or not message.strip():
		raise ValueError("message must be a non-empty string")
	if level not in VALID_NOTIFICATION_LEVELS:
		raise ValueError("level must be one of: info, warning, error")
	if not machine_exists(machine_id):
		raise ValueError("machine_id does not exist")

	inserted = insert_notification(
		machine_id=machine_id,
		message=message.strip(),
		level=level,
	)

	created_at = _to_utc_datetime(inserted.get("created_at"))
	return {
		"id": inserted["id"],
		"machine_id": inserted["machine_id"],
		"message": inserted["message"],
		"level": inserted["level"],
		"created_at": created_at.isoformat() if created_at else None,
	}