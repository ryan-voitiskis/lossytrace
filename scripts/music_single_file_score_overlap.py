"""Describe ordering in the consumed procedural pilot, without fitting or returning cutoffs."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

RECIPES = ("pulse_lead", "mallet", "vibrato_strings", "noise_resonator")
STATES = ("baseline", "mp3-128", "mp3-192", "mp3-320", "aac-128", "aac-192", "aac-256")


def read(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    keys = Counter((r["recipe"], r["cell"], r["state"]) for r in data)
    if keys != Counter((r, i, s) for r in RECIPES for i in range(16) for s in STATES):
        raise ValueError("unexpected procedural pilot rows")
    return data, hashlib.sha256(raw).hexdigest()


def overlap(data, model):
    controls = [r[model] for r in data if r["state"] == "baseline"]
    encodes = sorted((r[model] for r in data if r["state"] != "baseline"), reverse=True)
    if not all(math.isfinite(x) for x in controls + encodes):
        raise ValueError("nonfinite score")
    half = math.ceil(len(encodes) / 2)
    # Flagging the half-th encode also flags all controls ranked above or tied with it.
    alerts = sum(x >= encodes[half-1] for x in controls)
    return dict(controls=len(controls), encodes=len(encodes),
                encodes_strictly_above_all_controls=sum(x > max(controls) for x in encodes),
                minimum_control_flags_for_half_detection=alerts)


def run(root):
    cnns, cnn_sha = read(root / "single-file-20261123-001/evaluation-scores.json")
    comparator, cmp_sha = read(root / "validation/single-file-comparator-20261124-002/evaluation.json")
    return dict(cnn_scores_sha256=cnn_sha, measurement_scores_sha256=cmp_sha,
                models={key: overlap(rows, key) for rows, key in (
                    (cnns, "baseline"), (cnns, "ranking"), (comparator, "comparator"))})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(json.dumps(run(parser.parse_args().archive), indent=2))
