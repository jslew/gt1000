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
