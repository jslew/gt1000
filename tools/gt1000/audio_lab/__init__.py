"""Compatibility package for GT-1000 audio lab."""

import importlib
import sys

_impl = importlib.import_module("skills.gt1000.tools.gt1000.audio_lab")

sys.modules[__name__] = _impl

for _name in ("audio_io", "commands", "coreaudio_io", "devices", "errors", "metrics", "session", "wav_io"):
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(f"skills.gt1000.tools.gt1000.audio_lab.{_name}")
