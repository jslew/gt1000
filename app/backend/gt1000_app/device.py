from __future__ import annotations

import argparse
import asyncio
import copy
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from gt1000_app.app_logging import app_log
from gt1000_app.events import EventBus

try:
    from skills.gt1000.tools.gt1000 import agent_cli, live, patch_edit
except ModuleNotFoundError:
    # Allow running the backend from within the skill folder too.
    from tools.gt1000 import agent_cli, live, patch_edit  # type: ignore

T = TypeVar("T")

# Patch reads are cached until apply, explicit refresh, a live block read, or TTL expiry.
# Hardware patch/bank changes on the unit require "Refresh chain" in the UI.
PATCH_CACHE_TTL_SECONDS = 120.0


@dataclass
class DeviceStatus:
    ok: bool
    busy: bool
    blocked_reason: str | None
    last_error: str | None
    last_activity_monotonic: float | None


@dataclass
class _PatchReadCache:
    chain: dict[str, Any] | None = None
    overview: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    controls: dict[str, Any] | None = None
    musician_summary: dict[str, Any] | None = None
    cached_at: float | None = None


class DeviceService:
    @staticmethod
    def live_worker_timeout(timeout: float) -> float:
        # patch_view lenient reads use live_summary_total_timeout(timeout) inside the worker.
        return agent_cli.live_summary_total_timeout(timeout) + 5.0

    def __init__(self, events: EventBus) -> None:
        self._events = events
        self._lock = asyncio.Lock()
        self._busy = False
        self._last_error: str | None = None
        self._last_activity: float | None = None
        self._patch_cache = _PatchReadCache()
        self._patch_cache_lock = asyncio.Lock()
        self._patch_inflight: dict[str, asyncio.Task[dict[str, Any]]] = {}

    def invalidate_patch_cache(self) -> None:
        self._patch_cache = _PatchReadCache()
        for task in self._patch_inflight.values():
            if not task.done():
                task.cancel()
        self._patch_inflight.clear()

    def _cache_is_fresh(self) -> bool:
        if self._patch_cache.cached_at is None:
            return False
        return (time.monotonic() - self._patch_cache.cached_at) <= PATCH_CACHE_TTL_SECONDS

    def _cached_value(self, field: str) -> dict[str, Any] | None:
        if not self._cache_is_fresh():
            return None
        value = getattr(self._patch_cache, field, None)
        if value is None:
            return None
        return copy.deepcopy(value)

    def _note_cache_write(self) -> None:
        self._patch_cache.cached_at = time.monotonic()

    def _store_chain_view(self, result: dict[str, Any]) -> None:
        stored = copy.deepcopy(result)
        self._patch_cache.chain = stored
        # Keep preview aligned with the latest full chain read (same patch generation).
        self._patch_cache.preview = copy.deepcopy(stored)
        self._note_cache_write()

    def _store_cached_field(self, field: str, result: dict[str, Any]) -> None:
        setattr(self._patch_cache, field, copy.deepcopy(result))
        self._note_cache_write()

    async def _patch_read_cached(
        self,
        field: str,
        *,
        label: str,
        force_refresh: bool,
        load: Callable[[], dict[str, Any]],
        thread_timeout: float,
    ) -> dict[str, Any]:
        if force_refresh:
            self.invalidate_patch_cache()

        async def complete() -> dict[str, Any]:
            result = await self._with_device_lock(label, load, thread_timeout=thread_timeout)
            async with self._patch_cache_lock:
                if field == "chain":
                    self._store_chain_view(result)
                else:
                    self._store_cached_field(field, result)
            return copy.deepcopy(result)

        async with self._patch_cache_lock:
            cached = self._cached_value(field)
            if cached is not None:
                app_log("debug", "device", f"patch.{field} cache hit")
                return cached
            task = self._patch_inflight.get(field)
            if task is None:
                task = asyncio.create_task(complete())
                self._patch_inflight[field] = task

        try:
            return copy.deepcopy(await task)
        finally:
            async with self._patch_cache_lock:
                if self._patch_inflight.get(field) is task:
                    self._patch_inflight.pop(field, None)

    def _sandbox_block_reason(self) -> str | None:
        # Reuse the CLI's sandbox/CoreMIDI preflight logic.
        try:
            return agent_cli.live_midi_environment_block_reason()
        except Exception:
            return None

    def status(self) -> DeviceStatus:
        blocked = self._sandbox_block_reason()
        return DeviceStatus(
            ok=blocked is None and sys.platform == "darwin",
            busy=self._busy,
            blocked_reason=blocked,
            last_error=self._last_error,
            last_activity_monotonic=self._last_activity,
        )

    async def _with_device_lock(self, label: str, fn: Callable[[], T], *, thread_timeout: float | None = None) -> T:
        async with self._lock:
            started = time.monotonic()
            self._busy = True
            self._last_activity = started
            await self._events.emit("device.busy", label=label)
            app_log("info", "device", f"Device busy: {label}", label=label)
            try:
                # Run device/MIDI work off the event loop so /api/models and chat stay responsive.
                budget = thread_timeout if thread_timeout is not None else 60.0
                result = await asyncio.wait_for(asyncio.to_thread(fn), timeout=budget)
                self._last_activity = time.monotonic()
                duration_ms = round((self._last_activity - started) * 1000, 2)
                await self._events.emit("device.idle", label=label)
                app_log("info", "device", f"Device idle: {label}", label=label, durationMs=duration_ms)
                return result
            except asyncio.TimeoutError as error:
                message = f"{label} timed out after {thread_timeout or 60.0:g}s"
                self._last_error = message
                self._last_activity = time.monotonic()
                duration_ms = round((self._last_activity - started) * 1000, 2)
                app_log("error", "device", message, label=label, durationMs=duration_ms)
                await self._events.emit("device.error", label=label, error=message)
                await self._events.emit("device.idle", label=label)
                raise TimeoutError(message) from error
            except Exception as error:
                self._last_error = str(error)
                self._last_activity = time.monotonic()
                duration_ms = round((self._last_activity - started) * 1000, 2)
                app_log("error", "device", f"Device error: {label}", label=label, error=str(error), durationMs=duration_ms)
                await self._events.emit("device.error", label=label, error=str(error))
                await self._events.emit("device.idle", label=label)
                raise
            finally:
                self._busy = False

    async def ports(self, *, timeout: float = 8.0) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            return agent_cli.live_call_with_timeout("ports", timeout, live.ports)

        return await self._with_device_lock("ports", run, thread_timeout=timeout + 5.0)

    def _patch_view_args(self, *, timeout: float) -> argparse.Namespace:
        return argparse.Namespace(
            live=True,
            file=None,
            timeout=timeout,
        )

    async def patch_overview(self, *, timeout: float = 8.0, force_refresh: bool = False) -> dict[str, Any]:
        worker_timeout = self.live_worker_timeout(timeout)

        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            args = self._patch_view_args(timeout=timeout)
            return agent_cli.live_call_with_timeout(
                "patch.overview", worker_timeout, agent_cli.patch_view, args, "overview"
            )

        return await self._patch_read_cached(
            "overview",
            label="patch.overview",
            force_refresh=force_refresh,
            load=run,
            thread_timeout=worker_timeout + 5.0,
        )

    async def patch_preview(self, *, timeout: float = 10.0, force_refresh: bool = False) -> dict[str, Any]:
        """Fast read (INITIAL_READS only): patch title, levels, and chain layout without block detail."""
        worker_timeout = self.live_worker_timeout(timeout)

        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            snapshot = agent_cli.read_live_snapshot_with_timeout(
                "patch.preview",
                timeout,
                requests=agent_cli.requests_for_view("overview"),
            )
            return agent_cli.chain_from_full(snapshot)

        return await self._patch_read_cached(
            "preview",
            label="patch.preview",
            force_refresh=force_refresh,
            load=run,
            thread_timeout=worker_timeout + 5.0,
        )

    async def patch_chain(self, *, timeout: float = 25.0, force_refresh: bool = False) -> dict[str, Any]:
        worker_timeout = self.live_worker_timeout(timeout)

        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            args = self._patch_view_args(timeout=timeout)
            return agent_cli.live_call_with_timeout(
                "patch.chain", worker_timeout, agent_cli.patch_view, args, "chain"
            )

        return await self._patch_read_cached(
            "chain",
            label="patch.chain",
            force_refresh=force_refresh,
            load=run,
            thread_timeout=worker_timeout + 5.0,
        )

    async def patch_controls(self, *, timeout: float = 20.0, force_refresh: bool = False) -> dict[str, Any]:
        worker_timeout = self.live_worker_timeout(timeout)

        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            args = self._patch_view_args(timeout=timeout)
            return agent_cli.live_call_with_timeout(
                "patch.controls", worker_timeout, agent_cli.patch_view, args, "controls"
            )

        return await self._patch_read_cached(
            "controls",
            label="patch.controls",
            force_refresh=force_refresh,
            load=run,
            thread_timeout=worker_timeout + 5.0,
        )

    async def patch_musician_summary(self, *, timeout: float = 20.0, force_refresh: bool = False) -> dict[str, Any]:
        worker_timeout = self.live_worker_timeout(timeout)

        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            args = self._patch_view_args(timeout=timeout)
            return agent_cli.live_call_with_timeout(
                "patch.musician-summary",
                worker_timeout,
                agent_cli.patch_view,
                args,
                "musician-summary",
            )

        return await self._patch_read_cached(
            "musician_summary",
            label="patch.musician-summary",
            force_refresh=force_refresh,
            load=run,
            thread_timeout=worker_timeout + 5.0,
        )

    def _patch_block_args(self, *, block_id: str, timeout: float, user_slot: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            live=True,
            file=None,
            timeout=timeout,
            block_id=block_id,
            position=None,
            user_slot=user_slot,
        )

    async def patch_block(
        self,
        block_id: str,
        *,
        timeout: float = 20.0,
        user_slot: str | None = None,
    ) -> dict[str, Any]:
        # Live block read may reflect knob changes; drop cached patch views so chain/tools stay consistent.
        self.invalidate_patch_cache()
        worker_timeout = self.live_worker_timeout(timeout)

        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            args = self._patch_block_args(block_id=block_id, timeout=timeout, user_slot=user_slot)
            return agent_cli.live_call_with_timeout(
                f"patch.block:{block_id}",
                worker_timeout,
                agent_cli.cmd_patch_block,
                args,
            )

        return await self._with_device_lock(
            f"patch.block:{block_id}", run, thread_timeout=worker_timeout + 5.0
        )

    async def build_plan(self, plan_id: str, *, name: str | None = None, user_slot: str | None = None) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            plan = patch_edit.plan_by_id(plan_id, name=name)
            if user_slot:
                plan = patch_edit.plan_for_user_slot(plan, user_slot)
            return plan.to_dict()

        return await self._with_device_lock(f"patch.plan:{plan_id}", run)

    async def apply_plan(self, plan: patch_edit.PatchPlan, *, timeout: float, verify: bool) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            agent_cli.assert_live_midi_environment()
            return patch_edit.apply_plan(plan, timeout=timeout, verify=verify)

        result = await self._with_device_lock(f"patch.apply:{plan.id}", run)
        self.invalidate_patch_cache()
        await self._events.emit("patch.updated", view="apply", plan=plan.id, verified=result.get("verified"))
        return result

    async def apply_plan_id(
        self,
        plan_id: str,
        *,
        name: str | None = None,
        user_slot: str | None = None,
        timeout: float = 20.0,
        verify: bool = True,
    ) -> dict[str, Any]:
        plan = patch_edit.plan_by_id(plan_id, name=name)
        if user_slot:
            plan = patch_edit.plan_for_user_slot(plan, user_slot)
        return await self.apply_plan(plan, timeout=timeout, verify=verify)
