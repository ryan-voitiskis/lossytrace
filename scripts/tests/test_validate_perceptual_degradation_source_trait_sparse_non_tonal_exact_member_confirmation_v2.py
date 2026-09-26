from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v2.py"
SPEC = importlib.util.spec_from_file_location("validate_sparse_non_tonal_confirmation_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseNonTonalExactMemberConfirmationV2ValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_committed_public_report_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate_report(self.report))

    def test_committed_audit_replays_from_public_projection(self) -> None:
        audit = MODULE.load_json(MODULE.AUDIT_PATH)
        self.assertEqual([], MODULE.validate_audit(audit, self.report))
        self.assertTrue(audit["decision"]["rigorous_negative_preserved"])
        self.assertEqual("class_mismatch", audit["decision"]["terminal_outcome"])
        self.assertFalse(audit["decision"]["descriptor_confirmation_passed"])

    def test_public_measurement_or_path_tamper_is_rejected(self) -> None:
        for key, value, expected in (
            ("channel_descriptors", [], "channel_descriptors"),
            ("private_path", "/private/source.wav", "path-like"),
        ):
            tampered = copy.deepcopy(self.report)
            tampered[key] = value
            self.assertTrue(any(expected in error for error in MODULE.validate_report(tampered)))

    def test_terminal_outcome_tamper_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["decision"]["terminal_outcome"] = "passed"
        self.assertIn("public confirmation predicate differs", MODULE.validate_report(tampered))


if __name__ == "__main__":
    unittest.main()
