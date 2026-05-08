#!/usr/bin/env python3
"""Agent-facing GT-1000 CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from tools.gt1000 import live, patch_edit
except ModuleNotFoundError:
    import live
    import patch_edit


ROOT = Path(__file__).resolve().parents[2]


class CLIError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = args.func(args)
        if result is not None:
            emit(result, pretty=args.pretty)
        return 0
    except CLIError as error:
        print(f"error: {error}", file=sys.stderr)
        return error.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gt1000-agent",
        description="Agent-facing GT-1000 patch inspection CLI.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    subcommands = parser.add_subparsers(dest="command", required=True)

    ports = subcommands.add_parser("ports", help="List live MIDI ports.")
    ports.add_argument("--live", action="store_true", help="Required for live MIDI port reads.")
    ports.set_defaults(func=cmd_ports)

    patch = subcommands.add_parser("patch", help="Inspect GT-1000 patch data.")
    patch_subcommands = patch.add_subparsers(dest="patch_command", required=True)

    overview = patch_subcommands.add_parser("overview", help="Show compact patch metadata.")
    add_input_options(overview)
    overview.set_defaults(func=lambda args: patch_view(args, "overview"))

    chain = patch_subcommands.add_parser("chain", help="Show the signal chain without parameters.")
    add_input_options(chain)
    chain.set_defaults(func=lambda args: patch_view(args, "chain"))

    block = patch_subcommands.add_parser("block", help="Show one block's detailed parameters.")
    add_input_options(block)
    block.add_argument("block_id", nargs="?", help="Block id such as preamp1 or delay1.")
    block.add_argument("--position", type=int, help="Signal-chain position to inspect.")
    block.set_defaults(func=cmd_patch_block)

    dump = patch_subcommands.add_parser("dump", help="Read/write a full diagnostic patch JSON dump.")
    dump.add_argument("--live", action="store_true", help="Read live patch data.")
    dump.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    dump.add_argument("--output", type=Path, help="Write JSON dump to this file instead of stdout.")
    dump.set_defaults(func=cmd_patch_dump)

    inspect = patch_subcommands.add_parser("inspect", help="Inspect a saved full patch JSON dump.")
    inspect.add_argument("file", type=Path, help="Saved full patch JSON file.")
    inspect.add_argument("--view", choices=["overview", "chain", "full"], default="overview")
    inspect.set_defaults(func=cmd_patch_inspect)

    plan = patch_subcommands.add_parser("plan", help="Build a validated patch-write plan without sending it.")
    plan.add_argument("plan_id", choices=["default", "4cm", "4cm-template"], help="Patch plan to build.")
    plan.add_argument("--name", help="Patch name to write into the temporary patch.")
    plan.set_defaults(func=cmd_patch_plan)

    apply = patch_subcommands.add_parser("apply", help="Apply a validated patch-write plan to the temporary patch.")
    apply.add_argument("plan_id", choices=["default", "4cm", "4cm-template"], help="Patch plan to apply.")
    apply.add_argument("--name", help="Patch name to write into the temporary patch.")
    apply.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000 temporary patch.")
    apply.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    apply.add_argument("--verify", action="store_true", help="Re-read every written range and compare exact bytes.")
    apply.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    apply.set_defaults(func=cmd_patch_apply)

    set_param = patch_subcommands.add_parser("set", help="Set one validated block parameter.")
    set_param.add_argument("block_id", help="Block id such as delay1 or dist1.")
    set_param.add_argument("parameter_id", help="Parameter id such as sw, type, time, or drive.")
    set_param.add_argument("value", help="Raw value, on/off, or exact type name.")
    set_param.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    set_param.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    set_param.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    set_param.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    set_param.set_defaults(func=cmd_patch_set)

    return parser


def add_input_options(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--live", action="store_true", help="Read live patch data.")
    source.add_argument("--file", type=Path, help="Inspect a saved full patch JSON dump.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")


def cmd_ports(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("ports requires --live because MIDI ports are live device state", 64)
    return live.list_ports()


def patch_view(args: argparse.Namespace, view: str) -> Any:
    if args.live or args.file is None:
        snapshot = read_live_snapshot(args.timeout, requests=live.INITIAL_READS if view in {"overview", "chain"} else None)
        if view == "chain":
            return chain_from_full(snapshot)
        if view == "overview":
            return overview_from_full(snapshot)
        return snapshot

    snapshot = load_json(args.file)
    if view == "overview":
        return overview_from_full(snapshot)
    if view == "chain":
        return chain_from_full(snapshot)
    raise CLIError(f"unsupported patch view {view}", 64)


def cmd_patch_block(args: argparse.Namespace) -> Any:
    if (args.block_id is None) == (args.position is None):
        raise CLIError("patch block requires exactly one selector: block_id or --position", 64)

    if args.live or args.file is None:
        block_request = None
        if args.block_id is not None:
            block_definition = next((block for block in live.SUMMARY_BLOCKS if block.id == args.block_id), None)
            if block_definition is None:
                raise CLIError(f"unknown block {args.block_id}", 64)
            block_request = live.PatchReadRequest(
                block_definition.display_name,
                block_definition.address,
                live.seven_bit_address(block_definition.size),
            )
        else:
            header_snapshot = read_live_snapshot(args.timeout, requests=live.INITIAL_READS)
            element = next(
                (item for item in header_snapshot.get("signalChainElements", []) if item.get("position") == args.position),
                None,
            )
            if element is None:
                raise CLIError(f"unknown chain position {args.position}", 64)
            block_definition = next(
                (block for block in live.SUMMARY_BLOCKS if block.chain_element_value == element.get("rawValue")),
                None,
            )
            if block_definition is None:
                raise CLIError(
                    f"chain position {args.position} ({element.get('displayName')}) has no decoded detail block",
                    64,
                )
            block_request = live.PatchReadRequest(
                block_definition.display_name,
                block_definition.address,
                live.seven_bit_address(block_definition.size),
            )
        requests = live.INITIAL_READS + ([block_request] if block_request else live.BLOCK_READS)
        snapshot = read_live_snapshot(args.timeout, requests=requests)
        if args.position is not None:
            block = block_for_position(snapshot, args.position)
        else:
            block = block_for_id(snapshot, args.block_id)
        return block_detail_from_full(snapshot, block)

    snapshot = load_json(args.file)
    if args.position is not None:
        block = block_for_position(snapshot, args.position)
    else:
        block = block_for_id(snapshot, args.block_id)
    return block_detail_from_full(snapshot, block)


def cmd_patch_dump(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch dump currently requires --live", 64)

    dump = read_live_snapshot(args.timeout)
    if args.output:
        args.output.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"output": str(args.output), "patchName": dump.get("patchName")}
    return dump


def cmd_patch_inspect(args: argparse.Namespace) -> Any:
    snapshot = load_json(args.file)
    if args.view == "overview":
        return overview_from_full(snapshot)
    if args.view == "chain":
        return chain_from_full(snapshot)
    return snapshot


def cmd_patch_plan(args: argparse.Namespace) -> Any:
    return patch_edit.plan_by_id(args.plan_id, args.name).to_dict()


def cmd_patch_apply(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch apply requires --live because it writes to the connected GT-1000 temporary patch", 64)
    plan = patch_edit.plan_by_id(args.plan_id, args.name)
    if args.user_slot:
        plan = patch_edit.plan_for_user_slot(plan, args.user_slot)
    try:
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch set requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_parameter_set_plan(args.block_id, args.parameter_id, args.value, slot=args.user_slot)
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def read_live_snapshot(timeout: float, requests: list[live.PatchReadRequest] | None = None) -> dict[str, Any]:
    try:
        return live.read_current_patch(timeout=timeout, requests=requests)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CLIError(f"file not found: {path}", 66) from error
    except json.JSONDecodeError as error:
        raise CLIError(f"invalid JSON in {path}: {error}", 65) from error

    if not isinstance(value, dict):
        raise CLIError(f"expected top-level JSON object in {path}", 65)
    return value


def overview_from_full(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "patchName": snapshot.get("patchName"),
        "masterBPM": snapshot.get("masterBPM"),
        "masterPatchLevel": snapshot.get("masterPatchLevel"),
        "masterKey": snapshot.get("masterKey"),
        "ampControl1Enabled": snapshot.get("ampControl1Enabled"),
        "ampControl2Enabled": snapshot.get("ampControl2Enabled"),
        "signalChainElementCount": len(snapshot.get("signalChainElements", [])),
        "detailBlockCount": len(snapshot.get("blocks", [])),
    }


def chain_from_full(snapshot: dict[str, Any]) -> dict[str, Any]:
    blocks = snapshot.get("blocks", [])
    detail_by_value = {
        block.get("chainElementValue"): block
        for block in blocks
        if block.get("chainElementValue") is not None
    }
    elements = []
    description_elements = []
    for element in snapshot.get("signalChainElements", []):
        block = detail_by_value.get(element.get("rawValue"))
        is_enabled = block.get("isEnabled") if block else None
        has_control_assignment = block_has_control_assignment(block)
        description_candidate = include_element_in_description(
            element,
            block,
            is_enabled=is_enabled,
            has_control_assignment=has_control_assignment,
        )
        chain_element = {
            "id": element.get("id"),
            "position": element.get("position"),
            "displayName": element.get("displayName"),
            "detailBlockID": block.get("id") if block else None,
            "isEnabled": is_enabled,
            "hasControlAssignment": has_control_assignment,
            "includeInDescription": description_candidate,
            "isReserved": element.get("isReserved", False),
            "isOutput": element.get("isOutput", False),
        }
        elements.append(chain_element)
        if description_candidate:
            description_elements.append(chain_element)

    return {
        "overview": overview_from_full(snapshot),
        "signalChainSummary": " -> ".join(
            element["displayName"] for element in elements if element.get("displayName")
        ),
        "descriptionSignalChainSummary": " -> ".join(
            element["displayName"] for element in description_elements if element.get("displayName")
        ),
        "descriptionPolicy": (
            "Omits reserved elements and switched-off blocks unless a decoded hardware/control "
            "assignment indicates the user can bring that block into the live sound."
        ),
        "elements": elements,
        "descriptionElements": description_elements,
    }


def block_has_control_assignment(block: dict[str, Any] | None) -> bool:
    if not block:
        return False

    direct_flags = [
        block.get("hasControlAssignment"),
        block.get("hasHardwareAssignment"),
        block.get("hasActiveAssign"),
        block.get("isAssignedToControl"),
    ]
    if any(value is True for value in direct_flags):
        return True

    controls = block.get("assignedControls")
    return isinstance(controls, list) and len(controls) > 0


def include_element_in_description(
    element: dict[str, Any],
    block: dict[str, Any] | None,
    *,
    is_enabled: Any,
    has_control_assignment: bool,
) -> bool:
    if element.get("isReserved", False):
        return False
    if element.get("isOutput", False):
        return True
    if block is None:
        return True
    if is_enabled is False and not has_control_assignment:
        return False
    return True


def block_for_id(snapshot: dict[str, Any], block_id: str | None) -> dict[str, Any]:
    for block in snapshot.get("blocks", []):
        if block.get("id") == block_id:
            return block
    raise CLIError(f"unknown block {block_id}", 64)


def block_for_position(snapshot: dict[str, Any], position: int) -> dict[str, Any]:
    element = next(
        (item for item in snapshot.get("signalChainElements", []) if item.get("position") == position),
        None,
    )
    if element is None:
        raise CLIError(f"unknown chain position {position}", 64)
    raw_value = element.get("rawValue")
    for block in snapshot.get("blocks", []):
        if block.get("chainElementValue") == raw_value:
            return block
    raise CLIError(
        f"chain position {position} ({element.get('displayName')}) has no decoded detail block",
        64,
    )


def block_detail_from_full(snapshot: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    positions = [
        element.get("position")
        for element in snapshot.get("signalChainElements", [])
        if element.get("rawValue") == block.get("chainElementValue")
    ]
    return {
        "overview": overview_from_full(snapshot),
        "chainPositions": positions,
        "block": block,
    }


def emit(value: Any, pretty: bool) -> None:
    indent = 2 if pretty else None
    print(json.dumps(value, indent=indent, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
