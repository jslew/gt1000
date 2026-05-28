"""ffmpeg-backed capture and playback on macOS."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .devices import (
    USB_DRY_STEREO,
    USB_MAIN_STEREO,
    AudioDevice,
    is_gt1000_audio_name,
    parse_audiotoolbox_outputs,
    parse_avfoundation_inputs,
)
from .errors import AudioLabError
from .wav_io import extract_channels


def find_ffmpeg() -> str:
    env = os.environ.get("GT1000_FFMPEG", "").strip()
    if env:
        path = Path(env)
        if path.is_file():
            return str(path)
        raise AudioLabError(f"GT1000_FFMPEG is set but not a file: {env}")
    found = shutil.which("ffmpeg")
    if not found:
        raise AudioLabError("ffmpeg not found on PATH; install ffmpeg or set GT1000_FFMPEG", 64)
    return found


def run_ffmpeg(args: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    command = [find_ffmpeg(), "-hide_banner", "-nostdin", *args]
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise AudioLabError(f"ffmpeg timed out after {timeout}s: {' '.join(command)}") from error


def list_devices() -> dict[str, Any]:
    if os.name != "posix" or os.uname().sysname != "Darwin":
        raise AudioLabError("audio device listing is implemented for macOS only in Phase 1", 64)
    ffmpeg = find_ffmpeg()
    input_listing = subprocess.run(
        [ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
        check=False,
    )
    inputs = parse_avfoundation_inputs(input_listing.stderr)
    output_listing = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "0.01",
            "-f",
            "audiotoolbox",
            "-list_devices",
            "1",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = parse_audiotoolbox_outputs(output_listing.stderr)
    gt_inputs = [device.to_dict() for device in inputs if is_gt1000_audio_name(device.name)]
    gt_outputs = [device.to_dict() for device in outputs if is_gt1000_audio_name(device.name)]
    return {
        "ffmpeg": ffmpeg,
        "inputs": [device.to_dict() for device in inputs],
        "outputs": [device.to_dict() for device in outputs],
        "gt1000Inputs": gt_inputs,
        "gt1000Outputs": gt_outputs,
        "recommended": {
            "captureInput": gt_inputs[0] if gt_inputs else None,
            "playbackOutput": gt_outputs[0] if gt_outputs else None,
        },
    }


def pick_gt1000_input(devices: list[AudioDevice]) -> AudioDevice:
    for device in devices:
        if is_gt1000_audio_name(device.name):
            return device
    raise AudioLabError("GT-1000 audio input device not found via avfoundation", 64)


def pick_gt1000_output(devices: list[AudioDevice]) -> AudioDevice:
    for device in devices:
        if is_gt1000_audio_name(device.name):
            return device
    raise AudioLabError("GT-1000 audio output device not found via audiotoolbox", 64)


def record_multichannel(
    output_path: Path,
    *,
    duration: float,
    channels: int = 6,
    sample_rate: int = 44100,
    device_index: int | None = None,
    pre_roll: float = 0.15,
) -> dict[str, Any]:
    listing = run_ffmpeg(["-f", "avfoundation", "-list_devices", "true", "-i", ""])
    inputs = parse_avfoundation_inputs(listing.stderr)
    device = next((item for item in inputs if item.index == device_index), None) if device_index is not None else None
    if device is None:
        device = pick_gt1000_input(inputs)
    capture_seconds = duration + pre_roll
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_ffmpeg(
        [
            "-y",
            "-loglevel",
            "error",
            "-f",
            "avfoundation",
            "-i",
            f":{device.index}",
            "-t",
            f"{capture_seconds:.3f}",
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            str(output_path),
        ],
        timeout=capture_seconds + 30.0,
    )
    if result.returncode != 0:
        raise AudioLabError(f"ffmpeg capture failed: {result.stderr.strip() or result.stdout.strip()}")
    return {
        "capturePath": str(output_path),
        "device": device.to_dict(),
        "channels": channels,
        "sampleRate": sample_rate,
        "durationSeconds": duration,
    }


def play_to_device(
    input_path: Path,
    *,
    device_index: int,
    duration: float | None = None,
    output_channels: int = 6,
    pre_roll: float = 0.1,
) -> None:
    args = [
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ac",
        str(output_channels),
        "-f",
        "audiotoolbox",
        "-audio_device_index",
        str(device_index),
    ]
    if duration is not None:
        args.extend(["-t", f"{duration:.3f}"])
    args.append("-")
    time.sleep(pre_roll)
    result = run_ffmpeg(args, timeout=(duration or 60.0) + 30.0)
    if result.returncode != 0:
        raise AudioLabError(f"ffmpeg playback failed: {result.stderr.strip() or result.stdout.strip()}")


def playback_filter_for_role(role: str) -> list[str]:
    if role == "dry":
        return ["-af", "volume=1.0"]
    return []


def reamp_capture(
    input_path: Path,
    output_path: Path,
    *,
    playback_role: str = "dry",
    record_seconds: float | None = None,
    sample_rate: int = 44100,
) -> dict[str, Any]:
    devices = list_devices()
    gt_outputs = [
        AudioDevice(item["backend"], item["index"], item["name"], item["direction"])
        for item in devices.get("gt1000Outputs", [])
    ]
    if not gt_outputs:
        raw_outputs = [
            AudioDevice(item["backend"], item["index"], item["name"], item["direction"])
            for item in devices.get("outputs", [])
        ]
        output_device = pick_gt1000_output(raw_outputs)
    else:
        output_device = gt_outputs[0]
    input_device = pick_gt1000_input(
        [
            AudioDevice(item["backend"], item["index"], item["name"], item["direction"])
            for item in devices.get("inputs", [])
        ]
    )
    capture_path = output_path.with_suffix(".capture6.wav")
    duration = record_seconds
    if duration is None:
        import wave

        with wave.open(str(input_path), "rb") as handle:
            duration = handle.getnframes() / float(handle.getframerate())
    duration = max(0.5, float(duration))
    record_seconds_total = duration + 1.0
    record_proc = subprocess.Popen(
        [
            find_ffmpeg(),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "avfoundation",
            "-i",
            f":{input_device.index}",
            "-t",
            f"{record_seconds_total:.3f}",
            "-ac",
            "6",
            "-ar",
            str(sample_rate),
            str(capture_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        play_args = ["-loglevel", "error", "-i", str(input_path), "-ac", "6"]
        play_args.extend(playback_filter_for_role(playback_role))
        play_args.extend(
            [
                "-f",
                "audiotoolbox",
                "-audio_device_index",
                str(output_device.index),
                "-t",
                f"{duration:.3f}",
                "-",
            ]
        )
        play_result = run_ffmpeg(play_args, timeout=duration + 30.0)
        if play_result.returncode != 0:
            raise AudioLabError(f"ffmpeg playback failed: {play_result.stderr.strip()}")
        record_stderr = record_proc.communicate(timeout=record_seconds_total + 30.0)[1]
        if record_proc.returncode != 0:
            raise AudioLabError(f"ffmpeg capture failed: {record_stderr.strip()}")
    finally:
        if record_proc.poll() is None:
            record_proc.kill()
    # After dry USB playback, processed tone should appear on main USB channels 1-2.
    extract_info = extract_channels(capture_path, USB_MAIN_STEREO, output_path)
    return {
        "wetPath": str(output_path),
        "capturePath": str(capture_path),
        "playbackDevice": output_device.to_dict(),
        "captureDevice": input_device.to_dict(),
        "playbackRole": playback_role,
        "extracted": extract_info,
    }
