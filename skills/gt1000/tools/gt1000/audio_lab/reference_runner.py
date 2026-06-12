"""End-to-end reference-tone candidate runner for audio lab Phase 4."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from tools.gt1000 import live, patch_edit
except ModuleNotFoundError:
    import live
    import patch_edit

from .branch_lab import apply_plan_after_audio
from .errors import AudioLabError
from .metrics import reference_match_report, reference_match_score, reference_profile
from .orchestrator import render_labeled_wet
from .reference_planner import plan_reference_candidates
from .session import append_session_event, resolve_session_dir


def run_reference_candidates(
    profile_path: Path,
    *,
    session: str,
    max_candidates: int = 12,
    score_weights: dict[str, Any] | None = None,
    emphasis: str = "balanced",
    midi_timeout: float = 20.0,
    settle_seconds: float = 0.25,
    prepare_usb: bool = True,
    verify_writes: bool = True,
) -> dict[str, Any]:
    if not profile_path.is_file():
        raise AudioLabError(f"reference profile not found: {profile_path}", 64)
    session_dir = resolve_session_dir(session, create=False)
    if not session_dir.is_dir():
        raise AudioLabError(f"session does not exist: {session_dir}", 64)
    reference = json.loads(profile_path.read_text(encoding="utf-8"))
    # Plan a larger pool than the budget so inactive-block candidates can be
    # replaced instead of silently burning renders on inaudible writes.
    pool_budget = max(max_candidates * 2, max_candidates + 8)
    plan = plan_reference_candidates(reference, session=session, max_candidates=pool_budget)
    selection = _select_active_block_candidates(
        plan["candidates"],
        max_candidates=max_candidates,
        timeout=midi_timeout,
    )
    candidates = selection["selected"]
    skipped_candidates: list[dict[str, Any]] = list(selection["skippedInactive"])
    if skipped_candidates:
        append_session_event(
            session_dir,
            {
                "type": "reference-run-block-filter",
                "blockStates": selection["blockStates"],
                "skipped": [item["label"] for item in skipped_candidates],
            },
        )
    candidate_plans = [_candidate_patch_plan(candidate) for candidate in candidates]
    original_data = _read_original_write_data(candidate_plans, timeout=midi_timeout)

    scored_renders: list[dict[str, Any]] = []
    weights = score_weights or {}
    baseline = _render_and_score(
        reference,
        session=session,
        label="baseline-reference",
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
        settle_seconds=settle_seconds,
        candidate=None,
        score_weights=weights,
    )
    scored_renders.append(baseline)

    try:
        for index, (candidate, candidate_plan) in enumerate(zip(candidates, candidate_plans), start=1):
            candidate_verify = verify_writes or bool(candidate.get("requiresLiveVerification"))
            apply_result = apply_plan_after_audio(candidate_plan, timeout=midi_timeout, verify=candidate_verify)
            restore_result: dict[str, Any] | None = None
            try:
                if candidate_verify and apply_result.get("verified") is not True:
                    skipped_candidates.append(
                        {
                            "label": candidate["label"],
                            "reason": "candidate write did not pass live read-back verification",
                            "candidate": candidate,
                            "applyResult": apply_result,
                        }
                    )
                    continue
                scored = _render_and_score(
                    reference,
                    session=session,
                    label=candidate["renderLabel"],
                    prepare_usb=False,
                    midi_timeout=midi_timeout,
                    settle_seconds=settle_seconds,
                    candidate={**candidate, "applyResult": apply_result},
                    score_weights=weights,
                )
                scored_renders.append(scored)
            finally:
                restore_plan = _restore_plan_for(candidate_plan, original_data, label=f"candidate-{index:02d}")
                restore_result = _apply_restore_after_audio(
                    restore_plan,
                    timeout=midi_timeout,
                    verify=verify_writes,
                )
                append_session_event(
                    session_dir,
                    {
                        "type": "reference-run-restore",
                        "candidate": candidate["label"],
                        "restore": restore_result,
                    },
                )
                last_candidate = scored_renders[-1].get("candidate") if scored_renders else None
                if isinstance(last_candidate, dict) and last_candidate.get("label") == candidate["label"]:
                    scored_renders[-1]["restoreResult"] = restore_result
                if skipped_candidates and skipped_candidates[-1].get("label") == candidate["label"]:
                    skipped_candidates[-1]["restoreResult"] = restore_result
    except BaseException as error:
        emergency = _emergency_restore_all(candidate_plans, original_data, timeout=midi_timeout)
        append_session_event(
            session_dir,
            {
                "type": "reference-run-abort",
                "error": str(error),
                "emergencyRestore": emergency,
            },
        )
        raise

    ranked = sorted(scored_renders, key=lambda item: item["score"])
    improvement = _baseline_improvement_summary(baseline, ranked[0])
    audition_shortlist = _audition_shortlist(ranked)
    recommendation = _recommendation_summary(improvement, audition_shortlist)
    result = {
        "id": "audioReferenceRun",
        "session": session,
        "sessionDir": str(session_dir),
        "referenceProfilePath": str(profile_path),
        "emphasis": emphasis,
        "candidateBudget": max_candidates,
        "candidateCount": len(candidates),
        "blockStates": selection["blockStates"],
        "renders": scored_renders,
        "skippedCandidates": skipped_candidates,
        "ranked": ranked,
        "best": ranked[0],
        "baseline": baseline,
        "improvement": improvement,
        "auditionShortlist": audition_shortlist,
        "recommendation": recommendation,
        "notes": [
            "Temporary-patch candidate writes were restored after each render.",
            "Candidates targeting blocks that are switched off in the current patch are skipped and replaced from the planner pool.",
            "Candidates that do not pass live write/read-back verification are skipped before rendering.",
            "Lower score is closer to the reference profile by approximate band energy plus RMS penalty.",
            "Scores are an audition/ranking aid, not a guarantee of a perceptual tone match.",
            "No user-slot write was performed by this command.",
        ],
    }
    append_session_event(
        session_dir,
        {
            "type": "reference-run",
            "profilePath": str(profile_path),
            "candidateCount": len(candidates),
            "best": {
                "label": result["best"]["label"],
                "score": result["best"]["score"],
                "wetPath": result["best"]["wetPath"],
            },
            "improvement": improvement,
            "auditionShortlist": audition_shortlist,
            "recommendation": recommendation,
        },
    )
    return result


def _select_active_block_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_candidates: int,
    timeout: float,
) -> dict[str, Any]:
    """Drop candidates whose target block is switched off in the current patch.

    A write to a bypassed block verifies fine but cannot change the wet render,
    so it wastes one render of the candidate budget. Block switch state is read
    once up front (byte 0 of each switchable block). Unknown or unreadable
    states keep the candidate, so filtering can only narrow, never break, a run.
    """
    areas = sorted(
        {
            str(setting["area"])
            for candidate in candidates
            for setting in candidate.get("settings") or []
            if isinstance(setting, dict) and setting.get("area")
        }
    )
    block_states = _read_block_switch_states(areas, timeout=timeout)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in candidates:
        if len(selected) >= max_candidates:
            break
        inactive = [
            str(setting["area"])
            for setting in candidate.get("settings") or []
            if isinstance(setting, dict) and block_states.get(str(setting.get("area"))) == "off"
        ]
        if inactive:
            skipped.append(
                {
                    "label": candidate.get("label"),
                    "reason": f"block switched off in current patch: {', '.join(inactive)}",
                    "candidate": candidate,
                }
            )
            continue
        selected.append(candidate)
    return {"selected": selected, "skippedInactive": skipped, "blockStates": block_states}


def _read_block_switch_states(areas: list[str], *, timeout: float) -> dict[str, str]:
    requests: list[live.PatchReadRequest] = []
    request_areas: list[str] = []
    states: dict[str, str] = {}
    for area in areas:
        try:
            block = patch_edit.find_patch_block(area)
        except ValueError:
            states[area] = "unknown"
            continue
        parameters = getattr(block, "parameters", None) or []
        first = parameters[0] if parameters else None
        if first is None or first.id != "sw" or first.offset != 0:
            states[area] = "not-switchable"
            continue
        requests.append(
            live.PatchReadRequest(f"{area} switch", patch_edit.block_address(area), live.seven_bit_address(1))
        )
        request_areas.append(area)
    if not requests:
        return states
    try:
        raw = live.read_data_sets(timeout=timeout, requests=requests)
    except live.LiveMIDIError:
        for area in request_areas:
            states[area] = "unknown"
        return states
    for area, request in zip(request_areas, requests):
        data = raw.get(live.address_key(request.address))
        if not data:
            states[area] = "unknown"
        else:
            states[area] = "off" if data[0] == 0 else "on"
    return states


def _emergency_restore_all(
    candidate_plans: list[patch_edit.PatchPlan],
    original_data: dict[str, list[int]],
    *,
    timeout: float,
) -> dict[str, Any]:
    """Best-effort restore of every captured original byte range after an abort."""
    writes: list[live.PatchWrite] = []
    seen: set[str] = set()
    for plan in candidate_plans:
        for write in plan.writes:
            key = live.address_key(write.address)
            if key in seen:
                continue
            seen.add(key)
            data = original_data.get(key)
            if data is not None:
                writes.append(live.PatchWrite(f"Emergency restore {write.label}", write.address, list(data)))
    if not writes:
        return {"attempted": False, "reason": "no captured original bytes"}
    restore_plan = patch_edit.PatchPlan(
        id="reference-run-restore:abort",
        description="Best-effort restore of all original bytes after an aborted reference run.",
        writes=writes,
    )
    try:
        result = apply_plan_after_audio(restore_plan, timeout=timeout, verify=False)
        return {"attempted": True, "ok": True, "result": result}
    except Exception as error:  # noqa: BLE001 - never mask the original abort cause
        return {"attempted": True, "ok": False, "error": str(error)}


def _candidate_patch_plan(candidate: dict[str, Any]) -> patch_edit.PatchPlan:
    if candidate.get("command") == "master-set":
        return patch_edit.build_master_set_plan(
            str(candidate["parameter"]),
            str(candidate["value"]),
        )
    if candidate.get("command") == "compound-set":
        settings = candidate.get("settings")
        if not isinstance(settings, list) or not settings:
            raise AudioLabError(f"compound candidate {candidate.get('label')} has no settings", 64)
        writes: list[live.PatchWrite] = []
        for setting in settings:
            if not isinstance(setting, dict):
                raise AudioLabError(f"compound candidate {candidate.get('label')} has an invalid setting", 64)
            plan = patch_edit.build_parameter_set_plan(
                str(setting["area"]),
                str(setting["parameter"]),
                str(setting["value"]),
            )
            writes.extend(plan.writes)
        return patch_edit.PatchPlan(
            id=f"compound-set:{candidate.get('label')}",
            description=str(candidate.get("intent") or "Apply compound reference candidate."),
            writes=writes,
        )
    return patch_edit.build_parameter_set_plan(
        str(candidate["area"]),
        str(candidate["parameter"]),
        str(candidate["value"]),
    )


def _read_original_write_data(plans: list[patch_edit.PatchPlan], *, timeout: float) -> dict[str, list[int]]:
    requests: list[live.PatchReadRequest] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for plan in plans:
        for write in plan.writes:
            request = write.read_request
            key = (tuple(request.address), tuple(request.size))
            if key in seen:
                continue
            seen.add(key)
            requests.append(request)
    if not requests:
        return {}
    raw = live.read_data_sets(timeout=timeout, requests=requests)
    missing = [live.address_key(request.address) for request in requests if live.address_key(request.address) not in raw]
    if missing:
        raise AudioLabError(f"could not read original bytes for reference run restore: {', '.join(missing)}", 64)
    return raw


def _restore_plan_for(
    plan: patch_edit.PatchPlan,
    original_data: dict[str, list[int]],
    *,
    label: str,
) -> patch_edit.PatchPlan:
    writes: list[live.PatchWrite] = []
    for write in plan.writes:
        data = original_data.get(live.address_key(write.address))
        if data is None:
            raise AudioLabError(f"missing original data for restore at {live.address_key(write.address)}", 64)
        writes.append(live.PatchWrite(f"Restore {write.label}", write.address, list(data)))
    return patch_edit.PatchPlan(
        id=f"reference-run-restore:{label}",
        description=f"Restore temporary patch bytes after reference run {label}.",
        writes=writes,
    )


def _apply_restore_after_audio(
    plan: patch_edit.PatchPlan,
    *,
    timeout: float,
    verify: bool,
) -> dict[str, Any]:
    try:
        return apply_plan_after_audio(plan, timeout=timeout, verify=verify)
    except live.LiveMIDIError as error:
        message = str(error)
        if not verify or "verification phase failed" not in message:
            raise
        fallback = apply_plan_after_audio(plan, timeout=timeout, verify=False)
        fallback["verified"] = False
        fallback["verificationWarning"] = (
            "Restore write was retried without read-back because post-audio CoreMIDI verification failed: "
            f"{message}"
        )
        return fallback


def _baseline_improvement_summary(baseline: dict[str, Any], best: dict[str, Any]) -> dict[str, Any]:
    score_delta = _numeric_delta(baseline.get("score"), best.get("score"))
    band_delta = _numeric_delta(baseline.get("bandError"), best.get("bandError"))
    score_improvement = _improvement_percent(baseline.get("score"), best.get("score"))
    band_improvement = _improvement_percent(baseline.get("bandError"), best.get("bandError"))
    best_label = str(best.get("label"))
    improved = bool(score_delta is not None and score_delta < 0.0 and best_label != "baseline")
    band_target_met = bool(band_improvement is not None and band_improvement >= 30.0 and best_label != "baseline")
    if best_label == "baseline":
        status = "baseline-best"
        summary = "Baseline remained the best render; candidate changes did not improve the objective score."
    elif band_target_met:
        status = "target-met"
        summary = "Best candidate improved broad-band error by at least 30% versus baseline."
    elif improved:
        status = "improved"
        summary = "Best candidate improved the objective score, but did not meet the 30% broad-band improvement target."
    else:
        status = "not-improved"
        summary = "Best candidate did not improve the objective score versus baseline."
    return {
        "status": status,
        "baselineLabel": baseline.get("label"),
        "bestLabel": best.get("label"),
        "baselineScore": baseline.get("score"),
        "bestScore": best.get("score"),
        "scoreDelta": score_delta,
        "scoreImprovementPercent": score_improvement,
        "baselineBandError": baseline.get("bandError"),
        "bestBandError": best.get("bandError"),
        "bandErrorDelta": band_delta,
        "bandErrorImprovementPercent": band_improvement,
        "meetsThirtyPercentBandTarget": band_target_met,
        "plainSummary": summary,
    }


def _audition_shortlist(ranked: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    shortlist: list[dict[str, Any]] = []
    for rank, item in enumerate(ranked[:limit], start=1):
        candidate = item.get("candidate")
        candidate_payload = candidate if isinstance(candidate, dict) else None
        report = item.get("report") if isinstance(item.get("report"), dict) else {}
        shortlist.append(
            {
                "rank": rank,
                "label": item.get("label"),
                "renderLabel": item.get("renderLabel"),
                "wetPath": item.get("wetPath"),
                "score": item.get("score"),
                "bandError": item.get("bandError"),
                "rmsDeltaDb": item.get("rmsDeltaDb"),
                "candidateIntent": None if candidate_payload is None else candidate_payload.get("intent"),
                "candidateArea": None if candidate_payload is None else candidate_payload.get("area"),
                "candidateParameter": None if candidate_payload is None else candidate_payload.get("parameter"),
                "candidateValue": None if candidate_payload is None else candidate_payload.get("value"),
                "summary": report.get("plainSummary"),
            }
        )
    return shortlist


def _recommendation_summary(
    improvement: dict[str, Any],
    audition_shortlist: list[dict[str, Any]],
) -> dict[str, Any]:
    status = improvement.get("status")
    top = audition_shortlist[0] if audition_shortlist else {}
    if status == "baseline-best":
        action = "audition-baseline"
        summary = "Keep the baseline as the reference point; none of the rendered candidates improved the score."
    elif status == "target-met":
        action = "audition-best-candidate"
        summary = "Audition the top candidate first; it met the 30% broad-band improvement target."
    elif status == "improved":
        action = "audition-best-candidate"
        summary = "Audition the top candidate first, but treat it as partial progress because it missed the 30% broad-band target."
    else:
        action = "expand-or-rethink-candidates"
        summary = "Do not treat the top candidate as a win; expand or rethink the candidate set before recommending a sound."
    return {
        "action": action,
        "topLabel": top.get("label"),
        "topWetPath": top.get("wetPath"),
        "plainSummary": summary,
        "auditionCount": len(audition_shortlist),
    }


def _numeric_delta(before: Any, after: Any) -> float | None:
    if before is None or after is None:
        return None
    try:
        return float(after) - float(before)
    except (TypeError, ValueError):
        return None


def _improvement_percent(before: Any, after: Any) -> float | None:
    if before is None or after is None:
        return None
    try:
        before_float = float(before)
        after_float = float(after)
    except (TypeError, ValueError):
        return None
    if before_float <= 0.0:
        return None
    return ((before_float - after_float) / before_float) * 100.0


def _render_and_score(
    reference: dict[str, Any],
    *,
    session: str,
    label: str,
    prepare_usb: bool,
    midi_timeout: float,
    settle_seconds: float,
    candidate: dict[str, Any] | None,
    score_weights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    render = render_labeled_wet(
        session,
        label,
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
        settle_seconds=settle_seconds,
        snapshot_patch=False,
    )
    wet_path = Path(render["wetPath"])
    profile = reference_profile(wet_path)
    score = reference_match_score(reference, profile, **(score_weights or {}))
    candidate_label = "baseline" if candidate is None else str(candidate["label"])
    return {
        "label": candidate_label,
        "renderLabel": label,
        "wetPath": str(wet_path),
        "score": score["score"],
        "bandError": score["bandError"],
        "rmsDeltaDb": score["rmsDeltaDb"],
        "candidate": candidate,
        "render": render,
        "profile": profile,
        "details": score,
        "report": reference_match_report(reference, profile, score),
    }
