"""Replay the November 23 offline pilot from saved inspector reports."""
import argparse
import hashlib
import json
from collections import Counter
from itertools import product
from pathlib import Path
from statistics import median

from music_verdict_comparator import fit_logistic


CONDITIONS = ("identity", "gain", "dither16", "resample", "lowpass16k", "eq_dynamics")
CODECS = ("mp3-128", "mp3-192", "mp3-320", "aac-128", "aac-192", "aac-256")
STATES = ("baseline", *CODECS)
INPUT_HASH = "f169579ede1e8dfbda9ff1fd852dce78fe97de60889b6ac557bd299a6df5ab4c"


def load_reports(root):
    paths = sorted([*root.glob("library-*.json"), *root.glob("synthetic-*.json")])
    digest = hashlib.sha256()
    features = {}
    for path in paths:
        data = path.read_bytes()
        digest.update(path.name.encode() + b"\0" + hashlib.sha256(data).digest())
        row = json.loads(data)
        key = row["source_id"], row["case"], row["condition"]
        if path.stem != "-".join(key):
            raise ValueError(f"mismatched case identity in {path.name}")
        features[key] = row["report"]["compression_trace"]
    if len(features) != 2016 or digest.hexdigest() != INPUT_HASH:
        raise ValueError("reports differ from the prospective input set")
    return features


def synthetic_keys(families):
    return [(f"synthetic-{i:02d}", state, condition)
            for i, state, condition in product(range(24), STATES, CONDITIONS)
            if i // 6 in families]


def fit(features, families):
    keys = synthetic_keys(families)
    return fit_logistic([features[key] for key in keys],
                        [int(state != "baseline") for _, state, _ in keys],
                        [str(int(source[-2:]) // 6) for source, _, _ in keys],
                        partition="train")


def evaluate(features):
    families = set(range(4))
    synthetic = {}
    for family in sorted(families):
        model = fit(features, families - {family})
        keys = synthetic_keys({family})
        scores = model.logits([features[key] for key in keys])
        counts = Counter((state != "baseline", score >= 0)
                         for (_, state, _), score in zip(keys, scores, strict=True))
        sensitivity = counts[True, True] / 216
        specificity = counts[False, False] / 36
        synthetic[family] = dict(true_positive=counts[True, True], positives=216,
                                 true_negative=counts[False, False], negatives=36,
                                 sensitivity=sensitivity, specificity=specificity,
                                 balanced_accuracy=(sensitivity + specificity) / 2)

    model = fit(features, families)
    library = {}
    for condition in CONDITIONS:
        comparisons = {}
        for codec in CODECS:
            def scores(state):
                return model.logits([features[f"library-{i:02d}", state, condition]
                                     for i in range(24)])
            delta = scores(codec) - scores("baseline")
            comparisons[codec] = dict(higher=int((delta > 0).sum()), equal=int((delta == 0).sum()),
                                      lower=int((delta < 0).sum()), median_logit_delta=median(delta))
        library[condition] = comparisons
    return dict(report_digest=INPUT_HASH, synthetic_family_holdouts=synthetic, library_pairs=library)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path)
    parser.add_argument("output", type=Path, help="new aggregate JSON file")
    args = parser.parse_args()
    result = evaluate(load_reports(args.reports))
    with args.output.open("x") as out:
        out.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
