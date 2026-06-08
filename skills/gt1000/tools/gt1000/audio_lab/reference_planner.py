"""Offline reference-tone candidate planning for audio lab Phase 4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from tools.gt1000 import patch_edit
except ModuleNotFoundError:
    import patch_edit


@dataclass(frozen=True)
class CandidateSpec:
    label: str
    area: str
    parameter: str
    value: str
    intent: str
    command: str = "patch-set"


WARMER_CANDIDATES = (
    CandidateSpec("eq-low-plus", "eq1", "lowGain", "72", "Add low-end weight."),
    CandidateSpec("eq-high-minus", "eq1", "highGain", "56", "Soften upper treble."),
    CandidateSpec("eq-low-mid-plus", "eq1", "lowMidGain", "72", "Add lower-mid body."),
    CandidateSpec("preamp-gain-plus", "preamp1", "gain", "58", "Add preamp saturation and thickness."),
)

BRIGHTER_CANDIDATES = (
    CandidateSpec("eq-high-plus", "eq1", "highGain", "72", "Add top-end bite."),
    CandidateSpec("eq-low-minus", "eq1", "lowGain", "56", "Reduce low-end weight."),
    CandidateSpec("eq-high-mid-plus", "eq1", "highMidGain", "72", "Add upper-mid presence."),
    CandidateSpec("preamp-gain-minus", "preamp1", "gain", "45", "Reduce saturation for a clearer attack."),
)

LOUDNESS_CANDIDATES = (
    CandidateSpec("patch-level-plus", "master", "level", "115", "Raise the whole patch level.", "master-set"),
    CandidateSpec("patch-level-minus", "master", "level", "85", "Lower the whole patch level.", "master-set"),
)


def plan_reference_candidates(
    reference_profile: dict[str, Any],
    *,
    session: str,
    max_candidates: int = 12,
) -> dict[str, Any]:
    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1")
    centroid = reference_profile.get("spectralCentroidHz")
    try:
        centroid_hz = None if centroid is None else float(centroid)
    except (TypeError, ValueError):
        centroid_hz = None

    ordered_specs = _ordered_candidate_specs(centroid_hz)[:max_candidates]
    candidates = [_candidate_payload(index, spec, session=session) for index, spec in enumerate(ordered_specs, start=1)]
    return {
        "id": "audioReferencePlan",
        "session": session,
        "referencePath": reference_profile.get("path"),
        "referenceProfileVersion": reference_profile.get("profileVersion"),
        "spectralCentroidHz": centroid_hz,
        "candidateBudget": max_candidates,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "notes": [
            "Planner only: no patch writes, MIDI, audio capture, or persistent slot changes were performed.",
            "Each candidate command uses the existing validated patch set surface.",
            "Run candidates against a temp patch, render each label, then score wet WAVs with audio match-reference.",
        ],
    }


def _ordered_candidate_specs(centroid_hz: float | None) -> list[CandidateSpec]:
    if centroid_hz is None:
        return list(LOUDNESS_CANDIDATES + BRIGHTER_CANDIDATES + WARMER_CANDIDATES)
    if centroid_hz < 700.0:
        return list(LOUDNESS_CANDIDATES + BRIGHTER_CANDIDATES + WARMER_CANDIDATES)
    if centroid_hz > 1800.0:
        return list(LOUDNESS_CANDIDATES + WARMER_CANDIDATES + BRIGHTER_CANDIDATES)
    return list(LOUDNESS_CANDIDATES + BRIGHTER_CANDIDATES[:2] + WARMER_CANDIDATES[:2] + BRIGHTER_CANDIDATES[2:] + WARMER_CANDIDATES[2:])


def _candidate_payload(index: int, spec: CandidateSpec, *, session: str) -> dict[str, Any]:
    if spec.command == "master-set":
        plan = patch_edit.build_master_set_plan(spec.parameter, spec.value)
        patch_command = ["patch", "master-set", spec.parameter, spec.value, "--live", "--verify"]
    else:
        plan = patch_edit.build_parameter_set_plan(spec.area, spec.parameter, spec.value)
        patch_command = ["patch", "set", spec.area, spec.parameter, spec.value, "--live", "--verify"]
    render_label = f"candidate-{index:02d}-{spec.label}"
    return {
        "index": index,
        "label": spec.label,
        "renderLabel": render_label,
        "intent": spec.intent,
        "patchPlan": plan.id,
        "patchCommand": patch_command,
        "renderCommand": ["audio", "session", "render", "--session", session, "--label", render_label],
        "command": spec.command,
        "area": spec.area,
        "block": spec.area if spec.command == "patch-set" else None,
        "parameter": spec.parameter,
        "requiresLiveVerification": spec.command != "master-set",
        "value": spec.value,
        "writeCount": len(plan.writes),
    }
