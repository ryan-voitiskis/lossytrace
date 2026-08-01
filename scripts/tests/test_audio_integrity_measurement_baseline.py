import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "analyze-audio-integrity-measurement-baseline.py"
)
SPEC = importlib.util.spec_from_file_location("measurement_baseline", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def features(value):
    return {
        field: (value if field != "spectral_edge_hz" else value * 10_000)
        for field in MODULE.FEATURE_FIELDS
    }


class MeasurementBaselineTests(unittest.TestCase):
    def fixture(self):
        cases = [
            {
                "case_id": "negative",
                "source_group": "group-a",
                "source_domain": "domain-a",
                "class": "pcm",
                "expectation": "negative",
                "provenance_tier": "tier_a_confirmed_pcm",
            },
            {
                "case_id": "positive",
                "source_group": "group-a",
                "source_domain": "domain-a",
                "class": "mp3_to_flac",
                "expectation": "controlled_positive",
                "provenance_tier": "tier_a_confirmed_pcm",
            },
        ]
        manifest = {
            "schema_version": 1,
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "cases": cases,
        }
        report = {
            "schema_version": 1,
            "feature_version": 0,
            "runner_sha256": "runner",
            "harness_sha256": "harness",
            "gate_disposition": {"likely_lossy_derived_enabled": False},
            "runtime": {"cases": 2},
            "results": [
                {
                    "case_id": case["case_id"],
                    "source_group": case["source_group"],
                    "expectation": case["expectation"],
                    "runner": {
                        "compression_trace": features(0.1 + index * 0.2),
                        "research_transform_grid_enabled": False,
                        "research_transform_grid_profile": None,
                        "transform_grid_probe": None,
                    },
                }
                for index, case in enumerate(cases)
            ],
        }
        return manifest, report

    def test_emits_path_free_versioned_aggregate(self):
        manifest, report = self.fixture()
        output = MODULE.analyze(manifest, report, "manifest", "report")
        self.assertEqual(output["schema_version"], 2)
        self.assertFalse(output["public_verdict_enabled"])
        self.assertFalse(output["independent_validation"])
        self.assertEqual(output["inventory"]["case_count"], 2)
        paired = output["within_source_group_positive_minus_negative"]
        self.assertEqual(
            paired["spectral_edge_persistence"]["positive_delta_group_count"],
            1,
        )
        self.assertNotIn("results", output)

    def test_rejects_a_verdict_enabled_report(self):
        manifest, report = self.fixture()
        report["gate_disposition"]["likely_lossy_derived_enabled"] = True
        with self.assertRaisesRegex(ValueError, "public verdict disabled"):
            MODULE.analyze(manifest, report, "manifest", "report")


if __name__ == "__main__":
    unittest.main()
