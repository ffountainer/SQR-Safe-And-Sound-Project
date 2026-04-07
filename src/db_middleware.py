"""Low-level SQL helpers used by the service layer in `src/db.py`."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///laundry.db")
engine = create_engine(DATABASE_URL, future=True)


def _ensure_machine_metadata_columns(connection) -> None:
	existing_columns = [row[1] for row in connection.execute(text("PRAGMA table_info(machines)"))]
	if "floor" not in existing_columns:
		connection.execute(text("ALTER TABLE machines ADD COLUMN floor INTEGER"))
	if "building" not in existing_columns:
		connection.execute(text("ALTER TABLE machines ADD COLUMN building TEXT"))


def _ensure_existing_machine_metadata(connection) -> None:
	"""Populate metadata for already seeded machines when the schema was extended."""
	rows = connection.execute(text("SELECT id, floor, building FROM machines")).mappings().all()
	mapping = {
		1: (1, "1"),
		2: (2, "1"),
		3: (1, "1"),
		4: (2, "1"),
	}
	for row in rows:
		if row["id"] in mapping and (row["floor"] is None or row["building"] is None):
			floor, building = mapping[row["id"]]
			connection.execute(
				text(
					"UPDATE machines SET floor = :floor, building = :building WHERE id = :id"
				),
				{"floor": floor, "building": building, "id": row["id"]},
			)


def init_db() -> None:
	"""Create required tables if they do not exist."""
	with engine.begin() as connection:
		connection.execute(
			text(
				"""
				CREATE TABLE IF NOT EXISTS machines (
					id INTEGER PRIMARY KEY,
					name TEXT NOT NULL,
					type TEXT NOT NULL CHECK (type IN ('wash', 'dry')),
					floor INTEGER,
					building TEXT
				)
				"""
			)
		)

		connection.execute(
			text(
				"""
				CREATE TABLE IF NOT EXISTS reports (
					id INTEGER PRIMARY KEY,
					machine_id INTEGER NOT NULL,
					timestamp DATETIME NOT NULL,
					status TEXT NOT NULL CHECK (status IN ('free', 'busy', 'unavailable')),
					time_remaining INTEGER,
					reporter_name TEXT,
					FOREIGN KEY(machine_id) REFERENCES machines(id)
				)
				"""
			)
		)

		connection.execute(
			text(
				"""
				CREATE TABLE IF NOT EXISTS notifications (
					id INTEGER PRIMARY KEY,
					machine_id INTEGER NOT NULL,
					message TEXT NOT NULL,
					level TEXT NOT NULL DEFAULT 'info',
					created_at DATETIME NOT NULL,
					FOREIGN KEY(machine_id) REFERENCES machines(id)
				)
				"""
			)
		)

		_ensure_machine_metadata_columns(connection)
		_ensure_existing_machine_metadata(connection)


def seed_machines_if_empty() -> None:
	"""Populate the machine catalog when the table is empty."""
	with engine.begin() as connection:
		count_result = connection.execute(text("SELECT COUNT(*) FROM machines"))
		machines_count = int(count_result.scalar_one())
		if machines_count > 0:
			return

		# 7 buildings total:
		# - buildings 1-5 have 4 floors
		# - buildings 6-7 have 13 floors
		# on every floor there are 2 washers + 2 dryers (4 machines per floor)
		seed_data: list[dict[str, Any]] = []
		next_id = 1

		for building in range(1, 8):
			max_floor = 4 if building <= 5 else 13
			for floor in range(1, max_floor + 1):
				machines = [
					("Washer 1", "wash"),
					("Washer 2", "wash"),
					("Dryer 1", "dry"),
					("Dryer 2", "dry"),
				]
				for name, mtype in machines:
					seed_data.append(
						{
							"id": next_id,
							"name": f"B{building} F{floor} {name}",
							"type": mtype,
							"floor": floor,
							"building": str(building),
						}
					)
					next_id += 1
		connection.execute(
			text(
				"INSERT INTO machines (id, name, type, floor, building) VALUES (:id, :name, :type, :floor, :building)"
			),
			seed_data,
		)


def fetch_machines() -> list[dict[str, Any]]:
	"""Return all machines with their latest report (if present)."""
	query = text(
		"""
		SELECT
			m.id,
			m.name,
			m.type,
			m.floor,
			m.building,
			r.id AS report_id,
			r.timestamp AS report_timestamp,
			r.status AS report_status,
			r.time_remaining AS report_time_remaining,
			r.reporter_name AS report_reporter_name
		FROM machines AS m
		LEFT JOIN reports AS r
			ON r.id = (
				SELECT r2.id
				FROM reports AS r2
				WHERE r2.machine_id = m.id
				ORDER BY r2.timestamp DESC, r2.id DESC
				LIMIT 1
			)
		ORDER BY m.id
		"""
	)
	with engine.connect() as connection:
		result = connection.execute(query)
		return [dict(row._mapping) for row in result]


def fetch_machine_history(machine_id: int, limit: int = 10) -> list[dict[str, Any]]:
	"""Return the newest reports for a given machine."""
	query = text(
		"""
		SELECT
			id,
			machine_id,
			timestamp,
			status,
			time_remaining,
			reporter_name
		FROM reports
		WHERE machine_id = :machine_id
		ORDER BY timestamp DESC, id DESC
		LIMIT :limit
		"""
	)
	with engine.connect() as connection:
		result = connection.execute(query, {"machine_id": machine_id, "limit": limit})
		return [dict(row._mapping) for row in result]


def machine_exists(machine_id: int) -> bool:
	"""Return True when machine with given id exists."""
	query = text("SELECT 1 FROM machines WHERE id = :machine_id LIMIT 1")
	with engine.connect() as connection:
		result = connection.execute(query, {"machine_id": machine_id}).first()
		return result is not None


def insert_report(
	machine_id: int,
	status: str,
	time_remaining: int | None = None,
	reporter_name: str | None = None,
	reported_at: datetime | None = None,
) -> dict[str, Any]:
	"""Insert a report and return the inserted row metadata."""
	if reported_at is None:
		reported_at = datetime.now(timezone.utc)

	query = text(
		"""
		INSERT INTO reports (machine_id, timestamp, status, time_remaining, reporter_name)
		VALUES (:machine_id, :timestamp, :status, :time_remaining, :reporter_name)
		RETURNING id, machine_id, timestamp, status, time_remaining, reporter_name
		"""
	)
	params = {
		"machine_id": machine_id,
		"timestamp": reported_at,
		"status": status,
		"time_remaining": time_remaining,
		"reporter_name": reporter_name,
	}
	with engine.begin() as connection:
		inserted = connection.execute(query, params).one()
		return dict(inserted._mapping)


def insert_notification(
	machine_id: int,
	message: str,
	level: str = "info",
	created_at: datetime | None = None,
) -> dict[str, Any]:
	"""Insert a notification and return the inserted row metadata."""
	if created_at is None:
		created_at = datetime.now(timezone.utc)

	query = text(
		"""
		INSERT INTO notifications (machine_id, message, level, created_at)
		VALUES (:machine_id, :message, :level, :created_at)
		RETURNING id, machine_id, message, level, created_at
		"""
	)
	params = {
		"machine_id": machine_id,
		"message": message,
		"level": level,
		"created_at": created_at,
	}
	with engine.begin() as connection:
		inserted = connection.execute(query, params).one()
		return dict(inserted._mapping)