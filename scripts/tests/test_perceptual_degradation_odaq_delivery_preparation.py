from __future__ import annotations

import importlib.util
import math
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/prepare-perceptual-degradation-odaq-delivery.py"
SPEC = importlib.util.spec_from_file_location("odaq_delivery_preparation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DELIVERY_SCRIPT = ROOT / "scripts/serve-perceptual-degradation-lossless.py"
DELIVERY_SPEC = importlib.util.spec_from_file_location(
    "private_lossless_delivery", DELIVERY_SCRIPT
)
assert DELIVERY_SPEC and DELIVERY_SPEC.loader
DELIVERY = importlib.util.module_from_spec(DELIVERY_SPEC)
sys.modules[DELIVERY_SPEC.name] = DELIVERY
DELIVERY_SPEC.loader.exec_module(DELIVERY)


def chunk(chunk_id: bytes, payload: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")


def wave(chunks: list[bytes]) -> bytes:
    body = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def float_wave(samples: list[float]) -> bytes:
    data = struct.pack(f"<{len(samples)}f", *samples)
    frames = len(samples) // 2
    fmt = struct.pack("<HHIIHHH", 3, 2, 48_000, 384_000, 8, 32, 0)
    return wave([chunk(b"fmt ", fmt), chunk(b"fact", struct.pack("<I", frames)), chunk(b"data", data)])


def extensible_s24_wave(payload: bytes) -> bytes:
    fmt = struct.pack("<HHIIHHHHI", 0xFFFE, 2, 48_000, 288_000, 6, 24, 22, 24, 0)
    fmt += MODULE.PCM_SUBFORMAT_GUID
    return wave([chunk(b"fmt ", fmt), chunk(b"data", payload)])


class OdaqDeliveryPreparationTest(unittest.TestCase):
    def test_committed_preparation_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(MODULE.load_json(MODULE.PLAN)))

    def test_float_projection_is_deterministic_integer_pcm(self) -> None:
        source = float_wave([-1.0, -0.5, -2.0**-32, -0.0, 0.0, 2.0**-32, 0.5, 1.0 - 2.0**-24])
        first, record = MODULE.project_delivery_wav(source)
        second, second_record = MODULE.project_delivery_wav(source)
        self.assertEqual(first, second)
        self.assertEqual(record, second_record)
        self.assertEqual("deterministic_float32_to_signed_int32_nearest_ties_to_even", record["operation"])
        self.assertEqual(32, record["output_bit_depth"])
        self.assertFalse(record["dither_applied"])
        chunks = dict(MODULE._chunks(first))
        self.assertEqual(1, struct.unpack_from("<H", chunks[b"fmt "])[0])
        self.assertEqual(
            [-2147483648, -1073741824, 0, 0, 0, 0, 1073741824, 2147483520],
            list(struct.unpack("<8i", chunks[b"data"])),
        )
        self.assertEqual(
            {
                "sample_rate_hz": 48_000,
                "channel_count": 2,
                "bit_depth": 32,
                "byte_length": len(first),
            },
            DELIVERY.parse_pcm_wav(first),
        )

    def test_extensible_s24_projection_preserves_sample_payload(self) -> None:
        payload = bytes.fromhex("000000ffffff123456abcdef")
        output, record = MODULE.project_delivery_wav(extensible_s24_wave(payload))
        chunks = dict(MODULE._chunks(output))
        self.assertEqual(payload, chunks[b"data"])
        self.assertEqual(1, struct.unpack_from("<H", chunks[b"fmt "])[0])
        self.assertEqual(24, struct.unpack_from("<H", chunks[b"fmt "], 14)[0])
        self.assertEqual("container_canonicalization_payload_unchanged", record["operation"])
        self.assertEqual(24, DELIVERY.parse_pcm_wav(output)["bit_depth"])

    def test_float_projection_rejects_non_finite_and_out_of_range(self) -> None:
        for sample in (math.nan, math.inf, -math.inf, 1.0, -1.0001):
            with self.subTest(sample=sample):
                with self.assertRaisesRegex(ValueError, "non-finite or out-of-range"):
                    MODULE.project_delivery_wav(float_wave([sample, 0.0]))

    def test_rate_channel_and_extensible_mask_are_fail_closed(self) -> None:
        source = bytearray(extensible_s24_wave(b"\0" * 6))
        fmt_start = 20
        struct.pack_into("<I", source, fmt_start + 4, 44_100)
        with self.assertRaisesRegex(ValueError, "48 kHz stereo"):
            MODULE.project_delivery_wav(bytes(source))
        source = bytearray(extensible_s24_wave(b"\0" * 6))
        struct.pack_into("<I", source, fmt_start + 20, 3)
        with self.assertRaisesRegex(ValueError, "extensible WAV fields"):
            MODULE.project_delivery_wav(bytes(source))

    def test_no_live_corpus_command_exists(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('add_parser("convert")', source)
        self.assertNotIn('add_parser("live")', source)
        self.assertNotIn("Application Support", source)

    def test_retained_conversion_and_listening_remain_unauthorized(self) -> None:
        plan = MODULE.load_json(MODULE.PLAN)
        plan["access_boundary"]["retained_reference_conversion_authorized"] = True
        plan["access_boundary"]["listener_response_collection_authorized"] = True
        errors = MODULE.validate_plan(plan)
        self.assertIn(
            "access boundary must remain false: retained_reference_conversion_authorized",
            errors,
        )
        self.assertIn(
            "access boundary must remain false: listener_response_collection_authorized",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
