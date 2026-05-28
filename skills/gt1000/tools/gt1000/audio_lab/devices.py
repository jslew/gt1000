"""GT-1000 USB audio channel map and device matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# USB channel numbers are 1-based in BOSS docs; indexes here are 0-based.
USB_MAIN_STEREO = (0, 1)
USB_DRY_STEREO = (2, 3)
USB_SUB_STEREO = (4, 5)

GT1000_NAME_MARKERS = ("gt-1000", "gt1000")
ROLAND_USB_MARKERS = ("jp_co_roland", "rdusb0217", "roland")


@dataclass(frozen=True)
class AudioDevice:
    backend: str
    index: int
    name: str
    direction: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "index": self.index,
            "name": self.name,
            "direction": self.direction,
            "isGT1000": is_gt1000_audio_name(self.name),
        }


def is_gt1000_audio_name(name: str) -> bool:
    lower = name.lower()
    if any(marker in lower for marker in GT1000_NAME_MARKERS):
        return True
    return any(marker in lower for marker in ROLAND_USB_MARKERS)


def parse_avfoundation_inputs(listing: str) -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    in_audio = False
    for line in listing.splitlines():
        if "AVFoundation audio devices" in line:
            in_audio = True
            continue
        if in_audio and "AVFoundation video devices" in line:
            break
        match = re.search(r"\[(\d+)\]\s*(.+)$", line.strip())
        if in_audio and match:
            devices.append(AudioDevice("avfoundation", int(match.group(1)), match.group(2).strip(), "input"))
    return devices


def parse_audiotoolbox_outputs(listing: str) -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    for line in listing.splitlines():
        match = re.search(r"\]\s+\[(\d+)\]\s+(.+)$", line)
        if not match:
            continue
        index = int(match.group(1))
        remainder = match.group(2).strip()
        if "," in remainder:
            name, _uid = remainder.split(",", 1)
            name = name.strip()
            if name == "(null)":
                name = _uid.strip()
        else:
            name = remainder
        devices.append(AudioDevice("audiotoolbox", index, name, "output"))
    return devices


def channel_map_doc() -> list[dict[str, Any]]:
    return [
        {"usbChannels": "1-2", "role": "main", "indexes": [i + 1 for i in USB_MAIN_STEREO]},
        {"usbChannels": "3-4", "role": "dry", "indexes": [i + 1 for i in USB_DRY_STEREO]},
        {"usbChannels": "5-6", "role": "sub", "indexes": [i + 1 for i in USB_SUB_STEREO]},
    ]
