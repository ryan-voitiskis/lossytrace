from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validate-perceptual-degradation-odaq-retained-drift-validation-result.py"
)
SPEC = importlib.util.spec_from_file_location("odaq_retained_drift_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OdaqRetainedDriftValidationResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MODULE.load_json(MODULE.RESULT)

    def test_committed_result_validates(self) -> None:
        self.assertEqual([], MODULE.validate_result(self.result))

    def test_result_preserves_reproducible_negative(self) -> None:
        summary = self.result["gate_summary"]
        self.assertEqual(17, summary["predeclared_gate_count"])
        self.assertEqual(16, summary["predeclared_gate_pass_count"])
        self.assertFalse(summary["all_predeclared_gates_pass"])
        self.assertEqual(
            ["applied_case_minimum_post_correction_core_correlation_each_channel"],
            summary["failed_gate_ids"],
        )
        observations = self.result["aggregate_observations_per_replay"]
        self.assertEqual(6, observations["applied_case_count_below_post_correction_correlation_threshold"])
        self.assertEqual(0.998464803418, observations["minimum_applied_post_correction_core_correlation"])

    def test_result_is_aggregate_only_and_verdict_free(self) -> None:
        serialized = json.dumps(self.result, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("Application Support", serialized)
        self.assertNotIn("source_opaque_reference_id", serialized)
        self.assertNotIn("input_f64le_sha256", serialized)
        self.assertNotIn("output_f64le_sha256", serialized)
        self.assertNotIn('"cases"', serialized)
        self.assertFalse(self.result["access_boundary"]["public_verdict_emitted"])
        self.assertFalse(self.result["claim_boundary"]["final_validation_supported"])

    def test_gate_failure_cannot_be_promoted(self) -> None:
        changed = copy.deepcopy(self.result)
        changed["predeclared_gate_audit"][
            "applied_case_minimum_post_correction_core_correlation_each_channel"
        ] = True
        changed["gate_summary"]["all_predeclared_gates_pass"] = True
        self.assertIn("predeclared gate audit differs", MODULE.validate_result(changed))
        self.assertIn("gate summary differs", MODULE.validate_result(changed))

    def test_private_detail_is_rejected(self) -> None:
        changed = copy.deepcopy(self.result)
        changed["private_path"] = "/Users/example/private"
        self.assertTrue(
            any("prohibited private detail" in error for error in MODULE.validate_result(changed))
        )


if __name__ == "__main__":
    unittest.main()
