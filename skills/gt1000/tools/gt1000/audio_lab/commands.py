"""High-level audio lab operations used by the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .devices import USB_DRY_STEREO, USB_MAIN_STEREO, channel_map_doc
from .errors import AudioLabError
from .audio_io import list_devices, probe_capture, record_multichannel, reamp_capture
from .metrics import analyze_file, analyze_multichannel_peaks, capture_silence_troubleshooting, compare_files
from .device_snapshot import capture_live_snapshots, write_device_snapshots
from .orchestrator import render_labeled_wet
from .session import append_session_event, default_dry_path, resolve_session_dir, write_session_meta
from .wav_io import extract_channels, generate_sine_tone


def cmd_ports() -> dict[str, Any]:
    devices = list_devices()
    return {
        "id": "audioPorts",
        "channelMap": channel_map_doc(),
        **devices,
        "note": "MIDI ports remain under `ports --live`. USB audio uses sounddevice (PortAudio) on macOS.",
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


def cmd_probe(
    *,
    duration: float,
    sample_rate: int,
    device_index: int | None,
) -> dict[str, Any]:
    return probe_capture(duration=duration, sample_rate=sample_rate, device_index=device_index)


def cmd_record_dry(
    session: str,
    *,
    duration: float,
    sample_rate: int,
    device_index: int | None,
    bus: str,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session, create=True)
    capture_path = session_dir / "capture6.wav"
    capture_info = record_multichannel(
        capture_path,
        duration=duration,
        sample_rate=sample_rate,
        device_index=device_index,
    )
    peak_report = analyze_multichannel_peaks(capture_path)
    troubleshooting = capture_silence_troubleshooting(bus=bus)
    if not peak_report.get("anySignal"):
        troubleshooting.append("All captured channels were silent.")

    result: dict[str, Any] = {
        "id": "audioRecordDry",
        "session": session,
        "sessionDir": str(session_dir),
        "bus": bus,
        "capturePath": str(capture_path),
        "capture": capture_info,
        "channelPeaks": peak_report,
        "troubleshooting": troubleshooting,
    }

    if bus in {"dry", "both"}:
        dry_path = default_dry_path(session_dir)
        dry_extract = extract_channels(capture_path, USB_DRY_STEREO, dry_path)
        dry_metrics = analyze_file(dry_path)
        write_session_meta(
            session_dir,
            {
                "session": session,
                "dryPath": str(dry_path),
                "drySource": "usb-record",
                "capturePath": str(capture_path),
                "bus": bus,
                **capture_info,
                "dryExtract": dry_extract,
            },
        )
        append_session_event(session_dir, {"type": "record-dry", "durationSeconds": duration, "bus": bus})
        result["dryPath"] = str(dry_path)
        result["dryExtract"] = dry_extract
        result["dryMetrics"] = dry_metrics

    if bus in {"main", "both"}:
        renders = session_dir / "renders"
        renders.mkdir(exist_ok=True)
        wet_path = renders / "record-main.wav"
        main_extract = extract_channels(capture_path, USB_MAIN_STEREO, wet_path)
        wet_metrics = analyze_file(wet_path)
        result["wetPath"] = str(wet_path)
        result["mainExtract"] = main_extract
        result["wetMetrics"] = wet_metrics

    if bus == "dry":
        result["note"] = (
            "Saved USB dry channels 3–4. Strong signal on GarageBand inputs 1–2 does not appear in dry.wav; "
            "use --bus main or --bus both to capture processed MAIN."
        )
    elif bus == "main":
        result["note"] = "Saved USB main/processed channels 1–2."
    else:
        result["note"] = "Saved dry.wav (3–4) and renders/record-main.wav (1–2)."
    return result


def cmd_reamp(
    session: str,
    *,
    input_path: Path | None,
    output_path: Path | None,
    playback_role: str,
    prepare_usb: bool = True,
    midi_timeout: float = 8.0,
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
    result = reamp_capture(
        dry_path,
        output_path,
        playback_role=playback_role,
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
    )
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


def cmd_session_init(
    session: str,
    *,
    live: bool = False,
    midi_timeout: float = 20.0,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session, create=True)
    payload: dict[str, Any] = {
        "session": session,
        "sessionDir": str(session_dir),
        "dryPath": str(default_dry_path(session_dir)),
        "phase": 2,
    }
    device_snapshot_paths: dict[str, str] | None = None
    if live:
        snapshots = capture_live_snapshots(midi_timeout)
        device_snapshot_paths = write_device_snapshots(session_dir, snapshots)
        payload["deviceSnapshots"] = device_snapshot_paths
        payload["patchReadHash"] = snapshots["patch"].get("readHash")
        payload["patchName"] = snapshots["patch"].get("patchName")
    write_session_meta(session_dir, payload)
    append_session_event(
        session_dir,
        {"type": "session-init", "live": live, "deviceSnapshots": device_snapshot_paths},
    )
    return {
        "id": "audioSessionInit",
        **payload,
        "note": (
            "Add dry.wav via record-dry or generate-tone, then `audio session render --label <name>`. "
            "Use --live on init to store system IN/OUT + patch snapshots under deviceSnapshots/."
        ),
    }


def cmd_session_render(
    session: str,
    label: str,
    *,
    prepare_usb: bool = True,
    midi_timeout: float = 8.0,
    playback_role: str = "dry",
    settle_seconds: float = 0.25,
    snapshot_patch: bool = True,
) -> dict[str, Any]:
    return render_labeled_wet(
        session,
        label,
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
        playback_role=playback_role,
        settle_seconds=settle_seconds,
        snapshot_patch=snapshot_patch,
    )
