"""GT-1000 USB audio capture, playback, and device listing (sounddevice / PortAudio)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from . import coreaudio_io
from .devices import USB_DRY_STEREO, USB_MAIN_STEREO
from .errors import AudioLabError
from .metrics import analyze_multichannel_peaks, capture_silence_troubleshooting, reamp_silence_error_message
from .setup_efct import prepare_usb_reamp
from .wav_io import extract_channels, upmix_stereo_for_usb_role


def list_devices() -> dict[str, Any]:
    if os.name != "posix" or os.uname().sysname != "Darwin":
        raise AudioLabError("USB audio I/O is implemented for macOS only in Phase 1", 64)
    coreaudio_io._require_coreaudio()
    inputs = coreaudio_io.list_input_devices()
    outputs = coreaudio_io.list_output_devices()
    gt_inputs = [item for item in inputs if item.get("isGT1000")]
    gt_outputs = [item for item in outputs if item.get("isGT1000")]
    if not gt_inputs:
        raise AudioLabError("GT-1000 USB input not found; connect the unit and run audio ports again.", 64)
    if not gt_outputs:
        raise AudioLabError("GT-1000 USB output not found; connect the unit and run audio ports again.", 64)
    return {
        "audioBackend": "coreaudio",
        "inputs": inputs,
        "outputs": outputs,
        "gt1000Inputs": gt_inputs,
        "gt1000Outputs": gt_outputs,
        "recommended": {
            "captureInput": gt_inputs[0],
            "playbackOutput": gt_outputs[0],
            "audioBackend": "coreaudio",
        },
        "note": (
            "Requires sounddevice + numpy (skills/gt1000/requirements-audio.txt). "
            "Device index is the PortAudio index shown here."
        ),
    }


def record_multichannel(
    output_path: Path,
    *,
    duration: float,
    channels: int = 6,
    sample_rate: int = 44100,
    device_index: int | None = None,
    pre_roll: float = 0.15,
) -> dict[str, Any]:
    return coreaudio_io.record_multichannel(
        output_path,
        duration=duration,
        channels=channels,
        sample_rate=sample_rate,
        device_index=device_index,
        pre_roll=pre_roll,
    )


def probe_capture(
    *,
    duration: float = 3.0,
    sample_rate: int = 44100,
    device_index: int | None = None,
) -> dict[str, Any]:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="gt1000-probe-") as tmp:
        capture_path = Path(tmp) / "probe6.wav"
        capture_info = record_multichannel(
            capture_path,
            duration=duration,
            sample_rate=sample_rate,
            device_index=device_index,
        )
        peak_report = analyze_multichannel_peaks(capture_path)
    troubleshooting = capture_silence_troubleshooting()
    if not peak_report.get("anySignal"):
        troubleshooting.append(
            "If still silent: allow Microphone for Terminal/Cursor; quit other apps using GT-1000 USB audio."
        )
    return {
        "id": "audioProbe",
        "capture": capture_info,
        "channelPeaks": peak_report,
        "troubleshooting": troubleshooting,
        "channelMap": [
            {"usb": "1-2", "role": "main", "indexes": [1, 2]},
            {"usb": "3-4", "role": "dry", "indexes": [3, 4]},
            {"usb": "5-6", "role": "sub", "indexes": [5, 6]},
        ],
    }


def prepare_playback_file(
    input_path: Path,
    playback_role: str,
) -> tuple[Path, dict[str, Any] | None, tempfile.TemporaryDirectory[str] | None]:
    if playback_role not in {"dry", "main"}:
        raise AudioLabError(f"unsupported playback role {playback_role}", 64)
    import wave

    with wave.open(str(input_path), "rb") as handle:
        if handle.getnchannels() == 6:
            return input_path, None, None
    temp_dir = tempfile.TemporaryDirectory(prefix="gt1000-reamp-")
    playback_path = Path(temp_dir.name) / "playback6.wav"
    mapping = upmix_stereo_for_usb_role(input_path, playback_path, role=playback_role)
    return playback_path, mapping, temp_dir


def reamp_capture(
    input_path: Path,
    output_path: Path,
    *,
    playback_role: str = "dry",
    record_seconds: float | None = None,
    sample_rate: int = 44100,
    prepare_usb: bool = True,
    midi_timeout: float = 8.0,
    playback_device_index: int | None = None,
    capture_device_index: int | None = None,
) -> dict[str, Any]:
    setup_prepare = None
    if prepare_usb:
        setup_prepare = prepare_usb_reamp(midi_timeout, verify=True)

    capture_path = output_path.with_suffix(".capture6.wav")
    duration = record_seconds
    if duration is None:
        import wave

        with wave.open(str(input_path), "rb") as handle:
            duration = handle.getnframes() / float(handle.getframerate())
    duration = max(0.5, float(duration))

    playback_path, playback_mapping, temp_dir = prepare_playback_file(input_path, playback_role)
    duplex_info: dict[str, Any] | None = None
    try:
        duplex_info = coreaudio_io.duplex_playback_capture(
            playback_path,
            capture_path,
            device_index=playback_device_index or capture_device_index,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
    capture_info = duplex_info or {}
    if capture_info.get("digitalSilence"):
        raise AudioLabError(
            reamp_silence_error_message(playback_role=playback_role, capture_path=capture_path),
            66,
        )

    extract_info = extract_channels(capture_path, USB_MAIN_STEREO, output_path)
    return {
        "wetPath": str(output_path),
        "capturePath": str(capture_path),
        "playbackDevice": capture_info.get("playbackDevice"),
        "captureDevice": capture_info.get("captureDevice"),
        "audioBackend": "coreaudio",
        "captureBackend": capture_info.get("captureBackend"),
        "playbackBackend": capture_info.get("playbackBackend"),
        "playbackRole": playback_role,
        "playbackMapping": playback_mapping,
        "setupPrepare": setup_prepare,
        "extracted": extract_info,
    }
