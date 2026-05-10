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

    system = subcommands.add_parser("system", help="Inspect GT-1000 system/global MIDI sections.")
    system_subcommands = system.add_subparsers(dest="system_command", required=True)
    for name, help_text in [
        ("midi", "Read global MIDI settings."),
        ("inout", "Read global input/output settings."),
        ("controls", "Read global control preference settings."),
    ]:
        system_view = system_subcommands.add_parser(name, help=help_text)
        system_view.add_argument("--live", action="store_true", help="Required because system settings are live device state.")
        system_view.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
        system_view.set_defaults(func=cmd_system_view)

    patch = subcommands.add_parser("patch", help="Inspect GT-1000 patch data.")
    patch_subcommands = patch.add_subparsers(dest="patch_command", required=True)

    overview = patch_subcommands.add_parser("overview", help="Show compact patch metadata.")
    add_input_options(overview)
    overview.set_defaults(func=lambda args: patch_view(args, "overview"))

    chain = patch_subcommands.add_parser("chain", help="Show the signal chain without parameters.")
    add_input_options(chain)
    chain.set_defaults(func=lambda args: patch_view(args, "chain"))

    controls = patch_subcommands.add_parser("controls", help="Show physical control mappings and active Assigns.")
    add_input_options(controls)
    controls.set_defaults(func=lambda args: patch_view(args, "controls"))

    summary = patch_subcommands.add_parser("summary", help="Show aggregated patch overview, chain, and controls.")
    add_input_options(summary)
    summary.set_defaults(func=lambda args: patch_view(args, "summary"))

    slot = patch_subcommands.add_parser("slot", help="Read one persistent user patch slot without selecting it.")
    slot.add_argument("slot", help="User slot such as U01-1.")
    slot.add_argument("--live", action="store_true", help="Required because user slots are read from the connected GT-1000.")
    slot.add_argument("--view", choices=["overview", "chain", "controls", "summary", "full"], default="summary")
    slot.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    slot.set_defaults(func=cmd_patch_slot)

    bank = patch_subcommands.add_parser("bank", help="Read all five patches in a persistent user bank.")
    bank.add_argument("bank", help="User bank such as U01.")
    bank.add_argument("--live", action="store_true", help="Required because user banks are read from the connected GT-1000.")
    bank.add_argument("--view", choices=["overview", "chain", "controls", "summary", "full"], default="summary")
    bank.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds per slot.")
    bank.set_defaults(func=cmd_patch_bank)

    select = patch_subcommands.add_parser("select", help="Select a user patch slot with typed MIDI Program Change.")
    select.add_argument("slot", help="User slot such as U01-1.")
    select.add_argument("--live", action="store_true", help="Required because this sends MIDI to the connected GT-1000.")
    select.add_argument("--channel", type=int, default=1, help="1-based MIDI channel for Program Change, default 1.")
    select.set_defaults(func=cmd_patch_select)

    block = patch_subcommands.add_parser("block", help="Show one block's detailed parameters.")
    add_input_options(block)
    block.add_argument("block_id", nargs="?", help="Block id such as preamp1 or delay1.")
    block.add_argument("--position", type=int, help="Signal-chain position to inspect.")
    block.add_argument("--user-slot", help="Read the block from a persistent user slot such as U01-1.")
    block.set_defaults(func=cmd_patch_block)

    dump = patch_subcommands.add_parser("dump", help="Read/write a full diagnostic patch JSON dump.")
    dump.add_argument("--live", action="store_true", help="Read live patch data.")
    dump.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    dump.add_argument("--output", type=Path, help="Write JSON dump to this file instead of stdout.")
    dump.set_defaults(func=cmd_patch_dump)

    inspect = patch_subcommands.add_parser("inspect", help="Inspect a saved full patch JSON dump.")
    inspect.add_argument("file", type=Path, help="Saved full patch JSON file.")
    inspect.add_argument("--view", choices=["overview", "chain", "summary", "full"], default="overview")
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


def cmd_system_view(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("system views require --live because system settings are live device state", 64)
    sections = {
        "midi": ("systemMidi", "System MIDI", live.SYSTEM_MIDI, [0x00, 0x00, 0x00, 0x40], decode_system_midi),
        "inout": ("systemInOut", "System IN/OUT", live.SYSTEM_IN_OUT, [0x00, 0x00, 0x00, 0x60], decode_system_inout),
        "controls": ("systemControl", "System Control", live.SYSTEM_CONTROL, [0x00, 0x00, 0x00, 0x36], decode_system_controls),
    }
    section_id, label, address, size, decoder = sections[args.system_command]
    try:
        raw = live.read_system_section(address, size, timeout=args.timeout)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    data = raw.get(live.address_key(address), [])
    return {
        "id": section_id,
        "label": label,
        "address": live.hex_bytes(address),
        "size": live.hex_bytes(size),
        "dataHex": live.hex_string(data),
        "decoded": decoder(data),
    }


def resolve_block_id(block_id: str) -> str:
    aliases = {
        "distortion1": "dist1",
        "distortion2": "dist2",
        "ds1": "dist1",
        "ds2": "dist2",
        "preamp1": "preamp1",
        "preamp2": "preamp2",
        "sendreturn1": "sendReturn1",
        "sendreturn2": "sendReturn2",
        "sr1": "sendReturn1",
        "sr2": "sendReturn2",
    }
    lower_id = block_id.lower()
    if lower_id in aliases:
        return aliases[lower_id]

    all_definitions = list(live.SUMMARY_BLOCKS) + list(live.RESIDENT_BLOCKS)
    for block in all_definitions:
        if block.id.lower() == lower_id:
            return block.id
    return block_id


def patch_view(args: argparse.Namespace, view: str) -> Any:
    if args.live or args.file is None:
        assign_requests = [
            live.PatchReadRequest(f"Assign {i}", live.address_adding(live.ASSIGN_BASE, (i-1)*live.ASSIGN_STRIDE), [0x00, 0x00, 0x00, 0x2C])
            for i in range(1, 17)
        ] if view in {"controls", "summary"} else []
        
        snapshot = read_live_snapshot(args.timeout, requests=live.READ_PLAN + assign_requests if view in {"controls", "summary"} else live.READ_PLAN if view == "chain" else live.INITIAL_READS)
        if view == "chain":
            return chain_from_full(snapshot)
        if view == "overview":
            return overview_from_full(snapshot)
        if view == "controls":
            return controls_from_full(snapshot)
        if view == "summary":
            return summary_from_full(snapshot)
        return snapshot

    snapshot = load_json(args.file)
    if view == "overview":
        return overview_from_full(snapshot)
    if view == "chain":
        return chain_from_full(snapshot)
    if view == "controls":
        return controls_from_full(snapshot)
    if view == "summary":
        return summary_from_full(snapshot)
    raise CLIError(f"unsupported patch view {view}", 64)


def cmd_patch_slot(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch slot requires --live because user slots are live device state", 64)
    try:
        snapshot = read_user_slot_snapshot(args.slot, args.timeout, view=args.view)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    return view_from_full(snapshot, args.view)


def cmd_patch_bank(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch bank requires --live because user banks are live device state", 64)
    try:
        bank = live.normalize_user_bank(args.bank)
        patches = [
            {
                "slot": slot,
                "address": live.hex_bytes(live.user_patch_base(slot)),
                "view": args.view,
                "data": view_from_full(read_user_slot_snapshot(slot, args.timeout, view=args.view), args.view),
            }
            for slot in live.user_bank_slots(bank)
        ]
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    return {"bank": bank, "patches": patches}


def cmd_patch_select(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch select requires --live because it sends MIDI to the connected GT-1000", 64)
    try:
        slot = live.normalize_user_slot(args.slot)
        message = program_change_for_slot(slot, args.channel)
        live.send_channel_voice(message)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    return {
        "selectedSlot": slot,
        "channel": args.channel,
        "messageHex": live.hex_string(message),
        "note": "Selection uses MIDI Program Change and is subject to the GT-1000 RX channel and program-map settings.",
    }


def cmd_patch_block(args: argparse.Namespace) -> Any:
    if (args.block_id is None) == (args.position is None):
        raise CLIError("patch block requires exactly one selector: block_id or --position", 64)

    if args.user_slot:
        snapshot = read_user_slot_snapshot(args.user_slot, args.timeout, view="full")
        if args.position is not None:
            block = block_for_position(snapshot, args.position)
        else:
            args.block_id = resolve_block_id(args.block_id)
            block = block_for_id(snapshot, args.block_id)
        return block_detail_from_full(snapshot, block)

    if args.live or args.file is None:
        block_request = None
        if args.block_id is not None:
            args.block_id = resolve_block_id(args.block_id)
            all_definitions = list(live.SUMMARY_BLOCKS) + list(live.RESIDENT_BLOCKS)
            block_definition = next((block for block in all_definitions if block.id == args.block_id), None)
            if block_definition is None:
                raise CLIError(f"unknown block {args.block_id}", 64)
            
            if isinstance(block_definition, live.BlockDefinition):
                block_request = live.PatchReadRequest(
                    block_definition.display_name,
                    block_definition.address,
                    live.seven_bit_address(block_definition.size),
                )
            else:
                # Resident blocks are at fixed offsets in the PatchEfct record
                block_request = live.INITIAL_READS[2] # Patch Effect record
        else:
            header_snapshot = read_live_snapshot(args.timeout, requests=live.INITIAL_READS)
            element = next(
                (item for item in header_snapshot.get("signalChainElements", []) if item.get("position") == args.position),
                None,
            )
            if element is None:
                raise CLIError(f"unknown chain position {args.position}", 64)
            
            all_definitions = list(live.SUMMARY_BLOCKS) + list(live.RESIDENT_BLOCKS)
            block_definition = next(
                (block for block in all_definitions if block.chain_element_value == element.get("rawValue")),
                None,
            )
            if block_definition is None:
                raise CLIError(
                    f"chain position {args.position} ({element.get('displayName')}) has no decoded detail block",
                    64,
                )
            
            if isinstance(block_definition, live.BlockDefinition):
                block_request = live.PatchReadRequest(
                    block_definition.display_name,
                    block_definition.address,
                    live.seven_bit_address(block_definition.size),
                )
            else:
                block_request = live.INITIAL_READS[2] # Patch Effect record

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
        args.block_id = resolve_block_id(args.block_id)
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
    if args.view == "summary":
        return summary_from_full(snapshot)
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
        args.block_id = resolve_block_id(args.block_id)
        plan = patch_edit.build_parameter_set_plan(args.block_id, args.parameter_id, args.value, slot=args.user_slot)
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def summary_from_full(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "overview": overview_from_full(snapshot),
        "chain": chain_from_full(snapshot),
        "controls": controls_from_full(snapshot),
    }



def read_live_snapshot(timeout: float, requests: list[live.PatchReadRequest] | None = None) -> dict[str, Any]:
    try:
        return live.read_current_patch(timeout=timeout, requests=requests)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def read_user_slot_snapshot(slot: str, timeout: float, *, view: str) -> dict[str, Any]:
    requests = requests_for_view(view)
    try:
        return live.read_user_patch(slot, timeout=timeout, requests=requests)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def requests_for_view(view: str) -> list[live.PatchReadRequest]:
    assign_requests = [
        live.PatchReadRequest(f"Assign {i}", live.address_adding(live.ASSIGN_BASE, (i - 1) * live.ASSIGN_STRIDE), [0x00, 0x00, 0x00, 0x2C])
        for i in range(1, 17)
    ]
    if view in {"controls", "summary"}:
        return live.READ_PLAN + assign_requests
    if view == "chain":
        return live.READ_PLAN
    if view == "overview":
        return live.INITIAL_READS
    return live.READ_PLAN + assign_requests


def program_change_for_slot(slot: str, channel: int) -> list[int]:
    normalized = live.normalize_user_slot(slot)
    if not 1 <= channel <= 16:
        raise ValueError("MIDI channel must be 1...16")
    bank = int(normalized[1:3])
    number = int(normalized.split("-", 1)[1])
    patch_index = (bank - 1) * live.USER_PATCHES_PER_BANK + number
    program = patch_index - 1
    if program > 127:
        raise ValueError("patch select currently supports U01-1 through U26-3; higher slots need bank-select mapping validation")
    return [0xC0 + (channel - 1), program]


def view_from_full(snapshot: dict[str, Any], view: str) -> Any:
    if view == "overview":
        return overview_from_full(snapshot)
    if view == "chain":
        return chain_from_full(snapshot)
    if view == "controls":
        return controls_from_full(snapshot)
    if view == "summary":
        return summary_from_full(snapshot)
    if view == "full":
        return snapshot
    raise CLIError(f"unsupported patch view {view}", 64)


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
        "masterCarryoverEnabled": snapshot.get("masterCarryoverEnabled"),
        "controlAssignTempoHoldEnabled": snapshot.get("controlAssignTempoHoldEnabled"),
        "controlAssignInputSensitivity": snapshot.get("controlAssignInputSensitivity"),
        "signalChainElementCount": len(snapshot.get("signalChainElements", [])),
        "detailBlockCount": len(snapshot.get("blocks", [])),
    }


def controls_from_full(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_sections = {s["id"]: bytes.fromhex(s["dataHex"].replace(" ", "")) for s in snapshot.get("rawSections", [])}
    patch_common = raw_sections.get("patchCommon")
    system_control = raw_sections.get("systemControl")

    if not patch_common or not system_control:
        raise CLIError("missing patchCommon or systemControl raw data in snapshot", 64)

    controls = {}
    
    # Define physical switches and their offsets in PatchCommon and SystemControl
    switches = [
        ("NUM 1", 0x23, 0x23), ("NUM 2", 0x25, 0x24), ("NUM 3", 0x27, 0x25),
        ("NUM 4", 0x29, 0x26), ("NUM 5", 0x2B, 0x27),
        ("BANK DOWN", 0x2D, 0x28), ("BANK UP", 0x2F, 0x29),
        ("CTL 1", 0x31, 0x2A), ("CTL 2", 0x33, 0x2B), ("CTL 3", 0x35, 0x2C),
        ("CTL 4", 0x37, 0x2D), ("CTL 5", 0x39, 0x2E), ("CTL 6", 0x3B, 0x2F), ("CTL 7", 0x3D, 0x30),
        ("CUR NUM", 0x3F, 0x31), ("EXP 1 SW", 0x41, 0x32),
    ]

    for name, patch_offset, system_pref_offset in switches:
        preference = "SYSTEM" if system_control[system_pref_offset] == 1 else "PATCH"
        func_byte = system_control[patch_offset - 0x23] if preference == "SYSTEM" else patch_common[patch_offset]
        mode_byte = system_control[patch_offset - 0x23 + 1] if preference == "SYSTEM" else patch_common[patch_offset + 1]
        
        controls[name] = {
            "preference": preference,
            "function": decode_control_function(func_byte, is_num="NUM" in name),
            "mode": "MOMENT" if mode_byte == 1 else "TOGGLE",
        }

    # EXP Pedals
    exp_pedals = [("EXP 1", 0x43, 0x33), ("EXP 2", 0x44, 0x34), ("EXP 3", 0x45, 0x35)]
    for name, patch_offset, system_pref_offset in exp_pedals:
        preference = "SYSTEM" if system_control[system_pref_offset] == 1 else "PATCH"
        func_byte = system_control[patch_offset - 0x23] if preference == "SYSTEM" else patch_common[patch_offset]
        controls[name] = {
            "preference": preference,
            "function": decode_exp_function(func_byte),
        }

    # Active Assigns
    assigns = []
    # Assign data is currently stored in rawSections as Assign 1...16
    for i in range(1, 17):
        data = raw_sections.get(f"Assign {i}")
        if data and data[0] == 1: # SW == ON
            assigns.append(assign_from_data(f"Assign {i}", data))

    return {
        "overview": overview_from_full(snapshot),
        "controls": controls,
        "activeAssigns": assigns,
    }


def decode_control_function(raw: int, is_num: bool = False) -> str:
    # Paraphrased from patch-controls.md
    if raw == 0: return "OFF"
    if is_num and raw == 1: return "MATCHING NUM"
    if raw == 1: return "BANK UP"
    if raw == 2: return "BANK DOWN"
    if raw == 3: return "PATCH +1"
    if raw == 4: return "PATCH -1"
    if raw == 9: return "BPM TAP"
    if raw == 15: return "TUNER"
    # ... more mappings from patch-controls.md can be added as needed
    names = {
        16: "AMP CTL1", 17: "AMP CTL2", 18: "COMPRESSOR", 19: "DISTORTION 1",
        20: "DISTORTION 1 SOLO", 21: "DISTORTION 2", 22: "DISTORTION 2 SOLO",
        23: "PREAMP 1", 24: "PREAMP 1 SOLO", 25: "PREAMP 2", 26: "PREAMP 2 SOLO",
        27: "NOISE SUPPRESSOR 1", 28: "NOISE SUPPRESSOR 2", 29: "EQUALIZER 1",
        30: "EQUALIZER 2", 31: "EQUALIZER 3", 32: "EQUALIZER 4",
        33: "DELAY 1", 34: "DELAY 2", 35: "DELAY 3", 36: "DELAY 4",
        37: "MASTER DELAY", 38: "CHORUS", 39: "FX 1", 40: "FX 2",
        41: "FX 3", 42: "FX 1 TRIGGER", 43: "FX 2 TRIGGER", 44: "FX 3 TRIGGER",
        45: "REVERB", 46: "PEDAL FX", 47: "DIVIDER 1",
        48: "DIVIDER 2", 49: "DIVIDER 3", 50: "SEND/RETURN 1",
        51: "SEND/RETURN 2", 52: "LOOPER", 53: "LOOPER STOP", 54: "LOOPER CLEAR",
        55: "METRONOME", 56: "MIDI START", 57: "MMC PLAY", 58: "MASTER DELAY TRIGGER",
    }
    return names.get(raw, f"FUNC {raw}")


def decode_exp_function(raw: int) -> str:
    names = {0: "OFF", 1: "FOOT VOLUME", 2: "PEDAL FX", 3: "FV + PEDAL FX"}
    return names.get(raw, f"FUNC {raw}")


def decode_assign_target(raw: int) -> str:
    # Common targets from assigns.md
    names = {
        932: "DIVIDER 1 CHANNEL SELECT",
        933: "DIVIDER 2 CHANNEL SELECT",
        934: "DIVIDER 3 CHANNEL SELECT",
        987: "TUNER ON/OFF",
        991: "TUNER ON/OFF (PDF alternate)",
    }
    return names.get(raw, f"TARGET {raw}")


def decode_assign_source(raw: int) -> str:
    if 0 <= raw <= 4:
        return f"NUM {raw + 1}"
    names = {
        5: "CURRENT NUMBER", 6: "BANK DOWN", 7: "BANK UP",
        15: "EXP 1 SW", 16: "EXP 1 PEDAL", 17: "EXP 2 PEDAL", 18: "EXP 3 PEDAL",
        19: "INTERNAL PEDAL", 20: "WAVE PEDAL", 21: "INPUT LEVEL",
    }
    if 8 <= raw <= 14:
        return f"CTL {raw - 7}"
    if 22 <= raw <= 52:
        return f"MIDI CC {raw - 21}"
    if 53 <= raw <= 84:
        return f"MIDI CC {raw + 11}"
    if raw in names:
        return names[raw]
    return f"SOURCE {hex(raw)}"


def assign_from_data(assign_id: str, data: bytes) -> dict[str, Any]:
    target = live.integer_from_nibbles(list(data[1:5]))
    source = data[13]
    return {
        "id": assign_id,
        "enabled": data[0] == 1,
        "target": target,
        "targetName": decode_assign_target(target),
        "targetMin": decoded_assign_value(data[5:9]),
        "targetMax": decoded_assign_value(data[9:13]),
        "source": source,
        "sourceName": decode_assign_source(source),
        "mode": "MOMENT" if data[14] == 1 else "TOGGLE",
        "waveRate": data[15],
        "waveform": data[16],
        "internalPedalTrigger": data[17],
        "internalPedalTime": data[18],
        "internalPedalCurve": data[19],
        "activeRangeLow": live.integer_from_nibbles(list(data[20:24])),
        "activeRangeHigh": live.integer_from_nibbles(list(data[24:28])),
        "midi": {
            "channel": "SYSTEM" if data[28] == 0 else data[28],
            "ccNumber": data[29],
            "ccValueMin": live.integer_from_nibbles(list(data[30:34])),
            "ccValueMax": live.integer_from_nibbles(list(data[34:38])),
            "pcNumber": data[39] if len(data) > 39 else None,
            "bankMsb": live.integer_from_nibbles(list(data[40:42])) if len(data) > 41 else None,
            "bankLsb": live.integer_from_nibbles(list(data[42:44])) if len(data) > 43 else None,
        },
    }


def decoded_assign_value(values: bytes) -> dict[str, int | None]:
    encoded = live.integer_from_nibbles(list(values))
    logical = encoded - 32768 if encoded is not None and encoded >= 32768 else encoded
    return {"encoded": encoded, "logical": logical}


def decode_system_midi(data: list[int]) -> dict[str, Any]:
    return {
        "rxChannelRaw": data[0] if len(data) > 0 else None,
        "txChannelRaw": data[1] if len(data) > 1 else None,
        "note": "Raw values are exposed because the complete System MIDI enum table is not yet decoded.",
    }


def decode_system_inout(data: list[int]) -> dict[str, Any]:
    return {
        "inputLevelRaw": data[0] if len(data) > 0 else None,
        "mainOutSelectRaw": data[1] if len(data) > 1 else None,
        "subOutSelectRaw": data[2] if len(data) > 2 else None,
        "note": "Raw values are exposed for IN/OUT settings until the full enum table is validated.",
    }


def decode_system_controls(data: list[int]) -> dict[str, Any]:
    preferences = [
        "NUM 1", "NUM 2", "NUM 3", "NUM 4", "NUM 5", "BANK DOWN", "BANK UP",
        "CTL 1", "CTL 2", "CTL 3", "CTL 4", "CTL 5", "CTL 6", "CTL 7",
        "CURRENT NUMBER", "EXP 1 SW", "EXP 1", "EXP 2", "EXP 3",
    ]
    return {
        "preferences": {
            name: ("SYSTEM" if len(data) > 0x23 + index and data[0x23 + index] == 1 else "PATCH")
            for index, name in enumerate(preferences)
        },
        "note": "System control function bytes are decoded in patch controls when a control preference is SYSTEM.",
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
            "typeName": block.get("typeName") if block else None,
            "isEnabled": is_enabled,
            "hasControlAssignment": has_control_assignment,
            "includeInDescription": description_candidate,
            "isReserved": element.get("isReserved", False),
            "isOutput": element.get("isOutput", False),
        }
        elements.append(chain_element)
        if description_candidate:
            description_elements.append(chain_element)

    def element_summary(el: dict[str, Any]) -> str:
        name = el["displayName"]
        type_name = el.get("typeName")
        if type_name:
            return f"{name} ({type_name})"
        return name

    return {
        "overview": overview_from_full(snapshot),
        "signalChainSummary": " -> ".join(
            element_summary(element) for element in elements if element.get("displayName")
        ),
        "descriptionSignalChainSummary": " -> ".join(
            element_summary(element) for element in description_elements if element.get("displayName")
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
