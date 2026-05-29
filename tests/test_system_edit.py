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


if __name__ == "__main__":
    unittest.main()
