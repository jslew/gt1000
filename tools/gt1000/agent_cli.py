#!/usr/bin/env python3
"""Agent-facing GT-1000 CLI.

This Python layer owns command ergonomics and offline JSON shaping. Live MIDI
I/O remains in the Swift backend because it already has tested CoreMIDI code.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SWIFT_CLI = ROOT / "scripts" / "gt1000-cli.sh"


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
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr.rstrip(), file=sys.stderr)
        else:
            print(f"error: live backend failed with exit code {error.returncode}", file=sys.stderr)
        return error.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gt1000-agent",
        description="Agent-facing GT-1000 patch inspection CLI.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    subcommands = parser.add_subparsers(dest="command", required=True)

    ports = subcommands.add_parser("ports", help="List live MIDI ports using the Swift backend.")
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
    dump.add_argument("--live", action="store_true", help="Read live patch data from the Swift backend.")
    dump.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")
    dump.add_argument("--output", type=Path, help="Write JSON dump to this file instead of stdout.")
    dump.set_defaults(func=cmd_patch_dump)

    inspect = patch_subcommands.add_parser("inspect", help="Inspect a saved full patch JSON dump.")
    inspect.add_argument("file", type=Path, help="Saved full patch JSON file.")
    inspect.add_argument("--view", choices=["overview", "chain", "full"], default="overview")
    inspect.set_defaults(func=cmd_patch_inspect)

    return parser


def add_input_options(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--live", action="store_true", help="Read live patch data from the Swift backend.")
    source.add_argument("--file", type=Path, help="Inspect a saved full patch JSON dump.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Live read timeout in seconds.")


def cmd_ports(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("ports requires --live because MIDI ports are live device state", 64)
    return run_swift_json(["list-ports"])


def patch_view(args: argparse.Namespace, view: str) -> Any:
    if args.live or args.file is None:
        return run_swift_json(["read", "current-patch", "--view", view], timeout=args.timeout)

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
        command = ["read", "current-patch", "--view", "block"]
        if args.position is not None:
            command += ["--position", str(args.position)]
        else:
            command += ["--block", args.block_id]
        return run_swift_json(command, timeout=args.timeout)

    snapshot = load_json(args.file)
    if args.position is not None:
        block = block_for_position(snapshot, args.position)
    else:
        block = block_for_id(snapshot, args.block_id)
    return block_detail_from_full(snapshot, block)


def cmd_patch_dump(args: argparse.Namespace) -> Any:
    if not args.live:
        raise CLIError("patch dump currently requires --live", 64)

    dump = run_swift_json(["read", "current-patch", "--view", "full"], timeout=args.timeout)
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


def run_swift_json(command: list[str], timeout: float | None = None) -> Any:
    if not SWIFT_CLI.exists():
        raise CLIError(f"Swift live backend not found at {SWIFT_CLI}", 69)

    full_command = [str(SWIFT_CLI)] + command + ["--format", "json"]
    if timeout is not None:
        full_command += ["--timeout", str(timeout)]

    completed = subprocess.run(
        full_command,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


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
        block.get("chainElementValue"): block.get("id")
        for block in blocks
        if block.get("chainElementValue") is not None
    }
    elements = [
        {
            "id": element.get("id"),
            "position": element.get("position"),
            "displayName": element.get("displayName"),
            "detailBlockID": detail_by_value.get(element.get("rawValue")),
            "isReserved": element.get("isReserved", False),
            "isOutput": element.get("isOutput", False),
        }
        for element in snapshot.get("signalChainElements", [])
    ]
    return {
        "overview": overview_from_full(snapshot),
        "signalChainSummary": " -> ".join(
            element["displayName"] for element in elements if element.get("displayName")
        ),
        "elements": elements,
    }


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
