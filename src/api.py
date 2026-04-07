"""
fastapi entry: http from streamlit -> validate body -> db layer -> json back.

swagger ui: GET /docs
openapi schema: GET /openapi.json
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
    reporter_name: str | None = Field(default=None, description="optional reporter name")


class MachineOut(BaseModel):
    id: int
    name: str
    type: str
    floor: int | None = None
    building: str | None = None
    inferred_status: InferredStatus
    # timer logic
    time_remaining: int | None = None
    reported_status: ReportStatus | None = None
    last_report_at: datetime | None = None
    estimated_free_at: datetime | None = None
    last_reporter_name: str | None = None


class HistoryReportOut(BaseModel):
    id: int
    machine_id: int
    timestamp: datetime
    status: str
    time_remaining: int | None
    reporter_name: str | None = None


class ErrorDetail(BaseModel):
    detail: str


class PostReportOut(BaseModel):
    id: int
    machine_id: int
    timestamp: datetime
    status: ReportStatus
    time_remaining: int | None = None
    reporter_name: str | None = None


def _raise_http_from_value_error(error: ValueError) -> None:
    message = str(error).lower()
    if "does not exist" in message or "not found" in message:
        raise HTTPException(status_code=404, detail=str(error)) from None
    raise HTTPException(status_code=400, detail=str(error)) from None


@app.post(
    "/report",
    status_code=201,
    response_model=PostReportOut,
    responses={
        400: {"model": ErrorDetail, "description": "invalid input"},
        404: {"model": ErrorDetail, "description": "unknown machine_id"},
    },
)
def post_report(body: ReportIn) -> PostReportOut:
    try:
        inserted = save_report(
            body.machine_id,
            body.status,
            body.time_remaining,
            body.reporter_name,
        )
    except ValueError as error:
        _raise_http_from_value_error(error)

    return PostReportOut.model_validate(inserted)


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
    except ValueError as error:
        _raise_http_from_value_error(error)