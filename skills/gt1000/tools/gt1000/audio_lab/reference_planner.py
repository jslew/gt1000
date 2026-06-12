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
    paired_settings: tuple[tuple[str, str, str], ...] = ()


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

PREAMP_TONE_CANDIDATES = (
    CandidateSpec("preamp-level-plus", "preamp1", "level", "58", "Raise preamp output if the preamp is active."),
    CandidateSpec("preamp-level-minus", "preamp1", "level", "45", "Lower preamp output if the preamp is active."),
    CandidateSpec("preamp-middle-plus", "preamp1", "middle", "60", "Add amp midrange focus."),
    CandidateSpec("preamp-treble-plus", "preamp1", "treble", "60", "Add amp treble bite."),
    CandidateSpec("preamp-presence-plus", "preamp1", "presence", "60", "Add amp presence and edge."),
)

DRIVE_CANDIDATES = (
    CandidateSpec("dist-level-plus", "dist1", "level", "70", "Raise drive block output if active."),
    CandidateSpec("dist-level-minus", "dist1", "level", "45", "Lower drive block output if active."),
    CandidateSpec("dist-drive-plus", "dist1", "drive", "58", "Add drive saturation if the block is active."),
    CandidateSpec("dist-drive-minus", "dist1", "drive", "45", "Reduce drive saturation if the block is active."),
    CandidateSpec("dist-tone-plus", "dist1", "tone", "62", "Brighten the drive block if active."),
    CandidateSpec("dist-tone-minus", "dist1", "tone", "42", "Darken the drive block if active."),
    CandidateSpec("dist-bottom-plus", "dist1", "bottom", "65", "Add low-end support in the drive block if active."),
)

AMP_VOICE_CANDIDATES = (
    CandidateSpec("preamp-type-natural", "preamp1", "type", "NATURAL", "Try a clearer natural amp voicing."),
    CandidateSpec("preamp-type-brit-stack", "preamp1", "type", "BRIT STACK", "Try a more focused stack-style amp voicing."),
    CandidateSpec("preamp-type-x-hi-gain", "preamp1", "type", "X-HI GAIN", "Try a more saturated high-gain amp voicing."),
)

CAB_VOICE_CANDIDATES = (
    CandidateSpec(
        "main-cab-type-1",
        "mainSpeakerSimulator",
        "speakerType",
        "1",
        "Try main speaker simulator type 1 on both channels.",
        "compound-set",
        (("mainSpeakerSimulatorL", "speakerType", "1"), ("mainSpeakerSimulatorR", "speakerType", "1")),
    ),
    CandidateSpec(
        "main-cab-type-2",
        "mainSpeakerSimulator",
        "speakerType",
        "2",
        "Try main speaker simulator type 2 on both channels.",
        "compound-set",
        (("mainSpeakerSimulatorL", "speakerType", "2"), ("mainSpeakerSimulatorR", "speakerType", "2")),
    ),
    CandidateSpec(
        "main-cab-mic-center",
        "mainSpeakerSimulator",
        "micPosition",
        "35",
        "Move the main speaker simulator mic position toward center on both channels.",
        "compound-set",
        (("mainSpeakerSimulatorL", "micPosition", "35"), ("mainSpeakerSimulatorR", "micPosition", "35")),
    ),
    CandidateSpec(
        "main-cab-mic-edge",
        "mainSpeakerSimulator",
        "micPosition",
        "70",
        "Move the main speaker simulator mic position toward edge on both channels.",
        "compound-set",
        (("mainSpeakerSimulatorL", "micPosition", "70"), ("mainSpeakerSimulatorR", "micPosition", "70")),
    ),
)

DESCRIPTOR_CANDIDATES: dict[str, tuple[CandidateSpec, ...]] = {
    "space-wet": (
        CandidateSpec("reverb-level-plus", "reverb", "effectLevel", "35", "Add ambience level if reverb is active."),
        CandidateSpec("reverb-time-plus", "reverb", "time", "55", "Lengthen the reverb tail if reverb is active."),
        CandidateSpec("delay-level-plus", "delay1", "effectLevel", "35", "Add echo level if delay 1 is active."),
        CandidateSpec("delay-feedback-plus", "delay1", "feedback", "28", "Add repeat persistence if delay 1 is active."),
    ),
    "space-dry": (
        CandidateSpec("reverb-level-minus", "reverb", "effectLevel", "15", "Reduce ambience level if reverb is active."),
        CandidateSpec("delay-level-minus", "delay1", "effectLevel", "12", "Reduce echo level if delay 1 is active."),
    ),
    "fizz-control": (
        CandidateSpec("eq-high-minus", "eq1", "highGain", "56", "Soften upper treble."),
        CandidateSpec("dist-tone-minus", "dist1", "tone", "42", "Darken the drive block if active."),
        CandidateSpec("preamp-presence-minus", "preamp1", "presence", "45", "Reduce amp presence and edge."),
        CandidateSpec("eq-4k-minus", "eq1", "geq4kHz", "56", "Reduce hard upper-mid edge."),
    ),
    "brightness": (
        CandidateSpec("eq-high-plus", "eq1", "highGain", "72", "Add top-end bite."),
        CandidateSpec("eq-high-mid-plus", "eq1", "highMidGain", "72", "Add upper-mid presence."),
        CandidateSpec("preamp-presence-plus", "preamp1", "presence", "60", "Add amp presence and edge."),
        CandidateSpec("preamp-treble-plus", "preamp1", "treble", "60", "Add amp treble bite."),
        CandidateSpec("preamp-type-natural", "preamp1", "type", "NATURAL", "Try a clearer natural amp voicing."),
        CAB_VOICE_CANDIDATES[2],
    ),
    "body-support": (
        CandidateSpec("eq-low-mid-plus", "eq1", "lowMidGain", "72", "Add lower-mid body."),
        CandidateSpec("preamp-bass-plus", "preamp1", "bass", "58", "Add amp low-end support."),
        CandidateSpec("eq-low-plus", "eq1", "lowGain", "72", "Add low-end weight."),
        CandidateSpec("preamp-type-brit-stack", "preamp1", "type", "BRIT STACK", "Try a more focused stack-style amp voicing."),
        CAB_VOICE_CANDIDATES[1],
    ),
    "flub-control": (
        CandidateSpec("eq-low-minus", "eq1", "lowGain", "56", "Reduce low-end weight."),
        CandidateSpec("preamp-bass-minus", "preamp1", "bass", "45", "Reduce amp low-end support."),
        CandidateSpec("eq-low-mid-minus", "eq1", "lowMidGain", "56", "Reduce lower-mid buildup."),
    ),
    "lead-focus": (
        CandidateSpec("eq-2k-plus", "eq1", "geq2kHz", "72", "Bring the lead guitar range forward."),
        CandidateSpec("preamp-middle-plus", "preamp1", "middle", "60", "Add amp midrange focus."),
        CandidateSpec("eq-high-mid-plus", "eq1", "highMidGain", "72", "Add upper-mid presence."),
        CandidateSpec("preamp-presence-plus", "preamp1", "presence", "60", "Add amp presence and edge."),
        CandidateSpec("preamp-type-brit-stack", "preamp1", "type", "BRIT STACK", "Try a more focused stack-style amp voicing."),
    ),
    "sustain": (
        CandidateSpec("comp-sustain-plus", "comp", "sustain", "60", "Add compression sustain if the compressor is active."),
        CandidateSpec("preamp-gain-plus", "preamp1", "gain", "58", "Add preamp saturation and thickness."),
        CandidateSpec("dist-drive-plus", "dist1", "drive", "58", "Add drive saturation if the block is active."),
        CandidateSpec("preamp-type-x-hi-gain", "preamp1", "type", "X-HI GAIN", "Try a more saturated high-gain amp voicing."),
    ),
    "attack-clarity": (
        CandidateSpec("preamp-gain-minus", "preamp1", "gain", "45", "Reduce saturation for a clearer attack."),
        CandidateSpec("dist-drive-minus", "dist1", "drive", "45", "Reduce drive saturation if the block is active."),
        CandidateSpec("eq-high-mid-plus", "eq1", "highMidGain", "72", "Add upper-mid presence."),
    ),
}


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

    descriptor_specs, descriptor_guidance = _descriptor_candidate_specs(reference_profile)
    if descriptor_specs:
        ordered_specs = _dedupe_specs(descriptor_specs + list(LOUDNESS_CANDIDATES) + _ordered_candidate_specs(centroid_hz))[:max_candidates]
    else:
        ordered_specs = _dedupe_specs(list(LOUDNESS_CANDIDATES) + _ordered_candidate_specs(centroid_hz))[:max_candidates]
    candidates = [_candidate_payload(index, spec, session=session) for index, spec in enumerate(ordered_specs, start=1)]
    return {
        "id": "audioReferencePlan",
        "session": session,
        "referencePath": reference_profile.get("path"),
        "referenceProfileVersion": reference_profile.get("profileVersion"),
        "spectralCentroidHz": centroid_hz,
        "descriptorGuidance": descriptor_guidance,
        "candidateBudget": max_candidates,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "notes": [
            "Planner only: no patch writes, MIDI, audio capture, or persistent slot changes were performed.",
            "Each candidate command uses the existing validated patch edit surface.",
            "Candidates marked requiresLiveVerification must pass live write/read-back before rendering.",
            "Run candidates against a temp patch, render each label, then score wet WAVs with audio match-reference.",
        ],
    }


def _descriptor_candidate_specs(reference_profile: dict[str, Any]) -> tuple[list[CandidateSpec], list[dict[str, Any]]]:
    specs: list[CandidateSpec] = []
    guidance: list[dict[str, Any]] = []

    def add(signal: str, reason: str, value: float | None) -> None:
        if signal not in DESCRIPTOR_CANDIDATES:
            return
        specs.extend(DESCRIPTOR_CANDIDATES[signal])
        guidance.append({"signal": signal, "reason": reason, "value": value})

    duration_seconds = _profile_float(reference_profile, "analyzedDurationSeconds")
    space = reference_profile.get("space")
    if isinstance(space, dict) and space.get("available") and (duration_seconds is None or duration_seconds >= 1.0):
        tail_delta = _profile_float(space, "tailToActiveDeltaDb")
        repeat_strength = _profile_float(space, "repeatPeakStrength")
        side_to_mid = _profile_float(space, "tailSideToMidDb")
        if tail_delta is not None and tail_delta > -9.0:
            add("space-wet", "reference has a strong ambience tail", tail_delta)
        elif tail_delta is not None and tail_delta < -18.0:
            add("space-dry", "reference has a low ambience tail", tail_delta)
        if repeat_strength is not None and repeat_strength >= 0.05:
            add("space-wet", "reference has measurable repeat energy", repeat_strength)
        if side_to_mid is not None and side_to_mid > -9.0:
            add("space-wet", "reference ambience is relatively wide", side_to_mid)

    high_end = reference_profile.get("highEnd")
    if isinstance(high_end, dict) and high_end.get("available"):
        fizz_to_lead = _profile_float(high_end, "fizzToLeadMidDb")
        fizz_to_presence = _profile_float(high_end, "fizzToPresenceDb")
        presence_to_lead = _profile_float(high_end, "presenceToLeadMidDb")
        if (fizz_to_lead is not None and fizz_to_lead > -10.0) or (fizz_to_presence is not None and fizz_to_presence > -6.0):
            add("fizz-control", "reference upper end needs fizz-aware candidates", fizz_to_lead)
        elif presence_to_lead is not None and presence_to_lead < -8.0:
            add("brightness", "reference has restrained presence relative to lead mids, so test controlled brightness moves", presence_to_lead)
        elif presence_to_lead is not None and presence_to_lead > 4.0:
            add("brightness", "reference has prominent presence bite", presence_to_lead)

    low_body = reference_profile.get("lowBody")
    if isinstance(low_body, dict) and low_body.get("available"):
        sub_to_body_low_mid = _profile_float(low_body, "subToBodyLowMidDb")
        body_low_to_mid_lead = _profile_float(low_body, "bodyLowMidToMidLeadDb")
        if sub_to_body_low_mid is not None and sub_to_body_low_mid > -4.0:
            add("flub-control", "reference has enough sub energy that low-end control must be tested", sub_to_body_low_mid)
        if body_low_to_mid_lead is not None and body_low_to_mid_lead > 3.0:
            add("body-support", "reference has strong guitar body relative to mids", body_low_to_mid_lead)
        elif body_low_to_mid_lead is not None and body_low_to_mid_lead < -3.0:
            add("flub-control", "reference is lean below the lead range", body_low_to_mid_lead)

    lead_mid = reference_profile.get("leadMid")
    if isinstance(lead_mid, dict) and lead_mid.get("available"):
        lead_focus = _profile_float(lead_mid, "leadFocusIndexDb")
        lead_to_low = _profile_float(lead_mid, "leadMidToLowMidDb")
        if (lead_focus is not None and lead_focus > 3.0) or (lead_to_low is not None and lead_to_low > 3.0):
            add("lead-focus", "reference lead range is forward relative to surrounding guitar bands", lead_focus)
        elif lead_focus is not None and lead_focus < -4.0:
            add("body-support", "reference lead range is not dominant, so body candidates should stay in play", lead_focus)

    envelope = reference_profile.get("envelope")
    if isinstance(envelope, dict) and envelope.get("available"):
        sustain_drop = _profile_float(envelope, "sustainDropDb")
        within_12 = _profile_float(envelope, "sustainFractionWithin12Db")
        attack_to_sustain = _profile_float(envelope, "attackToSustainDb")
        if (sustain_drop is not None and sustain_drop < 2.0) or (within_12 is not None and within_12 > 0.85):
            add("sustain", "reference has stable singing sustain", sustain_drop)
        if attack_to_sustain is not None and attack_to_sustain > 4.0:
            add("attack-clarity", "reference has a pronounced pick attack", attack_to_sustain)

    return _dedupe_specs(specs), guidance


def _profile_float(section: dict[str, Any], field: str) -> float | None:
    value = section.get(field)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe_specs(specs: list[CandidateSpec]) -> list[CandidateSpec]:
    ordered: list[CandidateSpec] = []
    seen: set[tuple[str, str, str, str]] = set()
    for spec in specs:
        key = (spec.command, spec.area, spec.parameter, spec.value)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(spec)
    return ordered


def _ordered_candidate_specs(centroid_hz: float | None) -> list[CandidateSpec]:
    if centroid_hz is None:
        return list(LOUDNESS_CANDIDATES + BRIGHTER_CANDIDATES + WARMER_CANDIDATES + AMP_VOICE_CANDIDATES + CAB_VOICE_CANDIDATES[:2] + DRIVE_CANDIDATES[:4] + PREAMP_TONE_CANDIDATES + DRIVE_CANDIDATES[4:] + CAB_VOICE_CANDIDATES[2:])
    if centroid_hz < 700.0:
        return list(LOUDNESS_CANDIDATES + BRIGHTER_CANDIDATES + AMP_VOICE_CANDIDATES[:2] + CAB_VOICE_CANDIDATES[2:] + DRIVE_CANDIDATES[:4] + PREAMP_TONE_CANDIDATES + DRIVE_CANDIDATES[4:] + WARMER_CANDIDATES)
    if centroid_hz > 1800.0:
        return list(LOUDNESS_CANDIDATES + WARMER_CANDIDATES + AMP_VOICE_CANDIDATES[1:] + CAB_VOICE_CANDIDATES[:2] + DRIVE_CANDIDATES[:4] + PREAMP_TONE_CANDIDATES + DRIVE_CANDIDATES[4:] + BRIGHTER_CANDIDATES)
    return list(
        LOUDNESS_CANDIDATES
        + BRIGHTER_CANDIDATES[:2]
        + WARMER_CANDIDATES[:2]
        + AMP_VOICE_CANDIDATES
        + CAB_VOICE_CANDIDATES[:2]
        + PREAMP_TONE_CANDIDATES
        + DRIVE_CANDIDATES
        + BRIGHTER_CANDIDATES[2:]
        + WARMER_CANDIDATES[2:]
        + CAB_VOICE_CANDIDATES[2:]
    )


def _candidate_payload(index: int, spec: CandidateSpec, *, session: str) -> dict[str, Any]:
    if spec.command == "master-set":
        plan = patch_edit.build_master_set_plan(spec.parameter, spec.value)
        patch_command = ["patch", "master-set", spec.parameter, spec.value, "--live", "--verify"]
        patch_commands = [patch_command]
    elif spec.command == "compound-set":
        plans = [
            patch_edit.build_parameter_set_plan(area, parameter, value)
            for area, parameter, value in spec.paired_settings
        ]
        writes = [write for plan_item in plans for write in plan_item.writes]
        plan = patch_edit.PatchPlan(
            id=f"compound-set:{spec.label}",
            description=spec.intent,
            writes=writes,
        )
        patch_commands = [
            ["patch", "set", area, parameter, value, "--live", "--verify"]
            for area, parameter, value in spec.paired_settings
        ]
        patch_command = patch_commands[0]
    else:
        plan = patch_edit.build_parameter_set_plan(spec.area, spec.parameter, spec.value)
        patch_command = ["patch", "set", spec.area, spec.parameter, spec.value, "--live", "--verify"]
        patch_commands = [patch_command]
    render_label = f"candidate-{index:02d}-{spec.label}"
    return {
        "index": index,
        "label": spec.label,
        "renderLabel": render_label,
        "intent": spec.intent,
        "patchPlan": plan.id,
        "patchCommand": patch_command,
        "patchCommands": patch_commands,
        "renderCommand": ["audio", "session", "render", "--session", session, "--label", render_label],
        "command": spec.command,
        "area": spec.area,
        "block": spec.area if spec.command == "patch-set" else None,
        "parameter": spec.parameter,
        "settings": [
            {"area": area, "parameter": parameter, "value": value}
            for area, parameter, value in (spec.paired_settings or ((spec.area, spec.parameter, spec.value),))
        ],
        "requiresLiveVerification": spec.command != "master-set",
        "verificationPolicy": "existing-evidence" if spec.command == "master-set" else "verify-before-render",
        "value": spec.value,
        "writeCount": len(plan.writes),
    }
