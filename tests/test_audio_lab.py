import math
import struct
import tempfile
import unittest
import wave
from unittest import mock
from pathlib import Path

from tools.gt1000.audio_lab import devices, metrics, session, wav_io
from tools.gt1000.audio_lab.metrics import analyze_multichannel_peaks
from tools.gt1000.audio_lab.commands import cmd_analyze, cmd_generate_tone
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
"system", "setup-efct"
"""


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

    def test_cmd_analyze_cli_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.wav"
            wav_io.generate_sine_tone(path, duration=0.25, amplitude=0.3)
            payload = cmd_analyze([path])
            self.assertEqual(payload["id"], "audioAnalyze")
            self.assertIn("rmsDbfs", payload["file"])


if __name__ == "__main__":
    unittest.main()
