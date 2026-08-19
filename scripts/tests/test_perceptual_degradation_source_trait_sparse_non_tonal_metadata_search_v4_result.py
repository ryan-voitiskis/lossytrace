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
SCRIPT = SCRIPTS / "perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v4_result.py"
SPEC = importlib.util.spec_from_file_location("sparse_non_tonal_metadata_search_v4_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseNonTonalMetadataSearchV4ResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_report_replays_exactly(self) -> None:
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_search_exhausted_without_media_or_audio(self) -> None:
        execution = self.report["execution"]
        self.assertEqual(8, execution["discovery_query_count_executed"])
        self.assertEqual(2, execution["discovery_query_batch_count"])
        self.assertEqual(0, execution["discovery_query_transport_batch_retry_count"])
        self.assertEqual(3, execution["distinct_primary_record_count_attempted"])
        self.assertEqual(3, execution["primary_records_inspected_as_text_html"])
        self.assertEqual(0, execution["media_asset_request_count"])
        self.assertFalse(self.report["audio_accessed"])

    def test_bounded_negative_has_no_nomination(self) -> None:
        decision = self.report["decision"]
        self.assertTrue(decision["bounded_negative_preserved"])
        self.assertTrue(decision["search_exhausted_without_eligible_member"])
        self.assertEqual(0, decision["eligible_successor_count"])
        self.assertIsNone(decision["nominated_exact_member_id"])
        self.assertFalse(decision["metadata_nomination_is_descriptor_evidence"])
        self.assertFalse(decision["metadata_nomination_is_source_trait_truth"])

    def test_every_primary_record_has_a_fail_closed_disposition(self) -> None:
        self.assertEqual(3, len(self.report["record_dispositions"]))
        for row in self.report["record_dispositions"]:
            self.assertFalse(row["audio_accessed"])
            self.assertFalse(row["eligible_for_exact_member_checkpoint"])
            self.assertTrue(row["rejection_reasons"])

    def test_consumed_member_or_empty_rejection_fails_closed(self) -> None:
        prior = copy.deepcopy(MODULE.PRIMARY_RECORD_ATTEMPTS)
        try:
            MODULE.PRIMARY_RECORD_ATTEMPTS[0]["exact_member_id"] = "freesound_sound_476736"
            self.assertIn("consumed exact member was reinspected", MODULE.validate_observations(self.plan))
            MODULE.PRIMARY_RECORD_ATTEMPTS[:] = copy.deepcopy(prior)
            MODULE.PRIMARY_RECORD_ATTEMPTS[0]["rejection_reasons"] = []
            self.assertIn("unexpected eligible exact member", MODULE.validate_observations(self.plan))
        finally:
            MODULE.PRIMARY_RECORD_ATTEMPTS[:] = prior


if __name__ == "__main__":
    unittest.main()
