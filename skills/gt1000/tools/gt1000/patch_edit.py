from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

try:
    from tools.gt1000 import live
except ModuleNotFoundError:
    import live


PATCH_COMMON = [0x10, 0x00, 0x00, 0x00]
USER_PATCH_1 = [0x20, 0x00, 0x00, 0x00]
PATCH_ADDRESS_STRIDE = 0x4000
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
DISABLED_ASSIGN_DATA = [
    0x00, 0x00, 0x00, 0x00, 0x08, 0x08, 0x00, 0x00, 0x00, 0x08, 0x00,
    0x00, 0x01, 0x08, 0x00, 0x14, 0x01, 0x0D, 0x1E, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x03, 0x0F, 0x0F, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x03, 0x0F, 0x0F, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]


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
    base = user_slot_base(slot)
    temporary_base_value = live.seven_bit_address_value(PATCH_COMMON)
    user_base_value = live.seven_bit_address_value(base)
    writes = []
    for write in plan.writes:
        address_value = live.seven_bit_address_value(write.address)
        if address_value < temporary_base_value:
            raise ValueError(f"cannot remap address {live.hex_string(write.address)} into user patch memory")
        offset = address_value - temporary_base_value
        writes.append(live.PatchWrite(f"{slot} {write.label}", live.seven_bit_address(user_base_value + offset), write.data))
    return PatchPlan(
        id=f"{plan.id}:{slot}",
        description=f"{plan.description} Persistent target: {slot}.",
        writes=writes,
    )


def user_slot_base(slot: str) -> list[int]:
    normalized = slot.upper()
    if not normalized.startswith("U03-"):
        raise ValueError("only U03-1 through U03-5 are allowed; U01 and U02 are intentionally blocked")
    try:
        number = int(normalized.split("-", 1)[1])
    except ValueError as error:
        raise ValueError("slot must look like U03-1") from error
    if not 1 <= number <= 5:
        raise ValueError("only U03-1 through U03-5 are allowed")
    patch_index = 10 + number
    return live.seven_bit_address(live.seven_bit_address_value(USER_PATCH_1) + (patch_index - 1) * PATCH_ADDRESS_STRIDE)


def apply_plan(plan: PatchPlan, *, timeout: float, verify: bool) -> dict[str, Any]:
    live.write_data_sets(plan.writes)
    result: dict[str, Any] = {"plan": plan.id, "writeCount": len(plan.writes), "verified": None}
    if verify:
        time.sleep(0.25)
        verification = verify_plan(plan, timeout=timeout)
        result["verified"] = verification["ok"]
        result["verification"] = verification
    return result


def build_parameter_set_plan(block_id: str, parameter_id: str, raw_value: str, *, slot: str | None = None) -> PatchPlan:
    block = next((block for block in live.SUMMARY_BLOCKS if block.id == block_id), None)
    if block is None:
        raise ValueError(f"unknown block {block_id}")
    parameter = next((parameter for parameter in block.parameters if parameter.id == parameter_id), None)
    if parameter is None:
        raise ValueError(f"unknown parameter {parameter_id} for block {block_id}")

    value = parse_parameter_value(parameter, raw_value)
    address = live.address_adding(block.address, parameter.offset)
    write = live.PatchWrite(f"Set {block_id}.{parameter_id}", address, encode_parameter_value(parameter, value))
    plan = PatchPlan(
        id=f"set:{block_id}.{parameter_id}",
        description=f"Set {block.display_name} {parameter.display_name} to {value}.",
        writes=[write],
    )
    return plan_for_user_slot(plan, slot) if slot else plan


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
    raw = live.read_data_sets(timeout=timeout, requests=requests)
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
    target: int,
    target_min: int,
    target_max: int,
    source: int,
    mode: int,
    active_min: int = 0,
    active_max: int = 127,
    midi_cc: int = 0,
) -> list[int]:
    return (
        [0x01]
        + live.nibbles_for(target)
        + live.nibbles_for(target_min)
        + live.nibbles_for(target_max)
        + [source, mode, 0x00, 0x00, 0x00, 0x00, 0x00]
        + live.nibbles_for(active_min)
        + live.nibbles_for(active_max)
        + [0x00, midi_cc]
        + live.nibbles_for(0)
        + live.nibbles_for(0)
        + [0x00, 0x00]
        + live.nibbles_for(128, byte_count=2)
        + live.nibbles_for(128, byte_count=2)
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
    block = next((block for block in live.SUMMARY_BLOCKS if block.id == block_id), None)
    if block is None:
        raise ValueError(f"unknown block id {block_id}")
    return block.address
