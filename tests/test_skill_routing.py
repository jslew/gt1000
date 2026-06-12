"""Prove every skill reference file is registered and reachable from the routing card."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "gt1000"
ROUTING_INDEX = SKILL / "references" / "skill-routing-index.md"
SKILL_MD = SKILL / "SKILL.md"

# Routing card should stay small on activation (Cursor guidance: under ~500 lines).
MAX_ROUTING_CARD_LINES = 200

REF_PATH_RE = re.compile(r"`(references/[^`*]+\.md)`")


def _reference_markdown_files() -> set[str]:
    return {
        path.relative_to(SKILL).as_posix()
        for path in (SKILL / "references").rglob("*.md")
    }


def _paths_in_text(text: str) -> set[str]:
    return set(REF_PATH_RE.findall(text))


def _registry_paths_from_index() -> set[str]:
    text = ROUTING_INDEX.read_text()
    start = text.find("## File registry")
    end = text.find("## Intent routing")
    if start == -1 or end == -1:
        raise AssertionError("skill-routing-index.md missing File registry or Intent routing section")
    return _paths_in_text(text[start:end])


class SkillRoutingTests(unittest.TestCase):
    def test_routing_card_is_compact(self):
        line_count = len(SKILL_MD.read_text().splitlines())
        self.assertLessEqual(
            line_count,
            MAX_ROUTING_CARD_LINES,
            f"SKILL.md routing card is {line_count} lines; keep ≤ {MAX_ROUTING_CARD_LINES}",
        )

    def test_routing_card_links_to_index_and_detail(self):
        text = SKILL_MD.read_text()
        self.assertIn("references/skill-routing-index.md", text)
        self.assertIn("references/skill-detail.md", text)
        self.assertIn("references/skill-audio-setup.md", text)

    def test_file_registry_covers_all_reference_markdown(self):
        all_refs = _reference_markdown_files()
        registered = _registry_paths_from_index()
        missing = sorted(all_refs - registered)
        extra = sorted(registered - all_refs)
        self.assertEqual(missing, [], f"Unregistered reference files: {missing}")
        self.assertEqual(extra, [], f"Registry lists non-existent files: {extra}")

    def test_registry_paths_exist(self):
        for rel in _registry_paths_from_index():
            with self.subTest(path=rel):
                self.assertTrue((SKILL / rel).is_file(), f"missing {rel}")

    def test_intent_table_only_links_registered_files(self):
        text = ROUTING_INDEX.read_text()
        intent_start = text.find("## Intent routing")
        self.assertNotEqual(intent_start, -1)
        intent_paths = _paths_in_text(text[intent_start:])
        registered = _registry_paths_from_index()
        # Intent rows may cite skill-detail by short name; allow bare names used in prose.
        for path in intent_paths:
            with self.subTest(path=path):
                self.assertIn(path, registered)

    def test_skill_detail_links_only_registered_files(self):
        detail = (SKILL / "references" / "skill-detail.md").read_text()
        registered = _registry_paths_from_index()
        for path in _paths_in_text(detail):
            with self.subTest(path=path):
                self.assertIn(
                    path,
                    registered,
                    "skill-detail.md must not introduce orphan reference paths",
                )


if __name__ == "__main__":
    unittest.main()
