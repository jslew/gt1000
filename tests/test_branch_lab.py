import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.gt1000.audio_lab import branch_lab


class BranchLabTests(unittest.TestCase):
    def test_normalize_divider_aliases(self) -> None:
        self.assertEqual(branch_lab.normalize_divider_id("div1"), "divider1")

    def test_build_channel_select_plan(self) -> None:
        plan = branch_lab.build_channel_select_plan("divider1", 1)
        self.assertEqual(plan.writes[0].data, [1])

    def test_level_step_for_delta(self) -> None:
        self.assertEqual(branch_lab.level_step_for_delta(0.2), 0)
        self.assertEqual(branch_lab.level_step_for_delta(3.0), 5)

    def test_branch_balance_hypothesis(self) -> None:
        quiet_b = branch_lab._branch_balance_hypothesis(-4.0)
        self.assertEqual(quiet_b["status"], "branchB_quieter")
        self.assertEqual(quiet_b["suggestedParam"], "auto")

    def test_divider_present_in_snapshot(self) -> None:
        snapshot = {"signalChainElements": [{"rawValue": 35, "displayName": "DIVIDER 1"}]}
        self.assertTrue(branch_lab.divider_present_in_snapshot(snapshot, "divider1"))

    def test_parse_match_param(self) -> None:
        self.assertEqual(branch_lab.parse_match_param("auto", "divider1"), ("auto", None, None))
        self.assertEqual(branch_lab.parse_match_param("levelB", "divider1"), ("divider", "divider1", "levelB"))
        self.assertEqual(branch_lab.parse_match_param("dist1.level", "divider1"), ("block", "dist1", "level"))

    def test_blocks_on_divider_branch(self) -> None:
        snapshot = {
            "blocks": [
                {"id": "divider1", "chainElementValue": 35},
                {"id": "preamp1", "chainElementValue": 3},
                {"id": "branchSplit1", "chainElementValue": 36},
                {"id": "dist1", "chainElementValue": 1},
                {"id": "mixer1", "chainElementValue": 37},
            ],
            "signalChainElements": [
                {"position": 4, "rawValue": 35, "displayName": "DIVIDER 1"},
                {"position": 5, "rawValue": 3, "displayName": "AIRD PREAMP 1"},
                {"position": 9, "rawValue": 36, "displayName": "BRANCH SPLIT1"},
                {"position": 10, "rawValue": 1, "displayName": "DISTORTION 1"},
                {"position": 16, "rawValue": 37, "displayName": "MIXER 1"},
            ],
        }
        self.assertEqual(branch_lab.blocks_on_divider_branch(snapshot, "divider1", 0), ["preamp1"])
        self.assertEqual(branch_lab.blocks_on_divider_branch(snapshot, "divider1", 1), ["dist1"])

    def test_compare_branches_mocked(self) -> None:
        snapshot = {
            "signalChainElements": [{"rawValue": 35, "displayName": "DIVIDER 1"}],
            "blocks": [],
        }
        chain = {"elements": [], "reachability": {"unreachableElements": []}}
        divider_bytes = [0, 0, 0, 0, 0, 0, 50, 60, 0, 0]

        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp)
            (session_dir / "dry.wav").write_bytes(b"RIFF")
            with mock.patch.object(branch_lab, "resolve_session_dir", return_value=session_dir), mock.patch.object(
                branch_lab, "read_branch_lab_context", return_value=(snapshot, divider_bytes)
            ), mock.patch("tools.gt1000.agent_cli.chain_from_full", return_value=chain), mock.patch.object(
                branch_lab, "prepare_usb_reamp", return_value={}), mock.patch.object(
                branch_lab, "apply_plan", return_value={"verified": True}
            ), mock.patch.object(
                branch_lab,
                "_render_branch",
                side_effect=[
                    {"label": "divider1-branch-A", "wetPath": "/tmp/a.wav", "wetMetrics": {"rmsDbfs": -20.0}},
                    {"label": "divider1-branch-B", "wetPath": "/tmp/b.wav", "wetMetrics": {"rmsDbfs": -24.0}},
                ],
            ), mock.patch.object(branch_lab, "restore_divider_data", return_value={"verified": True}):
                result = branch_lab.compare_branches("lab", "divider1", midi_timeout=1.0, verify_writes=False)

        self.assertEqual(result["id"], "audioCompareBranches")
        self.assertAlmostEqual(result["comparison"]["deltaRmsDbBranchBVsA"], -4.0)


if __name__ == "__main__":
    unittest.main()
