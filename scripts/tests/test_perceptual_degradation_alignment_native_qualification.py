from __future__ import annotations
import copy
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts")) if str(ROOT / "scripts") not in sys.path else None
import perceptual_degradation_alignment_native_qualification as R


class QualificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary, cls.provenance = R.native.build(Path(cls.directory.name))

    def setUp(self):
        self.kernel = R.native.Kernel(self.binary, self.provenance["binary_sha256"])
        self.backend = patch.object(R.alignment, "NATIVE_BACKEND", self.kernel)
        self.backend.start()
        self.addCleanup(self.backend.stop)

    def small_control(self):
        record = R.measure("topology_mismatch", frames=32, seconds=2)
        record["frames"] = R.FRAMES
        return record

    def test_plan_bindings_and_closed_claims(self):
        plan = R.load_plan()
        self.assertEqual(R.EXPERIMENT, plan["experiment"])
        self.assertFalse(any(plan["claim_boundary"].values()))
        self.assertEqual(0, plan["equivalence_contract"]["numeric_tolerance"])

    def test_changed_file_and_native_runtime_fail_closed(self):
        with patch.object(R.binding, "sha_file", return_value="0"*64), self.assertRaises(ValueError):
            R.load_plan()
        with patch.object(R.binding, "bind_tools", return_value={}), self.assertRaises(ValueError):
            R.native_preflight(R.load_plan())

    def test_actual_small_wrapped_unwrapped_bytes_and_coverage(self):
        a = R.measure("identity_baseline", frames=2400, rate=200, seconds=20)
        with patch.object(R.alignment, "NATIVE_BACKEND", R.native.Kernel(self.binary, self.provenance["binary_sha256"])):
            b = R.measure("identity_instrumented", frames=2400, rate=200, seconds=20)
        self.assertEqual("completed", a["outcome"])
        self.assertEqual("completed", b["outcome"])
        self.assertEqual(R.canonical(a["alignment"]), R.canonical(b["alignment"]))
        self.assertEqual(a["native_audit"], b["native_audit"])
        self.assertEqual(0, a["native_audit"]["fallback_candidates"])
        self.assertEqual(14, b["stage_timing"]["completed"]["structural_local_search"])
        self.assertEqual(10, b["stage_timing"]["completed"]["drift_local_search"])

    def test_alarm_and_wrapper_restoration(self):
        original, handler = R.alignment.local_lag, signal.getsignal(signal.SIGALRM)
        def slow(**kwargs):
            time.sleep(.1)
        result = R.measure("identity_instrumented", frames=32, seconds=.01, align_fn=slow)
        self.assertEqual("alignment_timeout", result["outcome"])
        self.assertIsNone(result["alignment"])
        self.assertIs(original, R.alignment.local_lag)
        self.assertEqual(handler, signal.getsignal(signal.SIGALRM))

    def test_record_validation_rejects_native_and_geometry_mutations(self):
        record = self.small_control()
        R.validate_case(record, "topology_mismatch")
        for key, value in (("native_audit", None), ("frames", 32), ("perceptual_support", True), ("extra", 1)):
            with self.assertRaises(ValueError):
                R.validate_case({**record, key: value}, "topology_mismatch")
        for change in ({"native_candidates": -1}, {"searches": [{}]}):
            with self.assertRaises(ValueError):
                R.validate_case({**record, "native_audit": {**record["native_audit"], **change}}, "topology_mismatch")

    def test_worker_is_isolated_hash_bound_and_deadline_bounded(self):
        record = self.small_control()
        with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, R.canonical(record), b"")) as run:
            self.assertEqual(record, R.run_worker("topology_mismatch", self.binary, self.provenance["binary_sha256"]))
        command = run.call_args.args[0]
        self.assertIn("-I", command)
        self.assertEqual(self.provenance["binary_sha256"], command[-1])
        self.assertEqual(210, run.call_args.kwargs["timeout"])

    def test_worker_timeout_failure_and_malformed_output(self):
        with patch.object(R.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 210)):
            self.assertEqual("worker_timeout", R.run_worker(R.CASES[0])["outcome"])
        for code, data, expected in ((1, b"", "worker_failed_or_output_bound"), (0, b"{}", "invalid_worker_record"),
                                     (0, b"x"*(R.MAX_JSON+1), "worker_failed_or_output_bound")):
            with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], code, data, b"")):
                self.assertEqual(expected, R.run_worker(R.CASES[0])["outcome"])

    def test_parent_exactly_eight_mocked_slots_and_no_clobber_outputs(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(R.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(R.sys, "stderr"), patch.object(R.subprocess, "check_output", side_effect=[b"", b"a"*40]), \
                patch.object(R, "native_preflight"), patch.object(R, "reserve"), \
                patch.object(R.native, "build", return_value=(self.binary, self.provenance)), \
                patch.object(R, "run_worker", side_effect=lambda case, *args: {"case": case, "outcome": "worker_timeout", "alignment": None}) as worker:
            report = R.execute(Path(directory))
            self.assertEqual(list(R.CASES)*2, [call.args[0] for call in worker.call_args_list])
            self.assertFalse(report["baseline_completed_within_alignment_budget_both_rounds"])
            self.assertEqual(8, report["planned_case_slots"])
            run_root, = Path(directory).iterdir()
            self.assertEqual({"kernel", "execution.json", "round-1.json", "round-2.json", "result.json"}, {p.name for p in run_root.iterdir()})
            for p in run_root.glob("*.json"):
                self.assertEqual(0o600, p.stat().st_mode & 0o777)
                with self.assertRaises(FileExistsError):
                    R.write_new(p, {})

    def test_dirty_tree_and_disk_reserve_prevent_execution(self):
        with patch.object(R.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(R.subprocess, "check_output", return_value=b" M user"), patch.object(R.native, "build") as build:
            with self.assertRaises(ValueError):
                R.execute(Path("."))
            build.assert_not_called()
        with patch.object(R.shutil, "disk_usage", return_value=SimpleNamespace(free=15*1024**3-1)), self.assertRaises(ValueError):
            R.reserve()

    def test_aggregate_preserves_missingness_and_separates_timings(self):
        rows = [{"case": case, "outcome": "worker_timeout", "alignment": None} for case in R.CASES]
        rows[-1] = self.small_control()
        other = copy.deepcopy(rows)
        other[-1]["alignment_seconds"] += .01
        report = R.aggregate([rows, other])
        self.assertTrue(report["repeatability"][-1]["completed_alignment_bytes_equal"])
        self.assertIsNone(report["repeatability"][0]["completed_alignment_bytes_equal"])
        self.assertFalse(report["full_rate_pipeline_qualified"])
        for bad in ([rows], [rows, other[:-1]], [rows, list(reversed(other))]):
            with self.assertRaises(ValueError):
                R.aggregate(bad)

    def test_cli_default_has_no_full_size_execution_or_audio_route(self):
        command = [sys.executable, "-I", str(Path(R.__file__))]
        record = json.loads(subprocess.check_output([*command, "--check-plan"]))
        self.assertFalse(record["full_size_execution_performed"])
        for args in (["--input", "private.wav"], ["--seconds", "999"], ["--worker-case", R.CASES[0]],
                     ["--check-plan", "--kernel", str(self.binary)]):
            self.assertNotEqual(0, subprocess.run([*command, *args], capture_output=True).returncode)


if __name__ == "__main__":
    unittest.main()
