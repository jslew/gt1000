from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gt1000_app.agent import AgentService
from gt1000_app.app_logging import app_log, ingest_client_logs, log_paths, tail_logs
from gt1000_app.config import AppConfig, load_config, load_config_file_only, save_config
from gt1000_app.device import DeviceService
from gt1000_app.providers import list_provider_models


class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    openaiApiKey: str | None = None
    openaiBaseUrl: str | None = None
    ollamaBaseUrl: str | None = None
    systemPromptExtra: str | None = None
    openaiReasoningEffort: str | None = None
    openaiTextVerbosity: str | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


class PlanRequest(BaseModel):
    planId: str
    name: str | None = None
    userSlot: str | None = None


class ApplyRequest(BaseModel):
    planId: str
    name: str | None = None
    userSlot: str | None = None
    verify: bool = True
    timeout: float = 20.0


class ClientLogEntry(BaseModel):
    level: str = "info"
    category: str = "client"
    message: str
    data: dict[str, Any] | None = None
    ts: str | None = None


class ClientLogBatch(BaseModel):
    entries: list[ClientLogEntry] = Field(default_factory=list)


def build_api_router(device: DeviceService, agent: AgentService) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True}

    @router.get("/device/status")
    async def device_status() -> dict[str, Any]:
        return asdict(device.status())

    @router.get("/config")
    async def get_config() -> dict[str, Any]:
        return load_config().public_dict()

    @router.get("/models")
    async def list_models(provider: str | None = None) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                list_provider_models(load_config(), provider=provider),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            selected = (provider or load_config().provider).strip().lower()
            return {
                "provider": selected,
                "models": [],
                "error": "Model provider query timed out after 15s",
            }

    @router.put("/config")
    async def put_config(body: ConfigUpdate) -> dict[str, Any]:
        current = load_config()
        file_config = load_config_file_only()
        updated = AppConfig(
            provider=body.provider or current.provider,
            model=body.model or current.model,
            openai_api_key=body.openaiApiKey if body.openaiApiKey not in {None, "***"} else file_config.openai_api_key,
            openai_base_url=body.openaiBaseUrl or current.openai_base_url,
            ollama_base_url=body.ollamaBaseUrl or current.ollama_base_url,
            system_prompt_extra=body.systemPromptExtra if body.systemPromptExtra is not None else current.system_prompt_extra,
            openai_reasoning_effort=body.openaiReasoningEffort or current.openai_reasoning_effort,
            openai_text_verbosity=body.openaiTextVerbosity or current.openai_text_verbosity,
        )
        save_config(updated)
        effective = load_config()
        agent.update_config(effective)
        return effective.public_dict()

    @router.get("/ports")
    async def ports(timeout: float = 8.0) -> dict[str, Any]:
        try:
            return await device.ports(timeout=timeout)
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.get("/patch/overview")
    async def patch_overview(timeout: float = 8.0, refresh: bool = False) -> dict[str, Any]:
        try:
            return await device.patch_overview(timeout=timeout, force_refresh=refresh)
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.get("/patch/preview")
    async def patch_preview(timeout: float = 10.0, refresh: bool = False) -> dict[str, Any]:
        try:
            return await device.patch_preview(timeout=timeout, force_refresh=refresh)
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.get("/patch/chain")
    async def patch_chain(timeout: float = 25.0, refresh: bool = False) -> dict[str, Any]:
        try:
            return await device.patch_chain(timeout=timeout, force_refresh=refresh)
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.get("/patch/controls")
    async def patch_controls(timeout: float = 15.0, refresh: bool = False) -> dict[str, Any]:
        try:
            return await device.patch_controls(timeout=timeout, force_refresh=refresh)
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.get("/patch/musician-summary")
    async def patch_musician_summary(timeout: float = 15.0, refresh: bool = False) -> dict[str, Any]:
        try:
            return await device.patch_musician_summary(timeout=timeout, force_refresh=refresh)
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.post("/patch/plan")
    async def patch_plan(body: PlanRequest) -> dict[str, Any]:
        try:
            return await device.build_plan(body.planId, name=body.name, user_slot=body.userSlot)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/patch/apply")
    async def patch_apply(body: ApplyRequest) -> dict[str, Any]:
        try:
            return await device.apply_plan_id(
                body.planId,
                name=body.name,
                user_slot=body.userSlot,
                timeout=body.timeout,
                verify=body.verify,
            )
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @router.post("/logs/client")
    async def post_client_logs(body: ClientLogBatch) -> dict[str, Any]:
        raw_entries = [entry.model_dump(exclude_none=True) for entry in body.entries]
        count = ingest_client_logs(raw_entries)
        app_log("debug", "client", f"Ingested {count} client log entries", count=count)
        return {"ok": True, "ingested": count}

    @router.get("/logs/paths")
    async def get_log_paths() -> dict[str, str]:
        return log_paths()

    @router.get("/logs")
    async def get_logs(source: str = "server", limit: int = 200) -> dict[str, Any]:
        if source not in {"server", "client"}:
            raise HTTPException(status_code=400, detail="source must be server or client")
        entries = tail_logs(source, limit=limit)  # type: ignore[arg-type]
        return {"source": source, "limit": limit, "entries": entries}

    @router.post("/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        preview = body.message.strip().replace("\n", " ")[:120]
        app_log(
            "info",
            "chat",
            "Chat stream started",
            messagePreview=preview,
            historyCount=len(body.history),
        )

        async def event_stream():
            try:
                async for event in agent.stream_chat(body.message, body.history):
                    if event.type not in {"assistant.delta"}:
                        app_log(
                            "debug",
                            "chat",
                            f"SSE {event.type}",
                            eventType=event.type,
                            dataKeys=sorted(event.data.keys()),
                        )
                    payload = {"type": event.type, "data": event.data}
                    yield f"data: {json.dumps(payload)}\n\n"
                app_log("info", "chat", "Chat stream finished")
            except Exception as error:
                app_log("error", "chat", "Chat stream failed", error=str(error))
                payload = {"type": "error", "data": {"message": str(error)}}
                yield f"data: {json.dumps(payload)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return router
