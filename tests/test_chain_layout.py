import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "split_patch_chain.json"


class ChainLayoutLogicTests(unittest.TestCase):
    """Mirror of frontend split detection (divider → path A → branch → path B → mixer)."""

    DIVIDER_RAW = {35, 38, 41}
    BRANCH_RAW = {36, 39, 42}
    MIXER_RAW = {37, 40, 43}

    def _path_split(self, elements: list[dict]) -> tuple[list[dict], list[dict]]:
        divider_index = next(i for i, item in enumerate(elements) if item["rawValue"] in self.DIVIDER_RAW)
        index = divider_index + 1
        path_a: list[dict] = []
        while index < len(elements):
            raw = elements[index]["rawValue"]
            if raw in self.BRANCH_RAW or raw in self.MIXER_RAW or raw in self.DIVIDER_RAW:
                break
            path_a.append(elements[index])
            index += 1
        if index < len(elements) and elements[index]["rawValue"] in self.BRANCH_RAW:
            index += 1
        path_b: list[dict] = []
        while index < len(elements):
            raw = elements[index]["rawValue"]
            if raw in self.MIXER_RAW or raw in self.DIVIDER_RAW:
                break
            path_b.append(elements[index])
            index += 1
        return path_a, path_b

    def test_active_prefix_split_paths_match_tone_studio_order(self) -> None:
        from skills.gt1000.tools.gt1000 import agent_cli, live, patch_edit

        snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw_values = [item["rawValue"] for item in snapshot["signalChainElements"]]
        padded = patch_edit.valid_chain(raw_values)
        snapshot["signalChainElements"] = [
            {
                "id": f"chain-{index + 1}",
                "position": index + 1,
                "rawValue": value,
                "displayName": live.chain_element_name(value),
                "isReserved": live.chain_element_name(value) == "(RESERVED)",
                "isOutput": live.chain_element_name(value) in {"SUB OUT L", "SUB OUT R", "MAIN OUT L", "MAIN OUT R"},
            }
            for index, value in enumerate(padded)
        ]

        chain = agent_cli.chain_from_full(snapshot)
        ordered = chain["signalOrderElements"]
        self.assertEqual([item["rawValue"] for item in ordered], raw_values)

        path_a, path_b = self._path_split(ordered)
        self.assertEqual(path_a[0]["displayName"], "AIRD PREAMP 1")
        self.assertEqual(path_b[0]["displayName"], "DISTORTION 1")

    def test_active_chain_prefix_strips_canonical_padding(self) -> None:
        from skills.gt1000.tools.gt1000 import patch_edit

        prefix = [
            0,
            35,
            14,
            36,
            1,
            15,
            37,
            24,
            patch_edit.BYPASS_MAIN_R,
            patch_edit.BYPASS_MAIN_L,
            patch_edit.MAIN_OUT_L,
            patch_edit.MAIN_OUT_R,
        ]
        stored = patch_edit.valid_chain(prefix)
        self.assertEqual(patch_edit.active_chain_prefix(stored), prefix)

    def test_chain_from_full_includes_raw_value_and_signal_order(self) -> None:
        from skills.gt1000.tools.gt1000 import agent_cli

        snapshot = json.loads((ROOT / "tests" / "fixtures" / "full_patch.json").read_text(encoding="utf-8"))
        chain = agent_cli.chain_from_full(snapshot)
        self.assertIn("rawValue", chain["elements"][0])
        self.assertIn("signalOrderElements", chain)
        self.assertGreaterEqual(len(chain["signalOrderElements"]), 1)


if __name__ == "__main__":
    unittest.main()
