from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "perceptual_degradation_objective_completion_audit_v20.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v20", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV20Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_report_replays_exactly(self) -> None:
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_objective_remains_four_of_fourteen(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(14, summary["requirement_count"])
        self.assertEqual(4, summary["satisfied_count"])
        self.assertEqual(10, summary["unsatisfied_count"])
        self.assertFalse(summary["objective_complete"])

    def test_v4_bounded_negative_does_not_select_or_promote(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["sparse_non_tonal_metadata_search_v4_complete"])
        self.assertTrue(summary["sparse_non_tonal_metadata_search_v4_bounded_negative"])
        self.assertEqual(3, summary["sparse_non_tonal_metadata_search_v4_primary_record_count"])
        self.assertEqual(0, summary["sparse_non_tonal_metadata_search_v4_eligible_successor_count"])
        self.assertFalse(summary["sparse_non_tonal_successor_v4_selected"])
        self.assertFalse(summary["independent_sparse_and_tonal_contrasts_established"])
        self.assertFalse(summary["source_trait_manifest_frozen"])

    def test_prior_audio_and_negative_state_is_preserved(self) -> None:
        predecessor = MODULE.load_json(MODULE._bound(self.plan, "predecessor_audit_report"))
        self.assertEqual(predecessor["audio_accessed"], self.report["audio_accessed"])
        self.assertEqual(3, self.report["summary"]["sparse_non_tonal_failed_exact_candidate_count"])
        self.assertFalse(self.report["evidence_checks"]["sparse_non_tonal_metadata_search_v4_audio_accessed"])

    def test_public_and_scientific_boundaries_stay_closed(self) -> None:
        self.assertFalse(self.report["public_verdict_enabled"])
        self.assertFalse(self.report["metrics_executed"])
        self.assertFalse(self.report["no_reference_training_performed"])
        self.assertFalse(self.report["scores_opened"])
        self.assertFalse(self.report["sealed_evidence_opened"])

    def test_tampered_metadata_binding_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["bindings"]["metadata_result_report"]["sha256"] = "0" * 64
        self.assertIn("binding hash differs: metadata_result_report", MODULE.validate_plan(tampered))


if __name__ == "__main__":
    unittest.main()
