"""Score agent traces against routing scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field

from .scenarios import Scenario
from .trace import Trace, _CHAINED_LIVE_RE, extract_gt1000_invocation


@dataclass
class ScoreResult:
    scenario_id: str
    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"{status} {self.scenario_id}"]
        for v in self.violations:
            lines.append(f"  violation: {v}")
        for w in self.warnings:
            lines.append(f"  warning: {w}")
        return "\n".join(lines)


def score_trace(trace: Trace, scenario: Scenario) -> ScoreResult:
    result = ScoreResult(scenario_id=scenario.id, passed=True)

    invocations = []
    for event in trace.events:
        if event.kind == "shell" and event.command:
            inv = extract_gt1000_invocation(event.command)
            if inv:
                invocations.append((event, inv))

    first_inv_idx = None
    if scenario.first_cli:
        for i, (_event, inv) in enumerate(invocations):
            if scenario.first_cli.matches_invocation(inv):
                first_inv_idx = i
                break
        if first_inv_idx is None:
            result.violations.append(
                f"first CLI must match {scenario.first_cli.match!r} "
                f"(require_live={scenario.first_cli.require_live})"
            )
        else:
            before = trace.events[: trace.events.index(invocations[first_inv_idx][0])]
            _check_pattern_rules(
                result,
                before,
                scenario.forbidden_before_first_cli,
                prefix="before first CLI",
                violations=True,
            )
            _check_pattern_rules(
                result,
                before,
                scenario.allowed_before_first_cli,
                prefix="before first CLI",
                violations=False,
                allowed_only=True,
            )

    # Global forbidden patterns on all shell/reference events
    for event in trace.events:
        blob = event.command or event.text
        for rule in scenario.forbidden_anywhere:
            if rule.matches(blob):
                result.violations.append(
                    f"forbidden pattern {rule.pattern!r} matched: {blob[:120]!r}"
                )

    # Chained live MIDI (anti-pattern)
    for cmd in trace.shell_commands():
        if _CHAINED_LIVE_RE.search(cmd.replace("\n", " ")):
            result.violations.append(f"chained live gt1000 commands in one shell: {cmd[:120]!r}")

    # Over-inspection: too many gt1000 calls before any reference escalation
    if scenario.max_gt1000_commands_before_escalate is not None and invocations:
        limit = scenario.max_gt1000_commands_before_escalate
        if len(invocations) > limit:
            result.violations.append(
                f"too many gt1000 CLI calls ({len(invocations)}) before escalate; max {limit}"
            )

    # Harness consent: nothing forbidden after harness continuation
    if scenario.forbidden_after_harness:
        seen_harness = False
        for event in trace.events:
            if event.kind == "harness":
                seen_harness = True
                continue
            if not seen_harness:
                continue
            blob = event.command or event.text
            for rule in scenario.forbidden_after_harness:
                if rule.matches(blob):
                    result.violations.append(
                        f"after harness, forbidden {rule.pattern!r}: {blob[:120]!r}"
                    )

    if result.violations:
        result.passed = False

    # Golden traces marked expect_fail should fail scoring
    if trace.expect_fail and result.passed:
        result.passed = False
        result.violations.append("trace marked expect_fail but passed all rules")
    elif not trace.expect_fail and not result.passed:
        pass
    elif trace.expect_fail and not result.passed:
        # Anti-pattern trace: failing rules means success
        result.passed = True
        result.warnings.append("anti-pattern trace failed rules as expected")
        result.violations = []

    return result


def _check_pattern_rules(
    result: ScoreResult,
    events: list,
    rules: list,
    *,
    prefix: str,
    violations: bool,
    allowed_only: bool = False,
) -> None:
    if allowed_only:
        # allowed_before: only profile/onboarding shell allowed besides empty
        for event in events:
            if event.kind not in ("shell", "reference_read"):
                continue
            blob = event.command or event.text
            if event.kind == "reference_read":
                result.violations.append(f"{prefix}: reference read not allowed: {blob[:80]!r}")
                continue
            if event.is_gt1000_cli:
                result.violations.append(f"{prefix}: gt1000 CLI before first read: {blob[:80]!r}")
                continue
            if not any(r.matches(blob) for r in rules):
                result.violations.append(
                    f"{prefix}: unexpected shell before first CLI: {blob[:80]!r}"
                )
        return

    for event in events:
        blob = event.command or event.text
        for rule in rules:
            if rule.matches(blob):
                msg = f"{prefix}: matched forbidden {rule.pattern!r}"
                if violations:
                    result.violations.append(msg)
                else:
                    result.warnings.append(msg)
