"""Stored native qualification evidence only; never rerun full-size alignment."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "research/toolchains/evidence/perceptual-degradation-alignment-native-synthetic-20260908-001.json"


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


class NativeResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_bytes())
        cls.observed = cls.report["observations"]

    def test_bound_frozen_protocol_and_predecessors_unchanged(self):
        for binding in self.report["bindings"].values():
            self.assertEqual(binding["sha256"], hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest())
        plan = json.loads((ROOT / self.report["bindings"]["plan"]["path"]).read_bytes())
        for binding in plan["bindings"].values():
            self.assertEqual(binding["sha256"], hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest())
        self.assertEqual(self.observed["plan_sha256"], self.report["bindings"]["plan"]["sha256"])
        self.assertEqual(self.observed["execution_head"], self.report["execution"]["local_pre_observation_head"])
        self.assertFalse(self.report["execution"]["externally_preregistered"])
        self.assertEqual(1, self.report["execution"]["runner_invocations"])

    def test_eight_completed_slots_and_full_search_coverage(self):
        self.assertEqual(8, self.observed["planned_case_slots"])
        self.assertEqual(2, len(self.observed["replays"]))
        expected = [{"candidate_count": 9601, "search_count": 14, "stride": 1, "window_frames": 24000},
                    {"candidate_count": 121, "search_count": 10, "stride": 2, "window_frames": 48000}]
        for rows in self.observed["replays"]:
            self.assertEqual(["identity_baseline", "identity_instrumented", "constant_envelope", "topology_mismatch"], [r["case"] for r in rows])
            for index, r in enumerate(rows):
                self.assertEqual("completed", r["outcome"])
                self.assertEqual((576008, 48000), (r["frames"], r["sample_rate_hz"]))
                self.assertGreater(r["alignment_seconds"], 0)
                self.assertLessEqual(r["alignment_seconds"], 180)
                self.assertEqual(0, r["native_audit"]["fallback_candidates"])
                self.assertEqual(135624 if index < 2 else 0, r["native_audit"]["native_candidates"])
                self.assertEqual(expected if index < 2 else [], r["native_audit"]["searches"])
                if index < 2:
                    self.assertEqual("supported", r["alignment"]["status"])
                    self.assertEqual([], r["alignment"]["support"]["reasons"])
                    self.assertEqual(2, len(r["alignment"]["alignment"]["channels"]))

    def test_numerical_bytes_repeat_without_timing_byte_requirement(self):
        left, right = self.observed["replays"]
        self.assertNotEqual(canonical(left), canonical(right))
        for rows in (left, right):
            self.assertEqual(canonical(rows[0]["alignment"]), canonical(rows[1]["alignment"]))
        for a, b in zip(left, right, strict=True):
            self.assertEqual(canonical(a["alignment"]), canonical(b["alignment"]))
            self.assertEqual(a["native_audit"], b["native_audit"])
        self.assertFalse(self.observed["timing_byte_identity_required"])
        self.assertEqual([True, True], self.observed["baseline_instrumented_completed_alignment_bytes_equal"])

    def test_guards_preserve_reasons_and_null_common_summaries(self):
        for rows in self.observed["replays"]:
            for index in (2, 3):
                a = rows[index]["alignment"]
                self.assertEqual("unsupported", a["status"])
                self.assertTrue(all(v is None for v in a["alignment"]["summary"].values()))
                self.assertEqual(["no_valid_coarse_correlation"] if index == 2 else ["channel_map_mismatch", "channel_topology_mismatch"], a["support"]["reasons"])
            self.assertEqual([], rows[3]["alignment"]["alignment"]["channels"])
            for channel in rows[2]["alignment"]["alignment"]["channels"]:
                self.assertEqual({"valid": 0, "invalid": {"zero_centered_energy": 801}}, channel["diagnostics"]["search"]["coarse"])

    def test_audited_payload_and_timing_projection(self):
        audit = self.report["independent_artifact_audit"]
        self.assertEqual(audit["result_sha256"], hashlib.sha256(canonical(self.observed)).hexdigest())
        self.assertTrue(audit["all_eight_slots_audited"])
        for rows, summary in zip(self.observed["replays"], self.report["summary"], strict=True):
            row, s = rows[1], summary[1]
            t = row["stage_timing"]
            self.assertEqual(t["entered"], t["completed"])
            self.assertIsNone(t["deadline_stack"])
            self.assertEqual(14, t["completed"]["structural_local_search"])
            self.assertEqual(10, t["completed"]["drift_local_search"])
            self.assertEqual(t["exclusive_seconds"]["structural_local_search"], s["structural_local_search_seconds"])
            self.assertAlmostEqual(100*s["structural_local_search_seconds"]/row["alignment_seconds"], s["structural_percent_of_alignment_seconds"])
            self.assertLessEqual(sum(t["exclusive_seconds"].values()), row["alignment_seconds"]+.01)

    def test_research_scope_privacy_and_unavailable_predecessor_equivalence(self):
        self.assertTrue(all(v is False for v in self.report["claim_boundary"].values()))
        self.assertTrue(self.observed["baseline_completed_within_alignment_budget_both_rounds"])
        for key in ("full_rate_pipeline_qualified", "real_audio_accessed", "codec_executed", "perceptual_support", "public_verdict_enabled", "objective_complete"):
            self.assertFalse(self.observed[key])
        self.assertFalse(self.report["qualification"]["full_size_predecessor_identity_bytes_available"])
        self.assertFalse(self.report["qualification"]["all_inputs_and_platforms_proven_equivalent"])
        self.assertFalse(self.report["qualification"]["large_study_throughput_qualified"])
        for token in (b"/Users/", b"/private/", b"/Volumes/", b"NaN", b"Infinity", b"reference_samples", b"test_samples"):
            self.assertNotIn(token, canonical(self.report))


if __name__ == "__main__":
    unittest.main()
