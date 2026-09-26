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
SCRIPT = SCRIPTS / "perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v2_result.py"
SPEC = importlib.util.spec_from_file_location("sparse_non_tonal_metadata_search_v2_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseNonTonalMetadataSearchV2ResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_report_replays_exactly(self) -> None:
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_search_stopped_without_media_or_audio(self) -> None:
        execution = self.report["execution"]
        self.assertEqual(4, execution["discovery_query_count_executed"])
        self.assertEqual(4, execution["discovery_query_count_not_executed_after_stop"])
        self.assertEqual(9, execution["primary_record_count_inspected"])
        self.assertEqual(0, execution["media_asset_request_count"])
        self.assertFalse(execution["preview_or_waveform_accessed"])
        self.assertFalse(self.report["audio_accessed"])

    def test_exactly_one_metadata_candidate_is_nominated(self) -> None:
        self.assertEqual(1, self.report["decision"]["eligible_successor_count"])
        self.assertEqual("freesound_sound_703342", self.report["decision"]["nominated_exact_member_id"])
        self.assertFalse(self.report["decision"]["metadata_nomination_is_descriptor_evidence"])
        self.assertFalse(self.report["decision"]["metadata_nomination_is_source_trait_truth"])

    def test_consumed_member_or_missing_candidate_prerequisite_fails_closed(self) -> None:
        prior = copy.deepcopy(MODULE.OBSERVED_RECORDS)
        try:
            MODULE.OBSERVED_RECORDS[-1]["capture_chain"] = ""
            self.assertIn("candidate prerequisite absent: capture_chain", MODULE.validate_observations(self.plan))
            MODULE.OBSERVED_RECORDS[-1] = prior[-1]
            MODULE.OBSERVED_RECORDS[0]["exact_member_id"] = "freesound_sound_856645"
            errors = MODULE.validate_observations(self.plan)
            self.assertIn("consumed exact member was reinspected", errors)
        finally:
            MODULE.OBSERVED_RECORDS[:] = prior


if __name__ == "__main__":
    unittest.main()
