import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify-vamp-lossy-detector-pilot-replay.py"
SPEC = importlib.util.spec_from_file_location("vamp_pilot_replay", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def historical_row(index, *, missing=False):
    group = index % 8
    class_name = MODULE.EXPECTED_MISSING_CLASS if missing else "mp3_128"
    expectation = "negative" if missing else "controlled_positive"
    score = 0.9 if index % 2 else 0.1
    return {
        "case_id": f"case-{index:03}",
        "source_group": f"group-{group}",
        "class": class_name,
        "expectation": expectation,
        "provenance_tier": "tier_b_trusted",
        "positive_window_fraction": score,
        "detector_binary_label": score >= 0.25,
        "window_count": 20,
    }


def detector(schema_version):
    value = {
        "schema_version": schema_version,
        "detector": {
            "revision": MODULE.EXPECTED_REVISION,
            "plugin_key": MODULE.EXPECTED_PLUGIN_KEY,
            "host_sha256": "a" * 64,
        },
    }
    if schema_version == 2:
        value["detector"]["plugin_binary_sha256"] = "b" * 64
        value["detector"]["plugin_sdk_revision"] = MODULE.EXPECTED_SDK_REVISION
        value["detector"]["source_tracked_clean"] = True
        value["detector"]["plugin_sdk_tracked_clean"] = True
    return value


class VampPilotReplayTests(unittest.TestCase):
    def setUp(self):
        historical_rows = [
            historical_row(index, missing=index >= MODULE.EXPECTED_RETAINED_CASES)
            for index in range(MODULE.EXPECTED_HISTORICAL_CASES)
        ]
        self.historical = {
            **detector(1),
            "results": historical_rows,
        }
        cases = []
        for row in historical_rows[: MODULE.EXPECTED_RETAINED_CASES]:
            cases.append(
                {
                    "case_id": row["case_id"],
                    "source_group": row["source_group"],
                    "partition_group": row["source_group"],
                    "source_domain": "fixture",
                    "split": "development",
                    "provenance_tier": row["provenance_tier"],
                    "class": row["class"],
                    "expectation": row["expectation"],
                    "relative_path": f"audio/{row['case_id']}.flac",
                }
            )
        self.full = {
            "schema_version": 1,
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "cases": cases,
        }
        self.manifest = MODULE.compose_manifest(self.full, self.historical)
        self.manifest["source_manifest_sha256"] = "c" * 64
        self.manifest["historical_report_sha256"] = "d" * 64
        replay_rows = []
        for row in historical_rows[: MODULE.EXPECTED_RETAINED_CASES]:
            replay_rows.append(
                {
                    **row,
                    "partition_group": row["source_group"],
                    "source_domain": "fixture",
                    "split": "development",
                    "audio_sha256": "e" * 64,
                }
            )
        self.replay = {
            **detector(2),
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "thresholds_retuned": False,
            "decision_rule": {
                "window_threshold": 0.5,
                "file_positive_fraction_threshold": 0.25,
            },
            "manifest_sha256": "f" * 64,
            "results": replay_rows,
        }
        self.hashes = {
            "manifest_sha256": "f" * 64,
            "historical_report_sha256": "1" * 64,
            "replay_report_sha256": "2" * 64,
            "verifier_sha256": "3" * 64,
        }

    def test_compose_selects_only_retained_cases_and_records_limitation(self):
        self.assertEqual(len(self.manifest["cases"]), MODULE.EXPECTED_RETAINED_CASES)
        self.assertEqual(
            self.manifest["unretained_class_counts"],
            {MODULE.EXPECTED_MISSING_CLASS: MODULE.EXPECTED_MISSING_CASES},
        )
        self.assertFalse(self.manifest["holdout_scores_opened"])

    def test_compare_accepts_fixed_decision_replay_and_is_path_free(self):
        report = MODULE.compare(
            self.manifest, self.historical, self.replay, self.hashes
        )
        self.assertTrue(report["regression_passed"])
        self.assertEqual(report["comparison"]["fixed_decision_mismatch_count"], 0)
        self.assertEqual(
            report["comparison"]["positive_window_fraction_absolute_delta"][
                "maximum"
            ],
            0.0,
        )
        MODULE.assert_path_free(report)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("case-000", serialized)
        self.assertNotIn("group-0", serialized)

    def test_compare_reports_changed_fixed_decision(self):
        changed = copy.deepcopy(self.replay)
        changed["results"][1]["positive_window_fraction"] = 0.1
        changed["results"][1]["detector_binary_label"] = False
        report = MODULE.compare(
            self.manifest, self.historical, changed, self.hashes
        )
        self.assertFalse(report["regression_passed"])
        self.assertEqual(report["comparison"]["fixed_decision_mismatch_count"], 1)

    def test_compose_rejects_missing_class_drift(self):
        changed = copy.deepcopy(self.historical)
        changed["results"][-1]["class"] = "different_negative"
        with self.assertRaisesRegex(ValueError, "missing pilot class"):
            MODULE.compose_manifest(self.full, changed)


if __name__ == "__main__":
    unittest.main()
