"""Constructed qualification guards; no full-size alignment or real audio."""
import copy
from collections import Counter
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import perceptual_degradation_global_qualification as Q


class WorkloadQualificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary, cls.provenance = Q.native.build(cls.directory.name)

    def setUp(self):
        self.kernel_sha = self.provenance["binary_sha256"]

    def row(self, case):
        peaks = list(range(0, 24, 3))
        lags = sorted({lag for peak in peaks for lag in range(peak*240-240, peak*240+241)})
        geometries = Counter()
        for lag in lags:
            length = Q.FRAMES-abs(lag)
            stride = max(1, length//16384)
            geometries[(length, stride, len(range(0, length, stride)))] += 1
        records = [{"overlap_frames": k[0], "stride": k[1], "sampled_frames": k[2], "candidate_count": n}
                   for k, n in sorted(geometries.items())]
        searches = 1 if case.endswith("global_pair") else 2
        return {"case": case, "frames": Q.FRAMES, "sample_rate_hz": Q.RATE, "outcome": "completed",
                "wall_seconds": 1.0, "cpu_seconds": .8, "stage_wall_seconds": {}, "stage_cpu_seconds": {},
                "other_wall_seconds": 1.0, "other_cpu_seconds": .8,
                "alignment": None if case.endswith("global_pair") else {
                    "record_kind": Q.alignment.RECORD_KIND, "sample_correction_applied": False,
                    "perceptual_claim": False, "public_verdict_enabled": False},
                "component": {"coarse_candidates": 801, "selected_peaks": peaks,
                              "candidate_inventory_sha256": Q.sha(Q.canonical(lags)),
                              "global_candidates": 3848, "predecessor_sha256": "a"*64,
                              "successor_sha256": "a"*64, "all_candidate_records_byte_identical": True}
                             if case.endswith("global_pair") else {},
                "local_native": {"native_candidates": 0, "fallback_candidates": 0, "searches": []},
                "global_native": {"native_candidates": 3848*searches, "fallback_candidates": 0,
                                  "searches": [{"reference_frames": Q.FRAMES, "test_frames": Q.FRAMES,
                                                "candidate_count": 3848, "search_count": searches}],
                                  "short_overlap_candidates": 0, "geometry_rows": len(records),
                                  "geometry_sha256": Q.sha(Q.canonical(records)),
                                  "sampled_pair_evaluations": sum(r["sampled_frames"]*r["candidate_count"] for r in records)},
                "input_sha256": "b"*64, "inputs_unchanged": True, "perceptual_support": False}

    def rounds(self):
        return [[self.row(case) for case in Q.CASES] for _ in range(2)]

    def test_frozen_plan_and_no_real_access_boundary(self):
        plan = Q.load_plan()
        self.assertEqual(list(Q.CASES), plan["cases"])
        self.assertTrue(all(value is False for value in plan["claim_boundary"].values()))

    def test_missing_binding_and_changed_limits_fail_closed(self):
        plan = Q.load_plan()
        for mutation in (lambda p: p["bindings"].pop("alignment_v4"),
                         lambda p: p["limits"].update(case_seconds=181),
                         lambda p: p["bindings"]["alignment_v5"].update(sha256="0"*64),
                         lambda p: p["claim_boundary"].update(perceptual_support=True)):
            changed = copy.deepcopy(plan)
            mutation(changed)
            with patch.object(Q.PLAN.__class__, "read_bytes", return_value=Q.canonical(changed)), self.assertRaises(ValueError):
                Q.load_plan()

    def test_small_generators_deterministic_distinct_and_immutable(self):
        hashes = []
        for family in Q.FAMILIES:
            a, b = Q.fixture(family, 4800), Q.fixture(family, 4800)
            self.assertEqual(a, b)
            self.assertEqual((4800, 4800), tuple(map(len, a)))
            self.assertTrue(all(type(c) is tuple for c in a))
            hashes.append(Q.input_hash(a))
        self.assertEqual(4, len(set(hashes)))
        for family, frames in (("unknown", 1), ("quantized", 0), ("quantized", Q.FRAMES+1)):
            with self.assertRaises(ValueError):
                Q.fixture(family, frames)

    def test_small_component_exact_and_counter_geometry(self):
        for family in Q.FAMILIES:
            row = Q.measure(family+":global_pair", self.binary, self.kernel_sha, frames=1200, rate=200)
            self.assertEqual("completed", row["outcome"])
            self.assertTrue(row["component"]["all_candidate_records_byte_identical"])
            self.assertTrue(row["inputs_unchanged"])
            self.assertIsNone(Q.alignment.NATIVE_BACKEND)

    def test_small_timed_alignment_matches_untimed(self):
        for family in Q.FAMILIES:
            row = Q.measure(family+":full_native", self.binary, self.kernel_sha, frames=1200, rate=200)
            a = Q.fixture(family, 1200)
            kernel = Q.native.Kernel(self.binary, self.kernel_sha)
            with patch.object(Q.alignment, "NATIVE_BACKEND", kernel):
                expected = Q.alignment.align_channels(reference_channels=a, test_channels=a,
                    reference_channel_map=["L", "R"], test_channel_map=["L", "R"], sample_rate_hz=200,
                    recipe_identity=Q.PLAN_ID+":"+family, minimum_active_seconds=4, maximum_delay_seconds=2)
            self.assertEqual(Q.canonical(expected), Q.canonical(row["alignment"]))
            self.assertLessEqual(sum(row["stage_wall_seconds"].values()), row["wall_seconds"]+.01)

    def test_deadline_restores_backend_and_signal(self):
        previous = signal.getsignal(signal.SIGALRM)
        with patch.object(Q.alignment, "align_channels", side_effect=Q.Deadline):
            row = Q.measure("quantized:full_native", self.binary, self.kernel_sha, frames=120, rate=20)
        self.assertEqual("case_timeout", row["outcome"])
        self.assertIsNone(row["alignment"])
        self.assertIsNone(Q.alignment.NATIVE_BACKEND)
        self.assertEqual(previous, signal.getsignal(signal.SIGALRM))
        self.assertEqual((0.0, 0.0), signal.getitimer(signal.ITIMER_REAL))

    def test_worker_failures_accounted_without_retry(self):
        case = Q.CASES[0]
        for result, reason in ((subprocess.CompletedProcess([], 1, b"", b""), "worker_failed"),
                               (subprocess.CompletedProcess([], 0, b"{}", b""), "invalid_worker_record"),
                               (subprocess.CompletedProcess([], 0, b"null", b""), "invalid_worker_record"),
                               (subprocess.CompletedProcess([], 0, b"[]", b""), "invalid_worker_record")):
            with patch.object(Q.subprocess, "run", return_value=result) as invoke:
                self.assertEqual(reason, Q.run_worker(case, self.binary, self.kernel_sha)["outcome"])
                invoke.assert_called_once()
        with patch.object(Q.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 210)):
            self.assertEqual("worker_timeout", Q.run_worker(case, self.binary, self.kernel_sha)["outcome"])

    def test_complete_accounting_and_clock_exclusion(self):
        rounds = self.rounds()
        rounds[1][0]["wall_seconds"] = 2.0
        result = Q.aggregate(rounds, ["passed"]*4)
        self.assertEqual("synthetic_workload_margin_passed", result["state"])
        self.assertEqual(16, result["planned_slots"])
        self.assertFalse(result["full_rate_pipeline_qualified"])

    def test_margin_failure_and_numerical_difference_preserved(self):
        rounds = self.rounds()
        rounds[0][1]["wall_seconds"] = 120.001
        result = Q.aggregate(rounds, ["passed"]*4)
        self.assertFalse(result["all_full_alignments_within_120_seconds"])
        rounds = self.rounds()
        rounds[1][0]["component"].update(successor_sha256="d"*64, all_candidate_records_byte_identical=False)
        result = Q.aggregate(rounds, ["passed"]*4)
        self.assertFalse(result["global_candidate_equivalence_passed"])
        self.assertFalse(result["completed_evidence_repeated"])

    def test_timeout_and_resource_stop_remain_in_denominator(self):
        rounds = self.rounds()
        for items in rounds:
            items[0] = Q.incomplete(Q.CASES[0], "not_run_resource_stop")
        result = Q.aggregate(rounds, ["passed", "failed", "not_attempted_after_stop", "not_attempted_after_stop"])
        self.assertFalse(result["all_slots_completed"])
        self.assertIsNone(result["repeatability"][0]["completed_evidence_byte_identical"])
        self.assertEqual(16, result["planned_slots"])

    def test_invalid_accounting_and_claim_rejected(self):
        for mutation in (lambda r: r[0].pop(), lambda r: r[0][0].update(perceptual_support=True),
                         lambda r: r[0][0].update(wall_seconds=float("nan")),
                         lambda r: r[0][0]["local_native"].update(native_candidates=1)):
            rounds = self.rounds()
            mutation(rounds)
            with self.assertRaises(ValueError):
                Q.aggregate(rounds, ["passed"]*4)

    def test_output_is_no_clobber_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"record.json"
            Q.write_new(path, {"fixture": True})
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            with self.assertRaises(FileExistsError):
                Q.write_new(path, {"fixture": False})
            self.assertEqual({"fixture": True}, json.loads(path.read_bytes()))

    def test_reserve_checks_workspace_and_output(self):
        with patch.object(Q.shutil, "disk_usage", return_value=type("Usage", (), {"free": 0})()):
            with self.assertRaises(ValueError):
                Q.reserve(Path(self.directory.name))

    def test_nonisolated_and_dirty_execution_rejected_before_output(self):
        with patch.object(Q, "sys", SimpleNamespace(flags=SimpleNamespace(isolated=0))), \
                patch.object(Q, "load_plan") as load:
            with self.assertRaises(ValueError):
                Q.execute(Path(self.directory.name))
            load.assert_not_called()
        with patch.object(Q, "sys", SimpleNamespace(flags=SimpleNamespace(isolated=1))), \
                patch.object(Q.subprocess, "check_output", return_value=b" M dirty"), \
                patch.object(Q, "reserve") as reserve:
            with self.assertRaises(ValueError):
                Q.execute(Path(self.directory.name))
            reserve.assert_not_called()

    def test_resource_stop_does_not_restart_second_round(self):
        plan = Q.load_plan()
        calls = 0
        def reserve(parent):
            nonlocal calls
            calls += 1
            if calls >= 4:
                raise ValueError("constructed reserve stop")
        def git(args, **kwargs):
            return b"" if "status" in args else b"e"*40
        provenance = {**plan["native_build"], "binary_sha256": self.kernel_sha}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(Q, "sys", SimpleNamespace(flags=SimpleNamespace(isolated=1), stderr=sys.stderr)), \
                patch.object(Q.subprocess, "check_output", side_effect=git), \
                patch.object(Q, "check_tools"), patch.object(Q, "reserve", side_effect=reserve), \
                patch.object(Q.native, "build", return_value=(self.binary, provenance)), \
                patch.object(Q.native, "Kernel"), patch.object(Q, "run_worker", side_effect=lambda case, *args: self.row(case)) as worker:
            result = Q.execute(Path(directory))
            self.assertEqual(1, worker.call_count)
            self.assertEqual(16, result["planned_slots"])
            self.assertEqual(15, sum(r["outcome"] == "not_run_resource_stop" for rows in result["rounds"] for r in rows))
            self.assertFalse(result["all_slots_completed"])
            self.assertTrue((Path(directory)/(Q.PLAN_ID+".launch.json")).is_file())
            with self.assertRaises(ValueError):
                Q.execute(Path(directory))

    def test_component_count_or_geometry_cannot_fabricate_pass(self):
        for mutate in (lambda r: r["component"].update(global_candidates=3847),
                       lambda r: r["global_native"].update(geometry_sha256="0"*64),
                       lambda r: r["global_native"].update(native_candidates=0)):
            row = self.row(Q.CASES[0])
            mutate(row)
            with self.assertRaises(ValueError):
                Q.validate_case(row, Q.CASES[0])


if __name__ == "__main__":
    unittest.main()
