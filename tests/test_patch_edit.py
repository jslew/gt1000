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

    def test_user_slot_remap_is_restricted_to_u03(self):
        plan = patch_edit.build_default_patch_plan("PY DEFAULT")
        remapped = patch_edit.plan_for_user_slot(plan, "U03-1")

        self.assertEqual(remapped.writes[0].address, [0x20, 0x0A, 0x00, 0x00])
        self.assertEqual(remapped.writes[1].address, [0x20, 0x0A, 0x10, 0x68])
        with self.assertRaises(ValueError):
            patch_edit.plan_for_user_slot(plan, "U02-5")

    def test_parameter_set_plan_encodes_nibbles_and_user_slot(self):
        plan = patch_edit.build_parameter_set_plan("delay1", "time", "420", slot="U03-2")

        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x1D, 0x01])
        self.assertEqual(plan.writes[0].data, [0x00, 0x01, 0x0A, 0x04])

    def test_parameter_set_plan_accepts_type_names(self):
        plan = patch_edit.build_parameter_set_plan("dist1", "type", "T-SCREAM")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x13, 0x01])
        self.assertEqual(plan.writes[0].data, [15])


if __name__ == "__main__":
    unittest.main()
