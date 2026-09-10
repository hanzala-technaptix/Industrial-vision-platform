"""Use-case catalog and live switch endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.dependencies import get_session

router = APIRouter()


class SwitchBody(BaseModel):
    source: Optional[str] = None


@router.get("/use_cases")
def list_use_cases(request: Request):
    session = get_session(request)
    if session is None:
        return {"current": None, "use_cases": []}
    return session.snapshot()


@router.post("/use_cases/{use_case_id}")
def switch_use_case(use_case_id: str, request: Request, body: SwitchBody | None = None):
    session = get_session(request)
    if session is None:
        raise HTTPException(503, "Showcase session is not ready")
    source = body.source if body else None
    try:
        result = session.start(use_case_id, source=source)
        request.app.state.pipeline = session.pipeline
        return result
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
