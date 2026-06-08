"""Audio analysis metrics (stdlib only)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .wav_io import read_wav

SIGNAL_RMS_FLOOR_DBFS = -96.0
DEFAULT_REFERENCE_BANDS: tuple[tuple[float, float], ...] = (
    (80.0, 160.0),
    (160.0, 320.0),
    (320.0, 640.0),
    (640.0, 1250.0),
    (1250.0, 2500.0),
    (2500.0, 5000.0),
    (5000.0, 8000.0),
)
SPECTRAL_FLOOR = 1.0e-12


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


def _mono_samples(per_channel: list[list[float]], channels: int) -> list[float]:
    if channels == 1:
        return list(per_channel[0])
    if channels >= 2:
        return [(l_sample + r_sample) * 0.5 for l_sample, r_sample in zip(per_channel[0], per_channel[1])]
    return []


def _window_samples(samples: list[float], *, max_frames: int = 8192) -> list[float]:
    if not samples:
        return []
    if len(samples) <= max_frames:
        selected = list(samples)
    else:
        start = max(0, (len(samples) - max_frames) // 2)
        selected = samples[start : start + max_frames]
    count = len(selected)
    if count < 2:
        return selected
    return [
        sample * (0.5 - 0.5 * math.cos((2.0 * math.pi * index) / (count - 1)))
        for index, sample in enumerate(selected)
    ]


def _single_frequency_energy(samples: list[float], sample_rate: int, frequency: float) -> float:
    if not samples or frequency <= 0.0:
        return 0.0
    angular = 2.0 * math.pi * frequency / float(sample_rate)
    real = 0.0
    imag = 0.0
    for index, sample in enumerate(samples):
        phase = angular * index
        real += sample * math.cos(phase)
        imag -= sample * math.sin(phase)
    scale = max(1, len(samples))
    return ((real * real) + (imag * imag)) / float(scale * scale)


def _band_energy(samples: list[float], sample_rate: int, low_hz: float, high_hz: float) -> float:
    nyquist = sample_rate / 2.0
    low = max(1.0, min(low_hz, nyquist - 1.0))
    high = max(low + 1.0, min(high_hz, nyquist - 1.0))
    probe_count = 7
    ratio = high / low
    probes = [low * (ratio ** (index / (probe_count - 1))) for index in range(probe_count)]
    return sum(_single_frequency_energy(samples, sample_rate, frequency) for frequency in probes) / len(probes)


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
    any_signal = any(
        rms is not None and rms > SIGNAL_RMS_FLOOR_DBFS
        for rms in (item.get("rmsDbfs") for item in channel_metrics)
    )
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
        "macOS: System Settings > Privacy & Security > Microphone > allow the app running gt1000-agent "
        "(Codex, Terminal, Ghostty, Cursor, or iTerm), then restart that app.",
        "Quit GarageBand, Logic, or any other app using the GT-1000 USB audio device, then retry.",
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


def reamp_silence_error_message(*, playback_role: str, capture_path: Path) -> str:
    tips = [
        "GT-1000 USB re-amp captured digital silence on all input channels after playing a non-silent dry WAV.",
        f"Playback role was {playback_role!r}; six-channel capture path: {capture_path}.",
        "Most likely cause: macOS Microphone permission is missing for the app running gt1000-agent "
        "(Codex, Terminal, Ghostty, Cursor, or iTerm). Grant it, restart that app, then retry.",
        "Also quit GarageBand, Logic, Tone Studio, or any other app using the GT-1000 USB audio device.",
        "If permissions are correct, verify the GT-1000 USB audio routing: USB DIR MON OFF for re-amp, "
        "USB TO EFX/EFX OUT levels up, and any physical send/return loop used by the patch closed.",
    ]
    return " ".join(tips)


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


def reference_profile(
    path: Path,
    *,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
) -> dict[str, Any]:
    """Create a lightweight spectral profile for Phase 4 reference-tone scoring."""
    sample_rate, channels, per_channel = read_wav(path)
    if trim_start_seconds or trim_end_seconds:
        per_channel, trim_info = _trim_channels(
            per_channel,
            sample_rate=sample_rate,
            trim_start_seconds=trim_start_seconds,
            trim_end_seconds=trim_end_seconds,
        )
    else:
        frame_count = len(per_channel[0]) if per_channel else 0
        trim_info = {
            "trimStartSeconds": 0.0,
            "trimEndSeconds": 0.0,
            "trimStartFrame": 0,
            "trimEndFrame": frame_count,
            "analyzedFrames": frame_count,
            "totalFrames": frame_count,
            "analyzedDurationSeconds": frame_count / float(sample_rate) if sample_rate else 0.0,
        }
    mono = _window_samples(_mono_samples(per_channel, channels))
    if not mono:
        raise ValueError(f"no audio channels in {path}")

    bands: list[dict[str, Any]] = []
    total_energy = 0.0
    weighted_frequency = 0.0
    for low_hz, high_hz in DEFAULT_REFERENCE_BANDS:
        energy = max(SPECTRAL_FLOOR, _band_energy(mono, sample_rate, low_hz, high_hz))
        center = math.sqrt(low_hz * high_hz)
        total_energy += energy
        weighted_frequency += center * energy
        bands.append(
            {
                "lowHz": low_hz,
                "highHz": high_hz,
                "centerHz": center,
                "energy": energy,
                "logEnergy": math.log(energy),
            }
        )

    broadband = analyze_file_trimmed(
        path,
        trim_start_seconds=trim_start_seconds,
        trim_end_seconds=trim_end_seconds,
    ) if (trim_start_seconds or trim_end_seconds) else analyze_file(path)
    peak_dbfs = broadband.get("peakDbfs")
    rms_dbfs = broadband.get("rmsDbfs")
    return {
        "path": str(path),
        "sampleRate": sample_rate,
        "channels": channels,
        "profileVersion": 1,
        "bands": bands,
        "spectralCentroidHz": None if total_energy <= 0.0 else weighted_frequency / total_energy,
        "rmsDbfs": rms_dbfs,
        "peakDbfs": peak_dbfs,
        "crestDb": None if peak_dbfs is None or rms_dbfs is None else peak_dbfs - rms_dbfs,
        **trim_info,
        "note": "Lightweight stdlib-only Phase 4 profile; band scores are approximate, not a tone-match guarantee.",
    }


def reference_match_score(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    band_weight: float = 1.0,
    rms_weight: float = 0.05,
) -> dict[str, Any]:
    ref_bands = reference.get("bands") or []
    candidate_bands = candidate.get("bands") or []
    if len(ref_bands) != len(candidate_bands):
        raise ValueError("reference and candidate profiles use different band counts")
    band_error = 0.0
    band_errors: list[dict[str, Any]] = []
    for ref_band, candidate_band in zip(ref_bands, candidate_bands):
        ref_log = float(ref_band["logEnergy"])
        candidate_log = float(candidate_band["logEnergy"])
        error = candidate_log - ref_log
        squared = error * error
        band_error += squared
        band_errors.append(
            {
                "lowHz": ref_band["lowHz"],
                "highHz": ref_band["highHz"],
                "logEnergyError": error,
                "squaredError": squared,
            }
        )
    ref_rms = reference.get("rmsDbfs")
    candidate_rms = candidate.get("rmsDbfs")
    rms_delta = None
    rms_error = 0.0
    if ref_rms is not None and candidate_rms is not None:
        rms_delta = float(candidate_rms) - float(ref_rms)
        rms_error = rms_delta * rms_delta
    score = band_weight * band_error + rms_weight * rms_error
    return {
        "score": score,
        "bandError": band_error,
        "rmsError": rms_error,
        "rmsDeltaDb": rms_delta,
        "bandWeight": band_weight,
        "rmsWeight": rms_weight,
        "bandErrors": band_errors,
        "note": "Lower score is closer to the stored reference profile.",
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
