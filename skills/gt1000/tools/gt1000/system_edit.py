"""Typed builders for global system section writes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

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

# offset, maximum raw or decoded scale, canonical field id
_INOUT_OFFSET_DB_FIELDS: dict[str, tuple[int, str]] = {
    "inputLevel": (0x00, "inputLevel"),
    "totalNsThreshold": (0x22, "totalNsThreshold"),
}

_INOUT_SCALED_BYTE_FIELDS: dict[str, tuple[int, int, str]] = {
    "subOutputLevel": (0x3B, 100, "subOutputLevel"),
}

_INOUT_ENUM_FIELDS: dict[str, tuple[int, tuple[str, ...], str]] = {
    "phonesSetting": (0x21, ("MAIN OUT", "SUB OUT", "MAIN+SUB"), "phonesSetting"),
    "mainLevelSelect": (0x25, ("-10dBu", "+4dBu"), "mainLevelSelect"),
    "subLevelSelect": (0x3A, ("-10dBu", "+4dBu"), "subLevelSelect"),
    "subGroundLift": (0x3C, ("OFF", "ON"), "subGroundLift"),
    "mainStereoLink": (0x3D, ("OFF", "ON"), "mainStereoLink"),
    "subStereoLink": (0x3E, ("OFF", "ON"), "subStereoLink"),
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

_INOUT_FIELD_ALIASES: dict[str, str] = {
    "input-level": "inputLevel",
    "input-level-db": "inputLevel",
    "inputlevel": "inputLevel",
    "inputleveldb": "inputLevel",
    "total-ns-threshold": "totalNsThreshold",
    "totalnsthreshold": "totalNsThreshold",
    "phones-setting": "phonesSetting",
    "main-level-select": "mainLevelSelect",
    "sub-level-select": "subLevelSelect",
    "sub-output-level": "subOutputLevel",
    "sub-ground-lift": "subGroundLift",
    "main-stereo-link": "mainStereoLink",
    "sub-stereo-link": "subStereoLink",
    "total-reverb-level": "totalReverbLevel",
    "usb-dry-out": "usbDryOut",
    "usb-dry-to-efx": "usbDryToEfx",
    "usb-main-efx-out": "usbMainEfxOut",
    "usb-main-mix-level": "usbMainMixLevel",
    "usb-sub-efx-out": "usbSubEfxOut",
    "usb-sub-mix-level": "usbSubMixLevel",
}

_COMMON_FIELDS: dict[str, tuple[int, str, str]] = {
  # offset, kind, field_id — kind: metronomeBpm
    "metronomeBpm": (0x09, "metronomeBpm", "metronomeBpm"),
}

_COMMON_FIELD_ALIASES = {
    "metronome-bpm": "metronomeBpm",
    "metronomebpm": "metronomeBpm",
}

_MIDI_BYTE_FIELDS: dict[str, tuple[int, str, Any]] = {
    "rxChannel": (0x00, "rxChannel", {"minimum": 0, "maximum": 15, "display": "1...16"}),
    "omniMode": (0x01, "omniMode", ("OFF", "ON")),
    "txChannel": (0x02, "txChannel", "txChannel"),
    "syncClock": (0x03, "syncClock", ("AUTO", "INTERNAL", "MIDI(AUTO)", "USB(AUTO)")),
    "midiInThru": (0x04, "midiInThru", ("OFF", "MIDI OUT", "USB OUT", "USB/MIDI")),
    "usbInThru": (0x05, "usbInThru", ("OFF", "MIDI OUT", "USB OUT", "USB/MIDI")),
    "clockOut": (0x06, "clockOut", ("OFF", "ON")),
    "mapSelect": (0x08, "mapSelect", ("FIX", "PROG")),
}

_MIDI_FIELD_ALIASES = {
    "rx-channel": "rxChannel",
    "rxchannel": "rxChannel",
    "omni-mode": "omniMode",
    "omnimode": "omniMode",
    "tx-channel": "txChannel",
    "txchannel": "txChannel",
    "sync-clock": "syncClock",
    "syncclock": "syncClock",
    "midi-in-thru": "midiInThru",
    "midiinthru": "midiInThru",
    "usb-in-thru": "usbInThru",
    "usbinthru": "usbInThru",
    "clock-out": "clockOut",
    "clockout": "clockOut",
    "map-select": "mapSelect",
    "mapselect": "mapSelect",
}

_EFFECTS_BYTE_FIELDS: dict[str, tuple[int, str, Any]] = {
    "phraseLoopMode": (0x00, "phraseLoopMode", ("MONO", "STEREO")),
    "phraseLoopRecAction": (0x01, "phraseLoopRecAction", ("REC>PLAY>DUB", "REC>DUB>PLAY")),
    "metronomeLevel": (0x02, "metronomeLevel", {"minimum": 0, "maximum": 100}),
    "mainGroundLift": (0x03, "mainGroundLift", {"minimum": 1, "maximum": 6}),
    "totalMetronomeOut": (0x04, "totalMetronomeOut", ("MAIN OUT", "SUB OUT", "MAIN+SUB")),
}

_EFFECTS_FIELD_ALIASES = {
    "phrase-loop-mode": "phraseLoopMode",
    "phraseloopmode": "phraseLoopMode",
    "phrase-loop-rec-action": "phraseLoopRecAction",
    "phraselooprecaction": "phraseLoopRecAction",
    "metronome-level": "metronomeLevel",
    "metronomelevel": "metronomeLevel",
    "main-ground-lift": "mainGroundLift",
    "maingroundlift": "mainGroundLift",
    "total-metronome-out": "totalMetronomeOut",
    "totalmetronomeout": "totalMetronomeOut",
}

_PITCH_FIELDS: dict[str, tuple[int, str, Any]] = {
    "referencePitchHz": (0x00, "referencePitchHz", {"minimum": 435, "maximum": 445}),
    "polyTunerType": (0x04, "polyTunerType", ("6-REGULAR", "6-DROP D", "7-REGULAR", "7-DROP A", "4-B REGULAR", "5-B REGULAR")),
    "polyTunerOffset": (0x05, "polyTunerOffset", "polyTunerOffset"),
    "tunerOutput": (0x06, "tunerOutput", ("MUTE", "BYPASS", "THRU")),
}

_PITCH_FIELD_ALIASES = {
    "reference-pitch-hz": "referencePitchHz",
    "referencepitchhz": "referencePitchHz",
    "reference-pitch": "referencePitchHz",
    "poly-tuner-type": "polyTunerType",
    "polytunertype": "polyTunerType",
    "poly-tuner-offset": "polyTunerOffset",
    "polytuneroffset": "polyTunerOffset",
    "tuner-output": "tunerOutput",
    "tuneroutput": "tunerOutput",
}

_SETUP_EFCT_FIELDS: dict[str, tuple[int, str]] = {
    "mainDirMon": (0x01, "mainDirMon"),
    "subDirMon": (0x02, "subDirMon"),
}

_SETUP_EFCT_FIELD_ALIASES = {
    "main-dir-mon": "mainDirMon",
    "maindirmon": "mainDirMon",
    "sub-dir-mon": "subDirMon",
    "subdirmon": "subDirMon",
}


def _normalize_field(field: str, aliases: dict[str, str], allowed: set[str]) -> str:
    key = field.strip()
    lowered = key.lower().replace("_", "-")
    if lowered in aliases:
        return aliases[lowered]
    if key in allowed:
        return key
    raise ValueError(f"unknown field {field!r}; expected one of: {', '.join(sorted(allowed | set(aliases)))}")


def inout_field_accepts_string_value(field: str) -> bool:
    return normalize_inout_field(field) in _INOUT_ENUM_FIELDS


def normalize_inout_field(field: str) -> str:
    allowed = (
        set(_INOUT_OFFSET_DB_FIELDS)
        | set(_INOUT_SCALED_BYTE_FIELDS)
        | set(_INOUT_ENUM_FIELDS)
        | set(_USB_NIBBLE_FIELDS)
    )
    return _normalize_field(field, _INOUT_FIELD_ALIASES, allowed)


def normalize_common_field(field: str) -> str:
    return _normalize_field(field, _COMMON_FIELD_ALIASES, set(_COMMON_FIELDS))


def normalize_midi_field(field: str) -> str:
    return _normalize_field(field, _MIDI_FIELD_ALIASES, set(_MIDI_BYTE_FIELDS))


def normalize_effects_field(field: str) -> str:
    return _normalize_field(field, _EFFECTS_FIELD_ALIASES, set(_EFFECTS_BYTE_FIELDS))


def normalize_pitch_field(field: str) -> str:
    return _normalize_field(field, _PITCH_FIELD_ALIASES, set(_PITCH_FIELDS))


def normalize_setup_efct_field(field: str) -> str:
    return _normalize_field(field, _SETUP_EFCT_FIELD_ALIASES, set(_SETUP_EFCT_FIELDS))


def encode_offset_db(db: int) -> int:
    if not isinstance(db, int):
        raise ValueError("input level must be an integer dB offset")
    raw = db + 32
    if not 12 <= raw <= 52:
        raise ValueError(f"input level must be {INPUT_LEVEL_DB_MIN}...{INPUT_LEVEL_DB_MAX} dB (got {db})")
    return raw


def parse_bpm_tenths(raw_value: str) -> int:
    try:
        value = Decimal(raw_value.strip())
    except InvalidOperation as error:
        raise ValueError("BPM expects a number") from error
    bpm_tenths = value * 10
    if bpm_tenths != bpm_tenths.to_integral_value():
        raise ValueError("BPM supports one decimal place")
    bpm_tenths_int = int(bpm_tenths)
    if not 400 <= bpm_tenths_int <= 2500:
        raise ValueError("BPM must be 40.0...250.0")
    return bpm_tenths_int


def coerce_on_off(raw: str | int, *, field_id: str) -> int:
    if isinstance(raw, int):
        if raw in (0, 1):
            return raw
        raise ValueError(f"{field_id} must be OFF/ON or 0/1")
    text = str(raw).strip().lower().replace("_", "-")
    if text in {"off", "0", "false", "no"}:
        return 0
    if text in {"on", "1", "true", "yes"}:
        return 1
    raise ValueError(f"{field_id} must be OFF/ON or 0/1")


def coerce_enum(raw: str | int, values: tuple[str, ...], *, field_id: str) -> int:
    if isinstance(raw, int):
        if 0 <= raw < len(values):
            return raw
        raise ValueError(f"{field_id} must be 0...{len(values) - 1} or one of: {', '.join(values)}")
    text = str(raw).strip()
    lowered = text.lower().replace("_", "-")
    for index, label in enumerate(values):
        if text == label or lowered == label.lower().replace(" ", "-").replace("(", "").replace(")", ""):
            return index
        compact = label.lower().replace(" ", "").replace("(", "").replace(")", "").replace(">", "").replace("+", "")
        if lowered.replace(" ", "").replace(">", "").replace("+", "") == compact:
            return index
    raise ValueError(f"{field_id} must be one of: {', '.join(values)}")


def coerce_rx_channel(raw: str | int) -> int:
    if isinstance(raw, int):
        if 1 <= raw <= 16:
            return raw - 1
        if 0 <= raw <= 15:
            return raw
        raise ValueError("rxChannel must be 1...16 or raw 0...15")
    text = str(raw).strip().lower()
    if text.startswith("ch"):
        text = text[2:].lstrip(".")
    value = int(text)
    if 1 <= value <= 16:
        return value - 1
    raise ValueError("rxChannel must be 1...16")


def coerce_tx_channel(raw: str | int) -> int:
    if isinstance(raw, int):
        if 0 <= raw <= 16:
            return raw
        raise ValueError("txChannel must be 1...16, raw 0...15, or 16 for RX")
    text = str(raw).strip().lower()
    if text == "rx":
        return 16
    if text.startswith("ch"):
        text = text[2:].lstrip(".")
    value = int(text)
    if 1 <= value <= 16:
        return value - 1
    raise ValueError("txChannel must be 1...16, chN, or RX")


def coerce_poly_tuner_offset(raw: str | int) -> int:
    mapping = {"-5": 11, "-4": 12, "-3": 13, "-2": 14, "-1": 15, "----": 16, "0": 16}
    if isinstance(raw, int):
        if 11 <= raw <= 16:
            return raw
        raise ValueError("polyTunerOffset must be -5...-1, ----, or raw 11...16")
    text = str(raw).strip()
    if text in mapping:
        return mapping[text]
    raise ValueError("polyTunerOffset must be -5, -4, -3, -2, -1, or ----")


def coerce_int_range(raw: str | int, *, field_id: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw) if not isinstance(raw, int) else raw
    except ValueError as error:
        raise ValueError(f"{field_id} must be an integer {minimum}...{maximum}") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_id} must be an integer {minimum}...{maximum}")
    return value


def _system_byte_plan(section: str, base: list[int], field_id: str, offset: int, data: list[int], encoded: str) -> PatchPlan:
    address = live.address_adding(base, offset)
    return PatchPlan(
        id=f"system-{section}-set:{field_id}",
        description=f"Set System {section.upper()} {field_id} to {encoded}.",
        writes=[live.PatchWrite(f"System {section} {field_id}", address, data)],
    )


def build_system_inout_set_plan(field: str, value: int | str) -> PatchPlan:
    canonical = normalize_inout_field(field)
    if canonical in _INOUT_OFFSET_DB_FIELDS:
        offset, field_id = _INOUT_OFFSET_DB_FIELDS[canonical]
        db = coerce_int_range(value, field_id=field_id, minimum=INPUT_LEVEL_DB_MIN, maximum=INPUT_LEVEL_DB_MAX)
        data = [encode_offset_db(db)]
        encoded = f"{db} dB"
    elif canonical in _INOUT_SCALED_BYTE_FIELDS:
        offset, maximum, field_id = _INOUT_SCALED_BYTE_FIELDS[canonical]
        scaled = coerce_int_range(value, field_id=field_id, minimum=0, maximum=maximum)
        data = [scaled]
        encoded = str(scaled)
    elif canonical in _INOUT_ENUM_FIELDS:
        offset, labels, field_id = _INOUT_ENUM_FIELDS[canonical]
        raw = coerce_enum(value, labels, field_id=field_id)
        data = [raw]
        encoded = labels[raw]
    else:
        offset, maximum, field_id = _USB_NIBBLE_FIELDS[canonical]
        scaled = coerce_int_range(value, field_id=field_id, minimum=0, maximum=maximum)
        data = live.nibbles_for(scaled, byte_count=2)
        encoded = str(scaled)
    return _system_byte_plan("inout", live.SYSTEM_IN_OUT, field_id, offset, data, encoded)


def build_system_common_set_plan(field: str, value: str) -> PatchPlan:
    canonical = normalize_common_field(field)
    offset, kind, field_id = _COMMON_FIELDS[canonical]
    if kind == "metronomeBpm":
        bpm_tenths = parse_bpm_tenths(value)
        data = live.nibbles_for(bpm_tenths)
        encoded = f"{bpm_tenths / 10:.1f}"
    else:
        raise ValueError(f"unsupported System Common field {canonical}")
    return _system_byte_plan("common", live.SYSTEM_COMMON, field_id, offset, data, encoded)


def build_system_midi_set_plan(field: str, value: str | int) -> PatchPlan:
    canonical = normalize_midi_field(field)
    offset, field_id, spec = _MIDI_BYTE_FIELDS[canonical]
    if field_id == "rxChannel":
        raw = coerce_rx_channel(value)
        encoded = f"Ch.{raw + 1}"
    elif field_id == "txChannel":
        raw = coerce_tx_channel(value)
        encoded = "RX" if raw == 16 else f"Ch.{raw + 1}"
    elif isinstance(spec, tuple):
        raw = coerce_enum(value, spec, field_id=field_id)
        encoded = spec[raw]
    else:
        raise ValueError(f"unsupported System MIDI field {canonical}")
    return _system_byte_plan("midi", live.SYSTEM_MIDI, field_id, offset, [raw], encoded)


def build_system_effects_set_plan(field: str, value: str | int) -> PatchPlan:
    canonical = normalize_effects_field(field)
    offset, field_id, spec = _EFFECTS_BYTE_FIELDS[canonical]
    if field_id == "phraseLoopRecAction":
        aliases = {"rec-play-dub": 0, "rec-dub-play": 1}
        text = str(value).strip().lower().replace("_", "-")
        if text in aliases:
            raw = aliases[text]
            encoded = spec[raw]
        else:
            raw = coerce_enum(value, spec, field_id=field_id)
            encoded = spec[raw]
    elif isinstance(spec, tuple):
        raw = coerce_enum(value, spec, field_id=field_id)
        encoded = spec[raw]
    elif field_id == "mainGroundLift":
        lift = coerce_int_range(value, field_id=field_id, minimum=1, maximum=6)
        raw = lift - 1
        encoded = str(lift)
    else:
        bounds = spec
        raw = coerce_int_range(value, field_id=field_id, minimum=bounds["minimum"], maximum=bounds["maximum"])
        encoded = str(raw)
    return _system_byte_plan("effects", live.SYSTEM_EFFECTS, field_id, offset, [raw], encoded)


def build_system_pitch_set_plan(field: str, value: str | int) -> PatchPlan:
    canonical = normalize_pitch_field(field)
    offset, field_id, spec = _PITCH_FIELDS[canonical]
    if field_id == "referencePitchHz":
        hz = coerce_int_range(value, field_id=field_id, minimum=435, maximum=445)
        data = live.nibbles_for(hz)
        encoded = str(hz)
        return _system_byte_plan("pitch", live.SYSTEM_PITCH, field_id, offset, data, encoded)
    if isinstance(spec, tuple):
        raw = coerce_enum(value, spec, field_id=field_id)
        encoded = spec[raw]
    elif field_id == "polyTunerOffset":
        raw = coerce_poly_tuner_offset(value)
        encoded = str(value)
    else:
        raise ValueError(f"unsupported System Pitch field {canonical}")
    return _system_byte_plan("pitch", live.SYSTEM_PITCH, field_id, offset, [raw], encoded)


def build_system_setup_efct_set_plan(field: str, value: str | int) -> PatchPlan:
    canonical = normalize_setup_efct_field(field)
    offset, field_id = _SETUP_EFCT_FIELDS[canonical]
    raw = coerce_on_off(value, field_id=field_id)
    encoded = ("OFF", "ON")[raw]
    return _system_byte_plan("setup-efct", live.SETUP_EFCT, field_id, offset, [raw], encoded)


def list_inout_fields() -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = [
        {"id": field_id, "offset": offset, "minimumDb": INPUT_LEVEL_DB_MIN, "maximumDb": INPUT_LEVEL_DB_MAX}
        for offset, field_id in _INOUT_OFFSET_DB_FIELDS.values()
    ]
    rows.extend(
        {"id": field_id, "offset": offset, "maximum": maximum}
        for offset, maximum, field_id in _INOUT_SCALED_BYTE_FIELDS.values()
    )
    rows.extend(
        {"id": field_id, "offset": offset, "values": list(labels)}
        for offset, labels, field_id in _INOUT_ENUM_FIELDS.values()
    )
    rows.extend(
        {"id": field_id, "offset": offset, "maximum": maximum}
        for offset, maximum, field_id in _USB_NIBBLE_FIELDS.values()
    )
    return sorted(rows, key=lambda row: str(row["id"]))


def list_common_fields() -> list[dict[str, Any]]:
    return [{"id": "metronomeBpm", "offset": 0x09, "minimum": 40.0, "maximum": 250.0}]


def list_midi_fields() -> list[dict[str, Any]]:
    rows = []
    for field_id in _MIDI_BYTE_FIELDS:
        rows.append({"id": field_id})
    return rows


def list_effects_fields() -> list[dict[str, Any]]:
    return [{"id": field_id} for field_id in _EFFECTS_BYTE_FIELDS]


def list_pitch_fields() -> list[dict[str, Any]]:
    return [{"id": field_id} for field_id in _PITCH_FIELDS]


def list_setup_efct_fields() -> list[dict[str, Any]]:
    return [{"id": field_id, "values": ["OFF", "ON"]} for field_id in _SETUP_EFCT_FIELDS]


_INPUT_FIELD_ALIASES: dict[str, str] = {
    "input-level": "inputLevel",
    "input-level-db": "inputLevel",
    "inputlevel": "inputLevel",
    "inputleveldb": "inputLevel",
}


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
    return PatchPlan(
        id=f"system-inputs-set:{number}:{canonical}",
        description=f"Set System Input Setting {number} name to {name}.",
        writes=[live.PatchWrite(f"System Input {number} name", base, patch_name_data(name))],
    )


def list_inputs_fields() -> list[dict[str, str | int]]:
    return [
        {"id": "inputLevel", "offset": INPUT_LEVEL_OFFSET, "minimumDb": INPUT_LEVEL_DB_MIN, "maximumDb": INPUT_LEVEL_DB_MAX},
        {"id": "name", "offset": 0, "maxLength": 16},
    ]
