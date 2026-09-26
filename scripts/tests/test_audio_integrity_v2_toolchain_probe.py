from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "probe-audio-integrity-v2-toolchains.py"
SPEC = importlib.util.spec_from_file_location("v2_toolchain_probe", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ToolchainProbeTest(unittest.TestCase):
    def test_integer_probe_wave_is_golden_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            first = Path(name) / "first.wav"
            second = Path(name) / "second.wav"
            for path in (first, second):
                MODULE.generate_probe_wave(
                    path,
                    sample_rate_hz=44100,
                    frame_count=1000,
                )
            self.assertEqual(MODULE.sha256_file(first), MODULE.sha256_file(second))
            self.assertEqual(
                "55f403ef08e1a2ab834b56af355b60a9c6826658db0be100825b78689ba7cfc5",
                MODULE.sha256_file(first),
            )
            info = MODULE.wave_pcm_info(first)
            self.assertEqual(2, info["channel_count"])
            self.assertEqual(2, info["sample_width_bytes"])
            self.assertEqual(44100, info["sample_rate_hz"])
            self.assertEqual(1000, info["frame_count"])

    def test_public_command_replaces_private_locations(self) -> None:
        template = ["{tool}", "--input", "{input}", "--output={output}"]
        self.assertEqual(
            [
                "<TOOL:encoder>",
                "--input",
                "<INPUT>",
                "--output=<OUTPUT>",
            ],
            MODULE.public_command(template, "encoder"),
        )

    def test_integer_probe_wave_supports_mono(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "mono.wav"
            MODULE.generate_probe_wave(
                output,
                sample_rate_hz=48_000,
                frame_count=1000,
                channel_count=1,
            )
            info = MODULE.wave_pcm_info(output)
            self.assertEqual(1, info["channel_count"])
            self.assertEqual(
                "003f31b9da65a60e25c63991fb9bbb39167e0e0f90e1309cbdc02787355c7959",
                MODULE.sha256_file(output),
            )

    def test_path_free_guard_rejects_a_private_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "private path"):
            MODULE.assert_path_free(
                {"command": "/private/tool --version"}, ["/private/tool"]
            )

    def test_cross_decoder_disagreement_is_summarized(self) -> None:
        rows = [
            {
                "encoder_id": "encoder-a",
                "observed": {"pcm_sha256": "a", "frame_count": 10},
            },
            {
                "encoder_id": "encoder-a",
                "observed": {"pcm_sha256": "b", "frame_count": 10},
            },
        ]
        self.assertEqual(
            [
                {
                    "encoder_id": "encoder-a",
                    "decoder_count": 2,
                    "exact_pcm_equivalent_across_decoders": False,
                    "frame_count_equivalent_across_decoders": True,
                }
            ],
            MODULE.summarize_cross_decoder_outputs(rows),
        )

    def test_invalid_hash_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            MODULE.validate_sha256("abc", "fixture")


if __name__ == "__main__":
    unittest.main()
