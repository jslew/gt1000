#!/usr/bin/env python3
"""Agent-facing GT-1000 CLI."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

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
    ports.add_argument("--timeout", type=float, default=8.0, help="Live CoreMIDI port inventory timeout in seconds.")
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

    performance = patch_subcommands.add_parser("performance", help="Show what the patch controls do for performance.")
    add_input_options(performance)
    performance.set_defaults(func=lambda args: patch_view(args, "performance"))

    summary = patch_subcommands.add_parser("summary", help="Show aggregated patch overview, chain, and controls.")
    add_input_options(summary)
    summary.set_defaults(func=lambda args: patch_view(args, "summary"))

    slot = patch_subcommands.add_parser("slot", help="Read one persistent user patch slot without selecting it.")
    slot.add_argument("slot", help="User slot such as U01-1.")
    slot.add_argument("--live", action="store_true", help="Required because user slots are read from the connected GT-1000.")
    slot.add_argument("--view", choices=["overview", "chain", "controls", "performance", "summary", "full"], default="summary")
    slot.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    slot.set_defaults(func=cmd_patch_slot)

    preset = patch_subcommands.add_parser("preset", help="Read one preset patch's documented primary records without selecting it.")
    preset.add_argument("slot", help="Preset slot such as P01-1.")
    preset.add_argument("--live", action="store_true", help="Required because preset slots are read from the connected GT-1000.")
    preset.add_argument("--view", choices=["overview", "chain", "controls", "performance", "summary", "full"], default="summary")
    preset.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    preset.set_defaults(func=cmd_patch_preset)

    bank = patch_subcommands.add_parser("bank", help="Read all five patches in a persistent user bank.")
    bank.add_argument("bank", help="User bank such as U01.")
    bank.add_argument("--live", action="store_true", help="Required because user banks are read from the connected GT-1000.")
    bank.add_argument("--view", choices=["overview", "chain", "controls", "performance", "summary", "full"], default="summary")
    bank.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds per slot.")
    bank.set_defaults(func=cmd_patch_bank)

    diff = patch_subcommands.add_parser("diff", help="Compare two patches in musician-facing terms.")
    diff.add_argument("source", help="Source user slot when --live is set, otherwise a full patch JSON file.")
    diff.add_argument("target", help="Target user slot when --live is set, otherwise a full patch JSON file.")
    diff.add_argument("--live", action="store_true", help="Read source and target as live user slots.")
    diff.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds per slot.")
    diff.set_defaults(func=cmd_patch_diff)

    schema = patch_subcommands.add_parser("schema", help="Show editable parameter schema for decoded blocks.")
    schema.add_argument("block_id", nargs="?", help="Optional block id such as delay1, fx1, or sendReturn1.")
    schema.add_argument("--raw", action="store_true", help="Enumerate every bounded raw-editable offset for the selected block.")
    schema.set_defaults(func=cmd_patch_schema)

    select = patch_subcommands.add_parser("select", help="Select a user patch slot with typed MIDI Program Change.")
    select.add_argument("slot", help="User slot such as U01-1.")
    select.add_argument("--live", action="store_true", help="Required because this sends MIDI to the connected GT-1000.")
    select.add_argument("--channel", type=int, default=1, help="1-based MIDI channel for Program Change, default 1.")
    select.set_defaults(func=cmd_patch_select)

    clone = patch_subcommands.add_parser("clone", help="Clone one persistent user patch slot to another.")
    clone.add_argument("source_slot", help="Source user slot such as U10-1.")
    clone.add_argument("destination_slot", help="Destination user slot such as U10-2.")
    clone.add_argument("--live", action="store_true", help="Required because this reads and writes persistent GT-1000 user slots.")
    clone.add_argument("--verify", action="store_true", help="Re-read every written clone record and compare exact bytes.")
    clone.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    clone.set_defaults(func=cmd_patch_clone)

    copy = patch_subcommands.add_parser("copy", help="Copy one persistent user patch slot to another.")
    copy.add_argument("source_slot", help="Source user slot such as U10-1.")
    copy.add_argument("destination_slot", help="Destination user slot such as U10-2.")
    copy.add_argument("--live", action="store_true", help="Required because this reads and writes persistent GT-1000 user slots.")
    copy.add_argument("--verify", action="store_true", help="Re-read every written record and compare exact bytes.")
    copy.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    copy.set_defaults(func=cmd_patch_clone)

    batch_copy = patch_subcommands.add_parser("batch-copy", help="Copy multiple user patch slots to a consecutive destination range.")
    batch_copy.add_argument("source_slots", nargs="+", help="Source user slots such as U10-1 U10-2.")
    batch_copy.add_argument("--destination-start", required=True, help="First destination user slot.")
    batch_copy.add_argument("--live", action="store_true", help="Required because this reads and writes persistent GT-1000 user slots.")
    batch_copy.add_argument("--verify", action="store_true", help="Re-read every written record and compare exact bytes.")
    batch_copy.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    batch_copy.set_defaults(func=cmd_patch_batch_copy)

    export = patch_subcommands.add_parser("export", help="Export user patch slots to a validated JSON liveset file.")
    export.add_argument("slots", nargs="+", help="User slots to export, such as U10-1 U10-2.")
    export.add_argument("--output", type=Path, required=True, help="Destination JSON file.")
    export.add_argument("--live", action="store_true", help="Required because this reads persistent GT-1000 user slots.")
    export.add_argument("--timeout", type=float, default=20.0, help="Read timeout in seconds per slot.")
    export.set_defaults(func=cmd_patch_export)

    import_liveset = patch_subcommands.add_parser("import", help="Import a CLI JSON liveset file into consecutive user slots.")
    import_liveset.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    import_liveset.add_argument("--destination-start", required=True, help="First destination user slot.")
    import_liveset.add_argument("--live", action="store_true", help="Required because this writes persistent GT-1000 user slots.")
    import_liveset.add_argument("--verify", action="store_true", help="Re-read every written record and compare exact bytes.")
    import_liveset.add_argument("--timeout", type=float, default=20.0, help="Verification timeout in seconds.")
    import_liveset.set_defaults(func=cmd_patch_import)

    tsl_export = patch_subcommands.add_parser("tsl-export", help="Wrap a CLI JSON liveset in a JSON .tsl compatibility envelope.")
    tsl_export.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    tsl_export.add_argument("--output", type=Path, required=True, help="Destination .tsl JSON file.")
    tsl_export.add_argument("--name", default="GT-1000 CLI LIVESET", help="Liveset name stored in the .tsl envelope.")
    tsl_export.add_argument("--memo", default="", help="Optional liveset memo stored in the .tsl envelope.")
    tsl_export.set_defaults(func=cmd_patch_tsl_export)

    tsl_list = patch_subcommands.add_parser("tsl-list", help="Inspect a JSON .tsl liveset file.")
    tsl_list.add_argument("file", type=Path, help="JSON .tsl file.")
    tsl_list.set_defaults(func=cmd_patch_tsl_list)

    tsl_import = patch_subcommands.add_parser("tsl-import", help="Import an importable JSON .tsl liveset envelope into consecutive user slots.")
    tsl_import.add_argument("file", type=Path, help="JSON .tsl file created by patch tsl-export.")
    tsl_import.add_argument("--destination-start", required=True, help="First destination user slot.")
    tsl_import.add_argument("--live", action="store_true", help="Required because this writes persistent GT-1000 user slots.")
    tsl_import.add_argument("--verify", action="store_true", help="Re-read every written record and compare exact bytes.")
    tsl_import.add_argument("--timeout", type=float, default=20.0, help="Verification timeout in seconds.")
    tsl_import.set_defaults(func=cmd_patch_tsl_import)

    liveset_list = patch_subcommands.add_parser("liveset-list", help="List patches in a CLI JSON liveset file.")
    liveset_list.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    liveset_list.set_defaults(func=cmd_patch_liveset_list)

    liveset_move = patch_subcommands.add_parser("liveset-move", help="Move one patch inside a CLI JSON liveset file.")
    liveset_move.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    liveset_move.add_argument("from_index", type=int, help="1-based patch index to move.")
    liveset_move.add_argument("to_index", type=int, help="1-based destination index.")
    liveset_move.add_argument("--output", type=Path, required=True, help="Destination JSON liveset file.")
    liveset_move.set_defaults(func=cmd_patch_liveset_move)

    liveset_copy = patch_subcommands.add_parser("liveset-copy", help="Copy one patch inside a CLI JSON liveset file.")
    liveset_copy.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    liveset_copy.add_argument("from_index", type=int, help="1-based patch index to copy.")
    liveset_copy.add_argument("to_index", type=int, help="1-based insertion index for the copy.")
    liveset_copy.add_argument("--output", type=Path, required=True, help="Destination JSON liveset file.")
    liveset_copy.set_defaults(func=cmd_patch_liveset_copy)

    liveset_rename = patch_subcommands.add_parser("liveset-rename", help="Rename one patch inside a CLI JSON liveset file.")
    liveset_rename.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    liveset_rename.add_argument("index", type=int, help="1-based patch index to rename.")
    liveset_rename.add_argument("name", help="Patch name, truncated to the GT-1000 16-byte ASCII field.")
    liveset_rename.add_argument("--output", type=Path, required=True, help="Destination JSON liveset file.")
    liveset_rename.set_defaults(func=cmd_patch_liveset_rename)

    liveset_remove = patch_subcommands.add_parser("liveset-remove", help="Remove one patch from a CLI JSON liveset file.")
    liveset_remove.add_argument("file", type=Path, help="JSON liveset file created by patch export.")
    liveset_remove.add_argument("index", type=int, help="1-based patch index to remove.")
    liveset_remove.add_argument("--output", type=Path, required=True, help="Destination JSON liveset file.")
    liveset_remove.set_defaults(func=cmd_patch_liveset_remove)

    restore_preset = patch_subcommands.add_parser("restore-preset", help="Restore a preset patch's documented primary records into a user slot.")
    restore_preset.add_argument("preset_slot", help="Preset source slot such as P01-1.")
    restore_preset.add_argument("destination_slot", help="Destination user slot such as U10-1.")
    restore_preset.add_argument("--live", action="store_true", help="Required because this reads preset data and writes a persistent user slot.")
    restore_preset.add_argument("--verify", action="store_true", help="Re-read every written primary record and compare exact bytes.")
    restore_preset.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    restore_preset.set_defaults(func=cmd_patch_restore_preset)

    undo_last = patch_subcommands.add_parser("undo-last", help="Restore the most recent automatic restore point.")
    undo_last.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    undo_last.add_argument("--verify", action="store_true", help="Re-read every restored range and compare exact bytes.")
    undo_last.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    undo_last.set_defaults(func=cmd_patch_undo_last)

    exchange = patch_subcommands.add_parser("exchange", help="Exchange two persistent user patch slots.")
    exchange.add_argument("slot_a", help="First user slot such as U10-1.")
    exchange.add_argument("slot_b", help="Second user slot such as U10-2.")
    exchange.add_argument("--live", action="store_true", help="Required because this reads and writes persistent GT-1000 user slots.")
    exchange.add_argument("--verify", action="store_true", help="Re-read every written record and compare exact bytes.")
    exchange.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    exchange.set_defaults(func=cmd_patch_exchange)

    insert = patch_subcommands.add_parser("insert", help="Insert one patch into a bounded user-slot range.")
    insert.add_argument("source_slot", help="Source user slot to insert.")
    insert.add_argument("destination_slot", help="Destination slot where the source patch is inserted.")
    insert.add_argument("--range-end", required=True, help="Last destination range slot to shift down by one.")
    insert.add_argument("--live", action="store_true", help="Required because this reads and writes persistent GT-1000 user slots.")
    insert.add_argument("--verify", action="store_true", help="Re-read every written record and compare exact bytes.")
    insert.add_argument("--timeout", type=float, default=20.0, help="Read/verification timeout in seconds.")
    insert.set_defaults(func=cmd_patch_insert)

    rename = patch_subcommands.add_parser("rename", help="Rename the temporary patch or one persistent user patch slot.")
    rename.add_argument("name", help="Patch name, truncated to the GT-1000 16-byte ASCII field.")
    rename.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    rename.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    rename.add_argument("--verify", action="store_true", help="Re-read the name field and compare exact bytes.")
    rename.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    rename.set_defaults(func=cmd_patch_rename)

    initialize = patch_subcommands.add_parser("initialize", help="Initialize a patch using the validated default plan.")
    initialize.add_argument("--name", default="PY DEFAULT", help="Patch name to write.")
    initialize.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    initialize.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    initialize.add_argument("--verify", action="store_true", help="Re-read every written range and compare exact bytes.")
    initialize.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    initialize.set_defaults(func=cmd_patch_initialize)

    clear = patch_subcommands.add_parser("clear", help="Clear a patch using the validated default initializer.")
    clear.add_argument("--name", default="PY DEFAULT", help="Patch name to write.")
    clear.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    clear.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    clear.add_argument("--verify", action="store_true", help="Re-read every written range and compare exact bytes.")
    clear.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    clear.set_defaults(func=cmd_patch_initialize)

    batch_initialize = patch_subcommands.add_parser("batch-initialize", help="Initialize multiple user patch slots.")
    batch_initialize.add_argument("slots", nargs="+", help="User slots to initialize.")
    batch_initialize.add_argument("--name-prefix", default="PY DEFAULT", help="Patch name prefix; slot number is appended when multiple slots are initialized.")
    batch_initialize.add_argument("--live", action="store_true", help="Required because this writes persistent GT-1000 user slots.")
    batch_initialize.add_argument("--verify", action="store_true", help="Re-read every written range and compare exact bytes.")
    batch_initialize.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    batch_initialize.set_defaults(func=cmd_patch_batch_initialize)

    block = patch_subcommands.add_parser("block", help="Show one block's detailed parameters.")
    add_input_options(block)
    block.add_argument("block_id", nargs="?", help="Block id such as preamp1 or delay1.")
    block.add_argument("--position", type=int, help="Signal-chain position to inspect.")
    block.add_argument("--user-slot", help="Read the block from a persistent user slot such as U01-1.")
    block.set_defaults(func=cmd_patch_block)

    stompbox = patch_subcommands.add_parser("stompbox", help="Read decoded PatchStompBox selections.")
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
    apply.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    apply.add_argument("--verify", action="store_true", help="Re-read every written range and compare exact bytes.")
    apply.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    apply.set_defaults(func=cmd_patch_apply)

    set_param = patch_subcommands.add_parser("set", help="Set one validated block parameter.")
    set_param.add_argument("block_id", help="Block id such as delay1 or dist1.")
    set_param.add_argument("parameter_id", help="Parameter id such as sw, type, time, or drive.")
    set_param.add_argument("value", help="Raw value, on/off, or exact type name.")
    set_param.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    set_param.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    set_param.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    set_param.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    set_param.set_defaults(func=cmd_patch_set)

    raw_set = patch_subcommands.add_parser("raw-set", help="Set one validated raw block parameter offset.")
    raw_set.add_argument("block_id", help="Block id such as delay1, fx1, divider1, or mainSpeakerSimulatorL.")
    raw_set.add_argument("offset", type=int, help="Zero-based byte offset within the block record.")
    raw_set.add_argument("value", help="Raw integer value.")
    raw_set.add_argument("--width", choices=["byte", "nibbles2", "nibbles4"], default="byte", help="Encoding width, default byte.")
    raw_set.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    raw_set.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    raw_set.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    raw_set.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    raw_set.set_defaults(func=cmd_patch_raw_set)

    enable = patch_subcommands.add_parser("enable", help="Enable one validated switchable block.")
    enable.add_argument("block_id", help="Block id such as delay1 or dist1.")
    enable.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    enable.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    enable.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    enable.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    enable.set_defaults(func=cmd_patch_enable, enabled=True)

    disable = patch_subcommands.add_parser("disable", help="Disable one validated switchable block.")
    disable.add_argument("block_id", help="Block id such as delay1 or dist1.")
    disable.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    disable.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    disable.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    disable.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    disable.set_defaults(func=cmd_patch_enable, enabled=False)

    type_command = patch_subcommands.add_parser("type", help="Change one validated block effect type.")
    type_command.add_argument("block_id", help="Block id such as dist1, preamp1, chorus, or masterDelay.")
    type_command.add_argument("type_value", help="Exact type name such as T-SCREAM, or a raw type number.")
    type_command.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    type_command.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    type_command.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    type_command.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    type_command.set_defaults(func=cmd_patch_type)

    move = patch_subcommands.add_parser("move", help="Move one decoded block in the signal chain.")
    move.add_argument("block_id", help="Block id to move, such as delay1 or dist1.")
    relation = move.add_mutually_exclusive_group(required=True)
    relation.add_argument("--before", help="Move before this block id.")
    relation.add_argument("--after", help="Move after this block id.")
    move.add_argument("--live", action="store_true", help="Required because this reads and writes the connected GT-1000.")
    move.add_argument("--user-slot", help="Move within a user patch slot instead of the temporary patch.")
    move.add_argument("--verify", action="store_true", help="Re-read the full chain and compare exact bytes.")
    move.add_argument("--timeout", type=float, default=12.0, help="Read/verification timeout in seconds.")
    move.set_defaults(func=cmd_patch_move)

    control_set = patch_subcommands.add_parser("control-set", help="Set one patch-local NUM/BANK/CTL/EXP control function.")
    control_set.add_argument("control", help="Control id such as ctl1, num1, bank-up, exp1-sw, or exp1.")
    control_set.add_argument("function", help="Function id such as dist1, tuner, delay1-tap, foot-volume, or off.")
    control_set.add_argument("--mode", choices=["toggle", "moment"], default="toggle", help="Switch mode for non-pedal controls.")
    control_set.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    control_set.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    control_set.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    control_set.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    control_set.set_defaults(func=cmd_patch_control_set)

    system_control_set = patch_subcommands.add_parser("system-control-set", help="Set one global/system NUM/BANK/CTL/EXP control function.")
    system_control_set.add_argument("control", help="Control id such as ctl1, num1, bank-up, exp1-sw, or exp1.")
    system_control_set.add_argument("function", help="Function id such as dist1, tuner, delay1-tap, foot-volume, or off.")
    system_control_set.add_argument("--mode", choices=["toggle", "moment"], default="toggle", help="Switch mode for non-pedal controls.")
    system_control_set.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000 system control section.")
    system_control_set.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    system_control_set.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    system_control_set.set_defaults(func=cmd_patch_system_control_set)

    control_preference = patch_subcommands.add_parser("control-preference-set", help="Set one control's PATCH/SYSTEM preference.")
    control_preference.add_argument("control", help="Control id such as ctl1, num1, bank-up, exp1-sw, or exp1.")
    control_preference.add_argument("preference", choices=["patch", "system"], help="Whether the control uses patch-local or system mapping.")
    control_preference.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000 system control section.")
    control_preference.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    control_preference.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    control_preference.set_defaults(func=cmd_patch_control_preference_set)

    led_set = patch_subcommands.add_parser("led-set", help="Set one patch-local control LED color.")
    led_set.add_argument("control", help="LED control id: num1...num5, bank-down, bank-up, ctl1...ctl3, or exp1-sw.")
    led_set.add_argument("state", choices=["off", "on"], help="LED state color to edit.")
    led_set.add_argument("color", help="Color name such as red, blue, cyan, auto, or auto-cyan.")
    led_set.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    led_set.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    led_set.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    led_set.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    led_set.set_defaults(func=cmd_patch_led_set)

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
    assign_cc.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    assign_cc.add_argument("--verify", action="store_true", help="Re-read the Assign block and compare exact bytes.")
    assign_cc.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    assign_cc.set_defaults(func=cmd_patch_assign_cc)

    assign_set = patch_subcommands.add_parser("assign-set", help="Set one Assign block from raw validated fields.")
    assign_set.add_argument("number", type=int, help="Assign number 1...16.")
    assign_set.add_argument("--sw", choices=["on", "off"], default="on", help="Assign switch state.")
    assign_set.add_argument("--target", required=True, help="Assign target: raw 0...16383, block.parameter, or alias such as tuner.")
    assign_set.add_argument("--min", dest="target_min", type=int, required=True, help="Logical target minimum before +32768 encoding.")
    assign_set.add_argument("--max", dest="target_max", type=int, required=True, help="Logical target maximum before +32768 encoding.")
    assign_set.add_argument("--source", required=True, help="Assign source: raw 0...127, control alias such as ctl1, or MIDI CC alias such as cc80.")
    assign_set.add_argument("--mode", choices=["toggle", "moment"], required=True, help="Assign mode.")
    assign_set.add_argument("--active-min", type=int, default=0, help="Active range low, default 0.")
    assign_set.add_argument("--active-max", type=int, default=127, help="Active range high, default 127.")
    assign_set.add_argument("--midi-channel", type=int, default=0, help="Patch MIDI channel field, 0 system or 1...16.")
    assign_set.add_argument("--midi-cc", type=int, default=0, help="Patch MIDI CC number field.")
    assign_set.add_argument("--midi-cc-min", type=int, default=0, help="Patch MIDI CC value minimum.")
    assign_set.add_argument("--midi-cc-max", type=int, default=0, help="Patch MIDI CC value maximum.")
    assign_set.add_argument("--midi-pc", type=int, default=0, help="Patch MIDI PC number field.")
    assign_set.add_argument("--midi-bank-msb", type=int, default=128, help="Patch MIDI bank MSB field.")
    assign_set.add_argument("--midi-bank-lsb", type=int, default=128, help="Patch MIDI bank LSB field.")
    assign_set.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    assign_set.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    assign_set.add_argument("--verify", action="store_true", help="Re-read the Assign block and compare exact bytes.")
    assign_set.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    assign_set.set_defaults(func=cmd_patch_assign_set)

    set_bpm = patch_subcommands.add_parser("set-bpm", help="Set validated patch master BPM.")
    set_bpm.add_argument("bpm", help="Patch master BPM, 40.0...250.0 with at most one decimal place.")
    set_bpm.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    set_bpm.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    set_bpm.add_argument("--verify", action="store_true", help="Re-read the written range and compare exact bytes.")
    set_bpm.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    set_bpm.set_defaults(func=cmd_patch_set_bpm)

    master_set = patch_subcommands.add_parser("master-set", help="Set one validated patch master field.")
    master_set.add_argument("field", help="Field id such as level, key, amp-ctl1, carryover, tempo-hold, or input-sensitivity.")
    master_set.add_argument("value", help="Field value; booleans accept on/off and key accepts names such as C(Am).")
    master_set.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    master_set.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
    master_set.add_argument("--verify", action="store_true", help="Re-read the written field and compare exact bytes.")
    master_set.add_argument("--timeout", type=float, default=12.0, help="Verification read timeout in seconds.")
    master_set.set_defaults(func=cmd_patch_master_set)

    tuner_assign = patch_subcommands.add_parser("tuner-assign", help="Install the tested Assign 16 tuner mapping.")
    tuner_assign.add_argument("--live", action="store_true", help="Required because this writes to the connected GT-1000.")
    tuner_assign.add_argument("--user-slot", help="Persist to a user patch slot instead of the temporary patch.")
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
    return live_call_with_timeout("ports --live", args.timeout, live.list_ports)


def live_call_with_timeout(label: str, process_timeout: float, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if process_timeout <= 0:
        raise CLIError("timeout must be greater than 0", 64)
    try:
        pickle.dumps((func, args, kwargs))
    except Exception:
        return func(*args, **kwargs)
    context = multiprocessing.get_context("spawn")
    with tempfile.NamedTemporaryFile(prefix="gt1000-live-call-", suffix=".pickle", delete=False) as output_file:
        output_path = Path(output_file.name)
    try:
        process = context.Process(target=live_call_worker, args=(output_path, func, args, kwargs))
        process.start()
        process.join(process_timeout)
        if process.is_alive():
            process.terminate()
            process.join(2)
            raise CLIError(
                f"{label} live MIDI worker did not finish within {process_timeout:g}s",
                1,
            )
        if output_path.stat().st_size == 0:
            raise CLIError(f"{label} failed without returning a result", 1)
        with output_path.open("rb") as handle:
            ok, payload = pickle.load(handle)
    finally:
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass
    if ok:
        return payload
    message, exit_code = payload
    raise CLIError(message, exit_code)


def live_call_worker(output_path: Path, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    try:
        payload = (True, func(*args, **kwargs))
    except CLIError as error:
        payload = (False, (str(error), error.exit_code))
    except Exception as error:
        payload = (False, (str(error), 1))
    with output_path.open("wb") as handle:
        pickle.dump(payload, handle)


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
        raw = live_call_with_timeout(
            f"system {args.system_command} --live",
            patch_record_process_timeout(args.timeout, 1),
            live.read_system_section,
            address,
            size,
            timeout=args.timeout,
        )
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
            raw = live_call_with_timeout(
                f"system pcmap --live bank {bank}",
                patch_record_process_timeout(args.timeout, 1),
                live.read_system_section,
                address,
                size,
                timeout=args.timeout,
            )
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
            raw = live_call_with_timeout(
                f"system inputs --live number {number}",
                patch_record_process_timeout(args.timeout, 1),
                live.read_system_section,
                address,
                size,
                timeout=args.timeout,
            )
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

    all_definitions = list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) + list(live.RESIDENT_BLOCKS)
    for block in all_definitions:
        if block.id.lower() == lower_id:
            return block.id
    return block_id


def chain_value_for_block_id(block_id: str) -> int:
    resolved = resolve_block_id(block_id)
    all_definitions = list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) + list(live.RESIDENT_BLOCKS)
    block = next((definition for definition in all_definitions if definition.id == resolved), None)
    if block is None:
        raise ValueError(f"unknown chain block {block_id}")
    return block.chain_element_value


def assign_target_for_block_parameter(block_id: str, parameter_id: str) -> dict[str, Any]:
    resolved = resolve_block_id(block_id)
    parameter_key = normalize_cli_key(parameter_id)
    for target_range in ASSIGN_TARGET_RANGES:
        if target_range["blockId"] != resolved:
            continue
        for index, (candidate_id, _candidate_name) in enumerate(target_range["parameters"]):
            if candidate_id == parameter_id or normalize_cli_key(candidate_id) == parameter_key:
                raw = target_range["start"] + index
                return assign_target_detail(
                    raw,
                    name=f'{target_range["category"]} {_candidate_name}',
                    category=target_range["category"],
                    blockId=resolved,
                    parameterId=candidate_id,
                    isOnOff=candidate_id in {"sw", "soloSw", "bright", "trigger", "preampSw"},
                )
    raise ValueError(f"unknown Assign target for {block_id}.{parameter_id}")


def parse_assign_target_reference(value: str) -> int:
    text = value.strip()
    if text.isdigit():
        return int(text)
    key = normalize_cli_key(text)
    exact_targets = {
        "divider1-channel-select": 932,
        "divider1-channelselect": 932,
        "divider1.channelselect": 932,
        "divider1.channel-select": 932,
        "divider2-channel-select": 933,
        "divider2-channelselect": 933,
        "divider2.channelselect": 933,
        "divider2.channel-select": 933,
        "divider3-channel-select": 934,
        "divider3-channelselect": 934,
        "divider3.channelselect": 934,
        "divider3.channel-select": 934,
        "tuner": 987,
        "tuner-on-off": 987,
        "tuner-pdf-alternate": 991,
    }
    if key in exact_targets:
        return exact_targets[key]
    for separator in (".", ":"):
        if separator in text:
            block_id, parameter_id = text.split(separator, 1)
            return assign_target_for_block_parameter(block_id, parameter_id)["raw"]
    if "-" in key:
        parts = key.split("-")
        for split_at in range(len(parts) - 1, 0, -1):
            block_id = "-".join(parts[:split_at])
            parameter_id = "-".join(parts[split_at:])
            try:
                return assign_target_for_block_parameter(block_id, parameter_id)["raw"]
            except ValueError:
                continue
    raise ValueError(f"unknown Assign target {value}")


def parse_assign_source_reference(value: str) -> int:
    text = value.strip()
    if text.isdigit():
        return int(text)
    key = normalize_cli_key(text)
    source_aliases = {
        "cur-num": 5,
        "current-number": 5,
        "bank-down": 6,
        "bank-up": 7,
        "exp1-sw": 15,
        "exp1-switch": 15,
        "exp1": 16,
        "exp1-pedal": 16,
        "exp2": 17,
        "exp2-pedal": 17,
        "exp3": 18,
        "exp3-pedal": 18,
        "internal": 19,
        "internal-pedal": 19,
        "wave": 20,
        "wave-pedal": 20,
        "input": 21,
        "input-level": 21,
    }
    if key in source_aliases:
        return source_aliases[key]
    if key.startswith("num") and key[3:].isdigit():
        number = int(key[3:])
        if 1 <= number <= 5:
            return number - 1
    if key.startswith("ctl") and key[3:].isdigit():
        number = int(key[3:])
        if 1 <= number <= 7:
            return number + 7
    if key.startswith("midi-cc"):
        return assign_source_for_cc_text(key[7:])
    if key.startswith("cc"):
        return assign_source_for_cc_text(key[2:])
    raise ValueError(f"unknown Assign source {value}")


def assign_source_for_cc_text(value: str) -> int:
    if not value.isdigit():
        raise ValueError(f"unknown MIDI CC source cc{value}")
    return patch_edit.assign_source_for_cc(int(value))


def normalize_cli_key(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-").replace(".", "-")


def user_patch_zero_based_index(slot: str) -> int:
    return live.user_patch_zero_based_index(slot)


def decode_patch_stompbox_section(data: list[int], definitions: list[dict[str, str | None]], *, size: list[int]) -> dict[str, Any]:
    selections = []
    for index, definition in enumerate(definitions):
        raw = data[index] if len(data) > index else None
        prefix = definition["prefix"]
        selections.append({
            "offset": index,
            "address": f"00 {index:02X}",
            "id": definition["id"],
            "displayName": definition["displayName"],
            "rawValue": raw,
            "selection": stompbox_selection_name(raw, prefix) if raw is not None and prefix is not None else None,
        })
    return {
        "supported": True,
        "totalSize": live.hex_bytes(size),
        "selections": selections,
    }


def stompbox_selection_name(raw: int, prefix: str | None) -> str | None:
    if prefix is None:
        return None
    if raw == 0:
        return "---"
    if 1 <= raw <= 10:
        return f"{prefix}-{raw}"
    return None


def stompbox_definition(id_: str, display_name: str, prefix: str | None) -> dict[str, str | None]:
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

STOMPBOX2_SELECTIONS = [
    stompbox_definition("fx1PhaserBass", "FX 1 Bass Phaser", "PHB"),
    stompbox_definition("fx1TWahBass", "FX 1 Bass Touch Wah", "TWB"),
    stompbox_definition("fx2ChorusBass", "FX 2 Bass Chorus", "CHB"),
    stompbox_definition("fx2DefretterBass", "FX 2 Bass Defretter", "DFB"),
    stompbox_definition("fx2FlangerBass", "FX 2 Bass Flanger", "FLB"),
    stompbox_definition("fx2OctaveBass", "FX 2 Bass Octave", "OCB"),
    stompbox_definition("fx2PhaserBass", "FX 2 Bass Phaser", "PHB"),
    stompbox_definition("reserved07", "Reserved 07", None),
    stompbox_definition("reserved08", "Reserved 08", None),
    stompbox_definition("reserved09", "Reserved 09", None),
    stompbox_definition("fx2TWahBass", "FX 2 Bass Touch Wah", "TWB"),
    stompbox_definition("fx3ChorusBass", "FX 3 Bass Chorus", "CHB"),
    stompbox_definition("fx3DefretterBass", "FX 3 Bass Defretter", "DFB"),
    stompbox_definition("fx3FlangerBass", "FX 3 Bass Flanger", "FLB"),
    stompbox_definition("reserved0E", "Reserved 0E", None),
    stompbox_definition("reserved0F", "Reserved 0F", None),
    stompbox_definition("reserved10", "Reserved 10", None),
]

STOMPBOX3_SELECTIONS = [
    stompbox_definition("fx3OctaveBass", "FX 3 Bass Octave", "OCB"),
    stompbox_definition("fx3PhaserBass", "FX 3 Bass Phaser", "PHB"),
    stompbox_definition("fx3TWahBass", "FX 3 Bass Touch Wah", "TWB"),
    stompbox_definition("fx4AGSim", "FX 4 Acoustic Guitar Simulator", "ACO"),
    stompbox_definition("fx4AcReso", "FX 4 Acoustic Resonance", "ACR"),
    stompbox_definition("fx4AWah", "FX 4 Auto Wah", "AW"),
    stompbox_definition("fx4Chorus", "FX 4 Chorus", "CHO"),
    stompbox_definition("fx4CVibe", "FX 4 Classic Vibe", "CV"),
    stompbox_definition("fx4Comp", "FX 4 Compressor", "CMP"),
    stompbox_definition("fx4Defretter", "FX 4 Defretter", "DEF"),
    stompbox_definition("fx4Feedbacker", "FX 4 Feedbacker", "FB"),
    stompbox_definition("fx4Flanger", "FX 4 Flanger", "FL"),
    stompbox_definition("fx4Harmonist", "FX 4 Harmonist", "HRM"),
    stompbox_definition("fx4Humanizer", "FX 4 Humanizer", "HMN"),
    stompbox_definition("fx4Octave", "FX 4 Octave", "OC"),
    stompbox_definition("fx4Overtone", "FX 4 Overtone", "OT"),
    stompbox_definition("fx4Pan", "FX 4 Pan", "PAN"),
    stompbox_definition("fx4Phaser", "FX 4 Phaser", "PH"),
    stompbox_definition("fx4PitchShift", "FX 4 Pitch Shift", "PS"),
    stompbox_definition("fx4RingMod", "FX 4 Ring Modulator", "RM"),
    stompbox_definition("fx4Rotary", "FX 4 Rotary", "RT"),
    stompbox_definition("fx4SitarSim", "FX 4 Sitar Simulator", "STR"),
    stompbox_definition("fx4Slicer", "FX 4 Slicer", "SL"),
    stompbox_definition("fx4SlowGear", "FX 4 Slow Gear", "SG"),
    stompbox_definition("fx4SoundHold", "FX 4 Sound Hold", "SH"),
    stompbox_definition("fx4SBend", "FX 4 S-Bend", "SB"),
    stompbox_definition("fx4TWah", "FX 4 Touch Wah", "TW"),
    stompbox_definition("fx4Tremolo", "FX 4 Tremolo", "TR"),
    stompbox_definition("fx4Vibrato", "FX 4 Vibrato", "VIB"),
    stompbox_definition("fx4ChorusBass", "FX 4 Bass Chorus", "CHB"),
    stompbox_definition("fx4DefretterBass", "FX 4 Bass Defretter", "DFB"),
    stompbox_definition("fx4FlangerBass", "FX 4 Bass Flanger", "FLB"),
    stompbox_definition("reserved20", "Reserved 20", None),
    stompbox_definition("fx4OctaveBass", "FX 4 Bass Octave", "OCB"),
    stompbox_definition("fx4PhaserBass", "FX 4 Bass Phaser", "PHB"),
    stompbox_definition("fx4TWahBass", "FX 4 Bass Touch Wah", "TWB"),
    stompbox_definition("bassDist", "Bass Distortion", "BDS"),
]


def patch_view(args: argparse.Namespace, view: str) -> Any:
    if args.live or args.file is None:
        requests = requests_for_view(view)
        if view == "performance":
            snapshot = read_performance_snapshot_with_timeout(f"patch {view} --live", args.timeout)
        else:
            snapshot = read_live_snapshot_with_timeout(
                f"patch {view} --live",
                args.timeout,
                requests=requests,
            )
        if view == "chain":
            return chain_from_full(snapshot)
        if view == "overview":
            return overview_from_full(snapshot)
        if view == "controls":
            return controls_from_full(snapshot)
        if view == "performance":
            return performance_from_full(snapshot)
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
    if view == "performance":
        return performance_from_full(snapshot)
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


def cmd_patch_preset(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch preset requires --live because preset slots are live device state", 64)
    try:
        snapshot = read_preset_slot_snapshot(args.slot, args.timeout, view=args.view)
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


def cmd_patch_diff(args: argparse.Namespace) -> Any:
    if args.live:
        try:
            source = live.normalize_user_slot(args.source)
            target = live.normalize_user_slot(args.target)
            source_snapshot = read_clone_snapshot_with_timeout(f"patch diff {source} --live", args.timeout, source)
            target_snapshot = read_clone_snapshot_with_timeout(f"patch diff {target} --live", args.timeout, target)
        except ValueError as error:
            raise CLIError(str(error), 64) from error
        return patch_diff_from_full(source_snapshot, target_snapshot, source_label=source, target_label=target)

    source_path = Path(args.source)
    target_path = Path(args.target)
    return patch_diff_from_full(
        load_json(source_path),
        load_json(target_path),
        source_label=str(source_path),
        target_label=str(target_path),
    )


def cmd_patch_schema(args: argparse.Namespace) -> Any:
    try:
        if args.block_id:
            schema_key = normalize_cli_key(args.block_id)
            if schema_key in {"master", "patch-master"}:
                return master_schema()
            if schema_key in {"controls", "control", "ctl-exp"}:
                return controls_editor_schema()
            if schema_key in {"assign", "assigns"}:
                return assign_editor_schema()
            if schema_key in {"led", "leds", "patch-led"}:
                return led_editor_schema()
            block_id = resolve_block_id(args.block_id)
            return block_schema(block_id, include_raw=args.raw)
        blocks = [
            block_schema(block.id, include_raw=False)
            for block in list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) + list(live.RESIDENT_BLOCKS)
        ]
        return {"id": "patchSchema", "blocks": blocks}
    except ValueError as error:
        raise CLIError(str(error), 64) from error


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


def cmd_patch_clone(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError(f"patch {args.patch_command} requires --live because it reads and writes persistent GT-1000 user slots", 64)
    try:
        source = live.normalize_user_slot(args.source_slot)
        destination = live.normalize_user_slot(args.destination_slot)
        if source == destination:
            raise ValueError("source and destination slots must be different")
        source_data = read_clone_records_with_timeout(f"patch {args.patch_command} {source} --live", args.timeout, source)
        plan = patch_edit.build_clone_plan(source, destination, source_data)
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["sourceSlot"] = source
        result["destinationSlot"] = destination
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_batch_copy(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch batch-copy requires --live because it reads and writes persistent GT-1000 user slots", 64)
    try:
        sources = [live.normalize_user_slot(slot) for slot in args.source_slots]
        destinations = consecutive_user_slots(args.destination_start, len(sources))
        if len(set(destinations)) != len(destinations):
            raise ValueError("destination slots must be unique")
        writes = []
        operations = []
        for index, (source, destination) in enumerate(zip(sources, destinations)):
            if source == destination:
                raise ValueError("source and destination slots must be different")
            source_data = read_clone_records_with_timeout(f"patch batch-copy {source} --live", args.timeout, source)
            delay_between_slot_reads(index, len(sources))
            plan = patch_edit.build_clone_plan(source, destination, source_data)
            writes.extend(plan.writes)
            operations.append({"sourceSlot": source, "destinationSlot": destination, "writeCount": len(plan.writes)})
        plan = patch_edit.PatchPlan(
            id=f"batch-copy:{sources[0]}:{destinations[0]}:{len(sources)}",
            description=f"Copy {len(sources)} user patch slots to consecutive destinations starting at {destinations[0]}.",
            writes=writes,
        )
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["operations"] = operations
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_export(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch export requires --live because it reads persistent GT-1000 user slots", 64)
    try:
        slots = [live.normalize_user_slot(slot) for slot in args.slots]
        patches = []
        for index, slot in enumerate(slots):
            source_data = read_clone_records_with_timeout(f"patch export {slot} --live", args.timeout, slot)
            delay_between_slot_reads(index, len(slots))
            patches.append(patch_edit.export_liveset_patch(slot, source_data))
        liveset = patch_edit.build_liveset_export(patches)
        args.output.write_text(json.dumps(liveset, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "format": liveset["format"],
            "patchCount": liveset["patchCount"],
            "slots": slots,
            "output": str(args.output),
        }
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_import(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch import requires --live because it writes persistent GT-1000 user slots", 64)
    try:
        liveset = load_json(args.file)
        plan = patch_edit.build_liveset_import_plan(liveset, args.destination_start)
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        patch_count = len(liveset.get("patches", []))
        result["sourceFile"] = str(args.file)
        result["destinationSlots"] = patch_edit.consecutive_user_slots(args.destination_start, patch_count)
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_tsl_export(args: argparse.Namespace) -> Any:
    try:
        liveset = load_json(args.file)
        tsl = patch_edit.build_tsl_export(liveset, name=args.name, memo=args.memo)
        write_json(args.output, tsl)
        summary = patch_edit.tsl_summary(tsl)
        summary["output"] = str(args.output)
        return summary
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_tsl_list(args: argparse.Namespace) -> Any:
    try:
        return patch_edit.tsl_summary(load_json(args.file))
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_tsl_import(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch tsl-import requires --live because it writes persistent GT-1000 user slots", 64)
    try:
        tsl = load_json(args.file)
        plan = patch_edit.build_tsl_import_plan(tsl, args.destination_start)
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["sourceFile"] = str(args.file)
        result["destinationSlots"] = patch_edit.consecutive_user_slots(args.destination_start, len(patch_edit.tsl_patch_list(tsl)))
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_liveset_list(args: argparse.Namespace) -> Any:
    try:
        return patch_edit.liveset_summary(load_json(args.file))
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_liveset_move(args: argparse.Namespace) -> Any:
    try:
        liveset = patch_edit.move_liveset_patch(load_json(args.file), args.from_index, args.to_index)
        write_json(args.output, liveset)
        result = patch_edit.liveset_summary(liveset)
        result["operation"] = "move"
        result["fromIndex"] = args.from_index
        result["toIndex"] = args.to_index
        result["output"] = str(args.output)
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_liveset_copy(args: argparse.Namespace) -> Any:
    try:
        liveset = patch_edit.copy_liveset_patch(load_json(args.file), args.from_index, args.to_index)
        write_json(args.output, liveset)
        result = patch_edit.liveset_summary(liveset)
        result["operation"] = "copy"
        result["fromIndex"] = args.from_index
        result["toIndex"] = args.to_index
        result["output"] = str(args.output)
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_liveset_rename(args: argparse.Namespace) -> Any:
    try:
        liveset = patch_edit.rename_liveset_patch(load_json(args.file), args.index, args.name)
        write_json(args.output, liveset)
        result = patch_edit.liveset_summary(liveset)
        result["operation"] = "rename"
        result["index"] = args.index
        result["name"] = args.name
        result["output"] = str(args.output)
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_liveset_remove(args: argparse.Namespace) -> Any:
    try:
        liveset = patch_edit.remove_liveset_patch(load_json(args.file), args.index)
        write_json(args.output, liveset)
        result = patch_edit.liveset_summary(liveset)
        result["operation"] = "remove"
        result["index"] = args.index
        result["output"] = str(args.output)
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error


def cmd_patch_restore_preset(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch restore-preset requires --live because it reads preset data and writes a persistent GT-1000 user slot", 64)
    try:
        preset = live.normalize_preset_slot(args.preset_slot)
        destination = live.normalize_user_slot(args.destination_slot)
        source_data = read_patch_records_with_timeout(
            f"patch restore-preset {preset} --live",
            args.timeout,
            patch_edit.preset_restore_read_requests(preset),
        )
        plan = patch_edit.build_preset_restore_plan(preset, destination, source_data)
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["presetSlot"] = preset
        result["destinationSlot"] = destination
        result["recordScope"] = "documented-primary-patch-records"
        result["note"] = "Preset extra STOMPBOX records are not copied because their preset addresses are not documented."
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_undo_last(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch undo-last requires --live because it writes to the connected GT-1000", 64)
    restore_path = latest_restore_point_path()
    if not restore_path.is_file():
        raise CLIError(f"no restore point found at {restore_path}", 1)
    restore = load_json(restore_path)
    try:
        plan = restore_plan_from_data(restore)
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify, create_restore=False)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    result["restorePoint"] = str(restore_path)
    result["restoredPlan"] = restore.get("plan")
    return result


def cmd_patch_exchange(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch exchange requires --live because it reads and writes persistent GT-1000 user slots", 64)
    try:
        slot_a = live.normalize_user_slot(args.slot_a)
        slot_b = live.normalize_user_slot(args.slot_b)
        if slot_a == slot_b:
            raise ValueError("exchange slots must be different")
        data_a = read_clone_records_with_timeout(f"patch exchange {slot_a} --live", args.timeout, slot_a)
        delay_between_slot_reads(0, 2)
        data_b = read_clone_records_with_timeout(f"patch exchange {slot_b} --live", args.timeout, slot_b)
        plan = patch_edit.build_exchange_plan(slot_a, slot_b, data_a, data_b)
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["slotA"] = slot_a
        result["slotB"] = slot_b
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_insert(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch insert requires --live because it reads and writes persistent GT-1000 user slots", 64)
    try:
        source = live.normalize_user_slot(args.source_slot)
        destination = live.normalize_user_slot(args.destination_slot)
        range_end = live.normalize_user_slot(args.range_end)
        destination_index = live.user_patch_zero_based_index(destination)
        range_end_index = live.user_patch_zero_based_index(range_end)
        if range_end_index < destination_index:
            raise ValueError("--range-end must be at or after destination_slot")
        destination_range = consecutive_user_slots(destination, range_end_index - destination_index + 1)

        source_data = read_clone_records_with_timeout(f"patch insert {source} --live", args.timeout, source)
        read_slots = [source, *destination_range[:-1]]
        existing_data = {}
        for index, slot in enumerate(destination_range[:-1], start=1):
            delay_between_slot_reads(index - 1, len(read_slots))
            existing_data[slot] = read_clone_records_with_timeout(f"patch insert {slot} --live", args.timeout, slot)
        writes = []
        operations = []
        for from_slot, to_slot, source_records in [
            *[
                (slot, destination_range[index + 1], existing_data[slot])
                for index, slot in reversed(list(enumerate(destination_range[:-1])))
            ],
            (source, destination, source_data),
        ]:
            plan = patch_edit.build_clone_plan(from_slot, to_slot, source_records)
            writes.extend(plan.writes)
            operations.append({"sourceSlot": from_slot, "destinationSlot": to_slot, "writeCount": len(plan.writes)})
        plan = patch_edit.PatchPlan(
            id=f"insert:{source}:{destination}:{range_end}",
            description=f"Insert {source} at {destination}, shifting through {range_end}.",
            writes=writes,
        )
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["sourceSlot"] = source
        result["destinationSlot"] = destination
        result["rangeEnd"] = range_end
        result["operations"] = operations
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_rename(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch rename requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_rename_plan(args.name, slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_initialize(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch initialize requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_default_patch_plan(args.name)
        if args.user_slot:
            plan = patch_edit.plan_for_user_slot(plan, args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_batch_initialize(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch batch-initialize requires --live because it writes persistent GT-1000 user slots", 64)
    try:
        slots = [live.normalize_user_slot(slot) for slot in args.slots]
        if len(set(slots)) != len(slots):
            raise ValueError("slots must be unique")
        writes = []
        operations = []
        for index, slot in enumerate(slots, start=1):
            name = args.name_prefix if len(slots) == 1 else f"{args.name_prefix} {index}"
            plan = patch_edit.plan_for_user_slot(patch_edit.build_default_patch_plan(name), slot)
            writes.extend(plan.writes)
            operations.append({"slot": slot, "name": name, "writeCount": len(plan.writes)})
        plan = patch_edit.PatchPlan(
            id=f"batch-initialize:{slots[0]}:{len(slots)}",
            description=f"Initialize {len(slots)} user patch slots.",
            writes=writes,
        )
        result = apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
        result["operations"] = operations
        return result
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


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
            all_definitions = list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) + list(live.RESIDENT_BLOCKS)
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
            header_snapshot = read_live_snapshot_with_timeout(
                "patch block position header --live",
                args.timeout,
                requests=live.INITIAL_READS,
            )
            element = next(
                (item for item in header_snapshot.get("signalChainElements", []) if item.get("position") == args.position),
                None,
            )
            if element is None:
                raise CLIError(f"unknown chain position {args.position}", 64)
            
            all_definitions = list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) + list(live.RESIDENT_BLOCKS)
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
        snapshot = read_live_snapshot_with_timeout(
            "patch block --live",
            args.timeout,
            requests=requests,
        )
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
    source_slot = None
    records = [
        ("patchStompBox", "Patch Stompbox", live.TEMPORARY_PATCH_STOMPBOX, [0x00, 0x00, 0x00, 0x68], STOMPBOX_SELECTIONS),
        ("patchStompBox2", "Patch Stompbox 2", live.TEMPORARY_PATCH2_STOMPBOX, [0x00, 0x00, 0x00, 0x11], STOMPBOX2_SELECTIONS),
        ("patchStompBox3", "Patch Stompbox 3", live.TEMPORARY_PATCH3_STOMPBOX, [0x00, 0x00, 0x00, 0x25], STOMPBOX3_SELECTIONS),
    ]
    if args.user_slot:
        source_slot = live.normalize_user_slot(args.user_slot)
        records = [
            (records[0][0], records[0][1], live.remap_temporary_patch_address(records[0][2], live.user_patch_base(source_slot)), records[0][3], records[0][4]),
            (records[1][0], records[1][1], live.user_patch2_base(source_slot), records[1][3], records[1][4]),
            (records[2][0], records[2][1], live.user_patch3_base(source_slot), records[2][3], records[2][4]),
        ]
    requests = [
        live.PatchReadRequest(label, address, size)
        for _id, label, address, size, _definitions in records
    ]
    try:
        raw = read_patch_records_with_timeout(
            "patch stompbox --live",
            args.timeout,
            requests,
        )
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error
    sections = []
    selections = []
    for section_id, label, address, size, definitions in records:
        data = raw.get(live.address_key(address), [])
        decoded = decode_patch_stompbox_section(data, definitions, size=size)
        sections.append({
            "id": section_id,
            "label": label,
            "address": live.hex_bytes(address),
            "size": live.hex_bytes(size),
            "rawDataHex": live.hex_string(data),
            "decoded": decoded,
        })
        selections.extend(
            dict(selection, sectionId=section_id)
            for selection in decoded["selections"]
        )
    return {
        "id": "patchStompBox",
        "label": "Patch Stompbox Selections",
        "sourceSlot": source_slot,
        "sections": sections,
        "decoded": {
            "supported": True,
            "sections": [section["id"] for section in sections],
            "selections": selections,
        },
    }


def cmd_patch_dump(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch dump currently requires --live", 64)

    dump = read_live_snapshot_with_timeout(
        "patch dump --live",
        args.timeout,
    )
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
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch set requires --live because it writes to the connected GT-1000", 64)
    try:
        args.block_id = resolve_block_id(args.block_id)
        plan = patch_edit.build_parameter_set_plan(args.block_id, args.parameter_id, args.value, slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_raw_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch raw-set requires --live because it writes to the connected GT-1000", 64)
    try:
        block_id = resolve_block_id(args.block_id)
        plan = patch_edit.build_raw_parameter_set_plan(block_id, args.offset, args.value, width=args.width, slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
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
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
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
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
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
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_control_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch control-set requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_control_set_plan(args.control, args.function, mode=args.mode, slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_system_control_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch system-control-set requires --live because it writes to the connected GT-1000 system control section", 64)
    try:
        plan = patch_edit.build_system_control_set_plan(args.control, args.function, mode=args.mode)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_control_preference_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch control-preference-set requires --live because it writes to the connected GT-1000 system control section", 64)
    try:
        plan = patch_edit.build_control_preference_plan(args.control, args.preference)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_led_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch led-set requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_led_set_plan(args.control, args.state, args.color, slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
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
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_assign_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch assign-set requires --live because it writes to the connected GT-1000", 64)
    try:
        target = parse_assign_target_reference(args.target)
        source = parse_assign_source_reference(args.source)
        plan = patch_edit.build_assign_set_plan(
            args.number,
            enabled=args.sw == "on",
            target=target,
            target_min=args.target_min,
            target_max=args.target_max,
            source=source,
            mode=args.mode,
            active_min=args.active_min,
            active_max=args.active_max,
            midi_channel=args.midi_channel,
            midi_cc=args.midi_cc,
            midi_cc_min=args.midi_cc_min,
            midi_cc_max=args.midi_cc_max,
            midi_pc=args.midi_pc,
            midi_bank_msb=args.midi_bank_msb,
            midi_bank_lsb=args.midi_bank_lsb,
            slot=args.user_slot,
        )
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_set_bpm(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch set-bpm requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_bpm_set_plan(args.bpm, slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_master_set(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch master-set requires --live because it writes to the connected GT-1000", 64)
    try:
        if args.user_slot:
            slot = live.normalize_user_slot(args.user_slot)
            address = live.remap_temporary_patch_address(live.TEMPORARY_PATCH_EFFECT, live.user_patch_base(slot))
            request = live.PatchReadRequest("Patch Effect", address, [0x00, 0x00, 0x01, 0x1C])
            data = read_patch_records_with_timeout(
                f"patch master-set {slot} source record",
                args.timeout,
                [request],
                reader=patch_edit.read_data_sets_sequential_session,
            )[live.address_key(address)]
            plan = patch_edit.build_master_set_record_plan(args.field, args.value, data, slot=slot)
        else:
            plan = patch_edit.build_master_set_plan(args.field, args.value)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
    except ValueError as error:
        raise CLIError(str(error), 64) from error
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def cmd_patch_tuner_assign(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch tuner-assign requires --live because it writes to the connected GT-1000", 64)
    try:
        plan = patch_edit.build_tuner_assign_plan(slot=args.user_slot)
        return apply_plan_cli(plan, timeout=args.timeout, verify=args.verify)
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


def performance_from_full(snapshot: dict[str, Any]) -> dict[str, Any]:
    controls_view = controls_from_full(snapshot)
    controls = controls_view["controls"]
    active_assigns = controls_view["activeAssigns"]
    assigns_by_source: dict[str, list[dict[str, Any]]] = {}
    for assign in active_assigns:
        source = assign.get("sourceName")
        if source:
            assigns_by_source.setdefault(source, []).append(assign)

    rows = []
    matched_assign_ids: set[str] = set()
    system_controls = []
    no_action_controls = []
    tuner_available = False
    for name, control in controls.items():
        sources = assign_source_names_for_control(name)
        assigns = [
            assign
            for source in sources
            for assign in assigns_by_source.get(source, [])
        ]
        matched_assign_ids.update(assign.get("id", "") for assign in assigns)
        direct_function = control.get("function")
        direct_is_active = direct_function not in {None, "OFF"}
        if direct_function and "TUNER" in direct_function:
            tuner_available = True
        if any("TUNER" in (assign.get("targetName") or "") for assign in assigns):
            tuner_available = True
        if control.get("preference") == "SYSTEM":
            system_controls.append(name)
        formatted_assigns = [performance_assign(assign) for assign in assigns]
        if not direct_is_active and not formatted_assigns:
            no_action_controls.append(name)
        rows.append({
            "control": name,
            "kind": performance_control_kind(name),
            "preference": control.get("preference"),
            "mode": control.get("mode"),
            "directFunction": direct_function,
            "directTargetBlockId": control.get("functionTargetBlockId"),
            "directTargetParameterId": control.get("functionTargetParameterId"),
            "directCanEnableBlock": control.get("functionCanEnableBlock"),
            "assignCount": len(formatted_assigns),
            "assigns": formatted_assigns,
            "action": performance_action_summary(control, formatted_assigns),
        })

    external_assigns = [
        performance_assign(assign)
        for assign in active_assigns
        if assign.get("id") not in matched_assign_ids
    ]
    notes = []
    if not tuner_available:
        notes.append("No tuner control is mapped in the decoded direct controls or active Assigns.")
    if system_controls:
        notes.append(f"{len(system_controls)} controls use SYSTEM preference: {', '.join(system_controls)}.")
    if active_assigns:
        notes.append(f"{len(active_assigns)} active Assign overlays are enabled.")
    if no_action_controls:
        notes.append(f"{len(no_action_controls)} controls have no patch-specific action.")

    overview = overview_from_full(snapshot)
    return {
        "id": "patchPerformance",
        "overview": overview,
        "patchName": overview.get("patchName"),
        "masterBPM": overview.get("masterBPM"),
        "masterPatchLevel": overview.get("masterPatchLevel"),
        "tunerAvailable": tuner_available,
        "controlCount": len(rows),
        "activeAssignCount": len(active_assigns),
        "controls": rows,
        "externalAssigns": external_assigns,
        "notes": notes,
    }


def assign_source_names_for_control(name: str) -> list[str]:
    if name == "CUR NUM":
        return ["CURRENT NUMBER"]
    if name.startswith("EXP ") and not name.endswith("SW"):
        return [f"{name} PEDAL"]
    return [name]


def performance_control_kind(name: str) -> str:
    if name.startswith("EXP ") and not name.endswith("SW"):
        return "expression-pedal"
    return "footswitch"


def performance_assign(assign: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": assign.get("id"),
        "source": assign.get("sourceName"),
        "mode": assign.get("mode"),
        "target": assign.get("targetName"),
        "targetBlockId": assign.get("targetBlockId"),
        "targetParameterId": assign.get("targetParameterId"),
        "targetIsOnOff": assign.get("targetIsOnOff"),
        "targetMin": assign.get("targetMin"),
        "targetMax": assign.get("targetMax"),
        "summary": f"{assign.get('sourceName')} -> {assign.get('targetName')} ({assign.get('mode')})",
    }


def performance_action_summary(control: dict[str, Any], assigns: list[dict[str, Any]]) -> str:
    parts = []
    direct_function = control.get("function")
    if direct_function and direct_function != "OFF":
        mode = control.get("mode")
        parts.append(f"Direct: {direct_function}" + (f" ({mode})" if mode else ""))
    parts.extend(assign["summary"] for assign in assigns)
    return "; ".join(parts) if parts else "No patch action"


def patch_diff_from_full(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    source_label: str,
    target_label: str,
) -> dict[str, Any]:
    overview_changes = overview_diff(source, target)
    chain_changes = chain_diff(source, target)
    block_changes = block_diff(source, target)
    control_changes = controls_diff(source, target)
    assign_changes = assigns_diff(source, target)
    summary = diff_summary(overview_changes, chain_changes, block_changes, control_changes, assign_changes)
    return {
        "id": "patchDiff",
        "source": source_label,
        "target": target_label,
        "sourcePatchName": source.get("patchName"),
        "targetPatchName": target.get("patchName"),
        "summary": summary,
        "overviewChanges": overview_changes,
        "chainChanges": chain_changes,
        "blockChanges": block_changes,
        "controlChanges": control_changes,
        "assignChanges": assign_changes,
    }


def overview_diff(source: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [
        ("patchName", "Patch name"),
        ("masterBPM", "Master BPM"),
        ("masterPatchLevel", "Patch level"),
        ("masterKey", "Key"),
        ("masterCarryoverEnabled", "Carryover"),
    ]
    changes = []
    for key, label in fields:
        if source.get(key) != target.get(key):
            changes.append({"field": key, "label": label, "source": source.get(key), "target": target.get(key)})
    return changes


def chain_diff(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    source_chain = source.get("signalChainSummary") or chain_summary_from_elements(source)
    target_chain = target.get("signalChainSummary") or chain_summary_from_elements(target)
    return {
        "changed": source_chain != target_chain,
        "source": source_chain,
        "target": target_chain,
    }


def chain_summary_from_elements(snapshot: dict[str, Any]) -> str:
    return " -> ".join(
        element.get("displayName", "?")
        for element in snapshot.get("signalChainElements", [])
        if not element.get("isReserved")
    )


def block_diff(source: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    source_blocks = {block.get("id"): block for block in source.get("blocks", []) if block.get("id")}
    target_blocks = {block.get("id"): block for block in target.get("blocks", []) if block.get("id")}
    changes = []
    for block_id in sorted(set(source_blocks) | set(target_blocks)):
        source_block = source_blocks.get(block_id)
        target_block = target_blocks.get(block_id)
        if source_block is None or target_block is None:
            changes.append({
                "blockId": block_id,
                "label": (source_block or target_block or {}).get("displayName"),
                "change": "added" if source_block is None else "removed",
            })
            continue
        field_changes = []
        for key, label in [("isEnabled", "on/off"), ("typeName", "type"), ("isInSignalChain", "in chain")]:
            if source_block.get(key) != target_block.get(key):
                field_changes.append({"field": key, "label": label, "source": source_block.get(key), "target": target_block.get(key)})
        if field_changes:
            changes.append({
                "blockId": block_id,
                "label": source_block.get("displayName") or target_block.get("displayName"),
                "changes": field_changes,
            })
    return changes


def controls_diff(source: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        source_controls = controls_from_full(source)["controls"]
        target_controls = controls_from_full(target)["controls"]
    except CLIError:
        return []
    changes = []
    for name in sorted(set(source_controls) | set(target_controls)):
        source_control = source_controls.get(name, {})
        target_control = target_controls.get(name, {})
        field_changes = []
        for key, label in [("preference", "preference"), ("function", "function"), ("mode", "mode")]:
            if source_control.get(key) != target_control.get(key):
                field_changes.append({"field": key, "label": label, "source": source_control.get(key), "target": target_control.get(key)})
        if field_changes:
            changes.append({"control": name, "changes": field_changes})
    return changes


def assigns_diff(source: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    source_assigns = {assign.get("id"): assign for assign in active_assigns_from_snapshot(source) if assign.get("id")}
    target_assigns = {assign.get("id"): assign for assign in active_assigns_from_snapshot(target) if assign.get("id")}
    changes = []
    for assign_id in sorted(set(source_assigns) | set(target_assigns)):
        source_assign = source_assigns.get(assign_id)
        target_assign = target_assigns.get(assign_id)
        if source_assign is None or target_assign is None:
            changes.append({
                "assign": assign_id,
                "change": "added" if source_assign is None else "removed",
                "source": assign_summary(source_assign),
                "target": assign_summary(target_assign),
            })
            continue
        field_changes = []
        for key, label in [("sourceName", "source"), ("targetName", "target"), ("mode", "mode")]:
            if source_assign.get(key) != target_assign.get(key):
                field_changes.append({"field": key, "label": label, "source": source_assign.get(key), "target": target_assign.get(key)})
        if field_changes:
            changes.append({"assign": assign_id, "changes": field_changes})
    return changes


def assign_summary(assign: dict[str, Any] | None) -> str | None:
    if not assign:
        return None
    return f"{assign.get('sourceName')} -> {assign.get('targetName')} ({assign.get('mode')})"


def diff_summary(
    overview_changes: list[dict[str, Any]],
    chain_changes: dict[str, Any],
    block_changes: list[dict[str, Any]],
    control_changes: list[dict[str, Any]],
    assign_changes: list[dict[str, Any]],
) -> list[str]:
    summary = []
    for change in overview_changes:
        summary.append(f"{change['label']}: {change['source']} -> {change['target']}")
    if chain_changes.get("changed"):
        summary.append("Signal chain order or routing changed.")
    for change in block_changes[:8]:
        label = change.get("label") or change.get("blockId")
        fields = ", ".join(item["label"] for item in change.get("changes", []))
        if fields:
            summary.append(f"{label}: {fields} changed.")
        else:
            summary.append(f"{label}: {change.get('change')}.")
    for change in control_changes[:8]:
        fields = ", ".join(item["label"] for item in change.get("changes", []))
        summary.append(f"{change['control']}: {fields} changed.")
    for change in assign_changes[:8]:
        if "changes" in change:
            fields = ", ".join(item["label"] for item in change["changes"])
            summary.append(f"{change['assign']}: {fields} changed.")
        else:
            summary.append(f"{change['assign']}: {change.get('change')}.")
    return summary or ["No decoded musical differences found."]



def read_live_snapshot(timeout: float, requests: list[live.PatchReadRequest] | None = None) -> dict[str, Any]:
    try:
        return live.read_current_patch(timeout=timeout, requests=requests)
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def read_live_snapshot_with_timeout(
    label: str,
    timeout: float,
    requests: list[live.PatchReadRequest] | None = None,
) -> dict[str, Any]:
    source_requests = requests or live.READ_PLAN
    raw = read_patch_records_with_timeout(label, timeout, source_requests)
    return snapshot_from_patch_records(source_requests, source_requests, raw)


def read_performance_snapshot_with_timeout(label: str, timeout: float) -> dict[str, Any]:
    required_requests = performance_required_read_requests()
    assign_requests = assign_read_requests()
    raw = read_required_patch_records_with_timeout(f"{label} required record", timeout, required_requests)
    raw.update(read_patch_records_lenient_with_timeout(f"{label} Assign records", timeout, assign_requests))
    source_requests = required_requests + assign_requests
    return snapshot_from_patch_records(source_requests, source_requests, raw)


def read_user_slot_snapshot(slot: str, timeout: float, *, view: str) -> dict[str, Any]:
    requests = requests_for_view(view)
    try:
        patch_base = live.user_patch_base(slot)
        return read_mapped_patch_snapshot(
            requests=requests,
            patch_base=patch_base,
            timeout=timeout,
            source_slot=live.normalize_user_slot(slot),
            source_type="user",
        )
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def read_user_slot_snapshot_lenient(slot: str, timeout: float, *, view: str) -> dict[str, Any]:
    try:
        source_slot = live.normalize_user_slot(slot)
        patch_base = live.user_patch_base(source_slot)
        return read_mapped_patch_snapshot_lenient(
            requests=requests_for_view(view),
            patch_base=patch_base,
            timeout=timeout,
            source_slot=source_slot,
            source_type="user",
        )
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def read_preset_slot_snapshot(slot: str, timeout: float, *, view: str) -> dict[str, Any]:
    requests = requests_for_view(view)
    try:
        patch_base = live.preset_patch_base(slot)
        return read_mapped_patch_snapshot(
            requests=requests,
            patch_base=patch_base,
            timeout=timeout,
            source_slot=live.normalize_preset_slot(slot),
            source_type="preset",
        )
    except live.LiveMIDIError as error:
        raise CLIError(str(error)) from error


def read_mapped_patch_snapshot(
    *,
    requests: list[live.PatchReadRequest],
    patch_base: list[int],
    timeout: float,
    source_slot: str,
    source_type: str,
) -> dict[str, Any]:
    remapped_requests = [
        live.PatchReadRequest(request.label, live.remap_temporary_patch_address(request.address, patch_base), request.size)
        for request in requests
    ]
    raw = read_patch_records_with_timeout(
        f"patch {source_slot} --live",
        timeout,
        remapped_requests,
    )
    return snapshot_from_patch_records(
        requests,
        remapped_requests,
        raw,
        source_slot=source_slot,
        source_address=patch_base,
        source_type=source_type,
    )


def read_mapped_patch_snapshot_lenient(
    *,
    requests: list[live.PatchReadRequest],
    patch_base: list[int],
    timeout: float,
    source_slot: str,
    source_type: str,
) -> dict[str, Any]:
    remapped_requests = [
        live.PatchReadRequest(request.label, live.remap_temporary_patch_address(request.address, patch_base), request.size)
        for request in requests
    ]
    required_labels = {"Master BPM", "Patch Effect", "Patch Common", "System Control"}
    required_requests = [request for request in remapped_requests if request.label in required_labels]
    optional_requests = [request for request in remapped_requests if request.label not in required_labels]
    read_timeout = min(timeout, 5.0)
    raw: dict[str, list[int]] = {}
    for request in required_requests:
        try:
            raw.update(read_patch_records_with_timeout(
                f"patch {source_slot} --live {request.label}",
                read_timeout,
                [request],
                reader=patch_edit.read_data_sets_sequential_session,
                attempts=1,
            ))
        except CLIError:
            pass
    raw.update(read_patch_records_lenient_chunks(
        f"patch {source_slot} --live optional records",
        min(timeout, 2.0),
        optional_requests,
    ))
    return snapshot_from_patch_records(
        requests,
        remapped_requests,
        raw,
        source_slot=source_slot,
        source_address=patch_base,
        source_type=source_type,
    )


def snapshot_from_patch_records(
    source_requests: list[live.PatchReadRequest],
    remapped_requests: list[live.PatchReadRequest],
    raw: dict[str, list[int]],
    *,
    source_slot: str | None = None,
    source_address: list[int] | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    snapshot = live.empty_snapshot()
    for source_request, remapped_request in zip(source_requests, remapped_requests):
        data = raw.get(live.address_key(remapped_request.address))
        if data is not None:
            live.apply_data_set(snapshot, source_request.address, data)
    if source_slot is not None:
        snapshot["sourceSlot"] = source_slot
    if source_address is not None:
        snapshot["sourceAddress"] = live.hex_bytes(source_address)
    if source_type is not None and source_type != "user":
        snapshot["sourceType"] = source_type
    return snapshot


def read_patch_records_with_timeout(
    label: str,
    timeout: float,
    requests: list[live.PatchReadRequest],
    reader: Callable[..., dict[str, list[int]]] = patch_edit.read_data_sets_batched,
    attempts: int = 3,
) -> dict[str, list[int]]:
    transport_requests = transport_read_requests(requests)
    process_timeout = patch_record_process_timeout(timeout, len(transport_requests))
    for attempt in range(attempts):
        try:
            return live_call_with_timeout(
                label,
                process_timeout,
                reader,
                timeout=timeout,
                requests=transport_requests,
            )
        except CLIError:
            if attempt == attempts - 1:
                raise
            time.sleep(recovery_delay_seconds(attempt))
    raise CLIError(f"{label} failed without returning a result", 1)


def read_patch_records_lenient_with_timeout(
    label: str,
    timeout: float,
    requests: list[live.PatchReadRequest],
) -> dict[str, list[int]]:
    if not requests:
        return {}
    read_timeout = min(timeout, 2.0)
    raw = read_patch_records_lenient_chunks(label, read_timeout, requests)
    missing_requests = [
        request
        for request in requests
        if live.address_key(request.address) not in raw
    ]
    if missing_requests and len(missing_requests) < len(requests):
        retry_timeout = max(timeout, read_timeout)
        raw.update(read_patch_records_lenient_chunks(
            f"{label} missing records retry",
            retry_timeout,
            missing_requests,
        ))
    return raw


def read_patch_records_lenient_chunks(
    label: str,
    timeout: float,
    requests: list[live.PatchReadRequest],
) -> dict[str, list[int]]:
    raw: dict[str, list[int]] = {}
    batch_size = lenient_read_batch_size()
    transport_requests = transport_read_requests(requests)
    for start in range(0, len(transport_requests), batch_size):
        chunk = transport_requests[start:start + batch_size]
        process_timeout = lenient_patch_record_process_timeout(timeout, len(chunk))
        try:
            chunk_raw = live_call_with_timeout(
                label,
                process_timeout,
                live.read_data_sets_lenient,
                timeout=timeout,
                requests=chunk,
            )
        except CLIError:
            break
        raw.update(chunk_raw)
        if not chunk_raw:
            break
    return raw


def transport_read_requests(requests: list[live.PatchReadRequest]) -> list[live.PatchReadRequest]:
    selected: dict[str, live.PatchReadRequest] = {}
    order = []
    for request in requests:
        key = live.address_key(request.address)
        if key not in selected:
            order.append(key)
            selected[key] = request
            continue
        if live.seven_bit_address_value(request.size) > live.seven_bit_address_value(selected[key].size):
            selected[key] = request
    return [selected[key] for key in order]


def read_required_patch_records_with_timeout(
    label: str,
    timeout: float,
    requests: list[live.PatchReadRequest],
) -> dict[str, list[int]]:
    raw: dict[str, list[int]] = {}
    missing_requests = list(requests)
    for attempt in range(required_record_attempts()):
        for request in list(missing_requests):
            try:
                raw.update(read_patch_records_with_timeout(
                    f"{label} {request.label}",
                    timeout,
                    [request],
                    reader=patch_edit.read_data_sets_sequential_session,
                    attempts=1,
                ))
            except CLIError:
                pass
        missing_requests = [
            request
            for request in requests
            if live.address_key(request.address) not in raw
        ]
        if not missing_requests:
            return raw
        time.sleep(recovery_delay_seconds(attempt))
    raw.update(read_patch_records_lenient_with_timeout(f"{label} lenient retry", timeout, missing_requests))
    return raw


def read_clone_records_with_timeout(label: str, timeout: float, slot: str) -> dict[str, list[int]]:
    source = live.normalize_user_slot(slot)
    core_requests = patch_edit.clone_core_read_requests(source)
    required_labels = {"Patch Common", "Patch Effect"}
    required_requests = [
        request
        for request in core_requests
        if request.label in required_labels
    ]
    raw = read_required_patch_records_with_timeout(f"{label} required record", timeout, required_requests)
    missing_required = [
        request.label
        for request in required_requests
        if live.address_key(request.address) not in raw
    ]
    if missing_required:
        raise missing_required_records_error(label, missing_required, timeout)
    optional_core_requests = [
        request
        for request in core_requests
        if request.label not in required_labels
    ]
    raw.update(read_patch_records_lenient_with_timeout(f"{label} core records", timeout, optional_core_requests))
    active_requests = patch_edit.active_fx_algorithm_read_requests(source, raw)
    if active_requests:
        raw.update(read_patch_records_lenient_with_timeout(f"{label} active FX records", timeout, active_requests))
    return raw


def read_clone_snapshot_with_timeout(label: str, timeout: float, slot: str) -> dict[str, Any]:
    source = live.normalize_user_slot(slot)
    raw = read_clone_records_with_timeout(label, timeout, source)
    snapshot = live.empty_snapshot()
    for definition in patch_edit.clone_record_definitions_for_data(source, raw):
        source_address = patch_edit.remap_clone_address(definition.address, source)
        data = raw.get(live.address_key(source_address))
        if data is not None:
            live.apply_data_set(snapshot, definition.address, data)
    snapshot["sourceSlot"] = source
    snapshot["sourceAddress"] = live.hex_bytes(live.user_patch_base(source))
    return snapshot


def delay_between_slot_reads(index: int, total: int) -> None:
    if index >= total - 1:
        return
    delay = float(os.environ.get("GT1000_SLOT_READ_DELAY", "1.0"))
    if delay > 0:
        time.sleep(delay)


def missing_required_records_error(label: str, missing_required: list[str], timeout: float) -> CLIError:
    probe_ok, probe_detail = probe_gt1000_connectivity(min(5.0, max(2.0, timeout / 4.0)))
    missing_text = ", ".join(missing_required)
    if probe_ok:
        return CLIError(
            f"{label} missing required records after recovery attempts: {missing_text}; "
            "GT-1000 connectivity probe passed, so this is a recoverable live-read timeout. Retry the command.",
            1,
        )
    return CLIError(
        f"{label} missing required records after recovery attempts: {missing_text}; "
        f"GT-1000 connectivity probe failed ({probe_detail}). Reconnect or power-cycle the GT-1000; "
        "restart macOS only if CoreMIDI endpoint checks hang or never return.",
        1,
    )


def probe_gt1000_connectivity(timeout: float) -> tuple[bool, str]:
    try:
        ports = live_call_with_timeout("GT-1000 endpoint check", max(3.0, timeout + 1.0), live.list_ports)
    except CLIError as error:
        return False, f"endpoint check failed: {error}"
    destinations = ports.get("destinations", []) if isinstance(ports, dict) else []
    sources = ports.get("sources", []) if isinstance(ports, dict) else []
    has_destination = any(port.get("isDefaultGT1000Endpoint") for port in destinations)
    has_source = any(port.get("isDefaultGT1000Endpoint") for port in sources)
    if not has_destination or not has_source:
        return False, "normal GT-1000 source/destination endpoints are not both present"

    request = live.PatchReadRequest("System Common", live.SYSTEM_COMMON, [0x00, 0x00, 0x00, 0x0D])
    try:
        live_call_with_timeout(
            "GT-1000 system common health check",
            patch_record_process_timeout(timeout, 1),
            live.read_data_sets,
            timeout=timeout,
            requests=[request],
        )
    except CLIError as error:
        return False, f"system common read failed: {error}"
    return True, "normal endpoints and System Common read are responsive"


def patch_record_process_timeout(timeout: float, request_count: int) -> float:
    if request_count <= 0:
        return timeout
    return min(300.0, max(timeout + 5.0, (timeout + 0.25) * request_count + 5.0))


def lenient_patch_record_process_timeout(timeout: float, request_count: int) -> float:
    if request_count <= 0:
        return timeout
    return min(30.0, max(timeout + 2.0, (timeout + 0.1) * request_count + 2.0))


def lenient_read_batch_size() -> int:
    try:
        value = int(os.environ.get("GT1000_LENIENT_READ_BATCH_SIZE", "8"))
    except ValueError:
        return 8
    return max(1, value)


def required_record_attempts() -> int:
    try:
        value = int(os.environ.get("GT1000_REQUIRED_RECORD_ATTEMPTS", "3"))
    except ValueError:
        return 3
    return max(1, value)


def recovery_delay_seconds(attempt: int) -> float:
    return min(2.0, 0.5 * (attempt + 1))


def apply_plan_cli(
    plan: patch_edit.PatchPlan,
    *,
    timeout: float,
    verify: bool,
    create_restore: bool = True,
) -> dict[str, Any]:
    restore_path = create_restore_point(plan, timeout=timeout) if create_restore else None
    try:
        patch_edit.write_data_sets_resilient(plan.writes)
    except live.LiveMIDIError as error:
        raise live.LiveMIDIError(f"write phase failed for {plan.id}: {error}") from error

    result: dict[str, Any] = {
        "plan": plan.id,
        "writeCount": len(plan.writes),
        "verified": None,
        "restorePoint": str(restore_path) if restore_path else None,
    }
    if verify:
        time.sleep(0.25)
        try:
            verification = verify_plan_with_timeout(plan, timeout=timeout)
        except live.LiveMIDIError as error:
            raise live.LiveMIDIError(f"verification phase failed for {plan.id}: {error}") from error
        result["verified"] = verification["ok"]
        result["verification"] = verification
    return result


def create_restore_point(plan: patch_edit.PatchPlan, *, timeout: float) -> Path | None:
    if not plan.writes:
        return None
    requests = unique_restore_read_requests(plan.writes)
    raw = read_patch_records_with_timeout(
        f"restore point {plan.id}",
        timeout,
        requests,
        reader=patch_edit.read_data_sets_sequential_session,
    )
    records = []
    for request in requests:
        key = live.address_key(request.address)
        data = raw.get(key)
        if data is None:
            raise CLIError(f"restore point {plan.id} could not read {request.label} at {key}", 1)
        records.append({
            "label": request.label,
            "address": live.hex_bytes(request.address),
            "size": live.hex_bytes(request.size),
            "dataHex": live.hex_string(data),
        })
    restore = {
        "format": "gt1000-agent-restore-v1",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "plan": plan.id,
        "records": records,
    }
    directory = restore_point_dir()
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}-{safe_restore_plan_id(plan.id)}.json"
    path = directory / filename
    restore_text = json.dumps(restore, indent=2, sort_keys=True) + "\n"
    path.write_text(restore_text, encoding="utf-8")
    latest_restore_point_path().write_text(restore_text, encoding="utf-8")
    return path


def unique_restore_read_requests(writes: list[live.PatchWrite]) -> list[live.PatchReadRequest]:
    requests = []
    seen = set()
    for write in writes:
        request = write.read_request
        key = (tuple(request.address), tuple(request.size))
        if key in seen:
            continue
        seen.add(key)
        requests.append(request)
    return requests


def restore_point_dir() -> Path:
    return Path(os.environ.get("GT1000_RESTORE_DIR", str(Path.home() / ".gt1000-agent" / "restore-points")))


def latest_restore_point_path() -> Path:
    return restore_point_dir() / "latest.json"


def safe_restore_plan_id(plan_id: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in plan_id)
    return safe[:80] or "restore"


def restore_plan_from_data(restore: dict[str, Any]) -> patch_edit.PatchPlan:
    if restore.get("format") != "gt1000-agent-restore-v1":
        raise ValueError("unsupported restore point format")
    records = restore.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("restore point contains no records")
    writes = []
    for record in records:
        label = str(record.get("label") or "Restore record")
        address = bytes_from_hex_list(record.get("address"), "address")
        data = bytes.fromhex(str(record.get("dataHex", "")).replace(" ", ""))
        if not data:
            raise ValueError(f"restore record {label} contains no data")
        writes.append(live.PatchWrite(f"Restore {label}", address, list(data)))
    return patch_edit.PatchPlan(
        id=f"undo-last:{restore.get('plan', 'unknown')}",
        description=f"Restore previous data captured before {restore.get('plan', 'unknown')}.",
        writes=writes,
    )


def bytes_from_hex_list(value: Any, field: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"restore record {field} must be a list")
    try:
        return [int(str(byte), 16) for byte in value]
    except ValueError as error:
        raise ValueError(f"restore record {field} contains invalid hex") from error


def verify_plan_with_timeout(plan: patch_edit.PatchPlan, *, timeout: float) -> dict[str, Any]:
    requests = [write.read_request for write in plan.writes]
    raw = read_patch_records_with_timeout(
        f"verify {plan.id}",
        timeout,
        requests,
        reader=patch_edit.read_data_sets_sequential_session,
    )
    checks = []
    for write in plan.writes:
        key = live.address_key(write.address)
        actual = raw.get(key)
        ok = actual is not None and actual[:len(write.data)] == write.data
        checks.append({
            "label": write.label,
            "address": live.hex_bytes(write.address),
            "ok": ok,
            "expectedHex": live.hex_string(write.data),
            "actualHex": live.hex_string(actual or []),
        })
    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def requests_for_view(view: str) -> list[live.PatchReadRequest]:
    assign_requests = assign_read_requests()
    if view in {"controls", "performance"}:
        return live.INITIAL_READS + assign_requests
    if view in {"chain", "summary"}:
        return live.READ_PLAN + assign_requests
    if view == "overview":
        return live.INITIAL_READS
    return live.READ_PLAN + assign_requests


def performance_required_read_requests() -> list[live.PatchReadRequest]:
    return [
        request
        for request in live.INITIAL_READS
        if request.label in {"Master BPM", "Patch Effect", "Patch Common", "System Control"}
    ]


def assign_read_requests() -> list[live.PatchReadRequest]:
    return [
        live.PatchReadRequest(f"Assign {i}", live.address_adding(live.ASSIGN_BASE, (i - 1) * live.ASSIGN_STRIDE), [0x00, 0x00, 0x00, 0x2C])
        for i in range(1, 17)
    ]


def parameter_schema(parameter: live.Parameter, relative_offset: int) -> dict[str, Any]:
    schema = {
        "id": parameter.id,
        "displayName": parameter.display_name,
        "offset": relative_offset,
        "absoluteOffset": parameter.offset,
        "kind": parameter.kind,
        "byteCount": parameter.byte_count,
        "values": list(parameter.values),
    }
    if parameter.kind == "bool":
        schema["minimum"] = 0
        schema["maximum"] = 1
        schema["values"] = ["off", "on"]
    elif parameter.kind == "type" and parameter.values:
        schema["minimum"] = 0
        schema["maximum"] = len(parameter.values) - 1
    elif parameter.kind in {"byte", "type"}:
        schema["minimum"] = 0
        schema["maximum"] = 127
    elif parameter.kind == "nibbles":
        schema["minimum"] = 0
        schema["maximum"] = (1 << (parameter.byte_count * 4)) - 1
    return schema


def block_schema(block_id: str, *, include_raw: bool = False) -> dict[str, Any]:
    block = patch_edit.find_patch_block(block_id)
    if isinstance(block, live.BlockDefinition):
        address = block.address
        block_type = "effect"
    else:
        address = live.address_adding(live.TEMPORARY_PATCH_EFFECT, block.offset)
        block_type = "resident"
    editable_size = patch_edit.editable_block_size(block)
    named_parameters = [
        parameter_schema(parameter, parameter.offset if isinstance(block, live.BlockDefinition) else parameter.offset - block.offset)
        for parameter in block.parameters
    ]
    named_by_offset = {}
    for parameter in block.parameters:
        relative_offset = parameter.offset if isinstance(block, live.BlockDefinition) else parameter.offset - block.offset
        for offset in range(relative_offset, relative_offset + parameter.byte_count):
            named_by_offset.setdefault(offset, parameter)
    schema = {
        "id": block.id,
        "displayName": block.display_name,
        "type": block_type,
        "chainElementValue": block.chain_element_value,
        "temporaryAddress": live.hex_bytes(address),
        "summarySize": block.size,
        "editableSize": editable_size,
        "namedParameterCount": len(named_parameters),
        "namedParameters": named_parameters,
        "rawEditable": {
            "command": f"patch raw-set {block.id} <offset> <value>",
            "offsetRange": [0, editable_size - 1],
            "widths": ["byte", "nibbles2", "nibbles4"],
        },
    }
    if include_raw:
        schema["rawEditable"]["parameters"] = [
            {
                "id": f"offset{offset}",
                "offset": offset,
                "command": f"patch raw-set {block.id} {offset} <value>",
                "isNamed": offset in named_by_offset,
                "namedParameterId": named_by_offset[offset].id if offset in named_by_offset else None,
            }
            for offset in range(editable_size)
        ]
    return schema


def master_schema() -> dict[str, Any]:
    fields = [
        {
            "id": "level",
            "displayName": "PATCH LEVEL",
            "offset": 0x5F,
            "kind": "nibbles2",
            "byteCount": 2,
            "minimum": 0,
            "maximum": 200,
        },
        {"id": "key", "displayName": "MASTER KEY", "offset": 0x65, "kind": "key", "minimum": 0, "maximum": 11, "values": list(patch_edit.MASTER_KEY_VALUES)},
        {"id": "amp-ctl1", "displayName": "AMP CTL1", "offset": 0x66, "kind": "bool", "minimum": 0, "maximum": 1},
        {"id": "amp-ctl2", "displayName": "AMP CTL2", "offset": 0x67, "kind": "bool", "minimum": 0, "maximum": 1},
        {"id": "carryover", "displayName": "MASTER CARRYOVER", "offset": 0x99, "kind": "bool", "minimum": 0, "maximum": 1},
        {"id": "tempo-hold", "displayName": "CONTROL ASSIGN TEMPO HOLD", "offset": 0x9A, "kind": "bool", "minimum": 0, "maximum": 1},
        {"id": "input-sensitivity", "displayName": "CONTROL ASSIGN INPUT SENS", "offset": 0x9B, "kind": "byte", "minimum": 0, "maximum": 100},
    ]
    return {
        "id": "master",
        "displayName": "PATCH MASTER",
        "type": "patchEffect",
        "temporaryAddress": live.hex_bytes(live.TEMPORARY_PATCH_EFFECT),
        "namedParameterCount": len(fields),
        "namedParameters": fields,
        "command": "patch master-set <field> <value>",
    }


def controls_editor_schema() -> dict[str, Any]:
    return {
        "id": "controls",
        "displayName": "PATCH/SYSTEM CONTROLS",
        "type": "editor",
        "commands": {
            "patch": "patch control-set <control> <function>",
            "system": "patch system-control-set <control> <function>",
            "preference": "patch control-preference-set <control> <patch|system>",
        },
        "controls": sorted(set(patch_edit.PATCH_CONTROL_FIELDS) | set(patch_edit.PATCH_EXP_PEDAL_FIELDS)),
        "switchFunctions": sorted(patch_edit.CONTROL_FUNCTION_VALUES),
        "pedalFunctions": sorted(patch_edit.EXP_PEDAL_FUNCTION_VALUES),
        "modes": ["toggle", "moment"],
        "preferences": ["patch", "system"],
    }


def assign_editor_schema() -> dict[str, Any]:
    return {
        "id": "assign",
        "displayName": "ASSIGN",
        "type": "editor",
        "commands": {
            "decodedCc": "patch assign-cc <number> <block> <parameter> --cc <cc> --mode <toggle|moment>",
            "general": "patch assign-set <number> --target <target> --min <value> --max <value> --source <source> --mode <toggle|moment>",
        },
        "assignRange": [1, 16],
        "targetRange": [0, 16383],
        "logicalValueRange": [0, 16383],
        "activeRange": [0, 16383],
        "midiCcSources": ["cc1...cc31", "cc64...cc95"],
        "sourceAliases": [
            "num1...num5", "cur-num", "bank-down", "bank-up", "ctl1...ctl7",
            "exp1-sw", "exp1", "exp2", "exp3", "internal-pedal", "wave-pedal", "input-level",
        ],
        "targetAliases": ["tuner", "divider1-channel-select", "divider2-channel-select", "divider3-channel-select", "block.parameter"],
        "modes": ["toggle", "moment"],
        "patchMidiFields": {
            "midi-channel": [0, 16],
            "midi-cc": [0, 127],
            "midi-cc-min": [0, 16383],
            "midi-cc-max": [0, 16383],
            "midi-pc": [0, 127],
            "midi-bank-msb": [0, 16383],
            "midi-bank-lsb": [0, 16383],
        },
    }


def led_editor_schema() -> dict[str, Any]:
    off_colors = [name for name, value in patch_edit.LED_COLOR_VALUES.items() if value <= 10]
    return {
        "id": "led",
        "displayName": "PATCH LED",
        "type": "editor",
        "command": "patch led-set <control> <off|on> <color>",
        "temporaryAddress": live.hex_bytes(live.TEMPORARY_PATCH_LED),
        "controls": sorted(patch_edit.PATCH_LED_COLOR_OFFSETS),
        "states": ["off", "on"],
        "offColors": off_colors,
        "onColors": sorted(patch_edit.LED_COLOR_VALUES),
    }


def consecutive_user_slots(start_slot: str, count: int) -> list[str]:
    if count <= 0:
        raise ValueError("count must be positive")
    start = live.normalize_user_slot(start_slot)
    start_index = live.user_patch_zero_based_index(start)
    end_index = start_index + count - 1
    max_index = live.USER_BANK_COUNT * live.USER_PATCHES_PER_BANK - 1
    if end_index > max_index:
        raise ValueError("destination range exceeds U50-5")
    return [slot_from_patch_index("U", index) for index in range(start_index, end_index + 1)]


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
    if view == "performance":
        return performance_from_full(snapshot)
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


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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

    def byte_at(data: bytes, offset: int) -> int | None:
        return data[offset] if 0 <= offset < len(data) else None

    def control_source(preference: str, patch_offset: int) -> tuple[bytes, int]:
        if preference == "SYSTEM":
            return system_control, patch_offset - 0x23
        return patch_common, patch_offset
    
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
        preference = "SYSTEM" if byte_at(system_control, system_pref_offset) == 1 else "PATCH"
        source, source_offset = control_source(preference, patch_offset)
        func_byte = byte_at(source, source_offset)
        mode_byte = byte_at(source, source_offset + 1)
        if func_byte is None:
            continue
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
        preference = "SYSTEM" if byte_at(system_control, system_pref_offset) == 1 else "PATCH"
        source, source_offset = control_source(preference, patch_offset)
        func_byte = byte_at(source, source_offset)
        if func_byte is None:
            continue
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
    block = next((item for item in list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) if item.id == block_id), None)
    if block is None:
        return []
    by_id = {parameter.id: (parameter.id, parameter.display_name) for parameter in block.parameters}
    if block_id.startswith("eq"):
        return [
            by_id[parameter_id]
            for parameter_id in [
                "sw", "type", "lowGain", "highGain", "lowMidFreq", "lowMidQ", "lowMidGain",
                "highMidFreq", "highMidQ", "highMidGain", "level", "lowCut", "highCut",
                "geq31_5Hz", "geq63Hz", "geq125Hz", "geq250Hz", "geq500Hz", "geq1kHz",
                "geq2kHz", "geq4kHz", "geq8kHz", "geq16kHz", "geqLevel",
            ]
        ]
    if block_id == "masterDelay":
        return [
            by_id[parameter_id]
            for parameter_id in [
                "sw", "type", "time", "feedback", "highCut", "effectLevel", "directLevel", "modRate",
                "modDepth", "duckSens", "duckPreDepth", "duckPostDepth", "head", "pitch", "pitchBal",
                "pitchFeedback", "dualMode", "d1Type", "d1Time", "d1Feedback", "d1HighCut",
                "d1EffectLevel", "d2Type", "d2Time", "d2Feedback", "d2HighCut", "d2EffectLevel",
                "trigger", "twistMode", "riseTime", "fallTime", "level",
            ]
        ]
    if block_id == "reverb":
        return [
            by_id[parameter_id]
            for parameter_id in [
                "sw", "type", "time", "tone", "density", "preDelay", "lowCut", "highCut",
                "lowDamp", "highDamp", "modRate", "modDepth", "duckSens", "duckPreDepth",
                "duckPostDepth", "effectLevel", "directLevel", "pitch1", "level1", "pitch2",
                "level2", "type1", "time1", "preDelay1", "density1", "tone1", "lowCut1",
                "highCut1", "effectLevel1", "type2", "time2", "preDelay2", "density2", "tone2",
                "lowCut2", "highCut2", "effectLevel2",
            ]
        ]
    if block_id == "pedalFx":
        return [
            by_id[parameter_id]
            for parameter_id in [
                "sw", "type", "pitch", "effectLevel", "directMix", "wahType", "pedalMin",
                "pedalMax", "wahPedalPosition", "pedalBendPedalPosition",
            ]
        ]
    by_offset = {parameter.offset: (parameter.id, parameter.display_name) for parameter in block.parameters}
    return [by_offset.get(offset, (f"param{offset}", f"PARAM {offset}")) for offset in range(block.size)]


FX_ASSIGN_ORDERS = {
    "AGSim": ["body", "low", "high", "level"],
    "AcReso": ["type", "resonance", "tone", "level"],
    "AWah": ["filterMode", "rate", "depth", "frequency", "resonance", "waveform", "effectLevel", "directMix"],
    "Chorus": [
        "type", "rate", "depth", "preDelay", "waveform", "lowCut", "highCut", "effectLevel", "directLevel",
        "rate1", "depth1", "preDelay1", "waveform1", "lowCut1", "highCut1", "effectLevel1",
        "rate2", "depth2", "preDelay2", "waveform2", "lowCut2", "highCut2", "effectLevel2",
        "outputMode", "sweetness", "bell", "preampSw", "preampGain", "preampLevel",
    ],
    "CVibe": ["mode", "rate", "depth", "effectLevel"],
    "Comp": ["type", "sustain", "attack", "tone", "ratio", "level", "directMix"],
    "Defretter": ["sens", "depth", "tone", "attack", "resonance", "effectLevel", "directMix"],
    "Feedbacker": ["mode", "trigger", "depth", "riseTime", "octRiseTime", "feedback", "octFeedback", "vibRate", "vibDepth"],
    "Flanger": [
        "rate", "depth", "resonance", "manual", "turbo", "waveform", "stepRate", "separation",
        "lowDamp", "highDamp", "lowCut", "highCut", "effectLevel", "directMix",
    ],
    "Harmonist": [
        "voice", "hr1Harmony", "hr1PreDelay", "hr1Feedback", "hr1Level",
        "hr2Harmony", "hr2PreDelay", "hr2Level", "directLevel",
    ],
    "Humanizer": ["mode", "vowel1", "vowel2", "sens", "rate", "depth", "manual", "level"],
    "Octave": ["type", "minus2oct", "minus1oct", "directLevel", "range", "octaveLevel"],
    "Overtone": ["lowerLevel", "upperLevel", "unisonLevel", "directLevel", "detune", "low", "high", "outputMode"],
    "Pan": ["rate", "depth", "waveform", "effectLevel", "directMix"],
    "Phaser": [
        "type", "stage", "rate", "depth", "resonance", "manual", "waveform", "stepRate",
        "biPhase", "separation", "lowDamp", "highDamp", "lowCut", "highCut", "effectLevel", "directMix",
    ],
    "PitchShift": [
        "voice", "ps1Pitch", "ps1Mode", "ps1Fine", "ps1PreDelay", "ps1Feedback", "ps1Level",
        "ps2Pitch", "ps2Mode", "ps2Fine", "ps2PreDelay", "ps2Level", "directLevel",
    ],
    "RingMod": ["intelligent", "frequency", "freqModRate", "freqModDepth", "effectLevel", "directMix"],
    "Rotary": ["speedSelect", "slowRate", "fastRate", "riseTime", "fallTime", "micDistance", "rotorHorn", "drive", "effectLevel", "directMix"],
    "SitarSim": ["sens", "depth", "tone", "resonance", "buzz", "effectLevel", "directMix"],
    "Slicer": ["pattern", "rate", "trigger", "attack", "duty", "effectLevel", "directMix"],
    "SlowGear": ["sens", "riseTime", "level"],
    "SoundHold": ["trigger", "riseTime", "effectLevel"],
    "SBend": ["trigger", "pitch", "riseTime", "fallTime"],
    "Tremolo": ["rate", "depth", "waveform", "trigger", "riseTime", "effectLevel", "directMix"],
    "TWah": ["filterMode", "polarity", "sens", "frequency", "resonance", "decay", "effectLevel", "directMix"],
    "Vibrato": ["rate", "depth", "color", "trigger", "riseTime", "effectLevel", "directMix"],
}

FX_ASSIGN_STARTS = {
    "AGSim": 240, "AcReso": 244, "AWah": 248, "Chorus": 256, "CVibe": 285, "Comp": 289,
    "Defretter": 296, "Feedbacker": 303, "Flanger": 312, "Harmonist": 326, "Humanizer": 335,
    "Octave": 343, "Overtone": 349, "Pan": 357, "Phaser": 362, "PitchShift": 378,
    "RingMod": 391, "Rotary": 397, "SitarSim": 407, "Slicer": 414, "SlowGear": 421,
    "SoundHold": 424, "SBend": 427, "Tremolo": 431, "TWah": 438, "Vibrato": 446,
}


def fx_algorithm_assign_ranges() -> list[dict[str, Any]]:
    ranges = []
    for fx_number, target_offset in [(1, 0), (2, 215), (3, 430), (4, 937)]:
        for suffix, start in FX_ASSIGN_STARTS.items():
            block_id = f"fx{fx_number}{suffix}"
            by_id = {parameter_id: (parameter_id, name) for parameter_id, name in block_parameter_names(block_id)}
            parameters = [by_id[parameter_id] for parameter_id in FX_ASSIGN_ORDERS[suffix] if parameter_id in by_id]
            ranges.append({
                "start": start + target_offset,
                "category": f"FX {fx_number} {suffix}",
                "blockId": block_id,
                "parameters": parameters,
            })
    return ranges


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
    *fx_algorithm_assign_ranges(),
    {"start": 1175, "category": "FX 4", "blockId": "fx4", "parameters": block_parameter_names("fx4")},
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
