from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AppEvent:
    type: str
    data: dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[AppEvent]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[AppEvent]:
        queue: asyncio.Queue[AppEvent] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[AppEvent]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def emit(self, event_type: str, **data: Any) -> None:
        event = AppEvent(type=event_type, data=dict(data))
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop events for slow clients; UI can always refetch state.
                pass

