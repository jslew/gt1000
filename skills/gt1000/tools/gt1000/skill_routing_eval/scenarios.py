"""Load routing eval scenarios and sync with skill-routing-index.md."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PatternRule:
    pattern: str
    flags: int = re.IGNORECASE

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, self.flags)

    def matches(self, text: str) -> bool:
        return bool(self.compiled().search(text))


@dataclass
class FirstCliRule:
    """First gt1000-agent invocation must match this CLI tail."""

    match: str
    require_live: bool = False
    require_verify: bool = False
    timeout: int | None = None

    def matches_invocation(self, invocation: str) -> bool:
        if self.match not in invocation:
            return False
        if self.require_live and "--live" not in invocation:
            return False
        if self.require_verify and "--verify" not in invocation:
            return False
        if self.timeout is not None and f"--timeout {self.timeout}" not in invocation:
            return False
        return True


@dataclass
class Scenario:
    id: str
    index_intent: str = ""
    user_messages: list[str] = field(default_factory=list)
    first_cli: FirstCliRule | None = None
    allowed_before_first_cli: list[PatternRule] = field(default_factory=list)
    forbidden_before_first_cli: list[PatternRule] = field(default_factory=list)
    forbidden_anywhere: list[PatternRule] = field(default_factory=list)
    max_gt1000_commands_before_escalate: int | None = None
    forbidden_after_harness: list[PatternRule] = field(default_factory=list)
    notes: str = ""

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Scenario:
        first = data.get("first_cli")
        first_cli = None
        if first:
            first_cli = FirstCliRule(
                match=first["match"],
                require_live=bool(first.get("require_live")),
                require_verify=bool(first.get("require_verify")),
                timeout=first.get("timeout"),
            )
        return Scenario(
            id=data["id"],
            index_intent=data.get("index_intent", ""),
            user_messages=list(data.get("user_messages", [])),
            first_cli=first_cli,
            allowed_before_first_cli=[
                PatternRule(p["pattern"], _flag_int(p.get("flags", "i")))
                for p in data.get("allowed_before_first_cli", [])
            ],
            forbidden_before_first_cli=[
                PatternRule(p["pattern"], _flag_int(p.get("flags", "i")))
                for p in data.get("forbidden_before_first_cli", [])
            ],
            forbidden_anywhere=[
                PatternRule(p["pattern"], _flag_int(p.get("flags", "i")))
                for p in data.get("forbidden_anywhere", [])
            ],
            max_gt1000_commands_before_escalate=data.get(
                "max_gt1000_commands_before_escalate"
            ),
            forbidden_after_harness=[
                PatternRule(p["pattern"], _flag_int(p.get("flags", "i")))
                for p in data.get("forbidden_after_harness", [])
            ],
            notes=data.get("notes", ""),
        )


def _flag_int(flags: str) -> int:
    value = 0
    if "i" in flags.lower():
        value |= re.IGNORECASE
    return value or re.IGNORECASE


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged


def load_scenarios(path: Path) -> dict[str, Scenario]:
    data = json.loads(path.read_text())
    defaults = data.get("defaults", {})
    out: dict[str, Scenario] = {}
    for raw in data.get("scenarios", []):
        scenario = Scenario.from_dict(_merge_dict(defaults, raw))
        out[scenario.id] = scenario
    return out


_INTENT_ROW_RE = re.compile(
    r"^\|\s*(?P<intent>[^|]+?)\s*\|\s*`(?P<first>[^`]+)`\s*\|\s*(?P<escalate>[^|]*)\|\s*$"
)


def parse_index_intents(index_path: Path) -> dict[str, str]:
    """Map index_intent label → first CLI cell from skill-routing-index.md."""
    text = index_path.read_text()
    start = text.find("## Intent routing")
    if start == -1:
        return {}
    section = text[start:]
    intents: dict[str, str] = {}
    for line in section.splitlines():
        match = _INTENT_ROW_RE.match(line.strip())
        if not match or match.group("intent").startswith("---"):
            continue
        intent = match.group("intent").strip()
        first = match.group("first").strip()
        intents[intent] = first
    return intents


def index_intent_to_scenario_id(intent: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", intent.lower()).strip("_")
    return slug


def default_scenarios_path(repo_root: Path) -> Path:
    return repo_root / "tests" / "skill_routing_eval" / "scenarios.json"
