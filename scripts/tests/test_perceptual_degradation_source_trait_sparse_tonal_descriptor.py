from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_tonal_descriptor.py"
SPEC = importlib.util.spec_from_file_location("sparse_tonal_descriptor", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseTonalDescriptorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_plan_and_committed_report_replay_exactly(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_three_synthetic_structures_are_separated(self) -> None:
        rows = {row["fixture_id"]: row["descriptor"] for row in self.report["synthetic_fixture_results"]}
        self.assertTrue(rows["sparse-tonal-overlap"]["sparse_tonal_overlap"])
        self.assertTrue(rows["sparse-nontonal-contrast"]["sparse_non_tonal_contrast"])
        self.assertTrue(rows["tonal-nonsparse-contrast"]["tonal_non_sparse_contrast"])

    def test_boundary_values_abstain(self) -> None:
        values = [1000 if 2 <= index // 800 < 7 else 0 for index in range(8000)]
        result = MODULE.classify(values)
        self.assertTrue(result["abstain"])
        self.assertFalse(result["sparse_non_tonal_contrast"])
        self.assertFalse(result["tonal_non_sparse_contrast"])

    def test_silence_abstains(self) -> None:
        result = MODULE.classify([0] * 8000)
        self.assertTrue(result["abstain"])
        self.assertFalse(result["time_occupancy"]["supported"])

    def test_candidate_access_and_assignment_remain_closed(self) -> None:
        decision = self.report["decision"]
        self.assertFalse(decision["exact_member_selection_authorized"])
        self.assertFalse(decision["candidate_audio_access_authorized"])
        self.assertFalse(decision["source_trait_assignment_authorized"])
        self.assertFalse(decision["source_trait_manifest_frozen"])


if __name__ == "__main__":
    unittest.main()
