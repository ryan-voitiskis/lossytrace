from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audio_integrity_v2_preconditioning.py"
AUDIT_PATH = ROOT / "scripts" / "audit-audio-integrity-v2-preconditioning.py"
PLAN_PATH = (
    ROOT / "benchmarks" / "audio-integrity-v2" / "preconditioning-audit-plan.json"
)


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = import_script("v2_preconditioning_test", MODULE_PATH)
AUDIT = import_script("v2_preconditioning_audit_test", AUDIT_PATH)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class AudioIntegrityV2PreconditioningTest(unittest.TestCase):
    def test_plan_is_synthetic_only_and_binds_exact_modules(self) -> None:
        self.assertEqual(
            "preconditioning_audit_frozen_before_synthetic_replay", PLAN["state"]
        )
        self.assertFalse(PLAN["benchmark_source_audio_read"])
        self.assertFalse(PLAN["benchmark_audio_generated"])
        self.assertFalse(PLAN["construction_authorized"])
        self.assertEqual(
            AUDIT.sha256_file(MODULE_PATH),
            PLAN["bindings"]["preconditioning_module_sha256"],
        )
        self.assertEqual(
            AUDIT.sha256_file(AUDIT_PATH),
            PLAN["bindings"]["audit_generator_sha256"],
        )

    def test_short_provider_window_is_not_shifted_or_padded(self) -> None:
        self.assertEqual(
            (25, 125),
            MODULE.identity_hashed_excerpt_bounds(
                group_id="group",
                member_id="member",
                provider_start_frame=25,
                provider_end_frame_exclusive=125,
                native_sample_rate_hz=10,
            ),
        )

    def test_long_excerpt_is_exact_and_within_provider_window(self) -> None:
        start, end = MODULE.identity_hashed_excerpt_bounds(
            group_id="group",
            member_id="member",
            provider_start_frame=25,
            provider_end_frame_exclusive=225,
            native_sample_rate_hz=10,
        )
        self.assertGreaterEqual(start, 25)
        self.assertLessEqual(end, 225)
        self.assertEqual(120, end - start)

    def test_binary64_quantization_is_ties_even_and_saturating(self) -> None:
        self.assertEqual(0, MODULE.quantize_f64_to_s16(0.5 / 32768))
        self.assertEqual(2, MODULE.quantize_f64_to_s16(1.5 / 32768))
        self.assertEqual(32767, MODULE.quantize_f64_to_s16(1.0))
        self.assertEqual(-32768, MODULE.quantize_f64_to_s16(-1.0))

    def test_filter_graph_preserves_frozen_operation_order(self) -> None:
        graph = MODULE.preconditioning_filter_graph(
            excerpt_start_frame=100,
            excerpt_end_frame_exclusive=1000,
            native_channel_count=2,
            native_sample_rate_hz=44100,
            channel_treatment_id="mono",
            target_sample_rate_hz=48000,
        )
        self.assertLess(graph.index("atrim="), graph.index("pan=mono"))
        self.assertLess(graph.index("pan=mono"), graph.index("aresample=48000"))
        self.assertIn("dither_method=none", graph)

    def test_public_evidence_rejects_private_identity_and_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "private key"):
            AUDIT.assert_public_path_free({"group_id": "private"})
        with self.assertRaisesRegex(ValueError, "private path"):
            AUDIT.assert_public_path_free({"note": "/private/audio.wav"})


if __name__ == "__main__":
    unittest.main()
