import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_CLI = ROOT / "skills" / "gt1000" / "scripts" / "gt1000-agent"
AUDIO_LIVE = os.environ.get("GT1000_AUDIO_LIVE") == "1"


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SKILL_CLI), "--pretty", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@unittest.skipUnless(AUDIO_LIVE, "set GT1000_AUDIO_LIVE=1 to run USB audio live tests")
class LiveAudioLabTests(unittest.TestCase):
    def test_sprint_a_generate_reamp_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = "live-sprint-a"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            ports = run_cli("audio", "ports", env=env)
            self.assertEqual(ports.returncode, 0, ports.stderr)
            self.assertIn("gt1000Inputs", ports.stdout)

            tone = run_cli(
                "audio",
                "generate-tone",
                "--session",
                session,
                "--duration",
                "2",
                "--frequency",
                "440",
                env=env,
            )
            self.assertEqual(tone.returncode, 0, tone.stderr)

            reamp = run_cli("audio", "reamp", "--session", session, env=env)
            self.assertEqual(reamp.returncode, 0, reamp.stderr)

            session_dir = Path(tmp) / session
            dry = session_dir / "dry.wav"
            wet = session_dir / "renders" / "reamp-main.wav"
            self.assertTrue(dry.is_file())
            self.assertTrue(wet.is_file())

            analyze = run_cli("audio", "analyze", str(dry), str(wet), env=env)
            self.assertEqual(analyze.returncode, 0, analyze.stderr)
            self.assertIn("rmsDbfs", analyze.stdout)


if __name__ == "__main__":
    unittest.main()
