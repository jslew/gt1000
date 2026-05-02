import unittest
from pathlib import Path

from tools.gt1000 import agent_cli


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "full_patch.json"


class AgentCLITests(unittest.TestCase):
    def test_offline_overview(self):
        snapshot = agent_cli.load_json(FIXTURE)

        overview = agent_cli.overview_from_full(snapshot)

        self.assertEqual(overview["patchName"], "TEST PATCH")
        self.assertEqual(overview["signalChainElementCount"], 4)
        self.assertEqual(overview["detailBlockCount"], 3)

    def test_offline_chain_links_detail_blocks(self):
        snapshot = agent_cli.load_json(FIXTURE)

        chain = agent_cli.chain_from_full(snapshot)

        self.assertEqual(chain["signalChainSummary"], "AIRD PREAMP 1 -> DELAY 1 -> CHORUS -> MAIN OUT L")
        self.assertEqual(chain["descriptionSignalChainSummary"], "AIRD PREAMP 1 -> CHORUS -> MAIN OUT L")
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


if __name__ == "__main__":
    unittest.main()
