from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validate_perceptual_degradation_source_trait_exact_member_confirmation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "source_trait_exact_member_confirmation_result", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceTraitExactMemberConfirmationResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_committed_public_report_validates(self) -> None:
        self.assertEqual([], MODULE.validate_report(self.report, self.plan))

    def test_numeric_mutation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["descriptor_observations"]["quiet"]["sum_squares"] += 1
        changed["descriptor_observations"]["clipped"][
            "plateau_or_saturation_support_event_present"
        ] = False
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("quiet sum of squares differs", errors)
        self.assertIn("clipped support predicate differs", errors)

    def test_trait_and_verdict_promotion_is_rejected(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["decision"]["quiet_or_clipped_trait_assigned"] = True
        changed["decision"]["public_verdict_enabled"] = True
        changed["claim_boundary"]["metadata_plus_descriptor_is_perceptual_truth"] = True
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("decision must remain false: quiet_or_clipped_trait_assigned", errors)
        self.assertIn("decision must remain false: public_verdict_enabled", errors)
        self.assertIn("claim boundary must remain false", errors)

    def test_paths_and_per_reference_hashes_are_rejected(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["private_path"] = "/Users/example/provider-originals/source.wav"
        changed["encoded_sha256"] = "0" * 64
        errors = MODULE.validate_report(changed, self.plan)
        self.assertTrue(
            any(error.startswith("public report exposes forbidden material") for error in errors)
        )

    def test_observations_do_not_claim_trait_truth(self) -> None:
        self.assertTrue(
            self.report["decision"]["quiet_nonzero_activity_support_observed"]
        )
        self.assertTrue(
            self.report["decision"][
                "clipped_plateau_or_saturation_support_event_observed"
            ]
        )
        self.assertFalse(
            self.report["decision"]["quiet_or_clipped_trait_assigned"]
        )
        self.assertFalse(self.report["decision"]["source_trait_manifest_frozen"])


if __name__ == "__main__":
    unittest.main()
