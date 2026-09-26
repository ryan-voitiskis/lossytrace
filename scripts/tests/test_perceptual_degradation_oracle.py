from __future__ import annotations

import copy
import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = importlib.import_module("perceptual_degradation_oracle")


class PerceptualDegradationOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.replay = MODULE.build_replay()

    def test_score_free_replay_is_byte_identical(self) -> None:
        first = MODULE.canonical_bytes(self.replay)
        second = MODULE.canonical_bytes(MODULE.build_replay())
        self.assertEqual(first, second)
        self.assertEqual([], MODULE.validate_replay(self.replay))

    def test_alignment_failure_and_execution_block_are_distinct(self) -> None:
        by_state = {record["result_state"]: record for record in self.replay["records"]}
        blocked = by_state["execution_blocked"]
        unsupported = by_state["unsupported_alignment"]
        self.assertEqual("supported", blocked["alignment"]["status"])
        self.assertEqual(
            [
                "human_calibration_unavailable",
                "perceptual_metric_execution_not_authorized",
            ],
            blocked["support"]["abstention_reasons"],
        )
        self.assertEqual("unsupported", unsupported["alignment"]["status"])
        self.assertEqual(
            ["alignment_unsupported"],
            unsupported["support"]["abstention_reasons"],
        )
        self.assertIn(
            "channel_topology_mismatch",
            unsupported["support"]["alignment_reason_codes"],
        )

    def test_score_free_records_cannot_fabricate_outputs(self) -> None:
        for record in self.replay["records"]:
            self.assertEqual("indeterminate", record["outcomes"]["categorical_state"])
            self.assertIsNone(record["outcomes"]["impairment_severity"])
            self.assertIsNone(record["outcomes"]["audibility_probability"])
            self.assertEqual(
                {key: None for key in MODULE.ARTIFACT_COMPONENTS},
                record["outcomes"]["artifact_profile"]["components"],
            )
            self.assertFalse(record["support"]["supported"])
            self.assertEqual("unquantified", record["uncertainty"]["state"])
            self.assertEqual(0, record["uncertainty"]["source_group_bootstrap_replicates"])
            for family in record["metric_families"]:
                self.assertIsNone(family["raw_primary_value"])
                self.assertFalse(family["supporting_outputs_present"])

    def test_metric_human_and_public_boundaries_fail_closed(self) -> None:
        record = copy.deepcopy(self.replay["records"][0])
        record["evidence_scope"]["perceptual_metric_executed"] = True
        record["evidence_scope"]["human_score_accessed"] = True
        record["public_verdict_enabled"] = True
        record["metric_families"][0]["raw_primary_value"] = 4.2
        record["outcomes"]["impairment_severity"] = 12.0
        errors = MODULE.validate_score_free_record(record)
        self.assertIn(
            "evidence scope must remain false: perceptual_metric_executed", errors
        )
        self.assertIn("evidence scope must remain false: human_score_accessed", errors)
        self.assertIn("public verdict must remain disabled", errors)
        self.assertIn("metric-family boundary differs", errors)
        self.assertIn("score-free outcomes must remain unavailable", errors)

    def test_alignment_reason_projection_cannot_be_hidden(self) -> None:
        record = copy.deepcopy(self.replay["records"][1])
        record["support"]["alignment_reason_codes"] = []
        self.assertIn(
            "alignment reason projection differs",
            MODULE.validate_score_free_record(record),
        )
        record = copy.deepcopy(self.replay["records"][1])
        record["alignment"]["support"]["reasons"] = []
        self.assertIn(
            "unsupported alignment lacks an abstention reason",
            MODULE.validate_score_free_record(record),
        )

    def test_embedded_alignment_shape_and_numeric_values_fail_closed(self) -> None:
        record = copy.deepcopy(self.replay["records"][0])
        record["alignment"]["unexpected"] = True
        record["alignment"]["alignment"]["minimum_correlation"] = float("nan")
        record["alignment"]["input"]["reference"]["channel_count"] = 1
        errors = MODULE.validate_score_free_record(record)
        self.assertIn("alignment field set differs", errors)
        self.assertIn(
            "alignment numeric field differs: minimum_correlation", errors
        )
        self.assertIn("alignment side topology differs: reference", errors)

    def test_malformed_nested_types_return_errors_instead_of_crashing(self) -> None:
        record = copy.deepcopy(self.replay["records"][0])
        record["evidence_scope"] = None
        record["support"] = None
        record["alignment"]["support"]["reasons"] = [None]
        errors = MODULE.validate_score_free_record(record)
        self.assertIn("evidence scope differs", errors)
        self.assertIn("oracle support differs", errors)
        self.assertIn("alignment reasons differ", errors)

    def test_schema_is_score_free_and_exposes_all_eventual_output_slots(self) -> None:
        schema = json.loads(MODULE.SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["public_verdict_enabled"]["const"])
        outcomes = schema["properties"]["outcomes"]["properties"]
        for key in (
            "impairment_severity",
            "audibility_probability",
            "artifact_profile",
        ):
            self.assertIn(key, outcomes)
        self.assertEqual("null", outcomes["impairment_severity"]["type"])
        self.assertEqual("null", outcomes["audibility_probability"]["type"])
        components = schema["$defs"]["artifact_profile"]["properties"]["components"]
        self.assertEqual(set(MODULE.ARTIFACT_COMPONENTS), set(components["required"]))

    def test_replay_is_path_free_and_uses_only_synthetic_numeric_fixtures(self) -> None:
        serialized = json.dumps(self.replay, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("Application Support", serialized)
        self.assertNotIn(".wav", serialized)
        self.assertTrue(
            self.replay["access_boundary"]["synthetic_numeric_fixtures_only"]
        )
        source = (SCRIPTS / "perceptual_degradation_oracle.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('add_parser("live")', source)
        self.assertNotIn('add_parser("metric")', source)

    def test_committed_replay_and_plan_validate(self) -> None:
        committed_replay = MODULE.load_json(MODULE.REPLAY)
        self.assertEqual([], MODULE.validate_replay(committed_replay))
        self.assertEqual(
            MODULE.canonical_bytes(self.replay), MODULE.REPLAY.read_bytes()
        )
        self.assertEqual([], MODULE.validate_plan(MODULE.load_json(MODULE.PLAN)))


if __name__ == "__main__":
    unittest.main()
