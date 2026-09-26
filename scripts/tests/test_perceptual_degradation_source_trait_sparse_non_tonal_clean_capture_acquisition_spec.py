from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_acquisition_spec.py"
SPEC = importlib.util.spec_from_file_location("clean_capture_spec", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanCaptureAcquisitionSpecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)

    def test_committed_spec_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_external_actions_and_audio_stay_closed(self) -> None:
        authorization = self.plan["authorization"]
        for key in ("audio_access_authorized", "collection_authorized", "external_communication_authorized", "payment_or_purchase_authorized"):
            self.assertFalse(authorization[key])
        self.assertTrue(all(value is False for value in self.plan["claim_boundary"].values()))

    def test_capture_is_safe_single_event_with_quiet_margins(self) -> None:
        capture = self.plan["capture_specification"]
        self.assertEqual(1, capture["event_count"])
        self.assertEqual("5.000", capture["minimum_pre_event_quiet_seconds"])
        self.assertEqual("5.000", capture["minimum_post_event_quiet_seconds"])
        self.assertIn("no_firearm_explosive_pyrotechnic_or_hazardous_event", capture["physical_safety_policy"])

    def test_acceptance_is_metadata_first_and_fail_closed(self) -> None:
        acceptance = self.plan["metadata_first_acceptance"]
        self.assertFalse(acceptance["audio_preview_or_download_before_metadata_acceptance_authorized"])
        self.assertTrue(acceptance["exact_member_checkpoint_required_before_audio_access"])
        self.assertTrue(acceptance["fail_closed_on_ambiguous_or_missing_field"])
        self.assertFalse(acceptance["member_substitution_after_audio_observation_allowed"])
        self.assertFalse(acceptance["threshold_change_allowed"])

    def test_authority_or_processing_tamper_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["authorization"]["external_communication_authorized"] = True
        tampered["processing_boundary"]["allowed_transformations"] = ["trim"]
        errors = MODULE.validate_plan(tampered)
        self.assertIn("authorization differs: external_communication_authorized", errors)
        self.assertIn("allowed processing boundary differs", errors)


if __name__ == "__main__":
    unittest.main()
