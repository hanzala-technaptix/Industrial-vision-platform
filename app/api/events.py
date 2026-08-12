from typing import Optional

from fastapi import APIRouter, Query

from app.db.database import event_stats, list_events

router = APIRouter()


@router.get("/events")
def get_events(limit: int = Query(50, ge=1, le=500),
               event_type: Optional[str] = Query(None)):
    events = list_events(limit=limit, event_type=event_type)
    return {"count": len(events), "events": events}


@router.get("/events/stats")
def get_stats():
    return event_stats()
