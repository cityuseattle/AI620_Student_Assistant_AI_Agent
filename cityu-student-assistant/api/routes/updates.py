"""
Prerequisite self-update endpoints.

``GET  /updates``                — list recent change-log entries (optionally by status)
``GET  /updates/pending``        — list proposals awaiting approval
``POST /updates/{change_id}/approve`` — approve a pending change (writes to DB)
``POST /updates/{change_id}/reject``  — reject a pending change
``GET  /updates/mode``           — get the current update mode
``POST /updates/mode``           — set the update mode ('approval' | 'auto')
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from agent import prereq_updater
from api.schemas import (
    ActionResponse,
    ModeRequest,
    ModeResponse,
    PrereqUpdateEntry,
    PrereqUpdateList,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/updates", tags=["Prerequisite Updates"])


def _to_entries(raw: list[dict]) -> list[PrereqUpdateEntry]:
    return [
        PrereqUpdateEntry(
            id=e.get("id", ""),
            course_code=e.get("course_code", ""),
            prereqs=e.get("prereqs", []),
            status=e.get("status", ""),
            mode=e.get("mode", ""),
            reasoning=e.get("reasoning", ""),
            source=e.get("source", "agent"),
            unknown_prereqs=e.get("unknown_prereqs", []),
            created_at=e.get("created_at", ""),
        )
        for e in raw
    ]


@router.get("", response_model=PrereqUpdateList, summary="List prerequisite changes")
async def list_updates(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: pending | applied | approved | rejected",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> PrereqUpdateList:
    raw = prereq_updater.list_entries(status=status_filter, limit=limit)
    return PrereqUpdateList(mode=prereq_updater.get_mode(), entries=_to_entries(raw))


@router.get("/pending", response_model=PrereqUpdateList, summary="List pending proposals")
async def list_pending(limit: int = Query(default=50, ge=1, le=200)) -> PrereqUpdateList:
    raw = prereq_updater.list_pending(limit=limit)
    return PrereqUpdateList(mode=prereq_updater.get_mode(), entries=_to_entries(raw))


@router.get("/mode", response_model=ModeResponse, summary="Get the update mode")
async def get_mode() -> ModeResponse:
    return ModeResponse(mode=prereq_updater.get_mode())


@router.post("/mode", response_model=ModeResponse, summary="Set the update mode")
async def set_mode(request: ModeRequest) -> ModeResponse:
    try:
        new_mode = prereq_updater.set_mode(request.mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return ModeResponse(mode=new_mode)


@router.post(
    "/{change_id}/approve",
    response_model=ActionResponse,
    summary="Approve a pending change",
)
async def approve(change_id: str) -> ActionResponse:
    result = prereq_updater.approve(change_id)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result["message"]
        )
    return ActionResponse(**{k: result.get(k) for k in ("status", "message", "id")})


@router.post(
    "/{change_id}/reject",
    response_model=ActionResponse,
    summary="Reject a pending change",
)
async def reject(change_id: str) -> ActionResponse:
    result = prereq_updater.reject(change_id)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result["message"]
        )
    return ActionResponse(**{k: result.get(k) for k in ("status", "message", "id")})
