"""Offline comparison on synthetic FLACs and their existing identity reports."""
import argparse
import hashlib
import json
import subprocess
from itertools import product
from pathlib import Path
from statistics import mean, median

import numpy as np
import torch
from torch.nn import functional as F

from music_verdict_candidate import SEED, build_candidate, frontend
from music_verdict_comparator import fit_logistic


STATES = ("baseline", "mp3-128", "mp3-192", "mp3-320", "aac-128", "aac-192", "aac-256")
STARTS = (0, 23, 46, 69, 92, 116)


def load_inputs(variants, reports, origin="synthetic"):
    images, measures = {}, {}
    for i in range(24):
        source = f"{origin}-{i:02d}"
        for c, state in enumerate(STATES):
            row = json.loads((reports / f"{source}-{state}-identity.json").read_bytes())
            expected_origin = "controlled_synthesis_no_lossy_stage" if origin == "synthetic" else "unknown_history"
            if (row["source_id"], row["case"], row["condition"], row["origin"]) != (
                    source, state, "identity", expected_origin):
                raise ValueError("case identity mismatch")
            if origin == "synthetic" and row["component"] != f"synthetic-family-{i//6}":
                raise ValueError("synthetic family mismatch")
            report = row["report"]
            rate = report["source_facts"]["sample_rate_hz"]
            bits = report["source_facts"]["declared_bits_per_sample"]
            if bits not in (16, 24) or report["source_facts"]["channel_count"] != 2:
                raise ValueError("unsupported input")
            raw = subprocess.check_output(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-nostdin",
                   "-i", str(variants / source / f"{state}.flac"), "-f", f"s{bits}le", "-"])
            if len(raw) != 120 * rate * 2 * (bits//8) or hashlib.sha256(raw).hexdigest() != row["pcm_sha256"]:
                raise ValueError(f"PCM differs from audited report: {source}/{state}")
            if bits == 16:
                pcm = np.frombuffer(raw, dtype="<i2").reshape(-1, 2)
            else:
                octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
                values = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
                pcm = ((values ^ 0x800000) - 0x800000).reshape(-1, 2)
            clips = np.stack([pcm[t*rate:(t+4)*rate].T for t in STARTS])
            spec = frontend(torch.from_numpy(clips).float() / (1 << (bits-1)), rate)
            images[i, c] = F.adaptive_avg_pool2d(spec, (128, 32))
            measures[i, c] = report["compression_trace"]
    return images, measures


def fit_cnn(images, train, *, ranking_weight=0.0):
    model = build_candidate()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    rng = torch.Generator().manual_seed(SEED)
    pairs = list(product(train, range(1, 7)))
    target = torch.tensor([0., 1.] * 6)
    for epoch in range(6):
        order = torch.randperm(len(pairs), generator=rng).tolist()
        for offset in range(0, len(order), 6):
            batch = []
            for index in order[offset:offset+6]:
                i, c = pairs[index]
                crop = (i + c - 1 + epoch) % 6
                batch.extend((images[i, 0][crop], images[i, c][crop]))
            optimizer.zero_grad(set_to_none=True)
            logits = model(torch.stack(batch))
            loss = F.binary_cross_entropy_with_logits(logits, target)
            if ranking_weight:
                loss = loss + ranking_weight * F.softplus(logits[::2] - logits[1::2]).mean()
            loss.backward()
            optimizer.step()
    model.eval()
    return model


def cnn_scores(model, images, test):
    with torch.inference_mode():
        return {key: model(images[key]).double().mean().item() for key in test}


def counts(scores):
    actual = np.array([c > 0 for i, c in scores])
    positive = np.array(list(scores.values())) >= 0
    tp = int((actual & positive).sum())
    tn = int((~actual & ~positive).sum())
    return dict(true_positive=tp, positives=36, true_negative=tn, negatives=6,
                sensitivity=tp/36, specificity=tn/6, balanced_accuracy=(tp/36 + tn/6)/2,
                detected_by_setting={STATES[c]: sum(int(s >= 0) for (_, k), s in scores.items() if k == c)
                                     for c in range(1, 7)})


def run(variants, reports, library_transfer):
    torch.set_num_threads(3)
    torch.use_deterministic_algorithms(True)
    images, measures = load_inputs(variants, reports)
    if library_transfer:
        model = fit_cnn(images, range(24))
        library, _ = load_inputs(variants, reports, "library")
        scores = cnn_scores(model, library, library.keys())
        comparisons = {}
        for c, state in enumerate(STATES[1:], 1):
            deltas = [scores[i, c] - scores[i, 0] for i in range(24)]
            comparisons[state] = dict(higher=sum(x > 0 for x in deltas), equal=sum(x == 0 for x in deltas),
                                      lower=sum(x < 0 for x in deltas), median_logit_delta=median(deltas))
        return dict(torch_version=torch.__version__, synthetic_pcm_hashes_verified=len(images),
                    library_pcm_hashes_verified=len(library), library_pairs=comparisons)
    folds = []
    for family in range(4):
        train = [i for i in range(24) if i//6 != family]
        test = list(product(range(family*6, family*6 + 6), range(7)))
        keys = list(product(train, range(7)))
        logistic = fit_logistic([measures[k] for k in keys], [int(c > 0) for _, c in keys],
                                [str(i//6) for i, _ in keys], partition="train")
        logits = logistic.logits([measures[k] for k in test])
        folds.append(dict(family=family, cnn=counts(cnn_scores(fit_cnn(images, train), images, test)),
                          logistic=counts(dict(zip(test, logits, strict=True)))))
        print(f"Completed held-out recipe {family}", flush=True)
    return dict(torch_version=torch.__version__, numpy_version=np.__version__, device="cpu",
                synthetic_pcm_hashes_verified=len(images), folds=folds, mean_balanced_accuracy={
                    name: mean(f[name]["balanced_accuracy"] for f in folds) for name in ("cnn", "logistic")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("variants", "reports", "output"):
        parser.add_argument(arg, type=Path)
    parser.add_argument("--library-transfer", action="store_true")
    args = parser.parse_args()
    result = run(args.variants, args.reports, args.library_transfer)
    with args.output.open("x") as out:
        out.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
