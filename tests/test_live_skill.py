import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from tools.gt1000 import live


ROOT = Path(__file__).resolve().parents[1]
SKILL_CLI = ROOT / "skills" / "gt1000" / "scripts" / "gt1000-agent"
RUN_LIVE = os.environ.get("GT1000_LIVE") == "1"
ALLOW_DESTRUCTIVE = os.environ.get("GT1000_ALLOW_DESTRUCTIVE") == "1"
LIVE_BACKUP_DIR = os.environ.get("GT1000_LIVE_BACKUP_DIR")
LIVE_BACKUP_FILE = os.environ.get("GT1000_LIVE_BACKUP_FILE")
LIVE_SYSTEM_CONTROL_BACKUP_FILE = os.environ.get("GT1000_LIVE_SYSTEM_CONTROL_BACKUP_FILE")
LIVE_PROCESS_TIMEOUT_MULTIPLIER = float(os.environ.get("GT1000_LIVE_PROCESS_TIMEOUT_MULTIPLIER", "3"))
LIVE_WRITE_SLOTS = {
    "default": "U10-1",
    "four_cm": "U10-2",
    "parameter": "U10-3",
    "clone_source": "U10-4",
    "clone_template": "U10-5",
    "clone_destination": "U11-1",
}


def live_process_timeout(timeout: int) -> float:
    return timeout * LIVE_PROCESS_TIMEOUT_MULTIPLIER
LIVE_WRITE_RESTORE_SLOTS = ["U10-1", "U10-2", "U10-3", "U10-4", "U10-5", "U11-1", "U11-2"]
LIVE_VERIFIED_COMMAND_PATHS = {
    ("ports",),
    ("midi", "bank-select"),
    ("midi", "cc"),
    ("midi", "pc"),
    ("patch", "apply"),
    ("patch", "assign-cc"),
    ("patch", "assign-set"),
    ("patch", "bank"),
    ("patch", "batch-copy"),
    ("patch", "batch-initialize"),
    ("patch", "block"),
    ("patch", "chain"),
    ("patch", "clear"),
    ("patch", "clone"),
    ("patch", "control-preference-set"),
    ("patch", "control-set"),
    ("patch", "controls"),
    ("patch", "copy"),
    ("patch", "disable"),
    ("patch", "diff"),
    ("patch", "dump"),
    ("patch", "enable"),
    ("patch", "exchange"),
    ("patch", "export"),
    ("patch", "import"),
    ("patch", "initialize"),
    ("patch", "insert"),
    ("patch", "inspect"),
    ("patch", "led-set"),
    ("patch", "liveset-copy"),
    ("patch", "liveset-list"),
    ("patch", "liveset-move"),
    ("patch", "liveset-remove"),
    ("patch", "liveset-rename"),
    ("patch", "master-set"),
    ("patch", "move"),
    ("patch", "overview"),
    ("patch", "performance"),
    ("patch", "plan"),
    ("patch", "preset"),
    ("patch", "raw-set"),
    ("patch", "rename"),
    ("patch", "restore-preset"),
    ("patch", "schema"),
    ("patch", "select"),
    ("patch", "set"),
    ("patch", "setlist-audit"),
    ("patch", "set-bpm"),
    ("patch", "slot"),
    ("patch", "stompbox"),
    ("patch", "summary"),
    ("patch", "system-control-set"),
    ("patch", "tsl-export"),
    ("patch", "tsl-import"),
    ("patch", "tsl-list"),
    ("patch", "tuner-assign"),
    ("patch", "type"),
    ("patch", "undo-last"),
    ("system", "common"),
    ("system", "controls"),
    ("system", "effects"),
    ("system", "inout"),
    ("system", "inputs"),
    ("system", "manual"),
    ("system", "midi"),
    ("system", "pcmap"),
    ("system", "pitch"),
}


class LiveUtilityTests(unittest.TestCase):
    def test_find_endpoint_retries_transient_empty_endpoint_names(self):
        class FakeMidi:
            def __init__(self):
                self.calls = 0

            def endpoint_name(self, endpoint):
                self.calls += 1
                return "" if self.calls == 1 else "GT-1000"

        midi = FakeMidi()
        with mock.patch.object(live.time, "sleep") as sleep:
            endpoint = live.find_endpoint(midi, lambda: 1, lambda index: 123)

        self.assertEqual(endpoint, 123)
        sleep.assert_called_once_with(0.25)

    def test_lenient_consecutive_miss_limit_defaults_and_ignores_bad_env(self):
        with mock.patch.dict(live.os.environ, {}, clear=False):
            live.os.environ.pop("GT1000_LENIENT_MAX_CONSECUTIVE_MISSES", None)
            self.assertEqual(live.lenient_consecutive_miss_limit(), 8)
        with mock.patch.dict(live.os.environ, {"GT1000_LENIENT_MAX_CONSECUTIVE_MISSES": "3"}):
            self.assertEqual(live.lenient_consecutive_miss_limit(), 3)
        with mock.patch.dict(live.os.environ, {"GT1000_LENIENT_MAX_CONSECUTIVE_MISSES": "bad"}):
            self.assertEqual(live.lenient_consecutive_miss_limit(), 8)


@unittest.skipUnless(RUN_LIVE, "set GT1000_LIVE=1 to run live GT-1000 tests")
class LiveSkillReadTests(unittest.TestCase):
    def run_cli(self, *args: str, timeout: int = 30) -> dict:
        result = subprocess.run(
            [str(SKILL_CLI), "--pretty", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=live_process_timeout(timeout),
            check=True,
        )
        return json.loads(result.stdout)

    def test_live_ports_use_normal_gt1000_endpoint(self):
        ports = self.run_cli("ports", "--live", "--timeout", "8")

        self.assertTrue(any(port["name"] == "GT-1000" and port["isDefaultGT1000Endpoint"] for port in ports["destinations"]))
        self.assertTrue(any(port["name"] == "GT-1000" and port["isDefaultGT1000Endpoint"] for port in ports["sources"]))

    def test_live_summary_chain_controls_and_block(self):
        summary = self.run_cli("patch", "summary", "--live", "--timeout", "20", timeout=40)

        self.assertIn("overview", summary)
        self.assertIn("chain", summary)
        self.assertIn("controls", summary)
        self.assertIsInstance(summary["overview"].get("patchName"), str)
        self.assertGreater(summary["overview"].get("signalChainElementCount", 0), 0)
        self.assertGreater(len(summary["chain"].get("elements", [])), 0)
        self.assertIn("controls", summary["controls"])

        block = self.run_cli("patch", "block", "delay1", "--live", "--timeout", "20", timeout=40)
        self.assertEqual(block["block"]["id"], "delay1")

    def test_live_standalone_views_and_dump_round_trip(self):
        overview = self.run_cli("patch", "overview", "--live", "--timeout", "20", timeout=40)
        chain = self.run_cli("patch", "chain", "--live", "--timeout", "20", timeout=40)
        controls = self.run_cli("patch", "controls", "--live", "--timeout", "20", timeout=40)

        self.assertIsInstance(overview.get("patchName"), str)
        self.assertGreater(overview.get("signalChainElementCount", 0), 0)
        self.assertGreater(len(chain.get("elements", [])), 0)
        self.assertIn("controls", controls)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "live-patch.json"
            dump = self.run_cli("patch", "dump", "--live", "--timeout", "20", "--output", str(output), timeout=40)
            self.assertEqual(Path(dump["output"]), output)
            self.assertTrue(output.is_file())

            inspected = self.run_cli("patch", "inspect", str(output), "--view", "summary", timeout=30)
            self.assertEqual(inspected["overview"]["patchName"], dump["patchName"])

        stompbox = self.run_cli("patch", "stompbox", "--live", "--timeout", "20", timeout=40)
        self.assertEqual(stompbox["id"], "patchStompBox")
        self.assertIn("selections", stompbox["decoded"])

    def test_live_user_slot_and_bank_overview_reads(self):
        slot = self.run_cli("patch", "slot", "U01-1", "--live", "--view", "overview", "--timeout", "20", timeout=40)
        preset = self.run_cli("patch", "preset", "P01-1", "--live", "--view", "overview", "--timeout", "20", timeout=40)
        bank = self.run_cli("patch", "bank", "U01", "--live", "--view", "overview", "--timeout", "20", timeout=80)

        self.assertIsInstance(slot.get("patchName"), str)
        self.assertIsInstance(preset.get("patchName"), str)
        self.assertEqual(bank["bank"], "U01")
        self.assertEqual([patch["slot"] for patch in bank["patches"]], ["U01-1", "U01-2", "U01-3", "U01-4", "U01-5"])
        self.assertEqual(bank["patches"][0]["data"]["patchName"], slot["patchName"])

    def test_patch_plans_build_without_writing(self):
        default = self.run_cli("patch", "plan", "default", timeout=30)
        four_cm = self.run_cli("patch", "plan", "4cm-template", timeout=30)
        schema = self.run_cli("patch", "schema", "fx1", timeout=30)
        fx_algorithm_schema = self.run_cli("patch", "schema", "fx1Chorus", timeout=30)
        fx4_schema = self.run_cli("patch", "schema", "fx4", timeout=30)
        fx4_algorithm_schema = self.run_cli("patch", "schema", "fx4Chorus", timeout=30)

        self.assertEqual(default["id"], "default")
        self.assertGreater(default["writeCount"], 0)
        self.assertEqual(four_cm["id"], "4cm-template")
        self.assertGreater(four_cm["writeCount"], 0)
        self.assertEqual(schema["id"], "fx1")
        self.assertGreater(schema["editableSize"], schema["summarySize"])
        self.assertEqual(fx_algorithm_schema["id"], "fx1Chorus")
        self.assertIn("effectLevel2", [parameter["id"] for parameter in fx_algorithm_schema["namedParameters"]])
        self.assertEqual(fx4_schema["id"], "fx4")
        self.assertEqual(fx4_schema["temporaryAddress"], ["10", "02", "01", "00"])
        self.assertEqual(fx4_algorithm_schema["id"], "fx4Chorus")
        self.assertEqual(fx4_algorithm_schema["temporaryAddress"], ["10", "02", "05", "00"])


@unittest.skipUnless(RUN_LIVE, "set GT1000_LIVE=1 to run live GT-1000 tests")
class LiveSkillSystemReadTests(unittest.TestCase):
    def run_cli(self, *args: str, timeout: int = 30) -> dict:
        result = subprocess.run(
            [str(SKILL_CLI), "--pretty", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=live_process_timeout(timeout),
            check=True,
        )
        return json.loads(result.stdout)

    def test_live_system_sections_decode(self):
        common = self.run_cli("system", "common", "--live", "--timeout", "20", timeout=40)
        midi = self.run_cli("system", "midi", "--live", "--timeout", "20", timeout=40)
        inout = self.run_cli("system", "inout", "--live", "--timeout", "20", timeout=40)
        effects = self.run_cli("system", "effects", "--live", "--timeout", "20", timeout=40)
        pitch = self.run_cli("system", "pitch", "--live", "--timeout", "20", timeout=40)
        controls = self.run_cli("system", "controls", "--live", "--timeout", "20", timeout=40)
        manual = self.run_cli("system", "manual", "--live", "--timeout", "20", timeout=40)

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
        pcmap = self.run_cli("system", "pcmap", "--live", "--bank", "1", "--timeout", "20", timeout=40)
        inputs = self.run_cli("system", "inputs", "--live", "--number", "1", "--timeout", "20", timeout=40)

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
    backup_file: Path | None = None
    backup_system_control_file: Path | None = None
    backup_patch_common: dict[str, list[int]] = {}
    backup_system_control_data: list[int] = []

    @classmethod
    def setUpClass(cls) -> None:
        if not LIVE_BACKUP_DIR:
            raise unittest.SkipTest("set GT1000_LIVE_BACKUP_DIR so destructive-test backups survive interruption")
        backup_root = Path(LIVE_BACKUP_DIR)
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_timestamp = int(time.time())
        cls.backup_file = Path(LIVE_BACKUP_FILE) if LIVE_BACKUP_FILE else backup_root / f"live-write-slot-backup-{backup_timestamp}.json"
        cls.backup_system_control_file = backup_root / f"live-write-system-control-backup-{backup_timestamp}.json"
        if not LIVE_BACKUP_FILE:
            cls.run_cli_class(
                "patch",
                "export",
                *LIVE_WRITE_RESTORE_SLOTS,
                "--output",
                str(cls.backup_file),
                "--live",
                "--timeout",
                "20",
                timeout=240,
            )
        if not cls.backup_file.is_file():
            raise unittest.SkipTest(f"destructive-test slot backup does not exist: {cls.backup_file}")
        cls.backup_patch_common = cls.patch_common_records_from_backup(cls.backup_file)
        if LIVE_SYSTEM_CONTROL_BACKUP_FILE:
            system_control = json.loads(Path(LIVE_SYSTEM_CONTROL_BACKUP_FILE).read_text(encoding="utf-8"))
        else:
            system_control = cls.run_cli_class("system", "controls", "--live", "--timeout", "20", timeout=40)
        cls.backup_system_control_data = [int(byte, 16) for byte in system_control["dataHex"].split()]
        if LIVE_BACKUP_DIR and cls.backup_system_control_file is not None and not LIVE_SYSTEM_CONTROL_BACKUP_FILE:
            cls.backup_system_control_file.write_text(json.dumps(system_control, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        restore_errors = []
        if cls.backup_file and cls.backup_file.is_file():
            try:
                cls.run_cli_class(
                    "patch",
                    "import",
                    str(cls.backup_file),
                    "--destination-start",
                    LIVE_WRITE_RESTORE_SLOTS[0],
                    "--live",
                    "--timeout",
                    "40",
                    timeout=360,
                )
                for slot, expected in cls.backup_patch_common.items():
                    actual = cls.read_patch_common(slot, timeout=12)
                    if actual != expected:
                        raise AssertionError(f"{slot} restored Patch Common bytes did not match the pre-test backup")
            except Exception as error:
                restore_errors.append(f"slot restore failed: {error}")
        if cls.backup_system_control_data:
            try:
                live.write_data_sets([live.PatchWrite("Restore System Control", live.SYSTEM_CONTROL, cls.backup_system_control_data)])
                time.sleep(0.25)
                system_control = cls.run_cli_class("system", "controls", "--live", "--timeout", "20", timeout=40)
                restored_data = [int(byte, 16) for byte in system_control["dataHex"].split()]
                if restored_data != cls.backup_system_control_data:
                    raise AssertionError("System Control restore did not match the pre-test backup bytes")
            except Exception as error:
                restore_errors.append(f"System Control restore failed: {error}")
        if restore_errors:
            raise AssertionError(
                "Destructive live test cleanup did not fully restore state: "
                + "; ".join(restore_errors)
            )

    @staticmethod
    def patch_common_records_from_backup(path: Path) -> dict[str, list[int]]:
        liveset = json.loads(path.read_text(encoding="utf-8"))
        records = {}
        for patch in liveset["patches"]:
            common = next(record for record in patch["records"] if record["label"] == "Patch Common")
            records[patch["sourceSlot"]] = [int(byte, 16) for byte in common["dataHex"].split()]
        return records

    @staticmethod
    def read_patch_common(slot: str, *, timeout: float) -> list[int]:
        address = live.remap_temporary_patch_address(live.TEMPORARY_PATCH_COMMON, live.user_patch_base(slot))
        request = live.PatchReadRequest("Patch Common", address, [0x00, 0x00, 0x00, 0x7E])
        data = live.read_data_sets(timeout=timeout, requests=[request])
        return data[live.address_key(address)]

    @classmethod
    def run_cli_class(cls, *args: str, timeout: int = 60) -> dict:
        try:
            result = subprocess.run(
                [str(SKILL_CLI), "--pretty", *args],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=live_process_timeout(timeout),
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise AssertionError(
                "CLI command failed: "
                + " ".join(str(part) for part in error.cmd)
                + f"\nexit: {error.returncode}"
                + f"\nstdout:\n{error.stdout}"
                + f"\nstderr:\n{error.stderr}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise AssertionError(
                "CLI command timed out: "
                + " ".join(str(part) for part in error.cmd)
                + f"\nstdout:\n{error.stdout}"
                + f"\nstderr:\n{error.stderr}"
            ) from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(
                "CLI command did not return JSON: "
                + " ".join([str(SKILL_CLI), "--pretty", *args])
                + f"\nstdout:\n{result.stdout}"
                + f"\nstderr:\n{result.stderr}"
            ) from error

    def run_cli(self, *args: str, timeout: int = 60) -> dict:
        return self.run_cli_class(*args, timeout=timeout)

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

        move_result = self.run_cli(
            "patch",
            "move",
            "delay1",
            "--before",
            "chorus",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["four_cm"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )
        self.assertEqual(move_result["plan"], "move:chain:15:before:14:U10-2")
        self.assert_verified_patch1_slot(move_result, "2E")

    def test_p1_edit_commands_verify_on_u10_3(self):
        initialize_result = self.run_cli(
            "patch",
            "initialize",
            "--name",
            "LIVE P1 INIT",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )
        self.assertEqual(initialize_result["plan"], "default:U10-3")
        self.assert_verified_patch1_slot(initialize_result, "2F")

        clear_result = self.run_cli(
            "patch",
            "clear",
            "--name",
            "LIVE P1 CLEAR",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=90,
        )
        self.assertEqual(clear_result["plan"], "default:U10-3")
        self.assert_verified_patch1_slot(clear_result, "2F")

        rename_result = self.run_cli(
            "patch",
            "rename",
            "LIVE P1 REN",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(rename_result["plan"], "rename:U10-3")
        self.assert_verified_patch1_slot(rename_result, "2F")

        raw_result = self.run_cli(
            "patch",
            "raw-set",
            "delay1",
            "0",
            "1",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(raw_result["plan"], "raw-set:delay1:0:byte:U10-3")
        self.assert_verified_patch1_slot(raw_result, "2F")

        fx4_type_result = self.run_cli(
            "patch",
            "set",
            "fx4",
            "type",
            "CHORUS",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(fx4_type_result["plan"], "set:fx4.type:U10-3")
        self.assert_verified(fx4_type_result)
        self.assertEqual(fx4_type_result["verification"]["checks"][0]["address"][:2], ["24", "23"])

        fx4_chorus_result = self.run_cli(
            "patch",
            "set",
            "fx4Chorus",
            "effectLevel2",
            "75",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(fx4_chorus_result["plan"], "set:fx4Chorus.effectLevel2:U10-3")
        self.assert_verified(fx4_chorus_result)
        self.assertEqual(fx4_chorus_result["verification"]["checks"][0]["address"][:2], ["24", "23"])

        master_result = self.run_cli(
            "patch",
            "master-set",
            "level",
            "95",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(master_result["plan"], "master-set:level:U10-3")
        self.assert_verified_patch1_slot(master_result, "2F")

        control_result = self.run_cli(
            "patch",
            "control-set",
            "ctl1",
            "dist1",
            "--mode",
            "toggle",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(control_result["plan"], "control:ctl1:dist1:U10-3")
        self.assert_verified_patch1_slot(control_result, "2F")

        system_control_result = self.run_cli(
            "patch",
            "system-control-set",
            "ctl1",
            "dist1",
            "--mode",
            "toggle",
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(system_control_result["plan"], "system-control:ctl1:dist1")
        self.assert_verified(system_control_result)

        preference_result = self.run_cli(
            "patch",
            "control-preference-set",
            "ctl1",
            "patch",
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(preference_result["plan"], "control-preference:ctl1:patch")
        self.assert_verified(preference_result)

        led_result = self.run_cli(
            "patch",
            "led-set",
            "ctl1",
            "on",
            "auto-cyan",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(led_result["plan"], "led:ctl1:on:auto-cyan:U10-3")
        self.assert_verified_patch1_slot(led_result, "2F")

        assign_result = self.run_cli(
            "patch",
            "assign-set",
            "2",
            "--target",
            "tuner",
            "--min",
            "0",
            "--max",
            "1",
            "--source",
            "internal-pedal",
            "--mode",
            "toggle",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(assign_result["plan"], "set:assign2:target987:source19:U10-3")
        self.assert_verified_patch1_slot(assign_result, "2F")

    def test_existing_edit_and_midi_commands_have_live_paths(self):
        enable_result = self.run_cli(
            "patch",
            "enable",
            "delay1",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(enable_result["plan"], "set:delay1.sw:U10-3")
        self.assert_verified_patch1_slot(enable_result, "2F")

        disable_result = self.run_cli(
            "patch",
            "disable",
            "delay1",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(disable_result["plan"], "set:delay1.sw:U10-3")
        self.assert_verified_patch1_slot(disable_result, "2F")

        type_result = self.run_cli(
            "patch",
            "type",
            "dist1",
            "T-SCREAM",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(type_result["plan"], "set:dist1.type:U10-3")
        self.assert_verified_patch1_slot(type_result, "2F")

        bpm_result = self.run_cli(
            "patch",
            "set-bpm",
            "120.0",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(bpm_result["plan"], "set:masterBpm:U10-3")
        self.assert_verified_patch1_slot(bpm_result, "2F")

        assign_cc_result = self.run_cli(
            "patch",
            "assign-cc",
            "3",
            "delay1",
            "sw",
            "--cc",
            "80",
            "--mode",
            "moment",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(assign_cc_result["plan"], "set:assign3:cc80:target158:U10-3")
        self.assert_verified_patch1_slot(assign_cc_result, "2F")

        tuner_assign_result = self.run_cli(
            "patch",
            "tuner-assign",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["parameter"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assertEqual(tuner_assign_result["plan"], "set:tunerAssign:U10-3")
        self.assert_verified_patch1_slot(tuner_assign_result, "2F")

        cc_result = self.run_cli("midi", "cc", "80", "0", "--channel", "1", "--live", timeout=60)
        self.assertEqual(cc_result["type"], "controlChange")
        self.assertEqual(cc_result["controller"], 80)

        bank_result = self.run_cli("midi", "bank-select", "0", "--channel", "1", "--live", timeout=60)
        self.assertEqual(bank_result["type"], "bankSelect")
        self.assertEqual(len(bank_result["messagesHex"]), 2)

        pc_result = self.run_cli("midi", "pc", "1", "--channel", "1", "--live", timeout=60)
        self.assertEqual(pc_result["type"], "programChange")
        self.assertEqual(pc_result["program"], 1)

        select_result = self.run_cli("patch", "select", LIVE_WRITE_SLOTS["default"], "--live", "--channel", "1", timeout=60)
        self.assertEqual(select_result["selectedSlot"], "U10-1")
        self.assertEqual(len(select_result["messagesHex"]), 3)

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
            timeout=360,
        )
        destination = self.run_cli(
            "patch",
            "slot",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--view",
            "overview",
            "--timeout",
            "20",
            timeout=40,
        )

        self.assertEqual(clone_result["plan"], "clone:U10-4:U11-1")
        self.assertEqual(clone_result["sourceSlot"], "U10-4")
        self.assertEqual(clone_result["destinationSlot"], "U11-1")
        self.assert_verified(clone_result)
        self.assertEqual(destination["patchName"], "LIVE CLONE SRC")

    def test_zy_restore_preset_primary_records_to_restricted_user_slot(self):
        result = self.run_cli(
            "patch",
            "restore-preset",
            "P01-1",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=360,
        )

        self.assertEqual(result["plan"], "restore-preset:P01-1:U11-1")
        self.assertEqual(result["recordScope"], "documented-primary-patch-records")
        self.assertEqual(result["destinationSlot"], "U11-1")
        checks = result["verification"]["checks"]
        failed = [check for check in checks if not check["ok"]]
        self.assertTrue(checks)
        self.assertEqual([check["label"] for check in failed], ["Restore P01-1 Patch Effect"])

    def test_patch_copy_and_exchange_between_restricted_user_slots(self):
        source_result = self.run_cli(
            "patch",
            "rename",
            "LIVE COPY SRC",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["clone_source"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        destination_seed = self.run_cli(
            "patch",
            "rename",
            "LIVE COPY DST",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assert_verified(source_result)
        self.assert_verified(destination_seed)

        copy_result = self.run_cli(
            "patch",
            "copy",
            LIVE_WRITE_SLOTS["clone_source"],
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=360,
        )
        copied = self.run_cli(
            "patch",
            "slot",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--view",
            "overview",
            "--timeout",
            "20",
            timeout=40,
        )
        self.assertEqual(copy_result["plan"], "clone:U10-4:U11-1")
        self.assert_verified(copy_result)
        self.assertEqual(copied["patchName"], "LIVE COPY SRC")

        exchange_source_seed = self.run_cli(
            "patch",
            "rename",
            "LIVE EXCH A",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["clone_source"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        exchange_destination_seed = self.run_cli(
            "patch",
            "rename",
            "LIVE EXCH B",
            "--live",
            "--user-slot",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--verify",
            "--timeout",
            "20",
            timeout=60,
        )
        self.assert_verified(exchange_source_seed)
        self.assert_verified(exchange_destination_seed)

        exchange_result = self.run_cli(
            "patch",
            "exchange",
            LIVE_WRITE_SLOTS["clone_source"],
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=360,
        )
        exchanged_source = self.run_cli(
            "patch",
            "slot",
            LIVE_WRITE_SLOTS["clone_source"],
            "--live",
            "--view",
            "overview",
            "--timeout",
            "20",
            timeout=40,
        )
        self.assertEqual(exchange_result["plan"], "exchange:U10-4:U11-1")
        self.assert_verified(exchange_result)
        self.assertEqual(exchanged_source["patchName"], "LIVE EXCH B")

    def test_zz_batch_patch_management_commands(self):
        init_result = self.run_cli(
            "patch",
            "batch-initialize",
            LIVE_WRITE_SLOTS["clone_source"],
            LIVE_WRITE_SLOTS["clone_template"],
            "--name-prefix",
            "LIVE BINIT",
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=360,
        )
        self.assertEqual(init_result["plan"], "batch-initialize:U10-4:2")
        self.assert_verified(init_result)

        copy_result = self.run_cli(
            "patch",
            "batch-copy",
            LIVE_WRITE_SLOTS["clone_source"],
            LIVE_WRITE_SLOTS["clone_template"],
            "--destination-start",
            LIVE_WRITE_SLOTS["clone_destination"],
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=360,
        )
        self.assertEqual(copy_result["plan"], "batch-copy:U10-4:U11-1:2")
        self.assert_verified(copy_result)
        self.assertEqual(
            [operation["destinationSlot"] for operation in copy_result["operations"]],
            ["U11-1", "U11-2"],
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "live-liveset.json"
            tsl_output = Path(directory) / "live-liveset.tsl"
            export_result = self.run_cli(
                "patch",
                "export",
                LIVE_WRITE_SLOTS["clone_source"],
                LIVE_WRITE_SLOTS["clone_template"],
                "--output",
                str(output),
                "--live",
                "--timeout",
                "20",
                timeout=360,
            )
            self.assertEqual(export_result["format"], "gt1000-agent-liveset-v1")
            self.assertEqual(export_result["patchCount"], 2)
            self.assertTrue(output.is_file())

            liveset_list = self.run_cli("patch", "liveset-list", str(output), timeout=30)
            self.assertEqual(liveset_list["patchCount"], 2)

            moved_output = Path(directory) / "live-liveset-moved.json"
            liveset_move = self.run_cli(
                "patch",
                "liveset-move",
                str(output),
                "2",
                "1",
                "--output",
                str(moved_output),
                timeout=30,
            )
            self.assertEqual(liveset_move["patchCount"], 2)
            self.assertTrue(moved_output.is_file())

            copied_output = Path(directory) / "live-liveset-copied.json"
            liveset_copy = self.run_cli(
                "patch",
                "liveset-copy",
                str(output),
                "1",
                "2",
                "--output",
                str(copied_output),
                timeout=30,
            )
            self.assertEqual(liveset_copy["patchCount"], 3)
            self.assertTrue(copied_output.is_file())

            renamed_output = Path(directory) / "live-liveset-renamed.json"
            liveset_rename = self.run_cli(
                "patch",
                "liveset-rename",
                str(output),
                "1",
                "LIVE RENAMED",
                "--output",
                str(renamed_output),
                timeout=30,
            )
            self.assertEqual(liveset_rename["patches"][0]["patchName"], "LIVE RENAMED")
            self.assertTrue(renamed_output.is_file())

            removed_output = Path(directory) / "live-liveset-removed.json"
            liveset_remove = self.run_cli(
                "patch",
                "liveset-remove",
                str(output),
                "2",
                "--output",
                str(removed_output),
                timeout=30,
            )
            self.assertEqual(liveset_remove["patchCount"], 1)
            self.assertTrue(removed_output.is_file())

            tsl_export = self.run_cli(
                "patch",
                "tsl-export",
                str(output),
                "--output",
                str(tsl_output),
                "--name",
                "LIVE TEST SET",
                timeout=30,
            )
            self.assertEqual(tsl_export["format"], "gt1000-agent-tsl-json-v1")
            self.assertEqual(tsl_export["patchCount"], 2)
            self.assertTrue(tsl_export["canImportRecords"])
            self.assertTrue(tsl_output.is_file())

            tsl_list = self.run_cli("patch", "tsl-list", str(tsl_output), timeout=30)
            self.assertEqual(tsl_list["patchCount"], 2)
            self.assertTrue(tsl_list["canImportRecords"])

            import_result = self.run_cli(
                "patch",
                "import",
                str(output),
                "--destination-start",
                LIVE_WRITE_SLOTS["clone_destination"],
                "--live",
                "--verify",
                "--timeout",
                "20",
                timeout=360,
            )
            self.assertEqual(import_result["plan"], "liveset-import:U11-1:2")
            self.assertEqual(import_result["destinationSlots"], ["U11-1", "U11-2"])
            self.assert_verified(import_result)

            tsl_import_result = self.run_cli(
                "patch",
                "tsl-import",
                str(tsl_output),
                "--destination-start",
                LIVE_WRITE_SLOTS["clone_destination"],
                "--live",
                "--verify",
                "--timeout",
                "20",
                timeout=360,
            )
            self.assertEqual(tsl_import_result["plan"], "liveset-import:U11-1:2")
            self.assertEqual(tsl_import_result["destinationSlots"], ["U11-1", "U11-2"])
            self.assert_verified(tsl_import_result)

        insert_result = self.run_cli(
            "patch",
            "insert",
            LIVE_WRITE_SLOTS["clone_source"],
            LIVE_WRITE_SLOTS["clone_destination"],
            "--range-end",
            "U11-2",
            "--live",
            "--verify",
            "--timeout",
            "20",
            timeout=360,
        )
        self.assertEqual(insert_result["plan"], "insert:U10-4:U11-1:U11-2")
        self.assert_verified(insert_result)

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
