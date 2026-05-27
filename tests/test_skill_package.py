import os
import stat
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "gt1000"


class SkillPackageTests(unittest.TestCase):
    def test_skill_package_has_required_files(self):
        required = [
            "SKILL.md",
            "agents/openai.yaml",
            "scripts/gt1000-agent",
            "scripts/fetch-current-manuals.sh",
            "tools/__init__.py",
            "tools/gt1000/__init__.py",
            "tools/gt1000/agent_cli.py",
            "tools/gt1000/live.py",
            "tools/gt1000/patch_edit.py",
            "__init__.py",
            "references/user-profile-onboarding.md",
            "references/gt1000-wiki/README.md",
            "references/midi-reference/README.md",
            "references/midi-reference/cli-usage.md",
        ]

        for relative_path in required:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((SKILL / relative_path).is_file())

    def test_skill_scripts_are_executable(self):
        for relative_path in ["scripts/gt1000-agent", "scripts/fetch-current-manuals.sh"]:
            with self.subTest(relative_path=relative_path):
                mode = (SKILL / relative_path).stat().st_mode
                self.assertTrue(mode & stat.S_IXUSR)

    def test_skill_wrapper_runs_bundled_cli(self):
        result = subprocess.run(
            [str(SKILL / "scripts" / "gt1000-agent"), "--help"],
            cwd=SKILL,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Agent-facing GT-1000 patch inspection CLI", result.stdout)

    def test_skill_package_does_not_include_generated_python_cache(self):
        generated = [
            path.relative_to(SKILL)
            for path in SKILL.rglob("*")
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}
        ]

        self.assertEqual(generated, [])

    def test_skill_package_has_no_repo_local_path_references(self):
        forbidden = [
            "/Users/",
            "docs/gt1000-wiki",
            "docs/midi-reference",
            "GT1000AppPackage",
        ]
        text_files = [
            path
            for path in SKILL.rglob("*")
            if path.is_file() and path.suffix in {"", ".md", ".py", ".sh", ".yaml", ".yml"}
        ]

        for path in text_files:
            content = path.read_text()
            for pattern in forbidden:
                with self.subTest(path=path.relative_to(SKILL), pattern=pattern):
                    self.assertNotIn(pattern, content)

    def test_repo_local_tools_are_compatibility_wrappers(self):
        for relative_path in ["agent_cli.py", "live.py", "patch_edit.py"]:
            with self.subTest(relative_path=relative_path):
                content = (ROOT / "tools" / "gt1000" / relative_path).read_text()
                self.assertIn("skills.gt1000.tools.gt1000", content)

    def test_repo_local_docs_are_compatibility_pointers(self):
        for directory in [ROOT / "docs" / "gt1000-wiki", ROOT / "docs" / "midi-reference"]:
            for path in directory.glob("*.md"):
                with self.subTest(path=os.fspath(path.relative_to(ROOT))):
                    content = path.read_text()
                    self.assertIn("Canonical content lives in `skills/gt1000/references/", content)


if __name__ == "__main__":
    unittest.main()
