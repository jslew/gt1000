import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

from tools.gt1000 import agent_cli, live


class UserPatchReadTests(unittest.TestCase):
    def test_user_slot_addresses_use_roland_seven_bit_stride(self):
        self.assertEqual(live.user_patch_base("U01-1"), [0x20, 0x00, 0x00, 0x00])
        self.assertEqual(live.user_patch_base("u01-5"), [0x20, 0x04, 0x00, 0x00])
        self.assertEqual(live.user_patch_base("U03-1"), [0x20, 0x0A, 0x00, 0x00])

    def test_preset_slot_addresses_use_documented_primary_base(self):
        self.assertEqual(live.preset_patch_base("P01-1"), [0x30, 0x00, 0x00, 0x00])
        self.assertEqual(live.preset_patch_base("p01-5"), [0x30, 0x04, 0x00, 0x00])
        self.assertEqual(live.preset_patch_base("P03-1"), [0x30, 0x0A, 0x00, 0x00])

    def test_user_bank_slots_are_normalized(self):
        self.assertEqual(live.user_bank_slots("u1"), ["U01-1", "U01-2", "U01-3", "U01-4", "U01-5"])

    def test_master_delay_live_record_size_matches_device_response(self):
        master_delay = next(block for block in live.SUMMARY_BLOCKS if block.id == "masterDelay")

        self.assertEqual(master_delay.size, 28)

    def test_temporary_patch_addresses_remap_to_user_slot(self):
        base = live.user_patch_base("U01-2")

        self.assertEqual(
            live.remap_temporary_patch_address(live.TEMPORARY_PATCH_NAME, base),
            [0x20, 0x01, 0x00, 0x00],
        )
        self.assertEqual(
            live.remap_temporary_patch_address(live.TEMPORARY_PATCH_EFFECT, base),
            [0x20, 0x01, 0x10, 0x00],
        )
        self.assertEqual(
            live.remap_temporary_patch_address(live.SYSTEM_CONTROL, base),
            live.SYSTEM_CONTROL,
        )

    def test_patch_slot_command_reads_user_slot_snapshot(self):
        snapshot = {
            "sourceSlot": "U01-1",
            "sourceAddress": ["20", "00", "00", "00"],
            "patchName": "TEST SLOT",
            "masterBPM": 120.0,
            "masterPatchLevel": 90,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "masterCarryoverEnabled": True,
            "controlAssignTempoHoldEnabled": False,
            "controlAssignInputSensitivity": 100,
            "signalChainElements": [],
            "blocks": [],
        }
        args = agent_cli.build_parser().parse_args(["patch", "slot", "U01-1", "--live", "--view", "overview"])

        with mock.patch.object(agent_cli, "read_user_slot_snapshot", return_value=snapshot) as read_slot:
            result = agent_cli.cmd_patch_slot(args)

        read_slot.assert_called_once_with("U01-1", 8.0, view="overview")
        self.assertEqual(result["patchName"], "TEST SLOT")
        self.assertEqual(result["masterPatchLevel"], 90)
        self.assertTrue(result["masterCarryoverEnabled"])
        self.assertEqual(result["controlAssignInputSensitivity"], 100)

    def test_patch_preset_command_reads_preset_snapshot(self):
        snapshot = {
            "sourceSlot": "P01-1",
            "sourceAddress": ["30", "00", "00", "00"],
            "sourceType": "preset",
            "patchName": "PRESET",
            "masterBPM": 120.0,
            "masterPatchLevel": 90,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "masterCarryoverEnabled": True,
            "controlAssignTempoHoldEnabled": False,
            "controlAssignInputSensitivity": 100,
            "signalChainElements": [],
            "blocks": [],
        }
        args = agent_cli.build_parser().parse_args(["patch", "preset", "P01-1", "--live", "--view", "overview"])

        with mock.patch.object(agent_cli, "read_preset_slot_snapshot", return_value=snapshot) as read_slot:
            result = agent_cli.cmd_patch_preset(args)

        read_slot.assert_called_once_with("P01-1", 8.0, view="overview")
        self.assertEqual(result["patchName"], "PRESET")
        self.assertEqual(result["masterPatchLevel"], 90)

    def test_patch_bank_command_reads_five_slots_sequentially(self):
        def fake_read(slot: str, timeout: float, *, view: str) -> dict:
            return {
                "patchName": slot,
                "masterBPM": 120.0,
                "masterPatchLevel": 80,
                "masterKey": "C(Am)",
                "ampControl1Enabled": False,
                "ampControl2Enabled": False,
                "signalChainElements": [],
                "blocks": [],
            }

        args = agent_cli.build_parser().parse_args(["patch", "bank", "U01", "--live", "--view", "overview"])

        with mock.patch.object(agent_cli, "read_user_slot_snapshot", side_effect=fake_read) as read_slot:
            result = agent_cli.cmd_patch_bank(args)

        self.assertEqual(result["bank"], "U01")
        self.assertEqual([patch["slot"] for patch in result["patches"]], ["U01-1", "U01-2", "U01-3", "U01-4", "U01-5"])
        self.assertEqual([call.args[0] for call in read_slot.call_args_list], ["U01-1", "U01-2", "U01-3", "U01-4", "U01-5"])
        self.assertEqual(result["patches"][0]["data"]["patchName"], "U01-1")

    def test_patch_block_can_read_from_user_slot(self):
        snapshot = {
            "patchName": "TEST SLOT",
            "masterBPM": 120.0,
            "masterPatchLevel": 80,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainElements": [{"position": 1, "rawValue": 15, "displayName": "DELAY 1"}],
            "blocks": [
                {
                    "id": "delay1",
                    "displayName": "DELAY 1",
                    "chainElementValue": 15,
                    "address": ["10", "00", "1D", "00"],
                    "isInSignalChain": True,
                    "isEnabled": True,
                    "typeName": None,
                    "parameters": [{"id": "effectLevel", "displayName": "EFFECT LEVEL", "rawValue": 35, "displayValue": None}],
                    "rawDataHex": "01 00 00 00 00 00 00 23 64",
                }
            ],
        }
        args = agent_cli.build_parser().parse_args(["patch", "block", "delay1", "--user-slot", "U01-2"])

        with mock.patch.object(agent_cli, "read_user_slot_snapshot", return_value=snapshot) as read_slot:
            result = agent_cli.cmd_patch_block(args)

        read_slot.assert_called_once_with("U01-2", 8.0, view="full")
        self.assertEqual(result["block"]["id"], "delay1")
        self.assertEqual(result["chainPositions"], [1])

    def test_patch_stompbox_reads_known_raw_record(self):
        args = agent_cli.build_parser().parse_args(["patch", "stompbox", "--live"])
        data = [0] * 0x68
        data[0] = 2
        data[17] = 4
        data2 = [0] * 0x11
        data2[0] = 3
        data3 = [0] * 0x25
        data3[36] = 5

        with mock.patch.object(agent_cli, "read_patch_records_with_timeout", return_value={
            "10 00 01 00": data,
            "10 01 00 00": data2,
            "10 02 00 00": data3,
        }) as read_records:
            result = agent_cli.cmd_patch_stompbox(args)

        requests = read_records.call_args.args[2]
        self.assertEqual([request.label for request in requests], ["Patch Stompbox", "Patch Stompbox 2", "Patch Stompbox 3"])
        self.assertEqual(requests[0].address, [0x10, 0x00, 0x01, 0x00])
        self.assertEqual(requests[0].size, [0x00, 0x00, 0x00, 0x68])
        self.assertEqual(requests[1].size, [0x00, 0x00, 0x00, 0x11])
        self.assertEqual(requests[2].size, [0x00, 0x00, 0x00, 0x25])
        self.assertTrue(result["decoded"]["supported"])
        self.assertEqual(len(result["decoded"]["selections"]), 0x68 + 0x11 + 0x25)
        self.assertEqual(result["decoded"]["selections"][0]["id"], "comp")
        self.assertEqual(result["decoded"]["selections"][0]["selection"], "CMP-2")
        self.assertEqual(result["decoded"]["selections"][17]["id"], "fx1AGSim")
        self.assertEqual(result["decoded"]["selections"][17]["selection"], "ACO-4")
        self.assertEqual(result["sections"][1]["decoded"]["selections"][0]["selection"], "PHB-3")
        self.assertEqual(result["sections"][2]["decoded"]["selections"][36]["selection"], "BDS-5")

    def test_patch_stompbox_reads_user_slot_raw_record(self):
        args = agent_cli.build_parser().parse_args(["patch", "stompbox", "--live", "--user-slot", "U03-2"])

        with mock.patch.object(agent_cli, "read_patch_records_with_timeout", return_value={
            "20 0B 01 00": [0],
            "22 05 00 00": [0],
            "23 7F 00 00": [0],
        }) as read_records:
            result = agent_cli.cmd_patch_stompbox(args)

        requests = read_records.call_args.args[2]
        self.assertEqual(requests[0].address, [0x20, 0x0B, 0x01, 0x00])
        self.assertEqual(requests[1].address, [0x22, 0x05, 0x00, 0x00])
        self.assertEqual(requests[2].address, [0x23, 0x7F, 0x00, 0x00])
        self.assertEqual(result["sourceSlot"], "U03-2")
        self.assertEqual(result["sections"][0]["address"], ["20", "0B", "01", "00"])

    def test_program_change_for_slot_is_typed_and_bounded(self):
        self.assertEqual(agent_cli.program_change_for_slot("U01-1", 1), [0xC0, 0])
        self.assertEqual(agent_cli.program_change_for_slot("U01-5", 2), [0xC1, 4])
        self.assertEqual(agent_cli.program_change_for_slot("U26-3", 16), [0xCF, 127])
        self.assertEqual(agent_cli.program_change_for_slot("U26-4", 1), [0xC0, 0])

    def test_program_change_messages_for_slot_include_bank_select(self):
        self.assertEqual(
            agent_cli.program_change_messages_for_slot("U01-1", 1),
            [[0xB0, 0, 0], [0xB0, 32, 0], [0xC0, 0]],
        )
        self.assertEqual(
            agent_cli.program_change_messages_for_slot("U26-4", 2),
            [[0xB1, 0, 1], [0xB1, 32, 0], [0xC1, 0]],
        )
        self.assertEqual(
            agent_cli.program_change_messages_for_slot("U50-5", 16),
            [[0xBF, 0, 1], [0xBF, 32, 0], [0xCF, 121]],
        )

    def test_program_change_message_is_typed_and_bounded(self):
        self.assertEqual(agent_cli.program_change_message(1, 1), [0xC0, 0])
        self.assertEqual(agent_cli.program_change_message(128, 16), [0xCF, 127])

        with self.assertRaises(ValueError):
            agent_cli.program_change_message(0, 1)
        with self.assertRaises(ValueError):
            agent_cli.program_change_message(129, 1)
        with self.assertRaises(ValueError):
            agent_cli.program_change_message(1, 17)

    def test_midi_pc_command_sends_typed_message(self):
        args = agent_cli.build_parser().parse_args(["midi", "pc", "128", "--channel", "2", "--live"])

        with mock.patch.object(agent_cli.live, "send_channel_voice") as send:
            result = agent_cli.cmd_midi_pc(args)

        send.assert_called_once_with([0xC1, 127])
        self.assertEqual(result["type"], "programChange")
        self.assertEqual(result["program"], 128)
        self.assertEqual(result["programZeroBased"], 127)
        self.assertEqual(result["messageHex"], "C1 7F")

    def test_bank_select_messages_are_typed_and_bounded(self):
        self.assertEqual(agent_cli.bank_select_messages(2, 0, 1), [[0xB0, 0, 2], [0xB0, 32, 0]])
        self.assertEqual(agent_cli.bank_select_messages(127, 127, 16), [[0xBF, 0, 127], [0xBF, 32, 127]])

        with self.assertRaises(ValueError):
            agent_cli.bank_select_messages(128, 0, 1)
        with self.assertRaises(ValueError):
            agent_cli.bank_select_messages(0, 128, 1)
        with self.assertRaises(ValueError):
            agent_cli.bank_select_messages(0, 0, 17)

    def test_midi_bank_select_command_sends_typed_messages(self):
        args = agent_cli.build_parser().parse_args(["midi", "bank-select", "2", "1", "--channel", "3", "--live"])

        with mock.patch.object(agent_cli.live, "send_channel_voice") as send:
            result = agent_cli.cmd_midi_bank_select(args)

        send.assert_has_calls([
            mock.call([0xB2, 0, 2]),
            mock.call([0xB2, 32, 1]),
        ])
        self.assertEqual(result["type"], "bankSelect")
        self.assertEqual(result["messagesHex"], ["B2 00 02", "B2 20 01"])

    def test_patch_select_command_sends_bank_select_and_program_change(self):
        args = agent_cli.build_parser().parse_args(["patch", "select", "U26-4", "--channel", "2", "--live"])

        with mock.patch.object(agent_cli.live, "send_channel_voice") as send:
            result = agent_cli.cmd_patch_select(args)

        send.assert_has_calls([
            mock.call([0xB1, 0, 1]),
            mock.call([0xB1, 32, 0]),
            mock.call([0xC1, 0]),
        ])
        self.assertEqual(result["selectedSlot"], "U26-4")
        self.assertEqual(result["messagesHex"], ["B1 00 01", "B1 20 00", "C1 00"])

    def test_patch_clone_command_reads_source_and_applies_clone_plan(self):
        args = agent_cli.build_parser().parse_args(["patch", "clone", "U03-2", "U10-1", "--live", "--verify"])
        requests = agent_cli.patch_edit.clone_read_requests("U03-2")
        source_data = {
            agent_cli.live.address_key(request.address): [index % 0x80] * agent_cli.live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests)
        }

        def fake_read_patch_records(label, timeout, requests):
            return {
                agent_cli.live.address_key(request.address): source_data[agent_cli.live.address_key(request.address)]
                for request in requests
            }

        with mock.patch.object(agent_cli, "read_required_patch_records_with_timeout", side_effect=fake_read_patch_records) as read_required_records:
            with mock.patch.object(agent_cli, "read_patch_records_lenient_with_timeout", side_effect=fake_read_patch_records) as read_patch_records:
                with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"plan": "clone:U03-2:U10-1", "writeCount": len(requests), "verified": True}) as apply_plan:
                    result = agent_cli.cmd_patch_clone(args)

        self.assertEqual(read_required_records.call_count, 1)
        self.assertEqual(read_required_records.call_args_list[0].args[0], "patch clone U03-2 --live required record")
        self.assertEqual([request.label for request in read_required_records.call_args_list[0].args[2]], ["Patch Common", "Patch Effect"])
        self.assertEqual(read_patch_records.call_count, 1)
        self.assertEqual(read_patch_records.call_args_list[0].args[0], "patch clone U03-2 --live core records")
        self.assertEqual(read_patch_records.call_args_list[0].args[1], 20.0)
        self.assertNotIn("Patch Common", [request.label for request in read_patch_records.call_args_list[0].args[2]])
        self.assertNotIn("Patch Effect", [request.label for request in read_patch_records.call_args_list[0].args[2]])
        plan = apply_plan.call_args.args[0]
        self.assertEqual(plan.id, "clone:U03-2:U10-1")
        self.assertEqual(plan.writes[0].address, [0x20, 0x2D, 0x00, 0x00])
        self.assertTrue(apply_plan.call_args.kwargs["verify"])
        self.assertEqual(result["sourceSlot"], "U03-2")
        self.assertEqual(result["destinationSlot"], "U10-1")

    def test_patch_clone_rejects_same_slot_before_live_read(self):
        args = agent_cli.build_parser().parse_args(["patch", "clone", "U03-2", "u03-2", "--live"])

        with mock.patch.object(agent_cli.live, "read_data_sets") as read_data_sets:
            with self.assertRaises(agent_cli.CLIError):
                agent_cli.cmd_patch_clone(args)

        read_data_sets.assert_not_called()

    def test_patch_export_uses_guarded_slot_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "patches.json"
            args = agent_cli.build_parser().parse_args(["patch", "export", "U03-2", "U03-3", "--output", str(output), "--live"])

            def fake_read_records(label, timeout, requests):
                return {
                    agent_cli.live.address_key(request.address): [index % 0x80] * agent_cli.live.seven_bit_address_value(request.size)
                    for index, request in enumerate(requests)
                }

            with mock.patch.object(agent_cli, "read_required_patch_records_with_timeout", side_effect=fake_read_records) as read_required_records:
                with mock.patch.object(agent_cli, "read_patch_records_lenient_with_timeout", side_effect=fake_read_records) as read_records:
                    result = agent_cli.cmd_patch_export(args)

            self.assertEqual(read_required_records.call_count, 2)
            self.assertEqual([request.label for request in read_required_records.call_args_list[0].args[2]], ["Patch Common", "Patch Effect"])
            self.assertEqual(read_records.call_count, 2)
            self.assertTrue(all(call.args[1] == 20.0 for call in read_records.call_args_list))
            self.assertNotIn("Patch Common", [request.label for request in read_records.call_args_list[0].args[2]])
            self.assertNotIn("Patch Effect", [request.label for request in read_records.call_args_list[1].args[2]])
            self.assertEqual(result["format"], "gt1000-agent-liveset-v1")
            self.assertEqual(result["patchCount"], 2)
            self.assertTrue(output.is_file())

    def test_persistent_master_set_reads_and_writes_full_patch_effect_record(self):
        args = agent_cli.build_parser().parse_args(["patch", "master-set", "level", "95", "--live", "--user-slot", "U03-2", "--verify"])
        record = [0] * agent_cli.live.seven_bit_address_value([0x00, 0x00, 0x01, 0x1C])

        with mock.patch.object(agent_cli, "read_patch_records_with_timeout", return_value={"20 0B 10 00": record}) as read_records:
            with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"plan": "master-set:level:U03-2", "writeCount": 1, "verified": True}) as apply_plan:
                result = agent_cli.cmd_patch_master_set(args)

        self.assertEqual(read_records.call_args.args[2][0].address, [0x20, 0x0B, 0x10, 0x00])
        plan = apply_plan.call_args.args[0]
        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x10, 0x00])
        self.assertEqual(plan.writes[0].data[0x5F:0x61], [0x05, 0x0F])
        self.assertTrue(apply_plan.call_args.kwargs["verify"])
        self.assertEqual(result["plan"], "master-set:level:U03-2")

    def test_control_change_message_is_typed_and_bounded(self):
        self.assertEqual(agent_cli.control_change_message(80, 127, 1), [0xB0, 80, 127])
        self.assertEqual(agent_cli.control_change_message(1, 0, 16), [0xBF, 1, 0])

        with self.assertRaises(ValueError):
            agent_cli.control_change_message(128, 0, 1)
        with self.assertRaises(ValueError):
            agent_cli.control_change_message(80, 128, 1)
        with self.assertRaises(ValueError):
            agent_cli.control_change_message(80, 0, 17)

    def test_midi_cc_command_sends_typed_message(self):
        args = agent_cli.build_parser().parse_args(["midi", "cc", "80", "127", "--channel", "2", "--live"])

        with mock.patch.object(agent_cli.live, "send_channel_voice") as send:
            result = agent_cli.cmd_midi_cc(args)

        send.assert_called_once_with([0xB1, 80, 127])
        self.assertEqual(result["type"], "controlChange")
        self.assertEqual(result["messageHex"], "B1 50 7F")

    def test_patch_set_bpm_command_applies_typed_plan(self):
        args = agent_cli.build_parser().parse_args(["patch", "set-bpm", "120.0", "--live", "--verify"])

        with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": True}) as apply:
            result = agent_cli.cmd_patch_set_bpm(args)

        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "set:masterBpm")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x61])
        self.assertEqual(plan.writes[0].data, [0x00, 0x04, 0x0B, 0x00])
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": True})
        self.assertEqual(result, {"verified": True})

    def test_patch_enable_command_applies_typed_switch_plan(self):
        args = agent_cli.build_parser().parse_args(["patch", "enable", "delay1", "--live", "--verify"])

        with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": True}) as apply:
            result = agent_cli.cmd_patch_enable(args)

        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "set:delay1.sw")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x1D, 0x00])
        self.assertEqual(plan.writes[0].data, [0x01])
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": True})
        self.assertEqual(result, {"verified": True})

    def test_patch_disable_command_resolves_alias_and_user_slot(self):
        args = agent_cli.build_parser().parse_args(["patch", "disable", "ds1", "--live", "--user-slot", "U03-2"])

        with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": None}) as apply:
            result = agent_cli.cmd_patch_enable(args)

        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "set:dist1.sw:U03-2")
        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x13, 0x00])
        self.assertEqual(plan.writes[0].data, [0x00])
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": False})
        self.assertEqual(result, {"verified": None})

    def test_patch_type_command_applies_typed_type_plan(self):
        args = agent_cli.build_parser().parse_args(["patch", "type", "ds1", "T-SCREAM", "--live", "--verify"])

        with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": True}) as apply:
            result = agent_cli.cmd_patch_type(args)

        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "set:dist1.type")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x13, 0x01])
        self.assertEqual(plan.writes[0].data, [15])
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": True})
        self.assertEqual(result, {"verified": True})

    def test_patch_move_command_reads_chain_and_applies_typed_plan(self):
        chain_values = list(agent_cli.patch_edit.CANONICAL_FULL_CHAIN)
        snapshot = {
            "signalChainElements": [
                {"position": index + 1, "rawValue": value, "displayName": live.chain_element_name(value)}
                for index, value in enumerate(chain_values)
            ],
        }
        args = agent_cli.build_parser().parse_args(["patch", "move", "delay1", "--before", "chorus", "--live", "--verify"])

        with mock.patch.object(agent_cli, "read_live_snapshot", return_value=snapshot) as read_live:
            with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": True}) as apply:
                result = agent_cli.cmd_patch_move(args)

        read_live.assert_called_once()
        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "move:chain:15:before:14")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x68])
        self.assertLess(plan.writes[0].data.index(15), plan.writes[0].data.index(14))
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": True})
        self.assertEqual(result, {"verified": True})

    def test_patch_move_command_reads_user_slot_chain(self):
        chain_values = list(agent_cli.patch_edit.CANONICAL_FULL_CHAIN)
        snapshot = {
            "signalChainElements": [
                {"position": index + 1, "rawValue": value, "displayName": live.chain_element_name(value)}
                for index, value in enumerate(chain_values)
            ],
        }
        args = agent_cli.build_parser().parse_args(["patch", "move", "delay1", "--after", "chorus", "--live", "--user-slot", "U03-2"])

        with mock.patch.object(agent_cli, "read_user_slot_snapshot", return_value=snapshot) as read_slot:
            with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": None}) as apply:
                result = agent_cli.cmd_patch_move(args)

        read_slot.assert_called_once_with("U03-2", 12.0, view="chain")
        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "move:chain:15:after:14:U03-2")
        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x10, 0x68])
        self.assertGreater(plan.writes[0].data.index(15), plan.writes[0].data.index(14))
        self.assertEqual(result, {"verified": None})

    def test_patch_assign_cc_command_maps_decoded_on_off_target(self):
        args = agent_cli.build_parser().parse_args([
            "patch", "assign-cc", "3", "delay1", "sw", "--cc", "80", "--mode", "moment", "--live", "--verify",
        ])

        with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": True}) as apply:
            result = agent_cli.cmd_patch_assign_cc(args)

        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "set:assign3:cc80:target158")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x04, 0x00])
        self.assertEqual(plan.writes[0].data[1:5], live.nibbles_for(158))
        self.assertEqual(plan.writes[0].data[5:9], live.nibbles_for(32768))
        self.assertEqual(plan.writes[0].data[9:13], live.nibbles_for(32769))
        self.assertEqual(plan.writes[0].data[13], 69)
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": True})
        self.assertEqual(result, {"verified": True})

    def test_patch_assign_cc_requires_ranges_for_non_on_off_target(self):
        args = agent_cli.build_parser().parse_args([
            "patch", "assign-cc", "4", "delay1", "effectLevel", "--cc", "80", "--mode", "moment", "--live",
        ])

        with self.assertRaises(agent_cli.CLIError):
            agent_cli.cmd_patch_assign_cc(args)

    def test_patch_tuner_assign_command_applies_typed_plan(self):
        args = agent_cli.build_parser().parse_args(["patch", "tuner-assign", "--live", "--verify"])

        with mock.patch.object(agent_cli, "apply_plan_cli", return_value={"verified": True}) as apply:
            result = agent_cli.cmd_patch_tuner_assign(args)

        plan = apply.call_args.args[0]
        self.assertEqual(plan.id, "set:tunerAssign")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x0A, 0x40])
        self.assertEqual(plan.writes[0].data, agent_cli.patch_edit.tuner_assign_data())
        self.assertEqual(apply.call_args.kwargs, {"timeout": 12.0, "verify": True})
        self.assertEqual(result, {"verified": True})

    def test_assign_decode_includes_ranges_and_midi_fields(self):
        data = bytes([
            0x01, 0x00, 0x03, 0x0D, 0x0B, 0x08, 0x00, 0x00, 0x00,
            0x08, 0x00, 0x00, 0x01, 0x45, 0x01, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x0F,
            0x00, 0x00, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x07, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])

        assign = agent_cli.assign_from_data("Assign 16", data)

        self.assertEqual(assign["target"], 987)
        self.assertEqual(assign["targetName"], "TUNER ON/OFF")
        self.assertEqual(assign["targetCategory"], "TUNER")
        self.assertIsNone(assign["targetBlockId"])
        self.assertEqual(assign["targetParameterId"], "sw")
        self.assertTrue(assign["targetIsOnOff"])
        self.assertEqual(assign["targetMin"], {"encoded": 32768, "logical": 0})
        self.assertEqual(assign["targetMax"], {"encoded": 32769, "logical": 1})
        self.assertEqual(assign["sourceName"], "MIDI CC 80")
        self.assertEqual(assign["midi"]["ccNumber"], 0x50)

    def test_assign_target_decode_exposes_block_metadata(self):
        detail = agent_cli.decode_assign_target_detail(158)

        self.assertEqual(detail["name"], "DELAY 1 SW")
        self.assertEqual(detail["category"], "DELAY 1")
        self.assertEqual(detail["blockId"], "delay1")
        self.assertEqual(detail["parameterId"], "sw")
        self.assertTrue(detail["isOnOff"])

        self.assertEqual(agent_cli.decode_assign_target_detail(932)["blockId"], "divider1")

    def test_active_assign_marks_off_block_as_description_candidate(self):
        assign_data = [0] * 44
        assign_data[0] = 1
        assign_data[1:5] = live.nibbles_for(158)
        assign_data[5:9] = live.nibbles_for(32768)
        assign_data[9:13] = live.nibbles_for(32769)
        assign_data[13] = 8
        snapshot = {
            "patchName": "ASSIGNED DELAY",
            "masterBPM": 120.0,
            "masterPatchLevel": 80,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainElements": [
                {"position": 1, "rawValue": 15, "displayName": "DELAY 1"},
                {"position": 2, "rawValue": 31, "displayName": "MAIN OUT L", "isOutput": True},
            ],
            "blocks": [
                {
                    "id": "delay1",
                    "displayName": "DELAY 1",
                    "chainElementValue": 15,
                    "isEnabled": False,
                    "typeName": None,
                    "parameters": [],
                }
            ],
            "rawSections": {"Assign 1": assign_data},
        }

        chain = agent_cli.chain_from_full(snapshot)
        delay = chain["elements"][0]

        self.assertTrue(delay["hasControlAssignment"])
        self.assertTrue(delay["includeInDescription"])
        self.assertEqual(delay["activeAssignCount"], 1)
        self.assertEqual(delay["activeAssigns"][0]["targetBlockId"], "delay1")
        self.assertEqual(chain["descriptionElements"][0]["detailBlockID"], "delay1")

    def test_direct_control_marks_off_block_as_description_candidate(self):
        patch_common = [0] * 0x7E
        patch_common[0x31] = 33
        patch_common[0x32] = 0
        system_control = [0] * 0x36
        snapshot = {
            "patchName": "CTL DELAY",
            "masterBPM": 120.0,
            "masterPatchLevel": 80,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainElements": [
                {"position": 1, "rawValue": 15, "displayName": "DELAY 1"},
                {"position": 2, "rawValue": 31, "displayName": "MAIN OUT L", "isOutput": True},
            ],
            "blocks": [
                {
                    "id": "delay1",
                    "displayName": "DELAY 1",
                    "chainElementValue": 15,
                    "isEnabled": False,
                    "typeName": None,
                    "parameters": [],
                }
            ],
            "rawSections": [
                {"id": "patchCommon", "dataHex": live.hex_string(patch_common)},
                {"id": "systemControl", "dataHex": live.hex_string(system_control)},
            ],
        }

        controls = agent_cli.controls_from_full(snapshot)["controls"]
        chain = agent_cli.chain_from_full(snapshot)
        delay = chain["elements"][0]

        self.assertEqual(controls["CTL 1"]["function"], "DELAY 1")
        self.assertEqual(controls["CTL 1"]["functionTargetBlockId"], "delay1")
        self.assertTrue(controls["CTL 1"]["functionCanEnableBlock"])
        self.assertTrue(delay["hasControlAssignment"])
        self.assertTrue(delay["includeInDescription"])
        self.assertEqual(delay["directControlCount"], 1)
        self.assertEqual(delay["directControls"][0]["control"], "CTL 1")

    def test_performance_view_summarizes_direct_controls_and_assigns(self):
        patch_common = [0] * 0x7E
        patch_common[0x31] = 33
        patch_common[0x32] = 0
        system_control = [0] * 0x36
        system_control[0x2B] = 1
        assign_data = [0] * 0x2C
        assign_data[0] = 1
        assign_data[1:5] = live.nibbles_for(987)
        assign_data[5:9] = live.nibbles_for(32768)
        assign_data[9:13] = live.nibbles_for(32769)
        assign_data[13] = 8
        assign_data[14] = 1
        snapshot = {
            "patchName": "PERF",
            "masterBPM": 120.0,
            "masterPatchLevel": 80,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainElements": [],
            "blocks": [],
            "rawSections": [
                {"id": "patchCommon", "dataHex": live.hex_string(patch_common)},
                {"id": "systemControl", "dataHex": live.hex_string(system_control)},
                {"id": "Assign 1", "dataHex": live.hex_string(assign_data)},
            ],
        }

        performance = agent_cli.performance_from_full(snapshot)
        ctl1 = next(row for row in performance["controls"] if row["control"] == "CTL 1")

        self.assertEqual(performance["id"], "patchPerformance")
        self.assertTrue(performance["tunerAvailable"])
        self.assertEqual(performance["activeAssignCount"], 1)
        self.assertEqual(ctl1["directFunction"], "DELAY 1")
        self.assertEqual(ctl1["assigns"][0]["target"], "TUNER ON/OFF")
        self.assertEqual(ctl1["action"], "Direct: DELAY 1 (TOGGLE); CTL 1 -> TUNER ON/OFF (MOMENT)")
        self.assertTrue(any("controls use SYSTEM preference" in note for note in performance["notes"]))

    def test_live_patch_performance_reads_assigns_for_overlay_actions(self):
        snapshot = {
            "patchName": "PERF",
            "masterBPM": 120.0,
            "masterPatchLevel": 80,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainElements": [],
            "blocks": [],
            "rawSections": [],
        }
        args = agent_cli.build_parser().parse_args(["patch", "performance", "--live"])

        with mock.patch.object(agent_cli, "read_performance_snapshot_with_timeout", return_value=snapshot) as read_live:
            with mock.patch.object(agent_cli, "performance_from_full", return_value={"id": "patchPerformance"}):
                agent_cli.patch_view(args, "performance")

        self.assertEqual(read_live.call_args.args, ("patch performance --live", 8.0))

    def test_musician_summary_describes_tone_and_playable_controls(self):
        snapshot = self.performance_snapshot("MUSIC", level=83, delay_enabled=False, ctl1_function=33, assign_target=987)

        summary = agent_cli.musician_summary_from_full(snapshot)

        self.assertEqual(summary["id"], "patchMusicianSummary")
        self.assertEqual(summary["headline"], "MUSIC: level 83, 120 BPM")
        self.assertIn("DELAY 1", summary["tone"])
        self.assertIn("CTL 1", summary["controlSummary"])
        self.assertTrue(summary["tunerAvailable"])
        self.assertNotIn("rawSections", summary)
        self.assertNotIn("dataHex", json.dumps(summary))
        self.assertEqual(summary["playableControls"][0]["control"], "CTL 1")
        self.assertEqual(set(summary["playableControls"][0]), {"control", "kind", "preference", "action"})

    def test_live_patch_musician_summary_uses_performance_reader(self):
        snapshot = self.performance_snapshot("MUSIC", level=83, delay_enabled=False, ctl1_function=33, assign_target=987)
        args = agent_cli.build_parser().parse_args(["patch", "musician-summary", "--live"])

        with mock.patch.object(agent_cli, "read_performance_snapshot_with_timeout", return_value=snapshot) as read_live:
            with mock.patch.object(agent_cli, "musician_summary_from_full", return_value={"id": "patchMusicianSummary"}):
                agent_cli.patch_view(args, "musician-summary")

        self.assertEqual(read_live.call_args.args, ("patch musician-summary --live", 8.0))

    def test_performance_live_reader_reads_core_strictly_and_assigns_leniently(self):
        required_calls = []
        lenient_calls = []

        def fake_required(label, timeout, requests):
            required_calls.append((label, timeout, requests))
            return {agent_cli.live.address_key(request.address): [0] * agent_cli.live.seven_bit_address_value(request.size) for request in requests}

        def fake_lenient(label, timeout, requests):
            lenient_calls.append((label, timeout, requests))
            return {}

        original_required = agent_cli.read_required_patch_records_with_timeout
        original_lenient = agent_cli.read_patch_records_lenient_with_timeout
        agent_cli.read_required_patch_records_with_timeout = fake_required
        agent_cli.read_patch_records_lenient_with_timeout = fake_lenient
        try:
            agent_cli.read_performance_snapshot_with_timeout("patch performance --live", 8)
        finally:
            agent_cli.read_patch_records_lenient_with_timeout = original_lenient
            agent_cli.read_required_patch_records_with_timeout = original_required

        self.assertEqual([request.label for request in required_calls[0][2]], ["Master BPM", "Patch Effect", "Patch Common", "System Control"])
        self.assertEqual([request.label for request in lenient_calls[0][2]][0], "Assign 1")
        self.assertEqual([request.label for request in lenient_calls[0][2]][-1], "Assign 16")

    def test_patch_diff_reports_musical_changes(self):
        source = self.performance_snapshot("SOURCE", level=80, delay_enabled=False, ctl1_function=33, assign_target=987)
        target = self.performance_snapshot("TARGET", level=92, delay_enabled=True, ctl1_function=0, assign_target=158)

        diff = agent_cli.patch_diff_from_full(source, target, source_label="A", target_label="B")

        self.assertEqual(diff["id"], "patchDiff")
        self.assertIn({"field": "masterPatchLevel", "label": "Patch level", "source": 80, "target": 92}, diff["overviewChanges"])
        delay_change = next(change for change in diff["blockChanges"] if change["blockId"] == "delay1")
        self.assertIn({"field": "isEnabled", "label": "on/off", "source": False, "target": True}, delay_change["changes"])
        ctl1_change = next(change for change in diff["controlChanges"] if change["control"] == "CTL 1")
        self.assertIn({"field": "function", "label": "function", "source": "DELAY 1", "target": "OFF"}, ctl1_change["changes"])
        assign_change = next(change for change in diff["assignChanges"] if change["assign"] == "Assign 1")
        self.assertIn({"field": "targetName", "label": "target", "source": "TUNER ON/OFF", "target": "DELAY 1 SW"}, assign_change["changes"])

    def test_live_patch_diff_reads_user_slots_full(self):
        source = self.performance_snapshot("SOURCE", level=80, delay_enabled=False, ctl1_function=33, assign_target=987)
        target = self.performance_snapshot("TARGET", level=92, delay_enabled=True, ctl1_function=0, assign_target=158)
        args = agent_cli.build_parser().parse_args(["patch", "diff", "U10-1", "U10-2", "--live"])

        with mock.patch.object(agent_cli, "read_clone_snapshot_with_timeout", side_effect=[source, target]) as read_slot:
            result = agent_cli.cmd_patch_diff(args)

        self.assertEqual(result["id"], "patchDiff")
        self.assertEqual(read_slot.call_args_list[0].args, ("patch diff U10-1 --live", 8.0, "U10-1"))
        self.assertEqual(read_slot.call_args_list[1].args, ("patch diff U10-2 --live", 8.0, "U10-2"))

    def test_setlist_audit_flags_level_tuner_and_expression_risks(self):
        performances = [
            {"slot": "U10-1", "performance": self.performance_view("A", level=80, bpm=120.0, tuner=True, exp1="Direct: FOOT VOLUME")},
            {"slot": "U10-2", "performance": self.performance_view("B", level=94, bpm=128.0, tuner=False, exp1="Direct: PEDAL FX")},
        ]

        audit = agent_cli.setlist_audit_from_performances(["U10-1", "U10-2"], performances)

        self.assertEqual(audit["id"], "setlistAudit")
        self.assertEqual(audit["patchCount"], 2)
        categories = [finding["category"] for finding in audit["findings"]]
        self.assertIn("level", categories)
        self.assertIn("tuner", categories)
        self.assertIn("tempo", categories)
        self.assertIn("expression", categories)

    def test_setlist_audit_keeps_partial_patch_when_controls_do_not_decode(self):
        performance = {
            "patchName": "PARTIAL",
            "masterPatchLevel": 80,
            "masterBPM": 120.0,
            "tunerAvailable": False,
            "controls": [],
            "partial": True,
        }

        audit = agent_cli.setlist_audit_from_performances(["U10-1"], [{"slot": "U10-1", "performance": performance}])

        self.assertTrue(audit["patches"][0]["partial"])
        self.assertIn("read", [finding["category"] for finding in audit["findings"]])

    def test_live_setlist_audit_reads_requested_slots(self):
        args = agent_cli.build_parser().parse_args(["patch", "setlist-audit", "U10-1", "U10-2", "--live"])
        snapshots = [
            self.performance_snapshot("A", level=80, delay_enabled=False, ctl1_function=33, assign_target=987),
            self.performance_snapshot("B", level=82, delay_enabled=False, ctl1_function=33, assign_target=987),
        ]

        with mock.patch.object(agent_cli, "read_user_slot_snapshot_lenient", side_effect=snapshots) as read_slot:
            result = agent_cli.cmd_patch_setlist_audit(args)

        self.assertEqual(result["slots"], ["U10-1", "U10-2"])
        self.assertEqual(read_slot.call_args_list[0].args, ("U10-1", 8.0))
        self.assertEqual(read_slot.call_args_list[0].kwargs, {"view": "performance"})
        self.assertEqual(read_slot.call_args_list[1].args, ("U10-2", 8.0))

    def performance_view(self, name: str, *, level: int, bpm: float, tuner: bool, exp1: str) -> dict:
        return {
            "patchName": name,
            "masterPatchLevel": level,
            "masterBPM": bpm,
            "tunerAvailable": tuner,
            "controls": [
                {"control": "EXP 1", "action": exp1, "preference": "PATCH"},
                {"control": "EXP 2", "action": "No patch action", "preference": "PATCH"},
            ],
        }

    def performance_snapshot(self, name: str, *, level: int, delay_enabled: bool, ctl1_function: int, assign_target: int) -> dict:
        patch_common = [0] * 0x7E
        patch_common[0x31] = ctl1_function
        patch_common[0x32] = 0
        system_control = [0] * 0x36
        assign_data = [0] * 0x2C
        assign_data[0] = 1
        assign_data[1:5] = live.nibbles_for(assign_target)
        assign_data[5:9] = live.nibbles_for(32768)
        assign_data[9:13] = live.nibbles_for(32769)
        assign_data[13] = 8
        return {
            "patchName": name,
            "masterBPM": 120.0,
            "masterPatchLevel": level,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainSummary": "DELAY 1 -> MAIN OUT L",
            "signalChainElements": [
                {"position": 1, "rawValue": 15, "displayName": "DELAY 1"},
                {"position": 2, "rawValue": 31, "displayName": "MAIN OUT L", "isOutput": True},
            ],
            "blocks": [
                {
                    "id": "delay1",
                    "displayName": "DELAY 1",
                    "chainElementValue": 15,
                    "isEnabled": delay_enabled,
                    "isInSignalChain": True,
                    "typeName": None,
                    "parameters": [],
                }
            ],
            "rawSections": [
                {"id": "patchCommon", "dataHex": live.hex_string(patch_common)},
                {"id": "systemControl", "dataHex": live.hex_string(system_control)},
                {"id": "Assign 1", "dataHex": live.hex_string(assign_data)},
            ],
        }

    def test_chain_view_reads_assigns_for_reachability(self):
        labels = [request.label for request in agent_cli.requests_for_view("chain")]

        self.assertIn("Assign 1", labels)
        self.assertIn("Assign 16", labels)

    def test_live_patch_chain_reads_assigns_for_reachability(self):
        snapshot = {
            "patchName": "CHAIN",
            "masterBPM": 120.0,
            "masterPatchLevel": 80,
            "masterKey": "C(Am)",
            "ampControl1Enabled": False,
            "ampControl2Enabled": False,
            "signalChainElements": [],
            "blocks": [],
            "rawSections": [],
        }
        args = agent_cli.build_parser().parse_args(["patch", "chain", "--live"])

        with mock.patch.object(agent_cli, "read_live_snapshot_with_timeout", return_value=snapshot) as read_live:
            agent_cli.patch_view(args, "chain")

        labels = [request.label for request in read_live.call_args.kwargs["requests"]]
        self.assertIn("Assign 1", labels)
        self.assertIn("Assign 16", labels)

    def test_control_function_decode_covers_documented_patch_control_values(self):
        self.assertEqual(agent_cli.decode_control_function(5), "LEVEL +10")
        self.assertEqual(agent_cli.decode_control_function(14), "MASTER DELAY TAP")
        self.assertEqual(agent_cli.decode_control_function(1, is_num=True), "MATCHING NUM")
        detail = agent_cli.decode_control_function_detail(47)

        self.assertEqual(detail["name"], "DIVIDER 1 CHANNEL SELECT")
        self.assertEqual(detail["blockId"], "divider1")
        self.assertEqual(detail["parameterId"], "channelSelect")

    def test_system_view_decodes_raw_section(self):
        args = agent_cli.build_parser().parse_args(["system", "midi", "--live"])

        data = [0] * 0x1B
        data[0] = 1
        data[1] = 0
        data[2] = 16
        data[3] = 2
        data[4] = 3
        data[5] = 1
        data[6] = 1
        data[8] = 1
        data[9] = 0
        data[10] = 1
        data[13] = 32
        data[0x0E] = 33
        data[0x10] = 63
        data[0x1A] = 31

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 30 00": data}):
            result = agent_cli.cmd_system_view(args)

        self.assertEqual(result["id"], "systemMidi")
        self.assertEqual(result["address"], ["00", "00", "30", "00"])
        self.assertEqual(result["size"], ["00", "00", "00", "1B"])
        self.assertEqual(result["decoded"]["rxChannelRaw"], 1)
        self.assertEqual(result["decoded"]["rxChannel"], "Ch.2")
        self.assertEqual(result["decoded"]["txChannel"], "RX")
        self.assertEqual(result["decoded"]["syncClock"], "MIDI(AUTO)")
        self.assertEqual(result["decoded"]["midiInThru"], "USB/MIDI")
        self.assertEqual(result["decoded"]["clockOut"], "ON")
        self.assertEqual(result["decoded"]["mapSelect"], "PROG")
        self.assertEqual(result["decoded"]["controlChangeNumbers"]["NUM 1"], {"raw": 0, "cc": "OFF"})
        self.assertEqual(result["decoded"]["controlChangeNumbers"]["NUM 2"], {"raw": 1, "cc": "CC#1"})
        self.assertEqual(result["decoded"]["controlChangeNumbers"]["NUM 5"], {"raw": 32, "cc": "CC#64"})
        self.assertEqual(result["decoded"]["controlChangeNumbers"]["BANK DOWN"], {"raw": 33, "cc": "CC#65"})
        self.assertEqual(result["decoded"]["controlChangeNumbers"]["CTL 1"], {"raw": 63, "cc": "CC#95"})
        self.assertEqual(result["decoded"]["controlChangeNumbers"]["EXP 3"], {"raw": 31, "cc": "CC#31"})

    def test_system_common_view_decodes_metronome_bpm(self):
        args = agent_cli.build_parser().parse_args(["system", "common", "--live"])
        data = [0] * 0x0D
        data[0x09:0x0D] = live.nibbles_for(1200)

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 00 00": data}) as read_section:
            result = agent_cli.cmd_system_view(args)

        read_section.assert_called_once_with([0x00, 0x00, 0x00, 0x00], [0x00, 0x00, 0x00, 0x0D], timeout=8.0)
        self.assertEqual(result["id"], "systemCommon")
        self.assertEqual(result["address"], ["00", "00", "00", "00"])
        self.assertEqual(result["decoded"]["metronomeBpmRaw"], [0, 4, 11, 0])
        self.assertEqual(result["decoded"]["metronomeBpm"], 120.0)

    def test_pcmap_bank_decodes_user_and_preset_targets(self):
        data = []
        for value in [0, 249, 250, 499]:
            data.extend(live.nibbles_for(value))

        entries = agent_cli.decode_pcmap_bank(data, bank=2)

        self.assertEqual(entries[0]["programChange"], 129)
        self.assertEqual(entries[0]["patch"], "U01-1")
        self.assertEqual(entries[1]["patch"], "U50-5")
        self.assertEqual(entries[2]["patch"], "P01-1")
        self.assertEqual(entries[3]["patch"], "P50-5")
        self.assertEqual(agent_cli.pcmap_bank_address(2), [0x00, 0x10, 0x04, 0x00])

    def test_system_pcmap_view_reads_selected_bank(self):
        args = agent_cli.build_parser().parse_args(["system", "pcmap", "--live", "--bank", "1"])
        data = live.nibbles_for(0) + live.nibbles_for(250)

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 10 00 00": data}) as read_section:
            result = agent_cli.cmd_system_pcmap(args)

        read_section.assert_called_once_with([0x00, 0x10, 0x00, 0x00], [0x00, 0x00, 0x04, 0x00], timeout=8.0)
        self.assertEqual(result["id"], "programChangeMap")
        self.assertEqual(result["banks"][0]["entries"][0]["patch"], "U01-1")
        self.assertEqual(result["banks"][0]["entries"][1]["patch"], "P01-1")

    def test_system_input_setting_decodes_name_and_level(self):
        data = list(b"INPUT ONE       ") + [34]

        decoded = agent_cli.decode_system_input_setting(
            data,
            number=1,
            address=[0x00, 0x01, 0x00, 0x00],
            size=[0x00, 0x00, 0x00, 0x11],
        )

        self.assertEqual(decoded["number"], 1)
        self.assertEqual(decoded["address"], ["00", "01", "00", "00"])
        self.assertEqual(decoded["name"], "INPUT ONE")
        self.assertEqual(decoded["inputLevelRaw"], 34)
        self.assertEqual(decoded["inputLevelDb"], 2)
        self.assertEqual(agent_cli.system_input_setting_address(10), [0x00, 0x01, 0x09, 0x00])

    def test_system_inputs_view_reads_selected_input(self):
        args = agent_cli.build_parser().parse_args(["system", "inputs", "--live", "--number", "2"])
        data = list(b"SECOND          ") + [32]

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 01 01 00": data}) as read_section:
            result = agent_cli.cmd_system_inputs(args)

        read_section.assert_called_once_with([0x00, 0x01, 0x01, 0x00], [0x00, 0x00, 0x00, 0x11], timeout=8.0)
        self.assertEqual(result["id"], "systemInputSettings")
        self.assertEqual(result["settings"][0]["name"], "SECOND")
        self.assertEqual(result["settings"][0]["inputLevelDb"], 0)

    def test_system_inout_decodes_validated_common_fields(self):
        data = [0] * 0x43
        data[0] = 32
        data[1] = 0
        data[2] = 1
        data[0x03] = 30
        data[0x04] = 34
        data[0x05] = 17
        data[0x06] = 2
        data[0x08] = 0
        data[0x09] = 31
        data[0x11] = 24
        data[0x12] = 39
        data[0x21] = 2
        data[0x22] = 42
        data[0x23:0x25] = live.nibbles_for(125, byte_count=2)
        data[0x25] = 1
        data[0x26:0x28] = live.nibbles_for(150, byte_count=2)
        data[0x28:0x2A] = live.nibbles_for(75, byte_count=2)
        data[0x2B:0x2D] = live.nibbles_for(110, byte_count=2)
        data[0x2D:0x2F] = live.nibbles_for(111, byte_count=2)
        data[0x30:0x32] = live.nibbles_for(112, byte_count=2)
        data[0x32:0x34] = live.nibbles_for(113, byte_count=2)
        data[0x3A] = 0
        data[0x3B] = 88
        data[0x3C] = 1
        data[0x3D] = 1
        data[0x3E] = 0
        data[0x3F] = 31
        data[0x40] = 32
        data[0x41] = 33
        data[0x42] = 34

        decoded = agent_cli.decode_system_inout(data)

        self.assertEqual(decoded["inputLevelDb"], 0)
        self.assertEqual(decoded["mainOutSelect"], "LINE/PHONES")
        self.assertEqual(decoded["mainROutSelect"], "RECORDING")
        self.assertEqual(decoded["subOutSelect"], "KATANA-50 INPUT")
        self.assertEqual(decoded["subROutSelect"], "KATANA-50 MkII POWER AMP IN")
        self.assertEqual(decoded["mainLeft"]["lowGainDb"], -2)
        self.assertEqual(decoded["mainLeft"]["midGainDb"], 2)
        self.assertEqual(decoded["mainLeft"]["midFreq"], "1.00kHz")
        self.assertEqual(decoded["mainLeft"]["midQ"], "2")
        self.assertEqual(decoded["mainLeft"]["lowCut"], "FLAT")
        self.assertEqual(decoded["mainLeft"]["highCut"], "FLAT")
        self.assertEqual(decoded["phonesSetting"], "MAIN+SUB")
        self.assertEqual(decoded["totalNsThresholdDb"], 10)
        self.assertEqual(decoded["totalReverbLevel"], 125)
        self.assertEqual(decoded["mainLevelSelect"], "+4dBu")
        self.assertEqual(decoded["usbDryOut"], 150)
        self.assertEqual(decoded["usbDryToEfx"], 75)
        self.assertEqual(decoded["usbMainEfxOut"], 110)
        self.assertEqual(decoded["usbMainMixLevel"], 111)
        self.assertEqual(decoded["usbSubEfxOut"], 112)
        self.assertEqual(decoded["usbSubMixLevel"], 113)
        self.assertEqual(decoded["subLevelSelect"], "-10dBu")
        self.assertEqual(decoded["subOutputLevel"], 88)
        self.assertEqual(decoded["subGroundLift"], "ON")
        self.assertEqual(decoded["mainStereoLink"], "ON")
        self.assertEqual(decoded["subStereoLink"], "OFF")
        self.assertEqual(decoded["outputLevels"], {
            "mainLeftDb": -1,
            "mainRightDb": 0,
            "subLeftDb": 1,
            "subRightDb": 2,
        })

    def test_system_effects_view_decodes_validated_fields(self):
        args = agent_cli.build_parser().parse_args(["system", "effects", "--live"])
        data = [1, 0, 73, 2, 2, 0, 0]

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 50 00": data}):
            result = agent_cli.cmd_system_view(args)

        self.assertEqual(result["id"], "systemEffects")
        self.assertEqual(result["address"], ["00", "00", "50", "00"])
        self.assertEqual(result["decoded"]["phraseLoopMode"], "STEREO")
        self.assertEqual(result["decoded"]["phraseLoopRecAction"], "REC>PLAY>DUB")
        self.assertEqual(result["decoded"]["metronomeLevel"], 73)
        self.assertEqual(result["decoded"]["mainGroundLift"], 3)
        self.assertEqual(result["decoded"]["totalMetronomeOut"], "MAIN+SUB")

    def test_system_pitch_view_decodes_validated_fields(self):
        args = agent_cli.build_parser().parse_args(["system", "pitch", "--live"])
        data = live.nibbles_for(440) + [3, 14, 1]

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 60 00": data}):
            result = agent_cli.cmd_system_view(args)

        self.assertEqual(result["id"], "systemPitch")
        self.assertEqual(result["address"], ["00", "00", "60", "00"])
        self.assertEqual(result["decoded"]["referencePitchHz"], 440)
        self.assertEqual(result["decoded"]["polyTunerType"], "7-DROP A")
        self.assertEqual(result["decoded"]["polyTunerOffset"], "-2")
        self.assertEqual(result["decoded"]["tunerOutput"], "BYPASS")

    def test_system_controls_view_decodes_global_functions(self):
        args = agent_cli.build_parser().parse_args(["system", "controls", "--live"])
        data = [0] * 0x36
        data[0x00] = 1
        data[0x01] = 0
        data[0x0E] = 33
        data[0x0F] = 1
        data[0x20] = 3
        data[0x23] = 0
        data[0x2A] = 1
        data[0x33] = 1

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 10 00": data}):
            result = agent_cli.cmd_system_view(args)

        controls = result["decoded"]["controls"]
        self.assertEqual(result["id"], "systemControl")
        self.assertEqual(result["address"], ["00", "00", "10", "00"])
        self.assertEqual(controls["NUM 1"]["function"], "MATCHING NUM")
        self.assertEqual(controls["NUM 1"]["mode"], "TOGGLE")
        self.assertEqual(controls["NUM 1"]["preference"], "PATCH")
        self.assertEqual(controls["CTL 1"]["function"], "DELAY 1")
        self.assertEqual(controls["CTL 1"]["functionTargetBlockId"], "delay1")
        self.assertTrue(controls["CTL 1"]["functionCanEnableBlock"])
        self.assertEqual(controls["CTL 1"]["mode"], "MOMENT")
        self.assertEqual(controls["CTL 1"]["preference"], "SYSTEM")
        self.assertEqual(controls["EXP 1"]["function"], "FV + PEDAL FX")
        self.assertEqual(controls["EXP 1"]["functionTargetBlockId"], "pedalFx")
        self.assertEqual(result["decoded"]["preferences"]["EXP 1"], "SYSTEM")

    def test_system_manual_view_decodes_manual_control2_fields(self):
        args = agent_cli.build_parser().parse_args(["system", "manual", "--live"])
        data = [29, 0, 55, 1, 58, 0, 43, 1, 1, 0, 0, 1, 0, 1, 0]

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 70 00": data}):
            result = agent_cli.cmd_system_view(args)

        controls = result["decoded"]["controls"]
        self.assertEqual(result["id"], "systemManualControl")
        self.assertEqual(result["address"], ["00", "00", "70", "00"])
        self.assertEqual(controls["NUM 1"]["function"], "DELAY 1")
        self.assertEqual(controls["NUM 1"]["functionTargetBlockId"], "delay1")
        self.assertTrue(controls["NUM 1"]["functionCanEnableBlock"])
        self.assertEqual(controls["NUM 1"]["mode"], "TOGGLE")
        self.assertEqual(controls["NUM 2"]["function"], "TUNER")
        self.assertEqual(controls["NUM 2"]["mode"], "MOMENT")
        self.assertEqual(controls["NUM 2"]["preference"], "SYSTEM")
        self.assertEqual(controls["NUM 3"]["function"], "FX 4")
        self.assertEqual(controls["NUM 4"]["function"], "DIVIDER 1 CHANNEL SELECT")
        self.assertEqual(controls["NUM 4"]["functionTargetParameterId"], "channelSelect")
        self.assertEqual(controls["NUM 5"]["function"], "LEVEL +10")

    def test_fx_blocks_keep_validated_summary_read_size(self):
        fx1 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx1")
        fx2 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx2")
        fx3 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx3")
        fx4 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx4")

        self.assertEqual(fx1.size, 2)
        self.assertEqual(fx2.size, 2)
        self.assertEqual(fx3.size, 2)
        self.assertEqual(fx4.address, [0x10, 0x02, 0x01, 0x00])
        self.assertEqual(fx4.size, 2)
        self.assertEqual([parameter.id for parameter in fx1.parameters], ["sw", "type"])
        self.assertEqual(live.chain_element_name(20), "(RESERVED)")

    def test_fx_algorithm_blocks_expose_named_records_without_changing_summary_reads(self):
        fx1_chorus = next(block for block in live.FX_ALGORITHM_BLOCKS if block.id == "fx1Chorus")
        fx2_pitch_shift = next(block for block in live.FX_ALGORITHM_BLOCKS if block.id == "fx2PitchShift")
        fx1_tremolo = next(block for block in live.FX_ALGORITHM_BLOCKS if block.id == "fx1Tremolo")
        fx1_touch_wah = next(block for block in live.FX_ALGORITHM_BLOCKS if block.id == "fx1TWah")
        fx3_vibrato = next(block for block in live.FX_ALGORITHM_BLOCKS if block.id == "fx3Vibrato")
        fx4_chorus = next(block for block in live.FX_ALGORITHM_BLOCKS if block.id == "fx4Chorus")

        self.assertEqual(fx1_chorus.address, [0x10, 0x00, 0x27, 0x00])
        self.assertEqual(fx1_chorus.size, 29)
        self.assertIn("effectLevel2", [parameter.id for parameter in fx1_chorus.parameters])
        self.assertEqual(fx2_pitch_shift.address, [0x10, 0x00, 0x4E, 0x00])
        self.assertIn("ps1PreDelay", [parameter.id for parameter in fx2_pitch_shift.parameters])
        self.assertEqual(fx1_tremolo.address, [0x10, 0x00, 0x3B, 0x00])
        self.assertEqual(fx1_touch_wah.address, [0x10, 0x00, 0x3C, 0x00])
        self.assertEqual(fx3_vibrato.address, [0x10, 0x00, 0x73, 0x00])
        self.assertEqual(fx4_chorus.address, [0x10, 0x02, 0x05, 0x00])


if __name__ == "__main__":
    unittest.main()
