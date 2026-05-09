import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_CLI = ROOT / "skills" / "gt1000" / "scripts" / "gt1000-agent"
RUN_LIVE = os.environ.get("GT1000_LIVE") == "1"
ALLOW_U03_DESTRUCTIVE = os.environ.get("GT1000_ALLOW_U03_DESTRUCTIVE") == "1"


@unittest.skipUnless(RUN_LIVE, "set GT1000_LIVE=1 to run live GT-1000 tests")
class LiveSkillReadTests(unittest.TestCase):
    def run_cli(self, *args: str, timeout: int = 30) -> dict:
        result = subprocess.run(
            [str(SKILL_CLI), "--pretty", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        return json.loads(result.stdout)

    def test_live_ports_use_normal_gt1000_endpoint(self):
        ports = self.run_cli("ports", "--live")

        self.assertTrue(any(port["name"] == "GT-1000" and port["isDefaultGT1000Endpoint"] for port in ports["destinations"]))
        self.assertTrue(any(port["name"] == "GT-1000" and port["isDefaultGT1000Endpoint"] for port in ports["sources"]))

    def test_live_summary_chain_controls_and_block(self):
        summary = self.run_cli("patch", "summary", "--live", "--timeout", "12", timeout=40)

        self.assertIn("overview", summary)
        self.assertIn("chain", summary)
        self.assertIn("controls", summary)
        self.assertIsInstance(summary["overview"].get("patchName"), str)
        self.assertGreater(summary["overview"].get("signalChainElementCount", 0), 0)
        self.assertGreater(len(summary["chain"].get("elements", [])), 0)
        self.assertIn("controls", summary["controls"])

        block = self.run_cli("patch", "block", "delay1", "--live", "--timeout", "12", timeout=40)
        self.assertEqual(block["block"]["id"], "delay1")

    def test_live_standalone_views_and_dump_round_trip(self):
        overview = self.run_cli("patch", "overview", "--live", "--timeout", "12", timeout=40)
        chain = self.run_cli("patch", "chain", "--live", "--timeout", "12", timeout=40)
        controls = self.run_cli("patch", "controls", "--live", "--timeout", "12", timeout=40)

        self.assertIsInstance(overview.get("patchName"), str)
        self.assertGreater(overview.get("signalChainElementCount", 0), 0)
        self.assertGreater(len(chain.get("elements", [])), 0)
        self.assertIn("controls", controls)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "live-patch.json"
            dump = self.run_cli("patch", "dump", "--live", "--timeout", "12", "--output", str(output), timeout=40)
            self.assertEqual(Path(dump["output"]), output)
            self.assertTrue(output.is_file())

            inspected = self.run_cli("patch", "inspect", str(output), "--view", "summary", timeout=30)
            self.assertEqual(inspected["overview"]["patchName"], dump["patchName"])

    def test_patch_plans_build_without_writing(self):
        default = self.run_cli("patch", "plan", "default", timeout=30)
        four_cm = self.run_cli("patch", "plan", "4cm-template", timeout=30)

        self.assertEqual(default["id"], "default")
        self.assertGreater(default["writeCount"], 0)
        self.assertEqual(four_cm["id"], "4cm-template")
        self.assertGreater(four_cm["writeCount"], 0)


@unittest.skipUnless(
    RUN_LIVE and ALLOW_U03_DESTRUCTIVE,
    "set GT1000_LIVE=1 and GT1000_ALLOW_U03_DESTRUCTIVE=1 to destructively test U03 writes",
)
class LiveSkillU03WriteTests(unittest.TestCase):
    def run_cli(self, *args: str, timeout: int = 60) -> dict:
        result = subprocess.run(
            [str(SKILL_CLI), "--pretty", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        return json.loads(result.stdout)

    def assert_verified_u03(self, result: dict, slot: str) -> None:
        self.assertTrue(result["verified"])
        slot_second_byte = {
            "U03-1": "0A",
            "U03-2": "0B",
            "U03-3": "0C",
            "U03-4": "0D",
            "U03-5": "0E",
        }[slot]

        checks = result["verification"]["checks"]
        self.assertGreater(len(checks), 0)
        for check in checks:
            with self.subTest(label=check["label"]):
                self.assertTrue(check["ok"])
                self.assertEqual(check["address"][:2], ["20", slot_second_byte])

    def test_default_plan_verified_on_u03_1(self):
        result = self.run_cli(
            "patch",
            "apply",
            "default",
            "--name",
            "LIVE TST U031",
            "--live",
            "--user-slot",
            "U03-1",
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )

        self.assertEqual(result["plan"], "default:U03-1")
        self.assert_verified_u03(result, "U03-1")

    def test_4cm_plan_and_parameter_set_verified_on_u03_2(self):
        apply_result = self.run_cli(
            "patch",
            "apply",
            "4cm-template",
            "--name",
            "LIVE TST U032",
            "--live",
            "--user-slot",
            "U03-2",
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )

        self.assertEqual(apply_result["plan"], "4cm-template:U03-2")
        self.assert_verified_u03(apply_result, "U03-2")

        set_result = self.run_cli(
            "patch",
            "set",
            "delay1",
            "time",
            "420",
            "--live",
            "--user-slot",
            "U03-2",
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )

        self.assertEqual(set_result["plan"], "set:delay1.time:U03-2")
        self.assert_verified_u03(set_result, "U03-2")

    def test_non_u03_slot_is_rejected_before_write(self):
        result = subprocess.run(
            [
                str(SKILL_CLI),
                "--pretty",
                "patch",
                "apply",
                "default",
                "--live",
                "--user-slot",
                "U02-1",
                "--verify",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
