from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "probe-audio-integrity-v2-public-decoder.py"
SPEC = importlib.util.spec_from_file_location("v2_public_decoder_probe", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublicDecoderProbeTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        plan = MODULE.load_object(
            ROOT
            / "benchmarks"
            / "audio-integrity-v2"
            / "public-decoder-equivalence-plan.json"
        )
        result = (
            ROOT
            / "research"
            / "toolchains"
            / "evidence"
            / "factorial-v2-toolchain-observed-20260802-001-aggregate.json"
        )
        MODULE.validate_plan(plan, result)

    def test_projection_excludes_wrapper_specific_fields(self) -> None:
        report = {
            "schema_version": 1,
            "state": "experimental_measurements_only",
            "public_verdict_enabled": False,
            "input_sha256": "wrapper-specific",
            "analyzed_sample_count": 12,
            "analyzed_duration_seconds": 0.25,
            "truncated_by_limit": False,
            "source_facts": {
                "sample_rate_hz": 48_000,
                "channel_count": 2,
                "declared_bits_per_sample": 16,
                "codec_debug": "wrapper-specific",
                "container_extension": "flac",
            },
            "compression_trace": {"feature_version": 0},
        }
        projection = MODULE.report_projection(report)
        self.assertNotIn("input_sha256", projection)
        self.assertNotIn("codec_debug", projection["source_facts"])
        self.assertNotIn("container_extension", projection["source_facts"])
        self.assertEqual({"feature_version": 0}, projection["compression_trace"])

    def test_public_command_replaces_only_frozen_tokens(self) -> None:
        observed = MODULE.public_command(
            ["<TOOL:ffmpeg_8_1_2_1>", "-i", "<INPUT>", "<OUTPUT>"],
            Path("/ffmpeg"),
            Path("/input.wav"),
            Path("/output.flac"),
        )
        self.assertEqual(
            ["/ffmpeg", "-i", "/input.wav", "/output.flac"], observed
        )

    def test_generated_inputs_cover_mono_and_stereo(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            mono = Path(name) / "mono.wav"
            stereo = Path(name) / "stereo.wav"
            MODULE.BASE.generate_probe_wave(
                mono, sample_rate_hz=44_100, frame_count=100, channel_count=1
            )
            MODULE.BASE.generate_probe_wave(
                stereo, sample_rate_hz=44_100, frame_count=100, channel_count=2
            )
            self.assertEqual(1, MODULE.BASE.wave_pcm_info(mono)["channel_count"])
            self.assertEqual(2, MODULE.BASE.wave_pcm_info(stereo)["channel_count"])


if __name__ == "__main__":
    unittest.main()
