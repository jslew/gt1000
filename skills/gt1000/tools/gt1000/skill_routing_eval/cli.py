#!/usr/bin/env python3
"""Score agent routing traces against GT-1000 skill scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scenarios import default_scenarios_path, load_scenarios
from .scorer import score_trace
from .trace import load_trace, trace_from_gemini_jsonl


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "tests" / "skill_routing_eval" / "scenarios.json").is_file():
            return parent
    return here.parents[5]


def _pick_scenario(scenarios: dict, scenario_id: str | None, trace) -> str:
    if scenario_id and scenario_id != "auto":
        return scenario_id
    if trace.scenario_id:
        return trace.scenario_id
    # Match user message substrings
    users = " ".join(trace.user_messages()).lower()
    for sid, scenario in scenarios.items():
        for msg in scenario.user_messages:
            if msg.lower()[:40] in users or users[:40] in msg.lower():
                return sid
    raise SystemExit(
        "Could not auto-detect scenario; pass --scenario <id> "
        f"(available: {', '.join(sorted(scenarios))})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GT-1000 skill routing eval")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=None,
        help="Path to scenarios.json (default: tests/skill_routing_eval/scenarios.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    score_p = sub.add_parser("score", help="Score a JSON trace fixture")
    score_p.add_argument("--trace", type=Path, required=True)
    score_p.add_argument("--scenario", default="auto")

    jsonl_p = sub.add_parser("score-jsonl", help="Score an agy/Gemini CLI session JSONL")
    jsonl_p.add_argument("--jsonl", type=Path, required=True)
    jsonl_p.add_argument("--scenario", default="auto")

    args = parser.parse_args(argv)
    root = _repo_root()
    scenarios_path = args.scenarios or default_scenarios_path(root)
    scenarios = load_scenarios(scenarios_path)

    if args.command == "score":
        trace = load_trace(args.trace)
    else:
        trace = trace_from_gemini_jsonl(args.jsonl)

    sid = _pick_scenario(scenarios, args.scenario, trace)
    if sid not in scenarios:
        raise SystemExit(f"Unknown scenario {sid!r}")
    result = score_trace(trace, scenarios[sid])
    print(result.summary())
    if args.command == "score-jsonl":
        print(json.dumps({"scenario_id": sid, "passed": result.passed}, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
