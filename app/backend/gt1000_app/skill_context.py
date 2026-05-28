from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_SKILL_DOC_CHARS = 14_000

# Repo skill root: skills/gt1000 relative to gt1000 project root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_DIR = _REPO_ROOT / "skills" / "gt1000"

_SKILL_DOCS: dict[str, tuple[str, str]] = {
    "skill-routing": ("SKILL.md", "Progressive Disclosure Routing"),
    "skill-scope": ("SKILL.md", "Scope"),
    "wiki-owner-manual": ("references/gt1000-wiki/owner-manual.md", None),
    "wiki-parameter-guide": ("references/gt1000-wiki/parameter-guide.md", None),
    "wiki-agent-workflows": ("references/gt1000-wiki/agent-workflows.md", None),
    "wiki-readme": ("references/gt1000-wiki/README.md", None),
    "midi-patch-effect": ("references/midi-reference/patch-effect.md", None),
    "midi-patch-controls": ("references/midi-reference/patch-controls.md", None),
    "midi-assigns": ("references/midi-reference/assigns.md", None),
    "midi-readme": ("references/midi-reference/README.md", None),
    "midi-cli-usage": ("references/midi-reference/cli-usage.md", None),
    "profile-onboarding": ("references/user-profile-onboarding.md", None),
}


def skill_dir() -> Path:
    return _SKILL_DIR


def skill_doc_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": doc_id,
            "path": rel_path,
            "section": section or "(full file)",
            "hint": _doc_hint(doc_id),
        }
        for doc_id, (rel_path, section) in _SKILL_DOCS.items()
    ]


def _doc_hint(doc_id: str) -> str:
    hints = {
        "skill-routing": "When to use patch tools vs open reference docs",
        "skill-scope": "Musician-facing scope and response style",
        "wiki-owner-manual": "Play screen, STOMPBOX, device concepts",
        "wiki-parameter-guide": "Parameter meanings and block types",
        "wiki-agent-workflows": "Agent workflows for patch work",
        "midi-patch-effect": "Divider/branch/mixer routing and chain bytes",
        "midi-patch-controls": "Footswitches, CTL, CUR NUM, Assign overlays",
        "midi-assigns": "Assign sources, targets, CC mapping quirks",
        "midi-readme": "SysEx/MIDI index",
        "midi-cli-usage": "CLI command surface (internal)",
        "profile-onboarding": "User profile interview",
    }
    return hints.get(doc_id, "")


def _extract_section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    next_heading = re.search(r"\n##\s+", text[start:])
    end = start + next_heading.start() if next_heading else len(text)
    return text[match.start() : end].strip()


def load_skill_reference(doc_id: str) -> dict[str, Any]:
    doc_id = doc_id.strip().lower().replace("_", "-")
    entry = _SKILL_DOCS.get(doc_id)
    if not entry:
        return {
            "error": f"Unknown doc id {doc_id!r}",
            "available": sorted(_SKILL_DOCS.keys()),
        }
    rel_path, section = entry
    path = _SKILL_DIR / rel_path
    if not path.is_file():
        return {"error": f"Skill file missing: {path}"}
    text = path.read_text(encoding="utf-8")
    if section:
        extracted = _extract_section(text, section)
        if extracted is None:
            return {"error": f"Section {section!r} not found in {rel_path}"}
        text = extracted
    if len(text) > MAX_SKILL_DOC_CHARS:
        text = text[:MAX_SKILL_DOC_CHARS] + "\n\n… (truncated)"
    return {
        "docId": doc_id,
        "path": str(path.relative_to(_REPO_ROOT)),
        "section": section,
        "chars": len(text),
        "content": text,
    }


def skill_index_for_prompt() -> str:
    lines = ["Load extra GT-1000 skill/reference text with load_skill_reference when needed:"]
    for item in skill_doc_catalog():
        lines.append(f"- {item['id']}: {item['hint']}")
    return "\n".join(lines)


def skill_tool_definition() -> dict[str, Any]:
    return {
        "name": "load_skill_reference",
        "description": (
            "Load a section of the bundled GT-1000 musician skill or reference wiki. "
            "Use for routing/divider/mixer questions, control/Assign details, parameter meanings, "
            "or safe-edit rules — instead of guessing. Does not touch the device."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "docId": {
                    "type": "string",
                    "description": (
                        "Document id, e.g. skill-routing, midi-patch-effect, midi-assigns, "
                        "wiki-parameter-guide"
                    ),
                },
            },
            "required": ["docId"],
            "additionalProperties": False,
        },
    }


def all_tool_definitions() -> list[dict[str, Any]]:
    from gt1000_app.tools import TOOL_DEFINITIONS

    return TOOL_DEFINITIONS + [skill_tool_definition()]
