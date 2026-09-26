from __future__ import annotations

import copy
import importlib
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
R = importlib.import_module("perceptual_degradation_alignment_runtime")


def incomplete(case, outcome="worker_timeout"):
    return {"case": case, "outcome": outcome, "alignment": None}


class RuntimeInstrumentationTest(unittest.TestCase):
    def test_fixture_is_deterministic_bounded_and_immutable(self):
        a = R.fixture("identity_baseline", 47)
        self.assertEqual(a, R.fixture("identity_instrumented", 47))
        self.assertIs(a[0], a[1])
        self.assertEqual([47, 47], list(map(len, a[0])))
        self.assertLess(max(abs(x) for channel in a[0] for x in channel), 1)
        with self.assertRaises(TypeError):
            a[0][0][0] = 0

    def test_full_size_construction_only_has_the_declared_shape(self):
        a, b = R.fixture("identity_baseline")
        self.assertEqual([576008, 576008], list(map(len, a)))
        self.assertIs(a, b)

    def test_fixture_rejects_unknown_case_and_geometry(self):
        for name, frames in (("unknown", 32), ("identity_baseline", True), ("identity_baseline", 0), ("identity_baseline", R.FRAMES + 1)):
            with self.assertRaises(ValueError):
                R.fixture(name, frames)

    def test_fast_abstention_fixtures_keep_full_shape_contract(self):
        a, b = R.fixture("constant_envelope", 32)
        self.assertEqual(((0.125,) * 32,) * 2, a)
        self.assertIs(a, b)
        a, b = R.fixture("topology_mismatch", 32)
        self.assertEqual((2, 1), (len(a), len(b)))

    def test_wrappers_preserve_actual_small_alignment_bytes(self):
        baseline = R.measure("identity_baseline", frames=2400, rate=200, seconds=20)
        instrumented = R.measure("identity_instrumented", frames=2400, rate=200, seconds=20)
        self.assertEqual("completed", baseline["outcome"])
        self.assertEqual("completed", instrumented["outcome"])
        self.assertEqual(R.canonical(baseline["alignment"]), R.canonical(instrumented["alignment"]))
        timing = instrumented["stage_timing"]
        self.assertEqual(timing["entered"], timing["completed"])
        self.assertGreater(timing["entered"]["structural_correlation"], 0)
        self.assertGreater(timing["entered"]["drift_correlation"], 0)
        self.assertLessEqual(sum(timing["exclusive_seconds"].values()), instrumented["alignment_seconds"] + 0.01)

    def test_wrapper_restoration_on_success_and_exception(self):
        original = R.alignment.correlate
        timer = R.StageTimer()
        with self.assertRaisesRegex(RuntimeError, "test"):
            with timer.installed():
                self.assertIsNot(original, R.alignment.correlate)
                raise RuntimeError("test")
        self.assertIs(original, R.alignment.correlate)

    def test_signal_deadline_records_missing_alignment_and_restores_state(self):
        original = R.alignment.correlate
        handler = signal.getsignal(signal.SIGALRM)
        def slow(**kwargs):
            time.sleep(0.1)
        record = R.measure("identity_instrumented", frames=32, rate=200, seconds=0.01, align_fn=slow)
        self.assertEqual("alignment_timeout", record["outcome"])
        self.assertIsNone(record["alignment"])
        self.assertEqual(["alignment_other"], record["stage_timing"]["deadline_stack"])
        self.assertEqual(0, record["stage_timing"]["completed"]["alignment_other"])
        self.assertIs(original, R.alignment.correlate)
        self.assertEqual(handler, signal.getsignal(signal.SIGALRM))
        self.assertEqual((0.0, 0.0), signal.getitimer(signal.ITIMER_REAL))

    def test_existing_alarm_is_not_overwritten(self):
        with patch.object(R.signal, "getitimer", return_value=(5.0, 0.0)), patch.object(R.signal, "setitimer") as setter:
            with self.assertRaisesRegex(ValueError, "pre-existing"):
                R.measure("identity_baseline", frames=32)
            setter.assert_not_called()

    def test_invalid_deadline_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                R.measure("identity_baseline", frames=32, seconds=value)

    def test_numeric_invalidity_and_polarity_are_preserved_under_wrappers(self):
        values = [1.0, -1.0] * 16
        arguments = [(values, [-x for x in values]), (values, [0.0] * 32), ([1e-300, -1e-300] * 16, [1e-300, -1e-300] * 16)]
        expected = [R.alignment.correlate(a, b, 0).record() for a, b in arguments]
        with R.StageTimer().installed():
            actual = [R.alignment.correlate(a, b, 0).record() for a, b in arguments]
        self.assertEqual(expected, actual)
        self.assertAlmostEqual(-1.0, actual[0]["value"])
        self.assertIsNone(actual[1]["value"])

    def test_exclusive_nested_accounting_does_not_double_count(self):
        ticks = iter((0, 0, 1, 3, 4))
        timer = R.StageTimer(clock=lambda: next(ticks))
        with timer.stage("alignment_other"):
            with timer.stage("envelope"):
                pass
        self.assertEqual(2, timer.seconds["alignment_other"])
        self.assertEqual(2, timer.seconds["envelope"])


class RuntimeBoundaryTest(unittest.TestCase):
    def test_parent_runs_exactly_two_ordered_mocked_rounds(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(R.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(R.sys, "stderr"), \
                patch.object(R.subprocess, "check_output", side_effect=[b"", b"f" * 40 + b"\n"]), \
                patch.object(R, "native_preflight"), patch.object(R, "reserve"), \
                patch.object(R, "run_worker", side_effect=lambda case: incomplete(case)) as worker:
            report = R.execute(Path(directory))
            self.assertEqual(list(R.CASES) * 2, [call.args[0] for call in worker.call_args_list])
            self.assertEqual(8, report["planned_case_slots"])
            paths = list(Path(directory).iterdir())
            self.assertEqual(1, len(paths))
            self.assertEqual({"execution.json", "round-1.json", "round-2.json", "result.json"}, {p.name for p in paths[0].iterdir()})

    def test_dirty_checkout_stops_before_runtime_or_generation(self):
        with patch.object(R.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(R.subprocess, "check_output", return_value=b" M modified"), \
                patch.object(R, "native_preflight") as native, patch.object(R, "run_worker") as worker:
            with self.assertRaisesRegex(ValueError, "clean"):
                R.execute(Path("."))
            native.assert_not_called()
            worker.assert_not_called()

    def test_plan_binding_and_experiment(self):
        plan = R.load_plan()
        self.assertEqual(R.EXPERIMENT, plan["experiment"])
        self.assertTrue(all(value is False for value in plan["claim_boundary"].values()))

    def test_mutated_binding_fails_closed(self):
        with patch.object(R.binding, "sha_file", return_value="0" * 64), self.assertRaisesRegex(ValueError, "changed"):
            R.load_plan()

    def test_reserve_prevents_execution(self):
        with patch.object(R.shutil, "disk_usage") as usage:
            usage.return_value.free = 15 * 1024**3 - 1
            with self.assertRaises(ValueError):
                R.reserve()

    def test_native_mismatch_is_rejected_without_running_codec(self):
        with patch.object(R.binding, "bind_tools", return_value={}), self.assertRaisesRegex(ValueError, "native"):
            R.native_preflight(R.load_plan())

    def test_worker_timeout_is_not_alignment_support(self):
        with patch.object(R.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 210)):
            self.assertEqual(incomplete(R.CASES[0]), R.run_worker(R.CASES[0]))

    def test_worker_failure_and_output_limit(self):
        for code, data in ((1, b"error"), (0, b"x" * (R.MAX_JSON + 1))):
            with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], code, data, b"")):
                self.assertEqual("worker_failed_or_output_bound", R.run_worker(R.CASES[0])["outcome"])

    def test_worker_rejects_malformed_json_and_wrong_geometry(self):
        for payload in (b"[", b"[]", b"{}"):
            with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, payload, b"")):
                self.assertEqual("invalid_worker_record", R.run_worker(R.CASES[0])["outcome"])

    def test_completed_worker_validation_and_unknown_fields(self):
        # Small real rejection with a mocked worker-scale geometry field.
        record = R.measure("topology_mismatch", frames=32, seconds=2)
        record["frames"] = R.FRAMES
        R.validate_case(record, "topology_mismatch")
        with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, R.canonical(record), b"")):
            self.assertEqual(record, R.run_worker("topology_mismatch"))
        for field, value in (("private_path", "undeclared"), ("frames", 32), ("perceptual_support", True), ("alignment_seconds", float("nan"))):
            changed = {**record, field: value}
            with self.assertRaises(ValueError):
                R.validate_case(changed, "topology_mismatch")

    def test_timing_validation_does_not_accept_completed_timeout_stack(self):
        record = R.measure("topology_mismatch", frames=32, seconds=2)
        record["frames"] = R.FRAMES
        changed = copy.deepcopy(record)
        changed["stage_timing"]["deadline_stack"] = ["alignment_other"]
        with self.assertRaises(ValueError):
            R.validate_case(changed, "topology_mismatch")
        changed = copy.deepcopy(record)
        changed["stage_timing"]["exclusive_seconds"]["alignment_other"] = 1000
        with self.assertRaises(ValueError):
            R.validate_case(changed, "topology_mismatch")

    def test_completed_alignment_comparison_excludes_timings(self):
        rows = [incomplete(case) for case in R.CASES]
        record = R.measure("topology_mismatch", frames=32, seconds=2)
        record["frames"] = R.FRAMES
        rows[3] = record
        second = copy.deepcopy(rows)
        second[3]["alignment_seconds"] += 0.01
        report = R.aggregate([rows, second])
        self.assertTrue(report["repeatability"][3]["completed_alignment_bytes_equal"])
        self.assertNotEqual(R.canonical(rows), R.canonical(second))

    def test_child_invocation_is_isolated_and_has_no_audio_argument(self):
        with patch.object(R.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"")) as run:
            R.run_worker("identity_baseline")
        command = run.call_args.args[0]
        self.assertEqual(["-I", str(Path(R.__file__).resolve()), "--worker-case", "identity_baseline"], command[1:])
        self.assertEqual(210, run.call_args.kwargs["timeout"])

    def test_complete_denominator_and_missingness_not_byte_identity(self):
        rows = [incomplete(case) for case in R.CASES]
        report = R.aggregate([rows, copy.deepcopy(rows)])
        self.assertEqual(8, report["planned_case_slots"])
        self.assertFalse(report["baseline_completed_within_alignment_budget_both_rounds"])
        self.assertFalse(report["full_rate_pipeline_qualified"])
        self.assertFalse(report["timing_byte_identity_required"])
        self.assertTrue(all(row["completed_alignment_bytes_equal"] is None for row in report["repeatability"]))

    def test_missing_reordered_and_unknown_cases_rejected(self):
        rows = [incomplete(case) for case in R.CASES]
        for replays in ([rows], [rows, rows[:-1]], [rows, list(reversed(rows))]):
            with self.assertRaises(ValueError):
                R.aggregate(replays)
        rows[0]["outcome"] = "new_reason"
        with self.assertRaises(ValueError):
            R.aggregate([rows, rows])

    def test_new_output_is_no_clobber_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "report.json"
            R.write_new(file, {"ok": True})
            self.assertEqual({"ok": True}, json.loads(file.read_bytes()))
            with self.assertRaises(FileExistsError):
                R.write_new(file, {})
            with patch.object(R, "MAX_JSON", 1), self.assertRaises(ValueError):
                R.write_new(Path(directory) / "too-big.json", {})

    def test_cli_has_no_audio_rate_deadline_or_case_substitution_route(self):
        for options in (["--input", "private.wav"], ["--rate", "2000"], ["--worker-case", "undeclared"], ["--seconds", "999"]):
            process = subprocess.run([sys.executable, str(Path(R.__file__)), *options], capture_output=True)
            self.assertNotEqual(0, process.returncode)
            self.assertEqual(b"", process.stdout)

    def test_default_cli_does_not_run_full_size_work(self):
        process = subprocess.run([sys.executable, str(Path(R.__file__)), "--check-plan"], check=True, capture_output=True)
        self.assertFalse(json.loads(process.stdout)["full_size_execution_performed"])


if __name__ == "__main__":
    unittest.main()
