import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

from skills.gt1000.tools.gt1000 import agent_cli

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "app" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from gt1000_app.chain_graph import chain_nodes_from_chain_view  # noqa: E402


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "full_patch.json"


class GT1000AppChainTests(unittest.TestCase):
    def test_chain_nodes_from_fixture_snapshot(self) -> None:
        snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))
        chain = agent_cli.chain_from_full(snapshot)
        nodes = chain_nodes_from_chain_view(chain)
        self.assertGreaterEqual(len(nodes), 2)
        labels = [node["label"] for node in nodes]
        self.assertIn("AIRD PREAMP 1", labels)

    def test_description_elements_preferred(self) -> None:
        chain = {
            "elements": [{"id": "a", "displayName": "Hidden", "includeInDescription": False}],
            "descriptionElements": [{"id": "b", "displayName": "Visible", "includeInDescription": True}],
        }
        nodes = chain_nodes_from_chain_view(chain)
        self.assertEqual([node["label"] for node in nodes], ["Visible"])


if __name__ == "__main__":
    unittest.main()
