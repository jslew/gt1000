import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_CLI = ROOT / "skills" / "gt1000" / "scripts" / "gt1000-agent"
RUN_LIVE = os.environ.get("GT1000_LIVE") == "1"
ALLOW_DESTRUCTIVE = os.environ.get("GT1000_ALLOW_DESTRUCTIVE") == "1"
LIVE_WRITE_SLOTS = {
    "default": "U10-1",
    "four_cm": "U10-2",
    "parameter": "U10-3",
    "clone_source": "U10-4",
    "clone_template": "U10-5",
    "clone_destination": "U11-1",
}


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

    def test_live_user_slot_and_bank_overview_reads(self):
        slot = self.run_cli("patch", "slot", "U01-1", "--live", "--view", "overview", "--timeout", "12", timeout=40)
        bank = self.run_cli("patch", "bank", "U01", "--live", "--view", "overview", "--timeout", "12", timeout=80)

        self.assertIsInstance(slot.get("patchName"), str)
        self.assertEqual(bank["bank"], "U01")
        self.assertEqual([patch["slot"] for patch in bank["patches"]], ["U01-1", "U01-2", "U01-3", "U01-4", "U01-5"])
        self.assertEqual(bank["patches"][0]["data"]["patchName"], slot["patchName"])

    def test_patch_plans_build_without_writing(self):
        default = self.run_cli("patch", "plan", "default", timeout=30)
        four_cm = self.run_cli("patch", "plan", "4cm-template", timeout=30)

        self.assertEqual(default["id"], "default")
        self.assertGreater(default["writeCount"], 0)
        self.assertEqual(four_cm["id"], "4cm-template")
        self.assertGreater(four_cm["writeCount"], 0)


@unittest.skipUnless(RUN_LIVE, "set GT1000_LIVE=1 to run live GT-1000 tests")
class LiveSkillSystemReadTests(unittest.TestCase):
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

    def test_live_system_sections_decode(self):
        common = self.run_cli("system", "common", "--live", "--timeout", "12", timeout=40)
        midi = self.run_cli("system", "midi", "--live", "--timeout", "12", timeout=40)
        inout = self.run_cli("system", "inout", "--live", "--timeout", "12", timeout=40)
        effects = self.run_cli("system", "effects", "--live", "--timeout", "12", timeout=40)
        pitch = self.run_cli("system", "pitch", "--live", "--timeout", "12", timeout=40)
        controls = self.run_cli("system", "controls", "--live", "--timeout", "12", timeout=40)
        manual = self.run_cli("system", "manual", "--live", "--timeout", "12", timeout=40)

        self.assertEqual(common["id"], "systemCommon")
        self.assertEqual(midi["id"], "systemMidi")
        self.assertEqual(inout["id"], "systemInOut")
        self.assertEqual(effects["id"], "systemEffects")
        self.assertEqual(pitch["id"], "systemPitch")
        self.assertEqual(controls["id"], "systemControl")
        self.assertEqual(manual["id"], "systemManualControl")
        for section in [common, midi, inout, effects, pitch, controls, manual]:
            with self.subTest(section=section["id"]):
                self.assertIn("decoded", section)
                self.assertIsInstance(section.get("dataHex"), str)

    def test_live_pcmap_and_input_setting_decode(self):
        pcmap = self.run_cli("system", "pcmap", "--live", "--bank", "1", "--timeout", "12", timeout=40)
        inputs = self.run_cli("system", "inputs", "--live", "--number", "1", "--timeout", "12", timeout=40)

        self.assertEqual(pcmap["id"], "programChangeMap")
        self.assertEqual(pcmap["banks"][0]["bank"], 1)
        self.assertGreater(len(pcmap["banks"][0]["entries"]), 0)
        self.assertEqual(inputs["id"], "systemInputSettings")
        self.assertEqual(inputs["settings"][0]["number"], 1)


@unittest.skipUnless(
    RUN_LIVE and ALLOW_DESTRUCTIVE,
    "set GT1000_LIVE=1 and GT1000_ALLOW_DESTRUCTIVE=1 to destructively test user-slot writes",
)
class LiveSkillWriteTests(unittest.TestCase):
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

    def assert_verified(self, result: dict) -> None:
        self.assertTrue(result["verified"])
        checks = result["verification"]["checks"]
        self.assertGreater(len(checks), 0)
        for check in checks:
            with self.subTest(label=check["label"]):
                self.assertTrue(check["ok"])

    def assert_verified_patch1_slot(self, result: dict, second_byte: str) -> None:
        self.assert_verified(result)
        for check in result["verification"]["checks"]:
            with self.subTest(label=check["label"]):
                self.assertEqual(check["address"][:2], ["20", second_byte])

    def test_default_plan_verified_on_u10_1(self):
        result = self.run_cli(
            "patch",
            "apply",
            "default",
            "--name",
            "LIVE TST U101",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["default"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )

        self.assertEqual(result["plan"], "default:U10-1")
        self.assert_verified_patch1_slot(result, "2D")

    def test_4cm_plan_and_parameter_set_verified_on_u10_2(self):
        apply_result = self.run_cli(
            "patch",
            "apply",
            "4cm-template",
            "--name",
            "LIVE TST U102",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["four_cm"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )

        self.assertEqual(apply_result["plan"], "4cm-template:U10-2")
        self.assert_verified_patch1_slot(apply_result, "2E")

        set_result = self.run_cli(
            "patch",
            "set",
            "delay1",
            "time",
            "420",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )

        self.assertEqual(set_result["plan"], "set:delay1.time:U10-3")
        self.assert_verified_patch1_slot(set_result, "2F")

    def test_patch_clone_between_restricted_user_slots(self):
        source_result = self.run_cli(
            "patch",
            "apply",
            "default",
            "--name",
            "LIVE CLONE SRC",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["clone_source"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )
        template_result = self.run_cli(
            "patch",
            "apply",
            "4cm-template",
            "--name",
            "LIVE CLONE TMP",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["clone_template"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )

        self.assertEqual(source_result["plan"], "default:U10-4")
        self.assertEqual(template_result["plan"], "4cm-template:U10-5")
        self.assert_verified(source_result)
        self.assert_verified(template_result)

        clone_result = self.run_cli(
            "patch",
            "clone",
            LIVE_WRITE_SLOTS["clone_source"],
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=120,
        )
        destination = self.run_cli(
            "patch",
            "slot",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--view",
            "overview",
            "--timeout",
            "12",
            timeout=40,
        )

        self.assertEqual(clone_result["plan"], "clone:U10-4:U11-1")
        self.assertEqual(clone_result["sourceSlot"], "U10-4")
        self.assertEqual(clone_result["destinationSlot"], "U11-1")
        self.assert_verified(clone_result)
        self.assertEqual(destination["patchName"], "LIVE CLONE SRC")

    def test_invalid_user_slot_is_rejected_before_write(self):
        result = subprocess.run(
            [
                str(SKILL_CLI),
                "--pretty",
                "patch",
                "apply",
                "default",
                "--live",
                "--user-slot",
                "U51-1",
                "--verify",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("user bank must be U01...U50", result.stderr)


if __name__ == "__main__":
    unittest.main()
