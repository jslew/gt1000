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
        cmd_probe,
        cmd_record_dry,
        cmd_reamp,
        cmd_compare_branches,
        cmd_branch_context,
        cmd_probe_param,
        cmd_probe_branch,
        cmd_reference_analyze,
        cmd_match_reference,
        cmd_render_branch,
        cmd_analyze_trimmed,
        cmd_session_init,
        cmd_session_render,
    )
    from tools.gt1000.audio_lab.errors import AudioLabError
except ModuleNotFoundError:
    from audio_lab.commands import (
        cmd_analyze,
        cmd_generate_tone,
        cmd_ports,
        cmd_probe,
        cmd_record_dry,
        cmd_reamp,
        cmd_compare_branches,
        cmd_branch_context,
        cmd_probe_param,
        cmd_probe_branch,
        cmd_reference_analyze,
        cmd_match_reference,
        cmd_render_branch,
        cmd_analyze_trimmed,
        cmd_session_init,
        cmd_session_render,
    )
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
        "Run from a full-access shell on macOS with sounddevice and numpy installed.",
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

    ports = audio_sub.add_parser("ports", help="List PortAudio (sounddevice) devices for GT-1000 USB audio.")
    ports.set_defaults(func=wrap_audio_command(cmd_audio_ports))

    generate = audio_sub.add_parser("generate-tone", help="Write a test-tone dry.wav into a session (offline).")
    generate.add_argument("--session", required=True, help="Session name under GT1000_SESSION_DIR.")
    generate.add_argument("--duration", type=float, default=3.0, help="Tone duration in seconds.")
    generate.add_argument("--frequency", type=float, default=440.0, help="Sine frequency in Hz.")
    generate.add_argument("--amplitude", type=float, default=0.25, help="Peak amplitude 0..1.")
    generate.add_argument("--sample-rate", type=int, default=44100, help="Sample rate, default 44100.")
    generate.set_defaults(func=wrap_audio_command(cmd_audio_generate_tone))

    probe = audio_sub.add_parser(
        "probe",
        help="Capture ~3s from GT-1000 USB and report per-channel peaks (diagnostic).",
    )
    probe.add_argument("--duration", type=float, default=3.0, help="Capture duration in seconds.")
    probe.add_argument("--sample-rate", type=int, default=44100, help="Sample rate, default 44100.")
    probe.add_argument("--device-index", type=int, help="PortAudio input index (see audio ports → gt1000Inputs).")
    probe.set_defaults(func=wrap_audio_command(cmd_audio_probe, requires_device=True))

    record = audio_sub.add_parser(
        "record-dry",
        help="Capture GT-1000 USB audio into a session (default: dry 3-4; optional main 1-2).",
    )
    record.add_argument("--session", required=True, help="Session name.")
    record.add_argument("--duration", type=float, default=5.0, help="Capture duration in seconds.")
    record.add_argument("--sample-rate", type=int, default=44100, help="Sample rate, default 44100.")
    record.add_argument("--device-index", type=int, help="PortAudio input index (see audio ports → gt1000Inputs).")
    record.add_argument(
        "--bus",
        choices=["dry", "main", "both"],
        default="dry",
        help="USB bus to extract: dry=3-4, main=1-2 (wet), both.",
    )
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
    reamp.add_argument(
        "--no-prepare-usb",
        action="store_true",
        help="Skip SetupEfct SysEx that sets USB MAIN/SUB DIR MON OFF before playback.",
    )
    reamp.add_argument("--midi-timeout", type=float, default=8.0, help="SysEx timeout for USB prepare.")
    reamp.set_defaults(func=wrap_audio_command(cmd_audio_reamp, requires_device=True))

    prepare = audio_sub.add_parser(
        "prepare-reamp",
        help="Set SetupEfct USB DIR MON OFF via SysEx (required for computer re-amp).",
    )
    prepare.add_argument("--midi-timeout", type=float, default=8.0)
    prepare.set_defaults(func=wrap_audio_command(cmd_audio_prepare_reamp, requires_device=True))

    analyze = audio_sub.add_parser("analyze", help="Analyze one or more WAV files.")
    analyze.add_argument("files", nargs="+", type=Path, help="WAV files to analyze.")
    analyze.set_defaults(func=wrap_audio_command(cmd_audio_analyze))

    analyze_trim = audio_sub.add_parser(
        "analyze-trimmed",
        help="Analyze WAV RMS/peak on a trimmed middle region (skip re-amp settle/tail).",
    )
    analyze_trim.add_argument("files", nargs="+", type=Path, help="WAV files to analyze.")
    analyze_trim.add_argument("--trim-start", type=float, default=2.0, dest="trim_start_seconds")
    analyze_trim.add_argument("--trim-end", type=float, default=1.5, dest="trim_end_seconds")
    analyze_trim.set_defaults(func=wrap_audio_command(cmd_audio_analyze_trimmed))

    reference = audio_sub.add_parser("reference", help="Analyze reference guitar tones for Phase 4 scoring.")
    reference_sub = reference.add_subparsers(dest="reference_command", required=True)
    reference_analyze = reference_sub.add_parser(
        "analyze",
        help="Build a reference-profile JSON file from an isolated reference WAV.",
    )
    reference_analyze.add_argument("file", type=Path, help="Reference WAV file.")
    reference_analyze.add_argument("--output", type=Path, help="Profile JSON output path.")
    reference_analyze.add_argument("--trim-start", type=float, default=0.0, dest="trim_start_seconds")
    reference_analyze.add_argument("--trim-end", type=float, default=0.0, dest="trim_end_seconds")
    reference_analyze.set_defaults(func=wrap_audio_command(cmd_audio_reference_analyze))

    match_reference = audio_sub.add_parser(
        "match-reference",
        help="Score one or more wet WAVs against a stored reference profile.",
    )
    match_reference.add_argument("profile", type=Path, help="Reference profile JSON from audio reference analyze.")
    match_reference.add_argument("files", nargs="+", type=Path, help="Candidate wet WAV files to rank.")
    match_reference.add_argument("--trim-start", type=float, default=0.0, dest="trim_start_seconds")
    match_reference.add_argument("--trim-end", type=float, default=0.0, dest="trim_end_seconds")
    match_reference.add_argument("--band-weight", type=float, default=1.0)
    match_reference.add_argument("--rms-weight", type=float, default=0.05)
    match_reference.set_defaults(func=wrap_audio_command(cmd_audio_match_reference))

    session = audio_sub.add_parser("session", help="Initialize and render repeatable audio lab sessions.")
    session_sub = session.add_subparsers(dest="session_command", required=True)

    session_init = session_sub.add_parser(
        "init",
        help="Create a session directory; optionally snapshot live system IN/OUT and patch state.",
    )
    session_init.add_argument("--session", required=True, help="Session name under GT1000_SESSION_DIR.")
    session_init.add_argument(
        "--live",
        action="store_true",
        help="Read system IN/OUT, SetupEfct, and temporary patch summary over MIDI.",
    )
    session_init.add_argument("--midi-timeout", type=float, default=20.0, help="MIDI timeout for --live snapshots.")
    session_init.set_defaults(func=wrap_audio_command(cmd_audio_session_init))

    session_render = session_sub.add_parser(
        "render",
        help="Re-amp session dry.wav to renders/<label>-wet.wav with patch snapshot metadata.",
    )
    session_render.add_argument("--session", required=True, help="Session name.")
    session_render.add_argument("--label", required=True, help="Render label (used in output filenames).")
    session_render.add_argument(
        "--playback-role",
        choices=["dry", "main"],
        default="dry",
        help="USB playback routing hint for dry.wav.",
    )
    session_render.add_argument(
        "--no-prepare-usb",
        action="store_true",
        help="Skip SetupEfct SysEx that sets USB DIR MON OFF before playback.",
    )
    session_render.add_argument("--midi-timeout", type=float, default=8.0, help="SysEx timeout for USB prepare and patch snapshot.")
    session_render.add_argument(
        "--settle-seconds",
        type=float,
        default=0.25,
        help="Delay after patch writes before re-amp capture (default 0.25).",
    )
    session_render.add_argument(
        "--no-patch-snapshot",
        action="store_true",
        help="Skip MIDI patch snapshot before render (useful when chaining renders in separate CLI processes).",
    )
    session_render.set_defaults(func=wrap_audio_command(cmd_audio_session_render, requires_device=True))

    compare = audio_sub.add_parser(
        "compare-branches",
        help="Re-amp dry take on divider channel A and B; report loudness delta.",
    )
    compare.add_argument("--session", required=True, help="Session name with dry.wav.")
    compare.add_argument("--divider", default="divider1", choices=["divider1", "divider2", "divider3"])
    compare.add_argument("--midi-timeout", type=float, default=20.0)
    compare.add_argument("--settle-seconds", type=float, default=0.25)
    compare.add_argument("--no-verify", action="store_true", help="Skip SysEx read-back verification on divider writes.")
    compare.add_argument(
        "--no-prepare-usb",
        action="store_true",
        help="Skip SetupEfct DIR MON prepare (use after audio prepare-reamp).",
    )
    compare.add_argument("--user-slot", help="Optional user slot for persistent divider writes (default: temporary patch).")
    compare.set_defaults(func=wrap_audio_command(cmd_audio_compare_branches, requires_device=True))

    branch_ctx = audio_sub.add_parser(
        "branch-context",
        help="Inspect divider branches and gain candidates for agent-led experiments (no re-amp).",
    )
    branch_ctx.add_argument("--divider", default="divider1", choices=["divider1", "divider2", "divider3"])
    branch_ctx.add_argument("--midi-timeout", type=float, default=20.0)
    branch_ctx.set_defaults(func=wrap_audio_command(cmd_audio_branch_context, requires_device=True))

    probe_param_cmd = audio_sub.add_parser(
        "probe-param",
        help="Test whether a patch parameter moves USB re-amp level on one divider branch.",
    )
    probe_param_cmd.add_argument("--session", required=True, help="Session name with dry.wav.")
    probe_param_cmd.add_argument("--divider", default="divider1", choices=["divider1", "divider2", "divider3"])
    probe_param_cmd.add_argument(
        "--channel",
        required=True,
        help="branch-A, branch-B, 0, or 1 (active divider path to render).",
    )
    probe_param_cmd.add_argument("--block", required=True, dest="block_id", help="Block id (e.g. dist1, divider1).")
    probe_param_cmd.add_argument("--param", required=True, dest="parameter_id", help="Parameter id (e.g. level, levelB).")
    probe_param_cmd.add_argument("--low", type=int, default=0, dest="low_value")
    probe_param_cmd.add_argument("--high", type=int, default=100, dest="high_value")
    probe_param_cmd.add_argument("--midi-timeout", type=float, default=20.0)
    probe_param_cmd.add_argument("--settle-seconds", type=float, default=0.25)
    probe_param_cmd.add_argument(
        "--no-prepare-usb",
        action="store_true",
        help="Skip SetupEfct DIR MON prepare (use after audio prepare-reamp).",
    )
    probe_param_cmd.set_defaults(func=wrap_audio_command(cmd_audio_probe_param, requires_device=True))

    probe_branch_cmd = audio_sub.add_parser(
        "probe-branch",
        help="Screen branch blocks: probe each candidate param and rank USB level sensitivity.",
    )
    probe_branch_cmd.add_argument("--session", required=True)
    probe_branch_cmd.add_argument("--divider", default="divider1", choices=["divider1", "divider2", "divider3"])
    probe_branch_cmd.add_argument("--channel", required=True)
    probe_branch_cmd.add_argument("--max-probes", type=int, default=6)
    probe_branch_cmd.add_argument("--include-divider-levels", action="store_true")
    probe_branch_cmd.add_argument("--low", type=int, default=0, dest="low_value")
    probe_branch_cmd.add_argument("--high", type=int, default=100, dest="high_value")
    probe_branch_cmd.add_argument("--midi-timeout", type=float, default=20.0)
    probe_branch_cmd.add_argument("--settle-seconds", type=float, default=0.25)
    probe_branch_cmd.add_argument("--no-prepare-usb", action="store_true")
    probe_branch_cmd.set_defaults(func=wrap_audio_command(cmd_audio_probe_branch, requires_device=True))

    render_branch_cmd = audio_sub.add_parser(
        "render-branch",
        help="Select divider channel, re-amp dry.wav once, return wet metrics (restores divider by default).",
    )
    render_branch_cmd.add_argument("--session", required=True)
    render_branch_cmd.add_argument("--divider", default="divider1", choices=["divider1", "divider2", "divider3"])
    render_branch_cmd.add_argument("--channel", required=True)
    render_branch_cmd.add_argument("--label", help="Render label (default: dividerN-branch-A|B).")
    render_branch_cmd.add_argument("--trim-start", type=float, default=0.0, dest="trim_start_seconds")
    render_branch_cmd.add_argument("--trim-end", type=float, default=0.0, dest="trim_end_seconds")
    render_branch_cmd.add_argument("--midi-timeout", type=float, default=20.0)
    render_branch_cmd.add_argument("--settle-seconds", type=float, default=0.25)
    render_branch_cmd.add_argument("--no-verify", action="store_true")
    render_branch_cmd.add_argument("--no-prepare-usb", action="store_true")
    render_branch_cmd.add_argument("--no-restore-divider", action="store_true")
    render_branch_cmd.add_argument("--user-slot")
    render_branch_cmd.add_argument("--experiment-note", help="Append this note to session meta events.")
    render_branch_cmd.set_defaults(func=wrap_audio_command(cmd_audio_render_branch, requires_device=True))


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


def cmd_audio_probe(args: argparse.Namespace) -> Any:
    return cmd_probe(
        duration=args.duration,
        sample_rate=args.sample_rate,
        device_index=args.device_index,
    )


def cmd_audio_record_dry(args: argparse.Namespace) -> Any:
    return cmd_record_dry(
        args.session,
        duration=args.duration,
        sample_rate=args.sample_rate,
        device_index=args.device_index,
        bus=args.bus,
    )


def cmd_audio_reamp(args: argparse.Namespace) -> Any:
    return cmd_reamp(
        args.session,
        input_path=args.input,
        output_path=args.output,
        playback_role=args.playback_role,
        prepare_usb=not args.no_prepare_usb,
        midi_timeout=args.midi_timeout,
    )


def cmd_audio_prepare_reamp(args: argparse.Namespace) -> Any:
    try:
        from tools.gt1000.audio_lab.setup_efct import prepare_usb_reamp
    except ModuleNotFoundError:
        from audio_lab.setup_efct import prepare_usb_reamp

    return prepare_usb_reamp(args.midi_timeout, verify=True)


def cmd_audio_analyze(args: argparse.Namespace) -> Any:
    return cmd_analyze(list(args.files))


def cmd_audio_reference_analyze(args: argparse.Namespace) -> Any:
    return cmd_reference_analyze(
        args.file,
        output_path=args.output,
        trim_start_seconds=args.trim_start_seconds,
        trim_end_seconds=args.trim_end_seconds,
    )


def cmd_audio_match_reference(args: argparse.Namespace) -> Any:
    return cmd_match_reference(
        args.profile,
        list(args.files),
        trim_start_seconds=args.trim_start_seconds,
        trim_end_seconds=args.trim_end_seconds,
        band_weight=args.band_weight,
        rms_weight=args.rms_weight,
    )


def cmd_audio_session_init(args: argparse.Namespace) -> Any:
    return cmd_session_init(args.session, live=args.live, midi_timeout=args.midi_timeout)


def cmd_audio_session_render(args: argparse.Namespace) -> Any:
    return cmd_session_render(
        args.session,
        args.label,
        prepare_usb=not args.no_prepare_usb,
        midi_timeout=args.midi_timeout,
        playback_role=args.playback_role,
        settle_seconds=args.settle_seconds,
        snapshot_patch=not args.no_patch_snapshot,
    )


def cmd_audio_compare_branches(args: argparse.Namespace) -> Any:
    return cmd_compare_branches(
        args.session,
        args.divider,
        midi_timeout=args.midi_timeout,
        settle_seconds=args.settle_seconds,
        verify_writes=not args.no_verify,
        prepare_usb=not args.no_prepare_usb,
        user_slot=args.user_slot,
    )


def cmd_audio_branch_context(args: argparse.Namespace) -> Any:
    return cmd_branch_context(args.divider, midi_timeout=args.midi_timeout)


def cmd_audio_probe_param(args: argparse.Namespace) -> Any:
    return cmd_probe_param(
        args.session,
        args.divider,
        args.channel,
        args.block_id,
        args.parameter_id,
        low_value=args.low_value,
        high_value=args.high_value,
        midi_timeout=args.midi_timeout,
        settle_seconds=args.settle_seconds,
        prepare_usb=not args.no_prepare_usb,
    )


def cmd_audio_probe_branch(args: argparse.Namespace) -> Any:
    return cmd_probe_branch(
        args.session,
        args.divider,
        args.channel,
        max_probes=args.max_probes,
        include_divider_levels=args.include_divider_levels,
        low_value=args.low_value,
        high_value=args.high_value,
        midi_timeout=args.midi_timeout,
        settle_seconds=args.settle_seconds,
        prepare_usb=not args.no_prepare_usb,
    )


def cmd_audio_render_branch(args: argparse.Namespace) -> Any:
    return cmd_render_branch(
        args.session,
        args.divider,
        args.channel,
        label=args.label,
        midi_timeout=args.midi_timeout,
        settle_seconds=args.settle_seconds,
        verify_writes=not args.no_verify,
        prepare_usb=not args.no_prepare_usb,
        restore_divider=not args.no_restore_divider,
        trim_start_seconds=args.trim_start_seconds,
        trim_end_seconds=args.trim_end_seconds,
        user_slot=args.user_slot,
        experiment_note=args.experiment_note,
    )


def cmd_audio_analyze_trimmed(args: argparse.Namespace) -> Any:
    return cmd_analyze_trimmed(
        list(args.files),
        trim_start_seconds=args.trim_start_seconds,
        trim_end_seconds=args.trim_end_seconds,
    )
