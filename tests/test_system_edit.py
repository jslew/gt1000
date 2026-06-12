import unittest

from tools.gt1000 import live, system_edit


class SystemEditTests(unittest.TestCase):
    def test_build_system_inout_set_plan_usb_dry_out(self) -> None:
        plan = system_edit.build_system_inout_set_plan("usb-dry-out", 150)
        self.assertEqual(plan.id, "system-inout-set:usbDryOut")
        self.assertEqual(len(plan.writes), 1)
        write = plan.writes[0]
        self.assertEqual(write.address, live.address_adding(live.SYSTEM_IN_OUT, 0x26))
        self.assertEqual(write.data, live.nibbles_for(150, byte_count=2))

    def test_build_system_inout_set_rejects_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            system_edit.build_system_inout_set_plan("usbMainMixLevel", 201)

    def test_normalize_field_aliases(self) -> None:
        self.assertEqual(system_edit.normalize_inout_field("usb-main-efx-out"), "usbMainEfxOut")

    def test_build_system_inputs_set_plan_input_level(self) -> None:
        plan = system_edit.build_system_inputs_set_plan(3, "input-level", 12)
        self.assertEqual(plan.id, "system-inputs-set:3:inputLevel")
        self.assertEqual(len(plan.writes), 2)
        preset_write = plan.writes[0]
        active_write = plan.writes[1]
        self.assertEqual(preset_write.address, live.address_adding([0x00, 0x01, 0x02, 0x00], 0x10))
        self.assertEqual(preset_write.data, [44])
        self.assertEqual(active_write.address, live.address_adding(live.SYSTEM_IN_OUT, 0x00))
        self.assertEqual(active_write.data, [44])

    def test_build_system_inout_set_plan_input_level(self) -> None:
        plan = system_edit.build_system_inout_set_plan("input-level", 3)
        self.assertEqual(plan.id, "system-inout-set:inputLevel")
        write = plan.writes[0]
        self.assertEqual(write.address, live.address_adding(live.SYSTEM_IN_OUT, 0x00))
        self.assertEqual(write.data, [35])

    def test_build_system_inputs_set_plan_name(self) -> None:
        plan = system_edit.build_system_inputs_set_plan(1, "name", "TELE")
        write = plan.writes[0]
        self.assertEqual(write.address, [0x00, 0x01, 0x00, 0x00])
        self.assertEqual(write.data[:4], [0x54, 0x45, 0x4C, 0x45])

    def test_build_system_inputs_set_rejects_out_of_range_db(self) -> None:
        with self.assertRaises(ValueError):
            system_edit.build_system_inputs_set_plan(1, "inputLevel", 25)

    def test_build_system_inputs_set_rejects_non_ascii_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "ASCII"):
            system_edit.build_system_inputs_set_plan(1, "name", "TÉLÉ")

    def test_encode_offset_db_round_trip(self) -> None:
        self.assertEqual(system_edit.encode_offset_db(-20), 12)
        self.assertEqual(system_edit.encode_offset_db(20), 52)
        self.assertEqual(system_edit.encode_offset_db(0), 32)

    def test_build_system_common_set_plan_metronome_bpm(self) -> None:
        plan = system_edit.build_system_common_set_plan("metronome-bpm", "120.0")
        write = plan.writes[0]
        self.assertEqual(write.address, live.address_adding(live.SYSTEM_COMMON, 0x09))
        self.assertEqual(write.data, live.nibbles_for(1200))

    def test_build_system_midi_set_plan_rx_channel(self) -> None:
        plan = system_edit.build_system_midi_set_plan("rxChannel", "5")
        write = plan.writes[0]
        self.assertEqual(write.address, live.address_adding(live.SYSTEM_MIDI, 0x00))
        self.assertEqual(write.data, [4])

    def test_build_system_midi_set_plan_tx_rx_alias(self) -> None:
        plan = system_edit.build_system_midi_set_plan("txChannel", "RX")
        self.assertEqual(plan.writes[0].data, [16])

    def test_build_system_effects_set_plan_metronome_level(self) -> None:
        plan = system_edit.build_system_effects_set_plan("metronomeLevel", 75)
        self.assertEqual(plan.writes[0].address, live.address_adding(live.SYSTEM_EFFECTS, 0x02))
        self.assertEqual(plan.writes[0].data, [75])

    def test_build_system_effects_set_plan_phrase_loop_alias(self) -> None:
        plan = system_edit.build_system_effects_set_plan("phraseLoopRecAction", "rec-dub-play")
        self.assertEqual(plan.writes[0].data, [1])

    def test_build_system_pitch_set_plan_reference_pitch(self) -> None:
        plan = system_edit.build_system_pitch_set_plan("referencePitchHz", 440)
        self.assertEqual(plan.writes[0].data, live.nibbles_for(440))

    def test_build_system_setup_efct_set_plan_dir_mon(self) -> None:
        plan = system_edit.build_system_setup_efct_set_plan("mainDirMon", "off")
        self.assertEqual(plan.writes[0].address, live.address_adding(live.SETUP_EFCT, 0x01))
        self.assertEqual(plan.writes[0].data, [0])

    def test_build_system_inout_set_plan_enum_field(self) -> None:
        plan = system_edit.build_system_inout_set_plan("phonesSetting", "MAIN+SUB")
        self.assertEqual(plan.writes[0].address, live.address_adding(live.SYSTEM_IN_OUT, 0x21))
        self.assertEqual(plan.writes[0].data, [2])

    def test_build_system_inout_set_plan_total_ns_threshold(self) -> None:
        plan = system_edit.build_system_inout_set_plan("totalNsThreshold", -6)
        self.assertEqual(plan.writes[0].data, [26])

    def test_build_system_midi_set_rejects_invalid_sync_clock(self) -> None:
        with self.assertRaises(ValueError):
            system_edit.build_system_midi_set_plan("syncClock", "INVALID")


if __name__ == "__main__":
    unittest.main()
