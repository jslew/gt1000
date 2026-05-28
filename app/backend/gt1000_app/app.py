from __future__ import annotations

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from gt1000_app.agent import AgentService
from gt1000_app.api import build_api_router
from gt1000_app.app_logging import setup_logging
from gt1000_app.config import load_config
from gt1000_app.device import DeviceService
from gt1000_app.events import EventBus
from gt1000_app.http_logging import RequestLoggingMiddleware
from gt1000_app.ws import websocket_events


def create_app(
    device: DeviceService | None = None,
    agent: AgentService | None = None,
) -> FastAPI:
    setup_logging()
    events = EventBus()
    device = device or DeviceService(events)
    agent = agent or AgentService(device, load_config())

    app = FastAPI(title="GT-1000 Localhost App", version="0.1.0")
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(build_api_router(device, agent), prefix="/api")

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket) -> None:
        await websocket_events(ws, events)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app

