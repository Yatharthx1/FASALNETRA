"""Event log + live fan-out to dashboard websockets."""
import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Event


class Broadcaster:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def publish(self, message: dict[str, Any]) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:   # a stalled client must not block the others
                self._queues.discard(q)


broadcaster = Broadcaster()


async def emit(db: AsyncSession, type_: str, case_id: int | None = None, **payload: Any) -> Event:
    ev = Event(type=type_, case_id=case_id, payload=payload)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    broadcaster.publish({"id": ev.id, "ts": ev.ts.isoformat(), "type": type_, "case_id": case_id, "payload": payload})
    return ev
