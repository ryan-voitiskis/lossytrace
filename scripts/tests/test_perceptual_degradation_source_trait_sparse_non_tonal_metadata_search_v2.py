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
SCRIPT = SCRIPTS / "perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v2.py"
SPEC = importlib.util.spec_from_file_location("sparse_non_tonal_metadata_search_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseNonTonalMetadataSearchV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)

    def test_committed_plan_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_audio_and_scientific_surfaces_stay_closed(self) -> None:
        self.assertTrue(all(value is False for value in self.plan["claim_boundary"].values()))
        media = self.plan["media_boundary"]
        for key, value in media.items():
            if key not in {"maximum_text_response_bytes", "permitted_primary_record_content_types"}:
                self.assertFalse(value, key)

    def test_search_is_bounded_and_excludes_consumed_members(self) -> None:
        protocol = self.plan["search_protocol"]
        self.assertEqual(8, protocol["discovery_query_count_maximum"])
        self.assertEqual(20, protocol["exact_primary_record_count_maximum"])
        self.assertEqual(MODULE.EXPECTED_EXCLUDED_IDS, set(self.plan["candidate_eligibility"]["excluded_exact_member_ids"]))

    def test_tampered_binding_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["bindings"]["descriptor_plan"]["sha256"] = "0" * 64
        self.assertIn("binding hash differs: descriptor_plan", MODULE.validate_plan(tampered))

    def test_media_or_threshold_opening_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["media_boundary"]["audio_download_authorized"] = True
        tampered["result_policy"]["threshold_change_allowed"] = True
        errors = MODULE.validate_plan(tampered)
        self.assertIn("media boundary differs: audio_download_authorized", errors)
        self.assertIn("threshold change must remain closed", errors)

    def test_missing_authorization_and_substitution_fail_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        del tampered["authorization"]["sealed_evidence_access_authorized"]
        tampered["result_policy"]["member_substitution_after_audio_observation_allowed"] = True
        errors = MODULE.validate_plan(tampered)
        self.assertIn("authorization inventory differs", errors)
        self.assertIn("post-observation member substitution must remain closed", errors)


if __name__ == "__main__":
    unittest.main()
