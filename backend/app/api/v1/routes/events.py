import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select

from backend.app.api.deps import DbDep
from backend.app.core.config import settings
from backend.app.db.models import Case, DidiJob, Event, Photo
from backend.app.schemas import EventOut
from backend.app.services import didi
from backend.app.services.events import broadcaster, emit

router = APIRouter()
HEARTBEAT_S = 25


@router.get("/events", response_model=list[EventOut])
async def list_events(db: DbDep, case_id: int | None = None, limit: int = Query(100, ge=1, le=500)) -> list[EventOut]:
    q = select(Event).order_by(Event.id.desc()).limit(limit)
    if case_id is not None:
        q = q.where(Event.case_id == case_id)
    return list(reversed((await db.execute(q)).scalars().all()))


@router.websocket("/ws/events")
async def events_ws(ws: WebSocket) -> None:
    await ws.accept()
    q = broadcaster.subscribe()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_S)
                await ws.send_json(msg)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unsubscribe(q)


@router.post("/demo/reset", response_model=EventOut)
async def demo_reset(db: DbDep) -> EventOut:
    """Wipe cases, photos, jobs and events so the demo can run again from the warning call."""
    if not settings.demo_mode:
        from fastapi import HTTPException
        raise HTTPException(403, "Reset only allowed in demo mode")
    for model in (Photo, DidiJob, Case, Event):
        await db.execute(delete(model))
    await db.commit()
    await didi.seed_demo_tickets(db)
    return await emit(db, "demo_reset")
