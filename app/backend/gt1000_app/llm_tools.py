from __future__ import annotations

import json
from typing import Any

from gt1000_app.skill_context import all_tool_definitions


def tool_definitions() -> list[dict[str, Any]]:
    return all_tool_definitions()


def to_chat_completions_tools(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for item in definitions:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "parameters": item.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return tools


def to_responses_tools(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for item in definitions:
        tools.append(
            {
                "type": "function",
                "name": item["name"],
                "description": item.get("description", ""),
                "parameters": item.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return tools


def to_ollama_tools(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return to_chat_completions_tools(definitions)


def parse_tool_call_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_tool_calls(raw_calls: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for call in raw_calls or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        if not name and isinstance(call.get("function"), dict):
            name = call["function"].get("name")
        if not name:
            continue
        arguments = parse_tool_call_arguments(call.get("arguments"))
        if not arguments and isinstance(call.get("function"), dict):
            arguments = parse_tool_call_arguments(call["function"].get("arguments"))
        normalized.append(
            {
                "id": str(call.get("id") or call.get("call_id") or ""),
                "name": str(name),
                "arguments": arguments,
            }
        )
    return normalized
