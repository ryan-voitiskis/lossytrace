from __future__ import annotations

import importlib.util
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run-perceptual-degradation-odaq-retained-drift-validation.py"
SPEC = importlib.util.spec_from_file_location("odaq_retained_drift_runner", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

try:
    import numpy as NUMPY
except ImportError:
    NUMPY = None


def chunk(chunk_id: bytes, payload: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")


def canonical_wave(samples: list[int], bits: int) -> bytes:
    channels = 2
    if bits == 32:
        payload = struct.pack(f"<{len(samples)}i", *samples)
    else:
        payload = b"".join((value & 0xFFFFFF).to_bytes(3, "little") for value in samples)
    block_align = channels * (bits // 8)
    fmt = struct.pack(
        "<HHIIHH", 1, channels, 48_000, 48_000 * block_align, block_align, bits
    )
    body = b"WAVE" + chunk(b"fmt ", fmt) + chunk(b"data", payload)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def small_protocol() -> dict:
    return {
        "protocol_id": "synthetic-test",
        "source_sample_rate_hz": 2_000,
        "actual_drift_ppm_cases": [75, -60, 0, 20, -20, 100, -100],
        "candidate_drift_ppm_minimum": -100,
        "candidate_drift_ppm_maximum": 100,
        "candidate_drift_ppm_step": 5,
        "window_frame_count": 2_000,
        "window_start_frames": [2_000 * value for value in range(1, 11)],
        "training_window_positions": [0, 2, 4, 6, 8],
        "held_out_window_positions": [1, 3, 5, 7, 9],
        "minimum_channel_window_rms": 0.000001,
        "minimum_eligible_training_windows_per_channel": 3,
        "minimum_eligible_held_out_windows_per_channel": 3,
        "insufficient_energy_action": "abstain_insufficient_signal_support",
        "minimum_selection_margin": 0.0001,
        "minimum_held_out_correlation_after_correction": 0.99,
        "minimum_held_out_correlation_improvement_to_apply": 0.05,
        "mandatory_discard_frames_each_edge_when_applied": 64,
    }


def synthetic_gate_case(source: str, ppm: int) -> dict:
    apply = ppm != 0
    return {
        "source_opaque_reference_id": source,
        "actual_drift_ppm": ppm,
        "decision": {
            "state": "supported",
            "selected_correction_ppm": ppm,
            "selection_margin": 0.001,
            "held_out_mean_correlation_after_proxy": 0.9999,
            "held_out_mean_correlation_improvement_proxy": 0.1,
            "apply_correction": apply,
            "support": {"abstention_reason": None},
        },
        "output_bit_exact_to_observed": not apply,
        "channel_core_metrics": [
            {
                "correlation_after": 0.9999,
                "correlation_improvement": 0.02,
            },
            {
                "correlation_after": 0.9999,
                "correlation_improvement": 0.02,
            },
        ],
        "score_free_oracle": {
            "metric_execution_states": ["not_authorized"],
            "impairment_severity": None,
            "audibility_probability": None,
        },
        "derived_pcm_retained": False,
        "provider_processed_condition_accessed": False,
        "provider_listening_score_accessed": False,
        "actual_codec_generated": False,
        "perceptual_metric_executed": False,
        "human_playback_performed": False,
        "human_response_accessed": False,
        "sealed_evidence_opened": False,
        "no_reference_training_performed": False,
        "public_verdict_enabled": False,
    }


class OdaqRetainedDriftValidationRunnerTest(unittest.TestCase):
    def test_resume_accepts_an_existing_private_replay_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "replay"
            root.mkdir()
            (root / "journal.json").write_text("{}", encoding="utf-8")
            MODULE.ensure_replay_root(root, resume=True)
            self.assertTrue((root / "journal.json").is_file())
            with self.assertRaises(FileExistsError):
                MODULE.ensure_replay_root(root, resume=False)

    def test_recovery_predecessor_binding_must_be_explicit(self) -> None:
        authorization = {
            "authorization_id": "authorization",
            "authorization_scope": {"retained_inventory_sha256": "inventory"},
        }
        protocol = {"protocol_id": "protocol"}
        predecessor = ("a" * 40, "https://github.com/example/actions/runs/1")
        current = ("b" * 40, "https://github.com/example/actions/runs/2")
        journal = {
            "protocol_id": "protocol",
            "authorization_id": "authorization",
            "authorization_sha256": "authorization-sha",
            "authorization_head_commit": MODULE.AUTHORIZATION_HEAD,
            "runner_head_commit": predecessor[0],
            "runner_exact_head_ci_url": predecessor[1],
            "input_inventory_sha256": "inventory",
            "cases": [],
        }
        with self.assertRaisesRegex(ValueError, "runner binding differs"):
            MODULE.require_recovery_binding(
                journal,
                authorization=authorization,
                authorization_sha256="authorization-sha",
                protocol=protocol,
                runner_head=current[0],
                runner_ci_url=current[1],
            )
        self.assertEqual(
            [],
            MODULE.require_recovery_binding(
                journal,
                authorization=authorization,
                authorization_sha256="authorization-sha",
                protocol=protocol,
                runner_head=current[0],
                runner_ci_url=current[1],
                accepted_runner_bindings=[predecessor],
            ),
        )

    def test_exact_runner_head_requires_matching_clean_checkout(self) -> None:
        head = "a" * 40
        url = "https://github.com/ryan-voitiskis/lossytrace/actions/runs/123"
        with mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=[
                SimpleNamespace(stdout=f"{head}\n"),
                SimpleNamespace(stdout=b""),
            ],
        ):
            MODULE.require_exact_runner_head(head, url)
        with mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=[
                SimpleNamespace(stdout=f"{head}\n"),
                SimpleNamespace(stdout=b" M file"),
            ],
        ):
            with self.assertRaisesRegex(ValueError, "worktree must be clean"):
                MODULE.require_exact_runner_head(head, url)

    def test_committed_authorization_is_exact_and_narrow(self) -> None:
        authorization, plan, digest = MODULE.require_committed_authorization()
        self.assertEqual(64, len(digest))
        self.assertEqual(16, authorization["authorization_scope"]["retained_reference_count"])
        self.assertTrue(authorization["authorization_scope"]["retained_reference_access_authorized"])
        self.assertTrue(
            authorization["authorization_scope"]["controlled_synthetic_clock_drift_generation_authorized"]
        )
        self.assertFalse(authorization["authorization_scope"]["retained_derived_audio_authorized"])
        self.assertEqual(112, 16 * len(plan["validation_protocol"]["actual_drift_ppm_cases"]))

    def test_canonical_integer_pcm_decoding(self) -> None:
        int32 = MODULE.decode_canonical_segment(
            canonical_wave([-(1 << 31), -1, 0, (1 << 31) - 1], 32), 2
        )
        self.assertEqual([-1.0, 0.0], int32[0])
        self.assertAlmostEqual(-1 / (1 << 31), int32[1][0])
        self.assertAlmostEqual(1 - 1 / (1 << 31), int32[1][1])
        int24 = MODULE.decode_canonical_segment(
            canonical_wave([-(1 << 23), -1, 0, (1 << 23) - 1], 24), 2
        )
        self.assertEqual([-1.0, 0.0], int24[0])
        self.assertAlmostEqual(-1 / (1 << 23), int24[1][0])
        self.assertAlmostEqual(1 - 1 / (1 << 23), int24[1][1])

    def test_scalar_estimator_selects_frozen_nonzero_and_zero_cases(self) -> None:
        protocol = small_protocol()
        reference = MODULE.ESTIMATOR.integration._reference_channels(2_000, 12)
        for ppm, expected_apply in ((75, True), (0, False), (20, False)):
            with self.subTest(ppm=ppm):
                observed = [MODULE.apply_drift_scalar(channel, ppm) for channel in reference]
                decision, _ = MODULE.estimate_decision(
                    reference, observed, protocol, np=None
                )
                self.assertEqual("supported", decision["state"])
                self.assertEqual(ppm, decision["selected_correction_ppm"])
                self.assertIs(expected_apply, decision["apply_correction"])
                self.assertFalse(decision["selection_used_held_out_windows"])

    def test_insufficient_energy_abstains_before_selection(self) -> None:
        protocol = small_protocol()
        reference = [[0.0] * 24_000, [0.0] * 24_000]
        decision, proxy = MODULE.estimate_decision(reference, reference, protocol, np=None)
        self.assertEqual("abstained", decision["state"])
        self.assertEqual(
            "abstain_insufficient_signal_support",
            decision["support"]["abstention_reason"],
        )
        self.assertIsNone(decision["selected_correction_ppm"])
        self.assertFalse(decision["apply_correction"])
        self.assertIsNone(proxy)

    @unittest.skipIf(NUMPY is None, "NumPy proxy backend is not installed")
    def test_single_thread_numpy_proxy_matches_scalar_decisions(self) -> None:
        protocol = small_protocol()
        reference = MODULE.ESTIMATOR.integration._reference_channels(2_000, 12)
        for ppm in (75, -60, 0, 20, -20, 100, -100):
            with self.subTest(ppm=ppm):
                observed = [MODULE.apply_drift_scalar(channel, ppm) for channel in reference]
                scalar, _ = MODULE.estimate_decision(reference, observed, protocol, np=None)
                vector, _ = MODULE.estimate_decision(reference, observed, protocol, np=NUMPY)
                self.assertEqual(scalar["selected_correction_ppm"], vector["selected_correction_ppm"])
                self.assertEqual(scalar["apply_correction"], vector["apply_correction"])
                self.assertLessEqual(
                    abs(
                        scalar["held_out_mean_correlation_after_proxy"]
                        - vector["held_out_mean_correlation_after_proxy"]
                    ),
                    1e-10,
                )

    @unittest.skipIf(NUMPY is None, "NumPy alignment backend is not installed")
    def test_single_thread_numpy_alignment_matches_frozen_alignment(self) -> None:
        reference = MODULE.ESTIMATOR.integration._reference_channels(2_000, 12)
        scalar = MODULE.ALIGNMENT.align_channels(
            reference_channels=reference,
            test_channels=reference,
            reference_channel_map=["L", "R"],
            test_channel_map=["L", "R"],
            sample_rate_hz=2_000,
            recipe_identity="alignment-equivalence",
        )
        vector = MODULE.align_channels_vectorized(
            np=NUMPY,
            reference_channels=reference,
            test_channels=reference,
            sample_rate_hz=2_000,
            recipe_identity="alignment-equivalence",
        )
        self.assertEqual(scalar["status"], vector["status"])
        self.assertEqual(scalar["support"], vector["support"])
        self.assertEqual(
            scalar["alignment"]["integer_delay_samples"],
            vector["alignment"]["integer_delay_samples"],
        )
        for field in (
            "fractional_delay_samples",
            "clock_drift_ppm",
            "minimum_correlation",
            "minimum_ambiguity_margin",
            "edge_trim_seconds",
            "channel_lag_spread_samples",
            "structural_residual_samples",
            "minimum_structural_window_correlation",
        ):
            with self.subTest(field=field):
                self.assertAlmostEqual(
                    scalar["alignment"][field],
                    vector["alignment"][field],
                    places=12,
                )

    def test_predeclared_gate_audit_passes_exact_16_by_7_inventory(self) -> None:
        plan = MODULE.load_json(MODULE.PLAN)
        cases = [
            synthetic_gate_case(f"source-{source:02d}", ppm)
            for source in range(16)
            for ppm in plan["validation_protocol"]["actual_drift_ppm_cases"]
        ]
        gates = MODULE.gate_audit(cases, plan)
        self.assertEqual(13, len(gates))
        self.assertEqual(
            set(plan["predeclared_future_gates"])
            - {
                "exact_source_inventory_reverified",
                "fresh_replay_count",
                "fresh_replay_reports_must_be_byte_identical",
                "public_report_must_exclude_paths_per_reference_hashes_and_audio",
            },
            set(gates),
        )
        self.assertTrue(all(gates.values()))
        self.assertTrue(MODULE.closed_surfaces_remain_closed(cases))
        cases[0]["perceptual_metric_executed"] = True
        self.assertFalse(MODULE.closed_surfaces_remain_closed(cases))

    def test_recovery_inventory_must_be_an_exact_case_prefix(self) -> None:
        records = [
            {"opaque_reference_id": "source-00"},
            {"opaque_reference_id": "source-01"},
        ]
        protocol = {"actual_drift_ppm_cases": [75, -60, 0]}
        cases = [
            {"source_opaque_reference_id": "source-00", "actual_drift_ppm": 75},
            {"source_opaque_reference_id": "source-00", "actual_drift_ppm": -60},
        ]
        MODULE.require_case_prefix(cases, records, protocol)
        cases.append(
            {"source_opaque_reference_id": "source-01", "actual_drift_ppm": 75}
        )
        with self.assertRaisesRegex(ValueError, "case prefix differs"):
            MODULE.require_case_prefix(cases, records, protocol)

    def test_runner_has_no_private_path_or_retained_audio_output(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Application Support", source)
        self.assertNotIn("/Users/", source)
        self.assertNotIn("write_wav", source)
        self.assertNotIn("decodeAudioData", source)


if __name__ == "__main__":
    unittest.main()
