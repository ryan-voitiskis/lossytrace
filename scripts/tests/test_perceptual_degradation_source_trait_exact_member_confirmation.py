from __future__ import annotations

import copy
import importlib.util
import io
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_exact_member_confirmation.py"
SPEC = importlib.util.spec_from_file_location("source_trait_exact_member_confirmation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_s24_wav(path: Path, samples: list[int], sample_rate: int = 8000) -> None:
    payload = bytearray()
    for value in samples:
        if not -(1 << 23) <= value < (1 << 23):
            raise ValueError("s24 sample out of range")
        payload.extend((value & 0xFFFFFF).to_bytes(3, "little"))
    fmt = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 3, 3, 24)
    riff_bytes = 4 + 8 + len(fmt) + 8 + len(payload)
    path.write_bytes(
        b"RIFF"
        + struct.pack("<I", riff_bytes)
        + b"WAVEfmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(payload))
        + payload
    )


class SourceTraitExactMemberConfirmationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)

    def test_frozen_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_authority_and_exact_member_scope_fail_closed(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["authorization"]["source_trait_assignment_authorized"] = True
        changed["members"].append(copy.deepcopy(changed["members"][0]))
        errors = MODULE.validate_plan(changed)
        self.assertIn(
            "authorization must remain false: source_trait_assignment_authorized",
            errors,
        )
        self.assertIn("exact member inventory differs", errors)

    def test_s32_stream_recovers_exact_s24_codes(self) -> None:
        expected = [-(1 << 23), -3, 0, 4, (1 << 23) - 1]
        payload = b"".join(struct.pack("<i", value << 8) for value in expected)
        observed = [frame[0] for frame in MODULE.iter_s24_frames(io.BytesIO(payload), 1)]
        self.assertEqual(expected, observed)

    def test_nonzero_and_absolute_level_measurement_is_exact(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self.skipTest("ffmpeg is unavailable")
        samples = [0, 3, -4, 0, 5]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quiet.wav"
            write_s24_wav(path, samples)
            probe = {
                "channel_count": 1,
                "sample_rate_hz": 8000,
            }
            member = {"trait_id": "quiet"}
            observed = MODULE.measure_member(
                Path(ffmpeg), path, member, probe, self.plan
            )
        self.assertEqual(observed["frame_count"], 5)
        self.assertEqual(observed["sample_count"], 5)
        self.assertEqual(observed["peak_abs_code"], 5)
        self.assertEqual(observed["sum_squares"], 50)
        self.assertEqual(observed["nonzero_sample_count"], 3)
        self.assertEqual(observed["nonzero_frame_count"], 3)
        self.assertTrue(observed["nonzero_activity_present"])
        self.assertFalse(observed["quiet_classification_threshold_applied"])

    def test_clipping_support_predicate_uses_frozen_events(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self.skipTest("ffmpeg is unavailable")
        peak = (1 << 23) - 1
        samples = [0, peak, peak, peak, 0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clipped.wav"
            write_s24_wav(path, samples)
            observed = MODULE.measure_member(
                Path(ffmpeg),
                path,
                {"trait_id": "clipped"},
                {"channel_count": 1, "sample_rate_hz": 8000},
                self.plan,
            )
        self.assertEqual(observed["exact_rail_sample_count"], 3)
        self.assertEqual(observed["identical_high_magnitude_plateau_run_count"], 1)
        self.assertEqual(observed["maximum_identical_high_magnitude_plateau_frames"], 3)
        self.assertTrue(observed["plateau_or_saturation_support_event_present"])
        self.assertFalse(observed["trait_assignment_made"])

    def test_publication_omits_paths_and_hashes(self) -> None:
        quiet = {
            "nonzero_activity_present": True,
            "rms_dbfs": "-50.000000",
        }
        clipped = {
            "plateau_or_saturation_support_event_present": True,
            "exact_rail_sample_count": 3,
        }
        private = {
            "observations": [
                {
                    "trait_id": "quiet",
                    "encoded_sha256": "a" * 64,
                    "descriptor": quiet,
                },
                {
                    "trait_id": "clipped",
                    "encoded_sha256": "b" * 64,
                    "descriptor": clipped,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = root / "private-replays"
            replay.mkdir()
            payload = MODULE.canonical_json_bytes(private)
            (replay / "replay-1.json").write_bytes(payload)
            (replay / "replay-2.json").write_bytes(payload)
            report = MODULE.public_report(self.plan, root)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("encoded_sha256", serialized)
        self.assertNotIn("private-replays", serialized)
        self.assertNotIn("/Users/", serialized)
        self.assertFalse(report["decision"]["quiet_or_clipped_trait_assigned"])
        self.assertFalse(report["decision"]["public_verdict_enabled"])


if __name__ == "__main__":
    unittest.main()
