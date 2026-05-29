"""Single-process MIDI + USB audio orchestration for lab sessions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .audio_io import reamp_capture
from .device_snapshot import capture_patch_snapshot as read_patch_snapshot
from .device_snapshot import write_render_patch_snapshot
from .errors import AudioLabError
from .metrics import analyze_file
from .session import (
    append_render_log,
    append_session_event,
    default_dry_path,
    render_wet_path,
    resolve_session_dir,
)


def render_labeled_wet(
    session: str,
    label: str,
    *,
    prepare_usb: bool = True,
    midi_timeout: float = 8.0,
    playback_role: str = "dry",
    settle_seconds: float = 0.25,
    snapshot_patch: bool = True,
) -> dict[str, Any]:
    """Re-amp session dry.wav to a labeled wet render with optional patch snapshot."""
    session_dir = resolve_session_dir(session, create=False)
    if not session_dir.is_dir():
        raise AudioLabError(f"session does not exist: {session_dir}", 64)
    dry_path = default_dry_path(session_dir)
    if not dry_path.is_file():
        raise AudioLabError(f"session dry.wav not found: {dry_path}", 64)

    if settle_seconds > 0:
        time.sleep(settle_seconds)

    patch_snapshot: dict[str, Any] | None = None
    patch_snapshot_path: Path | None = None
    if snapshot_patch:
        patch_snapshot = read_patch_snapshot(midi_timeout)
        patch_snapshot_path = write_render_patch_snapshot(session_dir, label, patch_snapshot)

    wet_path = render_wet_path(session_dir, label)
    reamp_info = reamp_capture(
        dry_path,
        wet_path,
        playback_role=playback_role,
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
    )
    wet_metrics = analyze_file(wet_path)
    dry_metrics = analyze_file(dry_path)

    render_record = {
        "label": label,
        "wetPath": str(wet_path),
        "patchSnapshotPath": str(patch_snapshot_path) if patch_snapshot_path else None,
        "patchReadHash": patch_snapshot.get("readHash") if patch_snapshot else None,
        "wetMetrics": wet_metrics,
        "dryMetrics": dry_metrics,
        "playbackRole": playback_role,
    }
    append_render_log(session_dir, render_record)
    append_session_event(session_dir, {"type": "session-render", "label": label, "wetPath": str(wet_path)})

    return {
        "id": "audioSessionRender",
        "session": session,
        "sessionDir": str(session_dir),
        "label": label,
        "dryPath": str(dry_path),
        "wetPath": str(wet_path),
        "patchSnapshotPath": str(patch_snapshot_path) if patch_snapshot_path else None,
        "patchSnapshot": patch_snapshot,
        "dryMetrics": dry_metrics,
        "wetMetrics": wet_metrics,
        **reamp_info,
        "note": (
            "Re-amp protocol: use GT-1000 MAIN USB playback, DIR MON OFF (prepare-reamp), "
            "then capture USB 1-2. See docs/audio-lab-reamp-protocol.md."
        ),
    }
