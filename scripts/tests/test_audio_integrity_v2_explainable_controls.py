import unittest
from pathlib import Path

import analyze_audio_integrity_v2_explainable_controls as analyzer
import run_audio_integrity_v2_explainable_controls as runner


class AudioIntegrityV2ExplainableControlTest(unittest.TestCase):
    def test_adapter_plan_binds_implementations_and_sealed_inputs(self) -> None:
        root = Path(__file__).resolve().parents[2]
        plan = runner.common.load_object(
            root
            / "benchmarks"
            / "audio-integrity-v2"
            / "explainable-control-adapter-plan.json"
        )
        self.assertEqual(runner.ADAPTER_ID, plan["adapter_id"])
        self.assertEqual(
            "frozen_before_explainable_control_scores_opened", plan["state"]
        )
        self.assertFalse(plan["encoder_transfer_scores_opened"])
        self.assertFalse(plan["external_transfer_scores_opened"])
        self.assertFalse(plan["public_verdict_enabled"])
        self.assertEqual(
            runner.UPSTREAM_CHECKPOINT_COMMIT, plan["upstream_checkpoint_commit"]
        )
        bindings = plan["bindings"]
        repo_bindings = {
            "adapter_runner_sha256": root
            / "scripts"
            / "run_audio_integrity_v2_explainable_controls.py",
            "adapter_analyzer_sha256": root
            / "scripts"
            / "analyze_audio_integrity_v2_explainable_controls.py",
            "adapter_tests_sha256": Path(__file__).resolve(),
            "adapter_preregistration_sha256": root
            / "docs"
            / "research"
            / "explainable-control-v2-adapter-preregistration-20260803.md",
            "parent_development_baseline_plan_sha256": root
            / "benchmarks"
            / "audio-integrity-v2"
            / "development-baseline-plan.json",
            "common_module_sha256": Path(runner.common.__file__).resolve(),
            "frozen_exact_hybrid_helper_sha256": root
            / "scripts"
            / "run-audio-integrity-exact-hybrid-ablation.py",
            "frozen_codec_projection_helper_sha256": root
            / "scripts"
            / "run-audio-integrity-codec-projection.py",
            "exact_hybrid_oracle_source_sha256": root
            / "research"
            / "exact-transform"
            / "ablation-v1"
            / "src"
            / "main.rs",
            "exact_hybrid_cargo_toml_sha256": root
            / "research"
            / "exact-transform"
            / "ablation-v1"
            / "Cargo.toml",
            "exact_hybrid_cargo_lock_sha256": root
            / "research"
            / "exact-transform"
            / "ablation-v1"
            / "Cargo.lock",
            "codec_projection_oracle_source_sha256": root
            / "research"
            / "codec-projection"
            / "oracle-v1"
            / "src"
            / "main.rs",
            "codec_projection_cargo_toml_sha256": root
            / "research"
            / "codec-projection"
            / "oracle-v1"
            / "Cargo.toml",
            "codec_projection_cargo_lock_sha256": root
            / "research"
            / "codec-projection"
            / "oracle-v1"
            / "Cargo.lock",
            "codec_projection_config_sha256": root
            / "research"
            / "codec-projection"
            / "oracle-v1"
            / "config.json",
        }
        for key, path in repo_bindings.items():
            self.assertEqual(bindings[key], runner.common.sha256_file(path), key)
        for key in (
            "private_analysis_manifest_sha256",
            "private_constructor_manifest_sha256",
            "private_feature_v0_report_sha256",
        ):
            self.assertRegex(bindings[key], r"^[0-9a-f]{64}$")
        self.assertEqual(runner.MAXIMUM_WORKERS, plan["execution"]["maximum_concurrent_workers"])
        self.assertEqual(
            analyzer.MINIMUM_DIRECTION_RATE,
            plan["fixed_analysis"]["minimum_positive_direction_rate"],
        )
        self.assertEqual(
            analyzer.MINIMUM_DIRECTION_WILSON_LOWER,
            plan["fixed_analysis"]["minimum_one_sided_95_percent_wilson_lower"],
        )

    def test_scope_keeps_all_negatives_and_only_mp3_positives(self) -> None:
        rows = [
            {
                "case_id": "negative",
                "expectation": "negative",
                "codec_family": "pcm",
            },
            {
                "case_id": "mp3",
                "expectation": "controlled_positive",
                "codec_family": "mp3",
            },
            {
                "case_id": "aac",
                "expectation": "controlled_positive",
                "codec_family": "aac",
            },
        ]
        selected = runner.select_scope(rows, enforce_frozen_inventory=False)
        self.assertEqual(["mp3", "negative"], [row["case_id"] for row in selected])

    def test_scoped_representatives_are_stable_per_pcm_and_wrapper(self) -> None:
        rows = [
            {
                "case_id": "z",
                "_analysis_pcm_sha256": "p",
                "lossless_wrapper_id": "wav",
            },
            {
                "case_id": "a",
                "_analysis_pcm_sha256": "p",
                "lossless_wrapper_id": "wav",
            },
            {
                "case_id": "b",
                "_analysis_pcm_sha256": "p",
                "lossless_wrapper_id": "flac",
            },
        ]
        selected = runner.scoped_representatives(
            rows, enforce_frozen_inventory=False
        )
        self.assertEqual(["a", "b"], [row["case_id"] for row in selected])

    def test_exact_measurement_removes_identity_and_timing(self) -> None:
        aggregate = {
            field: index / 10.0
            for index, field in enumerate(runner.EXACT_SCORE_FIELDS.values(), 1)
        }
        measurement, elapsed = runner.normalized_exact_measurement(
            "case-a",
            {
                "schema_version": 2,
                "feature_version": 0,
                "case_id": "case-a",
                "algorithm": runner.LEGACY_EXACT.ALGORITHM,
                "public_verdict_enabled": False,
                "phase_offsets_samples": runner.LEGACY_EXACT.EXPECTED_PHASE_OFFSETS,
                "elapsed_ms": 12.5,
                "aggregate": aggregate,
            },
        )
        self.assertEqual(12.5, elapsed)
        self.assertNotIn("case_id", measurement["probe_without_identity_or_timing"])
        self.assertNotIn("elapsed_ms", measurement["probe_without_identity_or_timing"])
        self.assertTrue(all(measurement["support"].values()))

    def test_projection_formula_is_replayed_before_normalization(self) -> None:
        config = runner.LEGACY_PROJECTION.load_and_validate_config(
            runner.ROOT
            / "research"
            / "codec-projection"
            / "oracle-v1"
            / "config.json"
        )
        probe = {
            "schema_version": 1,
            "state": "codec_projection_raw_case_v1",
            "feature_version": 0,
            "public_verdict_enabled": False,
            "case_id": "case-a",
            "algorithm": config["algorithm"],
            "projection_performed": True,
            "support": {
                "supported": True,
                "supported_measurement_block_count": 1,
            },
            "scores": {
                "r1_cycle_residual_retention": 0.5,
                "r1_interquartile_range": 0.0,
                "r1_equivalent_db_median": 0.0,
                "r2_residual_directional_recurrence": 0.6,
                "r2_interquartile_range": 0.0,
            },
            "blocks": [
                {
                    "block_index": 0,
                    "signal_power": 0.1,
                    "first_residual_power": 0.01,
                    "second_residual_power": 0.01,
                    "r1_cycle_residual_retention": 0.5,
                    "r1_equivalent_db": 0.0,
                    "r2_residual_directional_recurrence": 0.6,
                }
            ],
        }
        measurement = runner.normalized_projection_measurement(
            "case-a", probe, config["algorithm"]
        )
        self.assertEqual({"R1": 0.5, "R2": 0.6}, measurement["scores"])
        probe["blocks"][0]["r1_cycle_residual_retention"] = 0.4
        with self.assertRaisesRegex(ValueError, "formula replay"):
            runner.normalized_projection_measurement(
                "case-a", probe, config["algorithm"]
            )

    def test_wrapper_invariance_ignores_identity_but_not_measurement(self) -> None:
        measurement = runner.unsupported_exact_measurement()
        rows = [
            {
                "analysis_pcm_sha256": "p",
                "lossless_wrapper_id": "wav",
                "measurement": measurement,
            },
            {
                "analysis_pcm_sha256": "p",
                "lossless_wrapper_id": "flac",
                "measurement": measurement,
            },
        ]
        result = runner.assert_wrapper_invariance(
            rows, enforce_frozen_inventory=False
        )
        self.assertTrue(result["exact_wrapper_invariance_passed"])
        changed = runner.unsupported_exact_measurement()
        changed["unsupported_reason"] = "different"
        rows[1]["measurement"] = changed
        with self.assertRaisesRegex(ValueError, "wrapper invariance failed"):
            runner.assert_wrapper_invariance(
                rows, enforce_frozen_inventory=False
            )

    def test_correlations_use_average_ranks_and_handle_constants(self) -> None:
        result = analyzer.correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0])
        self.assertAlmostEqual(-1.0, result["pearson"])
        self.assertAlmostEqual(-1.0, result["spearman"])
        constant = analyzer.correlation([1.0, 1.0], [2.0, 3.0])
        self.assertIsNone(constant["pearson"])
        self.assertIsNone(constant["spearman"])


if __name__ == "__main__":
    unittest.main()
