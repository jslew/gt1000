"""Parse agent shell traces and agy/Gemini CLI chat JSONL into a normalized event timeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


EventKind = Literal["user", "harness", "shell", "reference_read", "other"]


@dataclass
class TraceEvent:
    kind: EventKind
    text: str = ""
    command: str = ""

    @property
    def is_gt1000_cli(self) -> bool:
        return self.kind == "shell" and (
            "gt1000-agent" in self.command or "agent_cli.py" in self.command
        )


@dataclass
class Trace:
    scenario_id: str | None = None
    events: list[TraceEvent] = field(default_factory=list)
    expect_fail: bool = False
    notes: str = ""

    def shell_commands(self) -> list[str]:
        return [e.command for e in self.events if e.kind == "shell" and e.command]

    def gt1000_commands(self) -> list[str]:
        return [e.command for e in self.events if e.is_gt1000_cli]

    def user_messages(self) -> list[str]:
        return [e.text for e in self.events if e.kind == "user" and e.text.strip()]

    def harness_messages(self) -> list[str]:
        return [e.text for e in self.events if e.kind == "harness" and e.text.strip()]


_GT1000_RE = re.compile(
    r"(?:gt1000-agent|agent_cli\.py)\s+(.*)$",
    re.IGNORECASE,
)
_REF_READ_RE = re.compile(
    r"(?:grep|cat|sed|head)\s+.*\breferences/",
    re.IGNORECASE,
)
_CHAINED_LIVE_RE = re.compile(
    r"gt1000-agent.*&&.*gt1000-agent|agent_cli\.py.*&&.*agent_cli\.py",
    re.IGNORECASE,
)


def classify_shell_command(command: str) -> EventKind:
    if _REF_READ_RE.search(command):
        return "reference_read"
    return "shell"


def extract_gt1000_invocation(command: str) -> str | None:
    """Return the portion after gt1000-agent / agent_cli.py, or None."""
    for token in ("gt1000-agent", "agent_cli.py"):
        idx = command.lower().find(token)
        if idx == -1:
            continue
        tail = command[idx:]
        match = _GT1000_RE.search(tail.replace("\n", " "))
        if match:
            return match.group(1).strip()
        # Fallback: everything after script name
        parts = tail.split(None, 2)
        if len(parts) >= 2:
            return " ".join(parts[1:]).strip()
    return None


def load_trace(path: Path) -> Trace:
    data = json.loads(path.read_text())
    trace = Trace(
        scenario_id=data.get("scenario_id"),
        expect_fail=bool(data.get("expect_fail")),
        notes=data.get("notes", ""),
    )
    for raw in data.get("events", []):
        trace.events.append(_event_from_dict(raw))
    return trace


def _event_from_dict(raw: dict[str, Any]) -> TraceEvent:
    kind = raw.get("type") or raw.get("kind") or "other"
    if kind not in ("user", "harness", "shell", "reference_read", "other"):
        kind = "other"
    text = str(raw.get("text", "") or "")
    command = str(raw.get("command", "") or "")
    if kind == "shell" and command:
        kind = classify_shell_command(command)
    return TraceEvent(kind=kind, text=text, command=command)  # type: ignore[arg-type]


def trace_from_gemini_jsonl(path: Path) -> Trace:
    """Build a trace from an agy or Gemini CLI session JSONL export."""
    trace = Trace()
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('{"$set"'):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") == "user":
            for part in row.get("content", []) or []:
                if isinstance(part, dict):
                    text = part.get("text", "")
                    if text and "System: Please continue" in text:
                        trace.events.append(
                            TraceEvent(kind="harness", text=text.strip())
                        )
                    elif text.strip():
                        trace.events.append(TraceEvent(kind="user", text=text.strip()))
        elif row.get("type") == "gemini":
            for tc in row.get("toolCalls", []) or []:
                if tc.get("name") != "run_shell_command":
                    continue
                cmd = (tc.get("args") or {}).get("command", "")
                if not cmd:
                    continue
                trace.events.append(
                    TraceEvent(
                        kind=classify_shell_command(cmd),
                        command=cmd,
                    )
                )
    return trace


trace_from_agy_jsonl = trace_from_gemini_jsonl


def trace_from_command_list(commands: list[str], **kwargs: Any) -> Trace:
    trace = Trace(**{k: v for k, v in kwargs.items() if k in ("scenario_id", "expect_fail", "notes")})
    for command in commands:
        trace.events.append(
            TraceEvent(kind=classify_shell_command(command), command=command)
        )
    return trace
