from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_audio_integrity_v2_fixed_baselines as analysis
import audio_integrity_v2_baseline_common as common
import run_audio_integrity_v2_fixed_baselines as fixed
import train_audio_integrity_v2_crnn_baseline as crnn


PLAN_PATH = (
    ROOT / "benchmarks" / "audio-integrity-v2" / "development-baseline-plan.json"
)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
CRNN_EVIDENCE_PATH = (
    ROOT
    / "research"
    / "baselines"
    / "v2"
    / "evidence"
    / "crnn-observed-20260802-001-aggregate.json"
)


class AudioIntegrityV2DevelopmentBaselineTest(unittest.TestCase):
    def test_plan_binds_every_executable_baseline_component(self) -> None:
        bindings = PLAN["bindings"]
        for key, path in (
            ("common_module_sha256", Path(common.__file__)),
            ("fixed_baseline_runner_sha256", Path(fixed.__file__)),
            ("fixed_baseline_analyzer_sha256", Path(analysis.__file__)),
            (
                "crnn_runner_sha256",
                SCRIPTS / "train_audio_integrity_v2_crnn_baseline.py",
            ),
            (
                "crnn_analyzer_sha256",
                SCRIPTS / "analyze_audio_integrity_v2_crnn_baselines.py",
            ),
            (
                "crnn_requirements_sha256",
                ROOT / "research" / "baselines" / "v2" / "crnn-requirements.txt",
            ),
        ):
            self.assertEqual(common.sha256_file(path), bindings[key])

    def test_plan_keeps_transfer_sealed_and_freezes_model(self) -> None:
        self.assertEqual(
            "mechanism_development_baselines_frozen_before_waveform_decode",
            PLAN["state"],
        )
        self.assertFalse(PLAN["encoder_transfer_scores_opened"])
        self.assertFalse(PLAN["external_transfer_scores_opened"])
        self.assertFalse(PLAN["public_verdict_enabled"])
        model = PLAN["baselines"]["koops_style_crnn_replication"]
        self.assertEqual(crnn.MODEL_DEFINITION_SHA256, model["model_definition_sha256"])
        self.assertEqual(0.5, model["fixed_boundary"])
        self.assertFalse(model["source_paired_loss_enabled"])

    def test_cannam_published_rule_is_exact(self) -> None:
        result = fixed.parse_cannam(
            "0.000: 0.49 Original\n0.100: 0.50 Lossy\n0.200: 0.90 Lossy\n"
        )
        self.assertEqual(3, result["window_count"])
        self.assertEqual(2 / 3, result["positive_window_fraction"])
        self.assertTrue(result["fixed_binary_label"])
        self.assertEqual(0.5, fixed.WINDOW_THRESHOLD)
        self.assertEqual(0.25, fixed.FILE_THRESHOLD)

    def test_wrapper_invariance_is_exact(self) -> None:
        base = {
            "analysis_pcm_sha256": "a" * 64,
            "result": {
                "window_count": 2,
                "window_score_mean": 0.5,
                "window_score_median": 0.5,
                "window_score_p90": 0.9,
                "positive_window_fraction": 0.5,
                "fixed_binary_label": True,
            },
        }
        rows = [
            {**base, "lossless_wrapper_id": "wav16"},
            {**base, "lossless_wrapper_id": "flac16"},
        ]
        report = fixed.assert_wrapper_invariance(fixed.CANNAM_BASELINE, rows)
        self.assertTrue(report["exact_wrapper_invariance_passed"])
        rows[1] = {
            **rows[1],
            "result": {**rows[1]["result"], "positive_window_fraction": 1.0},
        }
        with self.assertRaisesRegex(ValueError, "wrapper invariance"):
            fixed.assert_wrapper_invariance(fixed.CANNAM_BASELINE, rows)

    def test_paired_effect_collapses_duplicate_pcm_pairs_by_source_group(self) -> None:
        reference = {
            "case_id": "ref",
            "expectation": "negative",
            "_analysis_pcm_sha256": "a",
            "source_group": "group-a",
        }
        positive = {
            "case_id": "positive-a",
            "reference_case_id": "ref",
            "expectation": "controlled_positive",
            "_analysis_pcm_sha256": "b",
            "source_group": "group-a",
            "source_domain": "music",
            "codec_family": "mp3",
            "encoder_lineage_id": "lame",
            "encoder_setting_id": "setting",
            "post_transform_ids": [],
        }
        duplicate = {**positive, "case_id": "positive-b"}
        result = common.paired_effects(
            [reference, positive, duplicate], {"a": 0.1, "b": 0.8}
        )
        self.assertEqual(1, result["overall"]["unique_pcm_pair_count"])
        self.assertEqual(1, result["overall"]["source_group_count"])
        self.assertEqual(1.0, result["overall"]["positive_direction_rate"])

    def test_inner_validation_is_grouped_and_deterministic(self) -> None:
        cases = []
        for domain in ("a", "b", "outer"):
            for group in range(5):
                cases.append(
                    {
                        "source_domain": domain,
                        "partition_group": f"{domain}-{group}",
                    }
                )
        first = crnn.inner_validation_groups(cases, "outer", 20260802)
        second = crnn.inner_validation_groups(cases, "outer", 20260802)
        self.assertEqual(first, second)
        self.assertEqual(2, len(first))
        self.assertFalse(any(value.startswith("outer-") for value in first))

    def test_confusion_keeps_selected_population_labels_explicit(self) -> None:
        rows = [
            ({"expectation": "controlled_positive"}, True),
            ({"expectation": "controlled_positive"}, False),
            ({"expectation": "negative"}, True),
            ({"expectation": "negative"}, False),
        ]
        result = analysis.confusion(rows)
        self.assertEqual(1, result["true_positive_count"])
        self.assertEqual(1, result["false_positive_count"])
        self.assertEqual(0.5, result["selected_population_accuracy"])

    def test_feature_slice_deduplicates_locally_without_global_count(self) -> None:
        cases = [
            {"_analysis_pcm_sha256": "pcm-a"},
            {"_analysis_pcm_sha256": "pcm-a"},
            {"_analysis_pcm_sha256": "pcm-b"},
        ]
        template = {field: None for field in analysis.FEATURE_FIELDS}
        features = {
            "pcm-a": {**template, "spectral_edge_hz": 16000.0},
            "pcm-b": {**template, "spectral_edge_hz": 18000.0},
        }
        result = analysis.feature_summary(cases, features)
        self.assertEqual(2, result["spectral_edge_hz"]["count"])
        self.assertEqual(17000.0, result["spectral_edge_hz"]["median"])

    def test_public_contract_rejects_private_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "private key"):
            common.assert_public_path_free({"case_id": "private"})
        with self.assertRaisesRegex(ValueError, "absolute path"):
            common.assert_public_path_free({"note": "/private/audio.wav"})

    def test_crnn_evidence_is_path_free_and_non_promotable(self) -> None:
        result = json.loads(CRNN_EVIDENCE_PATH.read_text(encoding="utf-8"))
        common.assert_public_path_free(result)
        self.assertEqual(
            "mechanism_development_crnn_path_free_evidence", result["state"]
        )
        self.assertEqual(9_653, result["inventory"]["factorial_case_count"])
        self.assertEqual(7_701, result["inventory"]["unique_analysis_pcm_count"])
        self.assertFalse(result["encoder_transfer_scores_opened"])
        self.assertFalse(result["external_transfer_scores_opened"])
        self.assertFalse(result["public_verdict_enabled"])
        self.assertFalse(result["interpretation"]["baseline_can_be_promoted"])

        naive = result["conditions"]["naive"]
        masked = result["conditions"]["random_high_frequency_mask"]
        self.assertEqual(518, naive["source_group_level"]["negative_source_group_alert_count"])
        self.assertEqual(527, masked["source_group_level"]["negative_source_group_alert_count"])
        for condition in (naive, masked):
            paired = condition["paired_positive_minus_matched_reference"]["overall"]
            self.assertLess(paired["positive_direction_rate"], 0.90)
            self.assertLess(paired["one_sided_95_percent_wilson_lower"], 0.85)


if __name__ == "__main__":
    unittest.main()
