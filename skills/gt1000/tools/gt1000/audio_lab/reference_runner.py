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
    max_candidates: int = 4,
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
    plan = plan_reference_candidates(reference, session=session, max_candidates=max_candidates)
    candidate_plans = [_candidate_patch_plan(candidate) for candidate in plan["candidates"]]
    original_data = _read_original_write_data(candidate_plans, timeout=midi_timeout)

    scored_renders: list[dict[str, Any]] = []
    skipped_candidates: list[dict[str, Any]] = []
    baseline = _render_and_score(
        reference,
        session=session,
        label="baseline-reference",
        prepare_usb=prepare_usb,
        midi_timeout=midi_timeout,
        settle_seconds=settle_seconds,
        candidate=None,
    )
    scored_renders.append(baseline)

    for index, (candidate, candidate_plan) in enumerate(zip(plan["candidates"], candidate_plans), start=1):
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

    ranked = sorted(scored_renders, key=lambda item: item["score"])
    improvement = _baseline_improvement_summary(baseline, ranked[0])
    result = {
        "id": "audioReferenceRun",
        "session": session,
        "sessionDir": str(session_dir),
        "referenceProfilePath": str(profile_path),
        "candidateBudget": max_candidates,
        "candidateCount": len(plan["candidates"]),
        "renders": scored_renders,
        "skippedCandidates": skipped_candidates,
        "ranked": ranked,
        "best": ranked[0],
        "baseline": baseline,
        "improvement": improvement,
        "notes": [
            "Temporary-patch candidate writes were restored after each render.",
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
            "candidateCount": len(plan["candidates"]),
            "best": {
                "label": result["best"]["label"],
                "score": result["best"]["score"],
                "wetPath": result["best"]["wetPath"],
            },
            "improvement": improvement,
        },
    )
    return result


def _candidate_patch_plan(candidate: dict[str, Any]) -> patch_edit.PatchPlan:
    if candidate.get("command") == "master-set":
        return patch_edit.build_master_set_plan(
            str(candidate["parameter"]),
            str(candidate["value"]),
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
    score = reference_match_score(reference, profile)
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
