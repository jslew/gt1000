from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket

from gt1000_app.events import AppEvent, EventBus


async def websocket_events(ws: WebSocket, events: EventBus) -> None:
    await ws.accept()
    queue = await events.subscribe()
    try:
        await ws.send_text(json.dumps({"type": "hello", "data": {"ok": True}}))
        while True:
            event: AppEvent = await queue.get()
            payload: dict[str, Any] = {"type": event.type, "data": event.data}
            await ws.send_text(json.dumps(payload))
    except Exception:
        # Client disconnects and other WS errors are normal.
        pass
    finally:
        await events.unsubscribe(queue)

