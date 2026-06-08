from __future__ import annotations

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
AUDIO_MANUAL_LIVE = os.environ.get("GT1000_AUDIO_MANUAL_LIVE") == "1"
COMPARE_LIVE = os.environ.get("GT1000_COMPARE_LIVE") == "1"

# Repeatability: long tone, measure steady middle only (skip stream settle + capture tail).
REPEATABILITY_TONE_SECONDS = 10.0
REPEATABILITY_TRIM_START_SECONDS = 2.0
REPEATABILITY_TRIM_END_SECONDS = 1.5


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


def silence_skip_message(payload: dict) -> str:
    troubleshooting = payload.get("troubleshooting") or []
    if not isinstance(troubleshooting, list):
        troubleshooting = [str(troubleshooting)]
    return "GT-1000 USB audio stream returned digital silence. " + " ".join(str(item) for item in troubleshooting)


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

    @unittest.skipUnless(
        AUDIO_MANUAL_LIVE,
        "set GT1000_AUDIO_MANUAL_LIVE=1 for manual strum/capture tests",
    )
    def test_audio_probe_reports_signal_while_strumming(self) -> None:
        payload = parse_json_stdout(run_cli("audio", "probe", "--duration", "3"))
        peaks = payload.get("channelPeaks", {})
        if not peaks.get("anySignal"):
            self.skipTest(silence_skip_message(payload))
        main = peaks.get("channelMetrics", [])[:2]
        self.assertTrue(
            any(item.get("peakDbfs") is not None for item in main),
            "expected level on USB main channels 1-2; strum guitar during the probe window",
        )

    @unittest.skipUnless(
        AUDIO_MANUAL_LIVE,
        "set GT1000_AUDIO_MANUAL_LIVE=1 for manual strum/capture tests",
    )
    def test_record_dry_main_bus_while_strumming(self) -> None:
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
            if wet.get("rmsDbfs") is None:
                self.skipTest(silence_skip_message(payload))
            self.assertIsNotNone(wet.get("rmsDbfs"))
            assert wet["rmsDbfs"] is not None
            if wet["rmsDbfs"] <= -96.0:
                self.skipTest(
                    f"GT-1000 USB main capture was below usable signal threshold "
                    f"({wet['rmsDbfs']:.1f} dBFS); strum during the capture window."
                )

    def test_generated_tone_simulates_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = "simulated-record"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            generated = parse_json_stdout(
                run_cli(
                    "audio",
                    "generate-tone",
                    "--session",
                    session,
                    "--duration",
                    "2",
                    "--frequency",
                    "440",
                    "--amplitude",
                    "0.25",
                    env=env,
                )
            )
            self.assertEqual(generated["id"], "audioGenerateTone")
            self.assertIsNotNone(generated["dryMetrics"]["rmsDbfs"])
            assert generated["dryMetrics"]["rmsDbfs"] is not None
            self.assertGreater(generated["dryMetrics"]["rmsDbfs"], -24.0)

            dry_path = Path(generated["dryPath"])
            self.assertTrue(dry_path.is_file())
            analyzed = parse_json_stdout(run_cli("audio", "analyze", str(dry_path), env=env))
            self.assertEqual(analyzed["id"], "audioAnalyze")
            self.assertEqual(analyzed["file"]["channels"], 2)
            self.assertAlmostEqual(
                generated["dryMetrics"]["rmsDbfs"],
                analyzed["file"]["rmsDbfs"],
                delta=0.1,
            )
            profile_path = Path(tmp) / session / "reference-profile.json"
            reference = parse_json_stdout(
                run_cli(
                    "audio",
                    "reference",
                    "analyze",
                    str(dry_path),
                    "--output",
                    str(profile_path),
                    env=env,
                )
            )
            self.assertEqual(reference["id"], "audioReferenceAnalyze")
            self.assertTrue(profile_path.is_file())
            plan = parse_json_stdout(
                run_cli(
                    "audio",
                    "reference",
                    "plan",
                    str(profile_path),
                    "--session",
                    session,
                    "--max-candidates",
                    "2",
                    env=env,
                )
            )
            self.assertEqual(plan["id"], "audioReferencePlan")
            self.assertEqual(plan["candidateCount"], 2)
            reference_run = parse_json_stdout(
                run_cli(
                    "audio",
                    "reference",
                    "run",
                    str(profile_path),
                    "--session",
                    session,
                    "--max-candidates",
                    "1",
                    "--midi-timeout",
                    "20",
                    env=env,
                )
            )
            self.assertEqual(reference_run["id"], "audioReferenceRun")
            self.assertEqual(reference_run["candidateCount"], 1)
            self.assertEqual(len(reference_run["ranked"]), 2)
            self.assertIn("restoreResult", reference_run["renders"][1])
            match = parse_json_stdout(run_cli("audio", "match-reference", str(profile_path), str(dry_path), env=env))
            self.assertEqual(match["id"], "audioMatchReference")
            self.assertEqual(match["best"]["path"], str(dry_path))

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
            if wet.get("rmsDbfs") is None:
                self.skipTest(silence_skip_message(reamp))
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

    @unittest.skipUnless(COMPARE_LIVE, "set GT1000_COMPARE_LIVE=1 for divider A/B live test (slow; many MIDI+audio steps)")
    def test_compare_branches_on_current_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = "live-div1"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            chain = parse_json_stdout(run_cli("patch", "chain", "--live", "--timeout", "15", env=env))
            summary = str(chain.get("signalChainSummary", ""))
            if "DIVIDER 1" not in summary and "DIVIDER 2" not in summary and "DIVIDER 3" not in summary:
                self.skipTest(f"current temporary patch has no divider in chain: {summary}")
            divider = "divider1" if "DIVIDER 1" in summary else ("divider2" if "DIVIDER 2" in summary else "divider3")
            parse_json_stdout(run_cli("audio", "generate-tone", "--session", session, "--duration", "2", env=env))
            parse_json_stdout(run_cli("audio", "prepare-reamp", "--midi-timeout", "15", env=env))
            time.sleep(1.0)
            compare = run_cli(
                "audio",
                "compare-branches",
                "--session",
                session,
                "--divider",
                divider,
                "--midi-timeout",
                "25",
                "--no-verify",
                "--no-prepare-usb",
                env=env,
            )
            combined = f"{compare.stderr or ''}\n{compare.stdout or ''}"
            if compare.returncode != 0:
                if "MIDI destination" in combined or "does not appear" in combined or "single mode" in combined:
                    self.skipTest(f"compare-branches not runnable on current hardware/patch: {combined.strip()[:200]}")
            result = parse_json_stdout(compare)
            self.assertEqual(result["id"], "audioCompareBranches")
            delta = result["comparison"].get("deltaRmsDbBranchBVsA")
            self.assertIsNotNone(delta)
            self.assertIn(result["hypothesis"]["status"], {"balanced", "branchB_quieter", "branchB_louder", "unknown"})

    def test_session_render_repeatability(self) -> None:
        from tools.gt1000.audio_lab.metrics import analyze_file_trimmed

        with tempfile.TemporaryDirectory() as tmp:
            session = "live-session"
            env = {**os.environ, "GT1000_SESSION_DIR": tmp}
            parse_json_stdout(run_cli("audio", "session", "init", "--session", session, env=env))
            parse_json_stdout(
                run_cli(
                    "audio",
                    "generate-tone",
                    "--session",
                    session,
                    "--duration",
                    str(REPEATABILITY_TONE_SECONDS),
                    env=env,
                )
            )
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
            wet_a = analyze_file_trimmed(
                Path(first["wetPath"]),
                trim_start_seconds=REPEATABILITY_TRIM_START_SECONDS,
                trim_end_seconds=REPEATABILITY_TRIM_END_SECONDS,
            )
            wet_b = analyze_file_trimmed(
                Path(second["wetPath"]),
                trim_start_seconds=REPEATABILITY_TRIM_START_SECONDS,
                trim_end_seconds=REPEATABILITY_TRIM_END_SECONDS,
            )
            rms_a = wet_a["rmsDbfs"]
            rms_b = wet_b["rmsDbfs"]
            if rms_a is None or rms_b is None:
                self.skipTest(
                    "GT-1000 USB reamp returned digital silence; cannot evaluate render repeatability."
                )
            self.assertIsNotNone(rms_a)
            self.assertIsNotNone(rms_b)
            assert rms_a is not None and rms_b is not None
            self.assertLess(
                abs(rms_a - rms_b),
                0.5,
                (
                    "trimmed steady-state RMS should match between renders "
                    f"(trim {REPEATABILITY_TRIM_START_SECONDS}s start, "
                    f"{REPEATABILITY_TRIM_END_SECONDS}s end)"
                ),
            )


if __name__ == "__main__":
    unittest.main()
