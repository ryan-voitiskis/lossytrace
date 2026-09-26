from __future__ import annotations

import importlib.util
import json
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/generate-perceptual-degradation-playback-qualification.py"
SPEC = importlib.util.spec_from_file_location("playback_qualification", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
DELIVERY_SCRIPT = ROOT / "scripts/serve-perceptual-degradation-lossless.py"
DELIVERY_SPEC = importlib.util.spec_from_file_location(
    "playback_qualification_delivery", DELIVERY_SCRIPT
)
assert DELIVERY_SPEC and DELIVERY_SPEC.loader
DELIVERY = importlib.util.module_from_spec(DELIVERY_SPEC)
sys.modules[DELIVERY_SPEC.name] = DELIVERY
DELIVERY_SPEC.loader.exec_module(DELIVERY)
VALIDATOR_SCRIPT = ROOT / "scripts/validate-perceptual-degradation-playback-qualification.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "playback_qualification_validator", VALIDATOR_SCRIPT
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


def pcm(path: Path) -> tuple[list[int], int, int]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        frames = source.getnframes()
        values = list(struct.unpack(f"<{frames * channels}h", source.readframes(frames)))
    return values, channels, frames


class PlaybackQualificationTest(unittest.TestCase):
    def test_committed_preparation_plan_validates(self) -> None:
        self.assertEqual([], VALIDATOR.validate(VALIDATOR.load_json(VALIDATOR.PLAN)))

    def test_two_replays_are_byte_identical_and_delivery_valid(self) -> None:
        with tempfile.TemporaryDirectory() as first_root, tempfile.TemporaryDirectory() as second_root:
            first = MODULE.generate(Path(first_root))
            second = MODULE.generate(Path(second_root))
            self.assertEqual(first, second)
            for filename in ("channel-check.wav", "level-calibration.wav"):
                first_value = (Path(first_root) / filename).read_bytes()
                second_value = (Path(second_root) / filename).read_bytes()
                self.assertEqual(first_value, second_value)
                parsed = DELIVERY.parse_pcm_wav(first_value)
                self.assertEqual(48_000, parsed["sample_rate_hz"])
                self.assertEqual(2, parsed["channel_count"])
                self.assertEqual(16, parsed["bit_depth"])
            session = DELIVERY.load_delivery_map(Path(first_root) / "delivery-map.json")
            self.assertEqual(2, len(session.stimuli))
            self.assertEqual(48_000, session.sample_rate_hz)

    def test_channel_fixture_has_distinct_low_level_channels(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            MODULE.generate(Path(root))
            values, channels, frames = pcm(Path(root) / "channel-check.wav")
            self.assertEqual(2, channels)
            self.assertEqual(48_000 * 6, frames)
            left = values[0::2]
            right = values[1::2]
            self.assertNotEqual(left, right)
            expected_peak = 10 ** (-30 / 20)
            self.assertLess(abs(max(map(abs, left)) / 32767 - expected_peak), 1e-4)
            self.assertLess(abs(max(map(abs, right)) / 32767 - expected_peak), 1e-4)

    def test_level_fixture_is_identical_stereo_and_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            MODULE.generate(Path(root))
            values, channels, frames = pcm(Path(root) / "level-calibration.wav")
            self.assertEqual(2, channels)
            self.assertEqual(48_000 * 20, frames)
            left = values[0::2]
            right = values[1::2]
            self.assertEqual(left, right)
            steady = left[48_000 : -48_000]
            rms = math.sqrt(sum(value * value for value in steady) / len(steady)) / 32767
            rms_dbfs = 20 * math.log10(rms)
            self.assertLess(abs(rms_dbfs - (-30.0)), 0.01)
            self.assertLess(max(map(abs, left)) / 32767, 0.062)

    def test_map_keeps_collection_closed_and_paths_private(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            result = MODULE.generate(Path(root))
            delivery_map = json.loads((Path(root) / "delivery-map.json").read_text())
            self.assertFalse(result["human_collection_authorized"])
            self.assertFalse(delivery_map["human_collection_authorized"])
            self.assertFalse(result["private_paths_printed"])
            self.assertTrue(
                all(Path(row["private_audio_path"]).is_absolute() for row in delivery_map["stimuli"])
            )

    def test_human_observation_cannot_be_prematurely_claimed(self) -> None:
        plan = VALIDATOR.load_json(VALIDATOR.PLAN)
        plan["human_observations"]["physical_playback_qualified"] = True
        self.assertIn(
            "human observation must remain pending: physical_playback_qualified",
            VALIDATOR.validate(plan),
        )


if __name__ == "__main__":
    unittest.main()
