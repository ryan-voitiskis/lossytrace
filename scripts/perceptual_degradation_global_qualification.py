"""Frozen synthetic-only global-search equivalence and workload qualification.

No waveform input, codec, playback or metric route. Full-size execution is
explicit and locally preregistered; tests use small arrays or mocked workers.
"""
from __future__ import annotations

import argparse
from array import array
from collections import Counter
from contextlib import contextmanager
import hashlib
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
import perceptual_degradation_alignment_v4 as predecessor
import perceptual_degradation_alignment_v5 as alignment
import perceptual_degradation_correlation_global as native
import perceptual_degradation_alignment_native_qualification as prior_qualification

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/alignment-global-workload-plan-20260908.json"
PLAN_ID = "alignment-global-workload-20260908-001"
FRAMES, RATE, DEADLINE, WORKER_DEADLINE, MARGIN = 576008, 48000, 180, 210, 120
FAMILIES = ("quantized", "dense_float", "mixed_scale", "sparse_bursts")
CASES = tuple(f"{family}:{mode}" for family in FAMILIES for mode in ("global_pair", "full_native"))
MAX_JSON = 4 * 1024**2
CLAIMS = {key: False for key in ("real_audio_accessed", "codec_executed", "capture_authorized",
    "playback_authorized", "metric_execution_authorized", "perceptual_support", "source_trait_assignment",
    "human_calibrated", "training_authorized", "full_rate_pipeline_qualified", "public_verdict_enabled", "objective_complete")}
BINDINGS = {
    "standing_authority": "benchmarks/perceptual-degradation-v1/digital-development-standing-authorization-20260908.json",
    "canary_negative": "research/toolchains/evidence/perceptual-degradation-digital-canary-20260908-001.json",
    "baseline_canary_plan": "benchmarks/perceptual-degradation-v1/digital-canary-proposal-20260908.json",
    "alignment_v1": "scripts/perceptual_degradation_alignment.py",
    "alignment_v2": "scripts/perceptual_degradation_alignment_v2.py",
    "alignment_v3": "scripts/perceptual_degradation_alignment_v3.py",
    "alignment_v4": "scripts/perceptual_degradation_alignment_v4.py",
    "alignment_v5": "scripts/perceptual_degradation_alignment_v5.py",
    "local_bridge": "scripts/perceptual_degradation_correlation_native.py",
    "local_source": "scripts/perceptual_degradation_correlation_native.c",
    "native_license": "research/licenses/alignment-kernel-PSF-LICENSE.txt",
    "global_bridge": "scripts/perceptual_degradation_correlation_global.py",
    "global_source": "scripts/perceptual_degradation_correlation_global.c",
    "native_tools": "research/toolchains/evidence/perceptual-degradation-digital-native-tools-20260908-001.json",
    "tool_binding": "scripts/perceptual_degradation_digital_tools.py",
    "old_qualification": "scripts/perceptual_degradation_alignment_native_qualification.py",
    "old_runtime": "scripts/perceptual_degradation_alignment_runtime.py",
    "equivalence_tests": "scripts/tests/test_perceptual_degradation_alignment_v5.py",
    "runner": "scripts/perceptual_degradation_global_qualification.py",
    "tests": "scripts/tests/test_perceptual_degradation_global_qualification.py",
}


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_plan():
    plan = json.loads(PLAN.read_bytes())
    if (plan["plan_id"] != PLAN_ID or plan["cases"] != list(CASES)
            or plan["geometry"] != {"frames": FRAMES, "sample_rate_hz": RATE, "channels": 2}
            or plan["limits"] != {"case_seconds": DEADLINE, "worker_seconds": WORKER_DEADLINE,
                                  "margin_gate_seconds": MARGIN, "rounds": 2, "workers": 1,
                                  "minimum_output_free_gib": 15, "minimum_workspace_free_gib": 15}):
        raise ValueError("workload protocol differs")
    if set(plan["bindings"]) != set(BINDINGS):
        raise ValueError("binding inventory differs")
    for name, relative in BINDINGS.items():
        if plan["bindings"][name] != {"path": relative, "sha256": sha((ROOT / relative).read_bytes())}:
            raise ValueError("frozen implementation changed")
    auth = json.loads((ROOT / plan["bindings"]["standing_authority"]["path"]).read_bytes())
    if auth["additional_synthetic_qualification_batches_authorized"] is not True:
        raise ValueError("synthetic development authority unavailable")
    if set(plan["claim_boundary"]) != set(CLAIMS) or any(value is not False for value in plan["claim_boundary"].values()):
        raise ValueError("claim boundary differs")
    return plan


def fixture(family, frames=FRAMES):
    if family not in FAMILIES or type(frames) is not int or not 0 < frames <= FRAMES:
        raise ValueError("undeclared construction")
    if family == "quantized":
        return prior_qualification.fixture("identity_baseline", frames)[0]
    left, right, state = [], [], 0x56842139D30A0F71
    for index in range(frames):
        values = []
        for channel in range(2):
            state = (6364136223846793005 * state + 1442695040888963407) % 2**64
            value = ((state >> 11) / 2**53 - .5) * .25
            value *= (1 + (index // 137 + channel) % 5) / 5
            if family == "mixed_scale":
                value = math.ldexp(value, -((index + channel * 7) % 41))
            elif family == "sparse_bursts" and (index // 2400) % 5 != 0:
                value = 0.0
            values.append(value)
        left.append(values[0])
        right.append(values[1])
    return tuple(left), tuple(right)


def input_hash(channels):
    digest = hashlib.sha256()
    for channel in channels:
        values = array("d", channel)
        if sys.byteorder != "little":
            values.byteswap()
        digest.update(values.tobytes())
    return digest.hexdigest()


class TimedKernel(native.Kernel):
    def __init__(self, *args):
        super().__init__(*args)
        self.wall, self.cpu = Counter(), Counter()

    @contextmanager
    def stage(self, name):
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            yield
        finally:
            self.wall[name] += time.perf_counter() - wall
            self.cpu[name] += time.process_time() - cpu

    def global_results(self, *args):
        with self.stage("global_native"):
            return super().global_results(*args)

    def results(self, *args):
        with self.stage("local_native"):
            return super().results(*args)


def global_audit(kernel):
    audit = kernel.global_record()
    geometries = audit.pop("geometries")
    audit.update(geometry_sha256=sha(canonical(geometries)),
                 geometry_rows=len(geometries),
                 sampled_pair_evaluations=sum(row["sampled_frames"] * row["candidate_count"] for row in geometries))
    return audit


class Deadline(Exception):
    pass


def measure(case, binary, binary_sha, *, frames=FRAMES, rate=RATE, seconds=DEADLINE):
    if case not in CASES:
        raise ValueError("unknown case")
    family, mode = case.split(":")
    channels = fixture(family, frames)
    before = input_hash(channels)
    kernel = TimedKernel(binary, binary_sha)
    if alignment.NATIVE_BACKEND is not None or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("exclusive backend and timer required")
    previous = signal.getsignal(signal.SIGALRM)
    outcome, result = "completed", None
    component = {}
    def expired(signum, frame):
        raise Deadline()
    wall, cpu = time.perf_counter(), time.process_time()
    try:
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        alignment.NATIVE_BACKEND = kernel
        if mode == "full_native":
            result = alignment.align_channels(reference_channels=channels, test_channels=channels,
                reference_channel_map=["L", "R"], test_channel_map=["L", "R"], sample_rate_hz=rate,
                recipe_identity=PLAN_ID + ":" + family, minimum_active_seconds=4, maximum_delay_seconds=2)
        else:
            a = channels[0]
            block = max(1, round(rate / predecessor.legacy.ENVELOPE_RATE_HZ))
            envelope = predecessor._rms_envelope(a, block)
            maximum = math.ceil(2 * rate / block)
            with kernel.stage("coarse_python"):
                coarse = {lag: predecessor.correlate(envelope, envelope, lag, centered=True)
                          for lag in range(-maximum, maximum+1)}
            peaks = predecessor.legacy._candidate_lags(predecessor.valid_scores(coarse, magnitude=False), count=8, exclusion=2)
            lags = sorted({lag for peak in peaks for lag in range(peak*block-block, peak*block+block+1)})
            component.update(coarse_candidates=len(coarse), selected_peaks=peaks,
                             global_candidates=len(lags), candidate_inventory_sha256=sha(canonical(lags)))
            with kernel.stage("global_python"):
                old_results = {lag: predecessor.correlate(a, a, lag) for lag in lags}
            old = {lag: value.record() for lag, value in old_results.items()}
            new = {lag: value.record() for lag, value in kernel.global_results(a, a, lags).items()}
            component.update(predecessor_sha256=sha(canonical(old)), successor_sha256=sha(canonical(new)),
                             all_candidate_records_byte_identical=canonical(old) == canonical(new))
    except Deadline:
        outcome, result = "case_timeout", None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        alignment.NATIVE_BACKEND = None
    elapsed, consumed = time.perf_counter() - wall, time.process_time() - cpu
    return {"case": case, "frames": frames, "sample_rate_hz": rate, "outcome": outcome,
            "wall_seconds": elapsed, "cpu_seconds": consumed,
            "stage_wall_seconds": dict(kernel.wall), "stage_cpu_seconds": dict(kernel.cpu),
            "other_wall_seconds": max(0, elapsed-sum(kernel.wall.values())),
            "other_cpu_seconds": max(0, consumed-sum(kernel.cpu.values())),
            "alignment": result, "component": component,
            "local_native": kernel.record(), "global_native": global_audit(kernel),
            "input_sha256": before, "inputs_unchanged": before == input_hash(channels),
            "perceptual_support": False}


def incomplete(case, reason):
    return {"case": case, "outcome": reason, "alignment": None}


def validate_case(row, case):
    if not isinstance(row, dict) or row.get("case") != case or case not in CASES:
        raise ValueError("case identity differs")
    if row["outcome"] in ("worker_timeout", "worker_failed", "invalid_worker_record", "not_run_resource_stop"):
        if set(row) != {"case", "outcome", "alignment"} or row["alignment"] is not None:
            raise ValueError("incomplete record differs")
        return
    expected = {"case", "frames", "sample_rate_hz", "outcome", "wall_seconds", "cpu_seconds",
                "stage_wall_seconds", "stage_cpu_seconds", "other_wall_seconds", "other_cpu_seconds",
                "alignment", "component", "local_native", "global_native", "input_sha256", "inputs_unchanged", "perceptual_support"}
    if (set(row) != expected or row["outcome"] not in ("completed", "case_timeout")
            or row["frames"] != FRAMES or row["sample_rate_hz"] != RATE
            or row["perceptual_support"] is not False or type(row["inputs_unchanged"]) is not bool):
        raise ValueError("measurement schema or geometry differs")
    if not isinstance(row["input_sha256"], str) or len(row["input_sha256"]) != 64:
        raise ValueError("construction binding differs")
    stages = {"global_native", "local_native", "global_python", "coarse_python"}
    for prefix in ("wall", "cpu"):
        values = row[f"stage_{prefix}_seconds"]
        if not isinstance(values, dict) or not set(values) <= stages:
            raise ValueError("timing stage differs")
        for value in [row[f"{prefix}_seconds"], row[f"other_{prefix}_seconds"], *values.values()]:
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid measured time")
        if sum(values.values()) > row[f"{prefix}_seconds"] + .01:
            raise ValueError("stage time exceeds whole observation")
    if row["wall_seconds"] > WORKER_DEADLINE:
        raise ValueError("worker time bound differs")
    for kind in ("local_native", "global_native"):
        audit = row[kind]
        for field in ("native_candidates", "fallback_candidates"):
            if type(audit[field]) is not int or audit[field] < 0:
                raise ValueError("invalid native inventory")
        for search in audit["searches"]:
            if any(type(value) is not int or value < 0 for value in search.values()) or search["search_count"] < 1:
                raise ValueError("invalid search geometry")
        if row["outcome"] == "completed" and audit["fallback_candidates"] == 0:
            short = audit.get("short_overlap_candidates", 0)
            if audit["native_candidates"] + short != sum(s["candidate_count"]*s["search_count"] for s in audit["searches"]):
                raise ValueError("completed native inventory differs")
    if row["outcome"] == "case_timeout":
        if row["alignment"] is not None:
            raise ValueError("timeout cannot expose completed alignment")
    elif case.endswith(":global_pair"):
        component = row["component"]
        fields = {"coarse_candidates", "selected_peaks", "global_candidates", "candidate_inventory_sha256",
                  "predecessor_sha256", "successor_sha256", "all_candidate_records_byte_identical"}
        if set(component) != fields or component["coarse_candidates"] != 801:
            raise ValueError("component inventory differs")
        peaks = component["selected_peaks"]
        if (not isinstance(peaks, list) or len(peaks) > 8 or any(type(p) is not int or abs(p) > 400 for p in peaks)
                or any(abs(a-b) <= 2 for i, a in enumerate(peaks) for b in peaks[i+1:])):
            raise ValueError("coarse peak inventory differs")
        lags = sorted({lag for peak in peaks for lag in range(peak*240-240, peak*240+241)})
        if component["global_candidates"] != len(lags) or component["candidate_inventory_sha256"] != sha(canonical(lags)):
            raise ValueError("fine candidate inventory differs")
        searches = [{"reference_frames": FRAMES, "test_frames": FRAMES, "candidate_count": len(lags), "search_count": 1}]
        geometries = Counter()
        for lag in lags:
            length = FRAMES-abs(lag)
            stride = max(1, length//16384)
            geometries[(length, stride, len(range(0, length, stride)))] += 1
        expected_geometry = [{"overlap_frames": key[0], "stride": key[1], "sampled_frames": key[2], "candidate_count": count}
                             for key, count in sorted(geometries.items())]
        g = row["global_native"]
        if (g["searches"] != searches or g["geometry_rows"] != len(geometries)
                or g["geometry_sha256"] != sha(canonical(expected_geometry))
                or g["sampled_pair_evaluations"] != sum(r["sampled_frames"]*r["candidate_count"] for r in expected_geometry)
                or row["local_native"] != {"native_candidates": 0, "fallback_candidates": 0, "searches": []}):
            raise ValueError("component native geometry differs")
        if (row["alignment"] is not None or type(component["all_candidate_records_byte_identical"]) is not bool
                or component["all_candidate_records_byte_identical"] is not (component["predecessor_sha256"] == component["successor_sha256"])):
            raise ValueError("component equality differs")
    else:
        aligned = row["alignment"]
        if (not isinstance(aligned, dict) or aligned["record_kind"] != alignment.RECORD_KIND
                or aligned["sample_correction_applied"] is not False
                or aligned["perceptual_claim"] is not False or aligned["public_verdict_enabled"] is not False):
            raise ValueError("alignment claim boundary differs")
        if sum(s["search_count"] for s in row["global_native"]["searches"]) != 2:
            raise ValueError("declared active constructions require both global searches")


def run_worker(case, binary, binary_sha):
    env = {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C", "TZ": "UTC",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
    try:
        result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "worker",
                                 "--case", case, "--binary", str(binary), "--binary-sha", binary_sha],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=WORKER_DEADLINE,
                                env=env, check=False)
    except subprocess.TimeoutExpired:
        return incomplete(case, "worker_timeout")
    if result.returncode or len(result.stdout) > MAX_JSON or len(result.stderr) > MAX_JSON:
        return incomplete(case, "worker_failed")
    try:
        row = json.loads(result.stdout)
        validate_case(row, case)
        return row
    except (ValueError, KeyError, TypeError, OverflowError):
        return incomplete(case, "invalid_worker_record")


def deterministic(row):
    excluded = {"wall_seconds", "cpu_seconds", "stage_wall_seconds", "stage_cpu_seconds",
                "other_wall_seconds", "other_cpu_seconds"}
    return {key: value for key, value in row.items() if key not in excluded}


def aggregate(rounds, edges):
    if len(rounds) != 2 or any([row["case"] for row in rows] != list(CASES) for rows in rounds):
        raise ValueError("all sixteen fixed slots required")
    if len(edges) != 4 or any(value not in ("passed", "failed", "not_attempted_after_stop") for value in edges):
        raise ValueError("four edge checks required")
    rows = [row for items in rounds for row in items]
    for row in rows:
        validate_case(row, row["case"])
    repeat = [{"case": left["case"], "outcome_equal": left["outcome"] == right["outcome"],
               "completed_evidence_byte_identical": canonical(deterministic(left)) == canonical(deterministic(right))
               if left["outcome"] == right["outcome"] == "completed" else None}
              for left, right in zip(*rounds, strict=True)]
    full = [row for row in rows if row["case"].endswith(":full_native")]
    components = [row for row in rows if row["case"].endswith(":global_pair")]
    complete = all(row["outcome"] == "completed" for row in rows)
    equality = all(row["outcome"] == "completed" and row["component"]["all_candidate_records_byte_identical"]
                   and row["component"]["global_candidates"] == 3848 for row in components)
    margin = all(row["outcome"] == "completed" and row["wall_seconds"] <= MARGIN for row in full)
    repeated = all(item["completed_evidence_byte_identical"] is True for item in repeat)
    no_fallback = complete and all(row[kind]["fallback_candidates"] == 0 for row in rows for kind in ("local_native", "global_native"))
    preserved = complete and all(row["inputs_unchanged"] for row in rows)
    passed = complete and equality and margin and repeated and no_fallback and preserved and all(e == "passed" for e in edges)
    return {"schema_version": 1, "plan_id": PLAN_ID, "planned_slots": 16,
            "state": "synthetic_workload_margin_passed" if passed else "synthetic_workload_negative_or_incomplete",
            "all_slots_completed": complete, "global_candidate_equivalence_passed": equality,
            "all_full_alignments_within_120_seconds": margin, "completed_evidence_repeated": repeated,
            "no_native_fallback": no_fallback, "all_inputs_preserved": preserved,
            "replay_edges": edges, "repeatability": repeat, "rounds": rounds,
            "real_audio_accessed": False, "codec_executed": False, "perceptual_support": False,
            "full_rate_pipeline_qualified": False, "public_verdict_enabled": False, "objective_complete": False}


def write_new(path, value):
    payload = canonical(value)
    if len(payload) > MAX_JSON:
        raise ValueError("bounded JSON record exceeded")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)


def reserve(parent):
    if any(shutil.disk_usage(path).free < 15 * 1024**3 for path in (ROOT, parent)):
        raise ValueError("15 GiB workspace/output reserve unavailable")


def check_tools(plan):
    prior_qualification.native_preflight({"bindings": {"native_tools": plan["bindings"]["native_tools"]}})


def execute(parent):
    if not sys.flags.isolated:
        raise ValueError("isolated Python required")
    plan = load_plan()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise ValueError("clean pre-observation local commit required")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    parent = parent.resolve(strict=True)
    if not parent.is_dir() or parent == ROOT or ROOT in parent.parents:
        raise ValueError("outside-repository output parent required")
    reserve(parent)
    check_tools(plan)
    write_new(parent / (PLAN_ID + ".launch.json"), {"head": head, "plan_sha256": sha(PLAN.read_bytes()), "invocation": 1})
    root = Path(tempfile.mkdtemp(prefix="alignment-global-", dir=parent))
    kernel_dir = root / "kernel"
    kernel_dir.mkdir(mode=0o700)
    binary, provenance = native.build(kernel_dir)
    if {k: v for k, v in provenance.items() if k != "binary_sha256"} != plan["native_build"]:
        raise ValueError("native compiler/environment differs")
    execution = {"head": head, "plan_sha256": sha(PLAN.read_bytes()), "kernel": provenance,
                 "locally_preregistered": True, "externally_preregistered": False, "synthetic_only": True}
    write_new(root / "execution.json", execution)
    rounds, edges, stopped = [], [], False
    def edge():
        nonlocal stopped
        if stopped:
            return "not_attempted_after_stop"
        try:
            load_plan()
            check_tools(plan)
            reserve(root)
            if sha(PLAN.read_bytes()) != execution["plan_sha256"] or native.sha(binary) != provenance["binary_sha256"]:
                raise ValueError("bound artifact changed")
            native.Kernel(binary, provenance["binary_sha256"])
            return "passed"
        except (ValueError, OSError, KeyError, subprocess.SubprocessError):
            stopped = True
            return "failed"
    for index in range(2):
        edges.append(edge())
        rows = []
        for case in CASES:
            try:
                reserve(root)
            except ValueError:
                stopped = True
            row = incomplete(case, "not_run_resource_stop") if stopped else run_worker(case, binary, provenance["binary_sha256"])
            rows.append(row)
            print(json.dumps({"round": index+1, "case": case, "outcome": row["outcome"]}), file=sys.stderr, flush=True)
        edges.append(edge())
        write_new(root / f"round-{index+1}.json", rows)
        rounds.append(rows)
    report = aggregate(rounds, edges)
    write_new(root / "result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    run = commands.add_parser("run")
    run.add_argument("--output-parent", type=Path, required=True)
    worker = commands.add_parser("worker")
    worker.add_argument("--case", choices=CASES, required=True)
    worker.add_argument("--binary", type=Path, required=True)
    worker.add_argument("--binary-sha", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        load_plan()
        result = {"plan_id": PLAN_ID, "synthetic_execution_performed": False}
    elif args.command == "worker":
        if not sys.flags.isolated:
            raise ValueError("isolated worker required")
        load_plan()
        result = measure(args.case, args.binary, args.binary_sha)
    else:
        result = execute(args.output_parent)
    print(canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
