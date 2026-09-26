import importlib.util
import re
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "run-audio-integrity-exact-hybrid-ablation.py"
)
SPEC = importlib.util.spec_from_file_location("exact_hybrid_ablation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ExactHybridAblationTest(unittest.TestCase):
    def test_selection_includes_all_negatives_and_only_target_positives(self):
        cases = [
            {"case_id": "negative", "expectation": "negative", "class": "pcm"},
            {
                "case_id": "mp3",
                "expectation": "controlled_positive",
                "class": "musdb_mp3_128_to_flac16",
            },
            {
                "case_id": "aac",
                "expectation": "controlled_positive",
                "class": "musdb_aac_lc_128_to_flac16",
            },
        ]
        selected = MODULE.select_cases(
            cases, re.compile(MODULE.DEFAULT_POSITIVE_CLASS_REGEX)
        )
        self.assertEqual([case["case_id"] for case in selected], ["mp3", "negative"])

    def test_input_contract_rejects_open_holdout(self):
        manifest = {
            "schema_version": 1,
            "evidence_partition": "observed_development",
            "holdout_scores_opened": True,
            "cases": [],
        }
        baseline = {
            "schema_version": 1,
            "feature_version": 0,
            "gate_disposition": {"likely_lossy_derived_enabled": False},
            "results": [],
        }
        with self.assertRaisesRegex(ValueError, "sealed observed"):
            MODULE.validate_inputs(manifest, baseline)


if __name__ == "__main__":
    unittest.main()
