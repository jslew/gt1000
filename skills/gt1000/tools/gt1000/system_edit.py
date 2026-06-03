"""Typed builders for global system section writes."""

from __future__ import annotations

try:
    from tools.gt1000 import live
    from tools.gt1000.patch_edit import PatchPlan, patch_name_data
except ModuleNotFoundError:
    import live
    from patch_edit import PatchPlan, patch_name_data

SYSTEM_INOUT_SIZE = 0x60
SYSTEM_INPUT_SETTING_SIZE = 0x11
INPUT_LEVEL_OFFSET = 0x10
INPUT_LEVEL_DB_MIN = -20
INPUT_LEVEL_DB_MAX = 20

# offset, maximum (decoded scale), canonical field id
_INOUT_BYTE_FIELDS: dict[str, tuple[int, int, str]] = {
    "inputLevel": (0x00, 52, "inputLevel"),
}

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
    "input-level": "inputLevel",
    "input-level-db": "inputLevel",
    "inputlevel": "inputLevel",
    "inputleveldb": "inputLevel",
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
    if key in _INOUT_BYTE_FIELDS or key in _USB_NIBBLE_FIELDS:
        return key
    allowed = sorted(set(_INOUT_BYTE_FIELDS) | set(_USB_NIBBLE_FIELDS) | set(_FIELD_ALIASES))
    raise ValueError(f"unknown system in/out field {field!r}; expected one of: {', '.join(allowed)}")


def build_system_inout_set_plan(field: str, value: int) -> PatchPlan:
    canonical = normalize_inout_field(field)
    if canonical in _INOUT_BYTE_FIELDS:
        offset, _maximum, field_id = _INOUT_BYTE_FIELDS[canonical]
        if not isinstance(value, int):
            raise ValueError(f"{field_id} must be an integer dB offset -20...+20")
        raw = encode_offset_db(value)
        address = live.address_adding(live.SYSTEM_IN_OUT, offset)
        data = [raw]
        encoded = f"{value} dB"
    else:
        offset, maximum, field_id = _USB_NIBBLE_FIELDS[canonical]
        if not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError(f"{field_id} must be an integer 0...{maximum}")
        address = live.address_adding(live.SYSTEM_IN_OUT, offset)
        data = live.nibbles_for(value, byte_count=2)
        encoded = str(value)
    return PatchPlan(
        id=f"system-inout-set:{field_id}",
        description=f"Set System IN/OUT {field_id} to {encoded}.",
        writes=[live.PatchWrite(f"System IN/OUT {field_id}", address, data)],
    )


def list_inout_fields() -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = [
        {
            "id": field_id,
            "offset": offset,
            "minimumDb": INPUT_LEVEL_DB_MIN,
            "maximumDb": INPUT_LEVEL_DB_MAX,
        }
        for offset, _maximum, field_id in _INOUT_BYTE_FIELDS.values()
    ]
    rows.extend(
        {"id": field_id, "offset": offset, "maximum": maximum}
        for offset, maximum, field_id in _USB_NIBBLE_FIELDS.values()
    )
    return sorted(rows, key=lambda row: str(row["id"]))


_INPUT_FIELD_ALIASES: dict[str, str] = {
    "input-level": "inputLevel",
    "input-level-db": "inputLevel",
    "inputlevel": "inputLevel",
    "inputleveldb": "inputLevel",
}


def encode_offset_db(db: int) -> int:
    if not isinstance(db, int):
        raise ValueError("input level must be an integer dB offset")
    raw = db + 32
    if not 12 <= raw <= 52:
        raise ValueError(f"input level must be {INPUT_LEVEL_DB_MIN}...{INPUT_LEVEL_DB_MAX} dB (got {db})")
    return raw


def system_input_setting_address(number: int) -> list[int]:
    if not 1 <= number <= 10:
        raise ValueError("system input setting number must be 1...10")
    return live.address_adding(
        live.SYSTEM_INPUT_SETTING_BASE,
        (number - 1) * live.SYSTEM_INPUT_SETTING_STRIDE,
    )


def normalize_inputs_field(field: str) -> str:
    key = field.strip()
    lowered = key.lower().replace("_", "-")
    if lowered in _INPUT_FIELD_ALIASES:
        return _INPUT_FIELD_ALIASES[lowered]
    if key == "inputLevel" or lowered == "name":
        return "name" if lowered == "name" else "inputLevel"
    allowed = sorted(set(_INPUT_FIELD_ALIASES) | {"inputLevel", "name"})
    raise ValueError(f"unknown system input field {field!r}; expected one of: {', '.join(allowed)}")


def build_system_inputs_set_plan(number: int, field: str, value: int | str) -> PatchPlan:
    canonical = normalize_inputs_field(field)
    base = system_input_setting_address(number)
    if canonical == "inputLevel":
        if not isinstance(value, int):
            raise ValueError("input level value must be an integer dB offset -20...+20")
        raw = encode_offset_db(value)
        field_label = "input level"
        encoded = f"{value} dB"
        writes = [
            live.PatchWrite(
                f"System Input {number} input level",
                live.address_adding(base, INPUT_LEVEL_OFFSET),
                [raw],
            ),
            live.PatchWrite(
                "System IN/OUT active input level",
                live.address_adding(live.SYSTEM_IN_OUT, 0x00),
                [raw],
            ),
        ]
        return PatchPlan(
            id=f"system-inputs-set:{number}:{canonical}",
            description=(
                f"Set System Input Setting {number} input level to {encoded} "
                f"and apply the same active IN/OUT input level."
            ),
            writes=writes,
        )
    else:
        if not isinstance(value, str):
            raise ValueError("input setting name must be a string")
        name = value.strip()
        if not name:
            raise ValueError("input setting name must not be empty")
        if len(name) > 16:
            raise ValueError("input setting name must be at most 16 ASCII characters")
        try:
            name.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError("input setting name must contain ASCII characters only") from error
        address = base
        data = patch_name_data(name)
        field_label = "name"
        encoded = name

    return PatchPlan(
        id=f"system-inputs-set:{number}:{canonical}",
        description=f"Set System Input Setting {number} {field_label} to {encoded}.",
        writes=[live.PatchWrite(f"System Input {number} {field_label}", address, data)],
    )


def list_inputs_fields() -> list[dict[str, str | int]]:
    return [
        {"id": "inputLevel", "offset": INPUT_LEVEL_OFFSET, "minimumDb": INPUT_LEVEL_DB_MIN, "maximumDb": INPUT_LEVEL_DB_MAX},
        {"id": "name", "offset": 0, "maxLength": 16},
    ]
