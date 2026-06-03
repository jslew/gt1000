"""LLM routing eval: score agent traces against skill routing scenarios."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "gt1000"
EVAL_DIR = ROOT / "tests" / "skill_routing_eval"
SCENARIOS_PATH = EVAL_DIR / "scenarios.json"
TRACES_DIR = EVAL_DIR / "traces"
INDEX_PATH = SKILL / "references" / "skill-routing-index.md"

sys.path.insert(0, str(SKILL / "tools"))

from gt1000.skill_routing_eval import (  # noqa: E402
    load_scenarios,
    load_trace,
    score_trace,
    trace_from_gemini_jsonl,
)
from gt1000.skill_routing_eval.scenarios import (  # noqa: E402
    index_intent_to_scenario_id,
    parse_index_intents,
)


class SkillRoutingEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = load_scenarios(SCENARIOS_PATH)

    def test_scenarios_cover_routing_index_intents(self):
        index_intents = parse_index_intents(INDEX_PATH)
        self.assertGreater(len(index_intents), 20, "intent table parse failed")

        by_index_label = {
            s.index_intent: sid for sid, s in self.scenarios.items() if s.index_intent
        }
        missing = []
        for intent in index_intents:
            if intent not in by_index_label:
                missing.append(intent)
        self.assertEqual(
            missing,
            [],
            "Add scenarios for index intents: " + ", ".join(missing),
        )

    def test_scenario_ids_match_index_slugs(self):
        index_intents = parse_index_intents(INDEX_PATH)
        for intent, _first in index_intents.items():
            expected = index_intent_to_scenario_id(intent)
            self.assertIn(
                expected,
                self.scenarios,
                f"expected scenario id {expected!r} for index intent {intent!r}",
            )
            self.assertEqual(self.scenarios[expected].index_intent, intent)

    def test_golden_traces(self):
        trace_files = sorted(TRACES_DIR.glob("*.json"))
        self.assertGreaterEqual(len(trace_files), 4)
        for path in trace_files:
            with self.subTest(trace=path.name):
                trace = load_trace(path)
                sid = trace.scenario_id
                self.assertIsNotNone(sid)
                self.assertIn(sid, self.scenarios)
                result = score_trace(trace, self.scenarios[sid])
                if trace.expect_fail:
                    self.assertTrue(
                        result.passed,
                        f"{path.name} should fail rules (anti-pattern): {result.violations}",
                    )
                else:
                    self.assertTrue(
                        result.passed,
                        f"{path.name}: {result.summary()}",
                    )

    def test_score_agy_fixture_if_present(self):
        fixture = EVAL_DIR / "fixtures" / "gemini_u01-03_balance.jsonl"
        if not fixture.is_file():
            self.skipTest("optional agy/gemini fixture not checked in")
        trace = trace_from_gemini_jsonl(fixture)
        # Anti-pattern transcript: reference mining + persist on continue
        result = score_trace(trace, self.scenarios["describe_user_slot"])
        self.assertFalse(result.passed)


class SkillRoutingEvalRunHarnessTests(unittest.TestCase):
    def test_build_prompt_and_discover(self):
        from gt1000.skill_routing_eval.run import (
            build_agy_prompt,
            chats_dir,
            main,
            project_slug,
        )

        workdir = Path("/tmp/gt1000-scratch")
        self.assertEqual(project_slug(workdir), "gt1000-scratch")
        self.assertTrue(str(chats_dir(workdir)).endswith("gt1000-scratch/chats"))
        prompt = build_agy_prompt("What does my current patch sound like?")
        self.assertIn("/gt1000", prompt)
        self.assertIn("references/", prompt)
        code = main(["suite", "--scenarios-list", "describe_current_patch", "--dry-run"])
        self.assertEqual(code, 0)

    def test_replay_saved_jsonl_if_present(self):
        jsonl = Path.home() / ".gemini/tmp/gt1000-scratch/chats"
        if not jsonl.is_dir():
            self.skipTest("no gt1000-scratch chats dir")
        sessions = sorted(jsonl.glob("session-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            self.skipTest("no session jsonl")
        from gt1000.skill_routing_eval.run import score_jsonl

        passed, summary, _violations = score_jsonl(
            sessions[0], "describe_user_slot", SCENARIOS_PATH
        )
        # Saved U01-03 session is a known anti-pattern; scorer should fail.
        self.assertFalse(passed)
        self.assertIn("FAIL", summary)


@unittest.skipUnless(
    os.environ.get("GT1000_ROUTING_EVAL_AGY") == "1",
    "set GT1000_ROUTING_EVAL_AGY=1 to run live agy routing eval",
)
class SkillRoutingEvalAgyLiveTests(unittest.TestCase):
    def test_agy_suite_smoke(self):
        from gt1000.skill_routing_eval.run import DEFAULT_SUITE, main

        code = main(
            [
                "suite",
                "--scenarios-list",
                ",".join(DEFAULT_SUITE[:1]),
                "--dry-run",
            ]
        )
        self.assertEqual(code, 0)


class SkillRoutingEvalCliTests(unittest.TestCase):
    def test_cli_good_trace(self):
        from gt1000.skill_routing_eval.cli import main

        trace = TRACES_DIR / "good_describe_current_patch.json"
        code = main(["score", "--trace", str(trace), "--scenario", "describe_current_patch"])
        self.assertEqual(code, 0)

    def test_cli_bad_trace(self):
        from gt1000.skill_routing_eval.cli import main

        trace = TRACES_DIR / "bad_reference_mining.json"
        code = main(["score", "--trace", str(trace), "--scenario", "describe_current_patch"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
