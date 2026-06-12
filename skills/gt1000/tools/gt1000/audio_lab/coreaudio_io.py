"""GT-1000 USB audio I/O via PortAudio (sounddevice) on macOS."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .devices import is_gt1000_audio_name
from .errors import AudioLabError
from .metrics import analyze_multichannel_peaks
from .wav_io import read_wav, write_wav_multichannel


def coreaudio_available() -> bool:
    try:
        import sounddevice  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


def _initialize_portaudio() -> None:
    import sounddevice as sd

    initialize = getattr(sd, "_initialize", None)
    if initialize is None:
        return
    try:
        initialize()
    except Exception:
        pass


def _require_coreaudio() -> None:
    if not coreaudio_available():
        raise AudioLabError(
            "PortAudio I/O requires sounddevice and numpy: pip install -r skills/gt1000/requirements-audio.txt",
            64,
        )
    _initialize_portaudio()


def _teardown_portaudio() -> None:
    """Release PortAudio/CoreAudio handles before the next CoreMIDI operation."""
    try:
        import sounddevice as sd
    except ImportError:
        return
    try:
        sd.stop()
    except Exception:
        pass
    terminate = getattr(sd, "_terminate", None)
    if terminate is None:
        return
    try:
        terminate()
    except Exception:
        pass


def list_input_devices() -> list[dict[str, Any]]:
    import sounddevice as sd

    devices: list[dict[str, Any]] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device["max_input_channels"]) <= 0:
            continue
        name = str(device["name"])
        devices.append(_device_dict(index, device, direction="input"))
    return devices


def list_output_devices() -> list[dict[str, Any]]:
    import sounddevice as sd

    devices: list[dict[str, Any]] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device["max_output_channels"]) <= 0:
            continue
        devices.append(_device_dict(index, device, direction="output"))
    return devices


def _device_dict(index: int, device: dict[str, Any], *, direction: str) -> dict[str, Any]:
    name = str(device["name"])
    payload: dict[str, Any] = {
        "backend": "coreaudio",
        "index": index,
        "name": name,
        "direction": direction,
        "defaultSampleRate": float(device["default_samplerate"]),
        "isGT1000": is_gt1000_audio_name(name),
    }
    if direction == "input":
        payload["maxInputChannels"] = int(device["max_input_channels"])
    else:
        payload["maxOutputChannels"] = int(device["max_output_channels"])
    return payload


def find_input_device_index(*, device_index: int | None = None, device_name: str = "GT-1000") -> int:
    import sounddevice as sd

    return _find_device_index(
        direction="input",
        device_index=device_index,
        device_name=device_name,
        channel_field="max_input_channels",
        list_fn=list_input_devices,
    )


def find_output_device_index(*, device_index: int | None = None, device_name: str = "GT-1000") -> int:
    import sounddevice as sd

    return _find_device_index(
        direction="output",
        device_index=device_index,
        device_name=device_name,
        channel_field="max_output_channels",
        list_fn=list_output_devices,
    )


def _find_device_index(
    *,
    direction: str,
    device_index: int | None,
    device_name: str,
    channel_field: str,
    list_fn: Any,
) -> int:
    import sounddevice as sd

    if device_index is not None:
        device = sd.query_devices(device_index)
        if int(device[channel_field]) <= 0:
            raise AudioLabError(f"device index {device_index} is not an {direction} device", 64)
        return device_index

    marker = device_name.lower()
    for index, device in enumerate(sd.query_devices()):
        name = str(device["name"]).lower()
        if marker in name and int(device[channel_field]) > 0:
            return index
    for index, device in enumerate(sd.query_devices()):
        name = str(device["name"])
        if is_gt1000_audio_name(name) and int(device[channel_field]) > 0:
            return index

    lines = [f"  [{item['index']}] {item['name']}" for item in list_fn()]
    raise AudioLabError(
        f"GT-1000 {direction} device not found via sounddevice. "
        f"Install: pip install sounddevice numpy.\n" + "\n".join(lines),
        64,
    )


def resolve_capture_rate_and_channels(
    device_index: int,
    *,
    sample_rate: int,
    channels: int,
) -> tuple[int, int]:
    import sounddevice as sd

    device = sd.query_devices(device_index)
    max_channels = int(device["max_input_channels"])
    if channels > max_channels:
        raise AudioLabError(
            f"device {device_index} ({device['name']}) supports {max_channels} input channels, not {channels}",
            64,
        )
    if sample_rate <= 0:
        sample_rate = int(device["default_samplerate"])
    return sample_rate, channels


def resolve_playback_rate_and_channels(
    device_index: int,
    *,
    sample_rate: int,
    channels: int,
) -> tuple[int, int]:
    import sounddevice as sd

    device = sd.query_devices(device_index)
    max_channels = int(device["max_output_channels"])
    if channels > max_channels:
        raise AudioLabError(
            f"device {device_index} ({device['name']}) supports {max_channels} output channels, not {channels}",
            64,
        )
    if sample_rate <= 0:
        sample_rate = int(device["default_samplerate"])
    return sample_rate, channels


def wav_to_float_array(path: Path) -> tuple[int, Any]:
    import numpy as np

    sample_rate, channel_count, per_channel = read_wav(path)
    frame_count = len(per_channel[0])
    columns = [np.asarray(channel, dtype=np.float32) for channel in per_channel]
    return sample_rate, np.column_stack(columns)


def record_multichannel(
    output_path: Path,
    *,
    duration: float,
    channels: int = 6,
    sample_rate: int = 44100,
    device_index: int | None = None,
    device_name: str = "GT-1000",
    pre_roll: float = 0.15,
) -> dict[str, Any]:
    import numpy as np
    import sounddevice as sd

    _require_coreaudio()
    index = find_input_device_index(device_index=device_index, device_name=device_name)
    sample_rate, channels = resolve_capture_rate_and_channels(
        index, sample_rate=sample_rate, channels=channels
    )
    device = sd.query_devices(index)
    frames_total = int(sample_rate * duration)
    recorded_chunks: list[Any] = []
    capture_seconds = duration + pre_roll

    def callback(indata, frames, time_info, status) -> None:
        if status:
            pass
        recorded_chunks.append(indata.copy())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sd.InputStream(
            device=index,
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            callback=callback,
        ):
            sd.sleep(int(capture_seconds * 1000))
    finally:
        _teardown_portaudio()

    if not recorded_chunks:
        raise AudioLabError("sounddevice capture returned no audio frames", 64)

    audio = np.concatenate(recorded_chunks, axis=0)
    if audio.shape[0] > frames_total:
        audio = audio[:frames_total]

    per_channel = [audio[:, channel].tolist() for channel in range(channels)]
    write_wav_multichannel(output_path, sample_rate, per_channel)

    peak_report = analyze_multichannel_peaks(output_path)
    device_info = _device_dict(index, device, direction="input")
    return {
        "capturePath": str(output_path),
        "audioBackend": "coreaudio",
        "captureBackend": "coreaudio",
        "device": device_info,
        "channels": channels,
        "sampleRate": sample_rate,
        "durationSeconds": duration,
        "channelPeaks": peak_report.get("channelMetrics"),
        "anySignal": peak_report.get("anySignal"),
        "digitalSilence": not bool(peak_report.get("anySignal")),
    }


def play_wav(
    input_path: Path,
    *,
    device_index: int | None = None,
    device_name: str = "GT-1000",
    pre_roll: float = 0.1,
    blocking: bool = True,
) -> dict[str, Any]:
    import sounddevice as sd

    _require_coreaudio()
    sample_rate, audio = wav_to_float_array(input_path)
    channels = int(audio.shape[1])
    index = find_output_device_index(device_index=device_index, device_name=device_name)
    sample_rate, channels = resolve_playback_rate_and_channels(
        index, sample_rate=sample_rate, channels=channels
    )
    device = sd.query_devices(index)
    duration = audio.shape[0] / float(sample_rate)
    if pre_roll > 0:
        time.sleep(pre_roll)
    try:
        sd.play(audio, sample_rate, device=index, blocking=blocking)
        if blocking:
            sd.wait()
    finally:
        if blocking:
            _teardown_portaudio()
    device_info = _device_dict(index, device, direction="output")
    return {
        "playbackPath": str(input_path),
        "audioBackend": "coreaudio",
        "playbackBackend": "coreaudio",
        "device": device_info,
        "channels": channels,
        "sampleRate": sample_rate,
        "durationSeconds": duration,
    }


def duplex_playback_capture(
    playback_path: Path,
    capture_path: Path,
    *,
    input_channels: int = 6,
    device_index: int | None = None,
    device_name: str = "GT-1000",
    pre_roll: float = 0.1,
    tail_seconds: float = 0.5,
) -> dict[str, Any]:
    """Play multichannel WAV to GT output while recording all input channels (reamp)."""
    import numpy as np
    import sounddevice as sd

    _require_coreaudio()
    in_index = find_input_device_index(device_index=device_index, device_name=device_name)
    out_index = find_output_device_index(device_index=device_index, device_name=device_name)
    sample_rate, playback = wav_to_float_array(playback_path)
    out_channels = int(playback.shape[1])
    sample_rate, out_channels = resolve_playback_rate_and_channels(
        out_index, sample_rate=sample_rate, channels=out_channels
    )
    sample_rate, input_channels = resolve_capture_rate_and_channels(
        in_index, sample_rate=sample_rate, channels=input_channels
    )
    playback_frames = playback.shape[0]
    capture_frames = playback_frames + int(sample_rate * tail_seconds)
    position = 0
    recorded_chunks: list[np.ndarray] = []

    def callback(indata, outdata, frames, _time_info, status) -> None:
        nonlocal position
        if status:
            pass
        if position < playback_frames:
            end = min(position + frames, playback_frames)
            chunk = playback[position:end]
            outdata[: len(chunk)] = chunk
            if len(chunk) < frames:
                outdata[len(chunk) :] = 0
        else:
            outdata.fill(0)
        recorded_chunks.append(indata.copy())
        position += frames

    in_device = sd.query_devices(in_index)
    out_device = sd.query_devices(out_index)
    stream = sd.Stream(
        device=(in_index, out_index),
        samplerate=sample_rate,
        channels=(input_channels, out_channels),
        dtype="float32",
        callback=callback,
    )
    try:
        with stream:
            if pre_roll > 0:
                sd.sleep(int(pre_roll * 1000))
            sd.sleep(int((capture_frames / sample_rate) * 1000) + 100)
    finally:
        _teardown_portaudio()

    if not recorded_chunks:
        raise AudioLabError("duplex capture returned no audio frames", 64)

    audio = np.concatenate(recorded_chunks, axis=0)[:capture_frames]
    per_channel = [audio[:, channel].tolist() for channel in range(input_channels)]
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    write_wav_multichannel(capture_path, sample_rate, per_channel)
    peak_report = analyze_multichannel_peaks(capture_path)

    return {
        "capturePath": str(capture_path),
        "playbackPath": str(playback_path),
        "audioBackend": "coreaudio",
        "captureBackend": "coreaudio",
        "playbackBackend": "coreaudio",
        "captureDevice": _device_dict(in_index, in_device, direction="input"),
        "playbackDevice": _device_dict(out_index, out_device, direction="output"),
        "channels": input_channels,
        "sampleRate": sample_rate,
        "durationSeconds": playback_frames / float(sample_rate),
        "channelPeaks": peak_report.get("channelMetrics"),
        "anySignal": peak_report.get("anySignal"),
        "digitalSilence": not bool(peak_report.get("anySignal")),
    }


def record_multichannel_async(
    output_path: Path,
    *,
    duration: float,
    channels: int = 6,
    sample_rate: int = 44100,
    device_index: int | None = None,
    device_name: str = "GT-1000",
    extra_seconds: float = 1.0,
) -> tuple[Any, dict[str, Any]]:
    """Start a background thread capture; returns (thread, result_holder)."""
    import threading

    holder: dict[str, Any] = {}

    def runner() -> None:
        holder["info"] = record_multichannel(
            output_path,
            duration=duration + extra_seconds,
            channels=channels,
            sample_rate=sample_rate,
            device_index=device_index,
            device_name=device_name,
            pre_roll=0.0,
        )

    thread = threading.Thread(target=runner, name="gt1000-coreaudio-capture")
    thread.start()
    time.sleep(0.05)
    return thread, holder
