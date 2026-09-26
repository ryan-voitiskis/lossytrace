from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_perceptual_degradation_source_trait_sparse_tonal_exact_member_confirmation.py"
SPEC = importlib.util.spec_from_file_location("validate_sparse_tonal_confirmation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseTonalExactMemberConfirmationValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_committed_public_report_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate_report(self.report))

    def test_committed_audit_replays_from_public_projection(self) -> None:
        audit = MODULE.load_json(MODULE.AUDIT_PATH)
        self.assertEqual([], MODULE.validate_audit(audit, self.report))
        self.assertTrue(audit["decision"]["rigorous_negative_preserved"])
        self.assertEqual("abstained", audit["decision"]["freesound_terminal_outcome"])
        self.assertFalse(audit["decision"]["freesound_sparse_non_tonal_confirmation_passed"])
        self.assertTrue(audit["decision"]["tinysol_tonal_non_sparse_confirmation_passed"])

    def test_active_block_tamper_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        channel = tampered["source_observations"][0]["measurement"]["channel_descriptors"][0]
        channel["time_occupancy"]["active_block_count"] = 2
        self.assertIn(
            "freesound_sound_856645 channel 0 active fraction differs",
            MODULE.validate_report(tampered),
        )


if __name__ == "__main__":
    unittest.main()
