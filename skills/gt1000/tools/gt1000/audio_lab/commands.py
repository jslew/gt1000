"""High-level audio lab operations used by the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .devices import USB_DRY_STEREO, channel_map_doc
from .errors import AudioLabError
from .ffmpeg_io import list_devices, record_multichannel, reamp_capture
from .metrics import analyze_file, compare_files
from .session import append_session_event, default_dry_path, resolve_session_dir, write_session_meta
from .wav_io import extract_channels, generate_sine_tone


def cmd_ports() -> dict[str, Any]:
    devices = list_devices()
    return {
        "id": "audioPorts",
        "channelMap": channel_map_doc(),
        **devices,
        "note": "MIDI ports remain under `ports --live`. USB audio uses Core Audio via ffmpeg on macOS.",
    }


def cmd_generate_tone(
    session: str,
    *,
    duration: float,
    frequency: float,
    amplitude: float,
    sample_rate: int,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session, create=True)
    dry_path = default_dry_path(session_dir)
    tone_info = generate_sine_tone(
        dry_path,
        sample_rate=sample_rate,
        duration=duration,
        frequency=frequency,
        amplitude=amplitude,
    )
    write_session_meta(
        session_dir,
        {
            "session": session,
            "dryPath": str(dry_path),
            "drySource": "generated-tone",
            **tone_info,
        },
    )
    append_session_event(session_dir, {"type": "generate-tone", **tone_info})
    return {
        "id": "audioGenerateTone",
        "session": session,
        "sessionDir": str(session_dir),
        "dryPath": str(dry_path),
        "tone": tone_info,
    }


def cmd_record_dry(
    session: str,
    *,
    duration: float,
    sample_rate: int,
    device_index: int | None,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session, create=True)
    capture_path = session_dir / "capture6.wav"
    dry_path = default_dry_path(session_dir)
    capture_info = record_multichannel(
        capture_path,
        duration=duration,
        sample_rate=sample_rate,
        device_index=device_index,
    )
    extract_info = extract_channels(capture_path, USB_DRY_STEREO, dry_path)
    write_session_meta(
        session_dir,
        {
            "session": session,
            "dryPath": str(dry_path),
            "drySource": "usb-record",
            "capturePath": str(capture_path),
            **capture_info,
            "dryExtract": extract_info,
        },
    )
    append_session_event(session_dir, {"type": "record-dry", "durationSeconds": duration})
    analysis = analyze_file(dry_path)
    return {
        "id": "audioRecordDry",
        "session": session,
        "sessionDir": str(session_dir),
        "dryPath": str(dry_path),
        "capturePath": str(capture_path),
        "capture": capture_info,
        "dryExtract": extract_info,
        "dryMetrics": analysis,
        "note": "If dryMetrics are very low, confirm guitar/input signal and MENU > IN/OUT USB dry levels.",
    }


def cmd_reamp(
    session: str,
    *,
    input_path: Path | None,
    output_path: Path | None,
    playback_role: str,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session, create=False)
    if not session_dir.is_dir():
        raise AudioLabError(f"session does not exist: {session_dir}", 64)
    dry_path = input_path or default_dry_path(session_dir)
    if not dry_path.is_file():
        raise AudioLabError(f"dry input not found: {dry_path}", 64)
    if output_path is None:
        renders = session_dir / "renders"
        renders.mkdir(exist_ok=True)
        output_path = renders / "reamp-main.wav"
    result = reamp_capture(dry_path, output_path, playback_role=playback_role)
    append_session_event(session_dir, {"type": "reamp", "wetPath": str(output_path), "playbackRole": playback_role})
    wet_metrics = analyze_file(output_path)
    dry_metrics = analyze_file(dry_path)
    return {
        "id": "audioReamp",
        "session": session,
        "sessionDir": str(session_dir),
        "dryPath": str(dry_path),
        "wetPath": str(output_path),
        "dryMetrics": dry_metrics,
        "wetMetrics": wet_metrics,
        **result,
        "note": (
            "If wetMetrics stay near silence: on the GT-1000 set MENU > IN/OUT SETTING > USB AUDIO > MAIN > "
            "DIR MON = OFF (cannot be saved; defaults ON at power-on). Confirm TO EFX and EFX OUT levels. "
            "See references/gt1000-wiki/usb-audio.md."
        ),
    }


def cmd_analyze(paths: list[Path]) -> dict[str, Any]:
    if len(paths) < 1:
        raise AudioLabError("analyze requires at least one WAV file", 64)
    if len(paths) == 1:
        return {"id": "audioAnalyze", "file": analyze_file(paths[0])}
    return {"id": "audioAnalyze", **compare_files(paths)}
