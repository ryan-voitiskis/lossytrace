import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/analyze-vamp-lossy-detector.py"
SPEC = importlib.util.spec_from_file_location("vamp_failure_atlas", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def case(case_id, group, domain, class_name, expectation):
    return {
        "case_id": case_id,
        "source_group": group,
        "source_domain": domain,
        "class": class_name,
        "expectation": expectation,
        "provenance_tier": "tier_a_confirmed_pcm",
    }


def result(metadata, score):
    return {
        **metadata,
        "audio_sha256": (metadata["case_id"][0] * 64),
        "window_count": 10,
        "positive_window_fraction": score,
        "detector_binary_label": score >= 0.25,
    }


class VampFailureAtlasTests(unittest.TestCase):
    def setUp(self):
        cases = [
            case("a-neg", "group-a", "music", "lowpass_only_pcm", "negative"),
            case("a-pos", "group-a", "music", "mp3_128", "controlled_positive"),
            case("b-neg", "group-b", "speech", "untouched_pcm", "negative"),
            case("b-pos", "group-b", "speech", "aac_lc_128", "controlled_positive"),
        ]
        scores = [0.9, 0.8, 0.1, 0.2]
        self.manifest = {
            "schema_version": 1,
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "cases": cases,
        }
        self.report = {
            "schema_version": 2,
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "thresholds_retuned": False,
            "decision_rule": {
                "window_threshold": 0.5,
                "file_positive_fraction_threshold": 0.25,
            },
            "detector": {
                "name": "cannam/vamp-lossy-encoding-detector",
                "repository": "https://github.com/cannam/vamp-lossy-encoding-detector",
                "revision": MODULE.EXPECTED_REVISION,
                "plugin_sdk_revision": MODULE.EXPECTED_SDK_REVISION,
                "plugin_key": MODULE.EXPECTED_PLUGIN_KEY,
                "host_sha256": "1" * 64,
                "host_version": "Simple Vamp plugin host version: 1.5",
                "plugin_binary_sha256": "2" * 64,
                "source_tracked_clean": True,
                "plugin_sdk_tracked_clean": True,
            },
            "results": [result(metadata, score) for metadata, score in zip(cases, scores)],
        }

    def analyze(self, report=None):
        return MODULE.analyze(
            self.manifest,
            self.report if report is None else report,
            {
                "manifest_sha256": "3" * 64,
                "raw_report_sha256": "4" * 64,
                "preregistration_sha256": "5" * 64,
                "analyzer_sha256": "6" * 64,
            },
            strict_inventory=False,
        )

    def test_fixed_rule_metrics_and_mp3_population(self):
        report = self.analyze()
        p1 = report["populations"]["p1_general_consumed"]
        self.assertEqual(
            p1["case_level"]["confusion"],
            {
                "true_positive": 1,
                "false_negative": 1,
                "true_negative": 1,
                "false_positive": 1,
            },
        )
        self.assertEqual(
            p1["negative_source_groups"]["alerts"]["successes"], 1
        )
        p2 = report["populations"]["p2_mp3_128_comparison"]
        self.assertEqual(p2["inventory"]["case_count"], 3)
        self.assertEqual(p2["inventory"]["controlled_positive_case_count"], 1)
        self.assertEqual(p2["case_level"]["recall"]["rate"], 1.0)

    def test_class_slice_preserves_hard_negative_failure(self):
        report = self.analyze()
        lowpass = report["populations"]["p1_general_consumed"]["by_class"][
            "lowpass_only_pcm"
        ]
        self.assertEqual(lowpass["source_group_alerts"]["rate"], 1.0)

    def test_aggregate_is_path_free_and_has_no_case_identities(self):
        report = self.analyze()
        MODULE.assert_path_free(report)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("a-neg", serialized)
        self.assertNotIn("group-a", serialized)

    def test_rejects_changed_file_threshold_or_label(self):
        changed = copy.deepcopy(self.report)
        changed["decision_rule"]["file_positive_fraction_threshold"] = 0.3
        with self.assertRaisesRegex(ValueError, "decision rule"):
            self.analyze(changed)
        changed = copy.deepcopy(self.report)
        changed["results"][0]["detector_binary_label"] = False
        with self.assertRaisesRegex(ValueError, "fixed detector result"):
            self.analyze(changed)

    def test_rejects_wrong_detector_revision(self):
        changed = copy.deepcopy(self.report)
        changed["detector"]["revision"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "detector identity"):
            self.analyze(changed)

    def test_wilson_interval_matches_retained_pilot_rounding(self):
        lower, upper = MODULE.wilson_bounds(61, 64)
        self.assertAlmostEqual(lower, 0.8710, places=4)
        self.assertAlmostEqual(upper, 0.9839, places=4)


if __name__ == "__main__":
    unittest.main()
