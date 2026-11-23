"""Replay the frozen measurement comparator on the previously examined synthetic files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import time
import wave

import numpy as np

import music_library_pilot_convert as codec
import music_library_pilot_transfer as transfer
from music_single_file_experiment import RECIPES, STATES, summarize, thresholds
from music_verdict_comparator import checkpoint_bytes, load_checkpoint
from music_verdict_comparator_runtime import BINARY, inspect
from music_verdict_runtime_probe import EXTERNAL, save

SOURCE = EXTERNAL.parent / "single-file-20261123-001"
MANIFESTS = "42a5dafb9feb54d6f1352357dbb2bdde8875326069a20fba3a5a1d3c1a9a4a59"
PLAN = Path("research/music-library-pilot-v1/single-file-comparator-plan-20261124.md")
PILOT = PLAN.parent / "single-file-results-20261123.json"


def inputs():
    manifests = {}
    digest = hashlib.sha256()
    for path in sorted(SOURCE.glob("*/*/inputs.json")):
        data = path.read_bytes()
        digest.update(str(path.relative_to(SOURCE)).encode() + b"\0" + hashlib.sha256(data).digest())
        item = json.loads(data)
        if [row["state"] for row in item["records"]] != list(STATES):
            raise ValueError("incomplete source manifest")
        manifests[path.parent] = item
    if digest.hexdigest() != MANIFESTS or len(manifests) != 96:
        raise ValueError("unrecognized source archive")
    return manifests


def measure(folder, manifest, output):
    rate = manifest["rate"]
    evidence = []
    with tempfile.TemporaryDirectory(dir=output) as temp:
        path = Path(temp) / "input.wav"
        for item in manifest["records"]:
            source = folder / item["file"]
            if codec.sha(source) != item["file_hash"]:
                raise ValueError("source file changed")
            raw, padding = codec.trim(codec.decode(source, 16), 16, rate * 32)
            if hashlib.sha256(raw).hexdigest() != item["pcm_hash"] or padding != item["trimmed_frames"]:
                raise ValueError("decoded PCM changed")
            with wave.open(str(path), "wb") as wav:
                wav.setparams((2, 2, rate, 0, "NONE", "not compressed"))
                wav.writeframes(raw)
            binding = codec.sha(path)
            start = time.perf_counter()
            report = inspect(path, binding, rate, 2, 16, 32)
            evidence.append(dict(recipe=folder.parent.name, cell=int(folder.name), state=item["state"],
                                 pcm_sha256=item["pcm_hash"], wav_sha256=binding,
                                 extract_seconds=time.perf_counter() - start,
                                 analyzed_frames=report["analyzed_sample_count"],
                                 features=report["compression_trace"]))
    return evidence


def score(recipes, model, manifests, output):
    folders = [SOURCE / recipe / str(i) for recipe in recipes for i in range(16)]
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(measure, folder, manifests[folder], output) for folder in folders]
        for future in futures:
            for row in future.result():
                row["comparator"] = float(model.logits([row["features"]])[0])
                rows.append(row)
    return rows


def run(output):
    if not EXTERNAL.parents[1].is_mount() or output.resolve().parent != EXTERNAL:
        raise ValueError("use a fresh directory on schwarz")
    manifests = inputs()
    bound_binary = json.loads((PLAN.parent / "measurement-plan-20261010.json").read_bytes())["bound_files"][0]
    if codec.sha(BINARY) != bound_binary["sha256"]:
        raise ValueError("inspector differs from training measurement build")
    output.mkdir()
    reports = transfer.load_reports(codec.ROOT / "library-nuisance-measurements-20261010-001")
    raw = checkpoint_bytes(transfer.fit(reports, set(range(4))))
    checkpoint = output / "checkpoint.json"
    checkpoint.write_bytes(raw)
    model = load_checkpoint(checkpoint.read_bytes(), hashlib.sha256(raw).hexdigest())
    calibration = score(RECIPES[:2], model, manifests, output)
    save(output / "calibration.json", calibration)
    limits = thresholds(calibration, "comparator")
    save(output / "thresholds.json", limits)
    evaluation = score(RECIPES[2:], model, manifests, output)
    save(output / "evaluation.json", evaluation)
    if len({row["pcm_sha256"] for row in calibration + evaluation}) != 672:
        raise ValueError("duplicate or missing decoded PCM")
    overall = summarize(evaluation, "comparator", limits)
    by_source = {(r["recipe"], r["cell"]):r["comparator"] for r in evaluation if r["state"] == "baseline"}
    positive = [r for r in evaluation if r["state"] != "baseline"]
    differences = np.subtract.outer([r["comparator"] for r in positive], list(by_source.values()))
    baseline = json.loads(PILOT.read_bytes())["overall"]["baseline"]
    win = (overall["clean_false_alerts"] < baseline["clean_false_alerts"]
           and overall["detection"] >= max(.5, baseline["detection"] - .05)
           and overall["balanced_coverage"] >= max(.6, baseline["balanced_coverage"] - .05))
    save(output / "summary.json", dict(
        plan_sha256=codec.sha(PLAN), runner_sha256=codec.sha(Path(__file__)), binary_sha256=codec.sha(BINARY),
        manifest_set_sha256=MANIFESTS, training_report_set_sha256=transfer.INPUT_HASH,
        checkpoint_sha256=codec.sha(checkpoint), thresholds_sha256=codec.sha(output / "thresholds.json"),
        calibration_count=len(calibration), evaluation_count=len(evaluation), thresholds=limits, overall=overall,
        by_recipe={recipe:summarize([r for r in evaluation if r["recipe"] == recipe], "comparator", limits)
                   for recipe in RECIPES[2:]},
        higher_than_matched_control=sum(r["comparator"] > by_source[r["recipe"], r["cell"]] for r in positive),
        roc_auc=float(np.mean((differences > 0) + 0.5 * (differences == 0))), met_pilot_criteria=win))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
