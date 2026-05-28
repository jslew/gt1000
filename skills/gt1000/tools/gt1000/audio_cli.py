"""CLI handlers for GT-1000 audio lab commands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

try:
    from tools.gt1000.audio_lab.commands import (
        cmd_analyze,
        cmd_generate_tone,
        cmd_ports,
        cmd_record_dry,
        cmd_reamp,
    )
    from tools.gt1000.audio_lab.errors import AudioLabError
except ModuleNotFoundError:
    from audio_lab.commands import cmd_analyze, cmd_generate_tone, cmd_ports, cmd_record_dry, cmd_reamp
    from audio_lab.errors import AudioLabError


def audio_environment_block_reason() -> str | None:
    if sys.platform != "darwin":
        return "audio lab Phase 1 capture is implemented for macOS only"
    sandbox = (os.environ.get("CODEX_SANDBOX") or os.environ.get("SANDBOX_MODE") or "").strip().lower()
    if sandbox and sandbox not in {"0", "false", "none", "off", "disabled", "danger-full-access"}:
        return f"{sandbox} sandbox is active"
    return None


def assert_audio_environment() -> None:
    reason = audio_environment_block_reason()
    if reason is None:
        return
    raise AudioLabError(
        f"GT-1000 audio capture is blocked in the current environment: {reason}. "
        "Run from a full-access shell on macOS with ffmpeg installed.",
        77,
    )


def wrap_audio_command(func, *, requires_device: bool = False):
    def runner(args: argparse.Namespace) -> Any:
        if requires_device:
            assert_audio_environment()
        return func(args)

    return runner


def register_audio_commands(subcommands: argparse._SubParsersAction) -> None:
    audio = subcommands.add_parser("audio", help="USB audio capture, re-amp, and analysis.")
    audio_sub = audio.add_subparsers(dest="audio_command", required=True)

    ports = audio_sub.add_parser("ports", help="List Core Audio / ffmpeg devices for GT-1000 USB audio.")
    ports.set_defaults(func=wrap_audio_command(cmd_audio_ports))

    generate = audio_sub.add_parser("generate-tone", help="Write a test-tone dry.wav into a session (offline).")
    generate.add_argument("--session", required=True, help="Session name under GT1000_SESSION_DIR.")
    generate.add_argument("--duration", type=float, default=3.0, help="Tone duration in seconds.")
    generate.add_argument("--frequency", type=float, default=440.0, help="Sine frequency in Hz.")
    generate.add_argument("--amplitude", type=float, default=0.25, help="Peak amplitude 0..1.")
    generate.add_argument("--sample-rate", type=int, default=44100, help="Sample rate, default 44100.")
    generate.set_defaults(func=wrap_audio_command(cmd_audio_generate_tone))

    record = audio_sub.add_parser("record-dry", help="Capture USB dry channels 3-4 into a session.")
    record.add_argument("--session", required=True, help="Session name.")
    record.add_argument("--duration", type=float, default=5.0, help="Capture duration in seconds.")
    record.add_argument("--sample-rate", type=int, default=44100, help="Sample rate, default 44100.")
    record.add_argument("--device-index", type=int, help="avfoundation input index override.")
    record.set_defaults(func=wrap_audio_command(cmd_audio_record_dry, requires_device=True))

    reamp = audio_sub.add_parser("reamp", help="Play session dry.wav to GT-1000 and capture main USB 1-2.")
    reamp.add_argument("--session", required=True, help="Session name.")
    reamp.add_argument("--input", type=Path, help="Override dry WAV path.")
    reamp.add_argument("--output", type=Path, help="Override wet WAV path.")
    reamp.add_argument(
        "--playback-role",
        choices=["dry", "main"],
        default="dry",
        help="Playback routing hint; Phase 1 still captures processed main 1-2.",
    )
    reamp.set_defaults(func=wrap_audio_command(cmd_audio_reamp, requires_device=True))

    analyze = audio_sub.add_parser("analyze", help="Analyze one or more WAV files.")
    analyze.add_argument("files", nargs="+", type=Path, help="WAV files to analyze.")
    analyze.set_defaults(func=wrap_audio_command(cmd_audio_analyze))


def cmd_audio_ports(_args: argparse.Namespace) -> Any:
    return cmd_ports()


def cmd_audio_generate_tone(args: argparse.Namespace) -> Any:
    return cmd_generate_tone(
        args.session,
        duration=args.duration,
        frequency=args.frequency,
        amplitude=args.amplitude,
        sample_rate=args.sample_rate,
    )


def cmd_audio_record_dry(args: argparse.Namespace) -> Any:
    return cmd_record_dry(
        args.session,
        duration=args.duration,
        sample_rate=args.sample_rate,
        device_index=args.device_index,
    )


def cmd_audio_reamp(args: argparse.Namespace) -> Any:
    return cmd_reamp(
        args.session,
        input_path=args.input,
        output_path=args.output,
        playback_role=args.playback_role,
    )


def cmd_audio_analyze(args: argparse.Namespace) -> Any:
    return cmd_analyze(list(args.files))
