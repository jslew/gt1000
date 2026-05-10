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

    midi = subcommands.add_parser("midi", help="Send typed MIDI channel-voice messages.")
    midi_subcommands = midi.add_subparsers(dest="midi_command", required=True)
    cc = midi_subcommands.add_parser("cc", help="Send a typed MIDI Control Change message.")
    cc.add_argument("controller", type=int, help="MIDI CC controller number 0...127.")
    cc.add_argument("value", type=int, help="MIDI CC value 0...127.")
    cc.add_argument("--channel", type=int, default=1, help="1-based MIDI channel, default 1.")
    cc.add_argument("--live", action="store_true", help="Required because this sends MIDI to the connected GT-1000.")
    cc.set_defaults(func=cmd_midi_cc)
    pc = midi_subcommands.add_parser("pc", help="Send a typed MIDI Program Change message.")
    pc.add_argument("program", type=int, help="MIDI Program Change number 1...128.")
    pc.add_argument("--channel", type=int, default=1, help="1-based MIDI channel, default 1.")
    pc.add_argument("--live", action="store_true", help="Required because this sends MIDI to the connected GT-1000.")
    pc.set_defaults(func=cmd_midi_pc)
    bank_select = midi_subcommands.add_parser("bank-select", help="Send typed MIDI Bank Select MSB/LSB messages.")
    bank_select.add_argument("msb", type=int, help="Bank Select MSB 0...127.")
    bank_select.add_argument("lsb", type=int, nargs="?", default=0, help="Bank Select LSB 0...127, default 0.")
    bank_select.add_argument("--channel", type=int, default=1, help="1-based MIDI channel, default 1.")
    bank_select.add_argument("--live", action="store_true", help="Required because this sends MIDI to the connected GT-1000.")
    bank_select.set_defaults(func=cmd_midi_bank_select)

    system = subcommands.add_parser("system", help="Inspect GT-1000 system/global MIDI sections.")
    system_subcommands = system.add_subparsers(dest="system_command", required=True)
    for name, help_text in [
        ("common", "Read common global settings."),
        ("midi", "Read global MIDI settings."),
        ("inout", "Read global input/output settings."),
        ("effects", "Read global effects settings."),
        ("pitch", "Read global pitch/tuner settings."),
        ("controls", "Read global control functions and preferences."),
        ("manual", "Read global manual-mode number switch settings."),
    ]:
        system_view = system_subcommands.add_parser(name, help=help_text)
        system_view.add_argument("--live", action="store_true", help="Required because system settings are live device state.")
        system_view.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
        system_view.set_defaults(func=cmd_system_view)
    pcmap = system_subcommands.add_parser("pcmap", help="Read MIDI Program Change map banks.")
    pcmap.add_argument("--live", action="store_true", help="Required because program maps are live device state.")
    pcmap.add_argument("--bank", type=int, choices=[1, 2, 3, 4], help="Read one PC map bank instead of all four.")
    pcmap.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds per bank.")
    pcmap.set_defaults(func=cmd_system_pcmap)
    inputs = system_subcommands.add_parser("inputs", help="Read named system input-level settings.")
    inputs.add_argument("--live", action="store_true", help="Required because input settings are live device state.")
    inputs.add_argument("--number", type=int, choices=range(1, 11), metavar="1-10", help="Read one input setting instead of all ten.")
    inputs.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds per setting.")
    inputs.set_defaults(func=cmd_system_inputs)

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

    stompbox = patch_subcommands.add_parser("stompbox", help="Read the raw PatchStompBox selection record.")
    stompbox.add_argument("--live", action="store_true", help="Required because this reads from the connected GT-1000.")
    stompbox.add_argument("--user-slot", help="Read the Stompbox record from a persistent user slot such as U01-1.")
    stompbox.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    stompbox.set_defaults(func=cmd_patch_stompbox)

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

    enable = patch_subcommands.add_parser("enable", help="Enable one validated switchable block.")
    enable.add_argument("block_id", help="Block id such as delay1 or dist1.")
    enable.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    enable.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    enable.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    enable.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    enable.set_defaults(func=cmd_patch_enable, enabled=True)

    disable = patch_subcommands.add_parser("disable", help="Disable one validated switchable block.")
    disable.add_argument("block_id", help="Block id such as delay1 or dist1.")
    disable.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    disable.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    disable.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    disable.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    disable.set_defaults(func=cmd_patch_enable, enabled=False)

    type_command = patch_subcommands.add_parser("type", help="Change one validated block effect type.")
    type_command.add_argument("block_id", help="Block id such as dist1, preamp1, chorus, or masterDelay.")
    type_command.add_argument("type_value", help="Exact type name such as T-SCREAM, or a raw type number.")
    type_command.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    type_command.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    type_command.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    type_command.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    type_command.set_defaults(func=cmd_patch_type)

    move = patch_subcommands.add_parser("move", help="Move one decoded block in the signal chain.")
    move.add_argument("block_id", help="Block id to move, such as delay1 or dist1.")
    relation = move.add_mutually_exclusive_group(required=True)
    relation.add_argument("--before", help="Move before this block id.")
    relation.add_argument("--after", help="Move after this block id.")
    move.add_argument("--live", action="store_true", help="Required because this reads and writes the connected GT-1000.")
    move.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Move within a U03 user patch slot instead of the temporary patch.")
    move.add_argument("--verify", action="store_true", help="Re-read the full chain and compare exact bytes.")
    move.add_argument("--timeout", type=float, default=12.0, help="Read/verification timeout in seconds.")
    move.set_defaults(func=cmd_patch_move)

    assign_cc = patch_subcommands.add_parser("assign-cc", help="Map one Assign to a decoded target from a MIDI CC source.")
    assign_cc.add_argument("number", type=int, help="Assign number 1...16.")
    assign_cc.add_argument("block_id", help="Decoded target block id, such as delay1.")
    assign_cc.add_argument("parameter_id", help="Decoded target parameter id, such as sw.")
    assign_cc.add_argument("--cc", type=int, required=True, help="MIDI CC source number. Supported: 1...31 and 64...95.")
    assign_cc.add_argument("--mode", choices=["toggle", "moment"], required=True, help="Assign source mode.")
    assign_cc.add_argument("--min", dest="target_min", type=int, help="Logical target minimum before the +32768 Assign offset.")
    assign_cc.add_argument("--max", dest="target_max", type=int, help="Logical target maximum before the +32768 Assign offset.")
    assign_cc.add_argument("--active-min", type=int, default=0, help="CC active range low, default 0.")
    assign_cc.add_argument("--active-max", type=int, default=127, help="CC active range high, default 127.")
    assign_cc.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    assign_cc.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    assign_cc.add_argument("--verify", action="store_true", help="Re-read the Assign block and compare exact bytes.")
    assign_cc.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    assign_cc.set_defaults(func=cmd_patch_assign_cc)

    set_bpm = patch_subcommands.add_parser("set-bpm", help="Set validated patch master BPM.")
    set_bpm.add_argument("bpm", help="Patch master BPM, 40.0...250.0 with at most one decimal place.")
    set_bpm.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    set_bpm.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    set_bpm.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    set_bpm.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    set_bpm.set_defaults(func=cmd_patch_set_bpm)

    tuner_assign = patch_subcommands.add_parser("tuner-assign", help="Install the tested Assign 16 tuner mapping.")
    tuner_assign.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    tuner_assign.add_argument("--user-slot", choices=["U03-1", "U03-2", "U03-3", "U03-4", "U03-5"], help="Persist to a U03 user patch slot instead of the temporary patch.")
    tuner_assign.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    tuner_assign.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    tuner_assign.set_defaults(func=cmd_patch_tuner_assign)

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


def cmd_midi_cc(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("midi cc requires --live because it sends MIDI to the connected GT-1000", 64)
    try:
        message = control_change_message(args.controller, args.value, args.channel)
        live.send_channel_voice(message)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    return {
        "type": "controlChange",
        "channel": args.channel,
        "controller": args.controller,
        "value": args.value,
        "messageHex": live.hex_string(message),
        "note": "Control Change messages are gated by the GT-1000 MIDI RX channel and only affect mapped Assign/control sources.",
    }


def cmd_midi_pc(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("midi pc requires --live because it sends MIDI to the connected GT-1000", 64)
    try:
        message = program_change_message(args.program, args.channel)
        live.send_channel_voice(message)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    return {
        "type": "programChange",
        "channel": args.channel,
        "program": args.program,
        "programZeroBased": args.program - 1,
        "messageHex": live.hex_string(message),
        "note": "Program Change messages are gated by the GT-1000 MIDI RX channel and resolved through MENU:MIDI:PROGRAM MAP.",
    }


def cmd_midi_bank_select(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("midi bank-select requires --live because it sends MIDI to the connected GT-1000", 64)
    try:
        messages = bank_select_messages(args.msb, args.lsb, args.channel)
        for message in messages:
            live.send_channel_voice(message)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    return {
        "type": "bankSelect",
        "channel": args.channel,
        "msb": args.msb,
        "lsb": args.lsb,
        "messagesHex": [live.hex_string(message) for message in messages],
        "note": "Bank Select is normally followed by Program Change and is gated by the GT-1000 MIDI RX channel.",
    }


def cmd_system_view(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("system views require --live because system settings are live device state", 64)
    sections = {
        "common": ("systemCommon", "System Common", live.SYSTEM_COMMON, [0x00, 0x00, 0x00, 0x0D], decode_system_common),
        "midi": ("systemMidi", "System MIDI", live.SYSTEM_MIDI, [0x00, 0x00, 0x00, 0x1B], decode_system_midi),
        "inout": ("systemInOut", "System IN/OUT", live.SYSTEM_IN_OUT, [0x00, 0x00, 0x00, 0x60], decode_system_inout),
        "effects": ("systemEffects", "System Effects", live.SYSTEM_EFFECTS, [0x00, 0x00, 0x00, 0x07], decode_system_effects),
        "pitch": ("systemPitch", "System Pitch", live.SYSTEM_PITCH, [0x00, 0x00, 0x00, 0x07], decode_system_pitch),
        "controls": ("systemControl", "System Control", live.SYSTEM_CONTROL, [0x00, 0x00, 0x00, 0x36], decode_system_controls),
        "manual": ("systemManualControl", "System Manual Control", live.SYSTEM_CONTROL2, [0x00, 0x00, 0x00, 0x0F], decode_system_manual_controls),
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


def cmd_system_pcmap(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("system pcmap requires --live because program maps are live device state", 64)
    banks = [args.bank] if args.bank else [1, 2, 3, 4]
    decoded_banks = []
    for bank in banks:
        address = pcmap_bank_address(bank)
        size = [0x00, 0x00, 0x04, 0x00]
        try:
            raw = live.read_system_section(address, size, timeout=args.timeout)
        except live.LiveMIDIError as error:
            raise CLIError(str(error)) from error
        data = raw.get(live.address_key(address), [])
        decoded_banks.append({
            "bank": bank,
            "address": live.hex_bytes(address),
            "size": live.hex_bytes(size),
            "dataHex": live.hex_string(data),
            "entries": decode_pcmap_bank(data, bank=bank),
        })
    return {
        "id": "programChangeMap",
        "label": "Program Change Map",
        "banks": decoded_banks,
        "note": "Each entry maps a received MIDI Program Change number to a user or preset patch according to MENU:MIDI:PROGRAM MAP.",
    }


def cmd_system_inputs(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("system inputs requires --live because input settings are live device state", 64)
    numbers = [args.number] if args.number else list(range(1, 11))
    settings = []
    for number in numbers:
        address = system_input_setting_address(number)
        size = [0x00, 0x00, 0x00, 0x11]
        try:
            raw = live.read_system_section(address, size, timeout=args.timeout)
        except live.LiveMIDIError as error:
            raise CLIError(str(error)) from error
        data = raw.get(live.address_key(address), [])
        settings.append(decode_system_input_setting(data, number=number, address=address, size=size))
    return {
        "id": "systemInputSettings",
        "label": "System Input Settings",
        "settings": settings,
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


def chain_value_for_block_id(block_id: str) -> int:
    resolved = resolve_block_id(block_id)
    all_definitions = list(live.SUMMARY_BLOCKS) + list(live.RESIDENT_BLOCKS)
    block = next((definition for definition in all_definitions if definition.id == resolved), None)
    if block is None:
        raise ValueError(f"unknown chain block {block_id}")
    return block.chain_element_value


def assign_target_for_block_parameter(block_id: str, parameter_id: str) -> dict[str, Any]:
    resolved = resolve_block_id(block_id)
    for target_range in ASSIGN_TARGET_RANGES:
        if target_range["blockId"] != resolved:
            continue
        for index, (candidate_id, _candidate_name) in enumerate(target_range["parameters"]):
            if candidate_id == parameter_id:
                return decode_assign_target_detail(target_range["start"] + index)
    raise ValueError(f"unknown Assign target for {block_id}.{parameter_id}")


def decode_patch_stompbox(data: list[int]) -> dict[str, Any]:
    selections = []
    for index, definition in enumerate(STOMPBOX_SELECTIONS):
        raw = data[index] if len(data) > index else None
        selections.append({
            "offset": index,
            "address": f"00 {index:02X}",
            "id": definition["id"],
            "displayName": definition["displayName"],
            "rawValue": raw,
            "selection": stompbox_selection_name(raw, definition["prefix"]) if raw is not None else None,
        })
    return {
        "supported": True,
        "totalSize": ["00", "00", "00", "68"],
        "selections": selections,
    }


def stompbox_selection_name(raw: int, prefix: str) -> str | None:
    if raw == 0:
        return "---"
    if 1 <= raw <= 10:
        return f"{prefix}-{raw}"
    return None


def stompbox_definition(id_: str, display_name: str, prefix: str) -> dict[str, str]:
    return {"id": id_, "displayName": display_name, "prefix": prefix}


def stompbox_fx_definitions(fx_number: int, start_prefix: str = "fx") -> list[dict[str, str]]:
    base = f"{start_prefix}{fx_number}"
    display_base = f"FX {fx_number}"
    return [
        stompbox_definition(f"{base}AGSim", f"{display_base} Acoustic Guitar Simulator", "ACO"),
        stompbox_definition(f"{base}AcReso", f"{display_base} Acoustic Resonance", "ACR"),
        stompbox_definition(f"{base}AWah", f"{display_base} Auto Wah", "AW"),
        stompbox_definition(f"{base}Chorus", f"{display_base} Chorus", "CHO"),
        stompbox_definition(f"{base}CVibe", f"{display_base} Classic Vibe", "CV"),
        stompbox_definition(f"{base}Comp", f"{display_base} Compressor", "CMP"),
        stompbox_definition(f"{base}Defretter", f"{display_base} Defretter", "DEF"),
        stompbox_definition(f"{base}Feedbacker", f"{display_base} Feedbacker", "FB"),
        stompbox_definition(f"{base}Flanger", f"{display_base} Flanger", "FL"),
        stompbox_definition(f"{base}Harmonist", f"{display_base} Harmonist", "HRM"),
        stompbox_definition(f"{base}Humanizer", f"{display_base} Humanizer", "HMN"),
        stompbox_definition(f"{base}Octave", f"{display_base} Octave", "OC"),
        stompbox_definition(f"{base}Overtone", f"{display_base} Overtone", "OT"),
        stompbox_definition(f"{base}Pan", f"{display_base} Pan", "PAN"),
        stompbox_definition(f"{base}Phaser", f"{display_base} Phaser", "PH"),
        stompbox_definition(f"{base}PitchShift", f"{display_base} Pitch Shift", "PS"),
        stompbox_definition(f"{base}RingMod", f"{display_base} Ring Modulator", "RM"),
        stompbox_definition(f"{base}Rotary", f"{display_base} Rotary", "RT"),
        stompbox_definition(f"{base}SitarSim", f"{display_base} Sitar Simulator", "STR"),
        stompbox_definition(f"{base}Slicer", f"{display_base} Slicer", "SL"),
        stompbox_definition(f"{base}SlowGear", f"{display_base} Slow Gear", "SG"),
        stompbox_definition(f"{base}SoundHold", f"{display_base} Sound Hold", "SH"),
        stompbox_definition(f"{base}SBend", f"{display_base} S-Bend", "SB"),
        stompbox_definition(f"{base}TWah", f"{display_base} Touch Wah", "TW"),
        stompbox_definition(f"{base}Tremolo", f"{display_base} Tremolo", "TR"),
        stompbox_definition(f"{base}Vibrato", f"{display_base} Vibrato", "VIB"),
    ]


STOMPBOX_SELECTIONS = [
    stompbox_definition("comp", "Compressor", "CMP"),
    stompbox_definition("dist1", "Distortion 1", "DS"),
    stompbox_definition("dist2", "Distortion 2", "DS"),
    stompbox_definition("preamp1", "Preamp 1", "AMP"),
    stompbox_definition("preamp2", "Preamp 2", "AMP"),
    stompbox_definition("ns1", "Noise Suppressor 1", "NS"),
    stompbox_definition("ns2", "Noise Suppressor 2", "NS"),
    stompbox_definition("eq1", "Equalizer 1", "EQ"),
    stompbox_definition("eq2", "Equalizer 2", "EQ"),
    stompbox_definition("eq3", "Equalizer 3", "EQ"),
    stompbox_definition("eq4", "Equalizer 4", "EQ"),
    stompbox_definition("delay1", "Delay 1", "DLY"),
    stompbox_definition("delay2", "Delay 2", "DLY"),
    stompbox_definition("delay3", "Delay 3", "DLY"),
    stompbox_definition("delay4", "Delay 4", "DLY"),
    stompbox_definition("masterDelay", "Master Delay", "MDL"),
    stompbox_definition("chorus", "Chorus", "CHO"),
    *stompbox_fx_definitions(1),
    *stompbox_fx_definitions(2),
    *stompbox_fx_definitions(3),
    stompbox_definition("reverb", "Reverb", "REV"),
    stompbox_definition("pedalFx", "Pedal FX", "PFX"),
    stompbox_definition("divider1", "Divider 1", "DIV"),
    stompbox_definition("divider2", "Divider 2", "DIV"),
    stompbox_definition("divider3", "Divider 3", "DIV"),
    stompbox_definition("fx1ChorusBass", "FX 1 Bass Chorus", "CHB"),
    stompbox_definition("fx1DefretterBass", "FX 1 Bass Defretter", "DFB"),
    stompbox_definition("fx1FlangerBass", "FX 1 Bass Flanger", "FLB"),
    stompbox_definition("fx1OctaveBass", "FX 1 Bass Octave", "OCB"),
]


def patch_view(args: argparse.Namespace, view: str) -> Any:
    if args.live or args.file is None:
        assign_requests = [
            live.PatchReadRequest(f"Assign {i}", live.address_adding(live.ASSIGN_BASE, (i-1)*live.ASSIGN_STRIDE), [0x00, 0x00, 0x00, 0x2C])
            for i in range(1, 17)
        ] if view in {"chain", "controls", "summary"} else []
        
        snapshot = read_live_snapshot(args.timeout, requests=live.READ_PLAN + assign_requests if view in {"chain", "controls", "summary"} else live.INITIAL_READS)
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
        messages = program_change_messages_for_slot(slot, args.channel)
        for message in messages:
            live.send_channel_voice(message)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    return {
        "selectedSlot": slot,
        "channel": args.channel,
        "messagesHex": [live.hex_string(message) for message in messages],
        "note": "Selection uses MIDI Bank Select plus Program Change and is subject to the GT-1000 RX channel and program-map settings.",
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


def cmd_patch_stompbox(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch stompbox requires --live because it reads from the connected GT-1000", 64)
    size = [0x00, 0x00, 0x00, 0x68]
    address = live.TEMPORARY_PATCH_STOMPBOX
    source_slot = None
    if args.user_slot:
        source_slot = live.normalize_user_slot(args.user_slot)
        address = live.remap_temporary_patch_address(address, live.user_patch_base(source_slot))
    request = live.PatchReadRequest("Patch Stompbox", address, size)
    try:
        raw = live.read_data_sets(timeout=args.timeout, requests=[request])
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    data = raw.get(live.address_key(address), [])
    return {
        "id": "patchStompBox",
        "label": "Patch Stompbox",
        "sourceSlot": source_slot,
        "address": live.hex_bytes(address),
        "size": live.hex_bytes(size),
        "rawDataHex": live.hex_string(data),
        "decoded": decode_patch_stompbox(data),
    }


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


def cmd_patch_enable(args: argparse.Namespace) -> Any:
    command = "enable" if args.enabled else "disable"
    if not args.live:
        raise CLIError(f"patch {command} requires --live because it writes to the connected GT-1000", 64)
    try:
        block_id = resolve_block_id(args.block_id)
        value = "on" if args.enabled else "off"
        plan = patch_edit.build_parameter_set_plan(block_id, "sw", value, slot=args.user_slot)
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_type(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch type requires --live because it writes to the connected GT-1000", 64)
    try:
        block_id = resolve_block_id(args.block_id)
        plan = patch_edit.build_parameter_set_plan(block_id, "type", args.type_value, slot=args.user_slot)
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_move(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch move requires --live because it reads and writes the connected GT-1000", 64)
    try:
        element = chain_value_for_block_id(args.block_id)
        before = chain_value_for_block_id(args.before) if args.before else None
        after = chain_value_for_block_id(args.after) if args.after else None
        if args.user_slot:
            snapshot = read_user_slot_snapshot(args.user_slot, args.timeout, view="chain")
        else:
            snapshot = read_live_snapshot(args.timeout, requests=requests_for_view("chain"))
        chain_values = [item["rawValue"] for item in snapshot.get("signalChainElements", [])]
        plan = patch_edit.build_chain_move_plan(chain_values, element, before=before, after=after, slot=args.user_slot)
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_assign_cc(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch assign-cc requires --live because it writes to the connected GT-1000", 64)
    try:
        target = assign_target_for_block_parameter(args.block_id, args.parameter_id)
        if target["isOnOff"]:
            target_min = 0 if args.target_min is None else args.target_min
            target_max = 1 if args.target_max is None else args.target_max
        elif args.target_min is None or args.target_max is None:
            raise ValueError("non-on/off Assign targets require --min and --max")
        else:
            target_min = args.target_min
            target_max = args.target_max
        plan = patch_edit.build_assign_cc_plan(
            args.number,
            target=target["raw"],
            target_min=target_min,
            target_max=target_max,
            source_cc=args.cc,
            mode=args.mode,
            active_min=args.active_min,
            active_max=args.active_max,
            slot=args.user_slot,
        )
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_set_bpm(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch set-bpm requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_bpm_set_plan(args.bpm, slot=args.user_slot)
        return patch_edit.apply_plan(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_tuner_assign(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch tuner-assign requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_tuner_assign_plan(slot=args.user_slot)
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
        return live.READ_PLAN + assign_requests
    if view == "overview":
        return live.INITIAL_READS
    return live.READ_PLAN + assign_requests


def program_change_for_slot(slot: str, channel: int) -> list[int]:
    return program_change_messages_for_slot(slot, channel)[-1]


def program_change_messages_for_slot(slot: str, channel: int) -> list[list[int]]:
    normalized = live.normalize_user_slot(slot)
    if not 1 <= channel <= 16:
        raise ValueError("MIDI channel must be 1...16")
    bank = int(normalized[1:3])
    number = int(normalized.split("-", 1)[1])
    patch_index = (bank - 1) * live.USER_PATCHES_PER_BANK + number
    program = patch_index - 1
    bank_select_msb = program // 128
    if bank_select_msb > 2:
        raise ValueError("patch select supports only GT-1000 documented Bank Select MSB 0...2")
    messages = bank_select_messages(bank_select_msb, 0, channel)
    messages.append(program_change_message((program % 128) + 1, channel))
    return messages


def program_change_message(program: int, channel: int) -> list[int]:
    if not 1 <= channel <= 16:
        raise ValueError("MIDI channel must be 1...16")
    if not 1 <= program <= 128:
        raise ValueError("MIDI Program Change number must be 1...128")
    return [0xC0 + (channel - 1), program - 1]


def control_change_message(controller: int, value: int, channel: int) -> list[int]:
    if not 1 <= channel <= 16:
        raise ValueError("MIDI channel must be 1...16")
    if not 0 <= controller <= 127:
        raise ValueError("MIDI CC controller must be 0...127")
    if not 0 <= value <= 127:
        raise ValueError("MIDI CC value must be 0...127")
    return [0xB0 + (channel - 1), controller, value]


def bank_select_messages(msb: int, lsb: int, channel: int) -> list[list[int]]:
    if not 0 <= msb <= 127:
        raise ValueError("MIDI Bank Select MSB must be 0...127")
    if not 0 <= lsb <= 127:
        raise ValueError("MIDI Bank Select LSB must be 0...127")
    return [
        control_change_message(0, msb, channel),
        control_change_message(32, lsb, channel),
    ]


def pcmap_bank_address(bank: int) -> list[int]:
    if bank not in {1, 2, 3, 4}:
        raise ValueError("PC map bank must be 1...4")
    return live.address_adding(live.PC_MAP_BASE, (bank - 1) * live.PC_MAP_BANK_STRIDE)


def decode_pcmap_bank(data: list[int], *, bank: int) -> list[dict[str, Any]]:
    entries = []
    for index in range(128):
        offset = index * 4
        if len(data) < offset + 4:
            break
        patch_value = live.integer_from_nibbles(data[offset:offset + 4])
        entries.append({
            "bank": bank,
            "programChange": (bank - 1) * 128 + index + 1,
            "programChangeInBank": index + 1,
            "raw": data[offset:offset + 4],
            "patchValue": patch_value,
            "patch": decode_pcmap_patch_value(patch_value),
        })
    return entries


def decode_pcmap_patch_value(value: int | None) -> str | None:
    if value is None:
        return None
    if 0 <= value < live.USER_BANK_COUNT * live.USER_PATCHES_PER_BANK:
        return slot_from_patch_index("U", value)
    preset_value = value - (live.USER_BANK_COUNT * live.USER_PATCHES_PER_BANK)
    if 0 <= preset_value < live.USER_BANK_COUNT * live.USER_PATCHES_PER_BANK:
        return slot_from_patch_index("P", preset_value)
    return None


def slot_from_patch_index(prefix: str, zero_based_index: int) -> str:
    bank = zero_based_index // live.USER_PATCHES_PER_BANK + 1
    number = zero_based_index % live.USER_PATCHES_PER_BANK + 1
    return f"{prefix}{bank:02d}-{number}"


def decode_system_common(data: list[int]) -> dict[str, Any]:
    metronome_bpm = live.bpm_from_data(data[0x09:0x0D]) if len(data) >= 0x0D else None
    return {
        "metronomeBpmRaw": data[0x09:0x0D] if len(data) >= 0x0D else [],
        "metronomeBpm": metronome_bpm,
        "note": "Only the documented system metronome BPM field is decoded here; other System Common bytes stay raw.",
    }


def system_input_setting_address(number: int) -> list[int]:
    if not 1 <= number <= 10:
        raise ValueError("system input setting number must be 1...10")
    return live.address_adding(live.SYSTEM_INPUT_SETTING_BASE, (number - 1) * live.SYSTEM_INPUT_SETTING_STRIDE)


def decode_system_input_setting(
    data: list[int],
    *,
    number: int,
    address: list[int] | None = None,
    size: list[int] | None = None,
) -> dict[str, Any]:
    name = live.decode_patch_name(data[:16]) if len(data) >= 16 else ""
    return {
        "number": number,
        "address": live.hex_bytes(address) if address else None,
        "size": live.hex_bytes(size) if size else None,
        "name": name,
        "inputLevelRaw": data[0x10] if len(data) > 0x10 else None,
        "inputLevelDb": decode_offset_db(data[0x10]) if len(data) > 0x10 else None,
        "dataHex": live.hex_string(data),
    }


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
    raw_sections = normalized_raw_sections(snapshot)
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
        function_detail = decode_control_function_detail(func_byte, is_num="NUM" in name)
        
        controls[name] = {
            "preference": preference,
            "functionRaw": func_byte,
            "function": function_detail["name"],
            "functionTargetBlockId": function_detail["blockId"],
            "functionTargetParameterId": function_detail["parameterId"],
            "functionCanEnableBlock": function_detail["canEnableBlock"],
            "mode": "MOMENT" if mode_byte == 1 else "TOGGLE",
        }

    # EXP Pedals
    exp_pedals = [("EXP 1", 0x43, 0x33), ("EXP 2", 0x44, 0x34), ("EXP 3", 0x45, 0x35)]
    for name, patch_offset, system_pref_offset in exp_pedals:
        preference = "SYSTEM" if system_control[system_pref_offset] == 1 else "PATCH"
        func_byte = system_control[patch_offset - 0x23] if preference == "SYSTEM" else patch_common[patch_offset]
        function_detail = decode_exp_function_detail(func_byte)
        controls[name] = {
            "preference": preference,
            "functionRaw": func_byte,
            "function": function_detail["name"],
            "functionTargetBlockId": function_detail["blockId"],
            "functionTargetParameterId": function_detail["parameterId"],
            "functionCanEnableBlock": function_detail["canEnableBlock"],
        }

    return {
        "overview": overview_from_full(snapshot),
        "controls": controls,
        "activeAssigns": active_assigns_from_snapshot(snapshot),
    }


def decode_control_function(raw: int, is_num: bool = False) -> str:
    return decode_control_function_detail(raw, is_num=is_num)["name"]


def decode_control_function_detail(raw: int, is_num: bool = False) -> dict[str, Any]:
    if is_num and raw == 1:
        return control_function_detail(raw, "MATCHING NUM")

    detail = CONTROL_FUNCTIONS.get(raw)
    if detail:
        return control_function_detail(raw, **detail)
    return control_function_detail(raw, f"FUNC {raw}")


def control_function_detail(
    raw: int,
    name: str,
    blockId: str | None = None,
    parameterId: str | None = None,
    canEnableBlock: bool = False,
) -> dict[str, Any]:
    return {
        "raw": raw,
        "name": name,
        "blockId": blockId,
        "parameterId": parameterId,
        "canEnableBlock": canEnableBlock,
    }


CONTROL_FUNCTIONS: dict[int, dict[str, Any]] = {
    0: {"name": "OFF"},
    1: {"name": "BANK UP"},
    2: {"name": "BANK DOWN"},
    3: {"name": "PATCH +1"},
    4: {"name": "PATCH -1"},
    5: {"name": "LEVEL +10"},
    6: {"name": "LEVEL +20"},
    7: {"name": "LEVEL -10"},
    8: {"name": "LEVEL -20"},
    9: {"name": "BPM TAP"},
    10: {"name": "DELAY 1 TAP", "blockId": "delay1", "parameterId": "time"},
    11: {"name": "DELAY 2 TAP", "blockId": "delay2", "parameterId": "time"},
    12: {"name": "DELAY 3 TAP", "blockId": "delay3", "parameterId": "time"},
    13: {"name": "DELAY 4 TAP", "blockId": "delay4", "parameterId": "time"},
    14: {"name": "MASTER DELAY TAP", "blockId": "masterDelay", "parameterId": "time"},
    15: {"name": "TUNER"},
    16: {"name": "AMP CTL1"},
    17: {"name": "AMP CTL2"},
    18: {"name": "COMPRESSOR", "blockId": "comp", "parameterId": "sw", "canEnableBlock": True},
    19: {"name": "DISTORTION 1", "blockId": "dist1", "parameterId": "sw", "canEnableBlock": True},
    20: {"name": "DISTORTION 1 SOLO", "blockId": "dist1", "parameterId": "soloSw"},
    21: {"name": "DISTORTION 2", "blockId": "dist2", "parameterId": "sw", "canEnableBlock": True},
    22: {"name": "DISTORTION 2 SOLO", "blockId": "dist2", "parameterId": "soloSw"},
    23: {"name": "PREAMP 1", "blockId": "preamp1", "parameterId": "sw", "canEnableBlock": True},
    24: {"name": "PREAMP 1 SOLO", "blockId": "preamp1", "parameterId": "soloSw"},
    25: {"name": "PREAMP 2", "blockId": "preamp2", "parameterId": "sw", "canEnableBlock": True},
    26: {"name": "PREAMP 2 SOLO", "blockId": "preamp2", "parameterId": "soloSw"},
    27: {"name": "NOISE SUPPRESSOR 1", "blockId": "ns1", "parameterId": "sw", "canEnableBlock": True},
    28: {"name": "NOISE SUPPRESSOR 2", "blockId": "ns2", "parameterId": "sw", "canEnableBlock": True},
    29: {"name": "EQUALIZER 1", "blockId": "eq1", "parameterId": "sw", "canEnableBlock": True},
    30: {"name": "EQUALIZER 2", "blockId": "eq2", "parameterId": "sw", "canEnableBlock": True},
    31: {"name": "EQUALIZER 3", "blockId": "eq3", "parameterId": "sw", "canEnableBlock": True},
    32: {"name": "EQUALIZER 4", "blockId": "eq4", "parameterId": "sw", "canEnableBlock": True},
    33: {"name": "DELAY 1", "blockId": "delay1", "parameterId": "sw", "canEnableBlock": True},
    34: {"name": "DELAY 2", "blockId": "delay2", "parameterId": "sw", "canEnableBlock": True},
    35: {"name": "DELAY 3", "blockId": "delay3", "parameterId": "sw", "canEnableBlock": True},
    36: {"name": "DELAY 4", "blockId": "delay4", "parameterId": "sw", "canEnableBlock": True},
    37: {"name": "MASTER DELAY", "blockId": "masterDelay", "parameterId": "sw", "canEnableBlock": True},
    38: {"name": "CHORUS", "blockId": "chorus", "parameterId": "sw", "canEnableBlock": True},
    39: {"name": "FX 1", "blockId": "fx1", "parameterId": "sw", "canEnableBlock": True},
    40: {"name": "FX 2", "blockId": "fx2", "parameterId": "sw", "canEnableBlock": True},
    41: {"name": "FX 3", "blockId": "fx3", "parameterId": "sw", "canEnableBlock": True},
    42: {"name": "FX 1 TRIGGER", "blockId": "fx1"},
    43: {"name": "FX 2 TRIGGER", "blockId": "fx2"},
    44: {"name": "FX 3 TRIGGER", "blockId": "fx3"},
    45: {"name": "REVERB", "blockId": "reverb", "parameterId": "sw", "canEnableBlock": True},
    46: {"name": "PEDAL FX", "blockId": "pedalFx", "parameterId": "sw", "canEnableBlock": True},
    47: {"name": "DIVIDER 1 CHANNEL SELECT", "blockId": "divider1", "parameterId": "channelSelect"},
    48: {"name": "DIVIDER 2 CHANNEL SELECT", "blockId": "divider2", "parameterId": "channelSelect"},
    49: {"name": "DIVIDER 3 CHANNEL SELECT", "blockId": "divider3", "parameterId": "channelSelect"},
    50: {"name": "SEND/RETURN 1", "blockId": "sendReturn1", "parameterId": "sw", "canEnableBlock": True},
    51: {"name": "SEND/RETURN 2", "blockId": "sendReturn2", "parameterId": "sw", "canEnableBlock": True},
    52: {"name": "LOOPER"},
    53: {"name": "LOOPER STOP"},
    54: {"name": "LOOPER CLEAR"},
    55: {"name": "METRONOME"},
    56: {"name": "MIDI START"},
    57: {"name": "MMC PLAY"},
    58: {"name": "MASTER DELAY TRIGGER", "blockId": "masterDelay"},
}


def decode_exp_function(raw: int) -> str:
    return decode_exp_function_detail(raw)["name"]


def decode_exp_function_detail(raw: int) -> dict[str, Any]:
    names = {
        0: {"name": "OFF"},
        1: {"name": "FOOT VOLUME", "blockId": "footVolume"},
        2: {"name": "PEDAL FX", "blockId": "pedalFx", "parameterId": "sw", "canEnableBlock": True},
        3: {"name": "FV + PEDAL FX", "blockId": "pedalFx", "parameterId": "sw", "canEnableBlock": True},
    }
    detail = names.get(raw)
    if detail:
        return control_function_detail(raw, **detail)
    return control_function_detail(raw, f"FUNC {raw}")


def decode_assign_target(raw: int) -> str:
    return decode_assign_target_detail(raw)["name"]


def decode_assign_target_detail(raw: int | None) -> dict[str, Any]:
    if raw is None:
        return {"name": "TARGET UNKNOWN", "category": None, "blockId": None, "parameterId": None, "isOnOff": False}

    exact_targets: dict[int, dict[str, Any]] = {
        932: {"name": "DIVIDER 1 CHANNEL SELECT", "category": "DIVIDER 1", "blockId": "divider1", "parameterId": "channelSelect"},
        933: {"name": "DIVIDER 2 CHANNEL SELECT", "category": "DIVIDER 2", "blockId": "divider2", "parameterId": "channelSelect"},
        934: {"name": "DIVIDER 3 CHANNEL SELECT", "category": "DIVIDER 3", "blockId": "divider3", "parameterId": "channelSelect"},
        987: {"name": "TUNER ON/OFF", "category": "TUNER", "blockId": None, "parameterId": "sw", "isOnOff": True},
        991: {"name": "TUNER ON/OFF (PDF alternate)", "category": "TUNER", "blockId": None, "parameterId": "sw", "isOnOff": True},
    }
    if raw in exact_targets:
        return assign_target_detail(raw, **exact_targets[raw])

    for target_range in ASSIGN_TARGET_RANGES:
        start = target_range["start"]
        parameter_names = target_range["parameters"]
        if start <= raw < start + len(parameter_names):
            index = raw - start
            parameter_id, parameter_name = parameter_names[index]
            return assign_target_detail(
                raw,
                name=f'{target_range["category"]} {parameter_name}',
                category=target_range["category"],
                blockId=target_range["blockId"],
                parameterId=parameter_id,
                isOnOff=parameter_id in {"sw", "soloSw", "bright"},
            )

    return assign_target_detail(raw, name=f"TARGET {raw}", category=None, blockId=None, parameterId=None)


def assign_target_detail(
    raw: int,
    *,
    name: str,
    category: str | None,
    blockId: str | None,
    parameterId: str | None,
    isOnOff: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "blockId": blockId,
        "parameterId": parameterId,
        "isOnOff": isOnOff,
        "raw": raw,
    }


def block_parameter_names(block_id: str) -> list[tuple[str, str]]:
    block = next((item for item in live.SUMMARY_BLOCKS if item.id == block_id), None)
    if block is None:
        return []
    by_offset = {parameter.offset: (parameter.id, parameter.display_name) for parameter in block.parameters}
    return [by_offset.get(offset, (f"param{offset}", f"PARAM {offset}")) for offset in range(block.size)]


ASSIGN_TARGET_RANGES = [
    {"start": 0, "category": "COMP", "blockId": "comp", "parameters": block_parameter_names("comp")},
    {"start": 8, "category": "OD/DS 1", "blockId": "dist1", "parameters": block_parameter_names("dist1")},
    {"start": 17, "category": "OD/DS 2", "blockId": "dist2", "parameters": block_parameter_names("dist2")},
    {"start": 26, "category": "PREAMP 1", "blockId": "preamp1", "parameters": block_parameter_names("preamp1")},
    {"start": 40, "category": "PREAMP 2", "blockId": "preamp2", "parameters": block_parameter_names("preamp2")},
    {"start": 54, "category": "NS 1", "blockId": "ns1", "parameters": block_parameter_names("ns1")},
    {"start": 58, "category": "NS 2", "blockId": "ns2", "parameters": block_parameter_names("ns2")},
    {"start": 62, "category": "EQ 1", "blockId": "eq1", "parameters": block_parameter_names("eq1")},
    {"start": 86, "category": "EQ 2", "blockId": "eq2", "parameters": block_parameter_names("eq2")},
    {"start": 110, "category": "EQ 3", "blockId": "eq3", "parameters": block_parameter_names("eq3")},
    {"start": 134, "category": "EQ 4", "blockId": "eq4", "parameters": block_parameter_names("eq4")},
    {"start": 158, "category": "DELAY 1", "blockId": "delay1", "parameters": block_parameter_names("delay1")[:6]},
    {"start": 164, "category": "DELAY 2", "blockId": "delay2", "parameters": block_parameter_names("delay2")[:6]},
    {"start": 170, "category": "DELAY 3", "blockId": "delay3", "parameters": block_parameter_names("delay3")[:6]},
    {"start": 176, "category": "DELAY 4", "blockId": "delay4", "parameters": block_parameter_names("delay4")[:6]},
    {"start": 182, "category": "MASTER DELAY", "blockId": "masterDelay", "parameters": block_parameter_names("masterDelay")},
    {"start": 213, "category": "CHORUS", "blockId": "chorus", "parameters": block_parameter_names("chorus")},
    {"start": 237, "category": "FX 1", "blockId": "fx1", "parameters": block_parameter_names("fx1")},
    {"start": 449, "category": "FX 2", "blockId": "fx2", "parameters": block_parameter_names("fx2")},
    {"start": 661, "category": "FX 3", "blockId": "fx3", "parameters": block_parameter_names("fx3")},
    {"start": 873, "category": "REVERB", "blockId": "reverb", "parameters": block_parameter_names("reverb")},
    {"start": 915, "category": "PEDAL FX", "blockId": "pedalFx", "parameters": block_parameter_names("pedalFx")},
]


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
    target_detail = decode_assign_target_detail(target)
    return {
        "id": assign_id,
        "enabled": data[0] == 1,
        "target": target,
        "targetName": target_detail["name"],
        "targetCategory": target_detail["category"],
        "targetBlockId": target_detail["blockId"],
        "targetParameterId": target_detail["parameterId"],
        "targetIsOnOff": target_detail["isOnOff"],
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


def active_assigns_from_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    assigns = []
    raw_sections = normalized_raw_sections(snapshot)
    for i in range(1, 17):
        data = raw_sections.get(f"Assign {i}")
        if data and data[0] == 1:
            assigns.append(assign_from_data(f"Assign {i}", bytes(data)))
    return assigns


def normalized_raw_sections(snapshot: dict[str, Any]) -> dict[str, bytes]:
    raw_sections = snapshot.get("rawSections", {})
    if isinstance(raw_sections, dict):
        return {
            key: bytes(value)
            for key, value in raw_sections.items()
            if isinstance(value, (bytes, bytearray, list, tuple))
        }
    if isinstance(raw_sections, list):
        normalized = {}
        for section in raw_sections:
            if not isinstance(section, dict) or "id" not in section:
                continue
            data_hex = section.get("dataHex")
            if isinstance(data_hex, str):
                normalized[section["id"]] = bytes.fromhex(data_hex.replace(" ", ""))
        return normalized
    return {}


def active_assigns_by_block(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_block: dict[str, list[dict[str, Any]]] = {}
    for assign in active_assigns_from_snapshot(snapshot):
        block_id = assign.get("targetBlockId")
        if block_id:
            by_block.setdefault(block_id, []).append(assign)
    return by_block


def direct_controls_by_block(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    try:
        controls = controls_from_full(snapshot)["controls"]
    except CLIError:
        return {}

    by_block: dict[str, list[dict[str, Any]]] = {}
    for control_name, control in controls.items():
        block_id = control.get("functionTargetBlockId")
        if not block_id or not control.get("functionCanEnableBlock"):
            continue
        by_block.setdefault(block_id, []).append({
            "control": control_name,
            "preference": control.get("preference"),
            "functionRaw": control.get("functionRaw"),
            "function": control.get("function"),
            "targetParameterId": control.get("functionTargetParameterId"),
            "mode": control.get("mode"),
        })
    return by_block


def decode_system_midi(data: list[int]) -> dict[str, Any]:
    return {
        "rxChannelRaw": data[0] if len(data) > 0 else None,
        "rxChannel": decode_one_based_channel(data[0]) if len(data) > 0 else None,
        "omniModeRaw": data[1] if len(data) > 1 else None,
        "omniMode": decode_on_off(data[1]) if len(data) > 1 else None,
        "txChannelRaw": data[2] if len(data) > 2 else None,
        "txChannel": decode_tx_channel(data[2]) if len(data) > 2 else None,
        "syncClockRaw": data[3] if len(data) > 3 else None,
        "syncClock": decode_enum(data[3], ["AUTO", "INTERNAL", "MIDI(AUTO)", "USB(AUTO)"]) if len(data) > 3 else None,
        "midiInThruRaw": data[4] if len(data) > 4 else None,
        "midiInThru": decode_enum(data[4], ["OFF", "MIDI OUT", "USB OUT", "USB/MIDI"]) if len(data) > 4 else None,
        "usbInThruRaw": data[5] if len(data) > 5 else None,
        "usbInThru": decode_enum(data[5], ["OFF", "MIDI OUT", "USB OUT", "USB/MIDI"]) if len(data) > 5 else None,
        "clockOutRaw": data[6] if len(data) > 6 else None,
        "clockOut": decode_on_off(data[6]) if len(data) > 6 else None,
        "fixedRaw": data[7] if len(data) > 7 else None,
        "mapSelectRaw": data[8] if len(data) > 8 else None,
        "mapSelect": decode_enum(data[8], ["FIX", "PROG"]) if len(data) > 8 else None,
        "controlChangeNumbers": decode_system_midi_cc_assignments(data),
    }


def decode_one_based_channel(raw: int) -> str | None:
    if 0 <= raw <= 15:
        return f"Ch.{raw + 1}"
    return None


def decode_tx_channel(raw: int) -> str | None:
    if 0 <= raw <= 15:
        return f"Ch.{raw + 1}"
    if raw == 16:
        return "RX"
    return None


def decode_on_off(raw: int) -> str | None:
    return decode_enum(raw, ["OFF", "ON"])


def decode_enum(raw: int, values: list[str]) -> str | None:
    if 0 <= raw < len(values):
        return values[raw]
    return None


def decode_system_midi_cc_assignments(data: list[int]) -> dict[str, dict[str, int | str | None]]:
    controls = [
        "NUM 1", "NUM 2", "NUM 3", "NUM 4", "NUM 5",
        "BANK DOWN", "BANK UP",
        "CTL 1", "CTL 2", "CTL 3", "CTL 4", "CTL 5", "CTL 6", "CTL 7",
        "EXP 1 SW", "EXP 1", "EXP 2", "EXP 3",
    ]
    return {
        name: {
            "raw": data[0x09 + index] if len(data) > 0x09 + index else None,
            "cc": decode_system_midi_cc(data[0x09 + index]) if len(data) > 0x09 + index else None,
        }
        for index, name in enumerate(controls)
    }


def decode_system_midi_cc(raw: int) -> str | None:
    if raw == 0:
        return "OFF"
    if 1 <= raw <= 31:
        return f"CC#{raw}"
    if 32 <= raw <= 63:
        return f"CC#{raw + 32}"
    return None


def decode_system_inout(data: list[int]) -> dict[str, Any]:
    return {
        "inputLevelRaw": data[0] if len(data) > 0 else None,
        "inputLevelDb": decode_offset_db(data[0]) if len(data) > 0 else None,
        "mainLeft": decode_system_output_channel(data, 0x03, output_select_offset=0x01),
        "mainRight": decode_system_output_channel(data, 0x0A, output_select_offset=0x02),
        "subLeft": decode_system_output_channel(data, 0x13, output_select_offset=0x11),
        "subRight": decode_system_output_channel(data, 0x1A, output_select_offset=0x12),
        "mainOutSelectRaw": data[0x01] if len(data) > 0x01 else None,
        "mainOutSelect": decode_aird_output_select(data[0x01]) if len(data) > 0x01 else None,
        "mainROutSelectRaw": data[0x02] if len(data) > 0x02 else None,
        "mainROutSelect": decode_aird_output_select(data[0x02]) if len(data) > 0x02 else None,
        "subOutSelectRaw": data[0x11] if len(data) > 0x11 else None,
        "subOutSelect": decode_aird_output_select(data[0x11]) if len(data) > 0x11 else None,
        "subROutSelectRaw": data[0x12] if len(data) > 0x12 else None,
        "subROutSelect": decode_aird_output_select(data[0x12]) if len(data) > 0x12 else None,
        "phonesSettingRaw": data[0x21] if len(data) > 0x21 else None,
        "phonesSetting": decode_enum(data[0x21], ["MAIN OUT", "SUB OUT", "MAIN+SUB"]) if len(data) > 0x21 else None,
        "totalNsThresholdRaw": data[0x22] if len(data) > 0x22 else None,
        "totalNsThresholdDb": decode_offset_db(data[0x22]) if len(data) > 0x22 else None,
        "totalReverbLevelRaw": data[0x23:0x25] if len(data) > 0x24 else [],
        "totalReverbLevel": decode_two_nibble_value(data, 0x23, 200),
        "mainLevelSelectRaw": data[0x25] if len(data) > 0x25 else None,
        "mainLevelSelect": decode_enum(data[0x25], ["-10dBu", "+4dBu"]) if len(data) > 0x25 else None,
        "usbDryOutRaw": data[0x26:0x28] if len(data) > 0x27 else [],
        "usbDryOut": decode_two_nibble_value(data, 0x26, 200),
        "usbDryToEfxRaw": data[0x28:0x2A] if len(data) > 0x29 else [],
        "usbDryToEfx": decode_two_nibble_value(data, 0x28, 200),
        "usbMainEfxOutRaw": data[0x2B:0x2D] if len(data) > 0x2C else [],
        "usbMainEfxOut": decode_two_nibble_value(data, 0x2B, 200),
        "usbMainMixLevelRaw": data[0x2D:0x2F] if len(data) > 0x2E else [],
        "usbMainMixLevel": decode_two_nibble_value(data, 0x2D, 200),
        "usbSubEfxOutRaw": data[0x30:0x32] if len(data) > 0x31 else [],
        "usbSubEfxOut": decode_two_nibble_value(data, 0x30, 200),
        "usbSubMixLevelRaw": data[0x32:0x34] if len(data) > 0x33 else [],
        "usbSubMixLevel": decode_two_nibble_value(data, 0x32, 200),
        "subLevelSelectRaw": data[0x3A] if len(data) > 0x3A else None,
        "subLevelSelect": decode_enum(data[0x3A], ["-10dBu", "+4dBu"]) if len(data) > 0x3A else None,
        "subOutputLevelRaw": data[0x3B] if len(data) > 0x3B else None,
        "subOutputLevel": data[0x3B] if len(data) > 0x3B and 0 <= data[0x3B] <= 100 else None,
        "subGroundLiftRaw": data[0x3C] if len(data) > 0x3C else None,
        "subGroundLift": decode_on_off(data[0x3C]) if len(data) > 0x3C else None,
        "mainStereoLinkRaw": data[0x3D] if len(data) > 0x3D else None,
        "mainStereoLink": decode_on_off(data[0x3D]) if len(data) > 0x3D else None,
        "subStereoLinkRaw": data[0x3E] if len(data) > 0x3E else None,
        "subStereoLink": decode_on_off(data[0x3E]) if len(data) > 0x3E else None,
        "outputLevels": {
            "mainLeftDb": decode_offset_db(data[0x3F]) if len(data) > 0x3F else None,
            "mainRightDb": decode_offset_db(data[0x40]) if len(data) > 0x40 else None,
            "subLeftDb": decode_offset_db(data[0x41]) if len(data) > 0x41 else None,
            "subRightDb": decode_offset_db(data[0x42]) if len(data) > 0x42 else None,
        },
    }


def decode_system_output_channel(data: list[int], offset: int, *, output_select_offset: int | None = None) -> dict[str, Any]:
    eq_offset = offset
    return {
        "outputSelectRaw": data[output_select_offset] if output_select_offset is not None and len(data) > output_select_offset else None,
        "outputSelect": decode_aird_output_select(data[output_select_offset]) if output_select_offset is not None and len(data) > output_select_offset else None,
        "lowGainRaw": data[eq_offset] if len(data) > eq_offset else None,
        "lowGainDb": decode_offset_db(data[eq_offset]) if len(data) > eq_offset else None,
        "midGainRaw": data[eq_offset + 1] if len(data) > eq_offset + 1 else None,
        "midGainDb": decode_offset_db(data[eq_offset + 1]) if len(data) > eq_offset + 1 else None,
        "midFreqRaw": data[eq_offset + 2] if len(data) > eq_offset + 2 else None,
        "midFreq": decode_mid_frequency(data[eq_offset + 2]) if len(data) > eq_offset + 2 else None,
        "midQRaw": data[eq_offset + 3] if len(data) > eq_offset + 3 else None,
        "midQ": decode_enum(data[eq_offset + 3], ["0.5", "1", "2", "4", "8", "16"]) if len(data) > eq_offset + 3 else None,
        "highGainRaw": data[eq_offset + 4] if len(data) > eq_offset + 4 else None,
        "highGainDb": decode_offset_db(data[eq_offset + 4]) if len(data) > eq_offset + 4 else None,
        "lowCutRaw": data[eq_offset + 5] if len(data) > eq_offset + 5 else None,
        "lowCut": decode_low_cut(data[eq_offset + 5]) if len(data) > eq_offset + 5 else None,
        "highCutRaw": data[eq_offset + 6] if len(data) > eq_offset + 6 else None,
        "highCut": decode_high_cut(data[eq_offset + 6]) if len(data) > eq_offset + 6 else None,
    }


def decode_offset_db(raw: int) -> int | None:
    if 12 <= raw <= 52:
        return raw - 32
    return None


def decode_mid_frequency(raw: int) -> str | None:
    values = [
        "20.0Hz", "25.0Hz", "31.5Hz", "40.0Hz", "50.0Hz", "63.0Hz",
        "80.0Hz", "100Hz", "125Hz", "160Hz", "200Hz", "250Hz", "315Hz",
        "400Hz", "500Hz", "630Hz", "800Hz", "1.00kHz", "1.25kHz",
        "1.60kHz", "2.00kHz", "2.50kHz", "3.15kHz", "4.00kHz",
        "5.00kHz", "6.30kHz", "8.00kHz", "10.0kHz", "12.5kHz", "16.0kHz",
    ]
    return decode_enum(raw, values)


def decode_low_cut(raw: int) -> str | None:
    return decode_enum(raw, ["FLAT"] + CUTOFF_FREQUENCIES)


def decode_high_cut(raw: int) -> str | None:
    return decode_enum(raw, CUTOFF_FREQUENCIES + ["FLAT"])


CUTOFF_FREQUENCIES = [
    "20.0Hz", "25.0Hz", "31.5Hz", "40.0Hz", "50.0Hz", "63.0Hz",
    "80.0Hz", "100Hz", "125Hz", "160Hz", "200Hz", "250Hz", "315Hz",
    "400Hz", "500Hz", "630Hz", "800Hz", "1.00kHz", "1.25kHz",
    "1.60kHz", "2.00kHz", "2.50kHz", "3.15kHz", "4.00kHz",
    "5.00kHz", "6.30kHz", "8.00kHz", "10.0kHz", "12.5kHz", "16.0kHz",
    "20.0kHz",
]


def decode_two_nibble_value(data: list[int], offset: int, maximum: int) -> int | None:
    if len(data) <= offset + 1:
        return None
    value = live.integer_from_nibbles(data[offset:offset + 2])
    if value is not None and 0 <= value <= maximum:
        return value
    return None


def decode_aird_output_select(raw: int) -> str | None:
    values = [
        "LINE/PHONES", "RECORDING", "JC-120 RETURN", "JC-120 INPUT",
        "Blues Cube Tour410 RETURN", "Blues Cube Tour410 INPUT",
        "Blues Cube Artist212 RETURN", "Blues Cube Artist212 INPUT",
        "WAZA Amp 412 RETURN", "WAZA Amp 412 INPUT", "WAZA Amp 212 RETURN",
        "WAZA Amp 212 INPUT", "KATANA-100/212 RETURN", "KATANA-100/212 INPUT",
        "KATANA-100 RETURN", "KATANA-100 INPUT", "TUBE COMBO 212 RETURN",
        "TUBE COMBO 212 INPUT", "TUBE COMBO 112 RETURN", "TUBE COMBO 112 INPUT",
        "TUBE STACK 412 RETURN", "TUBE STACK 412 INPUT", "USER 1", "USER 2",
        "KATANA-50 INPUT", "NEXTONE-Artist RETURN", "NEXTONE-Stage RETURN",
        "MUSTANG 212 RETURN", "Hot Rod Deluxe RETURN", "Twin Reverb INPUT",
        "AC30 INPUT", "JCM2000 412 RETURN", "JVM410H 412 RETURN",
        "Rectifier 412 RETURN", "TriAmp 412 RETURN", "BASS AMP WITH TWEETER",
        "BASS AMP NO TWEETER", "KATANA-100/212 MkII POWER AMP IN",
        "KATANA-100 MkII POWER AMP IN", "KATANA-50 MkII POWER AMP IN",
    ]
    return decode_enum(raw, values)


def decode_system_effects(data: list[int]) -> dict[str, Any]:
    return {
        "phraseLoopModeRaw": data[0] if len(data) > 0 else None,
        "phraseLoopMode": decode_enum(data[0], ["MONO", "STEREO"]) if len(data) > 0 else None,
        "phraseLoopRecActionRaw": data[1] if len(data) > 1 else None,
        "phraseLoopRecAction": decode_enum(data[1], ["REC>PLAY>DUB", "REC>DUB>PLAY"]) if len(data) > 1 else None,
        "metronomeLevelRaw": data[2] if len(data) > 2 else None,
        "metronomeLevel": data[2] if len(data) > 2 and 0 <= data[2] <= 100 else None,
        "mainGroundLiftRaw": data[3] if len(data) > 3 else None,
        "mainGroundLift": data[3] + 1 if len(data) > 3 and 0 <= data[3] <= 5 else None,
        "totalMetronomeOutRaw": data[4] if len(data) > 4 else None,
        "totalMetronomeOut": decode_enum(data[4], ["MAIN OUT", "SUB OUT", "MAIN+SUB"]) if len(data) > 4 else None,
        "fixedRaw": data[5:7] if len(data) > 5 else [],
    }


def decode_system_pitch(data: list[int]) -> dict[str, Any]:
    reference_pitch = live.integer_from_nibbles(data[0:4]) if len(data) >= 4 else None
    return {
        "referencePitchRaw": data[0:4] if len(data) >= 4 else [],
        "referencePitchHz": reference_pitch if reference_pitch is not None and 435 <= reference_pitch <= 445 else None,
        "polyTunerTypeRaw": data[4] if len(data) > 4 else None,
        "polyTunerType": decode_enum(data[4], ["6-REGULAR", "6-DROP D", "7-REGULAR", "7-DROP A", "4-B REGULAR", "5-B REGULAR"]) if len(data) > 4 else None,
        "polyTunerOffsetRaw": data[5] if len(data) > 5 else None,
        "polyTunerOffset": decode_poly_tuner_offset(data[5]) if len(data) > 5 else None,
        "tunerOutputRaw": data[6] if len(data) > 6 else None,
        "tunerOutput": decode_enum(data[6], ["MUTE", "BYPASS", "THRU"]) if len(data) > 6 else None,
    }


def decode_poly_tuner_offset(raw: int) -> str | None:
    values = {11: "-5", 12: "-4", 13: "-3", 14: "-2", 15: "-1", 16: "----"}
    return values.get(raw)


def decode_system_manual_controls(data: list[int]) -> dict[str, Any]:
    controls = {}
    for index in range(5):
        control_name = f"NUM {index + 1}"
        function_offset = index * 2
        mode_offset = function_offset + 1
        function_raw = data[function_offset] if len(data) > function_offset else None
        function_detail = decode_manual_control_function_detail(function_raw) if function_raw is not None else None
        controls[control_name] = {
            "functionRaw": function_raw,
            "function": function_detail["name"] if function_detail else None,
            "functionTargetBlockId": function_detail["blockId"] if function_detail else None,
            "functionTargetParameterId": function_detail["parameterId"] if function_detail else None,
            "functionCanEnableBlock": function_detail["canEnableBlock"] if function_detail else False,
            "modeRaw": data[mode_offset] if len(data) > mode_offset else None,
            "mode": "MOMENT" if len(data) > mode_offset and data[mode_offset] == 1 else "TOGGLE" if len(data) > mode_offset else None,
            "preferenceRaw": data[0x0A + index] if len(data) > 0x0A + index else None,
            "preference": decode_enum(data[0x0A + index], ["PATCH", "SYSTEM"]) if len(data) > 0x0A + index else None,
        }
    return {"controls": controls}


def decode_manual_control_function_detail(raw: int) -> dict[str, Any]:
    names: dict[int, dict[str, Any]] = {
        0: {"name": "OFF"},
        1: {"name": "LEVEL +10"},
        2: {"name": "LEVEL +20"},
        3: {"name": "LEVEL -10"},
        4: {"name": "LEVEL -20"},
        5: {"name": "BPM TAP"},
        6: {"name": "DELAY 1 TAP", "blockId": "delay1", "parameterId": "time"},
        7: {"name": "DELAY 2 TAP", "blockId": "delay2", "parameterId": "time"},
        8: {"name": "DELAY 3 TAP", "blockId": "delay3", "parameterId": "time"},
        9: {"name": "DELAY 4 TAP", "blockId": "delay4", "parameterId": "time"},
        10: {"name": "MASTER DELAY TAP", "blockId": "masterDelay", "parameterId": "time"},
        11: {"name": "TUNER/MANUAL"},
        12: {"name": "AMP CTL1"},
        13: {"name": "AMP CTL2"},
        14: {"name": "COMPRESSOR", "blockId": "comp", "parameterId": "sw", "canEnableBlock": True},
        15: {"name": "DISTORTION 1", "blockId": "dist1", "parameterId": "sw", "canEnableBlock": True},
        16: {"name": "DISTORTION 1 SOLO", "blockId": "dist1", "parameterId": "soloSw"},
        17: {"name": "DISTORTION 2", "blockId": "dist2", "parameterId": "sw", "canEnableBlock": True},
        18: {"name": "DISTORTION 2 SOLO", "blockId": "dist2", "parameterId": "soloSw"},
        19: {"name": "PREAMP 1", "blockId": "preamp1", "parameterId": "sw", "canEnableBlock": True},
        20: {"name": "PREAMP 1 SOLO", "blockId": "preamp1", "parameterId": "soloSw"},
        21: {"name": "PREAMP 2", "blockId": "preamp2", "parameterId": "sw", "canEnableBlock": True},
        22: {"name": "PREAMP 2 SOLO", "blockId": "preamp2", "parameterId": "soloSw"},
        23: {"name": "NOISE SUPPRESSOR 1", "blockId": "ns1", "parameterId": "sw", "canEnableBlock": True},
        24: {"name": "NOISE SUPPRESSOR 2", "blockId": "ns2", "parameterId": "sw", "canEnableBlock": True},
        25: {"name": "EQUALIZER 1", "blockId": "eq1", "parameterId": "sw", "canEnableBlock": True},
        26: {"name": "EQUALIZER 2", "blockId": "eq2", "parameterId": "sw", "canEnableBlock": True},
        27: {"name": "EQUALIZER 3", "blockId": "eq3", "parameterId": "sw", "canEnableBlock": True},
        28: {"name": "EQUALIZER 4", "blockId": "eq4", "parameterId": "sw", "canEnableBlock": True},
        29: {"name": "DELAY 1", "blockId": "delay1", "parameterId": "sw", "canEnableBlock": True},
        30: {"name": "DELAY 2", "blockId": "delay2", "parameterId": "sw", "canEnableBlock": True},
        31: {"name": "DELAY 3", "blockId": "delay3", "parameterId": "sw", "canEnableBlock": True},
        32: {"name": "DELAY 4", "blockId": "delay4", "parameterId": "sw", "canEnableBlock": True},
        33: {"name": "MASTER DELAY", "blockId": "masterDelay", "parameterId": "sw", "canEnableBlock": True},
        34: {"name": "CHORUS", "blockId": "chorus", "parameterId": "sw", "canEnableBlock": True},
        35: {"name": "FX 1", "blockId": "fx1", "parameterId": "sw", "canEnableBlock": True},
        36: {"name": "FX 2", "blockId": "fx2", "parameterId": "sw", "canEnableBlock": True},
        37: {"name": "FX 3", "blockId": "fx3", "parameterId": "sw", "canEnableBlock": True},
        38: {"name": "FX 1 TRIGGER", "blockId": "fx1"},
        39: {"name": "FX 2 TRIGGER", "blockId": "fx2"},
        40: {"name": "FX 3 TRIGGER", "blockId": "fx3"},
        41: {"name": "REVERB", "blockId": "reverb", "parameterId": "sw", "canEnableBlock": True},
        42: {"name": "PEDAL FX", "blockId": "pedalFx", "parameterId": "sw", "canEnableBlock": True},
        43: {"name": "DIVIDER 1 CHANNEL SELECT", "blockId": "divider1", "parameterId": "channelSelect"},
        44: {"name": "DIVIDER 2 CHANNEL SELECT", "blockId": "divider2", "parameterId": "channelSelect"},
        45: {"name": "DIVIDER 3 CHANNEL SELECT", "blockId": "divider3", "parameterId": "channelSelect"},
        46: {"name": "SEND/RETURN 1", "blockId": "sendReturn1", "parameterId": "sw", "canEnableBlock": True},
        47: {"name": "SEND/RETURN 2", "blockId": "sendReturn2", "parameterId": "sw", "canEnableBlock": True},
        48: {"name": "LOOPER"},
        49: {"name": "LOOPER STOP"},
        50: {"name": "LOOPER CLEAR"},
        51: {"name": "METRONOME"},
        52: {"name": "MIDI START"},
        53: {"name": "MMC PLAY"},
        54: {"name": "MASTER DELAY TRIGGER", "blockId": "masterDelay"},
        55: {"name": "TUNER"},
        56: {"name": "MANUAL"},
        57: {"name": "MANUAL/TUNER"},
        58: {"name": "FX 4", "blockId": "fx4", "parameterId": "sw", "canEnableBlock": True},
        59: {"name": "FX 4 TRIGGER", "blockId": "fx4"},
    }
    detail = names.get(raw)
    if detail:
        return control_function_detail(raw, **detail)
    return control_function_detail(raw, f"FUNC {raw}")


def decode_system_controls(data: list[int]) -> dict[str, Any]:
    controls = {}
    switches = [
        ("NUM 1", 0x00, 0x23), ("NUM 2", 0x02, 0x24), ("NUM 3", 0x04, 0x25),
        ("NUM 4", 0x06, 0x26), ("NUM 5", 0x08, 0x27),
        ("BANK DOWN", 0x0A, 0x28), ("BANK UP", 0x0C, 0x29),
        ("CTL 1", 0x0E, 0x2A), ("CTL 2", 0x10, 0x2B), ("CTL 3", 0x12, 0x2C),
        ("CTL 4", 0x14, 0x2D), ("CTL 5", 0x16, 0x2E), ("CTL 6", 0x18, 0x2F),
        ("CTL 7", 0x1A, 0x30), ("CURRENT NUMBER", 0x1C, 0x31), ("EXP 1 SW", 0x1E, 0x32),
    ]
    for name, function_offset, preference_offset in switches:
        function_raw = data[function_offset] if len(data) > function_offset else None
        mode_raw = data[function_offset + 1] if len(data) > function_offset + 1 else None
        preference_raw = data[preference_offset] if len(data) > preference_offset else None
        function_detail = decode_control_function_detail(function_raw, is_num=name.startswith("NUM ")) if function_raw is not None else None
        controls[name] = {
            "functionRaw": function_raw,
            "function": function_detail["name"] if function_detail else None,
            "functionTargetBlockId": function_detail["blockId"] if function_detail else None,
            "functionTargetParameterId": function_detail["parameterId"] if function_detail else None,
            "functionCanEnableBlock": function_detail["canEnableBlock"] if function_detail else False,
            "modeRaw": mode_raw,
            "mode": "MOMENT" if mode_raw == 1 else "TOGGLE" if mode_raw is not None else None,
            "preferenceRaw": preference_raw,
            "preference": decode_enum(preference_raw, ["PATCH", "SYSTEM"]) if preference_raw is not None else None,
        }

    exp_pedals = [("EXP 1", 0x20, 0x33), ("EXP 2", 0x21, 0x34), ("EXP 3", 0x22, 0x35)]
    for name, function_offset, preference_offset in exp_pedals:
        function_raw = data[function_offset] if len(data) > function_offset else None
        preference_raw = data[preference_offset] if len(data) > preference_offset else None
        function_detail = decode_exp_function_detail(function_raw) if function_raw is not None else None
        controls[name] = {
            "functionRaw": function_raw,
            "function": function_detail["name"] if function_detail else None,
            "functionTargetBlockId": function_detail["blockId"] if function_detail else None,
            "functionTargetParameterId": function_detail["parameterId"] if function_detail else None,
            "functionCanEnableBlock": function_detail["canEnableBlock"] if function_detail else False,
            "preferenceRaw": preference_raw,
            "preference": decode_enum(preference_raw, ["PATCH", "SYSTEM"]) if preference_raw is not None else None,
        }

    return {
        "controls": controls,
        "preferences": {
            name: control["preference"]
            for name, control in controls.items()
        },
    }


def chain_from_full(snapshot: dict[str, Any]) -> dict[str, Any]:
    blocks = snapshot.get("blocks", [])
    assigns_by_block = active_assigns_by_block(snapshot)
    controls_by_block = direct_controls_by_block(snapshot)
    detail_by_value = {
        block.get("chainElementValue"): block
        for block in blocks
        if block.get("chainElementValue") is not None
    }
    elements = []
    description_elements = []
    for element in snapshot.get("signalChainElements", []):
        block = detail_by_value.get(element.get("rawValue"))
        block_id = block.get("id") if block else None
        active_assigns = assigns_by_block.get(block_id, []) if block_id else []
        direct_controls = controls_by_block.get(block_id, []) if block_id else []
        is_enabled = block.get("isEnabled") if block else None
        has_control_assignment = block_has_control_assignment(block) or bool(active_assigns) or bool(direct_controls)
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
            "detailBlockID": block_id,
            "typeName": block.get("typeName") if block else None,
            "isEnabled": is_enabled,
            "hasControlAssignment": has_control_assignment,
            "activeAssignCount": len(active_assigns),
            "activeAssigns": active_assigns,
            "directControlCount": len(direct_controls),
            "directControls": direct_controls,
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
    active_assigns = active_assigns_by_block(snapshot).get(block.get("id"), [])
    direct_controls = direct_controls_by_block(snapshot).get(block.get("id"), [])
    return {
        "overview": overview_from_full(snapshot),
        "chainPositions": positions,
        "activeAssigns": active_assigns,
        "directControls": direct_controls,
        "block": block,
    }


def emit(value: Any, pretty: bool) -> None:
    indent = 2 if pretty else None
    print(json.dumps(value, indent=indent, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
