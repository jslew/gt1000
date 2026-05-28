"""WAV read/write helpers (stdlib only)."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Any


def read_wav(path: Path) -> tuple[int, int, list[list[float]]]:
    """Return sample rate, channel count, and normalized float samples per channel."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        if sample_width != 2:
            raise ValueError(f"unsupported sample width {sample_width} in {path}")
        frame_count = handle.getnframes()
        raw = handle.readframes(frame_count)
    count = len(raw) // 2
    samples = struct.unpack(f"<{count}h", raw)
    per_channel: list[list[float]] = [[] for _ in range(channels)]
    scale = 1.0 / 32768.0
    for index, value in enumerate(samples):
        per_channel[index % channels].append(value * scale)
    return sample_rate, channels, per_channel


def write_wav_multichannel(path: Path, sample_rate: int, channels: list[list[float]]) -> None:
    if not channels:
        raise ValueError("at least one channel is required")
    frame_count = len(channels[0])
    if any(len(channel) != frame_count for channel in channels):
        raise ValueError("all channels must have the same length")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(len(channels))
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for frame_index in range(frame_count):
            for channel in channels:
                value = max(-1.0, min(1.0, channel[frame_index]))
                frames += struct.pack("<h", int(value * 32767))
        handle.writeframes(frames)


def write_wav_stereo(path: Path, sample_rate: int, left: list[float], right: list[float]) -> None:
    if len(left) != len(right):
        raise ValueError("left and right channel lengths must match")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for l_sample, r_sample in zip(left, right):
            l_value = max(-1.0, min(1.0, l_sample))
            r_value = max(-1.0, min(1.0, r_sample))
            frames += struct.pack("<hh", int(l_value * 32767), int(r_value * 32767))
        handle.writeframes(frames)


def upmix_stereo_for_usb_role(
    stereo_path: Path,
    output_path: Path,
    *,
    role: str,
) -> dict[str, Any]:
    """Place stereo audio on GT-1000 USB playback channels for dry or main paths."""
    from .devices import USB_DRY_STEREO, USB_MAIN_STEREO

    sample_rate, channel_count, per_channel = read_wav(stereo_path)
    if channel_count != 2:
        raise ValueError(f"expected stereo input for USB upmix, got {channel_count} channels")
    if role == "dry":
        target = USB_DRY_STEREO
    elif role == "main":
        target = USB_MAIN_STEREO
    else:
        raise ValueError(f"unsupported USB playback role {role}")
    frame_count = len(per_channel[0])
    silent = [0.0] * frame_count
    channels = [list(silent) for _ in range(6)]
    channels[target[0]] = list(per_channel[0])
    channels[target[1]] = list(per_channel[1])
    write_wav_multichannel(output_path, sample_rate, channels)
    return {
        "sampleRate": sample_rate,
        "playbackRole": role,
        "usbChannels": [index + 1 for index in target],
    }


def extract_channels(path: Path, channel_indexes: tuple[int, int], output: Path) -> dict[str, int]:
    sample_rate, channels, per_channel = read_wav(path)
    if max(channel_indexes) >= channels:
        raise ValueError(f"capture has {channels} channels; need indexes {channel_indexes}")
    write_wav_stereo(output, sample_rate, per_channel[channel_indexes[0]], per_channel[channel_indexes[1]])
    return {"sampleRate": sample_rate, "sourceChannels": channels, "extracted": [index + 1 for index in channel_indexes]}


def generate_sine_tone(
    path: Path,
    *,
    sample_rate: int = 44100,
    duration: float = 3.0,
    frequency: float = 440.0,
    amplitude: float = 0.25,
) -> dict[str, float | int]:
    frame_count = max(1, int(sample_rate * duration))
    left: list[float] = []
    right: list[float] = []
    for index in range(frame_count):
        value = amplitude * math.sin(2.0 * math.pi * frequency * index / sample_rate)
        left.append(value)
        right.append(value)
    write_wav_stereo(path, sample_rate, left, right)
    return {
        "sampleRate": sample_rate,
        "durationSeconds": duration,
        "frequencyHz": frequency,
        "amplitude": amplitude,
        "frames": frame_count,
    }
