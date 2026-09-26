from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v15.py"
SPEC = importlib.util.spec_from_file_location("objective_v15", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV15Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_plan_and_report_replay_exactly(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_objective_remains_four_of_fourteen(self) -> None:
        self.assertEqual(4, self.report["summary"]["satisfied_count"])
        self.assertEqual(10, self.report["summary"]["unsatisfied_count"])
        self.assertFalse(self.report["summary"]["objective_complete"])

    def test_metadata_rejections_do_not_create_a_sparse_contrast(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["sparse_non_tonal_successor_metadata_audit_complete"])
        self.assertEqual(5, summary["sparse_non_tonal_successor_metadata_candidate_count"])
        self.assertEqual(0, summary["sparse_non_tonal_eligible_successor_count"])
        self.assertFalse(summary["sparse_non_tonal_successor_selected"])
        self.assertFalse(summary["independent_sparse_and_tonal_contrasts_established"])
        self.assertFalse(summary["source_trait_manifest_frozen"])

    def test_retained_drift_and_prior_audio_state_are_unchanged(self) -> None:
        predecessor = MODULE.load_json(MODULE._bound(self.plan, "predecessor_audit_report"))
        keys = {
            key
            for key in predecessor["evidence_checks"]
            if key.startswith("retained_drift") or key.startswith("oracle_drift")
        }
        self.assertEqual(
            {key: predecessor["evidence_checks"][key] for key in keys},
            {key: self.report["evidence_checks"][key] for key in keys},
        )
        self.assertEqual(predecessor["audio_accessed"], self.report["audio_accessed"])
        self.assertEqual(
            predecessor["evidence_checks"]["new_source_audio_accessed"],
            self.report["evidence_checks"]["new_source_audio_accessed"],
        )
        self.assertFalse(self.report["evidence_checks"]["sparse_non_tonal_successor_metadata_audio_accessed"])


if __name__ == "__main__":
    unittest.main()
