from __future__ import annotations

import copy
import importlib.util
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v2.py"
SPEC = importlib.util.spec_from_file_location("sparse_non_tonal_exact_confirmation_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def float_wav_bytes(channels: list[list[float]], sample_rate: int, extensible: bool = False) -> bytes:
    channel_count = len(channels)
    frame_count = len(channels[0])
    payload = bytearray()
    for frame in range(frame_count):
        for channel in channels:
            payload.extend(struct.pack("<f", channel[frame]))
    block_align = channel_count * 4
    if extensible:
        fmt = struct.pack(
            "<HHIIHHHHI16s",
            0xFFFE,
            channel_count,
            sample_rate,
            sample_rate * block_align,
            block_align,
            32,
            22,
            32,
            3,
            MODULE.FLOAT_SUBFORMAT_GUID,
        )
    else:
        fmt = struct.pack("<HHIIHH", 3, channel_count, sample_rate, sample_rate * block_align, block_align, 32)
    padded = bytes(payload) + (b"\0" if len(payload) & 1 else b"")
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(payload)) + padded
    return b"RIFF" + struct.pack("<I", len(body)) + body


def sparse_noise(frame_count: int) -> list[float]:
    values = [0.0] * frame_count
    state = 0x12345678
    for index in range(frame_count // 10):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        values[index] = (((state >> 8) & 0xFFFF) - 32768) / 32768.0
    return values


class SparseNonTonalExactMemberConfirmationV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)

    def test_committed_plan_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_float_parser_supports_direct_and_extensible_formats(self) -> None:
        channels = [[-1.0, 0.0, 0.5], [1.0, -0.5, 0.25]]
        for extensible in (False, True):
            facts, decoded, pcm = MODULE.parse_ieee_float_pcm_wav(float_wav_bytes(channels, 8000, extensible))
            self.assertEqual("ieee_float_pcm", facts["sample_format"])
            self.assertEqual(2, facts["channel_count"])
            self.assertEqual(3, facts["frame_count"])
            self.assertEqual(channels, decoded)
            self.assertEqual(24, len(pcm))

    def test_nonfinite_float_and_integer_pcm_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-finite"):
            MODULE.parse_ieee_float_pcm_wav(float_wav_bytes([[math.nan], [0.0]], 8000))
        encoded = bytearray(float_wav_bytes([[0.0], [0.0]], 8000))
        struct.pack_into("<H", encoded, 20, 1)
        with self.assertRaisesRegex(ValueError, "not IEEE float"):
            MODULE.parse_ieee_float_pcm_wav(bytes(encoded))

    def test_frozen_descriptor_passes_focused_sparse_noise_fixture(self) -> None:
        sample_rate = 8000
        samples = sparse_noise(sample_rate * 4)
        encoded = float_wav_bytes([samples, samples], sample_rate)
        record = copy.deepcopy(self.plan["member"])
        record["expected_container"] = {
            "bits_per_sample": 32,
            "channel_count": 2,
            "duration_seconds_maximum": "4.000001",
            "duration_seconds_minimum": "3.999999",
            "sample_format": "ieee_float_pcm",
            "sample_rate_hz": sample_rate,
        }
        descriptor = MODULE._load_module(MODULE._binding_path(self.plan, "descriptor_implementation"), "descriptor_test_v2")
        measurement, _ = MODULE._measure(descriptor, record, encoded)
        self.assertTrue(measurement["descriptor_confirmation_passed"])
        self.assertEqual("passed", measurement["terminal_outcome"])

    def test_two_replay_and_public_redaction_plumbing(self) -> None:
        private_payload = {
            "report_id": MODULE.REPORT_ID + "-private-replay",
            "schema_version": 1,
            "source_observation": {
                "attribution": self.plan["member"]["attribution"],
                "encoded_sha256": "1" * 64,
                "exact_member_id": "freesound_sound_703342",
                "licence": "CC0 1.0",
                "measurement": {
                    "all_supported_channels_agree": True,
                    "channel_descriptors": [{"sparse_non_tonal_contrast": True, "abstain": False}],
                    "container": {"frame_count": 1},
                    "descriptor_confirmation_passed": True,
                    "expected_descriptor_class": "sparse_non_tonal_contrast",
                    "terminal_outcome": "passed",
                },
                "pcm_sha256": "2" * 64,
                "provider_id": "freesound",
                "provider_record_url": self.plan["member"]["provider_record_url"],
            },
        }
        original = MODULE._private_replay
        MODULE._private_replay = lambda plan, descriptor, provider_original: private_payload
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "provider-original.wav"
                source.write_bytes(b"fixture")
                private = root / "private"
                public = root / "public.json"
                report = MODULE.run(self.plan, MODULE.PLAN_PATH, source, private, public)
                self.assertEqual((private / "private-replay-a.json").read_bytes(), (private / "private-replay-b.json").read_bytes())
                self.assertTrue((private / "source-attribution.json").is_file())
                public_text = public.read_text()
                self.assertNotIn(str(root), public_text)
                self.assertNotIn("encoded_sha256", public_text)
                self.assertNotIn("pcm_sha256", public_text)
                self.assertNotIn("channel_descriptors", public_text)
                self.assertTrue(report["decision"]["descriptor_confirmation_passed"])
        finally:
            MODULE._private_replay = original

    def test_tampered_member_and_open_verdict_fail_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["member"]["exact_member_id"] = "freesound_sound_856645"
        tampered["authorization"]["public_verdict_enabled"] = True
        errors = MODULE.validate_plan(tampered)
        self.assertIn("exact member differs", errors)
        self.assertIn("authorization differs: public_verdict_enabled", errors)

    def test_public_redaction_rejects_private_measurements(self) -> None:
        with self.assertRaisesRegex(ValueError, "channel_descriptors"):
            MODULE._validate_public_redaction({"channel_descriptors": []})
        with self.assertRaisesRegex(ValueError, "path-like"):
            MODULE._validate_public_redaction({"value": "/private/source.wav"})


if __name__ == "__main__":
    unittest.main()
