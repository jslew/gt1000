from __future__ import annotations

import json
import re
from typing import Any

TOOL_CALL_BLOCK = re.compile(r"<tool_call>[\s\S]*?</tool_call>", re.IGNORECASE)
# Legacy alias used by VisibleStreamFilter
TOOL_CALL_PATTERN = TOOL_CALL_BLOCK
PARTIAL_TOOL_TAGS = ("<tool_call>", "</tool_call>")


def _json_object_at(text: str, start: int) -> str | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for opener in re.finditer(r"<tool_call>", text, re.IGNORECASE):
        region_start = opener.end()
        closer = re.search(r"</tool_call>", text[region_start:], re.IGNORECASE)
        if not closer:
            continue
        inner = text[region_start : region_start + closer.start()].strip()
        brace = inner.find("{")
        if brace < 0:
            continue
        payload_text = _json_object_at(inner, brace)
        if not payload_text:
            continue
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("name"):
            calls.append(payload)
    return calls


def strip_tool_calls(text: str) -> str:
    cleaned = TOOL_CALL_BLOCK.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _split_partial_tag_tail(text: str) -> tuple[str, str]:
    for tag in PARTIAL_TOOL_TAGS:
        for length in range(min(len(text), len(tag) - 1), 0, -1):
            if tag.startswith(text[-length:]):
                return text[:-length], text[-length:]
    return text, ""


class VisibleStreamFilter:
    """Strip tool-call markup from streamed assistant text, including partial tags."""

    def __init__(self) -> None:
        self._hold = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._hold += chunk
        self._hold = TOOL_CALL_BLOCK.sub("", self._hold)
        emit, self._hold = _split_partial_tag_tail(self._hold)
        return emit

    def flush(self) -> str:
        self._hold = TOOL_CALL_BLOCK.sub("", self._hold)
        emit, self._hold = _split_partial_tag_tail(self._hold)
        self._hold = ""
        return emit
