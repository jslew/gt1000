from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    from tools.gt1000 import live
except ModuleNotFoundError:
    import live


PATCH_COMMON = [0x10, 0x00, 0x00, 0x00]
PATCH_CTL1_FUNCTION = live.address_adding(PATCH_COMMON, 0x31)
TEMPORARY_ASSIGN_1 = [0x10, 0x00, 0x03, 0x00]
CHAIN_START = live.address_adding(live.TEMPORARY_PATCH_EFFECT, 0x68)
DIVIDER1 = live.address_adding(live.TEMPORARY_PATCH_EFFECT, 0x0D)
MIXER1 = live.address_adding(live.TEMPORARY_PATCH_EFFECT, 0x17)
SEND_RETURN1 = live.address_adding(live.TEMPORARY_PATCH_EFFECT, 0x35)

MAIN_OUT_L = 47
MAIN_OUT_R = 48
BYPASS_MAIN_L = 33
BYPASS_MAIN_R = 34

CANONICAL_FULL_CHAIN = [
    0, 34, 33, 47, 48, 1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 32, 27, 28, 29, 30, 35, 36, 37, 38,
    39, 40, 41, 42, 43, 31, 45, 46, 44,
]

CTL1_SOURCE = 0x08
CTL1_DIRECT_DIVIDER1_CHANNEL_SELECT = 47
ASSIGN_TARGET_DIVIDER1_CHANNEL_SELECT = 932
ASSIGN_TARGET_TUNER_ON_OFF = 987
LIVESET_FORMAT = "gt1000-agent-liveset-v1"
TSL_FORMAT = "gt1000-agent-tsl-json-v1"
VERIFY_READ_BATCH_SIZE = 4
DISABLED_ASSIGN_DATA = [
    0x00, 0x00, 0x00, 0x00, 0x08, 0x08, 0x00, 0x00, 0x00, 0x08, 0x00,
    0x00, 0x01, 0x08, 0x00, 0x14, 0x01, 0x0D, 0x1E, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x03, 0x0F, 0x0F, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x03, 0x0F, 0x0F, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]

PATCH_CONTROL_FIELDS = {
    "num1": (0x23, True), "num2": (0x25, True), "num3": (0x27, True),
    "num4": (0x29, True), "num5": (0x2B, True),
    "bank-down": (0x2D, False), "bank-up": (0x2F, False),
    "ctl1": (0x31, False), "ctl2": (0x33, False), "ctl3": (0x35, False),
    "ctl4": (0x37, False), "ctl5": (0x39, False), "ctl6": (0x3B, False), "ctl7": (0x3D, False),
    "cur-num": (0x3F, False), "exp1-sw": (0x41, False),
}

PATCH_EXP_PEDAL_FIELDS = {
    "exp1": 0x43,
    "exp2": 0x44,
    "exp3": 0x45,
}

SYSTEM_CONTROL_PREFERENCE_OFFSETS = {
    "num1": 0x23, "num2": 0x24, "num3": 0x25, "num4": 0x26, "num5": 0x27,
    "bank-down": 0x28, "bank-up": 0x29,
    "ctl1": 0x2A, "ctl2": 0x2B, "ctl3": 0x2C, "ctl4": 0x2D, "ctl5": 0x2E, "ctl6": 0x2F, "ctl7": 0x30,
    "cur-num": 0x31, "exp1-sw": 0x32, "exp1": 0x33, "exp2": 0x34, "exp3": 0x35,
}

CONTROL_FUNCTION_VALUES = {
    "off": 0,
    "matching-num": 1,
    "bank-up": 1,
    "bank-down": 2,
    "patch-plus-1": 3,
    "patch-minus-1": 4,
    "level-plus-10": 5,
    "level-plus-20": 6,
    "level-minus-10": 7,
    "level-minus-20": 8,
    "bpm-tap": 9,
    "delay1-tap": 10,
    "delay2-tap": 11,
    "delay3-tap": 12,
    "delay4-tap": 13,
    "master-delay-tap": 14,
    "tuner": 15,
    "amp-ctl1": 16,
    "amp-ctl2": 17,
    "comp": 18,
    "dist1": 19,
    "dist1-solo": 20,
    "dist2": 21,
    "dist2-solo": 22,
    "preamp1": 23,
    "preamp1-solo": 24,
    "preamp2": 25,
    "preamp2-solo": 26,
    "ns1": 27,
    "ns2": 28,
    "eq1": 29,
    "eq2": 30,
    "eq3": 31,
    "eq4": 32,
    "delay1": 33,
    "delay2": 34,
    "delay3": 35,
    "delay4": 36,
    "master-delay": 37,
    "chorus": 38,
    "fx1": 39,
    "fx2": 40,
    "fx3": 41,
    "fx1-trigger": 42,
    "fx2-trigger": 43,
    "fx3-trigger": 44,
    "reverb": 45,
    "pedal-fx": 46,
    "divider1-channel-select": 47,
    "divider2-channel-select": 48,
    "divider3-channel-select": 49,
    "send-return1": 50,
    "send-return2": 51,
    "looper": 52,
    "looper-stop": 53,
    "looper-clear": 54,
    "metronome": 55,
    "midi-start": 56,
    "mmc-play": 57,
    "master-delay-trigger": 58,
}

EXP_PEDAL_FUNCTION_VALUES = {
    "off": 0,
    "foot-volume": 1,
    "pedal-fx": 2,
    "foot-volume-pedal-fx": 3,
}

LED_COLOR_VALUES = {
    "off": 0,
    "red": 1,
    "blue": 2,
    "light-blue": 3,
    "orange": 4,
    "green": 5,
    "yellow": 6,
    "white": 7,
    "purple": 8,
    "pink": 9,
    "cyan": 10,
    "auto": 11,
    "auto-red": 12,
    "auto-blue": 13,
    "auto-light-blue": 14,
    "auto-orange": 15,
    "auto-green": 16,
    "auto-yellow": 17,
    "auto-white": 18,
    "auto-purple": 19,
    "auto-pink": 20,
    "auto-cyan": 21,
}

MASTER_KEY_VALUES = {
    "c-am": 0,
    "db-bbm": 1,
    "d-bm": 2,
    "eb-cm": 3,
    "e-c#m": 4,
    "f-dm": 5,
    "f#-d#m": 6,
    "g-em": 7,
    "ab-fm": 8,
    "a-f#m": 9,
    "bb-gm": 10,
    "b-g#m": 11,
}

PATCH_MASTER_FIELDS = {
    "level": (0x60, "byte", 0, 200),
    "patch-level": (0x60, "byte", 0, 200),
    "key": (0x65, "key", 0, 11),
    "master-key": (0x65, "key", 0, 11),
    "amp-ctl1": (0x66, "bool", 0, 1),
    "amp-control1": (0x66, "bool", 0, 1),
    "amp-ctl2": (0x67, "bool", 0, 1),
    "amp-control2": (0x67, "bool", 0, 1),
    "carryover": (0x99, "bool", 0, 1),
    "master-carryover": (0x99, "bool", 0, 1),
    "tempo-hold": (0x9A, "bool", 0, 1),
    "input-sensitivity": (0x9B, "byte", 0, 100),
}

PATCH_LED_COLOR_OFFSETS = {
    "num1": (0x00, 0x01), "num2": (0x02, 0x03), "num3": (0x04, 0x05),
    "num4": (0x06, 0x07), "num5": (0x08, 0x09),
    "bank-down": (0x0A, 0x0B), "bank-up": (0x0C, 0x0D),
    "ctl1": (0x0E, 0x0F), "ctl2": (0x10, 0x11), "ctl3": (0x12, 0x13),
    "exp1-sw": (0x14, 0x15),
}

EDITABLE_BLOCK_SIZES = {
    # Roland addresses are 7-bit. A table step from 00 12 00 to 00 13 00 is 0x80 bytes.
    "comp": 0x80,
    "dist1": 0x80,
    "dist2": 0x80,
    "preamp1": 0x80,
    "preamp2": 0x80,
    "ns1": 0x80,
    "ns2": 0x80,
    "eq1": 0x80,
    "eq2": 0x80,
    "eq3": 0x80,
    "eq4": 0x80,
    "delay1": 0x80,
    "delay2": 0x80,
    "delay3": 0x80,
    "delay4": 0x80,
    "masterDelay": 0x80,
    "chorus": 0x80,
    "fx1": 0x0D80,
    "fx2": 0x0D80,
    "fx3": 0x0D80,
    "reverb": 0x80,
    "pedalFx": 0x80,
}


@dataclass(frozen=True)
class PatchPlan:
    id: str
    description: str
    writes: list[live.PatchWrite]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "writeCount": len(self.writes),
            "writes": [
                {
                    "label": write.label,
                    "address": live.hex_bytes(write.address),
                    "dataHex": live.hex_string(write.data),
                    "messageHex": live.hex_string(write.message),
                }
                for write in self.writes
            ],
        }


def build_default_patch_plan(name: str = "PY DEFAULT") -> PatchPlan:
    writes = [
        live.PatchWrite("Patch name", live.TEMPORARY_PATCH_NAME, patch_name_data(name)),
        chain_write([0, BYPASS_MAIN_R, BYPASS_MAIN_L, MAIN_OUT_L, MAIN_OUT_R], "Minimal no-branch chain"),
        live.PatchWrite("CTL1 direct function off", PATCH_CTL1_FUNCTION, [0x00, 0x00]),
    ]
    writes.extend(assign_switch_writes(enabled=False))
    writes.extend(all_switchable_blocks_off())
    return PatchPlan(
        id="default",
        description="Minimal pass-through temporary patch: compressor placeholder, main outs, no branch, switchable blocks off.",
        writes=writes,
    )


def build_4cm_template_plan(name: str = "PY 4CM CTL1") -> PatchPlan:
    writes = [
        live.PatchWrite("Patch name", live.TEMPORARY_PATCH_NAME, patch_name_data(name)),
        chain_write(
            [0, 35, 14, 36, 1, 15, 37, 24, BYPASS_MAIN_R, BYPASS_MAIN_L, MAIN_OUT_L, MAIN_OUT_R],
            "4CM CTL1 divider template chain",
        ),
        live.PatchWrite("CTL1 direct function: DIVIDER 1 channel select", PATCH_CTL1_FUNCTION, [CTL1_DIRECT_DIVIDER1_CHANNEL_SELECT, 0x00]),
        live.PatchWrite("Divider 1 single mode, channel A", DIVIDER1, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x64, 0x02, 0x10]),
        live.PatchWrite("Mixer 1 centered", MIXER1, [0x00, 50, 50]),
        live.PatchWrite("Compressor on", block_address("comp"), [0x01, 0x00, 50, 50, 50, 50]),
        live.PatchWrite("Chorus clean path on", block_address("chorus"), [0x01, 0x01, 35, 45, 20, 35]),
        live.PatchWrite("Distortion 1 T-SCREAM path on", block_address("dist1"), [0x01, 15, 45, 50, 55, 50, 0, 0, 50]),
        live.PatchWrite("Delay 1 dirty path on", block_address("delay1"), [0x01] + live.nibbles_for(380) + [28, 8, 35, 100]),
        live.PatchWrite("Send/Return 1 4CM loop on", SEND_RETURN1, [0x01, 0x00, 0x06, 0x04, 0x06, 0x04, 0x00]),
    ]
    writes.extend(assign_switch_writes(enabled=False))
    return PatchPlan(
        id="4cm-template",
        description="4CM temporary patch: COMP -> DIV1, CTL1 toggles DIV1 A/B between chorus and T-SCREAM/delay paths, then SEND/RETURN 1.",
        writes=writes,
    )


def plan_by_id(plan_id: str, name: str | None = None) -> PatchPlan:
    if plan_id == "default":
        return build_default_patch_plan(name or "PY DEFAULT")
    if plan_id in {"4cm", "4cm-template"}:
        return build_4cm_template_plan(name or "PY 4CM CTL1")
    raise ValueError(f"unknown patch plan {plan_id}")


def plan_for_user_slot(plan: PatchPlan, slot: str) -> PatchPlan:
    temporary_base_value = live.seven_bit_address_value(PATCH_COMMON)
    writes = []
    for write in plan.writes:
        address_value = live.seven_bit_address_value(write.address)
        if address_value < temporary_base_value:
            raise ValueError(f"cannot remap address {live.hex_string(write.address)} into user patch memory")
        writes.append(live.PatchWrite(f"{slot} {write.label}", remap_clone_address(write.address, slot), write.data))
    return PatchPlan(
        id=f"{plan.id}:{slot}",
        description=f"{plan.description} Persistent target: {slot}.",
        writes=writes,
    )


def user_slot_base(slot: str) -> list[int]:
    return live.user_patch_base(slot)


def consecutive_user_slots(start_slot: str, count: int) -> list[str]:
    if count <= 0:
        raise ValueError("count must be positive")
    start = live.normalize_user_slot(start_slot)
    start_index = live.user_patch_zero_based_index(start)
    end_index = start_index + count - 1
    max_index = live.USER_BANK_COUNT * live.USER_PATCHES_PER_BANK - 1
    if end_index > max_index:
        raise ValueError("destination range exceeds U50-5")
    slots = []
    for index in range(start_index, end_index + 1):
        bank = index // live.USER_PATCHES_PER_BANK + 1
        patch = index % live.USER_PATCHES_PER_BANK + 1
        slots.append(f"U{bank:02d}-{patch}")
    return slots


def clone_read_requests(slot: str) -> list[live.PatchReadRequest]:
    return [
        live.PatchReadRequest(
            definition.label,
            remap_clone_address(definition.address, slot),
            definition.size,
        )
        for definition in clone_record_definitions()
    ]


def clone_core_read_requests(slot: str) -> list[live.PatchReadRequest]:
    return [
        live.PatchReadRequest(
            definition.label,
            remap_clone_address(definition.address, slot),
            definition.size,
        )
        for definition in clone_core_record_definitions()
    ]


def active_fx_algorithm_read_requests(slot: str, source_data: dict[str, list[int]]) -> list[live.PatchReadRequest]:
    return [
        live.PatchReadRequest(
            definition.label,
            remap_clone_address(definition.address, slot),
            definition.size,
        )
        for definition in active_fx_algorithm_record_definitions(slot, source_data)
    ]


def preset_restore_read_requests(slot: str) -> list[live.PatchReadRequest]:
    preset = live.normalize_preset_slot(slot)
    preset_base = live.preset_patch_base(preset)
    return [
        live.PatchReadRequest(
            definition.label,
            live.remap_temporary_patch_address(definition.address, preset_base),
            definition.size,
        )
        for definition in preset_restore_record_definitions()
    ]


def build_clone_plan(source_slot: str, destination_slot: str, source_data: dict[str, list[int]]) -> PatchPlan:
    source = live.normalize_user_slot(source_slot)
    destination = live.normalize_user_slot(destination_slot)
    if source == destination:
        raise ValueError("source and destination slots must be different")

    writes = []
    for definition in clone_record_definitions_for_data(source, source_data):
        source_address = remap_clone_address(definition.address, source)
        destination_address = remap_clone_address(definition.address, destination)
        data = source_data.get(live.address_key(source_address))
        if data is None:
            raise ValueError(f"missing source data for {definition.label} at {live.hex_string(source_address)}")
        expected_size = live.seven_bit_address_value(definition.size)
        if len(data) != expected_size:
            raise ValueError(f"{definition.label} expected {expected_size} bytes but read {len(data)}")
        writes.append(live.PatchWrite(f"Clone {definition.label}", destination_address, data))

    return PatchPlan(
        id=f"clone:{source}:{destination}",
        description=f"Clone known patch records from {source} to {destination}.",
        writes=writes,
    )


def build_preset_restore_plan(preset_slot: str, destination_slot: str, source_data: dict[str, list[int]]) -> PatchPlan:
    preset = live.normalize_preset_slot(preset_slot)
    destination = live.normalize_user_slot(destination_slot)
    preset_base = live.preset_patch_base(preset)
    writes = []
    for definition in preset_restore_record_definitions():
        source_address = live.remap_temporary_patch_address(definition.address, preset_base)
        destination_address = remap_clone_address(definition.address, destination)
        data = source_data.get(live.address_key(source_address))
        expected_size = live.seven_bit_address_value(definition.size)
        if data is None:
            raise ValueError(f"missing preset data for {definition.label} at {live.hex_string(source_address)}")
        if len(data) != expected_size:
            raise ValueError(f"{definition.label} expected {expected_size} bytes but read {len(data)}")
        writes.append(live.PatchWrite(f"Restore {preset} {definition.label}", destination_address, data))
    return PatchPlan(
        id=f"restore-preset:{preset}:{destination}",
        description=(
            f"Restore documented primary patch records from preset {preset} to {destination}. "
            "Preset extra STOMPBOX records are not copied because their preset addresses are not documented."
        ),
        writes=writes,
    )


def export_liveset_patch(slot: str, source_data: dict[str, list[int]]) -> dict[str, Any]:
    source = live.normalize_user_slot(slot)
    records = []
    for definition in clone_record_definitions_for_data(source, source_data):
        source_address = remap_clone_address(definition.address, source)
        data = source_data.get(live.address_key(source_address))
        expected_size = live.seven_bit_address_value(definition.size)
        if data is None:
            raise ValueError(f"missing source data for {definition.label} at {live.hex_string(source_address)}")
        if len(data) != expected_size:
            raise ValueError(f"{definition.label} expected {expected_size} bytes but read {len(data)}")
        records.append({
            "label": definition.label,
            "sourceAddress": live.hex_bytes(source_address),
            "temporaryAddress": live.hex_bytes(definition.address),
            "size": live.hex_bytes(definition.size),
            "dataHex": live.hex_string(data),
        })
    return {"sourceSlot": source, "records": records}


def build_liveset_export(patches: list[dict[str, Any]]) -> dict[str, Any]:
    if not patches:
        raise ValueError("liveset export requires at least one patch")
    return {
        "format": LIVESET_FORMAT,
        "patchCount": len(patches),
        "patches": patches,
    }


def build_liveset_import_plan(liveset: dict[str, Any], destination_start: str) -> PatchPlan:
    if liveset.get("format") != LIVESET_FORMAT:
        raise ValueError(f"unsupported liveset format; expected {LIVESET_FORMAT}")
    patches = liveset.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("liveset must contain at least one patch")
    destinations = consecutive_user_slots(destination_start, len(patches))
    definitions = {definition.label: definition for definition in clone_record_definitions()}
    writes = []
    for patch, destination in zip(patches, destinations):
        records = records_by_label(patch)
        if "Patch Common" not in records:
            raise ValueError("liveset patch missing Patch Common")
        for label, record in records.items():
            definition = definitions.get(label)
            if definition is None:
                raise ValueError(f"unknown liveset patch record {label}")
            data = data_from_record(record)
            expected_size = live.seven_bit_address_value(definition.size)
            if len(data) != expected_size:
                raise ValueError(f"{definition.label} expected {expected_size} bytes but found {len(data)}")
            destination_address = remap_clone_address(definition.address, destination)
            writes.append(live.PatchWrite(f"Import {destination} {definition.label}", destination_address, data))
    return PatchPlan(
        id=f"liveset-import:{destinations[0]}:{len(patches)}",
        description=f"Import {len(patches)} exported patches to consecutive user slots starting at {destinations[0]}.",
        writes=writes,
    )


def build_tsl_import_plan(tsl: dict[str, Any], destination_start: str) -> PatchPlan:
    patch_list = tsl_patch_list(tsl)
    if not patch_list:
        raise ValueError("TSL must contain at least one patch")
    if all(tsl_patch_payload(patch) is not None for patch in patch_list):
        return build_liveset_import_plan(liveset_from_tsl(tsl), destination_start)
    destinations = consecutive_user_slots(destination_start, len(patch_list))
    writes: list[live.PatchWrite] = []
    for index, (patch, destination) in enumerate(zip(patch_list, destinations), start=1):
        payload = tsl_patch_payload(patch)
        if payload is not None:
            records = records_by_label(payload)
            for definition in clone_record_definitions():
                record = records.get(definition.label)
                if record is None:
                    raise ValueError(f"TSL patch {index} missing {definition.label}")
                writes.append(live.PatchWrite(
                    f"Import {destination} {definition.label}",
                    remap_clone_address(definition.address, destination),
                    data_from_record(record),
                ))
            continue
        writes.extend(tsl_paramset_writes(patch, destination, index))
    return PatchPlan(
        id=f"tsl-import:{destinations[0]}:{len(patch_list)}",
        description=f"Import {len(patch_list)} TSL patches to consecutive user slots starting at {destinations[0]}.",
        writes=writes,
    )


def build_tsl_export(liveset: dict[str, Any], *, name: str = "GT-1000 CLI LIVESET", memo: str = "") -> dict[str, Any]:
    validate_liveset(liveset)
    patches = []
    for index, patch in enumerate(liveset["patches"], start=1):
        patches.append({
            "orderNumber": index,
            "name": liveset_patch_name(patch) or f"PATCH {index}",
            "memo": "",
            "data": {
                "format": LIVESET_FORMAT,
                "patch": clone_json_value(patch),
            },
        })
    return {
        "format": TSL_FORMAT,
        "formatRev": 1,
        "device": "GT-1000",
        "name": name,
        "memo": memo,
        "liveSetData": {
            "name": name,
            "memo": memo,
            "patchList": patches,
        },
    }


def tsl_summary(tsl: dict[str, Any]) -> dict[str, Any]:
    patch_list = tsl_patch_list(tsl)
    return {
        "format": tsl.get("format"),
        "formatRev": tsl.get("formatRev"),
        "device": tsl.get("device"),
        "name": tsl.get("name") or (tsl.get("liveSetData") or {}).get("name"),
        "patchCount": len(patch_list),
        "canImportRecords": all(tsl_patch_can_import(patch) for patch in patch_list),
        "patches": [
            {
                "index": index,
                "orderNumber": patch.get("orderNumber"),
                "name": tsl_patch_name(patch, index),
                "hasImportableRecords": tsl_patch_can_import(patch),
                "unsupportedParamSetKeys": unsupported_tsl_paramset_keys(patch),
            }
            for index, patch in enumerate(patch_list, start=1)
        ],
    }


def liveset_from_tsl(tsl: dict[str, Any]) -> dict[str, Any]:
    patches = []
    for index, patch in enumerate(tsl_patch_list(tsl), start=1):
        payload = tsl_patch_payload(patch)
        if payload is None:
            raise ValueError(f"TSL patch {index} does not contain importable {LIVESET_FORMAT} record data")
        patches.append(payload)
    return build_liveset_export(patches)


def tsl_patch_list(tsl: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(tsl, dict):
        raise ValueError("TSL JSON must be an object")
    live_set_data = tsl.get("liveSetData")
    candidates = []
    if isinstance(live_set_data, dict):
        candidates.append(live_set_data.get("patchList"))
    candidates.append(tsl.get("patchList"))
    for candidate in candidates:
        if candidate is None:
            continue
        if not isinstance(candidate, list):
            raise ValueError("TSL patchList must be a list")
        if not all(isinstance(patch, dict) for patch in candidate):
            raise ValueError("TSL patchList entries must be objects")
        return candidate
    data_patches = tsl_data_patch_list(tsl.get("data"), device=tsl.get("device"))
    if data_patches:
        return data_patches
    raise ValueError("TSL JSON does not contain liveSetData.patchList, patchList, or data patch entries")


def tsl_data_patch_list(data: Any, *, device: Any = None) -> list[dict[str, Any]]:
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("TSL data must be a list")
    patches: list[dict[str, Any]] = []
    for group_index, group in enumerate(data, start=1):
        entries = group if isinstance(group, list) else [group]
        for entry_index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                raise ValueError("TSL data patch entries must be objects")
            patch = clone_json_value(entry)
            patch.setdefault("orderNumber", len(patches) + 1)
            patch.setdefault("tslDataGroup", group_index)
            patch.setdefault("tslDataIndex", entry_index)
            if isinstance(device, str):
                patch.setdefault("tslDevice", device)
            patches.append(patch)
    return patches


def tsl_patch_can_import(patch: dict[str, Any]) -> bool:
    if tsl_patch_payload(patch) is not None:
        return True
    try:
        return bool(tsl_paramset_writes(patch, "U01-1", 1))
    except ValueError:
        return False


def tsl_paramset_writes(patch: dict[str, Any], destination: str, patch_index: int) -> list[live.PatchWrite]:
    if patch.get("tslDevice") != "GT-1000":
        raise ValueError(f"TSL patch {patch_index} is not a GT-1000 paramSet patch")
    param_set = patch.get("paramSet")
    if not isinstance(param_set, dict):
        raise ValueError(f"TSL patch {patch_index} does not contain importable {LIVESET_FORMAT} record data")
    specs = tsl_paramset_specs()
    unsupported = sorted(key for key in param_set if key not in specs and not is_ignorable_tsl_paramset_key(key))
    if unsupported:
        preview = ", ".join(unsupported[:5])
        suffix = "" if len(unsupported) <= 5 else f", ... ({len(unsupported)} total)"
        raise ValueError(f"TSL patch {patch_index} contains unsupported GT-1000 paramSet keys: {preview}{suffix}")
    writes: list[live.PatchWrite] = []
    for key, value in param_set.items():
        spec = specs.get(key)
        if spec is None:
            continue
        label, address, max_size = spec
        data = data_from_tsl_hex_list(key, value)
        if len(data) > max_size:
            raise ValueError(f"TSL {key} has {len(data)} bytes, exceeding supported size {max_size}")
        writes.append(live.PatchWrite(f"Import {destination} TSL {label}", remap_clone_address(address, destination), data))
    if not writes:
        raise ValueError(f"TSL patch {patch_index} does not contain supported GT-1000 paramSet records")
    return writes


def is_ignorable_tsl_paramset_key(key: str) -> bool:
    return key in {
        "UserPatch%PatchName",
        "UserPatch%Patch_0",
        "User_patch3%fx1MasterFx",
        "User_patch3%fx2MasterFx",
        "User_patch3%fx3MasterFx",
        "User_patch3%fx4MasterFx",
    }


def unsupported_tsl_paramset_keys(patch: dict[str, Any]) -> list[str]:
    if patch.get("tslDevice") != "GT-1000":
        return []
    param_set = patch.get("paramSet")
    if not isinstance(param_set, dict):
        return []
    specs = tsl_paramset_specs()
    return sorted(key for key in param_set if key not in specs and not is_ignorable_tsl_paramset_key(key))


def tsl_paramset_specs() -> dict[str, tuple[str, list[int], int]]:
    specs: dict[str, tuple[str, list[int], int]] = {
        "User_patch%common": ("Patch Common", live.TEMPORARY_PATCH_COMMON, 0x7E),
        "User_patch%stompBox": ("Patch Stompbox", live.TEMPORARY_PATCH_STOMPBOX, 0x68),
        "User_patch%led": ("Patch Led", live.TEMPORARY_PATCH_LED, 0x20),
        "User_patch%efct": ("Patch Effect A", live.TEMPORARY_PATCH_EFFECT, 0x68),
        "User_patch%efctB": ("Patch Effect B", live.address_adding(live.TEMPORARY_PATCH_EFFECT, 0x68), 0x39),
        "User_patch2%stompBox": ("Patch Stompbox 2", live.TEMPORARY_PATCH2_STOMPBOX, 0x11),
        "User_patch2%efct": ("Patch Effect 2", [0x10, 0x01, 0x0A, 0x00], 0x07),
        "User_patch2%mstDelay": ("Master Delay 2", [0x10, 0x01, 0x07, 0x00], 0x04),
        "User_patch3%stompBox": ("Patch Stompbox 3", live.TEMPORARY_PATCH3_STOMPBOX, 0x25),
        "User_patch3%fx(4)%fx": ("FX 4", [0x10, 0x02, 0x01, 0x00], 0x02),
    }
    for number in range(1, 17):
        specs[f"User_patch%assign({number})"] = (
            f"Assign {number}",
            live.address_adding(live.ASSIGN_BASE, (number - 1) * live.ASSIGN_STRIDE),
            0x2C,
        )
    block_keys = {
        "comp": "User_patch%comp",
        "dist1": "User_patch%dist(1)",
        "dist2": "User_patch%dist(2)",
        "preamp1": "User_patch%preamp(1)",
        "preamp2": "User_patch%preamp(2)",
        "ns1": "User_patch%ns(1)",
        "ns2": "User_patch%ns(2)",
        "eq1": "User_patch%eq(1)",
        "eq2": "User_patch%eq(2)",
        "eq3": "User_patch%eq(3)",
        "eq4": "User_patch%eq(4)",
        "delay1": "User_patch%delay(1)",
        "delay2": "User_patch%delay(2)",
        "delay3": "User_patch%delay(3)",
        "delay4": "User_patch%delay(4)",
        "masterDelay": "User_patch%mstDelay",
        "chorus": "User_patch%chorus",
        "fx1": "User_patch%fx(1)%fx",
        "fx2": "User_patch%fx(2)%fx",
        "fx3": "User_patch%fx(3)%fx",
        "reverb": "User_patch%reverb",
        "pedalFx": "User_patch%pedalFx",
    }
    blocks_by_id = {block.id: block for block in list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS)}
    for block_id, key in block_keys.items():
        block = blocks_by_id[block_id]
        specs[key] = (block.display_name, block.address, 0x80)
    for block in live.FX_ALGORITHM_BLOCKS:
        for number in range(1, 5):
            prefix = f"fx{number}"
            if block.id.startswith(prefix):
                suffix = block.id[len(prefix):]
                if number == 4:
                    key = f"User_patch3%fx4{suffix}"
                else:
                    key = f"User_patch%fx({number})%fx{suffix}"
                specs[key] = (block.display_name, block.address, 0x80)
                break
    for offset, suffix, label, size in [
        (0x01, "fx1ChorusBass", "FX 1 Chorus Bass", 0x06),
        (0x02, "fx1FlangerBass", "FX 1 Flanger Bass", 0x10),
        (0x03, "fx2ChorusBass", "FX 2 Chorus Bass", 0x06),
        (0x04, "fx2FlangerBass", "FX 2 Flanger Bass", 0x10),
        (0x05, "fx3ChorusBass", "FX 3 Chorus Bass", 0x06),
        (0x06, "fx3FlangerBass", "FX 3 Flanger Bass", 0x10),
    ]:
        specs[f"User_patch2%{suffix}"] = (label, [0x10, 0x01, offset, 0x00], size)
    for suffix, label, offset, size in [
        ("ChorusBass", "FX 4 Chorus Bass", 0x1C, 0x06),
        ("FlangerBass", "FX 4 Flanger Bass", 0x1D, 0x10),
        ("Dist", "FX 4 Dist", 0x22, 0x08),
    ]:
        specs[f"User_patch3%fx4{suffix}"] = (label, [0x10, 0x02, offset, 0x00], size)
    for number, offset in [(1, 0x1F), (2, 0x20), (3, 0x21)]:
        specs[f"User_patch3%fx{number}Dist"] = (
            f"FX {number} DIST",
            [0x10, 0x02, offset, 0x00],
            0x08,
        )
    return specs


def data_from_tsl_hex_list(key: str, value: Any) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"TSL {key} must be a list of hex bytes")
    data: list[int] = []
    for item in value:
        if isinstance(item, str):
            try:
                byte = int(item, 16)
            except ValueError as error:
                raise ValueError(f"TSL {key} contains invalid hex byte {item!r}") from error
        elif isinstance(item, int):
            byte = item
        else:
            raise ValueError(f"TSL {key} contains non-byte value")
        if not 0 <= byte <= 0x7F:
            raise ValueError(f"TSL {key} byte values must be 0...7F")
        data.append(byte)
    return data


def tsl_patch_payload(patch: dict[str, Any]) -> dict[str, Any] | None:
    data = patch.get("data")
    if isinstance(data, dict) and data.get("format") == LIVESET_FORMAT and isinstance(data.get("patch"), dict):
        records_by_label(data["patch"])
        return clone_json_value(data["patch"])
    if patch.get("format") == LIVESET_FORMAT and isinstance(patch.get("records"), list):
        records_by_label(patch)
        return clone_json_value(patch)
    return None


def tsl_patch_name(patch: dict[str, Any], index: int) -> str | None:
    for key in ("name", "PatchName", "patchName"):
        value = patch.get(key)
        if isinstance(value, str) and value:
            return value
    param_set = patch.get("paramSet")
    if isinstance(param_set, dict):
        for key in ("UserPatch%PatchName", "User_patch%common", "PatchName", "patchName"):
            value = param_set.get(key)
            if key == "User_patch%common" and isinstance(value, list):
                value = value[:16]
            name = patch_name_from_hex_bytes(value)
            if name:
                return name
    payload = tsl_patch_payload(patch)
    if payload is not None:
        return liveset_patch_name(payload)
    return None


def patch_name_from_hex_bytes(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    bytes_: list[int] = []
    for item in value:
        if isinstance(item, str):
            try:
                byte = int(item, 16)
            except ValueError:
                return None
        elif isinstance(item, int):
            byte = item
        else:
            return None
        if not 0 <= byte <= 0x7F:
            return None
        bytes_.append(byte)
    return bytes(bytes_).decode("ascii", errors="ignore").strip() or None


def liveset_summary(liveset: dict[str, Any]) -> dict[str, Any]:
    validate_liveset(liveset)
    patches = liveset["patches"]
    return {
        "format": LIVESET_FORMAT,
        "patchCount": len(patches),
        "patches": [
            {
                "index": index,
                "sourceSlot": patch.get("sourceSlot"),
                "patchName": liveset_patch_name(patch),
                "recordCount": len(patch.get("records", [])),
            }
            for index, patch in enumerate(patches, start=1)
        ],
    }


def move_liveset_patch(liveset: dict[str, Any], from_index: int, to_index: int) -> dict[str, Any]:
    validate_liveset(liveset)
    patches = list(liveset["patches"])
    validate_liveset_index("from_index", from_index, len(patches))
    validate_liveset_index("to_index", to_index, len(patches))
    patch = patches.pop(from_index - 1)
    patches.insert(to_index - 1, patch)
    return build_liveset_export(patches)


def copy_liveset_patch(liveset: dict[str, Any], from_index: int, to_index: int) -> dict[str, Any]:
    validate_liveset(liveset)
    patches = list(liveset["patches"])
    validate_liveset_index("from_index", from_index, len(patches))
    if not 1 <= to_index <= len(patches) + 1:
        raise ValueError(f"to_index must be 1...{len(patches) + 1}")
    patches.insert(to_index - 1, clone_json_value(patches[from_index - 1]))
    return build_liveset_export(patches)


def rename_liveset_patch(liveset: dict[str, Any], index: int, name: str) -> dict[str, Any]:
    validate_liveset(liveset)
    patches = [clone_json_value(patch) for patch in liveset["patches"]]
    validate_liveset_index("index", index, len(patches))
    patch = patches[index - 1]
    records = records_by_label(patch)
    common = records.get("Patch Common")
    if common is None:
        raise ValueError("liveset patch missing Patch Common")
    data = data_from_record(common)
    if len(data) < 16:
        raise ValueError("Patch Common record is too short for a patch name")
    common["dataHex"] = live.hex_string(patch_name_data(name) + data[16:])
    return build_liveset_export(patches)


def remove_liveset_patch(liveset: dict[str, Any], index: int) -> dict[str, Any]:
    validate_liveset(liveset)
    patches = list(liveset["patches"])
    validate_liveset_index("index", index, len(patches))
    patches.pop(index - 1)
    return build_liveset_export(patches)


def validate_liveset(liveset: dict[str, Any]) -> None:
    if liveset.get("format") != LIVESET_FORMAT:
        raise ValueError(f"unsupported liveset format; expected {LIVESET_FORMAT}")
    patches = liveset.get("patches")
    if not isinstance(patches, list):
        raise ValueError("liveset patches must be a list")
    for patch in patches:
        records_by_label(patch)


def validate_liveset_index(label: str, index: int, count: int) -> None:
    if not 1 <= index <= count:
        raise ValueError(f"{label} must be 1...{count}")


def clone_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone_json_value(item) for item in value]
    return value


def liveset_patch_name(patch: dict[str, Any]) -> str | None:
    records = records_by_label(patch)
    common = records.get("Patch Common")
    if common is None:
        return None
    try:
        return live.decode_patch_name(data_from_record(common)[:16])
    except ValueError:
        return None


def records_by_label(patch: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(patch, dict):
        raise ValueError("liveset patch must be an object")
    records = patch.get("records")
    if not isinstance(records, list):
        raise ValueError("liveset patch records must be a list")
    result = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("liveset record must be an object")
        label = record.get("label")
        if not isinstance(label, str):
            raise ValueError("liveset record label must be a string")
        if label in result:
            raise ValueError(f"duplicate liveset record {label}")
        result[label] = record
    return result


def data_from_record(record: dict[str, Any]) -> list[int]:
    data_hex = record.get("dataHex")
    if not isinstance(data_hex, str):
        raise ValueError("liveset record dataHex must be a string")
    compact = "".join(data_hex.split())
    if len(compact) % 2:
        raise ValueError("liveset record dataHex must contain whole bytes")
    try:
        values = list(bytes.fromhex(compact))
    except ValueError as error:
        raise ValueError("liveset record dataHex is not valid hexadecimal") from error
    if any(value > 0x7F for value in values):
        raise ValueError("liveset record contains non-7-bit MIDI data")
    return values


def apply_plan(plan: PatchPlan, *, timeout: float, verify: bool) -> dict[str, Any]:
    try:
        write_data_sets_resilient(plan.writes)
    except live.LiveMIDIError as error:
        raise live.LiveMIDIError(f"write phase failed for {plan.id}: {error}") from error
    result: dict[str, Any] = {"plan": plan.id, "writeCount": len(plan.writes), "verified": None}
    if verify:
        time.sleep(0.25)
        try:
            verification = verify_plan(plan, timeout=timeout)
        except live.LiveMIDIError as error:
            raise live.LiveMIDIError(f"verification phase failed for {plan.id}: {error}") from error
        result["verified"] = verification["ok"]
        result["verification"] = verification
    return result


def write_data_sets_resilient(writes: list[live.PatchWrite]) -> None:
    attempts = 3
    for attempt in range(attempts):
        try:
            live.write_data_sets(writes)
            return
        except live.LiveMIDIError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5)


def build_parameter_set_plan(block_id: str, parameter_id: str, raw_value: str, *, slot: str | None = None) -> PatchPlan:
    block = find_patch_block(block_id)
    parameter = next((parameter for parameter in block.parameters if parameter.id == parameter_id), None)
    if parameter is None:
        raise ValueError(f"unknown parameter {parameter_id} for block {block_id}")

    value = parse_parameter_value(parameter, raw_value)
    address = parameter_address(block, parameter.offset)
    write = live.PatchWrite(f"Set {block_id}.{parameter_id}", address, encode_parameter_value(parameter, value))
    plan = PatchPlan(
        id=f"set:{block_id}.{parameter_id}",
        description=f"Set {block.display_name} {parameter.display_name} to {value}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_raw_parameter_set_plan(
    block_id: str,
    offset: int,
    raw_value: str,
    *,
    width: str = "byte",
    slot: str | None = None,
) -> PatchPlan:
    block = find_patch_block(block_id)
    byte_count = parse_raw_width(width)
    editable_size = editable_block_size(block)
    if not 0 <= offset < editable_size:
        raise ValueError(f"offset must be 0...{editable_size - 1} for {block_id}")
    if offset + byte_count > editable_size:
        raise ValueError(f"{width} write at offset {offset} exceeds {block_id} editable size {editable_size}")
    try:
        value = int(raw_value.strip())
    except ValueError as error:
        raise ValueError("raw parameter value expects an integer") from error
    if byte_count == 1:
        if not 0 <= value <= 127:
            raise ValueError("byte value must be 0...127")
        data = [value]
    else:
        max_value = (1 << (byte_count * 4)) - 1
        if not 0 <= value <= max_value:
            raise ValueError(f"nibble value must be 0...{max_value}")
        data = live.nibbles_for(value, byte_count=byte_count)
    write = live.PatchWrite(f"Set {block_id}.offset{offset}", raw_parameter_address(block, offset), data)
    plan = PatchPlan(
        id=f"raw-set:{block_id}:{offset}:{width}",
        description=f"Set {block.display_name} raw offset {offset} to {value} using {width} encoding.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_bpm_set_plan(raw_value: str, *, slot: str | None = None) -> PatchPlan:
    bpm_tenths = parse_bpm_tenths(raw_value)
    write = live.PatchWrite("Set master BPM", live.TEMPORARY_PATCH_MASTER_BPM, live.nibbles_for(bpm_tenths))
    plan = PatchPlan(
        id="set:masterBpm",
        description=f"Set patch master BPM to {bpm_tenths / 10:.1f}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_chain_move_plan(
    chain_values: list[int],
    element: int,
    *,
    before: int | None = None,
    after: int | None = None,
    slot: str | None = None,
) -> PatchPlan:
    if (before is None) == (after is None):
        raise ValueError("chain move requires exactly one of before or after")
    if len(chain_values) != len(CANONICAL_FULL_CHAIN):
        raise ValueError(f"chain data must contain {len(CANONICAL_FULL_CHAIN)} elements")
    if set(chain_values) != set(CANONICAL_FULL_CHAIN):
        raise ValueError("chain data does not match the known GT-1000 chain element set")
    reference = before if before is not None else after
    if element == reference:
        raise ValueError("cannot move a chain element relative to itself")
    if element not in chain_values:
        raise ValueError(f"chain element {element} is not present in the current chain")
    if reference not in chain_values:
        raise ValueError(f"reference chain element {reference} is not present in the current chain")

    reordered = list(chain_values)
    reordered.remove(element)
    reference_index = reordered.index(reference)
    insert_index = reference_index if before is not None else reference_index + 1
    reordered.insert(insert_index, element)
    relation = "before" if before is not None else "after"
    write = chain_write(reordered, f"Move chain element {element} {relation} {reference}")
    plan = PatchPlan(
        id=f"move:chain:{element}:{relation}:{reference}",
        description=f"Move chain element {element} {relation} {reference}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_tuner_assign_plan(*, slot: str | None = None) -> PatchPlan:
    write = live.PatchWrite("Assign 16 tuner on CC80", assign_address(16), tuner_assign_data())
    plan = PatchPlan(
        id="set:tunerAssign",
        description="Map Assign 16 to tested TUNER ON/OFF target 987, source CC#80, active range 0...127.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_master_set_plan(field: str, raw_value: str, *, slot: str | None = None) -> PatchPlan:
    field_key = normalize_key(field)
    definition = PATCH_MASTER_FIELDS.get(field_key)
    if definition is None:
        raise ValueError(f"unknown patch master field {field}")
    offset, kind, minimum, maximum = definition
    value = parse_master_field_value(field_key, kind, raw_value, minimum, maximum)
    write = live.PatchWrite(f"Set patch master {field_key}", live.address_adding(live.TEMPORARY_PATCH_EFFECT, offset), encode_master_field_value(kind, value))
    plan = PatchPlan(
        id=f"master-set:{field_key}",
        description=f"Set patch master {field_key} to {value}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_master_set_record_plan(field: str, raw_value: str, patch_effect_data: list[int], *, slot: str) -> PatchPlan:
    field_key = normalize_key(field)
    definition = PATCH_MASTER_FIELDS.get(field_key)
    if definition is None:
        raise ValueError(f"unknown patch master field {field}")
    offset, kind, minimum, maximum = definition
    if offset >= len(patch_effect_data):
        raise ValueError(f"patch effect record is too short for {field_key}")
    value = parse_master_field_value(field_key, kind, raw_value, minimum, maximum)
    encoded = encode_master_field_value(kind, value)
    data = list(patch_effect_data)
    if offset + len(encoded) > len(data):
        raise ValueError(f"patch effect record is too short for {field_key}")
    data[offset:offset + len(encoded)] = encoded
    normalized_slot = live.normalize_user_slot(slot)
    write = live.PatchWrite(
        f"Set {normalized_slot} patch master {field_key}",
        remap_clone_address(live.TEMPORARY_PATCH_EFFECT, normalized_slot),
        data,
    )
    return PatchPlan(
        id=f"master-set:{field_key}:{normalized_slot}",
        description=f"Set patch master {field_key} to {value} in {normalized_slot}.",
        writes=[write],
    )


def build_assign_cc_plan(
    number: int,
    *,
    target: int,
    target_min: int,
    target_max: int,
    source_cc: int,
    mode: str,
    active_min: int = 0,
    active_max: int = 127,
    slot: str | None = None,
) -> PatchPlan:
    source = assign_source_for_cc(source_cc)
    if mode not in {"toggle", "moment"}:
        raise ValueError("assign mode must be toggle or moment")
    for label, value in {"target": target, "target_min": target_min, "target_max": target_max}.items():
        if not 0 <= value <= 16383:
            raise ValueError(f"{label} must be 0...16383")
    if not 0 <= active_min <= 127 or not 0 <= active_max <= 127:
        raise ValueError("active range must be 0...127")
    if active_min > active_max:
        raise ValueError("active range low must be <= high")

    data = assign_data(
        target=target,
        target_min=target_min + 32768,
        target_max=target_max + 32768,
        source=source,
        mode=0x00 if mode == "toggle" else 0x01,
        active_min=active_min,
        active_max=active_max,
        midi_cc=source_cc,
    )
    write = live.PatchWrite(f"Assign {number} target {target} from CC{source_cc}", assign_address(number), data)
    plan = PatchPlan(
        id=f"set:assign{number}:cc{source_cc}:target{target}",
        description=f"Map Assign {number} target {target} to MIDI CC#{source_cc}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_assign_set_plan(
    number: int,
    *,
    enabled: bool,
    target: int,
    target_min: int,
    target_max: int,
    source: int,
    mode: str,
    active_min: int = 0,
    active_max: int = 127,
    midi_channel: int = 0,
    midi_cc: int = 0,
    midi_cc_min: int = 0,
    midi_cc_max: int = 0,
    midi_pc: int = 0,
    midi_bank_msb: int = 128,
    midi_bank_lsb: int = 128,
    slot: str | None = None,
) -> PatchPlan:
    if mode not in {"toggle", "moment"}:
        raise ValueError("assign mode must be toggle or moment")
    validate_assign_int("target", target, 0, 16383)
    validate_assign_int("target_min", target_min, 0, 16383)
    validate_assign_int("target_max", target_max, 0, 16383)
    validate_assign_int("source", source, 0, 127)
    validate_assign_int("active_min", active_min, 0, 16383)
    validate_assign_int("active_max", active_max, 0, 16383)
    validate_assign_int("midi_channel", midi_channel, 0, 16)
    validate_assign_int("midi_cc", midi_cc, 0, 127)
    validate_assign_int("midi_cc_min", midi_cc_min, 0, 16383)
    validate_assign_int("midi_cc_max", midi_cc_max, 0, 16383)
    validate_assign_int("midi_pc", midi_pc, 0, 127)
    validate_assign_int("midi_bank_msb", midi_bank_msb, 0, 16383)
    validate_assign_int("midi_bank_lsb", midi_bank_lsb, 0, 16383)
    if active_min > active_max:
        raise ValueError("active range low must be <= high")

    data = assign_data(
        enabled=enabled,
        target=target,
        target_min=target_min + 32768,
        target_max=target_max + 32768,
        source=source,
        mode=0x00 if mode == "toggle" else 0x01,
        active_min=active_min,
        active_max=active_max,
        midi_channel=midi_channel,
        midi_cc=midi_cc,
        midi_cc_min=midi_cc_min,
        midi_cc_max=midi_cc_max,
        midi_pc=midi_pc,
        midi_bank_msb=midi_bank_msb,
        midi_bank_lsb=midi_bank_lsb,
    )
    write = live.PatchWrite(f"Assign {number} raw target {target}", assign_address(number), data)
    plan = PatchPlan(
        id=f"set:assign{number}:target{target}:source{source}",
        description=f"Set Assign {number} to target {target}, source {source}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_control_set_plan(
    control: str,
    function_name: str,
    *,
    mode: str = "toggle",
    slot: str | None = None,
) -> PatchPlan:
    control_key = normalize_key(control)
    if control_key in PATCH_EXP_PEDAL_FIELDS:
        return build_exp_pedal_set_plan(control_key, function_name, slot=slot)
    if control_key not in PATCH_CONTROL_FIELDS:
        raise ValueError(f"unknown control {control}")
    function_key = normalize_key(function_name)
    if function_key not in CONTROL_FUNCTION_VALUES:
        raise ValueError(f"unknown control function {function_name}")
    if control_key.startswith("num") and function_key == "bank-up":
        raise ValueError("NUM controls use matching-num instead of bank-up for raw function 1")
    if not control_key.startswith("num") and function_key == "matching-num":
        raise ValueError("matching-num is only valid for NUM controls")
    mode_value = parse_mode(mode)
    offset, _is_num = PATCH_CONTROL_FIELDS[control_key]
    write = live.PatchWrite(f"Set {control_key} control", live.address_adding(PATCH_COMMON, offset), [CONTROL_FUNCTION_VALUES[function_key], mode_value])
    plan = PatchPlan(
        id=f"control:{control_key}:{function_key}",
        description=f"Set patch-local {control_key} to {function_key} / {mode}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_system_control_set_plan(control: str, function_name: str, *, mode: str = "toggle") -> PatchPlan:
    control_key = normalize_key(control)
    if control_key in PATCH_EXP_PEDAL_FIELDS:
        return build_system_exp_pedal_set_plan(control_key, function_name)
    if control_key not in PATCH_CONTROL_FIELDS:
        raise ValueError(f"unknown system control {control}")
    function_key = normalize_key(function_name)
    if function_key not in CONTROL_FUNCTION_VALUES:
        raise ValueError(f"unknown control function {function_name}")
    if control_key.startswith("num") and function_key == "bank-up":
        raise ValueError("NUM controls use matching-num instead of bank-up for raw function 1")
    if not control_key.startswith("num") and function_key == "matching-num":
        raise ValueError("matching-num is only valid for NUM controls")
    mode_value = parse_mode(mode)
    patch_offset, _is_num = PATCH_CONTROL_FIELDS[control_key]
    system_offset = patch_offset - 0x23
    write = live.PatchWrite(
        f"Set system {control_key} control",
        live.address_adding(live.SYSTEM_CONTROL, system_offset),
        [CONTROL_FUNCTION_VALUES[function_key], mode_value],
    )
    return PatchPlan(
        id=f"system-control:{control_key}:{function_key}",
        description=f"Set global/system {control_key} to {function_key} / {mode}.",
        writes=[write],
    )


def build_led_set_plan(control: str, state: str, color: str, *, slot: str | None = None) -> PatchPlan:
    control_key = normalize_key(control)
    state_key = normalize_key(state)
    color_key = normalize_key(color)
    if control_key not in PATCH_LED_COLOR_OFFSETS:
        raise ValueError(f"unknown LED control {control}")
    if state_key not in {"off", "on"}:
        raise ValueError("LED state must be off or on")
    if color_key not in LED_COLOR_VALUES:
        raise ValueError(f"unknown LED color {color}")
    value = LED_COLOR_VALUES[color_key]
    if state_key == "off" and value > 10:
        raise ValueError("LED off colors support off/red/blue/light-blue/orange/green/yellow/white/purple/pink/cyan only")
    offset = PATCH_LED_COLOR_OFFSETS[control_key][0 if state_key == "off" else 1]
    write = live.PatchWrite(f"Set {control_key} LED {state_key}", live.address_adding(live.TEMPORARY_PATCH_LED, offset), [value])
    plan = PatchPlan(
        id=f"led:{control_key}:{state_key}:{color_key}",
        description=f"Set {control_key} {state_key} LED color to {color_key}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_exp_pedal_set_plan(control_key: str, function_name: str, *, slot: str | None = None) -> PatchPlan:
    function_key = normalize_key(function_name)
    if function_key not in EXP_PEDAL_FUNCTION_VALUES:
        raise ValueError(f"unknown EXP pedal function {function_name}")
    offset = PATCH_EXP_PEDAL_FIELDS[control_key]
    write = live.PatchWrite(f"Set {control_key} pedal", live.address_adding(PATCH_COMMON, offset), [EXP_PEDAL_FUNCTION_VALUES[function_key]])
    plan = PatchPlan(
        id=f"control:{control_key}:{function_key}",
        description=f"Set patch-local {control_key} to {function_key}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_system_exp_pedal_set_plan(control_key: str, function_name: str) -> PatchPlan:
    function_key = normalize_key(function_name)
    if function_key not in EXP_PEDAL_FUNCTION_VALUES:
        raise ValueError(f"unknown EXP pedal function {function_name}")
    patch_offset = PATCH_EXP_PEDAL_FIELDS[control_key]
    system_offset = patch_offset - 0x23
    write = live.PatchWrite(
        f"Set system {control_key} pedal",
        live.address_adding(live.SYSTEM_CONTROL, system_offset),
        [EXP_PEDAL_FUNCTION_VALUES[function_key]],
    )
    return PatchPlan(
        id=f"system-control:{control_key}:{function_key}",
        description=f"Set global/system {control_key} to {function_key}.",
        writes=[write],
    )


def build_control_preference_plan(control: str, preference: str) -> PatchPlan:
    control_key = normalize_key(control)
    preference_key = normalize_key(preference)
    if control_key not in SYSTEM_CONTROL_PREFERENCE_OFFSETS:
        raise ValueError(f"unknown control preference {control}")
    if preference_key not in {"patch", "system"}:
        raise ValueError("control preference must be patch or system")
    value = 0 if preference_key == "patch" else 1
    write = live.PatchWrite(
        f"Set {control_key} control preference",
        live.address_adding(live.SYSTEM_CONTROL, SYSTEM_CONTROL_PREFERENCE_OFFSETS[control_key]),
        [value],
    )
    return PatchPlan(
        id=f"control-preference:{control_key}:{preference_key}",
        description=f"Set {control_key} effective control preference to {preference_key}.",
        writes=[write],
    )


def build_rename_plan(name: str, *, slot: str | None = None) -> PatchPlan:
    write = live.PatchWrite("Patch name", live.TEMPORARY_PATCH_NAME, patch_name_data(name))
    plan = PatchPlan(
        id="rename",
        description=f"Rename patch to {name!r}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


def build_exchange_plan(slot_a: str, slot_b: str, data_a: dict[str, list[int]], data_b: dict[str, list[int]]) -> PatchPlan:
    a = live.normalize_user_slot(slot_a)
    b = live.normalize_user_slot(slot_b)
    if a == b:
        raise ValueError("exchange slots must be different")
    writes = []
    for definition in clone_record_definitions_for_data(a, data_a):
        address_a = remap_clone_address(definition.address, a)
        address_b = remap_clone_address(definition.address, b)
        record_a = data_a.get(live.address_key(address_a))
        expected_size = live.seven_bit_address_value(definition.size)
        if record_a is None:
            raise ValueError(f"missing source data for {definition.label}")
        if len(record_a) != expected_size:
            raise ValueError(f"{definition.label} expected {expected_size} bytes")
        writes.append(live.PatchWrite(f"Exchange {definition.label} {a} to {b}", address_b, record_a))
    for definition in clone_record_definitions_for_data(b, data_b):
        address_a = remap_clone_address(definition.address, a)
        address_b = remap_clone_address(definition.address, b)
        record_b = data_b.get(live.address_key(address_b))
        expected_size = live.seven_bit_address_value(definition.size)
        if record_b is None:
            raise ValueError(f"missing source data for {definition.label}")
        if len(record_b) != expected_size:
            raise ValueError(f"{definition.label} expected {expected_size} bytes")
        writes.append(live.PatchWrite(f"Exchange {definition.label} {b} to {a}", address_a, record_b))
    return PatchPlan(
        id=f"exchange:{a}:{b}",
        description=f"Exchange known patch records between {a} and {b}.",
        writes=writes,
    )


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


def parse_master_field_value(field_key: str, kind: str, raw_value: str, minimum: int, maximum: int) -> int:
    text = raw_value.strip()
    if kind == "bool":
        lowered = normalize_key(text)
        if lowered in {"on", "true", "yes", "1"}:
            return 1
        if lowered in {"off", "false", "no", "0"}:
            return 0
        raise ValueError(f"{field_key} expects on/off")
    if kind == "key" and not text.isdigit():
        key = normalize_key(text).replace("(", "-").replace(")", "")
        if key not in MASTER_KEY_VALUES:
            raise ValueError(f"{field_key} expects one of: {', '.join(MASTER_KEY_VALUES)}")
        return MASTER_KEY_VALUES[key]
    try:
        value = int(text)
    except ValueError as error:
        raise ValueError(f"{field_key} expects an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_key} must be {minimum}...{maximum}")
    return value


def encode_master_field_value(kind: str, value: int) -> list[int]:
    if kind == "nibbles2":
        return live.nibbles_for(value, byte_count=2)
    return [value]


def parse_parameter_value(parameter: live.Parameter, raw_value: str) -> int:
    text = raw_value.strip()
    if parameter.kind == "bool":
        lowered = text.lower()
        if lowered in {"on", "true", "1"}:
            return 1
        if lowered in {"off", "false", "0"}:
            return 0
        raise ValueError(f"{parameter.id} expects on/off")
    if parameter.kind == "type" and not text.isdigit():
        matches = [index for index, value in enumerate(parameter.values) if value.lower() == text.lower()]
        if not matches:
            raise ValueError(f"{parameter.id} expects one of: {', '.join(parameter.values)}")
        return matches[0]
    try:
        value = int(text)
    except ValueError as error:
        raise ValueError(f"{parameter.id} expects an integer") from error
    if parameter.kind == "type" and parameter.values and not 0 <= value < len(parameter.values):
        raise ValueError(f"{parameter.id} type value must be 0...{len(parameter.values) - 1}")
    if parameter.kind in {"byte", "type"} and not 0 <= value <= 127:
        raise ValueError(f"{parameter.id} byte value must be 0...127")
    if parameter.kind == "bool" and value not in {0, 1}:
        raise ValueError(f"{parameter.id} expects 0 or 1")
    max_nibble_value = (1 << (parameter.byte_count * 4)) - 1
    if parameter.kind == "nibbles" and not 0 <= value <= max_nibble_value:
        raise ValueError(f"{parameter.id} nibble value must be 0...{max_nibble_value}")
    return value


def encode_parameter_value(parameter: live.Parameter, value: int) -> list[int]:
    if parameter.kind == "nibbles":
        return live.nibbles_for(value, byte_count=parameter.byte_count)
    return [value]


def verify_plan(plan: PatchPlan, *, timeout: float) -> dict[str, Any]:
    requests = [write.read_request for write in plan.writes]
    raw = read_data_sets_sequential_session(timeout=timeout, requests=requests)
    checks = []
    for write in plan.writes:
        key = live.address_key(write.address)
        actual = raw.get(key)
        ok = actual is not None and actual[:len(write.data)] == write.data
        checks.append({
            "label": write.label,
            "address": live.hex_bytes(write.address),
            "ok": ok,
            "expectedHex": live.hex_string(write.data),
            "actualHex": live.hex_string(actual or []),
        })
    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def read_data_sets_sequential_session(*, timeout: float, requests: list[live.PatchReadRequest]) -> dict[str, list[int]]:
    if not requests:
        return {}
    return live.read_data_sets(timeout=timeout, requests=requests)


def read_data_sets_batched(*, timeout: float, requests: list[live.PatchReadRequest]) -> dict[str, list[int]]:
    raw: dict[str, list[int]] = {}
    for start in range(0, len(requests), VERIFY_READ_BATCH_SIZE):
        raw.update(read_data_set_batch_resilient(timeout=timeout, requests=requests[start:start + VERIFY_READ_BATCH_SIZE]))
        time.sleep(0.05)
    return raw


def read_data_set_batch_resilient(*, timeout: float, requests: list[live.PatchReadRequest]) -> dict[str, list[int]]:
    if not requests:
        return {}
    attempts = 3
    for attempt in range(attempts):
        try:
            return live.read_data_sets(timeout=timeout, requests=requests)
        except live.LiveMIDIError:
            if attempt == attempts - 1:
                if len(requests) == 1:
                    raise
                break
            time.sleep(0.25)
    midpoint = len(requests) // 2
    raw = read_data_set_batch_resilient(timeout=timeout, requests=requests[:midpoint])
    raw.update(read_data_set_batch_resilient(timeout=timeout, requests=requests[midpoint:]))
    return raw


def clone_record_definitions() -> list[live.PatchReadRequest]:
    return [
        *primary_patch_record_definitions(include_fx_algorithms=True),
        live.PatchReadRequest("Patch Stompbox 2", live.TEMPORARY_PATCH2_STOMPBOX, [0x00, 0x00, 0x00, 0x11]),
        live.PatchReadRequest("Patch Stompbox 3", live.TEMPORARY_PATCH3_STOMPBOX, [0x00, 0x00, 0x00, 0x25]),
        *extended_patch_record_definitions(),
    ]


def clone_core_record_definitions() -> list[live.PatchReadRequest]:
    return [
        *primary_patch_record_definitions(include_fx_algorithms=False),
        live.PatchReadRequest("Patch Stompbox 2", live.TEMPORARY_PATCH2_STOMPBOX, [0x00, 0x00, 0x00, 0x11]),
        live.PatchReadRequest("Patch Stompbox 3", live.TEMPORARY_PATCH3_STOMPBOX, [0x00, 0x00, 0x00, 0x25]),
        *extended_patch_record_definitions(),
    ]


def extended_patch_record_definitions() -> list[live.PatchReadRequest]:
    return [
        live.PatchReadRequest("FX 1 Chorus Bass", [0x10, 0x01, 0x01, 0x00], [0x00, 0x00, 0x00, 0x06]),
        live.PatchReadRequest("FX 1 Flanger Bass", [0x10, 0x01, 0x02, 0x00], [0x00, 0x00, 0x00, 0x10]),
        live.PatchReadRequest("FX 2 Chorus Bass", [0x10, 0x01, 0x03, 0x00], [0x00, 0x00, 0x00, 0x06]),
        live.PatchReadRequest("FX 2 Flanger Bass", [0x10, 0x01, 0x04, 0x00], [0x00, 0x00, 0x00, 0x10]),
        live.PatchReadRequest("FX 3 Chorus Bass", [0x10, 0x01, 0x05, 0x00], [0x00, 0x00, 0x00, 0x06]),
        live.PatchReadRequest("FX 3 Flanger Bass", [0x10, 0x01, 0x06, 0x00], [0x00, 0x00, 0x00, 0x10]),
        live.PatchReadRequest("Master Delay 2", [0x10, 0x01, 0x07, 0x00], [0x00, 0x00, 0x00, 0x04]),
        live.PatchReadRequest("Patch Effect 2", [0x10, 0x01, 0x0A, 0x00], [0x00, 0x00, 0x00, 0x07]),
        live.PatchReadRequest("FX 4 Chorus Bass", [0x10, 0x02, 0x1C, 0x00], [0x00, 0x00, 0x00, 0x06]),
        live.PatchReadRequest("FX 4 Flanger Bass", [0x10, 0x02, 0x1D, 0x00], [0x00, 0x00, 0x00, 0x10]),
        live.PatchReadRequest("FX 1 DIST", [0x10, 0x02, 0x1F, 0x00], [0x00, 0x00, 0x00, 0x08]),
        live.PatchReadRequest("FX 2 DIST", [0x10, 0x02, 0x20, 0x00], [0x00, 0x00, 0x00, 0x08]),
        live.PatchReadRequest("FX 3 DIST", [0x10, 0x02, 0x21, 0x00], [0x00, 0x00, 0x00, 0x08]),
        live.PatchReadRequest("FX 4 Dist", [0x10, 0x02, 0x22, 0x00], [0x00, 0x00, 0x00, 0x08]),
    ]


def clone_record_definitions_for_data(slot: str, source_data: dict[str, list[int]]) -> list[live.PatchReadRequest]:
    source = live.normalize_user_slot(slot)
    required_labels = {"Patch Common", "Patch Effect"}
    return [
        *[
            definition
            for definition in clone_core_record_definitions()
            if definition.label in required_labels or live.address_key(remap_clone_address(definition.address, source)) in source_data
        ],
        *[
            definition
            for definition in active_fx_algorithm_record_definitions(source, source_data)
            if live.address_key(remap_clone_address(definition.address, source)) in source_data
        ],
    ]


def active_fx_algorithm_record_definitions(slot: str, source_data: dict[str, list[int]]) -> list[live.PatchReadRequest]:
    source = live.normalize_user_slot(slot)
    definitions = []
    for number in range(1, 5):
        summary = next((block for block in live.SUMMARY_BLOCKS if block.id == f"fx{number}"), None)
        if summary is None:
            continue
        summary_address = remap_clone_address(summary.address, source)
        summary_data = source_data.get(live.address_key(summary_address))
        if summary_data is None or len(summary_data) < 2:
            continue
        type_index = summary_data[1]
        if not 0 <= type_index < len(live.FX_ALGORITHM_TEMPLATES):
            continue
        suffix = live.FX_ALGORITHM_TEMPLATES[type_index][0]
        definition = next((block for block in live.FX_ALGORITHM_BLOCKS if block.id == f"fx{number}{suffix}"), None)
        if definition is None:
            continue
        definitions.append(
            live.PatchReadRequest(definition.display_name, definition.address, live.seven_bit_address(definition.size))
        )
    return definitions


def primary_patch_record_definitions(*, include_fx_algorithms: bool = True) -> list[live.PatchReadRequest]:
    return [
        live.PatchReadRequest("Patch Common", live.TEMPORARY_PATCH_COMMON, [0x00, 0x00, 0x00, 0x7E]),
        live.PatchReadRequest("Patch Stompbox", live.TEMPORARY_PATCH_STOMPBOX, [0x00, 0x00, 0x00, 0x68]),
        live.PatchReadRequest("Patch Led", live.TEMPORARY_PATCH_LED, [0x00, 0x00, 0x00, 0x1E]),
        *[
            live.PatchReadRequest(
                f"Assign {number}",
                live.address_adding(live.ASSIGN_BASE, (number - 1) * live.ASSIGN_STRIDE),
                [0x00, 0x00, 0x00, 0x2C],
            )
            for number in range(1, 17)
        ],
        live.PatchReadRequest("Patch Effect", live.TEMPORARY_PATCH_EFFECT, [0x00, 0x00, 0x01, 0x1C]),
        *[
            live.PatchReadRequest(block.display_name, block.address, live.seven_bit_address(block.size))
            for block in list(live.SUMMARY_BLOCKS) + (list(live.FX_ALGORITHM_BLOCKS) if include_fx_algorithms else [])
        ],
    ]


def preset_restore_record_definitions() -> list[live.PatchReadRequest]:
    return [
        definition
        for definition in primary_patch_record_definitions()
        if not definition.label.startswith("FX 4 ")
    ]


def remap_clone_address(address: list[int], slot: str) -> list[int]:
    address_value = live.seven_bit_address_value(address)
    patch2_base_value = live.seven_bit_address_value(live.TEMPORARY_PATCH2_STOMPBOX)
    if patch2_base_value <= address_value < patch2_base_value + 0x0C00:
        return live.address_adding(live.user_patch2_base(slot), address_value - patch2_base_value)
    patch3_base_value = live.seven_bit_address_value(live.TEMPORARY_PATCH3_STOMPBOX)
    if patch3_base_value <= address_value < patch3_base_value + 0x2300:
        return live.address_adding(live.user_patch3_base(slot), address_value - patch3_base_value)
    return live.remap_temporary_patch_address(address, live.user_patch_base(slot))


def patch_name_data(name: str) -> list[int]:
    encoded = name.encode("ascii", errors="ignore")[:16]
    return list(encoded.ljust(16, b" "))


def chain_write(elements: list[int], label: str) -> live.PatchWrite:
    values = valid_chain(elements)
    return live.PatchWrite(label, CHAIN_START, values)


def valid_chain(audible_prefix: list[int]) -> list[int]:
    if len(set(audible_prefix)) != len(audible_prefix):
        raise ValueError("chain prefix contains duplicate elements")
    if set(audible_prefix) - set(CANONICAL_FULL_CHAIN):
        raise ValueError("chain prefix contains unknown elements")
    return audible_prefix + [value for value in CANONICAL_FULL_CHAIN if value not in set(audible_prefix)]


def assign_address(number: int) -> list[int]:
    if not 1 <= number <= 16:
        raise ValueError("assign number must be 1...16")
    return live.address_adding(TEMPORARY_ASSIGN_1, (number - 1) * 0x40)


def assign_switch_writes(enabled: bool) -> list[live.PatchWrite]:
    if enabled:
        return [live.PatchWrite(f"Assign {number} switch on", assign_address(number), [0x01]) for number in range(1, 17)]
    return [live.PatchWrite(f"Assign {number} disabled", assign_address(number), DISABLED_ASSIGN_DATA) for number in range(1, 17)]


def assign_data(
    *,
    enabled: bool = True,
    target: int,
    target_min: int,
    target_max: int,
    source: int,
    mode: int,
    active_min: int = 0,
    active_max: int = 127,
    midi_channel: int = 0,
    midi_cc: int = 0,
    midi_cc_min: int = 0,
    midi_cc_max: int = 0,
    midi_pc: int = 0,
    midi_bank_msb: int = 128,
    midi_bank_lsb: int = 128,
) -> list[int]:
    return (
        [0x01 if enabled else 0x00]
        + live.nibbles_for(target)
        + live.nibbles_for(target_min)
        + live.nibbles_for(target_max)
        + [source, mode, 0x00, 0x00, 0x00, 0x00, 0x00]
        + live.nibbles_for(active_min)
        + live.nibbles_for(active_max)
        + [midi_channel, midi_cc]
        + live.nibbles_for(midi_cc_min)
        + live.nibbles_for(midi_cc_max)
        + [0x00, midi_pc]
        + live.nibbles_for(midi_bank_msb, byte_count=2)
        + live.nibbles_for(midi_bank_lsb, byte_count=2)
    )


def divider1_channel_select_assign_data() -> list[int]:
    return assign_data(
        target=ASSIGN_TARGET_DIVIDER1_CHANNEL_SELECT,
        target_min=32768,
        target_max=32769,
        source=CTL1_SOURCE,
        mode=0x00,
    )


def tuner_assign_data() -> list[int]:
    return assign_data(
        target=ASSIGN_TARGET_TUNER_ON_OFF,
        target_min=32768,
        target_max=32769,
        source=0x45,
        mode=0x01,
        midi_cc=80,
    )


def assign_source_for_cc(cc: int) -> int:
    if 1 <= cc <= 31:
        return cc + 21
    if 64 <= cc <= 95:
        return cc - 11
    raise ValueError("MIDI CC Assign sources support CC#1...31 and CC#64...95")


def all_switchable_blocks_off() -> list[live.PatchWrite]:
    writes = []
    for block_id in [
        "comp", "dist1", "dist2", "preamp1", "preamp2", "ns1", "ns2", "eq1", "eq2", "eq3", "eq4",
        "delay1", "delay2", "delay3", "delay4", "masterDelay", "chorus", "fx1", "fx2", "fx3",
        "reverb", "pedalFx",
    ]:
        writes.append(live.PatchWrite(f"{block_id} switch off", block_address(block_id), [0x00]))
    writes.append(live.PatchWrite("Send/Return 1 switch off", SEND_RETURN1, [0x00]))
    writes.append(live.PatchWrite("Send/Return 2 switch off", live.address_adding(live.TEMPORARY_PATCH_EFFECT, 0x3C), [0x00]))
    return writes


def block_address(block_id: str) -> list[int]:
    return parameter_address(find_patch_block(block_id), 0)


def find_patch_block(block_id: str) -> live.BlockDefinition | live.ResidentBlockDefinition:
    block = next((block for block in list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) if block.id == block_id), None)
    if block is not None:
        return block
    resident = next((block for block in live.RESIDENT_BLOCKS if block.id == block_id), None)
    if resident is not None:
        return resident
    raise ValueError(f"unknown block id {block_id}")


def parameter_address(block: live.BlockDefinition | live.ResidentBlockDefinition, offset: int) -> list[int]:
    if isinstance(block, live.BlockDefinition):
        return live.address_adding(block.address, offset)
    return live.address_adding(live.TEMPORARY_PATCH_EFFECT, offset)


def raw_parameter_address(block: live.BlockDefinition | live.ResidentBlockDefinition, offset: int) -> list[int]:
    if isinstance(block, live.BlockDefinition):
        return live.address_adding(block.address, offset)
    return live.address_adding(live.TEMPORARY_PATCH_EFFECT, block.offset + offset)


def editable_block_size(block: live.BlockDefinition | live.ResidentBlockDefinition) -> int:
    if isinstance(block, live.BlockDefinition):
        return EDITABLE_BLOCK_SIZES.get(block.id, block.size)
    return block.size


def parse_raw_width(width: str) -> int:
    normalized = normalize_key(width)
    if normalized == "byte":
        return 1
    if normalized in {"nibbles2", "nibble2", "2-nibbles"}:
        return 2
    if normalized in {"nibbles4", "nibble4", "4-nibbles"}:
        return 4
    raise ValueError("width must be byte, nibbles2, or nibbles4")


def parse_mode(mode: str) -> int:
    normalized = normalize_key(mode)
    if normalized == "toggle":
        return 0
    if normalized == "moment":
        return 1
    raise ValueError("mode must be toggle or moment")


def normalize_key(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def validate_assign_int(label: str, value: int, minimum: int, maximum: int) -> None:
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be {minimum}...{maximum}")
