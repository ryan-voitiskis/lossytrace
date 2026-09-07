"""Stored synthetic evidence checks; never rerun the full-size measurement."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "research/toolchains/evidence/perceptual-degradation-alignment-runtime-synthetic-20260908-001.json"


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


class AlignmentRuntimeResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_bytes())
        cls.observed = cls.report["observations"]

    def test_result_preserves_bound_protocol_and_prior_real_result(self):
        for binding in self.report["bindings"].values():
            self.assertEqual(binding["sha256"], hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest())
        self.assertEqual(self.report["bindings"]["plan"]["sha256"], self.observed["plan_sha256"])
        self.assertEqual(self.report["execution"]["local_pre_observation_head"], self.observed["execution_head"])
        self.assertFalse(self.report["execution"]["externally_preregistered"])

    def test_all_eight_slots_remain_with_unavailable_timeout_alignment(self):
        self.assertEqual(8, self.observed["planned_case_slots"])
        self.assertEqual(2, len(self.observed["replays"]))
        for rows in self.observed["replays"]:
            self.assertEqual(["identity_baseline", "identity_instrumented", "constant_envelope", "topology_mismatch"], [row["case"] for row in rows])
            for row in rows[:2]:
                self.assertEqual("alignment_timeout", row["outcome"])
                self.assertIsNone(row["alignment"])
                self.assertGreaterEqual(row["alignment_seconds"], 180)
            for row in rows[2:]:
                self.assertEqual("completed", row["outcome"])
                self.assertEqual("unsupported", row["alignment"]["status"])
                self.assertTrue(all(value is None for value in row["alignment"]["alignment"]["summary"].values()))

    def test_completed_outputs_and_timing_repeatability_are_separate(self):
        left, right = self.observed["replays"]
        self.assertNotEqual(canonical(left), canonical(right))
        for a, b in zip(left[2:], right[2:], strict=True):
            self.assertEqual(canonical(a["alignment"]), canonical(b["alignment"]))
        self.assertFalse(self.observed["timing_byte_identity_required"])
        self.assertEqual([None, None], self.observed["baseline_instrumented_completed_alignment_bytes_equal"])
        self.assertEqual([None, None, True, True], [row["completed_alignment_bytes_equal"] for row in self.observed["repeatability"]])

    def test_localization_summary_is_derived_from_observed_partial_work(self):
        for rows, summary in zip(self.observed["replays"], self.report["summary"], strict=True):
            row, projected = rows[1], summary[1]
            timing = row["stage_timing"]
            seconds = timing["exclusive_seconds"]["structural_correlation"]
            self.assertEqual(seconds, projected["structural_correlation_seconds"])
            self.assertAlmostEqual(100 * seconds / row["alignment_seconds"], projected["structural_correlation_percent_of_observed_alignment_time"])
            self.assertEqual(["alignment_other", "channel_other", "structural_other", "structural_correlation"], timing["deadline_stack"])
            self.assertEqual(1, timing["entered"]["channel_other"])
            self.assertEqual(0, timing["completed"]["channel_other"])
            self.assertEqual(timing["completed"]["structural_correlation"] + 1, timing["entered"]["structural_correlation"])

    def test_projection_matches_independently_audited_bytes(self):
        audit = self.report["independent_artifact_audit"]
        self.assertEqual(audit["result_sha256"], hashlib.sha256(canonical(self.observed)).hexdigest())
        self.assertTrue(audit["all_eight_slots_audited"])
        self.assertFalse(audit["whole_round_bytes_equal"])

    def test_research_and_privacy_gates_remain_closed(self):
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))
        for key in ("baseline_completed_within_alignment_budget_both_rounds", "full_rate_pipeline_qualified", "real_audio_accessed", "codec_executed", "perceptual_support", "public_verdict_enabled", "objective_complete"):
            self.assertFalse(self.observed[key])
        encoded = canonical(self.report)
        for token in (b"/Users/", b"/private/", b"Application Support", b"file://", b"NaN", b"Infinity", b"reference_samples", b"test_samples"):
            self.assertNotIn(token, encoded)


if __name__ == "__main__":
    unittest.main()
