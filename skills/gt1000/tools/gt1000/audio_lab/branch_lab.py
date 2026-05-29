"""Divider A/B branch measurement and level matching for audio lab sessions."""

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
from .metrics import analyze_file
from .orchestrator import render_labeled_wet
from .session import resolve_session_dir, sanitize_label

SUPPORTED_DIVIDERS = ("divider1", "divider2", "divider3")
DIVIDER_CHAIN_VALUE = {"divider1": 35, "divider2": 38, "divider3": 41}
BRANCH_LABELS = {0: "branch-A", 1: "branch-B"}
CHANNEL_BY_LABEL = {"branch-A": 0, "branch-B": 1}
MODE_SINGLE = 0


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
) -> dict[str, Any]:
    label = sanitize_label(f"{divider_id}-{BRANCH_LABELS[channel]}")
    return render_labeled_wet(
        session,
        label,
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
        "summary": _compare_summary(divider_id, comparison, hypothesis),
    }


def _branch_balance_hypothesis(delta_rms: float | None) -> dict[str, Any]:
    if delta_rms is None:
        return {"status": "unknown", "detail": "Could not compute RMS delta between branches."}
    if abs(delta_rms) <= 1.0:
        return {"status": "balanced", "detail": f"Branches are within 1.0 dB RMS (Δ={delta_rms:+.2f} dB)."}
    if delta_rms < 0:
        return {
            "status": "branchB_quieter",
            "detail": f"Branch B is about {abs(delta_rms):.1f} dB quieter than branch A.",
            "suggestedParam": "levelB",
            "suggestedAction": "Increase divider LEVEL B or reduce LEVEL A.",
        }
    return {
        "status": "branchB_louder",
        "detail": f"Branch B is about {delta_rms:.1f} dB louder than branch A.",
        "suggestedParam": "levelA",
        "suggestedAction": "Increase divider LEVEL A or reduce LEVEL B.",
    }


def _compare_summary(divider_id: str, comparison: dict[str, Any], hypothesis: dict[str, Any]) -> str:
    delta = comparison.get("deltaRmsDbBranchBVsA")
    if delta is None:
        return f"{divider_id}: branch comparison incomplete (missing RMS)."
    return f"{divider_id}: Δ(B−A) = {delta:+.2f} dB RMS. {hypothesis.get('detail', '')}"


def level_step_for_delta(delta_db: float) -> int:
    magnitude = abs(delta_db)
    if magnitude < 0.5:
        return 0
    if magnitude < 2.0:
        return 2
    if magnitude < 5.0:
        return 5
    return 8


def match_levels(
    session: str,
    divider: str,
    param: str,
    *,
    target_match: str,
    threshold_db: float = 1.0,
    max_iterations: int = 8,
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    verify_writes: bool = True,
    user_slot: str | None = None,
) -> dict[str, Any]:
    divider_id = normalize_divider_id(divider)
    adjust_field = normalize_level_param(divider_id, param)
    reference_key = target_match.strip().lower().replace("_", "")
    if reference_key in {"branch-a", "brancha", "a"}:
        reference_channel = 0
        reference_label = "branch-A"
    elif reference_key in {"branch-b", "branchb", "b"}:
        reference_channel = 1
        reference_label = "branch-B"
    else:
        raise ValueError("target-match must be branch-A or branch-B")
    adjust_channel = 1 - reference_channel

    baseline = compare_branches(
        session,
        divider_id,
        midi_timeout=midi_timeout,
        settle_seconds=settle_seconds,
        verify_writes=verify_writes,
        user_slot=None,
    )
    ref_metrics = baseline["branchA"]["wetMetrics"] if reference_channel == 0 else baseline["branchB"]["wetMetrics"]
    ref_path = Path(baseline["branchA"]["wetPath"] if reference_channel == 0 else baseline["branchB"]["wetPath"])

    original = read_divider_data(divider_id, midi_timeout)
    divider_state = decode_divider_data(divider_id, original)
    current_level = divider_state.get(adjust_field)
    if current_level is None:
        raise AudioLabError(f"could not read {divider_id}.{adjust_field}", 64)

    iterations: list[dict[str, Any]] = []
    prepare_usb_reamp(midi_timeout, verify=True)
    try:
        for index in range(max_iterations):
            apply_plan(
                build_channel_select_plan(divider_id, adjust_channel, slot=user_slot),
                timeout=midi_timeout,
                verify=verify_writes,
            )
            time.sleep(settle_seconds)
            render = _render_branch(
                session,
                divider_id,
                adjust_channel,
                prepare_usb=False,
                midi_timeout=midi_timeout,
                settle_seconds=settle_seconds,
            )
            wet_metrics = render["wetMetrics"]
            ref_rms = ref_metrics.get("rmsDbfs")
            adj_rms = wet_metrics.get("rmsDbfs")
            delta = None
            if ref_rms is not None and adj_rms is not None:
                delta = adj_rms - ref_rms
            iteration = {
                "iteration": index + 1,
                "level": current_level,
                "deltaRmsVsReference": delta,
                "wetPath": render["wetPath"],
                "wetMetrics": wet_metrics,
            }
            iterations.append(iteration)
            if delta is None:
                break
            if abs(delta) <= threshold_db:
                break
            step = level_step_for_delta(delta)
            if step == 0:
                break
            if delta < 0:
                current_level = min(127, current_level + step)
            else:
                current_level = max(0, current_level - step)
            apply_plan(
                build_level_plan(divider_id, adjust_field, current_level, slot=user_slot),
                timeout=midi_timeout,
                verify=verify_writes,
            )
            divider_state[adjust_field] = current_level
            time.sleep(settle_seconds)
    finally:
        restore = restore_divider_data(divider_id, original, timeout=midi_timeout, verify=verify_writes)

    return {
        "id": "audioMatchLevels",
        "session": session,
        "dividerId": divider_id,
        "param": f"{divider_id}.{adjust_field}",
        "targetMatch": reference_label,
        "thresholdDb": threshold_db,
        "iterations": iterations,
        "restore": restore,
        "baselineCompare": baseline,
        "summary": baseline.get("summary"),
        "referenceWetPath": str(ref_path),
        "note": "Run audio compare-branches again to confirm balance after matching.",
    }
