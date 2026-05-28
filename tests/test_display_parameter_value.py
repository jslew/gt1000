import sys
import unittest

sys.dont_write_bytecode = True

from skills.gt1000.tools.gt1000 import agent_cli, live


class DisplayParameterValueTests(unittest.TestCase):
    def test_byte_parameters_get_numeric_display(self) -> None:
        drive = next(parameter for parameter in live.DISTORTION_PARAMETERS if parameter.id == "drive")
        self.assertEqual(live.display_parameter_value(drive, 45), "45")
        self.assertEqual(live.display_parameter_value(drive, 0), "0")

    def test_dist_block_from_bytes_includes_knob_values(self) -> None:
        definition = agent_cli.block_definition_for_id("dist1")
        # ON, X-DIST (type index 12), drive=50, tone=60, level=70, bottom=10, directMix=0, solo off, soloLevel=100
        data = [1, 12, 50, 60, 70, 10, 0, 0, 100]
        snapshot = {"signalChainElements": [{"rawValue": definition.chain_element_value}], "blocks": []}
        block = live.block_from_definition(snapshot, definition, data)
        by_id = {parameter["id"]: parameter for parameter in block["parameters"]}
        self.assertEqual(by_id["drive"]["displayValue"], "50")
        self.assertEqual(by_id["tone"]["displayValue"], "60")
        self.assertEqual(by_id["level"]["displayValue"], "70")
        self.assertEqual(by_id["type"]["displayValue"], "X-DIST")


if __name__ == "__main__":
    unittest.main()
