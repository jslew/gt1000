import json
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
    def test_ports_parser_and_live_timeout_wrapper(self):
        args = agent_cli.build_parser().parse_args(["ports", "--live", "--timeout", "2"])
        self.assertEqual(args.command, "ports")
        self.assertEqual(args.timeout, 2)

        self.assertEqual(agent_cli.live_call_with_timeout("test", 2, sorted, [3, 1, 2]), [1, 2, 3])
        self.assertEqual(len(agent_cli.live_call_with_timeout("large", 5, bytes, 1024 * 1024)), 1024 * 1024)
        with self.assertRaises(agent_cli.CLIError) as context:
            agent_cli.live_call_with_timeout("test", 0.1, time.sleep, 5)
        self.assertIn("did not finish", str(context.exception))

    def test_live_timeout_wrapper_preserves_kwargs_and_mock_fallback(self):
        def kwonly(*, value):
            return value

        self.assertEqual(agent_cli.live_call_with_timeout("kwargs", 2, kwonly, value=7), 7)

        mock = MagicMock(return_value={"ok": True})
        self.assertEqual(agent_cli.live_call_with_timeout("mock", 2, mock, timeout=8.0), {"ok": True})
        mock.assert_called_once_with(timeout=8.0)

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

    def test_required_patch_read_retries_records_independently(self):
        requests = [
            agent_cli.live.PatchReadRequest("Patch Common", [0x20, 0x00, 0x00, 0x00], [0, 0, 0, 1]),
            agent_cli.live.PatchReadRequest("Patch Effect", [0x20, 0x00, 0x10, 0x00], [0, 0, 0, 1]),
        ]
        calls = []

        def fake_strict_read(label, timeout, requests, reader=agent_cli.patch_edit.read_data_sets_batched, attempts=3):
            request = requests[0]
            calls.append(request.label)
            if request.label == "Patch Common" and calls.count("Patch Common") == 1:
                raise agent_cli.CLIError("transient")
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

        self.assertEqual(calls, ["Patch Common", "Patch Effect", "Patch Common"])
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
        self.assertEqual(master_parameters["level"]["offset"], 0x60)
        self.assertEqual(master_parameters["level"]["kind"], "byte")
        self.assertEqual(master_parameters["level"]["byteCount"], 1)
        self.assertIn("input-sensitivity", master_parameters)

        controls = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "controls"]))
        self.assertEqual(controls["id"], "controls")
        self.assertIn("ctl1", controls["controls"])
        self.assertIn("dist1", controls["switchFunctions"])

        assign = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "assign"]))
        self.assertEqual(assign["id"], "assign")
        self.assertIn("general", assign["commands"])
        self.assertIn("tuner", assign["targetAliases"])

        led = agent_cli.cmd_patch_schema(agent_cli.build_parser().parse_args(["patch", "schema", "led"]))
        self.assertEqual(led["id"], "led")
        self.assertIn("ctl1", led["controls"])
        self.assertIn("auto-cyan", led["onColors"])

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
        parser_paths = {("ports",)}

        self.assertIn(("ports",), live_paths)
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
