"""Divider A/B branch inspection and measurement primitives for agent-guided audio lab investigations."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

try:
    from tools.gt1000 import live, patch_edit
except ModuleNotFoundError:
    import live
    import patch_edit

from .audio_io import prepare_usb_reamp
from .device_snapshot import read_patch_effect_snapshot
from .errors import AudioLabError
from .metrics import analyze_file, analyze_file_trimmed
from .orchestrator import render_labeled_wet
from .session import append_session_event, resolve_session_dir, sanitize_label

SUPPORTED_DIVIDERS = ("divider1", "divider2", "divider3")
DIVIDER_CHAIN_VALUE = {"divider1": 35, "divider2": 38, "divider3": 41}
DIVIDER_BRANCH_SPLIT = {"divider1": "branchSplit1", "divider2": "branchSplit2", "divider3": "branchSplit3"}
DIVIDER_MIXER = {"divider1": "mixer1", "divider2": "mixer2", "divider3": "mixer3"}
BRANCH_LABELS = {0: "branch-A", 1: "branch-B"}
CHANNEL_BY_LABEL = {"branch-A": 0, "branch-B": 1}
MODE_SINGLE = 0
GAIN_PROBE_LOW = 0
GAIN_PROBE_HIGH = 100
MIN_GAIN_SENSITIVITY_DB = 0.5
# Parameters an agent may try when pursuing loudness/gain goals (verify with probe-param).
GAIN_LIKE_PARAMETER_IDS = frozenset({
    "level",
    "effectLevel",
    "directLevel",
    "directMix",
    "soloLevel",
    "gain",
    "returnLevel",
    "sendLevel",
    "balanceA",
    "balanceB",
})
DEFAULT_INVESTIGATION_TIMEOUT_MINUTES = 5


def normalize_divider_id(divider: str) -> str:
    key = divider.strip().lower().replace("_", "").replace(" ", "")
    aliases = {"div1": "divider1", "div2": "divider2", "div3": "divider3", "divider": "divider1"}
    resolved = aliases.get(key, key)
    if resolved not in SUPPORTED_DIVIDERS:
        raise ValueError(f"divider must be one of: {', '.join(SUPPORTED_DIVIDERS)}")
    return resolved


def normalize_level_param(divider_id: str, param: str) -> str:
    text = param.strip()
    if "." in text:
        block, field = text.split(".", 1)
        if normalize_divider_id(block) != divider_id:
            raise ValueError(f"param {param!r} must target {divider_id}")
        field_id = field.strip()
    else:
        field_id = text
    if field_id not in {"levelA", "levelB"}:
        raise ValueError("param must be levelA or levelB (or dividerN.levelA / levelB)")
    return field_id


def read_divider_data(divider_id: str, timeout: float) -> list[int]:
    block = patch_edit.find_patch_block(divider_id)
    if not isinstance(block, live.ResidentBlockDefinition):
        raise ValueError(f"{divider_id} is not a resident divider block")
    address = patch_edit.block_address(divider_id)
    size = live.seven_bit_address(block.size)
    raw = live.read_data_sets(timeout=timeout, requests=[live.PatchReadRequest(divider_id, address, size)])
    data = raw.get(live.address_key(address))
    if not data:
        raise AudioLabError(f"failed to read {divider_id} from device", 64)
    return data


def read_branch_lab_context(divider_id: str, timeout: float) -> tuple[dict[str, Any], list[int]]:
    """One MIDI transaction for patch-effect chain context + divider bytes."""
    divider_id = normalize_divider_id(divider_id)
    block = patch_edit.find_patch_block(divider_id)
    if not isinstance(block, live.ResidentBlockDefinition):
        raise ValueError(f"{divider_id} is not a resident divider block")
    divider_address = patch_edit.block_address(divider_id)
    divider_size = live.seven_bit_address(block.size)
    requests = [
        live.PatchReadRequest("Patch Effect", live.TEMPORARY_PATCH_EFFECT, [0x00, 0x00, 0x01, 0x1C]),
        live.PatchReadRequest(divider_id, divider_address, divider_size),
    ]
    raw = live.read_data_sets(timeout=timeout, requests=requests)
    effect = raw.get(live.address_key(live.TEMPORARY_PATCH_EFFECT), [])
    snapshot = live.empty_snapshot()
    if effect:
        live.apply_data_set(snapshot, live.TEMPORARY_PATCH_EFFECT, effect)
    divider_bytes = raw.get(live.address_key(divider_address), [])
    if not divider_bytes:
        raise AudioLabError(f"failed to read {divider_id} from device", 64)
    return snapshot, divider_bytes


def decode_divider_data(divider_id: str, data: list[int]) -> dict[str, Any]:
    block = patch_edit.find_patch_block(divider_id)
    if not isinstance(block, live.ResidentBlockDefinition):
        raise ValueError(f"{divider_id} is not a resident divider block")
    base = block.offset
    params: dict[str, int | None] = {}
    for param in block.parameters:
        index = param.offset - base
        params[param.id] = data[index] if 0 <= index < len(data) else None
    return {
        "dividerId": divider_id,
        "mode": params.get("mode"),
        "channelSelect": params.get("channelSelect"),
        "levelA": params.get("levelA"),
        "levelB": params.get("levelB"),
        "dataHex": live.hex_string(data),
    }


def divider_present_in_snapshot(snapshot: dict[str, Any], divider_id: str) -> bool:
    divider_id = normalize_divider_id(divider_id)
    expected = DIVIDER_CHAIN_VALUE[divider_id]
    for element in snapshot.get("signalChainElements", []):
        if element.get("rawValue") == expected:
            return True
        name = str(element.get("displayName") or "").upper()
        if name.startswith(f"DIVIDER {divider_id[-1]}"):
            return True
    for block in snapshot.get("blocks", []):
        if block.get("id") == divider_id:
            return True
    return False


def branch_reachability_report(
    snapshot: dict[str, Any],
    chain: dict[str, Any],
    divider_id: str,
    divider_state: dict[str, Any],
) -> dict[str, Any]:
    divider_id = normalize_divider_id(divider_id)
    warnings: list[str] = []
    if not divider_present_in_snapshot(snapshot, divider_id):
        warnings.append(f"{divider_id} does not appear in the current signal chain.")
    mode = divider_state.get("mode")
    if mode != MODE_SINGLE:
        warnings.append(f"{divider_id} MODE is {mode!r}; branch A/B compare expects single mode (0).")
    channel = divider_state.get("channelSelect")
    if channel not in {0, 1}:
        warnings.append(f"{divider_id} CHANNEL SELECT is {channel!r}; expected 0 (A) or 1 (B).")
    inactive = []
    for element in chain.get("elements", []):
        if element.get("isUnreachable") and element.get("unreachablePath"):
            inactive.append(
                {
                    "displayName": element.get("displayName"),
                    "unreachablePath": element.get("unreachablePath"),
                    "reason": element.get("unreachableReason"),
                }
            )
    if inactive:
        warnings.append(
            "Some blocks are on an inactive divider branch and will not affect re-amp output: "
            + ", ".join(item["displayName"] or "?" for item in inactive[:5])
        )
    return {
        "dividerId": divider_id,
        "warnings": warnings,
        "inactiveBranchElements": inactive,
        "ok": not any("does not appear" in item or "single mode" in item for item in warnings),
    }


def build_channel_select_plan(divider_id: str, channel: int, *, slot: str | None = None) -> patch_edit.PatchPlan:
    if channel not in {0, 1}:
        raise ValueError("channel must be 0 (A) or 1 (B)")
    plan = patch_edit.build_parameter_set_plan(divider_id, "channelSelect", str(channel), slot=slot)
    return plan


def build_level_plan(divider_id: str, field: str, value: int, *, slot: str | None = None) -> patch_edit.PatchPlan:
    if not 0 <= value <= 127:
        raise ValueError(f"{field} must be 0...127")
    return patch_edit.build_parameter_set_plan(divider_id, field, str(value), slot=slot)


def normalize_branch_channel(channel: str | int) -> int:
    if isinstance(channel, int):
        if channel in {0, 1}:
            return channel
        raise ValueError("channel must be 0 (A) or 1 (B)")
    key = channel.strip().lower().replace("_", "").replace(" ", "")
    if key in {"a", "brancha", "branch-a"}:
        return 0
    if key in {"b", "branchb", "branch-b"}:
        return 1
    if key in {"0", "1"}:
        return int(key)
    raise ValueError("channel must be branch-A, branch-B, 0, or 1")


def block_has_parameter(block_id: str, parameter_id: str) -> bool:
    block = patch_edit.find_patch_block(block_id)
    return any(parameter.id == parameter_id for parameter in block.parameters)


def read_block_data(block_id: str, timeout: float) -> list[int]:
    block = patch_edit.find_patch_block(block_id)
    if isinstance(block, live.ResidentBlockDefinition):
        address = patch_edit.block_address(block_id)
        size = live.seven_bit_address(block.size)
    else:
        address = block.address
        size = live.seven_bit_address(patch_edit.editable_block_size(block))
    raw = live.read_data_sets(timeout=timeout, requests=[live.PatchReadRequest(block_id, address, size)])
    data = raw.get(live.address_key(address))
    if not data:
        raise AudioLabError(f"failed to read {block_id} from device", 64)
    return data


def restore_block_data(block_id: str, original: list[int], *, timeout: float, verify: bool) -> dict[str, Any]:
    block = patch_edit.find_patch_block(block_id)
    if isinstance(block, live.ResidentBlockDefinition):
        address = patch_edit.block_address(block_id)
    else:
        address = block.address
    plan = patch_edit.PatchPlan(
        id=f"restore:{block_id}",
        description=f"Restore {block_id} bytes captured before branch lab.",
        writes=[live.PatchWrite(f"Restore {block_id}", address, list(original))],
    )
    return apply_plan(plan, timeout=timeout, verify=verify)


def build_block_param_plan(
    block_id: str,
    parameter_id: str,
    value: int,
    *,
    slot: str | None = None,
) -> patch_edit.PatchPlan:
    return patch_edit.build_parameter_set_plan(block_id, parameter_id, str(value), slot=slot)


def read_block_parameter_value(block_id: str, parameter_id: str, data: list[int]) -> int | None:
    block = patch_edit.find_patch_block(block_id)
    if isinstance(block, live.ResidentBlockDefinition):
        base = block.offset
        for parameter in block.parameters:
            if parameter.id != parameter_id:
                continue
            index = parameter.offset - base
            return data[index] if 0 <= index < len(data) else None
    for parameter in block.parameters:
        if parameter.id != parameter_id:
            continue
        index = parameter.offset
        return data[index] if 0 <= index < len(data) else None
    return None


def _static_block_ids_by_chain_value() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for block in list(live.SUMMARY_BLOCKS) + list(live.FX_ALGORITHM_BLOCKS) + list(live.RESIDENT_BLOCKS):
        mapping[block.chain_element_value] = block.id
    return mapping


def _block_ids_by_chain_value(snapshot: dict[str, Any]) -> dict[int, str]:
    mapping = _static_block_ids_by_chain_value()
    for block in snapshot.get("blocks", []):
        raw = block.get("chainElementValue")
        block_id = block.get("id")
        if isinstance(raw, int) and isinstance(block_id, str):
            mapping[raw] = block_id
    return mapping


def blocks_on_divider_branch(snapshot: dict[str, Any], divider_id: str, channel: int) -> list[str]:
    """Block ids on the active side of a single-mode divider (between divider and branch split, or split and mixer)."""
    divider_id = normalize_divider_id(divider_id)
    if channel not in {0, 1}:
        raise ValueError("channel must be 0 (A) or 1 (B)")
    by_value = _block_ids_by_chain_value(snapshot)
    divider_value = DIVIDER_CHAIN_VALUE[divider_id]
    branch_value = patch_edit.find_patch_block(DIVIDER_BRANCH_SPLIT[divider_id]).chain_element_value
    mixer_value = patch_edit.find_patch_block(DIVIDER_MIXER[divider_id]).chain_element_value

    elements = snapshot.get("signalChainElements", [])
    divider_pos = branch_pos = mixer_pos = None
    for element in elements:
        raw = element.get("rawValue")
        pos = element.get("position")
        if raw == divider_value:
            divider_pos = pos
        elif raw == branch_value:
            branch_pos = pos
        elif raw == mixer_value:
            mixer_pos = pos
    if not all(isinstance(value, int) for value in (divider_pos, branch_pos, mixer_pos)):
        return []
    if channel == 0:
        lo, hi = divider_pos + 1, branch_pos
    else:
        lo, hi = branch_pos, mixer_pos
    skip_values = {divider_value, branch_value}
    block_ids: list[str] = []
    for element in elements:
        pos = element.get("position")
        raw = element.get("rawValue")
        if not isinstance(pos, int) or not isinstance(raw, int):
            continue
        if lo <= pos < hi and raw not in skip_values:
            block_id = by_value.get(raw)
            if block_id:
                block_ids.append(block_id)
    return block_ids


def adjustable_parameters_for_block(block_id: str) -> list[dict[str, str]]:
    block = patch_edit.find_patch_block(block_id)
    return [
        {"id": parameter.id, "displayName": parameter.display_name}
        for parameter in block.parameters
        if parameter.id in GAIN_LIKE_PARAMETER_IDS
    ]


def describe_branch_blocks(snapshot: dict[str, Any], divider_id: str, channel: int) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for block_id in blocks_on_divider_branch(snapshot, divider_id, channel):
        params = adjustable_parameters_for_block(block_id)
        if not params:
            continue
        block = patch_edit.find_patch_block(block_id)
        blocks.append(
            {
                "blockId": block_id,
                "displayName": block.display_name,
                "adjustableParams": params,
            }
        )
    return blocks


def investigation_protocol(*, timeout_minutes: int = DEFAULT_INVESTIGATION_TIMEOUT_MINUTES) -> dict[str, Any]:
    return {
        "owner": "agent",
        "defaultTimeoutMinutes": timeout_minutes,
        "steps": [
            "Inspect: patch chain --live and audio branch-context --divider <n> --live",
            "Measure baseline: audio compare-branches (or session render) on a fixed dry.wav",
            "Hypothesis: name block.parameter and expected direction on USB re-amp level",
            "Test: audio probe-param for cheap confirmation, then patch set + re-measure",
            "Loop until goal met or timeout; restore temp patch state between experiments",
            "Present findings to the user (goal, baseline, tries, result, musical meaning)",
            "If successful: offer to re-apply winning patch set on temp patch or save to a user slot only with explicit consent",
        ],
        "doc": "docs/audio-lab-investigation.md",
    }


def branch_context(
    divider: str,
    *,
    midi_timeout: float = 20.0,
) -> dict[str, Any]:
    """Inspection-only context for agent divider investigations (no re-amp)."""
    divider_id = normalize_divider_id(divider)
    snapshot, divider_bytes = read_branch_lab_context(divider_id, midi_timeout)
    try:
        from tools.gt1000 import agent_cli
    except ModuleNotFoundError:
        import agent_cli
    chain = agent_cli.chain_from_full(snapshot)
    divider_state = decode_divider_data(divider_id, divider_bytes)
    reachability = branch_reachability_report(snapshot, chain, divider_id, divider_state)
    return {
        "id": "audioBranchContext",
        "dividerId": divider_id,
        "dividerState": divider_state,
        "reachability": reachability,
        "branches": {
            "branch-A": {
                "channel": 0,
                "blocks": describe_branch_blocks(snapshot, divider_id, 0),
            },
            "branch-B": {
                "channel": 1,
                "blocks": describe_branch_blocks(snapshot, divider_id, 1),
            },
        },
        "investigationProtocol": investigation_protocol(),
        "notes": [
            "Divider LEVEL A/B often do not change USB main re-amp level in single mode; use audio probe-param before assuming they work.",
            "Inactive-branch blocks (see reachability) do not affect the branch you are not hearing.",
            "compare-branches restores divider bytes after measurement; probe-param restores the probed block.",
        ],
    }


def gain_candidates_on_branch(snapshot: dict[str, Any], divider_id: str, channel: int) -> list[str]:
    return [
        block_id
        for block_id in blocks_on_divider_branch(snapshot, divider_id, channel)
        if adjustable_parameters_for_block(block_id)
    ]


def _render_branch_rms(
    session: str,
    divider_id: str,
    channel: int,
    *,
    midi_timeout: float,
    settle_seconds: float,
) -> float | None:
    apply_plan(build_channel_select_plan(divider_id, channel), timeout=midi_timeout, verify=False)
    time.sleep(settle_seconds)
    render = _render_branch(
        session,
        divider_id,
        channel,
        prepare_usb=False,
        midi_timeout=midi_timeout,
        settle_seconds=settle_seconds,
    )
    return render["wetMetrics"].get("rmsDbfs")


def probe_param(
    session: str,
    divider: str,
    channel: str | int,
    block_id: str,
    parameter_id: str,
    *,
    low_value: int = GAIN_PROBE_LOW,
    high_value: int = GAIN_PROBE_HIGH,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    prepare_usb: bool = True,
) -> dict[str, Any]:
    """One before/after re-amp experiment to test whether a parameter moves USB level on a branch."""
    divider_id = normalize_divider_id(divider)
    channel_index = normalize_branch_channel(channel)
    session_dir = resolve_session_dir(session, create=False)
    if not (session_dir / "dry.wav").is_file():
        raise AudioLabError(f"session dry.wav not found under {session_dir}", 64)
    if not block_has_parameter(block_id, parameter_id):
        raise ValueError(f"{block_id} has no parameter {parameter_id!r}")
    if not 0 <= low_value <= 127 or not 0 <= high_value <= 127:
        raise ValueError("probe values must be 0...127")

    if prepare_usb:
        prepare_usb_reamp(midi_timeout, verify=True)

    if block_id == divider_id:
        original = read_divider_data(divider_id, midi_timeout)
        restore_fn = lambda: restore_divider_data(divider_id, original, timeout=midi_timeout, verify=False)
        low_plan = build_level_plan(divider_id, parameter_id, low_value)
        high_plan = build_level_plan(divider_id, parameter_id, high_value)
    else:
        original = read_block_data(block_id, midi_timeout)
        restore_fn = lambda: restore_block_data(block_id, original, timeout=midi_timeout, verify=False)
        low_plan = build_block_param_plan(block_id, parameter_id, low_value)
        high_plan = build_block_param_plan(block_id, parameter_id, high_value)

    try:
        apply_plan(build_channel_select_plan(divider_id, channel_index), timeout=midi_timeout, verify=False)
        time.sleep(settle_seconds)
        apply_plan(low_plan, timeout=midi_timeout, verify=False)
        low_rms = _render_branch_rms(
            session,
            divider_id,
            channel_index,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
        )
        apply_plan(high_plan, timeout=midi_timeout, verify=False)
        high_rms = _render_branch_rms(
            session,
            divider_id,
            channel_index,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
        )
    finally:
        restore = restore_fn()

    sensitivity = None
    if low_rms is not None and high_rms is not None:
        sensitivity = abs(high_rms - low_rms)
    return {
        "id": "audioProbeParam",
        "session": session,
        "dividerId": divider_id,
        "branch": BRANCH_LABELS[channel_index],
        "blockId": block_id,
        "parameterId": parameter_id,
        "lowValue": low_value,
        "highValue": high_value,
        "lowRmsDbfs": low_rms,
        "highRmsDbfs": high_rms,
        "sensitivityDb": sensitivity,
        "affectsReamp": sensitivity is not None and sensitivity >= MIN_GAIN_SENSITIVITY_DB,
        "restore": restore,
        "summary": (
            f"{block_id}.{parameter_id} on {BRANCH_LABELS[channel_index]}: "
            f"Δ RMS {sensitivity:.2f} dB across {low_value}→{high_value}"
            if sensitivity is not None
            else f"{block_id}.{parameter_id}: could not measure RMS"
        ),
        "note": "Agent should reject parameters with affectsReamp=false and pick another candidate from branch-context.",
    }


def _preferred_probe_parameter(block_id: str) -> str | None:
    params = adjustable_parameters_for_block(block_id)
    if not params:
        return None
    for preferred in ("level", "effectLevel", "gain", "returnLevel", "sendLevel"):
        if any(item["id"] == preferred for item in params):
            return preferred
    return params[0]["id"]


def probe_branch(
    session: str,
    divider: str,
    channel: str | int,
    *,
    max_probes: int = 6,
    include_divider_levels: bool = False,
    low_value: int = GAIN_PROBE_LOW,
    high_value: int = GAIN_PROBE_HIGH,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    prepare_usb: bool = True,
) -> dict[str, Any]:
    """Probe adjustable parameters on one branch; rank by USB re-amp sensitivity (mechanical screening)."""
    divider_id = normalize_divider_id(divider)
    channel_index = normalize_branch_channel(channel)
    snapshot, _ = read_branch_lab_context(divider_id, midi_timeout)
    probes: list[dict[str, Any]] = []

    if include_divider_levels:
        for field in ("levelA", "levelB"):
            if field == "levelA" and channel_index != 0:
                continue
            if field == "levelB" and channel_index != 1:
                continue
            if len(probes) >= max_probes:
                break
            probes.append(
                probe_param(
                    session,
                    divider_id,
                    channel_index,
                    divider_id,
                    field,
                    low_value=low_value,
                    high_value=high_value,
                    midi_timeout=midi_timeout,
                    settle_seconds=settle_seconds,
                    prepare_usb=prepare_usb and not probes,
                )
            )
            prepare_usb = False

    for block_id in blocks_on_divider_branch(snapshot, divider_id, channel_index):
        if len(probes) >= max_probes:
            break
        parameter_id = _preferred_probe_parameter(block_id)
        if not parameter_id:
            continue
        probes.append(
            probe_param(
                session,
                divider_id,
                channel_index,
                block_id,
                parameter_id,
                low_value=low_value,
                high_value=high_value,
                midi_timeout=midi_timeout,
                settle_seconds=settle_seconds,
                prepare_usb=prepare_usb and not probes,
            )
        )
        prepare_usb = False

    ranked = sorted(
        probes,
        key=lambda item: item.get("sensitivityDb") if item.get("sensitivityDb") is not None else -1.0,
        reverse=True,
    )
    effective = [item for item in ranked if item.get("affectsReamp")]
    return {
        "id": "audioProbeBranch",
        "session": session,
        "dividerId": divider_id,
        "branch": BRANCH_LABELS[channel_index],
        "maxProbes": max_probes,
        "probes": probes,
        "rankedBySensitivity": ranked,
        "effectiveControls": [
            {"blockId": item["blockId"], "parameterId": item["parameterId"], "sensitivityDb": item["sensitivityDb"]}
            for item in effective
        ],
        "summary": (
            f"Best control on {BRANCH_LABELS[channel_index]}: "
            f"{effective[0]['blockId']}.{effective[0]['parameterId']} ({effective[0]['sensitivityDb']:.1f} dB)"
            if effective
            else f"No parameter on {BRANCH_LABELS[channel_index]} moved USB level by ≥{MIN_GAIN_SENSITIVITY_DB} dB."
        ),
        "investigationProtocol": investigation_protocol(),
    }


def render_branch(
    session: str,
    divider: str,
    channel: str | int,
    *,
    label: str | None = None,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    verify_writes: bool = False,
    prepare_usb: bool = True,
    restore_divider: bool = True,
    trim_start_seconds: float = 0.0,
    trim_end_seconds: float = 0.0,
    user_slot: str | None = None,
    experiment_note: str | None = None,
) -> dict[str, Any]:
    """Select divider channel, re-amp once, return metrics (optional trimmed steady-state RMS)."""
    divider_id = normalize_divider_id(divider)
    channel_index = normalize_branch_channel(channel)
    session_dir = resolve_session_dir(session, create=False)
    if not (session_dir / "dry.wav").is_file():
        raise AudioLabError(f"session dry.wav not found under {session_dir}", 64)

    if prepare_usb:
        prepare_usb_reamp(midi_timeout, verify=True)

    original = read_divider_data(divider_id, midi_timeout)
    render_label = sanitize_label(label) if label else sanitize_label(f"{divider_id}-{BRANCH_LABELS[channel_index]}")
    restore: dict[str, Any] | None = None
    try:
        apply_plan(
            build_channel_select_plan(divider_id, channel_index, slot=user_slot),
            timeout=midi_timeout,
            verify=verify_writes,
        )
        time.sleep(settle_seconds)
        render = render_labeled_wet(
            session,
            render_label,
            prepare_usb=False,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
            snapshot_patch=False,
        )
    finally:
        if restore_divider:
            try:
                restore = restore_divider_data(divider_id, original, timeout=midi_timeout, verify=verify_writes)
            except live.LiveMIDIError:
                restore = {"ok": False, "warning": "Could not restore divider bytes after render-branch."}

    wet_path = Path(render["wetPath"])
    if trim_start_seconds > 0 or trim_end_seconds > 0:
        wet_metrics = analyze_file_trimmed(
            wet_path,
            trim_start_seconds=trim_start_seconds,
            trim_end_seconds=trim_end_seconds,
        )
    else:
        wet_metrics = render["wetMetrics"]

    payload = {
        "id": "audioRenderBranch",
        "session": session,
        "dividerId": divider_id,
        "branch": BRANCH_LABELS[channel_index],
        "label": render_label,
        "wetPath": str(wet_path),
        "wetMetrics": wet_metrics,
        "restore": restore,
    }
    if experiment_note:
        append_session_event(
            session_dir,
            {"type": "experiment", "action": "render-branch", "note": experiment_note, **payload},
        )
    return payload


def apply_plan(plan: patch_edit.PatchPlan, *, timeout: float, verify: bool) -> dict[str, Any]:
    try:
        return patch_edit.apply_plan(plan, timeout=timeout, verify=verify)
    except live.LiveMIDIError as error:
        message = str(error)
        if "No GT-1000 MIDI destination found" in message or "No GT-1000 MIDI source found" in message:
            raise
        time.sleep(0.5)
        return patch_edit.apply_plan(plan, timeout=timeout, verify=verify)


def restore_divider_data(divider_id: str, original: list[int], *, timeout: float, verify: bool) -> dict[str, Any]:
    address = patch_edit.block_address(divider_id)
    plan = patch_edit.PatchPlan(
        id=f"restore:{divider_id}",
        description=f"Restore {divider_id} bytes captured before branch lab.",
        writes=[live.PatchWrite(f"Restore {divider_id}", address, list(original))],
    )
    return apply_plan(plan, timeout=timeout, verify=verify)


def _render_branch(
    session: str,
    divider_id: str,
    channel: int,
    *,
    prepare_usb: bool,
    midi_timeout: float,
    settle_seconds: float,
    label: str | None = None,
) -> dict[str, Any]:
    render_label = sanitize_label(label) if label else sanitize_label(f"{divider_id}-{BRANCH_LABELS[channel]}")
    return render_labeled_wet(
        session,
        render_label,
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
        settle_seconds=settle_seconds,
        snapshot_patch=False,
    )


def _metrics_delta(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> dict[str, Any]:
    rms_a = metrics_a.get("rmsDbfs")
    rms_b = metrics_b.get("rmsDbfs")
    delta = None
    if rms_a is not None and rms_b is not None:
        delta = rms_b - rms_a
    return {
        "branchA": metrics_a,
        "branchB": metrics_b,
        "deltaRmsDbBranchBVsA": delta,
        "note": "Positive delta means branch B is louder than branch A (broadband RMS, not LUFS).",
    }


def compare_branches(
    session: str,
    divider: str,
    *,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    verify_writes: bool = True,
    prepare_usb: bool = True,
    user_slot: str | None = None,
) -> dict[str, Any]:
    divider_id = normalize_divider_id(divider)
    session_dir = resolve_session_dir(session, create=False)
    if not (session_dir / "dry.wav").is_file():
        raise AudioLabError(f"session dry.wav not found under {session_dir}", 64)

    snapshot, original = read_branch_lab_context(divider_id, midi_timeout)
    try:
        from tools.gt1000 import agent_cli
    except ModuleNotFoundError:
        import agent_cli
    chain = agent_cli.chain_from_full(snapshot)
    divider_state = decode_divider_data(divider_id, original)
    reachability = branch_reachability_report(snapshot, chain, divider_id, divider_state)
    if not reachability["ok"]:
        raise AudioLabError("; ".join(reachability["warnings"]), 64)

    if prepare_usb:
        prepare_usb_reamp(midi_timeout, verify=True)
    applied: list[dict[str, Any]] = []
    render_a: dict[str, Any] | None = None
    render_b: dict[str, Any] | None = None
    restore: dict[str, Any] | None = None
    try:
        apply_plan(build_channel_select_plan(divider_id, 0, slot=user_slot), timeout=midi_timeout, verify=verify_writes)
        applied.append({"channel": 0, "label": BRANCH_LABELS[0]})
        time.sleep(settle_seconds)
        render_a = _render_branch(
            session,
            divider_id,
            0,
            prepare_usb=False,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
        )
        time.sleep(0.75)
        apply_plan(build_channel_select_plan(divider_id, 1, slot=user_slot), timeout=midi_timeout, verify=verify_writes)
        applied.append({"channel": 1, "label": BRANCH_LABELS[1]})
        time.sleep(settle_seconds)
        render_b = _render_branch(
            session,
            divider_id,
            1,
            prepare_usb=False,
            midi_timeout=midi_timeout,
            settle_seconds=settle_seconds,
        )
    except live.LiveMIDIError as error:
        try:
            restore_divider_data(divider_id, original, timeout=midi_timeout, verify=False)
        except live.LiveMIDIError:
            pass
        raise AudioLabError(str(error), 64) from error
    finally:
        if restore is None:
            try:
                restore = restore_divider_data(divider_id, original, timeout=midi_timeout, verify=verify_writes)
            except live.LiveMIDIError:
                restore = {"ok": False, "warning": "Could not restore divider bytes over MIDI after branch lab run."}

    if render_a is None or render_b is None:
        raise AudioLabError("branch renders did not complete", 64)

    comparison = _metrics_delta(render_a["wetMetrics"], render_b["wetMetrics"])
    hypothesis = _branch_balance_hypothesis(comparison["deltaRmsDbBranchBVsA"])

    return {
        "id": "audioCompareBranches",
        "session": session,
        "sessionDir": str(session_dir),
        "dividerId": divider_id,
        "dividerStateBefore": divider_state,
        "reachability": reachability,
        "appliedEdits": applied,
        "restore": restore,
        "branchA": {
            "label": render_a["label"],
            "wetPath": render_a["wetPath"],
            "wetMetrics": render_a["wetMetrics"],
        },
        "branchB": {
            "label": render_b["label"],
            "wetPath": render_b["wetPath"],
            "wetMetrics": render_b["wetMetrics"],
        },
        "comparison": comparison,
        "hypothesis": hypothesis,
        "investigationProtocol": investigation_protocol(),
        "summary": _compare_summary(divider_id, comparison, hypothesis),
    }


def _branch_balance_hypothesis(delta_rms: float | None) -> dict[str, Any]:
    if delta_rms is None:
        return {"status": "unknown", "detail": "Could not compute RMS delta between branches."}
    if abs(delta_rms) <= 1.0:
        return {"status": "balanced", "detail": f"Branches are within 1.0 dB RMS (Δ={delta_rms:+.2f} dB)."}
    protocol = investigation_protocol()
    if delta_rms < 0:
        return {
            "status": "branchB_quieter",
            "detail": f"Branch B is about {abs(delta_rms):.1f} dB quieter than branch A.",
            "suggestedNextSteps": [
                "audio branch-context --divider <id> --live",
                "audio probe-param on branch-B candidates (e.g. dist1.level); divider levelB often ineffective",
                "patch set <block> <param> <value> --live; audio compare-branches to verify",
            ],
            "investigationProtocol": protocol,
        }
    return {
        "status": "branchB_louder",
        "detail": f"Branch B is about {delta_rms:.1f} dB louder than branch A.",
        "suggestedNextSteps": [
            "audio branch-context --divider <id> --live",
            "audio probe-param on branch-B or shared-path candidates; divider levelA often ineffective",
            "patch set <block> <param> <value> --live; audio compare-branches to verify",
        ],
        "investigationProtocol": protocol,
    }


def _compare_summary(divider_id: str, comparison: dict[str, Any], hypothesis: dict[str, Any]) -> str:
    delta = comparison.get("deltaRmsDbBranchBVsA")
    if delta is None:
        return f"{divider_id}: branch comparison incomplete (missing RMS)."
    return f"{divider_id}: Δ(B−A) = {delta:+.2f} dB RMS. {hypothesis.get('detail', '')}"


