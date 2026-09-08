#!/usr/bin/env python3
"""Bound synthetic-only qualification of opt-in alignment v4 native local search.

No audio input, codec, playback or metric route. Full-size runs are opt-in;
ordinary tests use small constructions and mocked process boundaries.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, nullcontext
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import perceptual_degradation_alignment_v4 as alignment
import perceptual_degradation_correlation_native as native
import perceptual_degradation_digital_tools as binding


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/alignment-native-qualification-plan-20260908.json"
PLAN_ID = "alignment-native-qualification-20260908-001"
RATE, FRAMES, ALIGNMENT_SECONDS = 48000, 576008, 180
WORKER_SECONDS, MAX_JSON = 210, 2 * 1024**2
CASES = ("identity_baseline", "identity_instrumented", "constant_envelope", "topology_mismatch")
STAGES = ("alignment_other", "channel_other", "envelope", "coarse_correlation", "sample_correlation",
          "gain", "drift_other", "drift_local_search", "structural_other", "structural_local_search")
EXPERIMENT = {"sample_rate_hz": RATE, "frames": FRAMES, "reference_channels": 2,
              "cases": list(CASES), "rounds": 2, "workers": 1,
              "alignment_deadline_seconds": ALIGNMENT_SECONDS, "worker_deadline_seconds": WORKER_SECONDS,
              "minimum_active_seconds": 4, "maximum_delay_seconds": 2,
              "minimum_free_gib": 15, "input_mode": "constructed_arrays_only"}
BINDINGS = {
    "alignment_v1": "scripts/perceptual_degradation_alignment.py",
    "alignment_v2": "scripts/perceptual_degradation_alignment_v2.py",
    "alignment_v3": "scripts/perceptual_degradation_alignment_v3.py",
    "topology_freeze": "benchmarks/perceptual-degradation-v1/alignment-topology-freeze.json",
    "validity_plan": "benchmarks/perceptual-degradation-v1/alignment-validity-successor-plan.json",
    "digital_runtime_negative": "research/toolchains/evidence/perceptual-degradation-digital-technical-20260908-001.json",
    "native_tools": "research/toolchains/evidence/perceptual-degradation-digital-native-tools-20260908-001.json",
    "native_binding_implementation": "scripts/perceptual_degradation_digital_tools.py",
    "runtime_predecessor": "scripts/perceptual_degradation_alignment_runtime.py",
    "runtime_negative": "research/toolchains/evidence/perceptual-degradation-alignment-runtime-synthetic-20260908-001.json",
    "alignment_v4": "scripts/perceptual_degradation_alignment_v4.py",
    "native_source": "scripts/perceptual_degradation_correlation_native.c",
    "native_bridge": "scripts/perceptual_degradation_correlation_native.py",
    "native_license": "research/licenses/alignment-kernel-PSF-LICENSE.txt",
    "equivalence_tests": "scripts/tests/test_perceptual_degradation_alignment_v4.py",
    "runner": "scripts/perceptual_degradation_alignment_native_qualification.py",
    "tests": "scripts/tests/test_perceptual_degradation_alignment_native_qualification.py",
}


def canonical(value):
    return binding.canonical(value)


def load_plan():
    plan = json.loads(PLAN.read_bytes())
    if plan.get("plan_id") != PLAN_ID or plan.get("experiment") != EXPERIMENT:
        raise ValueError("synthetic experiment differs")
    if set(plan.get("bindings", {})) != set(BINDINGS):
        raise ValueError("binding inventory differs")
    for key, relative in BINDINGS.items():
        if plan["bindings"][key] != {"path": relative, "sha256": binding.sha_file(ROOT / relative)}:
            raise ValueError("bound file changed")
    if not plan.get("claim_boundary") or any(value is not False for value in plan["claim_boundary"].values()):
        raise ValueError("synthetic claim boundary differs")
    for module in (alignment, alignment.legacy, alignment.topology, binding, native):
        if Path(module.__file__).resolve() != ROOT / "scripts" / (module.__name__ + ".py"):
            raise ValueError("loaded implementation differs")
    return plan


def reserve():
    if shutil.disk_usage(ROOT).free < 15 * 1024**3:
        raise ValueError("disk reserve unavailable")


def native_preflight(plan):
    # Existing version/help metadata only, never an encode/decode invocation.
    installed = {name: Path(shutil.which(name) or "") for name in ("ffmpeg", "ffprobe", "oggenc")}
    expected = json.loads((ROOT / plan["bindings"]["native_tools"]["path"]).read_bytes())
    if binding.bind_tools(installed) != expected:
        raise ValueError("native runtime binding changed")


def fixture(kind, frames=FRAMES):
    if kind not in CASES or type(frames) is not int or not 0 < frames <= FRAMES:
        raise ValueError("undeclared synthetic construction")
    if kind == "constant_envelope":
        reference = ((0.125,) * frames,) * 2
    else:
        left, right, state = [], [], 0x35A719C3
        for index in range((frames + 1) // 2):
            pair = []
            for _ in range(2):
                state = (1664525 * state + 1013904223) % 2**32
                pair.append((((state >> 16) % 1024) - 512) * 32 * (1 + (index // 137) % 5) / 2**20)
            a, b = pair
            left.extend((a, b))
            right.extend((-b, a))
        reference = (tuple(left[:frames]), tuple(right[:frames]))
    test = (reference[0],) if kind == "topology_mismatch" else reference
    return reference, test


class AlignmentDeadline(Exception):
    pass


class StageTimer:
    """Exclusive stage accounting; wrappers delegate every unchanged operation.

    Stage entry counts and deadline position are performance observations, not
    deterministic numerical output. No profiling of every Python function.
    """
    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.stack = []
        self.started = clock()
        self.seconds = Counter()
        self.entered = Counter()
        self.completed = Counter()
        self.deadline_stack = None

    def charge(self):
        now = self.clock()
        if self.stack:
            self.seconds[self.stack[-1]] += now - self.started
        self.started = now

    @contextmanager
    def stage(self, name):
        if name not in STAGES:
            raise ValueError("unknown timing stage")
        self.charge()
        self.stack.append(name)
        self.entered[name] += 1
        try:
            yield
        except BaseException:
            raise
        else:
            self.completed[name] += 1
        finally:
            self.charge()
            self.stack.pop()

    @contextmanager
    def installed(self):
        originals = {name: getattr(alignment, name) for name in
                     ("_channel", "_rms_envelope", "correlate", "gain_diagnostics", "window_audit", "local_lag")}

        def wrapper(name, select):
            def call(*args, **kwargs):
                with self.stage(select(args, kwargs)):
                    return originals[name](*args, **kwargs)
            return call

        def correlation_stage(args, kwargs):
            if "structural_other" in self.stack:
                return "structural_local_search"
            if "drift_other" in self.stack:
                return "drift_local_search"
            return "coarse_correlation" if kwargs.get("centered", False) else "sample_correlation"

        selectors = {"_channel": lambda a, k: "channel_other", "_rms_envelope": lambda a, k: "envelope",
                     "correlate": correlation_stage, "gain_diagnostics": lambda a, k: "gain",
                     "local_lag": lambda a, k: "structural_local_search" if "structural_other" in self.stack else "drift_local_search",
                     "window_audit": lambda a, k: "structural_other" if k["structural"] else "drift_other"}
        try:
            for name, select in selectors.items():
                setattr(alignment, name, wrapper(name, select))
            yield
        finally:
            for name, original in originals.items():
                setattr(alignment, name, original)

    def record(self):
        if self.stack:
            raise ValueError("unfinished stage stack")
        return {"exclusive_seconds": {name: round(self.seconds[name], 6) for name in STAGES},
                "entered": {name: self.entered[name] for name in STAGES},
                "completed": {name: self.completed[name] for name in STAGES},
                "deadline_stack": self.deadline_stack}


def measure(case, *, frames=FRAMES, rate=RATE, seconds=ALIGNMENT_SECONDS, align_fn=None):
    """Small overrides are for unit tests only; the CLI has no geometry overrides."""
    reference, test = fixture(case, frames)
    instrumented = case != "identity_baseline"
    timer = StageTimer() if instrumented else None
    old_handler = signal.getsignal(signal.SIGALRM)
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("pre-existing alarm must not be replaced")
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("positive bounded deadline required")

    def expired(signum, frame):
        if timer is not None:
            timer.deadline_stack = list(timer.stack)
        raise AlignmentDeadline()

    # Fixture generation/import/startup are outside this isolated alignment timer.
    # The parent worker deadline still bounds the complete process.
    record, outcome = None, "completed"
    call = align_fn or alignment.align_channels
    began = time.perf_counter()
    try:
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        with timer.installed() if timer else nullcontext():
            with timer.stage("alignment_other") if timer else nullcontext():
                record = call(reference_channels=reference, test_channels=test,
                              reference_channel_map=["L", "R"],
                              test_channel_map=["M"] if case == "topology_mismatch" else ["L", "R"],
                              sample_rate_hz=rate, recipe_identity=PLAN_ID + ":" + ("identity" if case.startswith("identity_") else case),
                              minimum_active_seconds=4, maximum_delay_seconds=2)
    except AlignmentDeadline:
        outcome = "alignment_timeout"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    elapsed = time.perf_counter() - began
    return {"case": case, "frames": frames, "sample_rate_hz": rate, "instrumented": instrumented,
            "outcome": outcome, "alignment_seconds": round(elapsed, 6), "alignment": record,
            "stage_timing": timer.record() if timer else None, "inputs_immutable": True,
            "native_audit": alignment.NATIVE_BACKEND.record() if alignment.NATIVE_BACKEND else None,
            "perceptual_support": False}


def run_worker(case, kernel_path=None, kernel_sha256=None):
    env = {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C", "TZ": "UTC",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
    try:
        result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--worker-case", case,
                                 "--kernel", str(kernel_path), "--kernel-sha256", str(kernel_sha256)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=WORKER_SECONDS,
                                env=env, check=False)
    except subprocess.TimeoutExpired:
        return {"case": case, "outcome": "worker_timeout", "alignment": None}
    if result.returncode or len(result.stdout) > MAX_JSON or len(result.stderr) > MAX_JSON:
        return {"case": case, "outcome": "worker_failed_or_output_bound", "alignment": None}
    try:
        record = json.loads(result.stdout)
        validate_case(record, case)
        return record
    except (ValueError, TypeError, KeyError):
        return {"case": case, "outcome": "invalid_worker_record", "alignment": None}


def validate_case(record, case):
    if not isinstance(record, dict) or set(record) != {"case", "frames", "sample_rate_hz", "instrumented", "outcome", "alignment_seconds",
                       "alignment", "stage_timing", "inputs_immutable", "perceptual_support", "native_audit"}:
        raise ValueError("worker field inventory differs")
    if (record.get("case") != case or record.get("frames") != FRAMES or record.get("sample_rate_hz") != RATE
            or record.get("instrumented") is not (case != "identity_baseline")
            or record.get("inputs_immutable") is not True or record.get("perceptual_support") is not False
            or record.get("outcome") not in ("completed", "alignment_timeout")):
        raise ValueError("worker geometry or boundary differs")
    audit = record["native_audit"]
    if (not isinstance(audit, dict) or set(audit) != {"native_candidates", "fallback_candidates", "searches"}
            or any(type(audit[key]) is not int or audit[key] < 0 for key in ("native_candidates", "fallback_candidates"))
            or not isinstance(audit["searches"], list)):
        raise ValueError("native audit differs")
    for search in audit["searches"]:
        if (not isinstance(search, dict) or set(search) != {"window_frames", "stride", "candidate_count", "search_count"}
                or any(type(value) is not int or value < 0 for value in search.values())
                or search["stride"] < 1 or search["search_count"] < 1):
            raise ValueError("native search inventory differs")
    elapsed = record.get("alignment_seconds")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or not 0 <= elapsed <= WORKER_SECONDS:
        raise ValueError("invalid timing")
    aligned = record.get("alignment")
    if record["outcome"] == "alignment_timeout":
        if aligned is not None:
            raise ValueError("timeout cannot supply a completed alignment")
    elif (not isinstance(aligned, dict) or aligned.get("record_kind") != alignment.RECORD_KIND
          or aligned.get("perceptual_claim") is not False or aligned.get("public_verdict_enabled") is not False
          or aligned.get("sample_correction_applied") is not False):
        raise ValueError("completed alignment boundary differs")
    timings = record.get("stage_timing")
    if case == "identity_baseline":
        if timings is not None:
            raise ValueError("baseline cannot be instrumented")
    else:
        if not isinstance(timings, dict) or set(timings) != {"exclusive_seconds", "entered", "completed", "deadline_stack"}:
            raise ValueError("timing record differs")
        for field in ("exclusive_seconds", "entered", "completed"):
            if set(timings[field]) != set(STAGES):
                raise ValueError("timing stage inventory differs")
            for value in timings[field].values():
                if type(value) not in ((int, float) if field == "exclusive_seconds" else (int,)) or not math.isfinite(value) or value < 0:
                    raise ValueError("invalid stage timing/count")
        if any(timings["completed"][name] > timings["entered"][name] for name in STAGES):
            raise ValueError("completed stage without entry")
        stack = timings["deadline_stack"]
        if stack is not None and (not isinstance(stack, list) or any(name not in STAGES for name in stack)):
            raise ValueError("unknown deadline stage")
        if (record["outcome"] == "completed") != (stack is None):
            raise ValueError("deadline and completion disagree")
        if sum(timings["exclusive_seconds"].values()) > elapsed + 0.01:
            raise ValueError("exclusive timing exceeds elapsed time")


def aggregate(replays):
    if len(replays) != 2 or any([row["case"] for row in replay] != list(CASES) for replay in replays):
        raise ValueError("complete ordered two-round inventory required")
    for rows in replays:
        for row in rows:
            if row["outcome"] in ("completed", "alignment_timeout"):
                validate_case(row, row["case"])
            elif (row["outcome"] not in ("worker_timeout", "worker_failed_or_output_bound", "invalid_worker_record", "not_run_resource_stop")
                  or set(row) != {"case", "outcome", "alignment"} or row["alignment"] is not None):
                raise ValueError("invalid incomplete case record")
    repeatability = []
    for left, right in zip(*replays, strict=True):
        both = left["outcome"] == right["outcome"] == "completed"
        repeatability.append({"case": left["case"], "outcome_equal": left["outcome"] == right["outcome"],
                              "completed_alignment_bytes_equal": canonical(left["alignment"]) == canonical(right["alignment"]) if both else None})
    cross_mode = [canonical(rows[0]["alignment"]) == canonical(rows[1]["alignment"])
                  if rows[0]["outcome"] == rows[1]["outcome"] == "completed" else None for rows in replays]
    baseline_completed = all(rows[0]["outcome"] == "completed" and rows[0]["alignment_seconds"] <= ALIGNMENT_SECONDS for rows in replays)
    return {"schema_version": 1, "plan_id": PLAN_ID, "state": "synthetic_runtime_observation_complete",
            "planned_case_slots": 8, "replays": replays, "repeatability": repeatability,
            "baseline_completed_within_alignment_budget_both_rounds": baseline_completed,
            "full_rate_pipeline_qualified": False, "baseline_instrumented_completed_alignment_bytes_equal": cross_mode,
            "timing_byte_identity_required": False, "real_audio_accessed": False, "codec_executed": False,
            "perceptual_support": False, "public_verdict_enabled": False, "objective_complete": False}


def write_new(file, value):
    payload = canonical(value)
    if len(payload) > MAX_JSON:
        raise ValueError("report output bound exceeded")
    with file.open("xb") as stream:
        os.chmod(file, 0o600)
        stream.write(payload)


def execute(parent):
    plan = load_plan()
    plan_sha256 = binding.sha_file(PLAN)
    if not sys.flags.isolated:
        raise ValueError("isolated Python required")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise ValueError("clean locally committed checkpoint required")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    parent = parent.resolve(strict=True)
    if not parent.is_dir() or parent == ROOT or ROOT in parent.parents:
        raise ValueError("fresh output parent outside the repository required")
    reserve()
    native_preflight(plan)
    run_root = Path(tempfile.mkdtemp(prefix="alignment-native-", dir=parent))
    kernel_dir = run_root / "kernel"
    kernel_dir.mkdir(mode=0o700)
    kernel_path, kernel_provenance = native.build(kernel_dir)
    native.Kernel(kernel_path, kernel_provenance["binary_sha256"])
    write_new(run_root / "execution.json", {"head": head, "plan_sha256": plan_sha256,
                                           "externally_preregistered": False, "synthetic_only": True,
                                           "kernel": kernel_provenance})
    replays = []
    for index in range(2):
        if binding.sha_file(PLAN) != plan_sha256:
            raise ValueError("plan changed during qualification")
        load_plan()
        native_preflight(plan)
        rows = []
        stopped = False
        for case in CASES:
            try:
                reserve()
            except ValueError:
                stopped = True
            row = {"case": case, "outcome": "not_run_resource_stop", "alignment": None} if stopped else run_worker(case, kernel_path, kernel_provenance["binary_sha256"])
            rows.append(row)
            print(json.dumps({"round": index + 1, "case": case, "outcome": row["outcome"]}), file=sys.stderr, flush=True)
        write_new(run_root / f"round-{index + 1}.json", rows)
        replays.append(rows)
    if binding.sha_file(PLAN) != plan_sha256:
        raise ValueError("plan changed during qualification")
    load_plan()
    native_preflight(plan)
    report = aggregate(replays)
    if native.sha(kernel_path) != kernel_provenance["binary_sha256"]:
        raise ValueError("native binary changed during qualification")
    report.update({"kernel": kernel_provenance, "execution_head": head, "plan_sha256": plan_sha256, "native_binding_edge_checks_passed": True})
    write_new(run_root / "result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-plan", action="store_true")
    mode.add_argument("--execute-synthetic", action="store_true")
    mode.add_argument("--worker-case", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--output-parent", type=Path)
    parser.add_argument("--kernel", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--kernel-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if bool(args.worker_case) != bool(args.kernel and args.kernel_sha256):
        parser.error("native kernel binding required only for a worker")
    if (args.kernel or args.kernel_sha256) and not args.worker_case:
        parser.error("kernel arguments require worker mode")
    if args.execute_synthetic:
        if args.output_parent is None:
            parser.error("--output-parent required")
        report = execute(args.output_parent)
    elif args.output_parent is not None:
        parser.error("output parent requires synthetic execution")
    elif args.worker_case:
        load_plan()
        reserve()
        alignment.NATIVE_BACKEND = native.Kernel(args.kernel, args.kernel_sha256)
        report = measure(args.worker_case)
    else:
        load_plan()
        report = {"plan_id": PLAN_ID, "full_size_execution_performed": False}
    sys.stdout.buffer.write(canonical(report))


if __name__ == "__main__":
    main()
