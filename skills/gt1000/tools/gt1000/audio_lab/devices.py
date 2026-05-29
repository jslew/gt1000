"""GT-1000 USB audio channel map and device matching."""

from __future__ import annotations

from typing import Any


# USB channel numbers are 1-based in BOSS docs; indexes here are 0-based.
USB_MAIN_STEREO = (0, 1)
USB_DRY_STEREO = (2, 3)
USB_SUB_STEREO = (4, 5)

GT1000_NAME_MARKERS = ("gt-1000", "gt1000")
ROLAND_USB_MARKERS = ("jp_co_roland", "rdusb0217", "roland")


def is_gt1000_audio_name(name: str) -> bool:
    lower = name.lower()
    if any(marker in lower for marker in GT1000_NAME_MARKERS):
        return True
    return any(marker in lower for marker in ROLAND_USB_MARKERS)


def channel_map_doc() -> list[dict[str, Any]]:
    return [
        {"usbChannels": "1-2", "role": "main", "indexes": [i + 1 for i in USB_MAIN_STEREO]},
        {"usbChannels": "3-4", "role": "dry", "indexes": [i + 1 for i in USB_DRY_STEREO]},
        {"usbChannels": "5-6", "role": "sub", "indexes": [i + 1 for i in USB_SUB_STEREO]},
    ]
