import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_CLI = ROOT / "skills" / "gt1000" / "scripts" / "gt1000-agent"
AUDIO_LIVE = os.environ.get("GT1000_AUDIO_LIVE") == "1"


def audio_python() -> str:
    override = os.environ.get("GT1000_AUDIO_PYTHON", "").strip()
    if override:
        return override
    return sys.executable


def require_sounddevice() -> None:
    try:
        import sounddevice  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as error:
        raise unittest.SkipTest(
            "sounddevice and numpy required for live audio tests: "
            "pip install -r skills/gt1000/requirements-audio.txt"
        ) from error


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    python = audio_python()
    agent_cli = ROOT / "skills" / "gt1000" / "tools" / "gt1000" / "agent_cli.py"
    merged = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "skills" / "gt1000" / "tools"), str(ROOT)]),
    }
    if env:
        merged.update(env)
    return subprocess.run(
        [python, "-B", str(agent_cli), "--pretty", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def parse_json_stdout(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(f"CLI failed ({result.returncode}): {result.stderr or result.stdout}")
    return json.loads(result.stdout)


@unittest.skipUnless(AUDIO_LIVE, "set GT1000_AUDIO_LIVE=1 to run USB audio live tests")
class LiveAudioLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_sounddevice()

    def test_audio_ports_lists_gt1000_coreaudio(self) -> None:
        payload = parse_json_stdout(run_cli("audio", "ports"))
        self.assertEqual(payload.get("audioBackend"), "coreaudio")
        self.assertTrue(payload.get("gt1000Inputs"))
        self.assertTrue(payload.get("gt1000Outputs"))
        self.assertEqual(payload["recommended"]["audioBackend"], "coreaudio")

    def test_audio_probe_reports_signal(self) -> None:
        payload = parse_json_stdout(run_cli("audio", "probe", "--duration", "3"))
        peaks = payload.get("channelPeaks", {})
        self.assertTrue(peaks.get("anySignal"), peaks.get("troubleshooting"))
        main = peaks.get("channelMetrics", [])[:2]
        self.assertTrue(
            any(item.get("peakDbfs") is not None for item in main),
            "expected level on USB main channels 1-2; strum guitar during the probe window",
        )

    def test_record_dry_main_bus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            payload = parse_json_stdout(
                run_cli(
                    "audio",
                    "record-dry",
                    "--session",
                    "live-record",
                    "--bus",
                    "main",
                    "--duration",
                    "3",
                    env=env,
                )
            )
            wet = payload.get("wetMetrics", {})
            self.assertIsNotNone(wet.get("rmsDbfs"))
            assert wet["rmsDbfs"] is not None
            self.assertGreater(wet["rmsDbfs"], -90.0)

    def test_generate_reamp_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = "live-reamp"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            parse_json_stdout(run_cli("audio", "generate-tone", "--session", session, "--duration", "2", env=env))
            prepare = run_cli("audio", "prepare-reamp", "--midi-timeout", "8", env=env)
            if prepare.returncode == 0:
                prepared = json.loads(prepare.stdout)
                self.assertEqual(prepared.get("after", {}).get("decoded", {}).get("mainDirMon"), "OFF")
            reamp = parse_json_stdout(run_cli("audio", "reamp", "--session", session, env=env))
            self.assertEqual(reamp.get("captureBackend"), "coreaudio")
            self.assertEqual(reamp.get("playbackBackend"), "coreaudio")
            wet = reamp.get("wetMetrics", {})
            self.assertIsNotNone(wet.get("rmsDbfs"))
            session_dir = Path(tmp) / session
            self.assertTrue((session_dir / "dry.wav").is_file())
            self.assertTrue((session_dir / "renders" / "reamp-main.wav").is_file())
            analyze = parse_json_stdout(
                run_cli(
                    "audio",
                    "analyze",
                    str(session_dir / "dry.wav"),
                    str(session_dir / "renders" / "reamp-main.wav"),
                    env=env,
                )
            )
            self.assertEqual(analyze["id"], "audioAnalyze")
            self.assertIsNotNone(analyze["files"][1].get("rmsDbfs"))

    def test_session_init_live_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = "live-init"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            payload = parse_json_stdout(
                run_cli(
                    "audio",
                    "session",
                    "init",
                    "--session",
                    session,
                    "--live",
                    "--midi-timeout",
                    "20",
                    env=env,
                )
            )
            self.assertEqual(payload["id"], "audioSessionInit")
            self.assertIn("deviceSnapshots", payload)
            session_dir = Path(tmp) / session
            for name in ("systemInOut", "setupEfct", "patch"):
                path = session_dir / "deviceSnapshots" / f"{name}.json"
                self.assertTrue(path.is_file(), f"missing snapshot {path}")
                body = json.loads(path.read_text(encoding="utf-8"))
                if name == "patch":
                    self.assertIn("chain", body)
                else:
                    self.assertIn("decoded", body)

    def test_system_inout_set_roundtrip(self) -> None:
        inout = parse_json_stdout(run_cli("system", "inout", "--live", "--timeout", "15"))
        value = inout["decoded"]["usbDryOut"]
        self.assertIsNotNone(value)
        assert value is not None
        result = parse_json_stdout(
            run_cli(
                "system",
                "inout-set",
                "usbDryOut",
                str(value),
                "--live",
                "--verify",
                "--timeout",
                "20",
            )
        )
        self.assertTrue(result.get("verified"))

    def test_session_render_repeatability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = "live-session"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            parse_json_stdout(run_cli("audio", "session", "init", "--session", session, env=env))
            parse_json_stdout(run_cli("audio", "generate-tone", "--session", session, "--duration", "2", env=env))
            parse_json_stdout(run_cli("audio", "prepare-reamp", "--midi-timeout", "15", env=env))
            time.sleep(1.0)
            render_args = [
                "audio",
                "session",
                "render",
                "--session",
                session,
                "--no-prepare-usb",
                "--no-patch-snapshot",
                "--midi-timeout",
                "20",
            ]
            first = parse_json_stdout(run_cli(*render_args, "--label", "a", env=env))
            time.sleep(0.5)
            second = parse_json_stdout(run_cli(*render_args, "--label", "b", env=env))
            rms_a = first["wetMetrics"]["rmsDbfs"]
            rms_b = second["wetMetrics"]["rmsDbfs"]
            self.assertIsNotNone(rms_a)
            self.assertIsNotNone(rms_b)
            assert rms_a is not None and rms_b is not None
            self.assertLess(abs(rms_a - rms_b), 0.5, "same patch/dry should be within 0.5 dB RMS")


if __name__ == "__main__":
    unittest.main()
