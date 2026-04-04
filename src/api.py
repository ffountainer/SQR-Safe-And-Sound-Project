"""
fastapi entry: http from streamlit -> validate body -> db layer -> json back.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.db import get_machine_history, get_status, save_report

app = FastAPI(title="laundry status api")

ReportStatus = Literal["busy", "free", "unavailable"]
InferredStatus = Literal["free", "busy", "probably_free", "unavailable"]


class ReportIn(BaseModel):
    machine_id: int = Field(..., ge=1)
    status: ReportStatus
    time_remaining: int | None = Field(
        default=None,
        ge=0,
        description="minutes left when status is busy",
    )


class MachineOut(BaseModel):
    id: int
    name: str
    type: str
    inferred_status: InferredStatus


class HistoryReportOut(BaseModel):
    id: int
    machine_id: int
    timestamp: datetime
    status: str
    time_remaining: int | None


@app.post("/report", status_code=201)
def post_report(body: ReportIn) -> dict[str, str]:
    # front sends a new observation; we only store it; inference happens on read
    try:
        save_report(body.machine_id, body.status, body.time_remaining)
    except ValueError:
        raise HTTPException(status_code=404, detail="machine not found") from None
    return {"result": "ok"}


@app.get("/machines", response_model=list[MachineOut])
def list_machines() -> list[dict]:
    # front loads the grid
    return get_status()


@app.get("/machines/{machine_id}/history", response_model=list[HistoryReportOut])
def machine_history(machine_id: int, limit: int = 20) -> list[dict]:
    # last N raw rows
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    try:
        return get_machine_history(machine_id, limit=limit)
    except ValueError:
        raise HTTPException(status_code=404, detail="machine not found") from None