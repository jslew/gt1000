"""Audio analysis metrics (stdlib only)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .wav_io import read_wav


def _rms_dbfs(samples: list[float]) -> float | None:
    if not samples:
        return None
    mean_square = sum(sample * sample for sample in samples) / len(samples)
    if mean_square <= 0.0:
        return None
    return 20.0 * math.log10(math.sqrt(mean_square))


def _peak_dbfs(samples: list[float]) -> float | None:
    if not samples:
        return None
    peak = max(abs(sample) for sample in samples)
    if peak <= 0.0:
        return None
    return 20.0 * math.log10(peak)


def _stereo_metrics(left: list[float], right: list[float]) -> dict[str, Any]:
    mono = [(l_sample + r_sample) * 0.5 for l_sample, r_sample in zip(left, right)]
    left_rms = _rms_dbfs(left)
    right_rms = _rms_dbfs(right)
    mono_rms = _rms_dbfs(mono)
    return {
        "peakDbfs": _peak_dbfs(mono),
        "rmsDbfs": mono_rms,
        "leftRmsDbfs": left_rms,
        "rightRmsDbfs": right_rms,
        "stereoDeltaDb": None if left_rms is None or right_rms is None else left_rms - right_rms,
        "frameCount": len(left),
        "note": "rmsDbfs is broadband RMS in dBFS; not broadcast LUFS.",
    }


def analyze_multichannel_peaks(path: Path) -> dict[str, Any]:
    """Per-channel peak/RMS for multichannel captures (e.g. 6-ch GT-1000 USB)."""
    sample_rate, channels, per_channel = read_wav(path)
    channel_metrics: list[dict[str, Any]] = []
    for index, samples in enumerate(per_channel):
        channel_metrics.append(
            {
                "channel": index + 1,
                "peakDbfs": _peak_dbfs(samples),
                "rmsDbfs": _rms_dbfs(samples),
            }
        )
    any_signal = any(item.get("peakDbfs") is not None for item in channel_metrics)
    return {
        "path": str(path),
        "sampleRate": sample_rate,
        "channels": channels,
        "channelMetrics": channel_metrics,
        "anySignal": any_signal,
    }


def capture_silence_troubleshooting(*, bus: str | None = None) -> list[str]:
    tips = [
        "Install Core Audio capture: pip install -r skills/gt1000/requirements-audio.txt "
        "(sounddevice + numpy). This is the default capture path on macOS.",
        "Quit GarageBand, Logic, or any other app using the GT-1000 USB audio device, then retry.",
        "macOS: System Settings → Privacy & Security → Microphone → allow the app running gt1000-agent "
        "(Cursor, Terminal, or iTerm).",
        "Play guitar during the capture window; silence produces zero waveforms.",
    ]
    if bus == "dry":
        tips.append(
            "record-dry saves USB channels 3–4. GarageBand inputs 1–2 (MAIN/wet) are a different bus; "
            "use `audio record-dry --bus main` or `audio probe` to verify channels 1–2."
        )
    elif bus == "main":
        tips.append("This capture uses USB channels 1–2 (MAIN / processed path).")
    return tips


def _trim_channels(
    per_channel: list[list[float]],
    *,
    sample_rate: int,
    trim_start_seconds: float,
    trim_end_seconds: float,
) -> tuple[list[list[float]], dict[str, Any]]:
    if trim_start_seconds < 0 or trim_end_seconds < 0:
        raise ValueError("trim seconds must be non-negative")
    frame_count = len(per_channel[0]) if per_channel else 0
    start = min(frame_count, int(round(trim_start_seconds * sample_rate)))
    end = max(start, frame_count - int(round(trim_end_seconds * sample_rate)))
    if end <= start:
        raise ValueError("trim removes entire file; use shorter trim or longer capture")
    trimmed = [channel[start:end] for channel in per_channel]
    return trimmed, {
        "trimStartSeconds": trim_start_seconds,
        "trimEndSeconds": trim_end_seconds,
        "trimStartFrame": start,
        "trimEndFrame": end,
        "analyzedFrames": end - start,
        "totalFrames": frame_count,
        "analyzedDurationSeconds": (end - start) / float(sample_rate),
    }


def analyze_file(path: Path) -> dict[str, Any]:
    sample_rate, channels, per_channel = read_wav(path)
    if channels == 1:
        metrics = _stereo_metrics(per_channel[0], per_channel[0])
    elif channels >= 2:
        metrics = _stereo_metrics(per_channel[0], per_channel[1])
    else:
        raise ValueError(f"no audio channels in {path}")
    return {
        "path": str(path),
        "sampleRate": sample_rate,
        "channels": channels,
        **metrics,
    }


def analyze_file_trimmed(
    path: Path,
    *,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
) -> dict[str, Any]:
    """Measure RMS/peak on the middle of a file, dropping head/tail (reamp settle/tail)."""
    sample_rate, channels, per_channel = read_wav(path)
    trimmed, trim_info = _trim_channels(
        per_channel,
        sample_rate=sample_rate,
        trim_start_seconds=trim_start_seconds,
        trim_end_seconds=trim_end_seconds,
    )
    if channels == 1:
        metrics = _stereo_metrics(trimmed[0], trimmed[0])
    elif channels >= 2:
        metrics = _stereo_metrics(trimmed[0], trimmed[1])
    else:
        raise ValueError(f"no audio channels in {path}")
    return {
        "path": str(path),
        "sampleRate": sample_rate,
        "channels": channels,
        **metrics,
        **trim_info,
        "note": "Metrics computed on trimmed region only (excludes head/tail).",
    }


def rms_delta_db(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> float | None:
    """Return B minus A in dB RMS (broadband), or None if either side is missing."""
    rms_a = metrics_a.get("rmsDbfs")
    rms_b = metrics_b.get("rmsDbfs")
    if rms_a is None or rms_b is None:
        return None
    return rms_b - rms_a


def compare_files(paths: list[Path]) -> dict[str, Any]:
    reports = [analyze_file(path) for path in paths]
    reference_rms = reports[0].get("rmsDbfs") if reports else None
    comparisons: list[dict[str, Any]] = []
    for report in reports[1:]:
        other_rms = report.get("rmsDbfs")
        delta = None
        if reference_rms is not None and other_rms is not None:
            delta = other_rms - reference_rms
        comparisons.append({"path": report["path"], "deltaRmsDbVsFirst": delta})
    return {"files": reports, "comparisons": comparisons}
