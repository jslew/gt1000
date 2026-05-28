from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from gt1000_app.app_logging import app_log
from gt1000_app.chat_display import VisibleStreamFilter, strip_tool_calls
from gt1000_app.config import AppConfig
from gt1000_app.device import DeviceService
from gt1000_app.llm_tools import tool_definitions
from gt1000_app.providers import ChatMessage, build_provider, openai_tools_for_provider
from gt1000_app.tool_payload import compact_tool_result
from gt1000_app.skill_context import skill_index_for_prompt
from gt1000_app.tools import execute_tool

try:
    from skills.gt1000.tools.gt1000 import patch_edit
except ModuleNotFoundError:
    from tools.gt1000 import patch_edit  # type: ignore


@dataclass(frozen=True)
class ChatEvent:
    type: str
    data: dict[str, Any]


LLM_STREAM_TIMEOUT = 120.0
TOOL_TIMEOUTS: dict[str, float] = {
    "get_patch_chain": 45.0,
    "get_patch_overview": 25.0,
    "get_patch_controls": 40.0,
    "get_patch_musician_summary": 40.0,
    "get_patch_block": 35.0,
    "list_ports": 15.0,
    "plan_patch": 10.0,
}
CHAT_TURN_TIMEOUT = 240.0
MAX_TOOL_ROUNDS = 4
SKILL_TOOL_NAMES = frozenset({"load_skill_reference"})


def system_prompt(config: AppConfig) -> str:
    base = (
        "You are a GT-1000 guitar processor assistant (musician-facing). "
        "Explain patches in plain language. Never emit raw SysEx or naked byte arrays. "
        "Use the registered function tools to read the device, load reference docs, or build plans.\n\n"
        "Progressive disclosure: do NOT rely on memorized manual text for GT-1000-specific facts. "
        "Call load_skill_reference before answering about: divider/branch/mixer routing, "
        "Assign target encoding (min/max), footswitch/CTL/CUR NUM functions, or SysEx details.\n"
        "Tool routing:\n"
        "- get_patch_musician_summary: general patch overview (no per-block knob values).\n"
        "- get_patch_chain: signal-chain routing/dividers (no per-block parameters).\n"
        "- get_patch_block: current on/off, type, and knob values for one block (blockId dist1, delay1, preamp1, …).\n"
        "- load_skill_reference: manual/parameter meanings (e.g. wiki-parameter-guide).\n"
        "For questions about current block parameter values, call get_patch_block — not musician-summary. "
        "Never ask the user to paste tool output or re-read the patch.\n\n"
        f"{skill_index_for_prompt()}\n\n"
        "After tool results, answer briefly (low verbosity). "
        "Never include raw JSON or tool payloads in the user-facing reply. "
        "For writes, only describe validated plans; the user must confirm apply in the UI."
    )
    if config.system_prompt_extra.strip():
        return base + "\n\n" + config.system_prompt_extra.strip()
    return base


class AgentService:
    def __init__(self, device: DeviceService, config: AppConfig) -> None:
        self._device = device
        self._config = config

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    async def _iter_provider_deltas(
        self,
        provider: Any,
        messages: list[ChatMessage],
        *,
        visible_filter: VisibleStreamFilter,
    ) -> AsyncIterator[ChatEvent]:
        async with asyncio.timeout(LLM_STREAM_TIMEOUT):
            async for chunk in provider.stream_chat(messages):
                if chunk.content:
                    visible = visible_filter.feed(chunk.content)
                    if visible:
                        yield ChatEvent("assistant.delta", {"content": visible})
                if chunk.done:
                    break
        trailing = visible_filter.flush()
        if trailing:
            yield ChatEvent("assistant.delta", {"content": trailing})

    async def stream_chat(self, user_message: str, history: list[dict[str, str]] | None = None) -> AsyncIterator[ChatEvent]:
        preview = user_message.strip().replace("\n", " ")[:120]
        app_log(
            "info",
            "agent",
            "Chat turn started",
            messagePreview=preview,
            provider=self._config.provider,
            model=self._config.model,
        )
        try:
            async with asyncio.timeout(CHAT_TURN_TIMEOUT):
                async for event in self._stream_chat_turn(user_message, history):
                    yield event
        except TimeoutError:
            app_log("error", "agent", "Chat turn timed out", timeoutSeconds=CHAT_TURN_TIMEOUT)
            yield ChatEvent("error", {"message": f"Chat timed out after {CHAT_TURN_TIMEOUT:g}s"})
            yield ChatEvent(
                "assistant.done",
                {
                    "content": (
                        "Sorry — that took too long (device read or model reply). "
                        "Try again or power-cycle the GT-1000 if reads keep timing out."
                    )
                },
            )

    async def _stream_chat_turn(
        self,
        user_message: str,
        history: list[dict[str, str]] | None,
    ) -> AsyncIterator[ChatEvent]:
        provider = build_provider(self._config)
        messages = [ChatMessage(role="system", content=system_prompt(self._config))]
        for item in history or []:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append(ChatMessage(role=role, content=content))
        messages.append(ChatMessage(role="user", content=user_message))

        api_tools = openai_tools_for_provider(self._config.provider, tool_definitions())

        for round_index in range(MAX_TOOL_ROUNDS):
            yield ChatEvent(
                "assistant.status",
                {"message": "Choosing tools…" if round_index == 0 else "Checking for more tools…"},
            )
            completion = await provider.complete_chat(messages, api_tools)
            if not completion.tool_calls:
                final = completion.content.strip()
                if final:
                    app_log("info", "agent", "Chat turn finished with direct model reply", answerChars=len(final))
                    yield ChatEvent("assistant.done", {"content": final})
                    return
                yield ChatEvent("assistant.status", {"message": "Writing answer…"})
                visible_filter = VisibleStreamFilter()
                summary_visible = ""
                async for event in self._iter_provider_deltas(
                    provider, messages, visible_filter=visible_filter
                ):
                    if event.type == "assistant.delta":
                        summary_visible += str(event.data.get("content") or "")
                    yield event
                final = summary_visible.strip()
                app_log("info", "agent", "Chat turn finished after stream", answerChars=len(final))
                yield ChatEvent("assistant.done", {"content": final})
                return

            app_log(
                "info",
                "agent",
                "Tool calls from model",
                tools=[str(call.get("name")) for call in completion.tool_calls],
                round=round_index + 1,
            )
            if round_index == 0:
                yield ChatEvent("assistant.clear", {})

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=completion.content,
                    tool_calls=tuple(completion.tool_calls),
                )
            )
            for call in completion.tool_calls:
                name = str(call.get("name"))
                arguments = call.get("arguments")
                if not isinstance(arguments, dict):
                    arguments = {}
                call_id = str(call.get("id") or "")
                yield ChatEvent("tool.start", {"name": name, "arguments": arguments})
                status = "Loading reference…" if name in SKILL_TOOL_NAMES else f"Running {name}…"
                yield ChatEvent("assistant.status", {"message": status})
                timeout = 5.0 if name in SKILL_TOOL_NAMES else TOOL_TIMEOUTS.get(name, 45.0)
                app_log("info", "agent", f"Tool start: {name}", tool=name, timeoutSeconds=timeout)
                try:
                    result = await asyncio.wait_for(
                        execute_tool(self._device, name, arguments),
                        timeout=timeout,
                    )
                    app_log("info", "agent", f"Tool done: {name}", tool=name)
                    yield ChatEvent("tool.result", {"name": name})
                    if call_id:
                        messages.append(
                            ChatMessage(
                                role="tool",
                                tool_call_id=call_id,
                                content=json.dumps(compact_tool_result(name, result)),
                            )
                        )
                except Exception as error:
                    app_log("error", "agent", f"Tool failed: {name}", tool=name, error=str(error))
                    yield ChatEvent("tool.error", {"name": name, "error": str(error)})
                    if call_id:
                        messages.append(
                            ChatMessage(
                                role="tool",
                                tool_call_id=call_id,
                                content=json.dumps({"error": str(error)}),
                            )
                        )

        yield ChatEvent("assistant.status", {"message": "Writing answer…"})
        visible_filter = VisibleStreamFilter()
        summary_visible = ""
        async for event in self._iter_provider_deltas(provider, messages, visible_filter=visible_filter):
            if event.type == "assistant.delta":
                summary_visible += str(event.data.get("content") or "")
            yield event
        final = summary_visible.strip()
        app_log("info", "agent", "Chat turn finished after tool rounds", answerChars=len(final))
        yield ChatEvent("assistant.done", {"content": final})
