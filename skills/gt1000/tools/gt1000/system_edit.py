"""Typed builders for global system section writes."""

from __future__ import annotations

from tools.gt1000 import live
from tools.gt1000.patch_edit import PatchPlan

SYSTEM_INOUT_SIZE = 0x60

# offset, maximum (decoded scale), canonical field id
_USB_NIBBLE_FIELDS: dict[str, tuple[int, int, str]] = {
    "totalReverbLevel": (0x23, 200, "totalReverbLevel"),
    "usbDryOut": (0x26, 200, "usbDryOut"),
    "usbDryToEfx": (0x28, 200, "usbDryToEfx"),
    "usbMainEfxOut": (0x2B, 200, "usbMainEfxOut"),
    "usbMainMixLevel": (0x2D, 200, "usbMainMixLevel"),
    "usbSubEfxOut": (0x30, 200, "usbSubEfxOut"),
    "usbSubMixLevel": (0x32, 200, "usbSubMixLevel"),
}

_FIELD_ALIASES: dict[str, str] = {
    "total-reverb-level": "totalReverbLevel",
    "usb-dry-out": "usbDryOut",
    "usb-dry-to-efx": "usbDryToEfx",
    "usb-main-efx-out": "usbMainEfxOut",
    "usb-main-mix-level": "usbMainMixLevel",
    "usb-sub-efx-out": "usbSubEfxOut",
    "usb-sub-mix-level": "usbSubMixLevel",
}


def normalize_inout_field(field: str) -> str:
    key = field.strip()
    lowered = key.lower().replace("_", "-")
    if lowered in _FIELD_ALIASES:
        return _FIELD_ALIASES[lowered]
    if key in _USB_NIBBLE_FIELDS:
        return key
    allowed = sorted(set(_USB_NIBBLE_FIELDS) | set(_FIELD_ALIASES))
    raise ValueError(f"unknown system in/out field {field!r}; expected one of: {', '.join(allowed)}")


def build_system_inout_set_plan(field: str, value: int) -> PatchPlan:
    canonical = normalize_inout_field(field)
    offset, maximum, field_id = _USB_NIBBLE_FIELDS[canonical]
    if not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{field_id} must be an integer 0...{maximum}")
    address = live.address_adding(live.SYSTEM_IN_OUT, offset)
    data = live.nibbles_for(value, byte_count=2)
    return PatchPlan(
        id=f"system-inout-set:{field_id}",
        description=f"Set System IN/OUT {field_id} to {value}.",
        writes=[live.PatchWrite(f"System IN/OUT {field_id}", address, data)],
    )


def list_inout_fields() -> list[dict[str, int | str]]:
    rows = [
        {"id": field_id, "offset": offset, "maximum": maximum}
        for offset, maximum, field_id in _USB_NIBBLE_FIELDS.values()
    ]
    return sorted(rows, key=lambda row: str(row["id"]))
