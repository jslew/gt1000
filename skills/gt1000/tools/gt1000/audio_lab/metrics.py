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
SPACE_FRAME_SECONDS = 0.05
SPACE_HOP_SECONDS = 0.025
HIGH_END_WINDOW_FRAMES = 8192
HIGH_END_WINDOW_COUNT = 9


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


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) * 0.5


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((max(0.0, min(100.0, percentile)) / 100.0) * (len(ordered) - 1)))
    return ordered[index]


def _ratio_db(numerator: float, denominator: float) -> float | None:
    if numerator <= 0.0 or denominator <= 0.0:
        return None
    return 10.0 * math.log10(numerator / denominator)


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


def _stereo_correlation(left: list[float], right: list[float]) -> float | None:
    if not left or not right:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((l_sample - left_mean) * (r_sample - right_mean) for l_sample, r_sample in zip(left, right))
    left_power = math.sqrt(sum((sample - left_mean) * (sample - left_mean) for sample in left))
    right_power = math.sqrt(sum((sample - right_mean) * (sample - right_mean) for sample in right))
    if left_power <= 0.0 or right_power <= 0.0:
        return None
    return numerator / (left_power * right_power)


def _side_to_mid_db(left: list[float], right: list[float]) -> float | None:
    if not left or not right:
        return None
    mid = [(l_sample + r_sample) * 0.5 for l_sample, r_sample in zip(left, right)]
    side = [(l_sample - r_sample) * 0.5 for l_sample, r_sample in zip(left, right)]
    mid_energy = sum(sample * sample for sample in mid) / len(mid)
    side_energy = sum(sample * sample for sample in side) / len(side)
    if mid_energy <= 0.0:
        return None
    if side_energy <= 0.0:
        return SIGNAL_RMS_FLOOR_DBFS
    return _ratio_db(side_energy, mid_energy)


def _frame_space_metrics(
    left: list[float],
    right: list[float],
    *,
    sample_rate: int,
) -> list[dict[str, Any]]:
    frame_count = int(round(SPACE_FRAME_SECONDS * sample_rate))
    hop_count = int(round(SPACE_HOP_SECONDS * sample_rate))
    if frame_count <= 0 or hop_count <= 0:
        return []
    mono = [(l_sample + r_sample) * 0.5 for l_sample, r_sample in zip(left, right)]
    frames: list[dict[str, Any]] = []
    for start in range(0, len(mono) - frame_count + 1, hop_count):
        end = start + frame_count
        mono_frame = mono[start:end]
        left_frame = left[start:end]
        right_frame = right[start:end]
        frames.append(
            {
                "startSeconds": start / float(sample_rate),
                "rmsDbfs": _rms_dbfs(mono_frame),
                "stereoCorrelation": _stereo_correlation(left_frame, right_frame),
                "sideToMidDb": _side_to_mid_db(left_frame, right_frame),
                "left": left_frame,
                "right": right_frame,
                "mono": mono_frame,
            }
        )
    return frames


def _median_field(frames: list[dict[str, Any]], field: str) -> float | None:
    return _median([float(frame[field]) for frame in frames if frame.get(field) is not None])


def _frames_between_rms(
    frames: list[dict[str, Any]],
    *,
    low_dbfs: float,
    high_dbfs: float,
) -> list[dict[str, Any]]:
    return [
        frame
        for frame in frames
        if frame.get("rmsDbfs") is not None and low_dbfs <= float(frame["rmsDbfs"]) <= high_dbfs
    ]


def _concat_mono_frames(frames: list[dict[str, Any]], *, max_frames: int = 160) -> list[float]:
    samples: list[float] = []
    for frame in frames[:max_frames]:
        samples.extend(frame["mono"])
    return samples


def _brightness_db(samples: list[float], sample_rate: int) -> float | None:
    windowed = _window_samples(samples, max_frames=8192)
    if not windowed:
        return None
    body = _band_energy(windowed, sample_rate, 160.0, 2500.0)
    high = _band_energy(windowed, sample_rate, 2500.0, 8000.0)
    return _ratio_db(high, body)


def _analysis_windows(samples: list[float], *, window_frames: int, count: int) -> list[list[float]]:
    if not samples:
        return []
    if len(samples) <= window_frames:
        return [_window_samples(samples, max_frames=window_frames)]
    usable = len(samples) - window_frames
    if count <= 1:
        starts = [usable // 2]
    else:
        starts = [int(round((usable * index) / float(count - 1))) for index in range(count)]
    windows: list[list[float]] = []
    for start in starts:
        segment = samples[start : start + window_frames]
        windows.append(_window_samples(segment, max_frames=window_frames))
    return windows


def _energy_db(energy: float) -> float:
    return 10.0 * math.log10(max(SPECTRAL_FLOOR, energy))


def _window_high_end_metrics(window: list[float], sample_rate: int) -> dict[str, Any]:
    low_mid = max(SPECTRAL_FLOOR, _band_energy(window, sample_rate, 160.0, 1250.0))
    vocal = max(SPECTRAL_FLOOR, _band_energy(window, sample_rate, 1250.0, 2500.0))
    presence = max(SPECTRAL_FLOOR, _band_energy(window, sample_rate, 2500.0, 5000.0))
    fizz = max(SPECTRAL_FLOOR, _band_energy(window, sample_rate, 5000.0, 8000.0))
    air = max(SPECTRAL_FLOOR, _band_energy(window, sample_rate, 8000.0, 12000.0))
    return {
        "rmsDbfs": _rms_dbfs(window),
        "lowMidEnergyDb": _energy_db(low_mid),
        "vocalEnergyDb": _energy_db(vocal),
        "presenceEnergyDb": _energy_db(presence),
        "fizzEnergyDb": _energy_db(fizz),
        "airEnergyDb": _energy_db(air),
        "presenceToVocalDb": _ratio_db(presence, vocal),
        "fizzToPresenceDb": _ratio_db(fizz, presence),
        "fizzToVocalDb": _ratio_db(fizz, vocal),
        "airToVocalDb": _ratio_db(air, vocal),
        "airToPresenceDb": _ratio_db(air, presence),
        "lowMidToVocalDb": _ratio_db(low_mid, vocal),
    }


def _field_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    return [float(row[field]) for row in rows if row.get(field) is not None]


def high_end_profile(
    per_channel: list[list[float]],
    channels: int,
    *,
    sample_rate: int,
) -> dict[str, Any]:
    mono = _mono_samples(per_channel, channels)
    windows = _analysis_windows(
        mono,
        window_frames=HIGH_END_WINDOW_FRAMES,
        count=HIGH_END_WINDOW_COUNT,
    )
    if not windows:
        return {"available": False, "reason": "no audio samples"}
    all_rows = [_window_high_end_metrics(window, sample_rate) for window in windows if window]
    if not all_rows:
        return {"available": False, "reason": "no analysis windows"}
    rms_values = _field_values(all_rows, "rmsDbfs")
    active_floor = _percentile(rms_values, 35.0)
    rows = [
        row
        for row in all_rows
        if active_floor is None or row.get("rmsDbfs") is not None and float(row["rmsDbfs"]) >= active_floor
    ]
    if not rows:
        rows = all_rows
    fields = (
        "presenceToVocalDb",
        "fizzToPresenceDb",
        "fizzToVocalDb",
        "airToVocalDb",
        "airToPresenceDb",
        "lowMidToVocalDb",
    )
    summary: dict[str, Any] = {
        "available": True,
        "windowFrames": HIGH_END_WINDOW_FRAMES,
        "windowCount": len(all_rows),
        "activeWindowCount": len(rows),
        "activeWindowFloorDbfs": active_floor,
        "note": "High-end rolloff/fizz descriptors sampled across active windows; more-negative fizz ratios mean less high-end hash.",
    }
    for field in fields:
        values = _field_values(rows, field)
        summary[field] = _median(values)
        summary[f"{field}P90"] = _percentile(values, 90.0)
    return summary


def _repeat_hint(frames: list[dict[str, Any]]) -> dict[str, Any]:
    envelope_db = [
        float(frame["rmsDbfs"])
        for frame in frames
        if frame.get("rmsDbfs") is not None
    ]
    if len(envelope_db) < 16:
        return {"tailEnvelopeModulationDb": None, "repeatPeakLagMs": None, "repeatPeakStrength": None}
    modulation = None
    p10 = _percentile(envelope_db, 10.0)
    p90 = _percentile(envelope_db, 90.0)
    if p10 is not None and p90 is not None:
        modulation = p90 - p10
    count = len(envelope_db)
    x_mean = (count - 1) * 0.5
    y_mean = sum(envelope_db) / count
    denominator = sum((index - x_mean) * (index - x_mean) for index in range(count))
    slope = 0.0 if denominator <= 0.0 else sum((index - x_mean) * (value - y_mean) for index, value in enumerate(envelope_db)) / denominator
    intercept = y_mean - slope * x_mean
    centered_envelope = [value - (intercept + slope * index) for index, value in enumerate(envelope_db)]
    centered = [
        centered_envelope[index + 1] - centered_envelope[index]
        for index in range(len(centered_envelope) - 1)
    ]
    energy = sum(value * value for value in centered)
    if energy <= 0.0:
        return {"tailEnvelopeModulationDb": modulation, "repeatPeakLagMs": None, "repeatPeakStrength": None}
    min_lag = max(1, int(round(0.08 / SPACE_HOP_SECONDS)))
    max_lag = min(len(centered) - 1, int(round(0.9 / SPACE_HOP_SECONDS)))
    best_lag = None
    best_strength = None
    for lag in range(min_lag, max_lag + 1):
        correlation = sum(centered[index] * centered[index + lag] for index in range(len(centered) - lag))
        strength = correlation / energy
        if best_strength is None or strength > best_strength:
            best_strength = strength
            best_lag = lag
    return {
        "tailEnvelopeModulationDb": modulation,
        "repeatPeakLagMs": None if best_lag is None else best_lag * SPACE_HOP_SECONDS * 1000.0,
        "repeatPeakStrength": best_strength,
    }


def space_profile(
    per_channel: list[list[float]],
    channels: int,
    *,
    sample_rate: int,
) -> dict[str, Any]:
    if channels == 1:
        left = per_channel[0]
        right = per_channel[0]
    elif channels >= 2:
        left = per_channel[0]
        right = per_channel[1]
    else:
        return {"available": False, "reason": "no audio channels"}
    frames = _frame_space_metrics(left, right, sample_rate=sample_rate)
    rms_values = [float(frame["rmsDbfs"]) for frame in frames if frame.get("rmsDbfs") is not None]
    if not rms_values:
        return {"available": False, "reason": "no measurable audio frames"}
    tail_low = _percentile(rms_values, 10.0)
    tail_high = _percentile(rms_values, 35.0)
    active_low = _percentile(rms_values, 60.0)
    active_high = _percentile(rms_values, 95.0)
    tail_frames = [] if tail_low is None or tail_high is None else _frames_between_rms(frames, low_dbfs=tail_low, high_dbfs=tail_high)
    active_frames = [] if active_low is None or active_high is None else _frames_between_rms(frames, low_dbfs=active_low, high_dbfs=active_high)
    tail_rms = _median_field(tail_frames, "rmsDbfs")
    active_rms = _median_field(active_frames, "rmsDbfs")
    return {
        "available": True,
        "frameSeconds": SPACE_FRAME_SECONDS,
        "hopSeconds": SPACE_HOP_SECONDS,
        "frameCount": len(frames),
        "rmsPercentilesDbfs": {
            "p10": tail_low,
            "p35": tail_high,
            "p60": active_low,
            "p95": active_high,
        },
        "tailRmsDbfs": tail_rms,
        "activeRmsDbfs": active_rms,
        "tailToActiveDeltaDb": None if tail_rms is None or active_rms is None else tail_rms - active_rms,
        "stereoCorrelationMedian": _median_field(frames, "stereoCorrelation"),
        "sideToMidDbMedian": _median_field(frames, "sideToMidDb"),
        "tailStereoCorrelationMedian": _median_field(tail_frames, "stereoCorrelation"),
        "tailSideToMidDbMedian": _median_field(tail_frames, "sideToMidDb"),
        "activeStereoCorrelationMedian": _median_field(active_frames, "stereoCorrelation"),
        "activeSideToMidDbMedian": _median_field(active_frames, "sideToMidDb"),
        "tailBrightnessDb": _brightness_db(_concat_mono_frames(tail_frames), sample_rate),
        "activeBrightnessDb": _brightness_db(_concat_mono_frames(active_frames), sample_rate),
        **_repeat_hint(tail_frames),
        "note": "Low-level frame and stereo-width descriptors for ambience/reverb matching; descriptive only in the MVP score.",
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
        "space": space_profile(per_channel, channels, sample_rate=sample_rate),
        "highEnd": high_end_profile(per_channel, channels, sample_rate=sample_rate),
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
    space_weight: float = 0.15,
    high_end_weight: float = 0.25,
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
    space_error = _space_match_error(reference.get("space"), candidate.get("space"))
    high_end_error = _high_end_match_error(reference.get("highEnd"), candidate.get("highEnd"))
    score = band_weight * band_error + rms_weight * rms_error + space_weight * space_error + high_end_weight * high_end_error
    return {
        "score": score,
        "bandError": band_error,
        "rmsError": rms_error,
        "spaceError": space_error,
        "highEndError": high_end_error,
        "rmsDeltaDb": rms_delta,
        "bandWeight": band_weight,
        "rmsWeight": rms_weight,
        "spaceWeight": space_weight,
        "highEndWeight": high_end_weight,
        "bandErrors": band_errors,
        "note": "Lower score is closer to the stored reference profile; spaceError and highEndError are low-weight descriptors.",
    }


def _space_match_error(reference_space: Any, candidate_space: Any) -> float:
    if not isinstance(reference_space, dict) or not isinstance(candidate_space, dict):
        return 0.0
    if not reference_space.get("available") or not candidate_space.get("available"):
        return 0.0
    weighted_fields = (
        ("tailToActiveDeltaDb", 1.0, 6.0),
        ("tailSideToMidDbMedian", 0.8, 6.0),
        ("tailBrightnessDb", 0.7, 12.0),
        ("tailEnvelopeModulationDb", 0.4, 8.0),
        ("stereoCorrelationMedian", 0.5, 0.5),
    )
    error = 0.0
    used = 0.0
    for field, weight, scale in weighted_fields:
        ref_value = reference_space.get(field)
        candidate_value = candidate_space.get(field)
        if ref_value is None or candidate_value is None:
            continue
        normalized = (float(candidate_value) - float(ref_value)) / scale
        error += weight * normalized * normalized
        used += weight
    return 0.0 if used <= 0.0 else error / used


def _asymmetric_db_error(candidate_value: float, reference_value: float, *, scale: float, excess_multiplier: float = 2.5) -> float:
    delta = candidate_value - reference_value
    multiplier = excess_multiplier if delta > 0.0 else 1.0
    normalized = delta / scale
    return multiplier * normalized * normalized


def _high_end_match_error(reference_high: Any, candidate_high: Any) -> float:
    if not isinstance(reference_high, dict) or not isinstance(candidate_high, dict):
        return 0.0
    if not reference_high.get("available") or not candidate_high.get("available"):
        return 0.0
    weighted_fields = (
        ("fizzToVocalDb", 1.0, 8.0, 3.0),
        ("fizzToVocalDbP90", 0.8, 8.0, 3.0),
        ("fizzToPresenceDb", 0.8, 6.0, 2.5),
        ("airToVocalDb", 0.4, 12.0, 2.0),
        ("presenceToVocalDb", 0.5, 8.0, 1.5),
    )
    error = 0.0
    used = 0.0
    for field, weight, scale, excess_multiplier in weighted_fields:
        ref_value = reference_high.get(field)
        candidate_value = candidate_high.get(field)
        if ref_value is None or candidate_value is None:
            continue
        error += weight * _asymmetric_db_error(
            float(candidate_value),
            float(ref_value),
            scale=scale,
            excess_multiplier=excess_multiplier,
        )
        used += weight
    return 0.0 if used <= 0.0 else error / used


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
