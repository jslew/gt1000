import json
import io
import multiprocessing
import sys
import time
import tempfile
import unittest
import importlib.util
from unittest.mock import MagicMock
from pathlib import Path

sys.dont_write_bytecode = True

from tools.gt1000 import agent_cli


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "full_patch.json"


def live_verified_command_paths():
    path = Path(__file__).resolve().parent / "test_live_skill.py"
    spec = importlib.util.spec_from_file_location("test_live_skill_manifest", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.LIVE_VERIFIED_COMMAND_PATHS


class AgentCLITests(unittest.TestCase):
    def setUp(self):
        self._validation_log_dir = tempfile.TemporaryDirectory()
        self._validation_log_env = unittest.mock.patch.dict(
            agent_cli.os.environ,
            {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(self._validation_log_dir.name) / "encoding-validations.jsonl")},
            clear=False,
        )
        self._validation_log_env.start()

    def tearDown(self):
        self._validation_log_env.stop()
        self._validation_log_dir.cleanup()

    def test_ports_parser_and_live_timeout_wrapper(self):
        args = agent_cli.build_parser().parse_args(["ports", "--live", "--timeout", "2"])
        self.assertEqual(args.command, "ports")
        self.assertEqual(args.timeout, 2)

        self.assertEqual(agent_cli.live_call_with_timeout("test", 2, sorted, [3, 1, 2]), [1, 2, 3])
        self.assertEqual(len(agent_cli.live_call_with_timeout("large", 5, bytes, 1024 * 1024)), 1024 * 1024)
        with self.assertRaises(agent_cli.CLIError) as context:
            agent_cli.live_call_with_timeout("test", 0.1, time.sleep, 5)
        self.assertIn("did not finish", str(context.exception))
        self.assertIn("Verify BOSS Tone Studio", str(context.exception))

    def test_stop_live_process_kills_running_child(self):
        context = multiprocessing.get_context("spawn")
        process = context.Process(target=time.sleep, args=(30,))
        process.start()
        try:
            agent_cli.stop_live_process(process, terminate_timeout=0.1)
            self.assertFalse(process.is_alive())
        finally:
            if process.is_alive():
                process.kill()
                process.join(1)
            process.close()

    def test_live_timeout_wrapper_preserves_kwargs_and_mock_fallback(self):
        def kwonly(*, value):
            return value

        self.assertEqual(agent_cli.live_call_with_timeout("kwargs", 2, kwonly, value=7), 7)

        mock = MagicMock(return_value={"ok": True})
        self.assertEqual(agent_cli.live_call_with_timeout("mock", 2, mock, timeout=8.0), {"ok": True})
        mock.assert_called_once_with(timeout=8.0)

    def test_diagnostic_log_option_writes_jsonl_events(self):
        parser = agent_cli.build_parser()
        args = parser.parse_args(["--diagnostic-log", "diag.jsonl", "ports", "--live"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / args.diagnostic_log
            old_value = agent_cli.os.environ.get(agent_cli.DIAGNOSTIC_LOG_ENV)
            try:
                args.diagnostic_log = str(path)
                result = agent_cli.configure_diagnostic_logging(args)
                agent_cli.diagnostic_event("test.event", value=7)
            finally:
                if old_value is None:
                    agent_cli.os.environ.pop(agent_cli.DIAGNOSTIC_LOG_ENV, None)
                else:
                    agent_cli.os.environ[agent_cli.DIAGNOSTIC_LOG_ENV] = old_value

            self.assertEqual(result, str(path))
            lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(lines[0]["event"], "diagnostic.start")
            self.assertEqual(lines[1]["event"], "test.event")
            self.assertEqual(lines[1]["value"], 7)

    def test_diagnostic_log_normalization_keeps_subcommand_when_value_is_omitted(self):
        argv = ["--pretty", "--diagnostic-log", "patch", "encoding-status"]
        normalized = agent_cli.normalize_diagnostic_log_argv(argv)

        self.assertEqual(normalized, ["--pretty", "--diagnostic-log=auto", "patch", "encoding-status"])
        args = agent_cli.build_parser().parse_args(normalized)
        self.assertEqual(args.diagnostic_log, "auto")
        self.assertEqual(args.command, "patch")
        self.assertEqual(args.patch_command, "encoding-status")

    def test_diagnostic_log_normalization_preserves_explicit_path(self):
        argv = ["--diagnostic-log", "diag.jsonl", "ports", "--live"]

        self.assertEqual(agent_cli.normalize_diagnostic_log_argv(argv), argv)

    def test_validate_encoding_auto_enables_diagnostic_log(self):
        parser = agent_cli.build_parser()
        args = parser.parse_args(["patch", "validate-encoding", "master", "level", "90", "--live"])

        with tempfile.TemporaryDirectory() as directory:
            old_value = agent_cli.os.environ.get(agent_cli.DIAGNOSTIC_LOG_ENV)
            try:
                with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_DIAGNOSTIC_DIR": directory}, clear=False):
                    path = agent_cli.configure_diagnostic_logging(args)
            finally:
                if old_value is None:
                    agent_cli.os.environ.pop(agent_cli.DIAGNOSTIC_LOG_ENV, None)
                else:
                    agent_cli.os.environ[agent_cli.DIAGNOSTIC_LOG_ENV] = old_value

            self.assertIsNotNone(path)
            self.assertTrue(Path(path).is_file())
            self.assertEqual(Path(path).parent, Path(directory))

    def test_validate_encoding_batch_auto_enables_diagnostic_log(self):
        parser = agent_cli.build_parser()
        args = parser.parse_args(["patch", "validate-encoding-batch", "master.level=90", "--live"])

        with tempfile.TemporaryDirectory() as directory:
            old_value = agent_cli.os.environ.get(agent_cli.DIAGNOSTIC_LOG_ENV)
            try:
                with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_DIAGNOSTIC_DIR": directory}, clear=False):
                    path = agent_cli.configure_diagnostic_logging(args)
            finally:
                if old_value is None:
                    agent_cli.os.environ.pop(agent_cli.DIAGNOSTIC_LOG_ENV, None)
                else:
                    agent_cli.os.environ[agent_cli.DIAGNOSTIC_LOG_ENV] = old_value

            self.assertIsNotNone(path)
            self.assertTrue(Path(path).is_file())
            self.assertEqual(Path(path).parent, Path(directory))

    def test_validate_encoding_scope_auto_enables_diagnostic_log(self):
        parser = agent_cli.build_parser()
        args = parser.parse_args(["patch", "validate-encoding-scope", "master", "--live"])

        with tempfile.TemporaryDirectory() as directory:
            old_value = agent_cli.os.environ.get(agent_cli.DIAGNOSTIC_LOG_ENV)
            try:
                with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_DIAGNOSTIC_DIR": directory}, clear=False):
                    path = agent_cli.configure_diagnostic_logging(args)
            finally:
                if old_value is None:
                    agent_cli.os.environ.pop(agent_cli.DIAGNOSTIC_LOG_ENV, None)
                else:
                    agent_cli.os.environ[agent_cli.DIAGNOSTIC_LOG_ENV] = old_value

            self.assertIsNotNone(path)
            self.assertTrue(Path(path).is_file())
            self.assertEqual(Path(path).parent, Path(directory))

    def test_parse_encoding_validation_case_accepts_dot_and_colon_forms(self):
        self.assertEqual(
            agent_cli.parse_encoding_validation_case("master.level=90"),
            ("master", "level", "90"),
        )
        self.assertEqual(
            agent_cli.parse_encoding_validation_case("block:delay1.sw=on"),
            ("block", "delay1.sw", "on"),
        )
        with self.assertRaises(ValueError):
            agent_cli.parse_encoding_validation_case("delay1.sw=on")

    def test_record_encoding_validation_writes_compact_jsonl_record(self):
        result = {
            "area": "master",
            "field": "level",
            "slot": "U10-1",
            "targetValue": "90",
            "confidenceBefore": {"confidence": "legacy"},
            "confidenceRecommendation": "live-verified",
            "write": {"verified": True},
            "restored": True,
            "restore": {"verified": True},
            "before": [
                {
                    "address": ["20", "2D", "10", "5F"],
                    "readAddress": ["20", "2D", "10", "5F"],
                    "readSize": ["00", "00", "00", "02"],
                    "readOffset": 0,
                    "data": [5, 10],
                    "dataHex": "05 0A",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "encoding-validations.jsonl"
            with unittest.mock.patch.dict(
                agent_cli.os.environ,
                {
                    agent_cli.DIAGNOSTIC_LOG_ENV: str(Path(directory) / "diag.jsonl"),
                    agent_cli.ENCODING_VALIDATION_LOG_ENV: str(log_path),
                },
                clear=False,
            ):
                path = agent_cli.record_encoding_validation(result, "patch.master.level")

            self.assertEqual(path, str(log_path))
            record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["fieldId"], "patch.master.level")
            self.assertEqual(record["confidenceRecommendation"], "live-verified")
            self.assertEqual(record["before"][0]["dataHex"], "05 0A")
            self.assertNotIn("data", record["before"][0])

    def test_encoding_status_includes_validation_log_summary(self):
        records = [
            {"fieldId": "patch.block.delay3.sw", "confidenceRecommendation": "not-verified", "slot": "U10-1"},
            {
                "fieldId": "patch.block.delay3.sw",
                "createdAt": "2026-05-25T20:30:00-0400",
                "confidenceRecommendation": "live-verified",
                "slot": "U10-1",
                "targetValue": "on",
                "diagnosticLog": "/tmp/diag.jsonl",
                "writeVerified": True,
                "restored": True,
                "restoreVerified": True,
            },
            {"malformed": True},
        ]

        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "encoding-validations.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\nnot json\n",
                encoding="utf-8",
            )
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(log_path)}, clear=False):
                status = agent_cli.cmd_patch_encoding_status(
                    agent_cli.build_parser().parse_args(["patch", "encoding-status", "patch.block.delay3.sw"])
                )

        self.assertEqual(status["validationLog"], str(log_path))
        self.assertEqual(status["trustedCount"], 1)
        self.assertEqual(status["untrustedCount"], 0)
        entry = status["entries"][0]
        self.assertEqual(entry["id"], "patch.block.delay3.sw")
        self.assertEqual(entry["confidence"], "legacy")
        self.assertEqual(entry["effectiveConfidence"], "live-verified")
        self.assertTrue(entry["trustedEncoding"])
        self.assertEqual(entry["validationCount"], 2)
        self.assertEqual(entry["validationRecommendations"]["live-verified"], 1)
        self.assertEqual(entry["validationSuggestedConfidence"], "live-verified")
        self.assertEqual(entry["latestValidation"]["targetValue"], "on")
        self.assertNotIn("before", entry["latestValidation"])

    def test_encoding_status_infers_block_family_from_representative_validations(self):
        records = [
            {
                "fieldId": field_id,
                "confidenceRecommendation": "live-verified",
                "writeVerified": True,
                "restored": False,
                "restoreVerified": None,
                "slot": "U10-1",
            }
            for field_id in [
                "patch.block.chorus.effectLevel",
                "patch.block.delay1.effectLevel",
                "patch.block.fx1AWah.effectLevel",
            ]
        ]
        log_path = Path(agent_cli.os.environ[agent_cli.ENCODING_VALIDATION_LOG_ENV])
        log_path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

        status = agent_cli.cmd_patch_encoding_status(
            agent_cli.build_parser().parse_args(["patch", "encoding-status", "patch.block.delay2.effectLevel"])
        )

        entry = status["entries"][0]
        self.assertEqual(entry["confidence"], "legacy")
        self.assertEqual(entry["effectiveConfidence"], "inferred")
        self.assertFalse(entry["trustedEncoding"])
        self.assertEqual(entry["familyValidation"]["successfulBlockCount"], 3)
        effective = agent_cli.effective_encoding_confidence("patch.block.delay2.effectLevel")
        self.assertEqual(effective["confidence"], "inferred")
        self.assertEqual(effective["semanticConfidence"], "legacy")
        self.assertIn("layout/encoding evidence only", effective["evidence"])

    def test_parser_defaults_use_live_timeout_strategy(self):
        parser = agent_cli.build_parser()
        cases = [
            (["ports", "--live"], agent_cli.QUICK_TIMEOUT),
            (["patch", "overview", "--live"], agent_cli.QUICK_TIMEOUT),
            (["patch", "musician-summary", "--live"], agent_cli.FOCUSED_TIMEOUT),
            (["patch", "performance", "--live"], agent_cli.FOCUSED_TIMEOUT),
            (["patch", "summary", "--live"], agent_cli.FULL_READ_TIMEOUT),
            (["patch", "slot", "U01-1", "--live", "--view", "musician-summary"], agent_cli.PERSISTENT_TIMEOUT),
            (["patch", "bank", "U01", "--live", "--view", "musician-summary"], agent_cli.PERSISTENT_TIMEOUT),
            (["patch", "setlist-audit", "U10", "--live"], agent_cli.FULL_READ_TIMEOUT),
            (["patch", "diff", "U10-1", "U10-2", "--live"], agent_cli.PERSISTENT_TIMEOUT),
            (["patch", "clone", "U10-1", "U10-2", "--live"], agent_cli.PERSISTENT_TIMEOUT),
            (["patch", "export", "U10-1", "--output", "backup.json", "--live"], agent_cli.PERSISTENT_TIMEOUT),
            (["patch", "enable", "delay1", "--live", "--verify"], agent_cli.FULL_READ_TIMEOUT),
            (["patch", "system-control-set", "ctl1", "tuner", "--live", "--verify"], agent_cli.PERSISTENT_TIMEOUT),
        ]
        for argv, expected_timeout in cases:
            with self.subTest(argv=argv):
                self.assertEqual(parser.parse_args(argv).timeout, expected_timeout)

    def test_live_midi_environment_fast_fails_in_codex_sandbox(self):
        with unittest.mock.patch.dict(agent_cli.os.environ, {"CODEX_SANDBOX": "workspace-write"}, clear=False):
            with unittest.mock.patch.object(agent_cli, "macos_coremidi_mach_lookup_allowed", return_value=True):
                reason = agent_cli.live_midi_environment_block_reason()

        self.assertEqual(reason, "workspace-write sandbox is active")

    def test_live_midi_environment_fast_fails_when_seatbelt_denies_coremidi(self):
        with unittest.mock.patch.dict(agent_cli.os.environ, {}, clear=False):
            agent_cli.os.environ.pop("CODEX_SANDBOX", None)
            agent_cli.os.environ.pop("SANDBOX_MODE", None)
            with unittest.mock.patch.object(agent_cli, "macos_coremidi_mach_lookup_allowed", return_value=False):
                reason = agent_cli.live_midi_environment_block_reason()

        self.assertIn("CoreMIDI", reason)

    def test_live_midi_sandbox_override_allows_experimental_probe(self):
        with unittest.mock.patch.dict(agent_cli.os.environ, {
            "CODEX_SANDBOX": "workspace-write",
            "GT1000_ALLOW_SANDBOXED_COREMIDI": "1",
        }, clear=False):
            reason = agent_cli.live_midi_environment_block_reason()

        self.assertIsNone(reason)

    def test_main_fast_fails_live_command_before_touching_coremidi(self):
        stderr = io.StringIO()
        with unittest.mock.patch.dict(agent_cli.os.environ, {"CODEX_SANDBOX": "workspace-write"}, clear=False):
            with unittest.mock.patch.object(agent_cli.live, "list_ports") as list_ports:
                with unittest.mock.patch("sys.stderr", stderr):
                    code = agent_cli.main(["ports", "--live", "--timeout", "8"])

        self.assertEqual(code, 77)
        self.assertIn("execution sandbox", stderr.getvalue())
        list_ports.assert_not_called()

    def test_doctor_parser_and_status_from_mocked_checks(self):
        args = agent_cli.build_parser().parse_args(["doctor", "--live", "--user-slot", "U10-1", "--write-check"])
        self.assertEqual(args.command, "doctor")
        self.assertTrue(args.write_check)

        checks = [
            {"name": "endpoints", "ok": True},
            {"name": "sysex", "ok": True},
            {"name": "currentPatch", "ok": True},
            {"name": "userSlot", "ok": False, "error": "partial"},
            {"name": "midiRxChannel", "ok": True},
            {"name": "writeVerify", "ok": True},
        ]

        with unittest.mock.patch.object(agent_cli, "doctor_check", side_effect=checks):
            result = agent_cli.cmd_doctor(args)

        self.assertEqual(result["id"], "doctor")
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["failedOptionalChecks"], ["userSlot"])

    def test_patch_export_uses_process_timeout_guard_for_slot_reads(self):
        calls = []

        def fake_required_read(label, timeout, requests):
            calls.append((label, timeout, len(requests)))
            return {
                agent_cli.live.address_key(request.address): [0] * agent_cli.live.seven_bit_address_value(request.size)
                for request in requests
            }

        original_required = agent_cli.read_required_patch_records_with_timeout
        original_lenient = agent_cli.read_patch_records_lenient_with_timeout
        agent_cli.read_required_patch_records_with_timeout = fake_required_read
        agent_cli.read_patch_records_lenient_with_timeout = fake_required_read
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "export.json"
                args = agent_cli.build_parser().parse_args([
                    "patch", "export", "U10-1", "--output", str(output), "--live", "--timeout", "7",
                ])
                result = agent_cli.cmd_patch_export(args)
        finally:
            agent_cli.read_patch_records_lenient_with_timeout = original_lenient
            agent_cli.read_required_patch_records_with_timeout = original_required

        self.assertEqual(result["patchCount"], 1)
        self.assertEqual(calls, [
            ("patch export U10-1 --live required record", 7.0, 2),
            ("patch export U10-1 --live core records", 7.0, len(agent_cli.patch_edit.clone_core_read_requests("U10-1")) - 2),
            ("patch export U10-1 --live active FX records", 7.0, 4),
        ])

    def test_patch_record_timeout_helper_guards_whole_operation(self):
        requests = [
            agent_cli.live.PatchReadRequest(f"Read {index}", [0x20, 0x00, index, 0x00], [0, 0, 0, 1])
            for index in range(agent_cli.patch_edit.VERIFY_READ_BATCH_SIZE + 1)
        ]

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            return {agent_cli.live.address_key(request.address): [request.address[2]] for request in requests}

        live_call = MagicMock(side_effect=fake_live_call)
        sleep = MagicMock()
        original = agent_cli.live_call_with_timeout
        original_sleep = agent_cli.time.sleep
        agent_cli.live_call_with_timeout = live_call
        agent_cli.time.sleep = sleep
        try:
            result = agent_cli.read_patch_records_with_timeout("records", 9, requests)
        finally:
            agent_cli.time.sleep = original_sleep
            agent_cli.live_call_with_timeout = original

        self.assertEqual(sorted(result), [agent_cli.live.address_key(request.address) for request in requests])
        self.assertEqual(live_call.call_count, 1)
        self.assertEqual(live_call.call_args_list[0].args[0], "records")
        self.assertEqual(live_call.call_args_list[0].args[1], agent_cli.patch_record_process_timeout(9, len(requests)))
        self.assertIs(live_call.call_args_list[0].args[2], agent_cli.patch_edit.read_data_sets_batched)
        self.assertEqual(len(live_call.call_args_list[0].kwargs["requests"]), len(requests))

    def test_patch_record_timeout_helper_prefers_larger_duplicate_address_read(self):
        requests = [
            agent_cli.live.PatchReadRequest("Patch Name", [0x10, 0x00, 0x00, 0x00], [0, 0, 0, 0x10]),
            agent_cli.live.PatchReadRequest("Patch Common", [0x10, 0x00, 0x00, 0x00], [0, 0, 0, 0x7E]),
        ]

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            return {agent_cli.live.address_key(requests[0].address): [0] * agent_cli.live.seven_bit_address_value(requests[0].size)}

        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = MagicMock(side_effect=fake_live_call)
        try:
            result = agent_cli.read_patch_records_with_timeout("records", 9, requests)
            sent_requests = agent_cli.live_call_with_timeout.call_args.kwargs["requests"]
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertEqual(len(sent_requests), 1)
        self.assertEqual(sent_requests[0].label, "Patch Common")
        self.assertEqual(len(result["10 00 00 00"]), 0x7E)

    def test_verify_plan_uses_single_session_reader(self):
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-test",
            "Verify test",
            [agent_cli.live.PatchWrite("Write", [0x20, 0x00, 0x00, 0x00], [1])],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            return {agent_cli.live.address_key(requests[0].address): [1]}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.verify_plan_with_timeout(plan, timeout=9)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])
        self.assertIs(live_call.call_args_list[0].args[2], agent_cli.patch_edit.read_data_sets_sequential_session)

    def test_verify_plan_reads_exact_bytes_for_live_verified_level_write(self):
        address = agent_cli.patch_master_level_address("U10-1")
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-level",
            "Verify level",
            [agent_cli.live.PatchWrite("Level", address, [5, 10])],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            self.assertEqual(requests[0].address, address)
            self.assertEqual(requests[0].size, [0x00, 0x00, 0x00, 0x02])
            return {agent_cli.live.address_key(requests[0].address): [5, 10]}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.verify_plan_with_timeout(plan, timeout=9)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"][0]["readOffset"], 0)
        self.assertEqual(result["checks"][0]["actualHex"], "05 0A")

    def test_verify_plan_uses_short_timeout_for_tiny_exact_reads(self):
        address = agent_cli.patch_master_level_address("U10-1")
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-level",
            "Verify level",
            [agent_cli.live.PatchWrite("Level", address, [5, 10])],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            self.assertEqual(timeout, agent_cli.TARGETED_READ_TIMEOUT)
            self.assertLess(process_timeout, 10)
            return {agent_cli.live.address_key(requests[0].address): [5, 10]}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.verify_plan_with_timeout(plan, timeout=20)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])

    def test_verify_plan_exact_mode_reads_write_range_without_confidence_gate(self):
        address = agent_cli.patch_edit.remap_clone_address(
            agent_cli.patch_edit.parameter_address(
                agent_cli.patch_edit.find_patch_block("delay3"),
                0,
            ),
            "U10-1",
        )
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-delay3-sw",
            "Verify Delay 3 switch",
            [agent_cli.live.PatchWrite("Delay 3 switch", address, [1])],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            self.assertEqual(requests[0].address, address)
            self.assertEqual(requests[0].size, [0x00, 0x00, 0x00, 0x01])
            return {agent_cli.live.address_key(requests[0].address): [1]}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.verify_plan_with_timeout(plan, timeout=20, exact=True)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"][0]["readOffset"], 0)

    def test_verify_plan_reads_exact_bytes_for_live_verified_block_parameter(self):
        address = agent_cli.patch_edit.remap_clone_address(
            agent_cli.patch_edit.parameter_address(
                agent_cli.patch_edit.find_patch_block("delay1"),
                0,
            ),
            "U10-1",
        )
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-delay1-sw",
            "Verify Delay 1 switch",
            [agent_cli.live.PatchWrite("Delay 1 switch", address, [1])],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            self.assertEqual(requests[0].address, address)
            self.assertEqual(requests[0].size, [0x00, 0x00, 0x00, 0x01])
            return {agent_cli.live.address_key(requests[0].address): [1]}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.verify_plan_with_timeout(plan, timeout=9)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"][0]["readOffset"], 0)
        self.assertEqual(result["checks"][0]["actualHex"], "01")

    def test_verify_plan_reads_exact_bytes_for_live_verified_nibble_block_parameter(self):
        address = agent_cli.patch_edit.remap_clone_address(
            agent_cli.patch_edit.parameter_address(
                agent_cli.patch_edit.find_patch_block("delay1"),
                1,
            ),
            "U10-1",
        )
        expected = [0x00, 0x01, 0x0A, 0x04]
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-delay1-time",
            "Verify Delay 1 time",
            [agent_cli.live.PatchWrite("Delay 1 time", address, expected)],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            self.assertEqual(requests[0].address, address)
            self.assertEqual(requests[0].size, [0x00, 0x00, 0x00, 0x04])
            return {agent_cli.live.address_key(requests[0].address): expected}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.verify_plan_with_timeout(plan, timeout=9)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"][0]["readOffset"], 0)
        self.assertEqual(result["checks"][0]["actualHex"], "00 01 0A 04")

    def test_verify_plan_uses_validation_log_for_effective_exact_read(self):
        address = agent_cli.patch_edit.remap_clone_address(
            agent_cli.patch_edit.parameter_address(
                agent_cli.patch_edit.find_patch_block("delay3"),
                1,
            ),
            "U10-1",
        )
        expected = [0x00, 0x01, 0x0A, 0x04]
        plan = agent_cli.patch_edit.PatchPlan(
            "verify-delay3-time",
            "Verify Delay 3 time",
            [agent_cli.live.PatchWrite("Delay 3 time", address, expected)],
        )

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            self.assertEqual(requests[0].address, address)
            self.assertEqual(requests[0].size, [0x00, 0x00, 0x00, 0x04])
            return {agent_cli.live.address_key(requests[0].address): expected}

        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "encoding-validations.jsonl"
            log_path.write_text(json.dumps({
                "fieldId": "patch.block.delay3.time",
                "confidenceRecommendation": "live-verified",
                "writeVerified": True,
                "restored": True,
                "restoreVerified": True,
                "diagnosticLog": "/tmp/diag.jsonl",
            }) + "\n", encoding="utf-8")
            live_call = MagicMock(side_effect=fake_live_call)
            original = agent_cli.live_call_with_timeout
            agent_cli.live_call_with_timeout = live_call
            try:
                with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(log_path)}, clear=False):
                    result = agent_cli.verify_plan_with_timeout(plan, timeout=9)
            finally:
                agent_cli.live_call_with_timeout = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"][0]["readOffset"], 0)
        self.assertEqual(result["checks"][0]["actualHex"], "00 01 0A 04")

    def test_validation_record_requires_verified_write_and_restore_for_effective_confidence(self):
        self.assertTrue(agent_cli.validation_record_supports_effective_confidence({
            "confidenceRecommendation": "live-verified",
            "writeVerified": True,
            "restored": True,
            "restoreVerified": True,
        }))
        self.assertTrue(agent_cli.validation_record_supports_effective_confidence({
            "confidenceRecommendation": "live-verified",
            "writeVerified": True,
            "restored": False,
            "restoreVerified": None,
        }))
        self.assertFalse(agent_cli.validation_record_supports_effective_confidence({
            "confidenceRecommendation": "live-verified",
            "writeVerified": True,
            "restored": True,
            "restoreVerified": False,
        }))
        self.assertFalse(agent_cli.validation_record_supports_effective_confidence({
            "confidenceRecommendation": "live-verified",
            "writeVerified": False,
            "restored": True,
            "restoreVerified": True,
        }))

    def test_restore_point_captures_previous_bytes_for_writes(self):
        plan = agent_cli.patch_edit.PatchPlan(
            "restore-test",
            "Restore test",
            [agent_cli.live.PatchWrite("Write", [0x20, 0x00, 0x00, 0x00], [9])],
        )

        def fake_read(label, timeout, requests, reader=agent_cli.patch_edit.read_data_sets_batched, attempts=3):
            return {agent_cli.live.address_key(requests[0].address): [1, 2, 3]}

        original = agent_cli.read_patch_records_with_timeout
        agent_cli.read_patch_records_with_timeout = fake_read
        try:
            with tempfile.TemporaryDirectory() as directory:
                with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_RESTORE_DIR": directory}):
                    path = agent_cli.create_restore_point(plan, timeout=9)
                    latest = agent_cli.latest_restore_point_path()
                    self.assertTrue(path.is_file())
                    self.assertTrue(latest.is_file())
                    restore = agent_cli.load_json(path)
                    undo_plan = agent_cli.restore_plan_from_data(restore)
        finally:
            agent_cli.read_patch_records_with_timeout = original

        self.assertEqual(restore["plan"], "restore-test")
        self.assertEqual(restore["records"][0]["dataHex"], "01 02 03")
        self.assertEqual(undo_plan.id, "undo-last:restore-test")
        self.assertEqual(undo_plan.writes[0].address, [0x20, 0x00, 0x00, 0x00])
        self.assertEqual(undo_plan.writes[0].data, [1, 2, 3])

    def test_undo_last_uses_latest_restore_without_creating_another_restore_point(self):
        restore = {
            "format": "gt1000-agent-restore-v1",
            "createdAt": "2026-05-21T00:00:00-0400",
            "plan": "set:delay1:time",
            "records": [
                {
                    "label": "Delay Time",
                    "address": ["20", "00", "10", "00"],
                    "size": ["00", "00", "00", "02"],
                    "dataHex": "01 02",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_RESTORE_DIR": directory}):
                agent_cli.restore_point_dir().mkdir(parents=True, exist_ok=True)
                agent_cli.latest_restore_point_path().write_text(json.dumps(restore), encoding="utf-8")
                args = agent_cli.build_parser().parse_args(["patch", "undo-last", "--live", "--verify"])
                original_apply = agent_cli.apply_plan_cli
                agent_cli.apply_plan_cli = MagicMock(return_value={"plan": "undo-last:set:delay1:time", "writeCount": 1, "verified": True})
                try:
                    result = agent_cli.cmd_patch_undo_last(args)
                    plan = agent_cli.apply_plan_cli.call_args.args[0]
                    kwargs = agent_cli.apply_plan_cli.call_args.kwargs
                finally:
                    agent_cli.apply_plan_cli = original_apply

        self.assertEqual(result["restoredPlan"], "set:delay1:time")
        self.assertEqual(plan.id, "undo-last:set:delay1:time")
        self.assertEqual(plan.writes[0].data, [1, 2])
        self.assertFalse(kwargs["create_restore"])
        self.assertTrue(kwargs["verify"])

    def test_patch_record_timeout_helper_retries_failed_batch(self):
        requests = [agent_cli.live.PatchReadRequest("Read", [0x20, 0x00, 0x00, 0x00], [0, 0, 0, 1])]
        calls = 0

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise agent_cli.CLIError("transient")
            return {agent_cli.live.address_key(requests[0].address): [1]}

        live_call = MagicMock(side_effect=fake_live_call)
        sleep = MagicMock()
        original = agent_cli.live_call_with_timeout
        original_sleep = agent_cli.time.sleep
        agent_cli.live_call_with_timeout = live_call
        agent_cli.time.sleep = sleep
        try:
            result = agent_cli.read_patch_records_with_timeout("records", 9, requests)
        finally:
            agent_cli.time.sleep = original_sleep
            agent_cli.live_call_with_timeout = original

        self.assertEqual(result, {"20 00 00 00": [1]})
        self.assertEqual(live_call.call_count, 2)
        sleep.assert_any_call(0.5)

    def test_lenient_patch_read_retries_missing_records(self):
        requests = [
            agent_cli.live.PatchReadRequest("Read 0", [0x20, 0x00, 0x00, 0x00], [0, 0, 0, 1]),
            agent_cli.live.PatchReadRequest("Read 1", [0x20, 0x00, 0x01, 0x00], [0, 0, 0, 1]),
            agent_cli.live.PatchReadRequest("Read 2", [0x20, 0x00, 0x02, 0x00], [0, 0, 0, 1]),
        ]

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            if label == "records":
                return {agent_cli.live.address_key(requests[0].address): [0]}
            return {
                agent_cli.live.address_key(request.address): [request.address[2]]
                for request in requests
            }

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            result = agent_cli.read_patch_records_lenient_with_timeout("records", 9, requests)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertEqual(result, {
            "20 00 00 00": [0],
            "20 00 01 00": [1],
            "20 00 02 00": [2],
        })
        self.assertEqual(live_call.call_count, 2)
        self.assertEqual(live_call.call_args_list[1].args[0], "records missing records retry")
        self.assertEqual(live_call.call_args_list[1].kwargs["timeout"], 9)
        self.assertEqual([request.address for request in live_call.call_args_list[1].kwargs["requests"]], [
            [0x20, 0x00, 0x01, 0x00],
            [0x20, 0x00, 0x02, 0x00],
        ])

    def test_lenient_patch_read_chunks_and_stops_after_empty_chunk(self):
        requests = [
            agent_cli.live.PatchReadRequest(f"Read {index}", [0x20, 0x00, index, 0x00], [0, 0, 0, 1])
            for index in range(5)
        ]

        def fake_live_call(label, process_timeout, func, *, timeout, requests):
            if requests[0].address[2] == 0:
                return {
                    agent_cli.live.address_key(requests[0].address): [0],
                    agent_cli.live.address_key(requests[1].address): [1],
                }
            return {}

        live_call = MagicMock(side_effect=fake_live_call)
        original = agent_cli.live_call_with_timeout
        agent_cli.live_call_with_timeout = live_call
        try:
            with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_LENIENT_READ_BATCH_SIZE": "2"}):
                result = agent_cli.read_patch_records_lenient_chunks("records", 2, requests)
        finally:
            agent_cli.live_call_with_timeout = original

        self.assertEqual(result, {
            "20 00 00 00": [0],
            "20 00 01 00": [1],
        })
        self.assertEqual(live_call.call_count, 2)
        self.assertEqual([request.address[2] for request in live_call.call_args_list[0].kwargs["requests"]], [0, 1])
        self.assertEqual([request.address[2] for request in live_call.call_args_list[1].kwargs["requests"]], [2, 3])

    def test_lenient_batch_size_defaults_and_ignores_bad_env(self):
        with unittest.mock.patch.dict(agent_cli.os.environ, {}, clear=False):
            agent_cli.os.environ.pop("GT1000_LENIENT_READ_BATCH_SIZE", None)
            self.assertEqual(agent_cli.lenient_read_batch_size(), 8)
        with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_LENIENT_READ_BATCH_SIZE": "3"}):
            self.assertEqual(agent_cli.lenient_read_batch_size(), 3)
        with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_LENIENT_READ_BATCH_SIZE": "bad"}):
            self.assertEqual(agent_cli.lenient_read_batch_size(), 8)
        with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_LENIENT_READ_BATCH_SIZE": "0"}):
            self.assertEqual(agent_cli.lenient_read_batch_size(), 1)

    def test_required_patch_read_batches_required_records_and_retries_missing(self):
        requests = [
            agent_cli.live.PatchReadRequest("Patch Common", [0x20, 0x00, 0x00, 0x00], [0, 0, 0, 1]),
            agent_cli.live.PatchReadRequest("Patch Effect", [0x20, 0x00, 0x10, 0x00], [0, 0, 0, 1]),
        ]
        calls = []

        def fake_strict_read(label, timeout, requests, reader=agent_cli.patch_edit.read_data_sets_batched, attempts=3):
            self.assertIs(reader, agent_cli.patch_edit.read_data_sets_lenient_session)
            self.assertEqual(attempts, 1)
            calls.append([request.label for request in requests])
            if len(calls) == 1:
                request = requests[1]
                return {agent_cli.live.address_key(request.address): [len(calls)]}
            request = requests[0]
            return {agent_cli.live.address_key(request.address): [len(calls)]}

        original_strict = agent_cli.read_patch_records_with_timeout
        original_lenient = agent_cli.read_patch_records_lenient_with_timeout
        original_sleep = agent_cli.time.sleep
        agent_cli.read_patch_records_with_timeout = fake_strict_read
        agent_cli.read_patch_records_lenient_with_timeout = MagicMock(return_value={})
        agent_cli.time.sleep = MagicMock()
        try:
            with unittest.mock.patch.dict(agent_cli.os.environ, {"GT1000_REQUIRED_RECORD_ATTEMPTS": "2"}):
                result = agent_cli.read_required_patch_records_with_timeout("records", 9, requests)
        finally:
            agent_cli.time.sleep = original_sleep
            agent_cli.read_patch_records_lenient_with_timeout = original_lenient
            agent_cli.read_patch_records_with_timeout = original_strict

        self.assertEqual(calls, [["Patch Common", "Patch Effect"], ["Patch Common"]])
        self.assertEqual(sorted(result), ["20 00 00 00", "20 00 10 00"])

    def test_clone_read_reads_required_core_records_before_optional_core(self):
        core_requests = agent_cli.patch_edit.clone_core_read_requests("U10-1")
        patch_effect = next(request for request in core_requests if request.label == "Patch Effect")
        patch_common = next(request for request in core_requests if request.label == "Patch Common")
        patch_effect_key = agent_cli.live.address_key(patch_effect.address)

        required_calls = []

        def fake_required_read(label, timeout, requests):
            required_calls.append((label, timeout, requests))
            return {
                agent_cli.live.address_key(request.address): [0] * agent_cli.live.seven_bit_address_value(request.size)
                for request in requests
            }

        def fake_lenient_read(label, timeout, requests):
            if label.endswith("active FX records"):
                return {}
            return {
                agent_cli.live.address_key(request.address): [0] * agent_cli.live.seven_bit_address_value(request.size)
                for request in requests
            }

        original_required = agent_cli.read_required_patch_records_with_timeout
        original_lenient = agent_cli.read_patch_records_lenient_with_timeout
        agent_cli.read_required_patch_records_with_timeout = fake_required_read
        agent_cli.read_patch_records_lenient_with_timeout = fake_lenient_read
        try:
            result = agent_cli.read_clone_records_with_timeout("patch export U10-1 --live", 20, "U10-1")
        finally:
            agent_cli.read_patch_records_lenient_with_timeout = original_lenient
            agent_cli.read_required_patch_records_with_timeout = original_required

        self.assertIn(agent_cli.live.address_key(patch_common.address), result)
        self.assertIn(patch_effect_key, result)
        self.assertEqual(len(required_calls), 1)
        label, timeout, requests = required_calls[0]
        self.assertEqual(label, "patch export U10-1 --live required record")
        self.assertEqual(timeout, 20)
        self.assertEqual(requests, [patch_common, patch_effect])

    def test_missing_required_records_error_checks_connectivity_before_restart_guidance(self):
        original = agent_cli.probe_gt1000_connectivity
        try:
            agent_cli.probe_gt1000_connectivity = MagicMock(return_value=(True, "ok"))
            retryable = agent_cli.missing_required_records_error("patch export U10-1 --live", ["Patch Effect"], 20)
            self.assertIn("recoverable live-read timeout", str(retryable))
            self.assertNotIn("power-cycle", str(retryable))

            agent_cli.probe_gt1000_connectivity = MagicMock(return_value=(False, "endpoint check failed"))
            fatal = agent_cli.missing_required_records_error("patch export U10-1 --live", ["Patch Effect"], 20)
            self.assertIn("connectivity probe failed", str(fatal))
            self.assertIn("power-cycle", str(fatal))
            self.assertIn("restart macOS only if", str(fatal))
        finally:
            agent_cli.probe_gt1000_connectivity = original

    def test_offline_overview(self):
        snapshot = agent_cli.load_json(FIXTURE)

        overview = agent_cli.overview_from_full(snapshot)

        self.assertEqual(overview["patchName"], "TEST PATCH")
        self.assertEqual(overview["signalChainElementCount"], 4)
        self.assertEqual(overview["detailBlockCount"], 3)

    def test_offline_chain_links_detail_blocks(self):
        snapshot = agent_cli.load_json(FIXTURE)

        chain = agent_cli.chain_from_full(snapshot)

        self.assertEqual(chain["signalChainSummary"], "AIRD PREAMP 1 (DIAMOND AMP) -> DELAY 1 -> CHORUS -> MAIN OUT L")
        self.assertEqual(chain["descriptionSignalChainSummary"], "AIRD PREAMP 1 (DIAMOND AMP) -> CHORUS -> MAIN OUT L")
        self.assertEqual(chain["elements"][0]["detailBlockID"], "preamp1")
        self.assertEqual(chain["elements"][1]["detailBlockID"], "delay1")
        self.assertFalse(chain["elements"][1]["includeInDescription"])
        self.assertTrue(chain["elements"][2]["hasControlAssignment"])
        self.assertTrue(chain["elements"][2]["includeInDescription"])
        self.assertIsNone(chain["elements"][3]["detailBlockID"])

    def test_offline_block_by_position(self):
        snapshot = agent_cli.load_json(FIXTURE)

        block = agent_cli.block_for_position(snapshot, 1)
        detail = agent_cli.block_detail_from_full(snapshot, block)

        self.assertEqual(detail["chainPositions"], [1])
        self.assertEqual(detail["block"]["typeName"], "DIAMOND AMP")

    def test_block_requires_one_selector(self):
        args = agent_cli.build_parser().parse_args(["patch", "block", "--file", str(FIXTURE)])

        with self.assertRaises(agent_cli.CLIError):
            agent_cli.cmd_patch_block(args)

    def test_inspect_chain_view(self):
        args = agent_cli.build_parser().parse_args(["patch", "inspect", str(FIXTURE), "--view", "chain"])

        chain = agent_cli.cmd_patch_inspect(args)

        self.assertEqual(chain["elements"][0]["detailBlockID"], "preamp1")

    def test_patch_schema_exposes_named_and_raw_editable_fields(self):
        args = agent_cli.build_parser().parse_args(["patch", "schema", "fx1"])

        schema = agent_cli.cmd_patch_schema(args)

        self.assertEqual(schema["id"], "fx1")
        self.assertEqual(schema["type"], "effect")
        self.assertEqual(schema["temporaryAddress"], ["10", "00", "23", "00"])
        self.assertGreater(schema["editableSize"], schema["summarySize"])
        self.assertEqual(schema["rawEditable"]["offsetRange"], [0, schema["editableSize"] - 1])

        raw_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "delay1", "--raw"]))
        self.assertEqual(raw_schema["rawEditable"]["parameters"][0]["offset"], 0)
        self.assertEqual(raw_schema["rawEditable"]["parameters"][0]["namedParameterId"], "sw")
        self.assertEqual(len(raw_schema["rawEditable"]["parameters"]), raw_schema["editableSize"])
        delay_parameters = {parameter["id"]: parameter for parameter in raw_schema["namedParameters"]}
        self.assertEqual(delay_parameters["sw"]["minimum"], 0)
        self.assertEqual(delay_parameters["sw"]["maximum"], 1)
        self.assertEqual(delay_parameters["sw"]["values"], ["off", "on"])
        self.assertEqual(delay_parameters["feedback"]["maximum"], 127)
        self.assertEqual(delay_parameters["time"]["maximum"], 65535)

        fx_algorithm_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "fx1Chorus"]))
        fx_algorithm_parameters = {parameter["id"]: parameter for parameter in fx_algorithm_schema["namedParameters"]}
        self.assertEqual(fx_algorithm_schema["temporaryAddress"], ["10", "00", "27", "00"])
        self.assertEqual(fx_algorithm_parameters["rate2"]["offset"], 22)
        self.assertEqual(fx_algorithm_parameters["highCut2"]["offset"], 28)

        pitch_shift_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "fx2PitchShift"]))
        pitch_shift_parameters = {parameter["id"]: parameter for parameter in pitch_shift_schema["namedParameters"]}
        self.assertEqual(pitch_shift_schema["temporaryAddress"], ["10", "00", "4E", "00"])
        self.assertEqual(pitch_shift_parameters["ps1PreDelay"]["kind"], "nibbles")
        self.assertEqual(pitch_shift_parameters["ps2Level"]["offset"], 18)

        fx4_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "fx4"]))
        self.assertEqual(fx4_schema["temporaryAddress"], ["10", "02", "01", "00"])
        self.assertEqual(fx4_schema["namedParameters"][1]["maximum"], 25)

        fx4_chorus_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "fx4Chorus"]))
        self.assertEqual(fx4_chorus_schema["temporaryAddress"], ["10", "02", "05", "00"])
        self.assertIn("effectLevel2", [parameter["id"] for parameter in fx4_chorus_schema["namedParameters"]])

        eq_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "eq1", "--raw"]))
        eq_parameters = {parameter["id"]: parameter for parameter in eq_schema["namedParameters"]}
        self.assertEqual(eq_parameters["lowMidGain"]["offset"], 7)
        self.assertEqual(eq_parameters["highCut"]["offset"], 12)
        self.assertEqual(eq_parameters["geq16kHz"]["offset"], 23)
        self.assertEqual(eq_parameters["geqLevel"]["offset"], 13)
        self.assertEqual(eq_parameters["type"]["values"], ["PARAMETRIC", "GRAPHIC"])
        self.assertEqual(eq_parameters["type"]["maximum"], 1)
        self.assertEqual(eq_schema["rawEditable"]["parameters"][13]["namedParameterId"], "level")

        master_delay_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "masterDelay"]))
        master_delay_parameters = {parameter["id"]: parameter for parameter in master_delay_schema["namedParameters"]}
        self.assertEqual(master_delay_parameters["duckSens"]["offset"], 11)
        self.assertEqual(master_delay_parameters["d2EffectLevel"]["offset"], 34)
        self.assertEqual(master_delay_parameters["tapTime"]["offset"], 43)

        reverb_schema = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "reverb"]))
        reverb_parameters = {parameter["id"]: parameter for parameter in reverb_schema["namedParameters"]}
        self.assertEqual(reverb_parameters["directLevel"]["offset"], 2)
        self.assertEqual(reverb_parameters["preDelay"]["offset"], 14)
        self.assertEqual(reverb_parameters["highCut2"]["offset"], 39)

        resident = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "sendReturn1"]))
        self.assertEqual(resident["type"], "resident")
        self.assertEqual(resident["temporaryAddress"], ["10", "00", "10", "35"])
        self.assertIn("sendLevel", [parameter["id"] for parameter in resident["namedParameters"]])

        master = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "master"]))
        self.assertEqual(master["id"], "master")
        self.assertEqual(master["command"], "patch master-set <field> <value>")
        master_parameters = {parameter["id"]: parameter for parameter in master["namedParameters"]}
        self.assertEqual(master_parameters["level"]["offset"], 0x5F)
        self.assertEqual(master_parameters["level"]["kind"], "nibbles2")
        self.assertEqual(master_parameters["level"]["byteCount"], 2)
        self.assertEqual(master_parameters["level"]["encodingConfidence"]["confidence"], "live-verified")
        self.assertIn("input-sensitivity", master_parameters)

        controls = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "controls"]))
        self.assertEqual(controls["id"], "controls")
        self.assertEqual(controls["encodingConfidence"]["confidence"], "legacy")
        self.assertIn("ctl1", controls["controls"])
        self.assertIn("dist1", controls["switchFunctions"])

        assign = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "assign"]))
        self.assertEqual(assign["id"], "assign")
        self.assertEqual(assign["encodingConfidence"]["confidence"], "legacy")
        self.assertIn("general", assign["commands"])
        self.assertIn("tuner", assign["targetAliases"])

        led = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "led"]))
        self.assertEqual(led["id"], "led")
        self.assertEqual(led["encodingConfidence"]["confidence"], "legacy")
        self.assertIn("ctl1", led["controls"])
        self.assertIn("auto-cyan", led["onColors"])

    def test_encoding_status_reports_confidence_inventory(self):
        args = agent_cli.build_parser().parse_args(["patch", "encoding-status", "master"])

        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(directory) / "empty.jsonl")}, clear=False):
                status = agent_cli.cmd_patch_encoding_status(args)

        self.assertEqual(status["id"], "encodingStatus")
        self.assertEqual(status["filter"], "all")
        self.assertIn("live-verified", status["confidenceLevels"])
        self.assertIn("official", status["semanticConfidenceLevels"])
        self.assertGreater(status["trustedCount"], 0)
        self.assertEqual(status["untrustedCount"], 0)
        self.assertEqual(status["entryCount"], status["trustedCount"] + status["untrustedCount"])
        self.assertGreater(status["effectiveConfidenceCounts"]["live-verified"], 0)
        self.assertGreater(status["semanticConfidenceCounts"]["official"], 0)
        entries = {entry["id"]: entry for entry in status["entries"]}
        self.assertEqual(entries["patch.master.level"]["confidence"], "live-verified")
        self.assertEqual(entries["patch.master.level"]["effectiveConfidence"], "live-verified")
        self.assertEqual(entries["patch.master.level"]["semanticConfidence"], "official")
        self.assertTrue(entries["patch.master.level"]["trustedEncoding"])
        self.assertEqual(entries["patch.master.patch-level"]["confidence"], "live-verified")
        self.assertEqual(entries["patch.master.patch-level"]["canonicalId"], "patch.master.level")
        self.assertTrue(entries["patch.master.patch-level"]["trustedEncoding"])
        self.assertEqual(entries["patch.master.key"]["confidence"], "live-verified")
        self.assertEqual(entries["patch.master.key"]["effectiveConfidence"], "live-verified")
        self.assertTrue(entries["patch.master.key"]["trustedEncoding"])
        self.assertNotIn("patch.block.masterDelay.time", entries)

        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(directory) / "empty.jsonl")}, clear=False):
                control_status = agent_cli.cmd_patch_encoding_status(agent_cli.build_parser().parse_args(["patch", "encoding-status", "patch.controls"]))
        self.assertEqual(control_status["entries"][0]["id"], "patch.controls")
        self.assertEqual(control_status["entries"][0]["confidence"], "legacy")
        self.assertEqual(control_status["trustedCount"], 0)
        self.assertEqual(control_status["untrustedCount"], 1)

    def test_encoding_status_filters_trusted_and_untrusted_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(directory) / "empty.jsonl")}, clear=False):
                untrusted = agent_cli.cmd_patch_encoding_status(
                    agent_cli.build_parser().parse_args(["patch", "encoding-status", "patch.block.delay3", "--untrusted"])
                )
                trusted = agent_cli.cmd_patch_encoding_status(
                    agent_cli.build_parser().parse_args(["patch", "encoding-status", "master", "--trusted"])
                )

        self.assertEqual(untrusted["filter"], "untrusted")
        self.assertEqual(untrusted["trustedCount"], 0)
        self.assertEqual(untrusted["entryCount"], untrusted["untrustedCount"])
        self.assertTrue(all(not entry["trustedEncoding"] for entry in untrusted["entries"]))
        self.assertIn("validationTemplate", {key for entry in untrusted["entries"] for key in entry})
        self.assertIn("block.delay3.sw=on", untrusted["validationCases"])
        self.assertIn("block.delay3.time=1", untrusted["validationCases"])
        self.assertIn("patch validate-encoding-batch", untrusted["batchValidationCommand"])
        self.assertIn("block.delay3.sw=on", untrusted["batchValidationCommand"])
        self.assertEqual(trusted["filter"], "trusted")
        self.assertEqual(trusted["untrustedCount"], 0)
        self.assertEqual(trusted["entryCount"], trusted["trustedCount"])
        self.assertTrue(all(entry["trustedEncoding"] for entry in trusted["entries"]))
        self.assertNotIn("validationCases", trusted)

    def test_encoding_validation_case_generation_for_block_parameters(self):
        self.assertEqual(
            agent_cli.encoding_validation_case_for_field_id("patch.block.delay3.sw"),
            "block.delay3.sw=on",
        )
        self.assertEqual(
            agent_cli.encoding_validation_command_for_case("block.delay3.sw=on"),
            "patch validate-encoding block delay3.sw on --user-slot U10-1 --live --timeout 20",
        )
        self.assertEqual(
            agent_cli.encoding_validation_case_for_field_id("patch.block.delay3.time"),
            "block.delay3.time=1",
        )

    def test_encoding_validation_scope_generates_cases_from_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(directory) / "empty.jsonl")}, clear=False):
                cases = agent_cli.encoding_validation_cases_for_scope("master")
                trusted_cases = agent_cli.encoding_validation_cases_for_scope("master", include_trusted=True)

        self.assertEqual(cases, [])
        self.assertIn("master.key=1", trusted_cases)
        self.assertIn("master.amp-ctl1=on", trusted_cases)
        self.assertNotIn("master.amp-control1=on", trusted_cases)
        self.assertNotIn("master.level=1", cases)
        self.assertNotIn("master.patch-level=1", trusted_cases)

    def test_validate_encoding_scope_dry_run_lists_generated_cases(self):
        args = agent_cli.build_parser().parse_args(["patch", "validate-encoding-scope", "patch.block.delay3", "--limit", "2", "--dry-run"])

        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(directory) / "empty.jsonl")}, clear=False):
                result = agent_cli.cmd_patch_validate_encoding_scope(args)

        self.assertEqual(result["id"], "encodingValidationScope")
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["caseCount"], 2)
        self.assertEqual(len(result["cases"]), 2)
        self.assertIn("patch validate-encoding-scope patch.block.delay3", result["batchValidationCommand"])

    def test_validate_encoding_scope_filters_by_parameter_and_kind(self):
        args = agent_cli.build_parser().parse_args([
            "patch",
            "validate-encoding-scope",
            "patch.block",
            "--parameter",
            "sw",
            "--kind",
            "bool",
            "--current-value",
            "--limit",
            "3",
            "--dry-run",
        ])

        with tempfile.TemporaryDirectory() as directory:
            with unittest.mock.patch.dict(agent_cli.os.environ, {agent_cli.ENCODING_VALIDATION_LOG_ENV: str(Path(directory) / "empty.jsonl")}, clear=False):
                result = agent_cli.cmd_patch_validate_encoding_scope(args)

        self.assertEqual(result["parameters"], ["sw"])
        self.assertEqual(result["kinds"], ["bool"])
        self.assertTrue(result["currentValue"])
        self.assertEqual(result["caseCount"], 3)
        self.assertTrue(all(case.endswith(".sw=on") for case in result["cases"]))
        self.assertIn("--parameter sw", result["batchValidationCommand"])
        self.assertIn("--kind bool", result["batchValidationCommand"])
        self.assertIn("--current-value", result["batchValidationCommand"])

    def test_all_patch_block_definitions_have_schema(self):
        blocks = (
            list(agent_cli.live.SUMMARY_BLOCKS)
            + list(agent_cli.live.FX_ALGORITHM_BLOCKS)
            + list(agent_cli.live.RESIDENT_BLOCKS)
        )

        self.assertGreater(len(blocks), 100)
        for block in blocks:
            with self.subTest(block=block.id):
                schema = agent_cli.block_schema(block.id)
                self.assertEqual(schema["id"], block.id)
                self.assertGreater(schema["editableSize"], 0)

    def test_patch_command_surface_is_documented(self):
        parser = agent_cli.build_parser()
        patch_parser = next(
            action.choices["patch"]
            for action in parser._actions
            if getattr(action, "dest", None) == "command"
        )
        patch_commands = next(
            sorted(action.choices)
            for action in patch_parser._actions
            if getattr(action, "dest", None) == "patch_command"
        )
        cli_usage = (Path(__file__).resolve().parents[1] / "skills/gt1000/references/midi-reference/cli-usage.md").read_text()

        for command in patch_commands:
            with self.subTest(command=command):
                self.assertIn(f"patch {command}", cli_usage)

    def test_cli_command_paths_have_test_coverage(self):
        def parser_command_paths(prefix, parser):
            paths = []
            for action in parser._actions:
                choices = getattr(action, "choices", None)
                if not hasattr(choices, "items"):
                    continue
                for key, child in choices.items():
                    if not isinstance(key, str) or not hasattr(child, "_actions"):
                        continue
                    path = prefix + (key,)
                    paths.append(path)
                    paths.extend(parser_command_paths(path, child))
            return paths

        command_paths = parser_command_paths((), agent_cli.build_parser())
        test_sources = "\n".join(
            path.read_text()
            for path in Path(__file__).resolve().parent.glob("test_*.py")
            if path.name != "test_live_skill.py"
        )

        self.assertGreater(len(command_paths), 50)
        for command_path in command_paths:
            with self.subTest(command=" ".join(command_path)):
                parser_call = '"' + '", "'.join(command_path) + '"'
                self.assertIn(
                    parser_call,
                    test_sources,
                    f"{' '.join(command_path)} needs unit/parser coverage in tests",
                )

    def test_p1_write_commands_have_live_verification_paths(self):
        p1_write_commands = {
            "apply",
            "assign-set",
            "batch-copy",
            "batch-initialize",
            "clear",
            "clone",
            "control-preference-set",
            "control-set",
            "copy",
            "exchange",
            "export",
            "import",
            "intent",
            "initialize",
            "insert",
            "led-set",
            "liveset-copy",
            "liveset-list",
            "liveset-move",
            "liveset-remove",
            "liveset-rename",
            "master-set",
            "normalize-levels",
            "raw-set",
            "rename",
            "restore-preset",
            "set",
            "system-control-set",
            "tsl-export",
            "tsl-import",
            "tsl-list",
            "undo-last",
            "validate-encoding",
            "validate-encoding-batch",
            "validate-encoding-scope",
        }
        live_paths = live_verified_command_paths()

        for command in p1_write_commands:
            with self.subTest(command=command):
                self.assertIn(("patch", command), live_paths)

    def test_live_cli_commands_have_live_verification_paths(self):
        parser = agent_cli.build_parser()
        command_parsers = next(
            action.choices
            for action in parser._actions
            if getattr(action, "dest", None) == "command"
        )
        live_paths = live_verified_command_paths()
        parser_paths = {("doctor",), ("ports",)}

        self.assertIn(("ports",), live_paths)
        self.assertIn(("doctor",), live_paths)
        for group in ["patch", "midi", "system"]:
            subparser = command_parsers[group]
            subcommands = next(
                sorted(key for key in action.choices if isinstance(key, str))
                for action in subparser._actions
                if hasattr(getattr(action, "choices", None), "items")
            )
            for command in subcommands:
                parser_paths.add((group, command))
                with self.subTest(command=f"{group} {command}"):
                    self.assertIn((group, command), live_paths, f"{group} {command} needs a live test verification path")

        self.assertEqual(live_paths - parser_paths, set())

    def test_consecutive_user_slots(self):
        self.assertEqual(agent_cli.consecutive_user_slots("U10-4", 3), ["U10-4", "U10-5", "U11-1"])
        with self.assertRaises(ValueError):
            agent_cli.consecutive_user_slots("U50-5", 2)

    def test_new_p1_commands_parse(self):
        parser = agent_cli.build_parser()

        system_inout = parser.parse_args(["system", "inout", "--live"])
        self.assertEqual(system_inout.command, "system")
        self.assertEqual(system_inout.system_command, "inout")

        overview = parser.parse_args(["patch", "overview", "--live"])
        self.assertEqual(overview.patch_command, "overview")

        controls = parser.parse_args(["patch", "controls", "--live"])
        self.assertEqual(controls.patch_command, "controls")

        summary = parser.parse_args(["patch", "summary", "--live"])
        self.assertEqual(summary.patch_command, "summary")

        musician_summary = parser.parse_args(["patch", "musician-summary", "--live"])
        self.assertEqual(musician_summary.patch_command, "musician-summary")

        level_audit = parser.parse_args(["patch", "level-audit", "U10-1", "U10-2", "--target", "90", "--live"])
        self.assertEqual(level_audit.patch_command, "level-audit")
        self.assertEqual(level_audit.target, 90)

        normalize_levels = parser.parse_args(["patch", "normalize-levels", "U10-1", "U10-2", "--target", "90", "--live", "--verify"])
        self.assertEqual(normalize_levels.patch_command, "normalize-levels")
        self.assertEqual(normalize_levels.target, 90)

        encoding_status = parser.parse_args(["patch", "encoding-status", "master"])
        self.assertEqual(encoding_status.patch_command, "encoding-status")
        self.assertEqual(encoding_status.scope, "master")

        encoding_status_untrusted = parser.parse_args(["patch", "encoding-status", "master", "--untrusted"])
        self.assertEqual(encoding_status_untrusted.patch_command, "encoding-status")
        self.assertTrue(encoding_status_untrusted.untrusted)

        validate_encoding = parser.parse_args(["patch", "validate-encoding", "master", "level", "90", "--live"])
        self.assertEqual(validate_encoding.patch_command, "validate-encoding")
        self.assertEqual(validate_encoding.area, "master")
        self.assertEqual(validate_encoding.field, "level")
        self.assertEqual(validate_encoding.value, "90")

        validate_block_encoding = parser.parse_args(["patch", "validate-encoding", "block", "delay1.sw", "on", "--live"])
        self.assertEqual(validate_block_encoding.patch_command, "validate-encoding")
        self.assertEqual(validate_block_encoding.area, "block")
        self.assertEqual(validate_block_encoding.field, "delay1.sw")
        self.assertEqual(validate_block_encoding.value, "on")

        validate_encoding_batch = parser.parse_args(["patch", "validate-encoding-batch", "master.level=90", "block.delay1.sw=on", "--live"])
        self.assertEqual(validate_encoding_batch.patch_command, "validate-encoding-batch")
        self.assertEqual(validate_encoding_batch.cases, ["master.level=90", "block.delay1.sw=on"])

        validate_encoding_scope = parser.parse_args(["patch", "validate-encoding-scope", "master", "--live", "--limit", "2", "--parameter", "sw", "--kind", "bool", "--current-value"])
        self.assertEqual(validate_encoding_scope.patch_command, "validate-encoding-scope")
        self.assertEqual(validate_encoding_scope.scope, "master")
        self.assertEqual(validate_encoding_scope.limit, 2)
        self.assertEqual(validate_encoding_scope.parameter, ["sw"])
        self.assertEqual(validate_encoding_scope.kind, ["bool"])
        self.assertTrue(validate_encoding_scope.current_value)

        slot_default = parser.parse_args(["patch", "slot", "U10-1", "--live"])
        self.assertEqual(slot_default.view, "overview")

        bank_default = parser.parse_args(["patch", "bank", "U10", "--live"])
        self.assertEqual(bank_default.view, "overview")

        intent = parser.parse_args(["patch", "intent", "solo-boost", "--control", "ctl4", "--amount", "20", "--live", "--verify"])
        self.assertEqual(intent.patch_command, "intent")
        self.assertEqual(intent.intent, "solo-boost")
        self.assertEqual(intent.amount, 20)

        dump = parser.parse_args(["patch", "dump", "--live"])
        self.assertEqual(dump.patch_command, "dump")

        plan = parser.parse_args(["patch", "plan", "default"])
        self.assertEqual(plan.patch_command, "plan")
        self.assertEqual(plan.plan_id, "default")

        apply = parser.parse_args(["patch", "apply", "default", "--live", "--verify"])
        self.assertEqual(apply.patch_command, "apply")
        self.assertEqual(apply.plan_id, "default")

        set_param = parser.parse_args(["patch", "set", "delay1", "time", "380", "--live", "--verify"])
        self.assertEqual(set_param.patch_command, "set")
        self.assertEqual(set_param.block_id, "delay1")
        self.assertEqual(set_param.parameter_id, "time")

        raw = parser.parse_args(["patch", "raw-set", "fx1", "12", "64", "--live", "--verify"])
        self.assertEqual(raw.patch_command, "raw-set")
        self.assertEqual(raw.offset, 12)
        self.assertEqual(raw.width, "byte")

        master = parser.parse_args(["patch", "master-set", "level", "95", "--live", "--verify"])
        self.assertEqual(master.patch_command, "master-set")
        self.assertEqual(master.field, "level")

        control = parser.parse_args(["patch", "control-set", "ctl1", "dist1", "--mode", "toggle", "--live"])
        self.assertEqual(control.patch_command, "control-set")
        self.assertEqual(control.control, "ctl1")

        system_control = parser.parse_args(["patch", "system-control-set", "ctl1", "dist1", "--mode", "toggle", "--live"])
        self.assertEqual(system_control.patch_command, "system-control-set")
        self.assertEqual(system_control.control, "ctl1")

        preference = parser.parse_args(["patch", "control-preference-set", "ctl1", "patch", "--live"])
        self.assertEqual(preference.patch_command, "control-preference-set")
        self.assertEqual(preference.preference, "patch")

        led = parser.parse_args(["patch", "led-set", "ctl1", "on", "auto-cyan", "--live"])
        self.assertEqual(led.patch_command, "led-set")
        self.assertEqual(led.color, "auto-cyan")

        assign = parser.parse_args([
            "patch", "assign-set", "2",
            "--target", "tuner",
            "--min", "0",
            "--max", "1",
            "--source", "internal-pedal",
            "--mode", "toggle",
            "--live",
        ])
        self.assertEqual(assign.patch_command, "assign-set")
        self.assertEqual(assign.target, "tuner")

        self.assertEqual(agent_cli.parse_assign_target_reference("delay1.sw"), 158)
        self.assertEqual(agent_cli.parse_assign_target_reference("eq1.lowMidGain"), 68)
        self.assertEqual(agent_cli.parse_assign_target_reference("eq1.level"), 72)
        self.assertEqual(agent_cli.parse_assign_target_reference("eq1.geq31.5Hz"), 75)
        self.assertEqual(agent_cli.parse_assign_target_reference("eq1.geqLevel"), 85)
        self.assertEqual(agent_cli.parse_assign_target_reference("masterDelay.directLevel"), 188)
        self.assertEqual(agent_cli.parse_assign_target_reference("masterDelay.duckSens"), 191)
        self.assertEqual(agent_cli.parse_assign_target_reference("fx1Chorus.effectLevel2"), 278)
        self.assertEqual(agent_cli.parse_assign_target_reference("fx2PitchShift.ps1PreDelay"), 597)
        self.assertEqual(agent_cli.parse_assign_target_reference("fx3Vibrato.directMix"), 882)
        self.assertEqual(agent_cli.parse_assign_target_reference("fx4.sw"), 1175)
        self.assertEqual(agent_cli.parse_assign_target_reference("fx4Chorus.effectLevel2"), 1215)
        self.assertEqual(agent_cli.parse_assign_target_reference("divider1.channelSelect"), 932)
        self.assertEqual(agent_cli.parse_assign_target_reference("tuner"), 987)
        self.assertEqual(agent_cli.parse_assign_source_reference("ctl1"), 8)
        self.assertEqual(agent_cli.parse_assign_source_reference("exp1"), 16)
        self.assertEqual(agent_cli.parse_assign_source_reference("cc80"), 69)

        copy = parser.parse_args(["patch", "copy", "U10-1", "U10-2", "--live"])
        self.assertEqual(copy.patch_command, "copy")
        self.assertEqual(copy.source_slot, "U10-1")

        preset = parser.parse_args(["patch", "preset", "P01-1", "--live", "--view", "overview"])
        self.assertEqual(preset.patch_command, "preset")
        self.assertEqual(preset.slot, "P01-1")

        restore_preset = parser.parse_args(["patch", "restore-preset", "P01-1", "U10-1", "--live", "--verify"])
        self.assertEqual(restore_preset.patch_command, "restore-preset")
        self.assertEqual(restore_preset.preset_slot, "P01-1")
        self.assertEqual(restore_preset.destination_slot, "U10-1")

        batch_copy = parser.parse_args(["patch", "batch-copy", "U10-1", "U10-2", "--destination-start", "U11-1", "--live"])
        self.assertEqual(batch_copy.patch_command, "batch-copy")
        self.assertEqual(batch_copy.source_slots, ["U10-1", "U10-2"])

        export = parser.parse_args(["patch", "export", "U10-1", "U10-2", "--output", "patches.json", "--live"])
        self.assertEqual(export.patch_command, "export")
        self.assertEqual(export.slots, ["U10-1", "U10-2"])

        import_liveset = parser.parse_args(["patch", "import", "patches.json", "--destination-start", "U11-1", "--live"])
        self.assertEqual(import_liveset.patch_command, "import")
        self.assertEqual(import_liveset.destination_start, "U11-1")

        tsl_export = parser.parse_args(["patch", "tsl-export", "patches.json", "--output", "patches.tsl", "--name", "My Liveset"])
        self.assertEqual(tsl_export.patch_command, "tsl-export")
        self.assertEqual(tsl_export.file, Path("patches.json"))
        self.assertEqual(tsl_export.output, Path("patches.tsl"))
        self.assertEqual(tsl_export.name, "My Liveset")

        tsl_list = parser.parse_args(["patch", "tsl-list", "patches.tsl"])
        self.assertEqual(tsl_list.patch_command, "tsl-list")
        self.assertEqual(tsl_list.file, Path("patches.tsl"))

        tsl_import = parser.parse_args(["patch", "tsl-import", "patches.tsl", "--destination-start", "U11-1", "--live"])
        self.assertEqual(tsl_import.patch_command, "tsl-import")
        self.assertEqual(tsl_import.destination_start, "U11-1")

        liveset_list = parser.parse_args(["patch", "liveset-list", "patches.json"])
        self.assertEqual(liveset_list.patch_command, "liveset-list")

        liveset_move = parser.parse_args(["patch", "liveset-move", "patches.json", "2", "1", "--output", "moved.json"])
        self.assertEqual(liveset_move.patch_command, "liveset-move")
        self.assertEqual(liveset_move.from_index, 2)
        self.assertEqual(liveset_move.to_index, 1)

        liveset_copy = parser.parse_args(["patch", "liveset-copy", "patches.json", "1", "2", "--output", "copied.json"])
        self.assertEqual(liveset_copy.patch_command, "liveset-copy")
        self.assertEqual(liveset_copy.from_index, 1)
        self.assertEqual(liveset_copy.to_index, 2)

        liveset_rename = parser.parse_args(["patch", "liveset-rename", "patches.json", "1", "NEW NAME", "--output", "renamed.json"])
        self.assertEqual(liveset_rename.patch_command, "liveset-rename")
        self.assertEqual(liveset_rename.index, 1)
        self.assertEqual(liveset_rename.name, "NEW NAME")

        liveset_remove = parser.parse_args(["patch", "liveset-remove", "patches.json", "1", "--output", "removed.json"])
        self.assertEqual(liveset_remove.patch_command, "liveset-remove")
        self.assertEqual(liveset_remove.index, 1)

        exchange = parser.parse_args(["patch", "exchange", "U10-1", "U10-2", "--live"])
        self.assertEqual(exchange.patch_command, "exchange")

        insert = parser.parse_args(["patch", "insert", "U10-1", "U11-1", "--range-end", "U11-2", "--live"])
        self.assertEqual(insert.patch_command, "insert")
        self.assertEqual(insert.range_end, "U11-2")

        rename = parser.parse_args(["patch", "rename", "NEW NAME", "--live", "--user-slot", "U10-1"])
        self.assertEqual(rename.patch_command, "rename")

        initialize = parser.parse_args(["patch", "initialize", "--live", "--user-slot", "U10-1"])
        self.assertEqual(initialize.patch_command, "initialize")

        clear = parser.parse_args(["patch", "clear", "--live", "--user-slot", "U10-1"])
        self.assertEqual(clear.patch_command, "clear")

        batch_initialize = parser.parse_args(["patch", "batch-initialize", "U10-1", "U10-2", "--live"])
        self.assertEqual(batch_initialize.patch_command, "batch-initialize")
        self.assertEqual(batch_initialize.slots, ["U10-1", "U10-2"])


if __name__ == "__main__":
    unittest.main()
