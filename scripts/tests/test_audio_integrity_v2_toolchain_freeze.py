from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "freeze-audio-integrity-v2-toolchains.py"
SPEC = importlib.util.spec_from_file_location("v2_toolchain_freeze", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ToolchainFreezeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.factor_path = ROOT / "benchmarks" / "audio-integrity-v2" / "factor-levels.json"
        cls.prior_path = (
            ROOT
            / "research"
            / "toolchains"
            / "evidence"
            / "observed-20260802-001-aggregate.json"
        )
        cls.factor = MODULE.load_object(cls.factor_path)
        cls.manifest = MODULE.build_manifest(
            cls.factor,
            MODULE.load_object(cls.prior_path),
            cls.factor_path,
            cls.prior_path,
        )

    def test_manifest_expands_every_channel_setting_and_decoder_path(self) -> None:
        MODULE.validate_manifest(self.manifest, self.factor)
        self.assertEqual(46, len(self.manifest["expanded_encoder_settings"]))
        decoder_paths = sum(
            setting["codec_family"] in decoder["codec_families"]
            for setting in self.manifest["expanded_encoder_settings"]
            for decoder in self.manifest["history_decoder_bindings"]
        )
        self.assertEqual(126, decoder_paths)

    def test_explicit_lowpass_is_not_silently_applied_to_default_lame(self) -> None:
        settings = {
            row["expanded_setting_id"]: row
            for row in self.manifest["expanded_encoder_settings"]
        }
        explicit = settings["dev-mp3-lame-cbr128-lowpass16k--stereo"]["command"]
        default = settings["dev-mp3-lame-cbr128-default--stereo"]["command"]
        self.assertEqual("16", explicit[explicit.index("--lowpass") + 1])
        self.assertNotIn("--lowpass", default)
        self.assertTrue(
            all(
                row["command"][row["command"].index("--resample") + 1] == "44.1"
                for row in settings.values()
                if row["encoder_id"] == "mp3_lame_4_0"
            )
        )

    def test_native_ogg_commands_bind_serial_offsets(self) -> None:
        native = [
            row
            for row in self.manifest["expanded_encoder_settings"]
            if row["encoder_id"]
            in {"opus_ffmpeg_native_8_1_2", "vorbis_ffmpeg_native_8_1_2"}
        ]
        self.assertEqual(6, len(native))
        self.assertTrue(all("-serial_offset" in row["command"] for row in native))

    def test_native_vorbis_transfer_is_explicitly_stereo_only(self) -> None:
        native_vorbis = [
            row
            for row in self.manifest["expanded_encoder_settings"]
            if row["encoder_id"] == "vorbis_ffmpeg_native_8_1_2"
        ]
        self.assertEqual(2, len(native_vorbis))
        self.assertTrue(
            all(row["channel_treatment_id"] == "stereo" for row in native_vorbis)
        )

    def test_round_ratio_uses_ties_to_even_for_both_signs(self) -> None:
        self.assertEqual(2, MODULE.round_ratio_ties_even(5, 2))
        self.assertEqual(4, MODULE.round_ratio_ties_even(7, 2))
        self.assertEqual(-2, MODULE.round_ratio_ties_even(-5, 2))
        self.assertEqual(-4, MODULE.round_ratio_ties_even(-7, 2))

    def test_pcm_transforms_have_repeatable_golden_hashes(self) -> None:
        samples = [-32768, -1025, -17, -8, -1, 0, 1, 8, 17, 1025, 32767]
        observed = {}
        with tempfile.TemporaryDirectory() as name:
            for transform_id in (
                "gain-minus6db-q31",
                "requantize-12bit-tpdf",
                "alternate-channel-topology",
            ):
                channels, transformed = MODULE.apply_python_transform(
                    transform_id,
                    sample_rate=48_000,
                    channels=1,
                    samples=samples,
                    group_id="golden",
                )
                output = Path(name) / f"{transform_id}.wav"
                MODULE.write_wave(output, 48_000, channels, transformed)
                observed[transform_id] = MODULE.sha256_file(output)
        self.assertEqual(
            {
                "alternate-channel-topology": "b2d70b83eee892babd8ee2692e98bef011f804d31150f6fb457a3b57bdffa7d2",
                "gain-minus6db-q31": "10b2d55dabbd66ab08032d3fa1831af20cabcc348d91230652ea05827efbca12",
                "requantize-12bit-tpdf": "75a22789257a2fcdf9cc67252fb410c423f08ca0e48f3718a2c74b6d77f0df00",
            },
            observed,
        )

    def test_manifest_has_no_private_path_or_scoring_authority(self) -> None:
        serialized = MODULE.json.dumps(self.manifest, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertFalse(self.manifest["benchmark_audio_generated"])
        self.assertFalse(self.manifest["source_groups_assigned"])
        self.assertFalse(self.manifest["scores_opened"])
        self.assertFalse(self.manifest["selection_authorized"])


if __name__ == "__main__":
    unittest.main()
