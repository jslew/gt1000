import unittest

from tools.gt1000 import live, patch_edit


class PatchEditTests(unittest.TestCase):
    def test_default_plan_builds_minimal_no_branch_chain_and_off_writes(self):
        plan = patch_edit.build_default_patch_plan("PY DEFAULT")
        chain = next(write for write in plan.writes if write.label == "Minimal no-branch chain")

        self.assertEqual(chain.address, [0x10, 0x00, 0x10, 0x68])
        self.assertEqual(chain.data[:5], [0, 34, 33, 47, 48])
        self.assertEqual(len(chain.data), 49)
        self.assertEqual(len(set(chain.data)), 49)
        self.assertEqual(chain.data[-1], 44)
        self.assertIn(
            live.PatchWrite("CTL1 direct function off", [0x10, 0x00, 0x00, 0x31], [0, 0]),
            plan.writes,
        )
        self.assertIn(live.PatchWrite("dist1 switch off", [0x10, 0x00, 0x13, 0x00], [0]), plan.writes)
        self.assertIn(live.PatchWrite("Assign 16 disabled", [0x10, 0x00, 0x0A, 0x40], patch_edit.DISABLED_ASSIGN_DATA), plan.writes)

    def test_4cm_template_chain_and_ctl1_direct_mapping(self):
        plan = patch_edit.build_4cm_template_plan("PY 4CM CTL1")
        chain = next(write for write in plan.writes if write.label == "4CM CTL1 divider template chain")

        self.assertEqual(chain.data[:12], [0, 35, 14, 36, 1, 15, 37, 24, 34, 33, 47, 48])
        self.assertEqual(len(set(chain.data)), 49)
        self.assertEqual(chain.data[-1], 44)
        self.assertIn(
            live.PatchWrite(
                "CTL1 direct function: DIVIDER 1 channel select",
                [0x10, 0x00, 0x00, 0x31],
                [47, 0],
            ),
            plan.writes,
        )
        self.assertIn(
            live.PatchWrite("Distortion 1 T-SCREAM path on", [0x10, 0x00, 0x13, 0x00], [1, 15, 45, 50, 55, 50, 0, 0, 50]),
            plan.writes,
        )
        self.assertIn(
            live.PatchWrite("Send/Return 1 4CM loop on", [0x10, 0x00, 0x10, 0x35], [1, 0, 6, 4, 6, 4, 0]),
            plan.writes,
        )

    def test_assign_builder_matches_known_tuner_bytes(self):
        data = patch_edit.tuner_assign_data()

        self.assertEqual(len(data), 44)
        self.assertEqual(data[:5], [0x01, 0x00, 0x03, 0x0D, 0x0B])
        self.assertEqual(data[5:9], [0x08, 0x00, 0x00, 0x00])
        self.assertEqual(data[9:13], [0x08, 0x00, 0x00, 0x01])
        self.assertEqual(data[13], 0x45)
        self.assertEqual(data[14], 0x01)
        self.assertEqual(data[20:24], [0x00, 0x00, 0x00, 0x00])
        self.assertEqual(data[24:28], [0x00, 0x00, 0x07, 0x0F])
        self.assertEqual(data[29], 0x50)

    def test_divider_channel_select_assign_uses_tested_target_table(self):
        data = patch_edit.divider1_channel_select_assign_data()

        self.assertEqual(data[1:5], [0x00, 0x03, 0x0A, 0x04])
        self.assertEqual(data[5:13], [0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x01])
        self.assertEqual(data[13], 0x08)
        self.assertEqual(data[14], 0x00)

    def test_user_slot_remap_accepts_any_valid_user_slot(self):
        plan = patch_edit.build_default_patch_plan("PY DEFAULT")
        remapped = patch_edit.plan_for_user_slot(plan, "U03-1")

        self.assertEqual(remapped.writes[0].address, [0x20, 0x0A, 0x00, 0x00])
        self.assertEqual(remapped.writes[1].address, [0x20, 0x0A, 0x10, 0x68])

        u10 = patch_edit.plan_for_user_slot(plan, "U10-1")
        self.assertEqual(u10.writes[0].address, [0x20, 0x2D, 0x00, 0x00])

        u50 = patch_edit.plan_for_user_slot(plan, "U50-5")
        self.assertEqual(u50.writes[0].address, [0x21, 0x79, 0x00, 0x00])

        with self.assertRaises(ValueError):
            patch_edit.plan_for_user_slot(plan, "U51-1")

    def test_parameter_set_plan_encodes_nibbles_and_user_slot(self):
        plan = patch_edit.build_parameter_set_plan("delay1", "time", "420", slot="U03-2")

        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x1D, 0x01])
        self.assertEqual(plan.writes[0].data, [0x00, 0x01, 0x0A, 0x04])

    def test_parameter_set_plan_accepts_type_names(self):
        plan = patch_edit.build_parameter_set_plan("dist1", "type", "T-SCREAM")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x13, 0x01])
        self.assertEqual(plan.writes[0].data, [15])

    def test_chain_move_plan_reorders_full_validated_chain(self):
        chain = list(patch_edit.CANONICAL_FULL_CHAIN)
        plan = patch_edit.build_chain_move_plan(chain, 15, before=14)

        self.assertEqual(plan.id, "move:chain:15:before:14")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x68])
        data = plan.writes[0].data
        self.assertEqual(len(data), 49)
        self.assertEqual(set(data), set(patch_edit.CANONICAL_FULL_CHAIN))
        self.assertLess(data.index(15), data.index(14))

    def test_chain_move_plan_validates_reference_and_user_slot(self):
        chain = list(patch_edit.CANONICAL_FULL_CHAIN)
        plan = patch_edit.build_chain_move_plan(chain, 15, after=14, slot="U03-2")

        self.assertEqual(plan.id, "move:chain:15:after:14:U03-2")
        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x10, 0x68])
        self.assertGreater(plan.writes[0].data.index(15), plan.writes[0].data.index(14))

        with self.assertRaises(ValueError):
            patch_edit.build_chain_move_plan(chain[:-1], 15, before=14)
        with self.assertRaises(ValueError):
            patch_edit.build_chain_move_plan(chain, 15, before=15)

    def test_bpm_set_plan_encodes_tenths_and_user_slot(self):
        plan = patch_edit.build_bpm_set_plan("120.0")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x61])
        self.assertEqual(plan.writes[0].data, [0x00, 0x04, 0x0B, 0x00])

        remapped = patch_edit.build_bpm_set_plan("99.5", slot="U03-2")
        self.assertEqual(remapped.writes[0].address, [0x20, 0x0B, 0x10, 0x61])
        self.assertEqual(remapped.writes[0].data, [0x00, 0x03, 0x0E, 0x03])

    def test_bpm_set_plan_validates_documented_range(self):
        self.assertEqual(patch_edit.parse_bpm_tenths("40"), 400)
        self.assertEqual(patch_edit.parse_bpm_tenths("250.0"), 2500)

        for value in ["39.9", "250.1", "120.01", "fast"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    patch_edit.build_bpm_set_plan(value)

    def test_tuner_assign_plan_targets_assign_16_and_user_slot(self):
        plan = patch_edit.build_tuner_assign_plan()

        self.assertEqual(plan.id, "set:tunerAssign")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x0A, 0x40])
        self.assertEqual(plan.writes[0].data, patch_edit.tuner_assign_data())

        remapped = patch_edit.build_tuner_assign_plan(slot="U03-2")
        self.assertEqual(remapped.writes[0].address, [0x20, 0x0B, 0x0A, 0x40])
        self.assertEqual(remapped.writes[0].data, patch_edit.tuner_assign_data())

    def test_assign_cc_plan_encodes_source_and_offset_target_range(self):
        plan = patch_edit.build_assign_cc_plan(
            3,
            target=158,
            target_min=0,
            target_max=1,
            source_cc=80,
            mode="moment",
        )

        data = plan.writes[0].data
        self.assertEqual(plan.id, "set:assign3:cc80:target158")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x04, 0x00])
        self.assertEqual(data[0], 1)
        self.assertEqual(data[1:5], live.nibbles_for(158))
        self.assertEqual(data[5:9], live.nibbles_for(32768))
        self.assertEqual(data[9:13], live.nibbles_for(32769))
        self.assertEqual(data[13], 69)
        self.assertEqual(data[14], 1)
        self.assertEqual(data[20:28], live.nibbles_for(0) + live.nibbles_for(127))
        self.assertEqual(data[29], 80)

    def test_assign_cc_plan_validates_supported_cc_sources(self):
        self.assertEqual(patch_edit.assign_source_for_cc(1), 22)
        self.assertEqual(patch_edit.assign_source_for_cc(31), 52)
        self.assertEqual(patch_edit.assign_source_for_cc(64), 53)
        self.assertEqual(patch_edit.assign_source_for_cc(95), 84)

        with self.assertRaises(ValueError):
            patch_edit.build_assign_cc_plan(1, target=158, target_min=0, target_max=1, source_cc=32, mode="moment")


if __name__ == "__main__":
    unittest.main()
