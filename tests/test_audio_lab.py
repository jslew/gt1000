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
from tools.gt1000.audio_lab.commands import cmd_analyze, cmd_generate_tone, cmd_match_reference, cmd_reference_analyze, cmd_reference_plan, cmd_reference_run, cmd_session_init
from tools.gt1000.audio_lab.reference_planner import plan_reference_candidates
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
"audio", "reference", "run"
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


def _write_tail_fixture(
    path: Path,
    *,
    wide_tail: bool = False,
    pulsed_tail: bool = False,
    sample_rate: int = 44100,
) -> None:
    body_frames = int(1.0 * sample_rate)
    tail_frames = int(1.0 * sample_rate)
    left: list[float] = []
    right: list[float] = []
    for index in range(body_frames):
        value = 0.25 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate)
        left.append(value)
        right.append(value)
    for index in range(tail_frames):
        seconds = index / sample_rate
        envelope = 0.18 * math.exp(-3.0 * seconds)
        if pulsed_tail:
            pulse_phase = seconds % 0.2
            envelope *= 1.0 if pulse_phase < 0.055 else 0.15
        left_value = envelope * math.sin(2.0 * math.pi * 660.0 * index / sample_rate)
        if wide_tail:
            right_index = max(0, index - int(0.012 * sample_rate))
            right_value = -envelope * math.sin(2.0 * math.pi * 660.0 * right_index / sample_rate)
        else:
            right_value = left_value
        left.append(left_value)
        right.append(right_value)
    wav_io.write_wav_stereo(path, sample_rate, left, right)


def _write_high_end_fixture(
    path: Path,
    *,
    extra_frequency: float | None = None,
    extra_amplitude: float = 0.0,
    sample_rate: int = 44100,
) -> None:
    frames = int(1.25 * sample_rate)
    left: list[float] = []
    right: list[float] = []
    for index in range(frames):
        body = (
            0.16 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate)
            + 0.10 * math.sin(2.0 * math.pi * 1600.0 * index / sample_rate)
            + 0.05 * math.sin(2.0 * math.pi * 3200.0 * index / sample_rate)
        )
        extra = 0.0 if extra_frequency is None else extra_amplitude * math.sin(2.0 * math.pi * extra_frequency * index / sample_rate)
        value = body + extra
        left.append(value)
        right.append(value)
    wav_io.write_wav_stereo(path, sample_rate, left, right)


def _write_low_body_fixture(
    path: Path,
    *,
    body_boost: float = 0.0,
    sub_boost: float = 0.0,
    amplitude: float = 1.0,
    sample_rate: int = 44100,
) -> None:
    frames = int(1.25 * sample_rate)
    left: list[float] = []
    right: list[float] = []
    for index in range(frames):
        value = amplitude * (
            0.12 * math.sin(2.0 * math.pi * 220.0 * index / sample_rate)
            + 0.08 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate)
            + 0.10 * math.sin(2.0 * math.pi * 1000.0 * index / sample_rate)
            + body_boost * math.sin(2.0 * math.pi * 240.0 * index / sample_rate)
            + (body_boost * 0.6) * math.sin(2.0 * math.pi * 500.0 * index / sample_rate)
            + sub_boost * math.sin(2.0 * math.pi * 110.0 * index / sample_rate)
        )
        left.append(value)
        right.append(value)
    wav_io.write_wav_stereo(path, sample_rate, left, right)


def _write_envelope_fixture(
    path: Path,
    *,
    attack_spike: bool = False,
    fast_decay: bool = False,
    amplitude: float = 1.0,
    sample_rate: int = 44100,
) -> None:
    frames = int(1.5 * sample_rate)
    left: list[float] = []
    right: list[float] = []
    for index in range(frames):
        seconds = index / sample_rate
        if fast_decay:
            envelope = 0.28 * math.exp(-2.4 * seconds) + 0.035
        else:
            envelope = 0.22
        if attack_spike and seconds < 0.04:
            envelope += 0.38 * (1.0 - seconds / 0.04)
        value = amplitude * envelope * (
            0.7 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate)
            + 0.3 * math.sin(2.0 * math.pi * 880.0 * index / sample_rate)
        )
        left.append(value)
        right.append(value)
    wav_io.write_wav_stereo(path, sample_rate, left, right)


def _write_lead_mid_fixture(
    path: Path,
    *,
    lead_mid_boost: float = 0.0,
    low_mid_boost: float = 0.0,
    fizz_boost: float = 0.0,
    amplitude: float = 1.0,
    sample_rate: int = 44100,
) -> None:
    frames = int(1.25 * sample_rate)
    left: list[float] = []
    right: list[float] = []
    for index in range(frames):
        value = amplitude * (
            0.10 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate)
            + 0.08 * math.sin(2.0 * math.pi * 895.0 * index / sample_rate)
            + 0.08 * math.sin(2.0 * math.pi * 1768.0 * index / sample_rate)
            + 0.04 * math.sin(2.0 * math.pi * 3150.0 * index / sample_rate)
            + low_mid_boost * math.sin(2.0 * math.pi * 895.0 * index / sample_rate)
            + lead_mid_boost * math.sin(2.0 * math.pi * 1768.0 * index / sample_rate)
            + fizz_boost * math.sin(2.0 * math.pi * 5854.0 * index / sample_rate)
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
            self.assertTrue(profile_payload["profile"]["space"]["available"])

            match_payload = cmd_match_reference(profile_path, [far, close])
            self.assertEqual(match_payload["id"], "audioMatchReference")
            self.assertEqual(match_payload["best"]["path"], str(close))
            self.assertLess(
                match_payload["ranked"][0]["score"],
                match_payload["ranked"][1]["score"],
            )
            best_report = match_payload["best"]["report"]
            self.assertIn("weightedComponents", best_report)
            self.assertIn("strongestDifferences", best_report)
            self.assertIn("plainSummary", best_report)
            self.assertTrue(any(component["name"] == "broad bands" for component in best_report["weightedComponents"]))

    def test_reference_match_report_explains_descriptor_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference = directory / "reference.wav"
            fizz = directory / "fizz.wav"
            profile_path = directory / "reference-profile.json"
            _write_high_end_fixture(reference)
            _write_high_end_fixture(fizz, extra_frequency=5854.0, extra_amplitude=0.16)
            cmd_reference_analyze(reference, output_path=profile_path)

            match_payload = cmd_match_reference(profile_path, [fizz])
            report = match_payload["best"]["report"]

            labels = {item["label"] for item in report["descriptorDeltas"]}
            self.assertIn("fizz vs lead mids", labels)
            self.assertGreater(match_payload["best"]["details"]["highEndError"], 0.0)
            self.assertIn("Main score pressure", report["plainSummary"])

    def test_reference_profile_space_metrics_detect_wide_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mono_tail = directory / "mono-tail.wav"
            wide_tail = directory / "wide-tail.wav"
            _write_tail_fixture(mono_tail, wide_tail=False)
            _write_tail_fixture(wide_tail, wide_tail=True)

            mono_profile = metrics.reference_profile(mono_tail)
            wide_profile = metrics.reference_profile(wide_tail)
            mono_space = mono_profile["space"]
            wide_space = wide_profile["space"]

            self.assertTrue(mono_space["available"])
            self.assertTrue(wide_space["available"])
            self.assertIsNotNone(mono_space["tailStereoCorrelationMedian"])
            self.assertIsNotNone(wide_space["tailStereoCorrelationMedian"])
            self.assertGreater(mono_space["tailStereoCorrelationMedian"], 0.95)
            self.assertLess(wide_space["tailStereoCorrelationMedian"], 0.2)
            self.assertGreater(
                wide_space["tailSideToMidDbMedian"],
                mono_space["tailSideToMidDbMedian"],
            )

    def test_reference_profile_space_metrics_detect_repeated_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            smooth_tail = directory / "smooth-tail.wav"
            pulsed_tail = directory / "pulsed-tail.wav"
            _write_tail_fixture(smooth_tail, pulsed_tail=False)
            _write_tail_fixture(pulsed_tail, pulsed_tail=True)

            smooth_space = metrics.reference_profile(smooth_tail)["space"]
            pulsed_space = metrics.reference_profile(pulsed_tail)["space"]

            self.assertTrue(smooth_space["available"])
            self.assertTrue(pulsed_space["available"])
            self.assertIsNotNone(smooth_space["repeatPeakStrength"])
            self.assertIsNotNone(pulsed_space["repeatPeakStrength"])
            self.assertGreater(
                pulsed_space["tailEnvelopeModulationDb"],
                smooth_space["tailEnvelopeModulationDb"],
            )

    def test_reference_match_score_prefers_matching_space_when_bands_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mono_tail = directory / "mono-tail.wav"
            wide_tail = directory / "wide-tail.wav"
            _write_tail_fixture(mono_tail, wide_tail=False)
            _write_tail_fixture(wide_tail, wide_tail=True)

            reference = metrics.reference_profile(wide_tail)
            matching = metrics.reference_profile(wide_tail)
            mismatched = metrics.reference_profile(mono_tail)

            matching_score = metrics.reference_match_score(reference, matching)
            mismatched_score = metrics.reference_match_score(reference, mismatched)

            self.assertEqual(matching_score["spaceError"], 0.0)
            self.assertGreater(mismatched_score["spaceError"], matching_score["spaceError"])
            self.assertLess(matching_score["score"], mismatched_score["score"])

    def test_reference_profile_high_end_detects_added_fizz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference_path = directory / "reference.wav"
            fizz_path = directory / "fizz.wav"
            _write_high_end_fixture(reference_path)
            _write_high_end_fixture(fizz_path, extra_frequency=5854.0, extra_amplitude=0.10)

            reference = metrics.reference_profile(reference_path)
            fizz = metrics.reference_profile(fizz_path)

            self.assertTrue(reference["highEnd"]["available"])
            self.assertTrue(fizz["highEnd"]["available"])
            self.assertGreater(
                fizz["highEnd"]["fizzToPresenceDb"],
                reference["highEnd"]["fizzToPresenceDb"],
            )
            self.assertGreater(
                fizz["highEnd"]["fizzToLeadMidDb"],
                reference["highEnd"]["fizzToLeadMidDb"],
            )

    def test_reference_match_score_penalizes_fizz_more_than_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference_path = directory / "reference.wav"
            presence_path = directory / "presence.wav"
            fizz_path = directory / "fizz.wav"
            _write_high_end_fixture(reference_path)
            _write_high_end_fixture(presence_path, extra_frequency=3200.0, extra_amplitude=0.10)
            _write_high_end_fixture(fizz_path, extra_frequency=5854.0, extra_amplitude=0.10)

            reference = metrics.reference_profile(reference_path)
            presence = metrics.reference_profile(presence_path)
            fizz = metrics.reference_profile(fizz_path)
            presence_score = metrics.reference_match_score(reference, presence)
            fizz_score = metrics.reference_match_score(reference, fizz)

            self.assertGreater(fizz_score["highEndError"], presence_score["highEndError"])
            self.assertGreater(fizz_score["score"], presence_score["score"])

    def test_reference_profile_low_body_distinguishes_body_from_flub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            thin_path = directory / "thin.wav"
            body_path = directory / "body.wav"
            flub_path = directory / "flub.wav"
            _write_low_body_fixture(thin_path, body_boost=0.0, sub_boost=0.0)
            _write_low_body_fixture(body_path, body_boost=0.08, sub_boost=0.0)
            _write_low_body_fixture(flub_path, body_boost=0.08, sub_boost=0.12)

            thin = metrics.reference_profile(thin_path)["lowBody"]
            body = metrics.reference_profile(body_path)["lowBody"]
            flub = metrics.reference_profile(flub_path)["lowBody"]

            self.assertTrue(thin["available"])
            self.assertTrue(body["available"])
            self.assertTrue(flub["available"])
            self.assertGreater(
                body["bodyLowMidToMidLeadDb"],
                thin["bodyLowMidToMidLeadDb"],
            )
            self.assertGreater(
                flub["subToBodyLowMidDb"],
                body["subToBodyLowMidDb"],
            )

    def test_reference_match_score_prefers_body_over_flub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference_path = directory / "reference.wav"
            thin_path = directory / "thin.wav"
            body_path = directory / "body.wav"
            flub_path = directory / "flub.wav"
            _write_low_body_fixture(reference_path, body_boost=0.08, sub_boost=0.0)
            _write_low_body_fixture(thin_path, body_boost=0.0, sub_boost=0.0)
            _write_low_body_fixture(body_path, body_boost=0.08, sub_boost=0.0)
            _write_low_body_fixture(flub_path, body_boost=0.08, sub_boost=0.12)

            reference = metrics.reference_profile(reference_path)
            thin = metrics.reference_profile(thin_path)
            body = metrics.reference_profile(body_path)
            flub = metrics.reference_profile(flub_path)
            thin_score = metrics.reference_match_score(reference, thin)
            body_score = metrics.reference_match_score(reference, body)
            flub_score = metrics.reference_match_score(reference, flub)

            self.assertEqual(body_score["lowBodyError"], 0.0)
            self.assertGreater(thin_score["lowBodyError"], body_score["lowBodyError"])
            self.assertGreater(flub_score["lowBodyError"], body_score["lowBodyError"])
            self.assertLess(body_score["score"], thin_score["score"])
            self.assertLess(body_score["score"], flub_score["score"])

    def test_reference_low_body_ratios_survive_level_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            quiet_path = directory / "quiet.wav"
            loud_path = directory / "loud.wav"
            _write_low_body_fixture(quiet_path, body_boost=0.06, sub_boost=0.02, amplitude=0.5)
            _write_low_body_fixture(loud_path, body_boost=0.06, sub_boost=0.02, amplitude=1.0)

            quiet = metrics.reference_profile(quiet_path)
            loud = metrics.reference_profile(loud_path)
            score = metrics.reference_match_score(quiet, loud)

            self.assertAlmostEqual(
                quiet["lowBody"]["bodyLowMidToMidLeadDb"],
                loud["lowBody"]["bodyLowMidToMidLeadDb"],
                delta=0.2,
            )
            self.assertAlmostEqual(score["lowBodyError"], 0.0, delta=0.001)

    def test_reference_profile_envelope_detects_attack_spike(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            smooth_path = directory / "smooth.wav"
            spiky_path = directory / "spiky.wav"
            _write_envelope_fixture(smooth_path)
            _write_envelope_fixture(spiky_path, attack_spike=True)

            smooth = metrics.reference_profile(smooth_path)["envelope"]
            spiky = metrics.reference_profile(spiky_path)["envelope"]

            self.assertTrue(smooth["available"])
            self.assertTrue(spiky["available"])
            self.assertGreater(spiky["attackToSustainDb"], smooth["attackToSustainDb"])
            self.assertGreater(spiky["peakToSustainDb"], smooth["peakToSustainDb"])
            self.assertGreater(spiky["attackCrestP90Db"], smooth["attackCrestP90Db"])

    def test_reference_profile_envelope_detects_fast_decay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            smooth_path = directory / "smooth.wav"
            decay_path = directory / "decay.wav"
            _write_envelope_fixture(smooth_path)
            _write_envelope_fixture(decay_path, fast_decay=True)

            smooth = metrics.reference_profile(smooth_path)["envelope"]
            decay = metrics.reference_profile(decay_path)["envelope"]

            self.assertTrue(smooth["available"])
            self.assertTrue(decay["available"])
            self.assertGreater(decay["sustainDropDb"], smooth["sustainDropDb"])
            self.assertLess(decay["sustainSlopeDbPerSecond"], smooth["sustainSlopeDbPerSecond"])
            self.assertLess(decay["sustainFractionWithin12Db"], smooth["sustainFractionWithin12Db"])

    def test_reference_match_score_prefers_matching_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            smooth_path = directory / "smooth.wav"
            decay_path = directory / "decay.wav"
            _write_envelope_fixture(smooth_path)
            _write_envelope_fixture(decay_path, fast_decay=True)

            reference = metrics.reference_profile(smooth_path)
            smooth = metrics.reference_profile(smooth_path)
            decay = metrics.reference_profile(decay_path)
            smooth_score = metrics.reference_match_score(reference, smooth)
            decay_score = metrics.reference_match_score(reference, decay)

            self.assertEqual(smooth_score["envelopeError"], 0.0)
            self.assertGreater(decay_score["envelopeError"], smooth_score["envelopeError"])
            self.assertLess(smooth_score["score"], decay_score["score"])

    def test_reference_envelope_ratios_survive_level_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            quiet_path = directory / "quiet.wav"
            loud_path = directory / "loud.wav"
            _write_envelope_fixture(quiet_path, amplitude=0.5)
            _write_envelope_fixture(loud_path, amplitude=1.0)

            quiet = metrics.reference_profile(quiet_path)
            loud = metrics.reference_profile(loud_path)
            score = metrics.reference_match_score(quiet, loud)

            self.assertAlmostEqual(
                quiet["envelope"]["attackToSustainDb"],
                loud["envelope"]["attackToSustainDb"],
                delta=0.2,
            )
            self.assertAlmostEqual(score["envelopeError"], 0.0, delta=0.001)

    def test_reference_profile_lead_mid_distinguishes_focus_from_low_mid_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            low_mid_path = directory / "low-mid.wav"
            lead_mid_path = directory / "lead-mid.wav"
            _write_lead_mid_fixture(low_mid_path, low_mid_boost=0.10)
            _write_lead_mid_fixture(lead_mid_path, lead_mid_boost=0.10)

            low_mid = metrics.reference_profile(low_mid_path)["leadMid"]
            lead_mid = metrics.reference_profile(lead_mid_path)["leadMid"]

            self.assertTrue(low_mid["available"])
            self.assertTrue(lead_mid["available"])
            self.assertGreater(lead_mid["leadMidToLowMidDb"], low_mid["leadMidToLowMidDb"])
            self.assertGreater(lead_mid["leadFocusIndexDb"], low_mid["leadFocusIndexDb"])

    def test_reference_match_score_prefers_lead_mid_focus_over_fizz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference_path = directory / "reference.wav"
            lead_mid_path = directory / "lead-mid.wav"
            fizz_path = directory / "fizz.wav"
            _write_lead_mid_fixture(reference_path, lead_mid_boost=0.10)
            _write_lead_mid_fixture(lead_mid_path, lead_mid_boost=0.10)
            _write_lead_mid_fixture(fizz_path, fizz_boost=0.10)

            reference = metrics.reference_profile(reference_path)
            lead_mid = metrics.reference_profile(lead_mid_path)
            fizz = metrics.reference_profile(fizz_path)
            lead_mid_score = metrics.reference_match_score(reference, lead_mid)
            fizz_score = metrics.reference_match_score(reference, fizz)

            self.assertEqual(lead_mid_score["leadMidError"], 0.0)
            self.assertGreater(fizz_score["leadMidError"], lead_mid_score["leadMidError"])
            self.assertLess(lead_mid_score["score"], fizz_score["score"])

    def test_reference_lead_mid_ratios_survive_level_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            quiet_path = directory / "quiet.wav"
            loud_path = directory / "loud.wav"
            _write_lead_mid_fixture(quiet_path, lead_mid_boost=0.08, amplitude=0.35)
            _write_lead_mid_fixture(loud_path, lead_mid_boost=0.08, amplitude=0.7)

            quiet = metrics.reference_profile(quiet_path)
            loud = metrics.reference_profile(loud_path)
            score = metrics.reference_match_score(quiet, loud)

            self.assertAlmostEqual(
                quiet["leadMid"]["leadFocusIndexDb"],
                loud["leadMid"]["leadFocusIndexDb"],
                delta=0.2,
            )
            self.assertAlmostEqual(score["leadMidError"], 0.0, delta=0.001)

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
            self.assertIn("descriptorGuidance", plan)
            for candidate in plan["candidates"]:
                command = candidate["patchCommand"]
                self.assertEqual(command[0], "patch")
                self.assertIn("--verify", command)
                if candidate["command"] == "master-set":
                    self.assertFalse(candidate["requiresLiveVerification"])
                    self.assertEqual(candidate["verificationPolicy"], "live-verified-surface")
                else:
                    self.assertTrue(candidate["requiresLiveVerification"])
                    self.assertEqual(candidate["verificationPolicy"], "verify-before-render")
                self.assertEqual(candidate["writeCount"], 1)
                self.assertEqual(candidate["renderCommand"][:4], ["audio", "session", "render", "--session"])

    def test_reference_run_cli_default_candidate_budget_is_twelve(self) -> None:
        from tools.gt1000 import agent_cli

        parser = agent_cli.build_parser()
        args = parser.parse_args(["audio", "reference", "run", "profile.json", "--session", "tone-chase"])

        self.assertEqual(args.max_candidates, 12)

    def test_reference_plan_expands_to_verification_gated_drive_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reference = directory / "reference.wav"
            profile_path = directory / "reference-profile.json"
            _write_composite_tone(reference, frequencies=[220.0, 880.0])
            cmd_reference_analyze(reference, output_path=profile_path)

            plan = cmd_reference_plan(profile_path, session="tone-chase", max_candidates=30)

            labels = {candidate["label"]: candidate for candidate in plan["candidates"]}
            self.assertIn("dist-level-plus", labels)
            self.assertIn("dist-drive-plus", labels)
            self.assertIn("preamp-level-plus", labels)
            for label in ("dist-level-plus", "dist-drive-plus", "preamp-level-plus"):
                self.assertTrue(labels[label]["requiresLiveVerification"])
                self.assertEqual(labels[label]["verificationPolicy"], "verify-before-render")
                self.assertEqual(labels[label]["patchCommand"][-1], "--verify")

    def test_reference_plan_uses_space_lead_mid_and_sustain_descriptors(self) -> None:
        profile = {
            "path": "/tmp/reference.wav",
            "profileVersion": 1,
            "spectralCentroidHz": 950.0,
            "space": {
                "available": True,
                "tailToActiveDeltaDb": -6.0,
                "repeatPeakStrength": 0.08,
                "tailSideToMidDb": -6.5,
            },
            "leadMid": {
                "available": True,
                "leadFocusIndexDb": 5.5,
                "leadMidToLowMidDb": 4.5,
            },
            "envelope": {
                "available": True,
                "sustainDropDb": 1.0,
                "sustainFractionWithin12Db": 0.92,
            },
        }

        plan = plan_reference_candidates(profile, session="tone-chase", max_candidates=14)
        labels = [candidate["label"] for candidate in plan["candidates"]]
        guidance = {entry["signal"] for entry in plan["descriptorGuidance"]}

        self.assertIn("space-wet", guidance)
        self.assertIn("lead-focus", guidance)
        self.assertIn("sustain", guidance)
        self.assertEqual(labels[0], "reverb-level-plus")
        self.assertLess(labels.index("reverb-level-plus"), labels.index("patch-level-plus"))
        self.assertLess(labels.index("eq-2k-plus"), labels.index("patch-level-plus"))
        self.assertIn("comp-sustain-plus", labels)
        for label in ("reverb-level-plus", "eq-2k-plus", "comp-sustain-plus"):
            candidate = next(item for item in plan["candidates"] if item["label"] == label)
            self.assertTrue(candidate["requiresLiveVerification"])
            self.assertEqual(candidate["writeCount"], 1)

    def test_reference_plan_uses_fizz_and_flub_control_descriptors(self) -> None:
        profile = {
            "path": "/tmp/reference.wav",
            "profileVersion": 1,
            "spectralCentroidHz": 1400.0,
            "highEnd": {
                "available": True,
                "fizzToLeadMidDb": -4.0,
                "fizzToPresenceDb": -3.0,
                "presenceToLeadMidDb": 2.0,
            },
            "lowBody": {
                "available": True,
                "subToBodyLowMidDb": -1.0,
                "bodyLowMidToMidLeadDb": -4.0,
            },
        }

        plan = plan_reference_candidates(profile, session="tone-chase", max_candidates=9)
        labels = [candidate["label"] for candidate in plan["candidates"]]
        guidance = {entry["signal"] for entry in plan["descriptorGuidance"]}

        self.assertIn("fizz-control", guidance)
        self.assertIn("flub-control", guidance)
        self.assertLess(labels.index("eq-high-minus"), labels.index("patch-level-plus"))
        self.assertLess(labels.index("eq-low-minus"), labels.index("patch-level-plus"))
        self.assertIn("preamp-presence-minus", labels)
        self.assertEqual(len(labels), len(set(labels)))

    def test_reference_plan_includes_validated_amp_and_paired_cab_candidates(self) -> None:
        profile = {
            "path": "/tmp/reference.wav",
            "profileVersion": 1,
            "spectralCentroidHz": 950.0,
            "lowBody": {
                "available": True,
                "subToBodyLowMidDb": -8.0,
                "bodyLowMidToMidLeadDb": 5.0,
            },
        }

        plan = plan_reference_candidates(profile, session="tone-chase", max_candidates=8)
        labels = {candidate["label"]: candidate for candidate in plan["candidates"]}

        self.assertIn("preamp-type-brit-stack", labels)
        self.assertIn("main-cab-type-2", labels)
        amp = labels["preamp-type-brit-stack"]
        cab = labels["main-cab-type-2"]
        self.assertEqual(amp["patchPlan"], "set:preamp1.type")
        self.assertEqual(amp["writeCount"], 1)
        self.assertTrue(amp["requiresLiveVerification"])
        self.assertEqual(cab["command"], "compound-set")
        self.assertEqual(cab["writeCount"], 2)
        self.assertEqual(
            cab["settings"],
            [
                {"area": "mainSpeakerSimulatorL", "parameter": "speakerType", "value": "2"},
                {"area": "mainSpeakerSimulatorR", "parameter": "speakerType", "value": "2"},
            ],
        )
        self.assertEqual(len(cab["patchCommands"]), 2)
        self.assertTrue(cab["requiresLiveVerification"])
        self.assertEqual(cab["verificationPolicy"], "verify-before-render")

        from tools.gt1000.audio_lab import reference_runner

        cab_plan = reference_runner._candidate_patch_plan(cab)
        self.assertEqual(cab_plan.id, "compound-set:main-cab-type-2")
        self.assertEqual(len(cab_plan.writes), 2)

    def test_reference_run_applies_renders_scores_and_restores_candidate(self) -> None:
        from tools.gt1000 import live
        from tools.gt1000.audio_lab import reference_runner

        def fake_original_reads(*, timeout: float, requests: list[live.PatchReadRequest]) -> dict[str, list[int]]:
            return {
                live.address_key(request.address): [64] * live.seven_bit_address_value(request.size)
                for request in requests
            }

        def fake_render(
            session_name: str,
            label: str,
            *,
            prepare_usb: bool,
            midi_timeout: float,
            settle_seconds: float,
            snapshot_patch: bool,
        ) -> dict:
            session_dir = Path(tmp) / session_name
            wet_path = session_dir / "renders" / f"{label}-wet.wav"
            if "candidate" in label:
                _write_composite_tone(wet_path, frequencies=[3000.0, 6000.0])
            else:
                _write_composite_tone(wet_path, frequencies=[220.0, 440.0])
            return {
                "id": "audioSessionRender",
                "session": session_name,
                "label": label,
                "wetPath": str(wet_path),
                "dryPath": str(session_dir / "dry.wav"),
                "patchSnapshot": {"patchName": "TEST"},
            }

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with mock.patch.object(session, "session_root", return_value=directory):
                cmd_generate_tone("run-test", duration=0.2, frequency=440.0, amplitude=0.2, sample_rate=44100)
                reference = directory / "reference.wav"
                profile_path = directory / "reference-profile.json"
                _write_composite_tone(reference, frequencies=[3000.0, 6000.0])
                cmd_reference_analyze(reference, output_path=profile_path)
                with mock.patch.object(
                    reference_runner.live,
                    "read_data_sets",
                    side_effect=fake_original_reads,
                ), mock.patch.object(
                    reference_runner,
                    "apply_plan_after_audio",
                    return_value={"verified": True},
                ) as apply_mock, mock.patch.object(
                    reference_runner,
                    "render_labeled_wet",
                    side_effect=fake_render,
                ):
                    result = cmd_reference_run(
                        profile_path,
                        session="run-test",
                        max_candidates=1,
                        verify_writes=True,
                    )

            self.assertEqual(result["id"], "audioReferenceRun")
            self.assertEqual(result["candidateCount"], 1)
            self.assertEqual(len(result["renders"]), 2)
            self.assertNotEqual(result["best"]["label"], "baseline")
            self.assertEqual(result["baseline"]["label"], "baseline")
            self.assertIn(result["improvement"]["status"], {"improved", "target-met"})
            self.assertGreater(result["improvement"]["scoreImprovementPercent"], 0.0)
            self.assertEqual(result["auditionShortlist"][0]["label"], result["best"]["label"])
            self.assertEqual(result["auditionShortlist"][0]["wetPath"], result["best"]["wetPath"])
            self.assertEqual(result["recommendation"]["action"], "audition-best-candidate")
            self.assertEqual(result["recommendation"]["topWetPath"], result["best"]["wetPath"])
            self.assertEqual(apply_mock.call_count, 2)
            self.assertTrue(result["renders"][1]["restoreResult"]["verified"])
            self.assertIn("plainSummary", result["best"]["report"])
            self.assertIn("weightedComponents", result["best"]["report"])
            self.assertIn(
                "Scores are an audition/ranking aid, not a guarantee of a perceptual tone match.",
                result["notes"],
            )

    def test_reference_run_reports_baseline_when_candidates_do_not_improve(self) -> None:
        from tools.gt1000 import live
        from tools.gt1000.audio_lab import reference_runner

        def fake_original_reads(*, timeout: float, requests: list[live.PatchReadRequest]) -> dict[str, list[int]]:
            return {
                live.address_key(request.address): [64] * live.seven_bit_address_value(request.size)
                for request in requests
            }

        def fake_render(
            session_name: str,
            label: str,
            *,
            prepare_usb: bool,
            midi_timeout: float,
            settle_seconds: float,
            snapshot_patch: bool,
        ) -> dict:
            session_dir = Path(tmp) / session_name
            wet_path = session_dir / "renders" / f"{label}-wet.wav"
            if "candidate" in label:
                _write_composite_tone(wet_path, frequencies=[3000.0, 6000.0])
            else:
                _write_composite_tone(wet_path, frequencies=[220.0, 440.0])
            return {
                "id": "audioSessionRender",
                "session": session_name,
                "label": label,
                "wetPath": str(wet_path),
                "dryPath": str(session_dir / "dry.wav"),
            }

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with mock.patch.object(session, "session_root", return_value=directory):
                cmd_generate_tone("no-improve-test", duration=0.2, frequency=440.0, amplitude=0.2, sample_rate=44100)
                reference = directory / "reference.wav"
                profile_path = directory / "reference-profile.json"
                _write_composite_tone(reference, frequencies=[220.0, 440.0])
                cmd_reference_analyze(reference, output_path=profile_path)
                with mock.patch.object(
                    reference_runner.live,
                    "read_data_sets",
                    side_effect=fake_original_reads,
                ), mock.patch.object(
                    reference_runner,
                    "apply_plan_after_audio",
                    return_value={"verified": True},
                ), mock.patch.object(
                    reference_runner,
                    "render_labeled_wet",
                    side_effect=fake_render,
                ):
                    result = cmd_reference_run(
                        profile_path,
                        session="no-improve-test",
                        max_candidates=1,
                        verify_writes=True,
                    )

            self.assertEqual(result["best"]["label"], "baseline")
            self.assertEqual(result["improvement"]["status"], "baseline-best")
            self.assertFalse(result["improvement"]["meetsThirtyPercentBandTarget"])
            self.assertEqual(result["auditionShortlist"][0]["label"], "baseline")
            self.assertEqual(result["recommendation"]["action"], "audition-baseline")
            self.assertIn("Baseline remained the best render", result["improvement"]["plainSummary"])

    def test_reference_run_skips_unverified_candidate_before_render(self) -> None:
        from tools.gt1000 import live, patch_edit
        from tools.gt1000.audio_lab import reference_runner

        candidate = {
            "label": "untrusted",
            "renderLabel": "candidate-01-untrusted",
            "area": "eq1",
            "block": "eq1",
            "parameter": "highGain",
            "value": "72",
            "command": "patch-set",
            "requiresLiveVerification": True,
        }
        candidate_plan = patch_edit.build_parameter_set_plan("eq1", "highGain", "72")

        def fake_original_reads(*, timeout: float, requests: list[live.PatchReadRequest]) -> dict[str, list[int]]:
            return {
                live.address_key(request.address): [64] * live.seven_bit_address_value(request.size)
                for request in requests
            }

        def fake_render(
            session_name: str,
            label: str,
            *,
            prepare_usb: bool,
            midi_timeout: float,
            settle_seconds: float,
            snapshot_patch: bool,
        ) -> dict:
            session_dir = Path(tmp) / session_name
            wet_path = session_dir / "renders" / f"{label}-wet.wav"
            _write_composite_tone(wet_path, frequencies=[220.0, 440.0])
            return {"id": "audioSessionRender", "label": label, "wetPath": str(wet_path)}

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with mock.patch.object(session, "session_root", return_value=directory):
                cmd_generate_tone("skip-test", duration=0.2, frequency=440.0, amplitude=0.2, sample_rate=44100)
                reference = directory / "reference.wav"
                profile_path = directory / "reference-profile.json"
                _write_composite_tone(reference, frequencies=[220.0, 440.0])
                cmd_reference_analyze(reference, output_path=profile_path)
                with mock.patch.object(
                    reference_runner,
                    "plan_reference_candidates",
                    return_value={
                        "id": "audioReferencePlan",
                        "session": "skip-test",
                        "candidateCount": 1,
                        "candidates": [candidate],
                    },
                ), mock.patch.object(
                    reference_runner,
                    "_candidate_patch_plan",
                    return_value=candidate_plan,
                ), mock.patch.object(
                    reference_runner.live,
                    "read_data_sets",
                    side_effect=fake_original_reads,
                ), mock.patch.object(
                    reference_runner,
                    "apply_plan_after_audio",
                    side_effect=[{"verified": False}, {"verified": True}],
                ), mock.patch.object(
                    reference_runner,
                    "render_labeled_wet",
                    side_effect=fake_render,
                ) as render_mock:
                    result = cmd_reference_run(profile_path, session="skip-test", max_candidates=1, verify_writes=False)

            self.assertEqual(result["id"], "audioReferenceRun")
            self.assertEqual(len(result["renders"]), 1)
            self.assertEqual(result["skippedCandidates"][0]["label"], "untrusted")
            self.assertIn("restoreResult", result["skippedCandidates"][0])
            render_mock.assert_called_once()

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
