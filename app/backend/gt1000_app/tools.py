from __future__ import annotations

import json
from typing import Any

from gt1000_app.device import DeviceService

try:
    from skills.gt1000.tools.gt1000 import patch_edit
except ModuleNotFoundError:
    from tools.gt1000 import patch_edit  # type: ignore


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_patch_chain",
        "description": "Read the current temporary patch signal chain from the GT-1000.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_patch_overview",
        "description": "Read compact metadata for the current temporary patch.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_patch_controls",
        "description": "Read footswitch, expression pedal, and Assign mappings for the current patch.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_patch_musician_summary",
        "description": "Read a musician-facing summary of the current patch.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_patch_block",
        "description": (
            "Read detailed parameters for one effect block on the current temporary patch "
            "(e.g. dist1, delay1, preamp1). Use for current on/off, type, and knob values."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "blockId": {
                    "type": "string",
                    "description": "Block id such as dist1, distortion1, delay1, preamp1, chorus.",
                },
            },
            "required": ["blockId"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_ports",
        "description": "List CoreMIDI ports visible for the GT-1000.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "plan_patch",
        "description": "Build a validated patch write plan without sending MIDI.",
        "parameters": {
            "type": "object",
            "properties": {
                "planId": {"type": "string", "description": "Plan id such as default or 4cm-template."},
                "name": {"type": "string"},
                "userSlot": {"type": "string", "description": "Optional user slot like U10-1."},
            },
            "required": ["planId"],
            "additionalProperties": False,
        },
    },
]


async def execute_tool(device: DeviceService, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    if name == "load_skill_reference":
        from gt1000_app.skill_context import load_skill_reference

        doc_id = str(args.get("docId") or args.get("doc_id") or "")
        return load_skill_reference(doc_id)
    if name == "get_patch_chain":
        return await device.patch_chain()
    if name == "get_patch_overview":
        return await device.patch_overview()
    if name == "get_patch_controls":
        return await device.patch_controls()
    if name == "get_patch_musician_summary":
        return await device.patch_musician_summary()
    if name == "get_patch_block":
        block_id = str(args.get("blockId") or args.get("block_id") or "").strip()
        if not block_id:
            raise ValueError("blockId is required")
        return await device.patch_block(block_id)
    if name == "list_ports":
        return await device.ports()
    if name == "plan_patch":
        return await device.build_plan(
            str(args.get("planId") or args.get("plan_id")),
            name=args.get("name"),
            user_slot=args.get("userSlot") or args.get("user_slot"),
        )
    raise ValueError(f"unknown tool {name}")


def tools_prompt() -> str:
    from gt1000_app.skill_context import all_tool_definitions

    return json.dumps(all_tool_definitions(), indent=2)
