"""Measure the feature-v0 comparator on the generated inputs of the prior CNN timing run."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import time

import numpy as np

from music_verdict_calibration import CASES
from music_verdict_comparator import checkpoint_bytes, fit_logistic, load_checkpoint
import music_verdict_runtime_probe as cnn

BINARY = Path(__file__).resolve().parents[1] / "target/release/lossytrace"
TRAIN = cnn.EXTERNAL / "music-verdict-streaming-smoke-20261123-001/train"
TRAIN_HASH = "d340008397f29f2fb3083e4cb588b802b42c7e12aa4fdfd853573b2f35da9b63"
TIMING = cnn.EXTERNAL / "music-verdict-synthetic-runtime-20261123-001"


def inspect(path, expected_sha, rate, channels, bits, duration):
    report = json.loads(subprocess.check_output(
        [BINARY, "analyze", path, "--max-seconds", "120"], timeout=120))
    facts = report["source_facts"]
    seconds = min(120, duration)
    if (report["schema_version"] != 1 or report["public_verdict_enabled"] is not False
            or report["state"] != "experimental_measurements_only" or report["input_sha256"] != expected_sha
            or (facts["sample_rate_hz"], facts["channel_count"], facts["declared_bits_per_sample"]) !=
            (rate, channels, bits) or report["truncated_by_limit"] != (duration > 120)
            or report["analyzed_sample_count"] != seconds * rate or report["analyzed_duration_seconds"] != seconds):
        raise ValueError("inspector identity, format or analysis interval mismatch")
    return report


def train(output):
    path = TRAIN / "construction.json"
    if cnn.digest(path) != TRAIN_HASH:
        raise ValueError("unrecognized synthetic training manifest")
    cases = json.loads(path.read_bytes())["cases"]
    if [(r["state"], r["condition"]) for r in cases] != list(CASES):
        raise ValueError("incomplete synthetic training matrix")
    records, labels, groups = [], [], []
    for case in cases:
        audio = TRAIN / case["path"]
        report = inspect(audio, case["sha256"], case["rate"], case["channels"], case["bits"], 30)
        records.append(report["compression_trace"])
        labels.append(int(case["state"] != "baseline"))
        groups.append(case["group"])
    model = fit_logistic(records, labels, groups, partition="train")
    raw = checkpoint_bytes(model)
    key = hashlib.sha256(raw).hexdigest()
    restored = load_checkpoint(raw, key)
    if not np.array_equal(restored.logits(records), model.logits(records)):
        raise ValueError("restored training scores differ")
    with (output / "checkpoint.json").open("xb") as stream:
        stream.write(raw)
    cnn.save(output / "training-measurements.json", [
        dict(state=s, condition=c, features=r) for (s, c), r in zip(CASES, records)])
    return key


def worker(folder, fixture, key):
    model = load_checkpoint((folder / "checkpoint.json").read_bytes(), key)
    path = folder / fixture["file"]
    rate, channels, bits = (int(x) for x in path.stem.split("-"))
    for _ in range(1 + cnn.WARM_REPEATS):
        start = time.perf_counter()
        report = inspect(path, fixture["file_sha256"], rate, channels, bits, 300)
        after_extract = time.perf_counter()
        score = float(model.logits([report["compression_trace"]])[0])
        elapsed = time.perf_counter() - start
        print(json.dumps(dict(seconds=elapsed, inspect_seconds=after_extract-start, file_logit=score,
                              report=report, parent_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                              child_peak_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
                         allow_nan=False), flush=True)


def run(folder):
    if (platform.system() != "Darwin" or not cnn.EXTERNAL.parents[1].is_mount()
            or folder.resolve().parent != cnn.EXTERNAL or shutil.disk_usage(cnn.EXTERNAL).free < 2 * 1024**3):
        raise ValueError("requires a fresh output directory on mounted schwarz with fixture headroom")
    folder.mkdir()
    binary_sha = cnn.digest(BINARY)
    key = train(folder)
    results = []
    for rate, channels, bits in cnn.CASES:
        pair = cnn.make_pair(folder, rate, channels, bits)
        previous = None
        for fixture in pair:
            filename = fixture["file"]
            if fixture != json.loads((TIMING / (filename + ".json")).read_bytes())["fixture"]:
                raise ValueError("regenerated input differs from prior CNN fixture")
            cmd = [sys.executable, "-B", __file__, str(folder), "--worker", json.dumps(fixture), key]
            start = time.perf_counter()
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as child:
                first = child.stdout.readline()
                cold = time.perf_counter() - start
                lines = [first, *child.stdout]
                if child.wait() or not first or len(lines) != 1 + cnn.WARM_REPEATS:
                    raise RuntimeError("fixture worker failed")
            runs = [json.loads(s) for s in lines]
            first_run = runs[0]
            if any(r["report"] != first_run["report"] or r["file_logit"] != first_run["file_logit"] for r in runs):
                raise ValueError("repeatability failure")
            signature = first_run["report"]["compression_trace"], first_run["file_logit"]
            if previous is not None and signature != previous:
                raise ValueError("equal-PCM wrapper disagreement")
            previous = signature
            if cnn.digest(folder / filename) != fixture["file_sha256"]:
                raise ValueError("changed input")
            row = dict(fixture=fixture, cold_seconds=cold, runs=runs)
            cnn.save(folder / (filename + ".json"), row)
            results.append(row)
    if cnn.digest(BINARY) != binary_sha:
        raise ValueError("inspector changed during run")
    warm = [r for row in results for r in row["runs"][1:]]
    times = sorted(r["seconds"] for r in warm)
    report = dict(scope="generated signals only; one synthetic training group; no calibrated verdict",
                  training_cases=len(CASES), wrappers=len(results), warm_runs=len(warm),
                  python=platform.python_version(), numpy=np.__version__, platform=platform.platform(),
                  machine=subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
                  binary_sha256=binary_sha, checkpoint_sha256=key, train_manifest_sha256=TRAIN_HASH,
                  warm_median_s=statistics.median(times), warm_p95_s=times[math.ceil(.95*len(times))-1],
                  largest_cold_to_first_json_s=max(r["cold_seconds"] for r in results),
                  warm_median_by_wrapper_s={ext: statistics.median(r["seconds"] for row in results
                      if row["fixture"]["file"].endswith("." + ext) for r in row["runs"][1:]) for ext in ("flac", "wav")},
                  warm_median_inspector_s=statistics.median(r["inspect_seconds"] for r in warm),
                  warm_median_logistic_s=statistics.median(r["seconds"]-r["inspect_seconds"] for r in warm),
                  peak_parent_rss_bytes=max(r["parent_peak_bytes"] for row in results for r in row["runs"]),
                  peak_inspector_rss_bytes=max(r["child_peak_bytes"] for row in results for r in row["runs"]),
                  code_sha256={n: cnn.digest(Path(__file__).with_name(n)) for n in
                               ("music_verdict_comparator_runtime.py", "music_verdict_comparator.py",
                                "music_verdict_runtime_probe.py")})
    cnn.save(folder / "summary.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.output, json.loads(args.worker[0]), args.worker[1])
    else:
        run(args.output)
