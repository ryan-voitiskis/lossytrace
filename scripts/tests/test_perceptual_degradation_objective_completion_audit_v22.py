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
SCRIPT = SCRIPTS / "perceptual_degradation_objective_completion_audit_v22.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v22", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV22Test(unittest.TestCase):
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

    def test_authority_and_live_intake_readiness_are_recorded_without_promotion(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["clean_capture_one_safe_capture_authorized"])
        self.assertTrue(summary["clean_capture_live_intake_checkpoint_frozen"])
        self.assertTrue(summary["clean_capture_live_manifest_read_authorized"])
        self.assertFalse(summary["clean_capture_external_communication_authorized"])
        self.assertFalse(summary["clean_capture_payment_or_purchase_authorized"])
        self.assertFalse(summary["clean_capture_physical_chain_complete"])
        self.assertFalse(summary["clean_capture_live_delivery_present"])
        self.assertFalse(summary["clean_capture_live_delivery_accepted"])
        self.assertFalse(summary["clean_capture_capture_executed"])
        self.assertFalse(summary["clean_capture_audio_accessed"])
        self.assertFalse(summary["source_trait_manifest_frozen"])

    def test_prior_negative_and_audio_state_are_preserved(self) -> None:
        predecessor = MODULE.load_json(MODULE._bound(self.plan, "predecessor_audit_report"))
        self.assertEqual(predecessor["audio_accessed"], self.report["audio_accessed"])
        self.assertEqual(3, self.report["summary"]["sparse_non_tonal_failed_exact_candidate_count"])
        self.assertTrue(self.report["summary"]["sparse_non_tonal_metadata_search_v4_bounded_negative"])
        self.assertFalse(self.report["evidence_checks"]["clean_capture_audio_accessed"])

    def test_public_and_scientific_boundaries_stay_closed(self) -> None:
        self.assertFalse(self.report["public_verdict_enabled"])
        self.assertFalse(self.report["metrics_executed"])
        self.assertFalse(self.report["no_reference_training_performed"])
        self.assertFalse(self.report["scores_opened"])
        self.assertFalse(self.report["sealed_evidence_opened"])

    def test_tampered_authority_or_live_intake_binding_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["authorization"]["external_communication_authorized"] = True
        tampered["bindings"]["live_intake_plan"]["sha256"] = "0" * 64
        errors = MODULE.validate_plan(tampered)
        self.assertIn("authorization differs: external_communication_authorized", errors)
        self.assertIn("binding hash differs: live_intake_plan", errors)


if __name__ == "__main__":
    unittest.main()
