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
SCRIPT = SCRIPTS / "perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v3_result.py"
SPEC = importlib.util.spec_from_file_location("sparse_non_tonal_metadata_search_v3_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseNonTonalMetadataSearchV3ResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_report_replays_exactly(self) -> None:
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_search_stopped_without_media_or_audio(self) -> None:
        execution = self.report["execution"]
        self.assertEqual(8, execution["discovery_query_count_executed"])
        self.assertEqual(1, execution["discovery_query_transport_batch_retry_count"])
        self.assertFalse(execution["discovery_scope_expanded_by_transport_retry"])
        self.assertEqual(11, execution["distinct_primary_record_count_attempted"])
        self.assertEqual(5, execution["primary_records_inspected_as_text_html"])
        self.assertEqual(6, execution["primary_record_fetch_timeout_count"])
        self.assertEqual(0, execution["media_asset_request_count"])
        self.assertFalse(self.report["audio_accessed"])

    def test_exactly_one_metadata_candidate_is_nominated(self) -> None:
        self.assertEqual(1, self.report["decision"]["eligible_successor_count"])
        self.assertEqual("freesound_sound_476736", self.report["decision"]["nominated_exact_member_id"])
        self.assertFalse(self.report["decision"]["metadata_nomination_is_descriptor_evidence"])
        self.assertFalse(self.report["decision"]["metadata_nomination_is_source_trait_truth"])

    def test_timeout_rows_cannot_carry_discovery_metadata(self) -> None:
        prior = copy.deepcopy(MODULE.PRIMARY_RECORD_ATTEMPTS)
        try:
            MODULE.PRIMARY_RECORD_ATTEMPTS[1]["licence"] = "CC0 1.0"
            errors = MODULE.validate_observations(self.plan)
            self.assertIn("timeout row exposes unobserved metadata: freesound_sound_734656", errors)
        finally:
            MODULE.PRIMARY_RECORD_ATTEMPTS[:] = prior

    def test_consumed_member_or_missing_candidate_prerequisite_fails_closed(self) -> None:
        prior = copy.deepcopy(MODULE.PRIMARY_RECORD_ATTEMPTS)
        try:
            MODULE.PRIMARY_RECORD_ATTEMPTS[-1]["capture_chain"] = ""
            self.assertIn("candidate prerequisite absent: capture_chain", MODULE.validate_observations(self.plan))
            MODULE.PRIMARY_RECORD_ATTEMPTS[-1] = prior[-1]
            MODULE.PRIMARY_RECORD_ATTEMPTS[0]["exact_member_id"] = "freesound_sound_703342"
            self.assertIn("consumed exact member was reinspected", MODULE.validate_observations(self.plan))
        finally:
            MODULE.PRIMARY_RECORD_ATTEMPTS[:] = prior


if __name__ == "__main__":
    unittest.main()
