from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-perceptual-degradation-odaq-delivery-result.py"
SPEC = importlib.util.spec_from_file_location("odaq_delivery_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OdaqDeliveryResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MODULE.load_json(MODULE.RESULT)

    def test_committed_result_validates(self) -> None:
        self.assertEqual([], MODULE.validate_result(self.result))

    def test_exact_inventory_and_two_replays_are_recorded(self) -> None:
        self.assertEqual(16, self.result["input_inventory"]["reference_count"])
        self.assertTrue(self.result["input_inventory"]["source_inventory_reverified_before_projection"])
        self.assertEqual(16, self.result["delivery_inventory"]["reference_count_per_replay"])
        self.assertTrue(self.result["delivery_inventory"]["replay_trees_byte_identical"])
        self.assertEqual(32, self.result["delivery_inventory"]["ffprobe_verified_file_count"])
        self.assertTrue(self.result["attribution"]["attachments_byte_identical"])
        self.assertEqual(30, self.result["attribution"]["attached_licence_record_count_per_replay"])

    def test_projection_is_not_promoted_to_perceptual_evidence(self) -> None:
        claims = self.result["claim_boundary"]
        self.assertFalse(claims["delivery_projection_is_stimulus_generation"])
        self.assertFalse(claims["delivery_projection_is_perceptual_truth"])
        self.assertFalse(claims["delivery_projection_is_metric_evidence"])
        self.assertFalse(claims["delivery_projection_is_listening_evidence"])
        self.assertFalse(claims["full_reference_oracle_validated"])

    def test_closed_access_surfaces_remain_false(self) -> None:
        access = self.result["access_boundary"]
        self.assertTrue(access["retained_clean_reference_audio_read"])
        self.assertTrue(access["retained_clean_reference_audio_projected"])
        for key in (
            "odaq_processed_condition_opened",
            "odaq_listening_score_opened",
            "perceptual_metric_executed",
            "degradation_rating_collected",
            "listener_response_collected",
            "sealed_evidence_opened",
            "public_verdict_emitted",
        ):
            self.assertFalse(access[key])

    def test_private_paths_and_per_reference_hashes_remain_redacted(self) -> None:
        serialized = MODULE.json.dumps(self.result, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("Application Support", serialized)
        self.assertFalse(self.result["execution"]["private_paths_published"])
        self.assertFalse(self.result["execution"]["per_reference_hashes_published"])

    def test_mutations_fail_closed(self) -> None:
        changed = copy.deepcopy(self.result)
        changed["delivery_inventory"]["replay_trees_byte_identical"] = False
        changed["access_boundary"]["perceptual_metric_executed"] = True
        changed["claim_boundary"]["delivery_projection_is_perceptual_truth"] = True
        errors = MODULE.validate_result(changed)
        self.assertIn("delivery inventory observation differs", errors)
        self.assertIn("access boundary differs", errors)
        self.assertIn("claim boundary differs", errors)


if __name__ == "__main__":
    unittest.main()
