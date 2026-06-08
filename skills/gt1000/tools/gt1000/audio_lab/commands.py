"""High-level audio lab operations used by the CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .devices import USB_DRY_STEREO, USB_MAIN_STEREO, channel_map_doc
from .errors import AudioLabError
from .audio_io import list_devices, probe_capture, record_multichannel, reamp_capture
from .metrics import (
    analyze_file,
    analyze_file_trimmed,
    analyze_multichannel_peaks,
    capture_silence_troubleshooting,
    compare_files,
    reference_match_score,
    reference_profile,
    rms_delta_db,
)
from .branch_lab import branch_context, compare_branches, probe_branch, probe_param, render_branch
from .device_snapshot import capture_live_snapshots, write_device_snapshots
from .orchestrator import render_labeled_wet
from .reference_planner import plan_reference_candidates
from .reference_runner import run_reference_candidates
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
    dry_metrics = analyze_file(dry_path)
    return {
        "id": "audioGenerateTone",
        "session": session,
        "sessionDir": str(session_dir),
        "dryPath": str(dry_path),
        "dryMetrics": dry_metrics,
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


def cmd_analyze_trimmed(
    paths: list[Path],
    *,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
) -> dict[str, Any]:
    if len(paths) < 1:
        raise AudioLabError("analyze-trimmed requires at least one WAV file", 64)
    files = [
        analyze_file_trimmed(
            path,
            trim_start_seconds=trim_start_seconds,
            trim_end_seconds=trim_end_seconds,
        )
        for path in paths
    ]
    if len(files) == 1:
        return {"id": "audioAnalyzeTrimmed", "file": files[0]}
    deltas: list[dict[str, Any]] = []
    reference = files[0]
    for report in files[1:]:
        delta = rms_delta_db(reference, report)
        deltas.append(
            {
                "path": report.get("path"),
                "deltaRmsDbVsFirst": delta,
                "rmsDbfs": report.get("rmsDbfs"),
            }
        )
    return {
        "id": "audioAnalyzeTrimmed",
        "files": files,
        "comparisons": deltas,
        "note": "Metrics on trimmed regions only (steady-state); positive delta means louder than first file.",
    }


def cmd_reference_analyze(
    path: Path,
    *,
    output_path: Path | None = None,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
) -> dict[str, Any]:
    if not path.is_file():
        raise AudioLabError(f"reference WAV not found: {path}", 64)
    profile = reference_profile(
        path,
        trim_start_seconds=trim_start_seconds,
        trim_end_seconds=trim_end_seconds,
    )
    output = output_path or path.with_name(f"{path.stem}-reference-profile.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "id": "audioReferenceAnalyze",
        "referencePath": str(path),
        "profilePath": str(output),
        "profile": profile,
        "nextStep": "Run `audio match-reference <profile.json> <candidate.wav>...` to rank wet renders.",
    }


def cmd_match_reference(
    profile_path: Path,
    candidate_paths: list[Path],
    *,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
    band_weight: float = 1.0,
    rms_weight: float = 0.05,
) -> dict[str, Any]:
    if not profile_path.is_file():
        raise AudioLabError(f"reference profile not found: {profile_path}", 64)
    if not candidate_paths:
        raise AudioLabError("match-reference requires at least one candidate WAV", 64)
    reference = json.loads(profile_path.read_text(encoding="utf-8"))
    candidates: list[dict[str, Any]] = []
    for candidate_path in candidate_paths:
        if not candidate_path.is_file():
            raise AudioLabError(f"candidate WAV not found: {candidate_path}", 64)
        candidate_profile = reference_profile(
            candidate_path,
            trim_start_seconds=trim_start_seconds,
            trim_end_seconds=trim_end_seconds,
        )
        score = reference_match_score(
            reference,
            candidate_profile,
            band_weight=band_weight,
            rms_weight=rms_weight,
        )
        candidates.append(
            {
                "path": str(candidate_path),
                "score": score["score"],
                "bandError": score["bandError"],
                "rmsDeltaDb": score["rmsDeltaDb"],
                "profile": candidate_profile,
                "details": score,
            }
        )
    ranked = sorted(candidates, key=lambda item: item["score"])
    return {
        "id": "audioMatchReference",
        "referenceProfilePath": str(profile_path),
        "referencePath": reference.get("path"),
        "ranked": ranked,
        "best": ranked[0],
        "note": (
            "Phase 4 MVP scoring only: lower score is closer by approximate band energy plus RMS penalty. "
            "It does not guarantee a perceptual tone match."
        ),
    }


def cmd_reference_plan(
    profile_path: Path,
    *,
    session: str,
    max_candidates: int = 12,
) -> dict[str, Any]:
    if not profile_path.is_file():
        raise AudioLabError(f"reference profile not found: {profile_path}", 64)
    reference = json.loads(profile_path.read_text(encoding="utf-8"))
    try:
        plan = plan_reference_candidates(reference, session=session, max_candidates=max_candidates)
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error
    return {
        **plan,
        "referenceProfilePath": str(profile_path),
    }


def cmd_reference_run(
    profile_path: Path,
    *,
    session: str,
    max_candidates: int = 4,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    prepare_usb: bool = True,
    verify_writes: bool = True,
) -> dict[str, Any]:
    try:
        return run_reference_candidates(
            profile_path,
            session=session,
            max_candidates=max_candidates,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
            prepare_usb=prepare_usb,
            verify_writes=verify_writes,
        )
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error


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


def cmd_compare_branches(
    session: str,
    divider: str,
    *,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    verify_writes: bool = True,
    prepare_usb: bool = True,
    user_slot: str | None = None,
) -> dict[str, Any]:
    try:
        return compare_branches(
            session,
            divider,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
            verify_writes=verify_writes,
            prepare_usb=prepare_usb,
            user_slot=user_slot,
        )
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error
    except Exception as error:
        try:
            from tools.gt1000 import live
        except ModuleNotFoundError:
            import live
        if isinstance(error, live.LiveMIDIError):
            raise AudioLabError(str(error), 64) from error
        raise


def cmd_branch_context(
    divider: str,
    *,
    midi_timeout: float = 20.0,
) -> dict[str, Any]:
    try:
        return branch_context(divider, midi_timeout=midi_timeout)
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error


def cmd_probe_param(
    session: str,
    divider: str,
    channel: str,
    block_id: str,
    parameter_id: str,
    *,
    low_value: int = 0,
    high_value: int = 100,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    prepare_usb: bool = True,
) -> dict[str, Any]:
    try:
        return probe_param(
            session,
            divider,
            channel,
            block_id,
            parameter_id,
            low_value=low_value,
            high_value=high_value,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
            prepare_usb=prepare_usb,
        )
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error


def cmd_probe_branch(
    session: str,
    divider: str,
    channel: str,
    *,
    max_probes: int = 6,
    include_divider_levels: bool = False,
    low_value: int = 0,
    high_value: int = 100,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    prepare_usb: bool = True,
) -> dict[str, Any]:
    try:
        return probe_branch(
            session,
            divider,
            channel,
            max_probes=max_probes,
            include_divider_levels=include_divider_levels,
            low_value=low_value,
            high_value=high_value,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
            prepare_usb=prepare_usb,
        )
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error


def cmd_render_branch(
    session: str,
    divider: str,
    channel: str,
    *,
    label: str | None = None,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    verify_writes: bool = False,
    prepare_usb: bool = True,
    restore_divider: bool = True,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
    user_slot: str | None = None,
    experiment_note: str | None = None,
) -> dict[str, Any]:
    try:
        return render_branch(
            session,
            divider,
            channel,
            label=label,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
            verify_writes=verify_writes,
            prepare_usb=prepare_usb,
            restore_divider=restore_divider,
            trim_start_seconds=trim_start_seconds,
            trim_end_seconds=trim_end_seconds,
            user_slot=user_slot,
            experiment_note=experiment_note,
        )
    except ValueError as error:
        raise AudioLabError(str(error), 64) from error


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
