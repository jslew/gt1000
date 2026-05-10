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

    def test_chain_view_reads_assigns_for_reachability(self):
        labels = [request.label for request in agent_cli.requests_for_view("chain")]

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
