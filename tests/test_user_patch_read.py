import unittest
from unittest import mock

from tools.gt1000 import agent_cli, live


class UserPatchReadTests(unittest.TestCase):
    def test_user_slot_addresses_use_roland_seven_bit_stride(self):
        self.assertEqual(live.user_patch_base("U01-1"), [0x20, 0x00, 0x00, 0x00])
        self.assertEqual(live.user_patch_base("u01-5"), [0x20, 0x04, 0x00, 0x00])
        self.assertEqual(live.user_patch_base("U03-1"), [0x20, 0x0A, 0x00, 0x00])

    def test_user_bank_slots_are_normalized(self):
        self.assertEqual(live.user_bank_slots("u1"), ["U01-1", "U01-2", "U01-3", "U01-4", "U01-5"])

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

    def test_program_change_for_slot_is_typed_and_bounded(self):
        self.assertEqual(agent_cli.program_change_for_slot("U01-1", 1), [0xC0, 0])
        self.assertEqual(agent_cli.program_change_for_slot("U01-5", 2), [0xC1, 4])
        self.assertEqual(agent_cli.program_change_for_slot("U26-3", 16), [0xCF, 127])

        with self.assertRaises(ValueError):
            agent_cli.program_change_for_slot("U26-4", 1)

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
        self.assertEqual(assign["targetMin"], {"encoded": 32768, "logical": 0})
        self.assertEqual(assign["targetMax"], {"encoded": 32769, "logical": 1})
        self.assertEqual(assign["sourceName"], "MIDI CC 80")
        self.assertEqual(assign["midi"]["ccNumber"], 0x50)

    def test_system_view_decodes_raw_section(self):
        args = agent_cli.build_parser().parse_args(["system", "midi", "--live"])

        with mock.patch.object(agent_cli.live, "read_system_section", return_value={"00 00 30 00": [1, 2, 3]}):
            result = agent_cli.cmd_system_view(args)

        self.assertEqual(result["id"], "systemMidi")
        self.assertEqual(result["address"], ["00", "00", "30", "00"])
        self.assertEqual(result["decoded"]["rxChannelRaw"], 1)

    def test_fx_blocks_keep_validated_summary_read_size(self):
        fx1 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx1")
        fx2 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx2")
        fx3 = next(block for block in live.SUMMARY_BLOCKS if block.id == "fx3")

        self.assertEqual(fx1.size, 2)
        self.assertEqual(fx2.size, 2)
        self.assertEqual(fx3.size, 2)
        self.assertEqual([parameter.id for parameter in fx1.parameters], ["sw", "type"])
        self.assertEqual(live.chain_element_name(20), "(RESERVED)")


if __name__ == "__main__":
    unittest.main()
