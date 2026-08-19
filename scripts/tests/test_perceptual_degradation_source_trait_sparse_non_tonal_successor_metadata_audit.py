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
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_successor_metadata_audit.py"
SPEC = importlib.util.spec_from_file_location("sparse_successor_metadata", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseNonTonalSuccessorMetadataAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_plan_and_report_replay_exactly(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_every_route_is_rejected_before_audio(self) -> None:
        self.assertFalse(self.report["audio_accessed"])
        self.assertEqual(0, self.report["decision"]["eligible_successor_count"])
        self.assertTrue(self.report["decision"]["previous_abstention_preserved"])
        for row in self.report["record_dispositions"]:
            self.assertFalse(row["audio_accessed"])
            self.assertFalse(row["eligible_for_audio_access_successor"])
            self.assertTrue(row["rejection_reasons"])

    def test_duration_boundary_is_enforced(self) -> None:
        tampered = copy.deepcopy(self.plan)
        row = next(item for item in tampered["observed_records"] if item["exact_member_id"] == "freesound_sound_866967")
        row["rejection_reasons"].remove("duration_below_frozen_minimum")
        with self.assertRaisesRegex(ValueError, "duration rejection missing"):
            MODULE.build_report(tampered)

    def test_claim_boundary_stays_false(self) -> None:
        self.assertTrue(self.report["claim_boundary"])
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))


if __name__ == "__main__":
    unittest.main()
