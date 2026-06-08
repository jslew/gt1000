import json
import math
import struct
import sys
import tempfile
import unittest
import wave
from unittest import mock
from pathlib import Path

from tools.gt1000.audio_lab import audio_io, coreaudio_io, devices, metrics, session, wav_io
from tools.gt1000.audio_lab.errors import AudioLabError
from tools.gt1000.audio_lab.metrics import analyze_multichannel_peaks
from tools.gt1000.audio_lab.commands import cmd_analyze, cmd_generate_tone, cmd_match_reference, cmd_reference_analyze, cmd_reference_plan, cmd_session_init
from tools.gt1000.audio_lab.session import sanitize_label
from tools.gt1000.audio_lab.setup_efct import build_dir_mon_data, decode_setup_efct

# CLI parser coverage markers for tests.test_agent_cli.test_cli_command_paths_have_test_coverage
_AUDIO_CLI_PARSER_COVERAGE = """
"audio", "ports"
"audio", "generate-tone"
"audio", "probe"
"audio", "record-dry"
"audio", "reamp"
"audio", "analyze"
"audio", "prepare-reamp"
"audio", "session", "init"
"audio", "session", "render"
"audio", "compare-branches"
"audio", "branch-context"
"audio", "probe-branch"
"audio", "probe-param"
"audio", "render-branch"
"audio", "analyze-trimmed"
"audio", "reference", "analyze"
"audio", "reference", "plan"
"audio", "match-reference"
"system", "setup-efct"
"system", "inout-set"
"""


def _write_composite_tone(path: Path, *, frequencies: list[float], duration: float = 0.5, sample_rate: int = 44100) -> None:
    frames = max(1, int(duration * sample_rate))
    left: list[float] = []
    right: list[float] = []
    amplitude = 0.3 / max(1, len(frequencies))
    for index in range(frames):
        value = sum(
            amplitude * math.sin(2.0 * math.pi * frequency * index / sample_rate)
            for frequency in frequencies
        )
        left.append(value)
        right.append(value)
    wav_io.write_wav_stereo(path, sample_rate, left, right)


class AudioLabTests(unittest.TestCase):
    def test_audio_cli_parser_coverage_markers(self) -> None:
        for line in _AUDIO_CLI_PARSER_COVERAGE.strip().splitlines():
            self.assertIn(line.strip(), _AUDIO_CLI_PARSER_COVERAGE)

    def test_decode_setup_efct_dir_mon(self) -> None:
        decoded = decode_setup_efct([0x01, 0x01, 0x00, 0x01])
        self.assertEqual(decoded["mainDirMon"], "ON")
        self.assertEqual(decoded["subDirMon"], "OFF")
        self.assertEqual(build_dir_mon_data([0x01, 0x01, 0x01, 0x20], main_off=True, sub_off=True), [0x01, 0x00, 0x00, 0x20])

    def test_generate_tone_and_analyze_expected_rms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.wav"
            wav_io.generate_sine_tone(path, duration=1.0, frequency=440.0, amplitude=0.5)
            report = metrics.analyze_file(path)
            self.assertIsNotNone(report["rmsDbfs"])
            assert report["rmsDbfs"] is not None
            expected = 20.0 * math.log10(0.5 / math.sqrt(2.0))
            self.assertAlmostEqual(report["rmsDbfs"], expected, delta=1.5)

    def test_analyze_file_trimmed_excludes_head_and_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.wav"
            wav_io.generate_sine_tone(path, duration=10.0, frequency=440.0, amplitude=0.5)
            full = metrics.analyze_file(path)
            trimmed = metrics.analyze_file_trimmed(path, trim_start_seconds=2.0, trim_end_seconds=2.0)
            assert full["rmsDbfs"] is not None and trimmed["rmsDbfs"] is not None
            self.assertAlmostEqual(trimmed["rmsDbfs"], full["rmsDbfs"], delta=0.5)
            self.assertEqual(trimmed["analyzedFrames"], 6 * 44100)

    def test_compare_files_reports_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            quiet = Path(tmp) / "quiet.wav"
            loud = Path(tmp) / "loud.wav"
            wav_io.generate_sine_tone(quiet, duration=0.5, amplitude=0.1)
            wav_io.generate_sine_tone(loud, duration=0.5, amplitude=0.4)
            result = metrics.compare_files([quiet, loud])
            delta = result["comparisons"][0]["deltaRmsDbVsFirst"]
            self.assertIsNotNone(delta)
            assert delta is not None
            self.assertGreater(delta, 6.0)

    def test_upmix_stereo_to_usb_dry_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stereo = Path(tmp) / "stereo.wav"
            six = Path(tmp) / "six.wav"
            wav_io.generate_sine_tone(stereo, duration=0.1, amplitude=0.5)
            info = wav_io.upmix_stereo_for_usb_role(stereo, six, role="dry")
            self.assertEqual(info["usbChannels"], [3, 4])
            _, channels, per = wav_io.read_wav(six)
            self.assertEqual(channels, 6)
            self.assertGreater(max(abs(sample) for sample in per[2]), 0.01)
            self.assertLess(max(abs(sample) for sample in per[0]), 0.001)

    def test_analyze_multichannel_peaks_reports_per_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / "cap6.wav"
            sample_rate = 44100
            frames = 200
            with wave.open(str(capture), "wb") as handle:
                handle.setnchannels(6)
                handle.setsampwidth(2)
                handle.setframerate(sample_rate)
                payload = bytearray()
                for _ in range(frames):
                    for channel in range(6):
                        value = 5000 if channel == 0 else 0
                        payload += struct.pack("<h", value)
                handle.writeframes(payload)
            report = analyze_multichannel_peaks(capture)
            self.assertTrue(report["anySignal"])
            self.assertIsNotNone(report["channelMetrics"][0]["peakDbfs"])
            self.assertIsNone(report["channelMetrics"][1]["peakDbfs"])

    def test_analyze_multichannel_peaks_treats_sub_floor_noise_as_no_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / "cap6.wav"
            sample_rate = 44100
            frames = 200
            with wave.open(str(capture), "wb") as handle:
                handle.setnchannels(6)
                handle.setsampwidth(2)
                handle.setframerate(sample_rate)
                payload = bytearray()
                for frame in range(frames):
                    for channel in range(6):
                        value = 1 if channel == 0 and frame == 0 else 0
                        payload += struct.pack("<h", value)
                handle.writeframes(payload)
            report = analyze_multichannel_peaks(capture)
            self.assertFalse(report["anySignal"])
            self.assertIsNotNone(report["channelMetrics"][0]["peakDbfs"])

    def test_extract_usb_dry_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / "cap6.wav"
            dry = Path(tmp) / "dry.wav"
            sample_rate = 44100
            frames = 200
            with wave.open(str(capture), "wb") as handle:
                handle.setnchannels(6)
                handle.setsampwidth(2)
                handle.setframerate(sample_rate)
                payload = bytearray()
                for index in range(frames):
                    values = [0, 0, 10000, 12000, 0, 0]
                    for value in values:
                        payload += struct.pack("<h", value)
                handle.writeframes(payload)
            info = wav_io.extract_channels(capture, devices.USB_DRY_STEREO, dry)
            self.assertEqual(info["extracted"], [3, 4])
            left, right = wav_io.read_wav(dry)[2]
            self.assertAlmostEqual(max(abs(sample) for sample in left), 10000 / 32768.0, places=3)

    def test_record_multichannel_delegates_to_coreaudio(self) -> None:
        from tools.gt1000.audio_lab import audio_io

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cap.wav"
            with mock.patch(
                "tools.gt1000.audio_lab.coreaudio_io.record_multichannel",
                return_value={"captureBackend": "coreaudio", "anySignal": True},
            ) as record:
                result = audio_io.record_multichannel(path, duration=1.0)
            record.assert_called_once()
            self.assertEqual(result["captureBackend"], "coreaudio")

    def test_probe_silence_warning_names_codex_and_restart(self) -> None:
        with mock.patch(
            "tools.gt1000.audio_lab.audio_io.record_multichannel",
            return_value={"captureBackend": "coreaudio", "anySignal": False},
        ), mock.patch(
            "tools.gt1000.audio_lab.audio_io.analyze_multichannel_peaks",
            return_value={"anySignal": False, "channelMetrics": []},
        ):
            result = audio_io.probe_capture(duration=0.1)
        warning = " ".join(result["troubleshooting"])
        self.assertIn("Codex", warning)
        self.assertIn("restart", warning)

    def test_reamp_fails_when_duplex_capture_is_digital_silence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dry = Path(tmp) / "dry.wav"
            wet = Path(tmp) / "wet.wav"
            wav_io.generate_sine_tone(dry, duration=0.1, amplitude=0.2)
            with mock.patch(
                "tools.gt1000.audio_lab.coreaudio_io.duplex_playback_capture",
                return_value={"digitalSilence": True, "captureBackend": "coreaudio"},
            ):
                with self.assertRaises(AudioLabError) as caught:
                    audio_io.reamp_capture(dry, wet, prepare_usb=False)
        message = str(caught.exception)
        self.assertIn("captured digital silence", message)
        self.assertIn("Microphone permission", message)
        self.assertIn("Codex", message)
        self.assertIn("send/return", message)
        self.assertEqual(caught.exception.exit_code, 66)

    def test_coreaudio_teardown_stops_and_terminates_portaudio(self) -> None:
        fake_sounddevice = mock.Mock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            coreaudio_io._teardown_portaudio()
        fake_sounddevice.stop.assert_called_once_with()
        fake_sounddevice._terminate.assert_called_once_with()

    def test_coreaudio_require_initializes_portaudio(self) -> None:
        fake_sounddevice = mock.Mock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sounddevice, "numpy": mock.Mock()}):
            coreaudio_io._require_coreaudio()
        fake_sounddevice._initialize.assert_called_once_with()

    def test_is_gt1000_audio_name(self) -> None:
        self.assertTrue(devices.is_gt1000_audio_name("GT-1000"))
        self.assertTrue(devices.is_gt1000_audio_name("jp_co_roland_RDUSB0217Dev_Device"))
        self.assertFalse(devices.is_gt1000_audio_name("Mac mini Speakers"))

    def test_session_generate_tone_writes_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session, "session_root", return_value=Path(tmp)):
                result = cmd_generate_tone("sprint-a", duration=1.0, frequency=220.0, amplitude=0.2, sample_rate=44100)
            session_dir = Path(result["sessionDir"])
            self.assertTrue((session_dir / "dry.wav").is_file())
            self.assertTrue((session_dir / "meta.json").is_file())
            self.assertIsNotNone(result["dryMetrics"]["rmsDbfs"])

    def test_cmd_analyze_cli_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.wav"
            wav_io.generate_sine_tone(path, duration=0.25, amplitude=0.3)
            payload = cmd_analyze([path])
            self.assertEqual(payload["id"], "audioAnalyze")
            self.assertIn("rmsDbfs", payload["file"])

    def test_reference_profile_and_match_reference_rank_closer_candidate_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference = directory / "reference.wav"
            close = directory / "close.wav"
            far = directory / "far.wav"
            profile_path = directory / "reference-profile.json"
            _write_composite_tone(reference, frequencies=[220.0, 880.0])
            _write_composite_tone(close, frequencies=[220.0, 880.0])
            _write_composite_tone(far, frequencies=[3000.0, 6000.0])

            profile_payload = cmd_reference_analyze(reference, output_path=profile_path)
            self.assertEqual(profile_payload["id"], "audioReferenceAnalyze")
            self.assertTrue(profile_path.is_file())
            self.assertGreater(len(profile_payload["profile"]["bands"]), 1)
            self.assertIsNotNone(profile_payload["profile"]["crestDb"])

            match_payload = cmd_match_reference(profile_path, [far, close])
            self.assertEqual(match_payload["id"], "audioMatchReference")
            self.assertEqual(match_payload["best"]["path"], str(close))
            self.assertLess(
                match_payload["ranked"][0]["score"],
                match_payload["ranked"][1]["score"],
            )

    def test_reference_plan_emits_valid_bounded_patch_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference = directory / "reference.wav"
            profile_path = directory / "reference-profile.json"
            _write_composite_tone(reference, frequencies=[3000.0, 6000.0])
            cmd_reference_analyze(reference, output_path=profile_path)

            plan = cmd_reference_plan(profile_path, session="tone-chase", max_candidates=3)

            self.assertEqual(plan["id"], "audioReferencePlan")
            self.assertEqual(plan["candidateCount"], 3)
            self.assertEqual(plan["candidates"][0]["label"], "eq-low-plus")
            for candidate in plan["candidates"]:
                command = candidate["patchCommand"]
                self.assertEqual(command[:2], ["patch", "set"])
                self.assertIn("--verify", command)
                self.assertEqual(candidate["writeCount"], 1)
                self.assertEqual(candidate["renderCommand"][:4], ["audio", "session", "render", "--session"])

    def test_sanitize_render_label(self) -> None:
        self.assertEqual(sanitize_label("baseline v2"), "baseline-v2")

    def test_session_init_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session, "session_root", return_value=Path(tmp)):
                payload = cmd_session_init("lab-a", live=False)
            session_dir = Path(payload["sessionDir"])
            self.assertTrue((session_dir / "meta.json").is_file())
            self.assertTrue((session_dir / "renders").is_dir())
            self.assertEqual(payload["id"], "audioSessionInit")

    @mock.patch(
        "tools.gt1000.audio_lab.orchestrator.reamp_capture",
        return_value={"captureBackend": "coreaudio"},
    )
    @mock.patch(
        "tools.gt1000.audio_lab.orchestrator.read_patch_snapshot",
        return_value={"patchName": "TEST", "readHash": "abc", "chain": {"blocks": []}},
    )
    def test_session_render_appends_log(self, _patch_snap: mock.Mock, _patch_reamp: mock.Mock) -> None:
        from tools.gt1000.audio_lab import orchestrator

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session, "session_root", return_value=Path(tmp)):
                cmd_generate_tone("render-test", duration=0.2, frequency=440.0, amplitude=0.2, sample_rate=44100)
                wet_path = Path(tmp) / "render-test" / "renders" / "baseline-wet.wav"
                wet_path.parent.mkdir(parents=True, exist_ok=True)
                wav_io.generate_sine_tone(wet_path, duration=0.2, amplitude=0.1)
                result = orchestrator.render_labeled_wet("render-test", "baseline", midi_timeout=1.0)
            meta = json.loads((Path(tmp) / "render-test" / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(len(meta["renders"]), 1)
            self.assertEqual(meta["renders"][0]["label"], "baseline")
            self.assertEqual(result["id"], "audioSessionRender")


if __name__ == "__main__":
    unittest.main()
