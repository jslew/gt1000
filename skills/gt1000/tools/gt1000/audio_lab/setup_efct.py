"""SetupEfct SysEx helpers (USB DIR MON and related runtime flags)."""

from __future__ import annotations

from typing import Any

try:
    from tools.gt1000 import live
except ModuleNotFoundError:
    import live


SETUP_EFCT_SIZE = live.SETUP_EFCT_SIZE


def decode_setup_efct(data: list[int]) -> dict[str, Any]:
    return {
        "leadingFixedRaw": data[0] if len(data) > 0 else None,
        "mainDirMonRaw": data[1] if len(data) > 1 else None,
        "mainDirMon": _decode_dir_mon(data[1]) if len(data) > 1 else None,
        "subDirMonRaw": data[2] if len(data) > 2 else None,
        "subDirMon": _decode_dir_mon(data[2]) if len(data) > 2 else None,
        "trailingFixedRaw": data[3] if len(data) > 3 else None,
        "note": "Parameter Guide: DIR MON cannot be saved; defaults ON at power-on. SysEx still sets runtime values.",
    }


def _decode_dir_mon(raw: int) -> str:
    if raw == 0:
        return "OFF"
    if raw == 1:
        return "ON"
    return f"UNKNOWN({raw})"


def read_setup_efct(timeout: float) -> dict[str, Any]:
    raw = live.read_system_section(live.SETUP_EFCT, SETUP_EFCT_SIZE, timeout)
    data = raw.get(live.address_key(live.SETUP_EFCT), [])
    if len(data) != 4:
        raise live.LiveMIDIError(f"SetupEfct read returned {len(data)} bytes, expected 4")
    return {"dataHex": live.hex_string(data), "decoded": decode_setup_efct(data)}


def build_dir_mon_data(
    current: list[int],
    *,
    main_off: bool,
    sub_off: bool,
) -> list[int]:
    if len(current) != 4:
        raise ValueError(f"SetupEfct must be 4 bytes, got {len(current)}")
    return [
        current[0],
        0x00 if main_off else 0x01,
        0x00 if sub_off else 0x01,
        current[3],
    ]


def prepare_usb_reamp_writes(current: list[int]) -> list[live.PatchWrite]:
    """DIR MON OFF on MAIN and SUB for computer pass-through / re-amp."""
    return [
        live.PatchWrite(
            "SetupEfct MAIN/SUB DIR MON OFF for USB re-amp",
            live.SETUP_EFCT,
            build_dir_mon_data(current, main_off=True, sub_off=True),
        )
    ]


def prepare_usb_reamp(timeout: float, *, verify: bool = True) -> dict[str, Any]:
    before = read_setup_efct(timeout)
    before_data = [int(byte, 16) for byte in before["dataHex"].split()]
    writes = prepare_usb_reamp_writes(before_data)
    live.write_data_sets(writes)
    result: dict[str, Any] = {
        "id": "audioPrepareReamp",
        "address": live.hex_bytes(live.SETUP_EFCT),
        "before": before,
        "writes": [{"label": write.label, "dataHex": live.hex_string(write.data)} for write in writes],
        "verified": None,
    }
    if verify:
        import time

        time.sleep(0.2)
        after = read_setup_efct(timeout)
        result["after"] = after
        expected = writes[0].data
        actual = after["decoded"]
        ok = (
            actual.get("mainDirMonRaw") == expected[1]
            and actual.get("subDirMonRaw") == expected[2]
        )
        result["verified"] = ok
        if not ok:
            raise live.LiveMIDIError("SetupEfct DIR MON verify failed after write")
    return result
