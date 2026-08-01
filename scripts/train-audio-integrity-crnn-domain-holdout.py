#!/usr/bin/env python3
"""Run a paper-aligned CRNN lossy-history probe with source-domain holdouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

TARGET_SAMPLE_RATE = 44_100
CLIP_SECONDS = 2
CLIP_SAMPLES = TARGET_SAMPLE_RATE * CLIP_SECONDS
N_FFT = 1_024
HOP_LENGTH = 512
CONV_CHANNELS = (16, 32, 64, 128)
POOL_SHAPES = ((2, 2), (2, 2), (2, 2), (2, 4))
LSTM_HIDDEN_SIZE = 128
LSTM_LAYERS = 2
CLASS_TO_LABEL = {"negative": 0, "controlled_positive": 1}
MODEL_DEFINITION = {
    "schema_version": 1,
    "paper": "Koops, Micchi, and Quinton, ISMIR 2024",
    "reproduction_boundary": "paper_aligned_independent_not_exact",
    "target_sample_rate": TARGET_SAMPLE_RATE,
    "clip_seconds": CLIP_SECONDS,
    "clip_samples": CLIP_SAMPLES,
    "spectrogram": {
        "n_fft": N_FFT,
        "win_length": N_FFT,
        "hop_length": HOP_LENGTH,
        "window": "hann",
        "center": True,
        "pad_mode": "reflect",
        "power": 1.0,
        "normalized": False,
        "onesided": True,
        "post_transform": "log1p_then_per_example_standardize",
    },
    "mask": {
        "training_probability": 1.0,
        "cutoff_distribution_hz": [14_000.0, TARGET_SAMPLE_RATE / 2],
        "masked_value": "per_example_standardized_minimum",
        "validation_and_evaluation": False,
    },
    "convolution": {
        "channels": CONV_CHANNELS,
        "kernel": [3, 3],
        "padding": [1, 1],
        "bias": False,
        "activation": "relu",
        "normalization": "batch_norm_2d",
        "pool_shapes": POOL_SHAPES,
    },
    "sequence": {
        "axis": "post_cnn_time",
        "input": "flattened_channel_frequency",
        "kind": "bidirectional_lstm",
        "layers": LSTM_LAYERS,
        "hidden_size": LSTM_HIDDEN_SIZE,
    },
    "classification": {
        "outputs": 2,
        "training_loss": "cross_entropy",
        "lossy_score": "softmax_output_1",
    },
    "track_inference": {
        "window_seconds": 2,
        "overlap_fraction": 0.5,
        "aggregation": "arithmetic_mean_lossy_probability",
    },
}
MODEL_DEFINITION_SHA256 = hashlib.sha256(
    json.dumps(MODEL_DEFINITION, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash_int(*values: object) -> int:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode())
        digest.update(b"\0")
    return int.from_bytes(digest.digest()[:8], "big")


def resolve_beneath(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise SystemExit(f"path escapes audio root: {relative}") from error
    return path


def resolve_across_roots(roots: list[Path], relative: str) -> Path:
    matches = [
        candidate
        for root in roots
        if (candidate := resolve_beneath(root, relative)).is_file()
    ]
    if not matches:
        raise SystemExit(f"audio is missing from every root: {relative}")
    if len(matches) > 1:
        raise SystemExit(f"audio path is ambiguous across roots: {relative}")
    return matches[0]


def domain_for_source_group(source_group: str, domain_map: dict[str, Any]) -> str:
    matches = [
        (rule["source_group_prefix"], rule["domain_id"])
        for rule in domain_map.get("rules", [])
        if source_group.startswith(rule.get("source_group_prefix", ""))
    ]
    if not matches:
        raise SystemExit(f"source group has no domain mapping: {source_group}")
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    longest = len(matches[0][0])
    top = {domain for prefix, domain in matches if len(prefix) == longest}
    if len(top) != 1:
        raise SystemExit(f"source group has ambiguous domain mapping: {source_group}")
    return next(iter(top))


def merged_cases(
    manifests: list[Path],
    audio_roots: list[Path],
    domain_map: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        for source_case in load_json(manifest).get("cases", []):
            case = dict(source_case)
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise SystemExit(f"{manifest}: case has no valid case_id")
            previous = by_id.setdefault(case_id, case)
            if previous != case:
                raise SystemExit(f"conflicting case definition: {case_id}")
    cases = sorted(by_id.values(), key=lambda item: item["case_id"])
    if not cases:
        raise SystemExit("manifests contain no cases")
    for case in cases:
        case_id = case["case_id"]
        if case.get("split") != "development":
            raise SystemExit(f"{case_id}: only development cases are accepted")
        if case.get("expectation") not in CLASS_TO_LABEL:
            raise SystemExit(f"{case_id}: unsupported expectation")
        source_group = case.get("source_group")
        partition_group = case.get("partition_group")
        if not isinstance(source_group, str) or not source_group:
            raise SystemExit(f"{case_id}: missing source_group")
        if not isinstance(partition_group, str) or not partition_group:
            raise SystemExit(f"{case_id}: missing partition_group")
        if partition_group != source_group:
            raise SystemExit(
                f"{case_id}: this public evaluation requires "
                "partition_group == source_group"
            )
        relative_path = case.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            raise SystemExit(f"{case_id}: missing relative_path")
        case["_audio_path"] = str(resolve_across_roots(audio_roots, relative_path))
        case["_domain"] = domain_for_source_group(source_group, domain_map)
        case["_label"] = CLASS_TO_LABEL[case["expectation"]]
    validate_domain_counts(cases, domain_map)
    return cases


def validate_domain_counts(
    cases: list[dict[str, Any]],
    domain_map: dict[str, Any],
) -> None:
    rules = {rule["domain_id"]: rule for rule in domain_map.get("rules", [])}
    domains = {case["_domain"] for case in cases}
    if "tier_b_private_full_mix" in domains:
        raise SystemExit("public CRNN cycle must not include the private full-mix domain")
    expected_domains = {
        "tier_a_guitarset",
        "tier_a_vocalset",
        "tier_a_groove",
        "tier_a_choralebricks",
        "tier_b_nsynth",
    }
    if domains != expected_domains:
        raise SystemExit(
            f"unexpected public domain set: {sorted(domains)}; "
            f"expected {sorted(expected_domains)}"
        )
    for domain in sorted(domains):
        rule = rules.get(domain)
        if rule is None:
            raise SystemExit(f"domain map has no rule for {domain}")
        selected = [case for case in cases if case["_domain"] == domain]
        groups = {case["partition_group"] for case in selected}
        negatives = sum(case["_label"] == 0 for case in selected)
        positives = sum(case["_label"] == 1 for case in selected)
        observed = (len(groups), len(selected), negatives, positives)
        expected = (
            rule["expected_partition_group_count"],
            rule["expected_case_count"],
            rule["expected_negative_count"],
            rule["expected_controlled_positive_count"],
        )
        if observed != expected:
            raise SystemExit(
                f"{domain}: observed groups/cases/negatives/positives "
                f"{observed}, expected {expected}"
            )


def verify_fingerprints(
    fingerprints: list[Path],
    cases: list[dict[str, Any]],
) -> str:
    expected: dict[str, str] = {}
    commitment = hashlib.sha256()
    for fingerprint in fingerprints:
        raw = fingerprint.read_bytes()
        commitment.update(raw)
        value = json.loads(raw)
        for case_id, digest in value.get("case_sha256", {}).items():
            previous = expected.setdefault(case_id, digest)
            if previous != digest:
                raise SystemExit(f"conflicting fingerprint for {case_id}")
    case_ids = {case["case_id"] for case in cases}
    if set(expected) != case_ids:
        missing = sorted(case_ids - set(expected))
        extra = sorted(set(expected) - case_ids)
        raise SystemExit(
            f"fingerprints differ from manifests; missing={missing[:3]} "
            f"extra={extra[:3]}"
        )
    for index, case in enumerate(cases, 1):
        path = Path(case["_audio_path"])
        if sha256_file(path) != expected[case["case_id"]]:
            raise SystemExit(f"{case['case_id']}: audio SHA-256 differs")
        if index % 100 == 0 or index == len(cases):
            print(f"[fingerprints {index:03}/{len(cases)}]")
    return commitment.hexdigest()


def manifest_commitment(manifests: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in manifests:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def inner_validation_groups(
    cases: list[dict[str, Any]],
    outer_domain: str,
    seed: int,
    fraction: float = 0.2,
) -> set[str]:
    groups_by_domain: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        if case["_domain"] != outer_domain:
            groups_by_domain[case["_domain"]].add(case["partition_group"])
    validation: set[str] = set()
    for domain, groups in sorted(groups_by_domain.items()):
        ordered = sorted(
            groups,
            key=lambda group: (stable_hash_int(seed, outer_domain, domain, group), group),
        )
        count = max(1, round(len(ordered) * fraction))
        count = min(count, len(ordered) - 1)
        if count < 1:
            raise SystemExit(f"{domain}: not enough groups for inner validation")
        validation.update(ordered[:count])
    return validation


def balanced_epoch_plan(
    cases: list[dict[str, Any]],
    seed: int,
    epoch: int,
) -> list[tuple[dict[str, Any], int]]:
    by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_label[case["_label"]].append(case)
    if set(by_label) != {0, 1}:
        raise ValueError("training cases must contain both labels")
    rng = random.Random(stable_hash_int(seed, "epoch-plan", epoch))
    target = max(len(by_label[0]), len(by_label[1]))
    result: list[tuple[dict[str, Any], int]] = []
    for label in (0, 1):
        ordered = sorted(by_label[label], key=lambda case: case["case_id"])
        rng.shuffle(ordered)
        for occurrence in range(target):
            if occurrence and occurrence % len(ordered) == 0:
                rng.shuffle(ordered)
            result.append((ordered[occurrence % len(ordered)], occurrence))
    rng.shuffle(result)
    return result


def strict_zero_false_positive_boundary(scores: list[float], labels: list[int]) -> float:
    negatives = [score for score, label in zip(scores, labels, strict=True) if label == 0]
    if not negatives:
        raise ValueError("at least one negative score is required")
    return math.nextafter(max(negatives), math.inf)


def binary_metrics(
    scores: list[float],
    labels: list[int],
    boundary: float,
) -> dict[str, Any]:
    if len(scores) != len(labels) or not scores:
        raise ValueError("scores and labels must be non-empty and equally sized")
    predictions = [score >= boundary for score in scores]
    true_positives = sum(prediction and label == 1 for prediction, label in zip(predictions, labels, strict=True))
    false_positives = sum(prediction and label == 0 for prediction, label in zip(predictions, labels, strict=True))
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    return {
        "positive_count": positive_count,
        "negative_count": negative_count,
        "true_positives": true_positives,
        "false_negatives": positive_count - true_positives,
        "false_positives": false_positives,
        "true_negatives": negative_count - false_positives,
        "recall": true_positives / positive_count if positive_count else None,
        "false_positive_rate": (
            false_positives / negative_count if negative_count else None
        ),
    }


def roc_auc(scores: list[float], labels: list[int]) -> float:
    positives = [score for score, label in zip(scores, labels, strict=True) if label == 1]
    negatives = [score for score, label in zip(scores, labels, strict=True) if label == 0]
    if not positives or not negatives:
        raise ValueError("AUC requires both labels")
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def binary_log_loss(scores: list[float], labels: list[int]) -> float:
    epsilon = 1.0e-7
    total = 0.0
    for score, label in zip(scores, labels, strict=True):
        probability = min(1.0 - epsilon, max(epsilon, score))
        total -= label * math.log(probability) + (1 - label) * math.log(
            1.0 - probability
        )
    return total / len(scores)


def import_ml_stack():
    try:
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio
        from torch import nn
        from torch.utils.data import DataLoader, Dataset
    except ImportError as error:
        raise SystemExit(
            "CRNN research requires numpy, soundfile, torch, and torchaudio "
            "in the selected Python environment"
        ) from error
    return np, sf, torch, torchaudio, nn, DataLoader, Dataset


def build_model(torch, torchaudio, nn):
    class LossyHistoryCrnn(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.spectrogram = torchaudio.transforms.Spectrogram(
                n_fft=N_FFT,
                win_length=N_FFT,
                hop_length=HOP_LENGTH,
                power=1.0,
                center=True,
                pad_mode="reflect",
                normalized=False,
                onesided=True,
            )
            blocks = []
            incoming = 1
            for outgoing, pool_shape in zip(
                CONV_CHANNELS, POOL_SHAPES, strict=True
            ):
                blocks.append(
                    nn.Sequential(
                        nn.Conv2d(
                            incoming,
                            outgoing,
                            kernel_size=3,
                            padding=1,
                            bias=False,
                        ),
                        nn.ReLU(),
                        nn.BatchNorm2d(outgoing),
                        nn.MaxPool2d(pool_shape),
                    )
                )
                incoming = outgoing
            self.blocks = nn.Sequential(*blocks)
            with torch.no_grad():
                shape_probe = torch.zeros(1, CLIP_SAMPLES)
                features = self._cnn_features(shape_probe, apply_mask=False)
            _, channels, frequency, _ = features.shape
            self.lstm_input_size = channels * frequency
            self.lstm = nn.LSTM(
                input_size=self.lstm_input_size,
                hidden_size=LSTM_HIDDEN_SIZE,
                num_layers=LSTM_LAYERS,
                batch_first=True,
                bidirectional=True,
            )
            self.classifier = nn.Linear(2 * LSTM_HIDDEN_SIZE, 2)

        def _cnn_features(self, waveforms, *, apply_mask: bool):
            magnitude = self.spectrogram(waveforms)
            features = torch.log1p(magnitude)
            mean = features.mean(dim=(-2, -1), keepdim=True)
            standard_deviation = features.std(
                dim=(-2, -1), keepdim=True, unbiased=False
            ).clamp_min(1.0e-6)
            features = (features - mean) / standard_deviation
            if apply_mask:
                batch = features.shape[0]
                cutoff = 14_000.0 + torch.rand(
                    batch, 1, 1, device=features.device
                ) * (TARGET_SAMPLE_RATE / 2 - 14_000.0)
                frequencies = torch.linspace(
                    0.0,
                    TARGET_SAMPLE_RATE / 2,
                    features.shape[-2],
                    device=features.device,
                ).view(1, -1, 1)
                minimum = features.amin(dim=(-2, -1), keepdim=True)
                features = torch.where(frequencies > cutoff, minimum, features)
            return self.blocks(features.unsqueeze(1))

        def forward(self, waveforms, *, apply_mask: bool = False):
            features = self._cnn_features(waveforms, apply_mask=apply_mask)
            sequence = features.permute(0, 3, 1, 2).flatten(start_dim=2)
            _, (hidden, _) = self.lstm(sequence)
            final = torch.cat((hidden[-2], hidden[-1]), dim=1)
            return self.classifier(final)

    return LossyHistoryCrnn()


def select_device(torch, requested: str):
    if requested == "auto":
        requested = "mps" if torch.backends.mps.is_available() else "cpu"
    if requested == "mps" and not torch.backends.mps.is_available():
        raise SystemExit("MPS was requested but is unavailable")
    return torch.device(requested)


def crop_start_fraction(seed: int, epoch: int, case_id: str, occurrence: int) -> float:
    numerator = stable_hash_int(seed, "crop", epoch, case_id, occurrence)
    return numerator / float(2**64 - 1)


def read_crop(
    case: dict[str, Any],
    fraction: float,
    *,
    start_frame: int | None = None,
    np,
    sf,
    torch,
    torchaudio,
):
    path = case["_audio_path"]
    with sf.SoundFile(path) as audio:
        sample_rate = int(audio.samplerate)
        source_length = round(CLIP_SECONDS * sample_rate)
        maximum_start = max(0, int(audio.frames) - source_length)
        if start_frame is None:
            start = min(maximum_start, math.floor(maximum_start * fraction))
        else:
            if not 0 <= start_frame <= maximum_start:
                raise RuntimeError(
                    f"{case['case_id']}: invalid evaluation start {start_frame}"
                )
            start = start_frame
        audio.seek(start)
        samples = audio.read(source_length, dtype="float32", always_2d=True)
    if len(samples) < source_length:
        samples = np.pad(samples, ((0, source_length - len(samples)), (0, 0)))
    mono = torch.from_numpy(samples.mean(axis=1)).view(1, -1)
    if sample_rate != TARGET_SAMPLE_RATE:
        mono = torchaudio.functional.resample(
            mono,
            sample_rate,
            TARGET_SAMPLE_RATE,
        )
    mono = mono.flatten()
    if mono.numel() < CLIP_SAMPLES:
        mono = torch.nn.functional.pad(mono, (0, CLIP_SAMPLES - mono.numel()))
    return mono[:CLIP_SAMPLES].contiguous()


def make_training_dataset_class(Dataset):
    class TrainingDataset(Dataset):
        def __init__(
            self,
            plan,
            *,
            seed,
            epoch,
            np,
            sf,
            torch,
            torchaudio,
        ):
            self.plan = plan
            self.seed = seed
            self.epoch = epoch
            self.np = np
            self.sf = sf
            self.torch = torch
            self.torchaudio = torchaudio

        def __len__(self):
            return len(self.plan)

        def __getitem__(self, index):
            case, occurrence = self.plan[index]
            fraction = crop_start_fraction(
                self.seed,
                self.epoch,
                case["case_id"],
                occurrence,
            )
            waveform = read_crop(
                case,
                fraction,
                np=self.np,
                sf=self.sf,
                torch=self.torch,
                torchaudio=self.torchaudio,
            )
            return waveform, case["_label"]

    return TrainingDataset


def case_window_starts(frame_count: int, sample_rate: int) -> list[int]:
    source_window = round(CLIP_SECONDS * sample_rate)
    if frame_count <= source_window:
        return [0]
    maximum_start = frame_count - source_window
    return list(range(0, maximum_start + 1, sample_rate))


def score_cases(
    model,
    cases: list[dict[str, Any]],
    *,
    batch_size: int,
    device,
    np,
    sf,
    torch,
    torchaudio,
) -> list[dict[str, Any]]:
    model.eval()
    results: list[dict[str, Any]] = []
    with torch.no_grad():
        for case_index, case in enumerate(cases, 1):
            info = sf.info(case["_audio_path"])
            sample_rate = int(info.samplerate)
            starts = case_window_starts(int(info.frames), sample_rate)
            probabilities: list[float] = []
            for offset in range(0, len(starts), batch_size):
                waveforms = [
                    read_crop(
                        case,
                        0.0,
                        start_frame=start,
                        np=np,
                        sf=sf,
                        torch=torch,
                        torchaudio=torchaudio,
                    )
                    for start in starts[offset : offset + batch_size]
                ]
                batch = torch.stack(waveforms).to(device)
                logits = model(batch, apply_mask=False)
                probabilities.extend(
                    torch.softmax(logits, dim=1)[:, 1].detach().cpu().tolist()
                )
            score = sum(probabilities) / len(probabilities)
            if not math.isfinite(score):
                raise RuntimeError(f"{case['case_id']}: non-finite score")
            results.append(
                {
                    "case_id": case["case_id"],
                    "source_group": case["source_group"],
                    "partition_group": case["partition_group"],
                    "domain": case["_domain"],
                    "class": case["class"],
                    "expectation": case["expectation"],
                    "original_sample_rate": sample_rate,
                    "window_count": len(probabilities),
                    "score": score,
                }
            )
            if case_index % 20 == 0 or case_index == len(cases):
                print(f"    [score {case_index:03}/{len(cases)}]")
    return results


def report_metrics(results: list[dict[str, Any]], boundary: float) -> dict[str, Any]:
    scores = [result["score"] for result in results]
    labels = [CLASS_TO_LABEL[result["expectation"]] for result in results]
    metrics = binary_metrics(scores, labels, boundary)
    metrics["auc"] = roc_auc(scores, labels)
    metrics["log_loss"] = binary_log_loss(scores, labels)
    return metrics


def by_class_counts(
    results: list[dict[str, Any]],
    boundary: float,
) -> dict[str, dict[str, int]]:
    by_class: dict[str, dict[str, int]] = {}
    for class_name in sorted({result["class"] for result in results}):
        selected = [result for result in results if result["class"] == class_name]
        by_class[class_name] = {
            "case_count": len(selected),
            "predicted_positive_count": sum(
                result["score"] >= boundary for result in selected
            ),
        }
    return by_class


def save_checkpoint_atomic(torch, path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temporary)
    temporary.replace(path)


def run_fold(
    outer_domain: str,
    cases: list[dict[str, Any]],
    *,
    args,
    output_dir: Path,
    device,
    np,
    sf,
    torch,
    torchaudio,
    nn,
    DataLoader,
    Dataset,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validation_groups = inner_validation_groups(cases, outer_domain, args.seed)
    outer = [case for case in cases if case["_domain"] == outer_domain]
    validation = [
        case
        for case in cases
        if case["_domain"] != outer_domain
        and case["partition_group"] in validation_groups
    ]
    training = [
        case
        for case in cases
        if case["_domain"] != outer_domain
        and case["partition_group"] not in validation_groups
    ]
    if (
        {case["partition_group"] for case in training}
        & {case["partition_group"] for case in validation}
    ):
        raise RuntimeError("inner training and validation groups overlap")
    if (
        {case["partition_group"] for case in training + validation}
        & {case["partition_group"] for case in outer}
    ):
        raise RuntimeError("outer and training/validation groups overlap")

    fold_seed = stable_hash_int(args.seed, outer_domain) % (2**31)
    random.seed(fold_seed)
    np.random.seed(fold_seed)
    torch.manual_seed(fold_seed)
    model = build_model(torch, torchaudio, nn).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    criterion = nn.CrossEntropyLoss()
    TrainingDataset = make_training_dataset_class(Dataset)
    checkpoint = output_dir / "checkpoints" / f"{outer_domain}.pt"
    epochs: list[dict[str, Any]] = []
    best_selection: tuple[float, float, float] | None = None
    best_epoch = 0
    without_improvement = 0

    print(
        f"[fold {outer_domain}] train={len(training)} "
        f"validation={len(validation)} outer={len(outer)}"
    )
    for epoch in range(1, args.max_epochs + 1):
        plan = balanced_epoch_plan(training, fold_seed, epoch)
        dataset = TrainingDataset(
            plan,
            seed=fold_seed,
            epoch=epoch,
            np=np,
            sf=sf,
            torch=torch,
            torchaudio=torchaudio,
        )
        loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=0,
        )
        model.train()
        total_loss = 0.0
        example_count = 0
        for waveforms, labels in loader:
            waveforms = waveforms.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(waveforms, apply_mask=True)
            loss = criterion(logits, labels)
            if not torch.isfinite(loss):
                raise RuntimeError(f"{outer_domain}: non-finite training loss")
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().cpu()) * len(labels)
            example_count += len(labels)
        validation_results = score_cases(
            model,
            validation,
            batch_size=args.batch_size,
            device=device,
            np=np,
            sf=sf,
            torch=torch,
            torchaudio=torchaudio,
        )
        validation_scores = [result["score"] for result in validation_results]
        validation_labels = [
            CLASS_TO_LABEL[result["expectation"]] for result in validation_results
        ]
        boundary = strict_zero_false_positive_boundary(
            validation_scores,
            validation_labels,
        )
        validation_metrics = report_metrics(validation_results, boundary)
        training_loss = total_loss / example_count
        selection = (
            validation_metrics["recall"],
            validation_metrics["auc"],
            -validation_metrics["log_loss"],
        )
        improved = best_selection is None or selection > best_selection
        epochs.append(
            {
                "epoch": epoch,
                "training_loss": training_loss,
                "validation_boundary_exclusive": boundary,
                "validation": validation_metrics,
                "selected": improved,
            }
        )
        print(
            f"[fold {outer_domain} epoch {epoch:02}] "
            f"train_loss={training_loss:.6f} "
            f"val_auc={validation_metrics['auc']:.6f} "
            f"val_strict_recall={validation_metrics['recall']:.6f}"
        )
        if improved:
            best_selection = selection
            best_epoch = epoch
            without_improvement = 0
            save_checkpoint_atomic(
                torch,
                checkpoint,
                {
                    "schema_version": 1,
                    "outer_domain": outer_domain,
                    "fold_seed": fold_seed,
                    "epoch": epoch,
                    "model_definition": MODEL_DEFINITION,
                    "model_definition_sha256": MODEL_DEFINITION_SHA256,
                    "model_state": model.state_dict(),
                    "validation_boundary_exclusive": boundary,
                    "validation_metrics": validation_metrics,
                },
            )
        else:
            without_improvement += 1
        if without_improvement >= args.patience:
            break

    saved = torch.load(checkpoint, map_location=device, weights_only=False)
    if saved["model_definition_sha256"] != MODEL_DEFINITION_SHA256:
        raise RuntimeError("checkpoint model definition differs")
    model.load_state_dict(saved["model_state"])
    boundary = float(saved["validation_boundary_exclusive"])
    outer_results = score_cases(
        model,
        outer,
        batch_size=args.batch_size,
        device=device,
        np=np,
        sf=sf,
        torch=torch,
        torchaudio=torchaudio,
    )
    for result in outer_results:
        result["boundary_exclusive"] = boundary
        result["predicted_positive"] = result["score"] >= boundary
    outer_metrics = report_metrics(outer_results, boundary)
    fold_gate = (
        outer_metrics["false_positives"] == 0
        and outer_metrics["recall"] is not None
        and outer_metrics["recall"] >= args.minimum_recall
    )
    fold = {
        "outer_domain": outer_domain,
        "fold_seed": fold_seed,
        "parameter_count": parameter_count,
        "training_case_count": len(training),
        "training_source_group_count": len(
            {case["partition_group"] for case in training}
        ),
        "validation_case_count": len(validation),
        "validation_source_group_count": len(validation_groups),
        "outer_case_count": len(outer),
        "outer_source_group_count": len(
            {case["partition_group"] for case in outer}
        ),
        "best_epoch": best_epoch,
        "epochs": epochs,
        "checkpoint": {
            "name": str(checkpoint.relative_to(output_dir)),
            "sha256": sha256_file(checkpoint),
            "size_bytes": checkpoint.stat().st_size,
        },
        "boundary_exclusive": boundary,
        "outer_metrics": outer_metrics,
        "outer_by_class": by_class_counts(outer_results, boundary),
        "gate_passed": fold_gate,
    }
    del model
    if device.type == "mps":
        torch.mps.empty_cache()
    return fold, outer_results


def validate_only(args) -> dict[str, Any]:
    domain_map = load_json(args.domain_map)
    cases = merged_cases(args.manifest, args.audio_root, domain_map)
    fingerprint_commitment = verify_fingerprints(args.fingerprints, cases)
    return {
        "case_count": len(cases),
        "source_group_count": len({case["source_group"] for case in cases}),
        "negative_count": sum(case["_label"] == 0 for case in cases),
        "controlled_positive_count": sum(case["_label"] == 1 for case in cases),
        "domains": sorted({case["_domain"] for case in cases}),
        "manifest_commitment": manifest_commitment(args.manifest),
        "fingerprint_commitment": fingerprint_commitment,
        "model_definition_sha256": MODEL_DEFINITION_SHA256,
    }


def run(args) -> None:
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite report: {args.report}")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to reuse output directory: {args.output_dir}")
    if not 0 < args.minimum_recall <= 1:
        raise SystemExit("--minimum-recall must be in (0, 1]")
    if args.max_epochs < 1 or args.patience < 1 or args.batch_size < 1:
        raise SystemExit("epoch, patience, and batch values must be positive")
    validation = validate_only(args)
    if args.command == "validate":
        print(json.dumps(validation, indent=2, sort_keys=True))
        return

    np, sf, torch, torchaudio, nn, DataLoader, Dataset = import_ml_stack()
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    torch.use_deterministic_algorithms(True, warn_only=True)
    device = select_device(torch, args.device)
    domain_map = load_json(args.domain_map)
    cases = merged_cases(args.manifest, args.audio_root, domain_map)
    args.output_dir.mkdir(parents=True)
    domains = sorted({case["_domain"] for case in cases})
    folds: list[dict[str, Any]] = []
    combined_results: list[dict[str, Any]] = []
    for domain in domains:
        fold, outer_results = run_fold(
            domain,
            cases,
            args=args,
            output_dir=args.output_dir,
            device=device,
            np=np,
            sf=sf,
            torch=torch,
            torchaudio=torchaudio,
            nn=nn,
            DataLoader=DataLoader,
            Dataset=Dataset,
        )
        folds.append(fold)
        combined_results.extend(outer_results)
        partial = {
            "schema_version": 1,
            "state": "partial_development_research",
            "completed_outer_domains": [item["outer_domain"] for item in folds],
            "folds": folds,
            "case_predictions": combined_results,
        }
        write_atomic(args.output_dir / "partial-report.json", partial)

    if {result["case_id"] for result in combined_results} != {
        case["case_id"] for case in cases
    }:
        raise RuntimeError("combined outer predictions do not cover every case once")
    combined_scores = [result["score"] for result in combined_results]
    combined_labels = [
        CLASS_TO_LABEL[result["expectation"]] for result in combined_results
    ]
    combined_predictions = [result["predicted_positive"] for result in combined_results]
    combined_metrics = {
        "positive_count": sum(combined_labels),
        "negative_count": len(combined_labels) - sum(combined_labels),
        "true_positives": sum(
            prediction and label == 1
            for prediction, label in zip(
                combined_predictions, combined_labels, strict=True
            )
        ),
        "false_positives": sum(
            prediction and label == 0
            for prediction, label in zip(
                combined_predictions, combined_labels, strict=True
            )
        ),
    }
    combined_metrics["false_negatives"] = (
        combined_metrics["positive_count"] - combined_metrics["true_positives"]
    )
    combined_metrics["true_negatives"] = (
        combined_metrics["negative_count"] - combined_metrics["false_positives"]
    )
    combined_metrics["recall"] = (
        combined_metrics["true_positives"] / combined_metrics["positive_count"]
    )
    combined_metrics["false_positive_rate"] = (
        combined_metrics["false_positives"] / combined_metrics["negative_count"]
    )
    combined_metrics["auc"] = roc_auc(combined_scores, combined_labels)
    gate_passed = all(fold["gate_passed"] for fold in folds)
    report = {
        "schema_version": 1,
        "state": "development_research_only",
        "method": "ismir_2024_paper_aligned_crnn_random_mask",
        "reproduction_boundary": "paper_aligned_independent_not_exact",
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "heldout_opened": False,
        "public_verdict_enabled": False,
        "feature_version": 0,
        "cache_schema_version": 21,
        "input_validation": validation,
        "runtime": {
            "python": os.sys.version,
            "torch": torch.__version__,
            "torchaudio": torchaudio.__version__,
            "device": str(device),
        },
        "model_definition": MODEL_DEFINITION,
        "model_definition_sha256": MODEL_DEFINITION_SHA256,
        "training": {
            "optimizer": "adam",
            "learning_rate": args.learning_rate,
            "batch_size": args.batch_size,
            "max_epochs": args.max_epochs,
            "patience": args.patience,
            "seed": args.seed,
            "checkpoint_selection": [
                "strict_zero_false_positive_validation_recall",
                "validation_auc",
                "negative_validation_log_loss",
            ],
        },
        "gate": {
            "minimum_recall_per_outer_domain": args.minimum_recall,
            "maximum_false_positives_per_outer_domain": 0,
            "passed": gate_passed,
        },
        "folds": folds,
        "combined_out_of_domain": combined_metrics,
        "case_predictions": sorted(
            combined_results, key=lambda result: result["case_id"]
        ),
        "disposition": (
            "development_gate_passed_candidate_requires_independent_review"
            if gate_passed
            else "failed_development_source_domain_gate"
        ),
    }
    write_atomic(args.report, report)
    write_atomic(args.output_dir / "final-report.json", report)
    print(
        f"wrote {args.report}; disposition={report['disposition']} "
        f"TP={combined_metrics['true_positives']}/"
        f"{combined_metrics['positive_count']} "
        f"FP={combined_metrics['false_positives']}/"
        f"{combined_metrics['negative_count']}"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("validate", "run"))
    result.add_argument("--manifest", action="append", type=Path, required=True)
    result.add_argument("--fingerprints", action="append", type=Path, required=True)
    result.add_argument("--audio-root", action="append", type=Path, required=True)
    result.add_argument("--domain-map", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--seed", type=int, default=20260731)
    result.add_argument("--batch-size", type=int, default=32)
    result.add_argument("--max-epochs", type=int, default=30)
    result.add_argument("--patience", type=int, default=5)
    result.add_argument("--learning-rate", type=float, default=0.001)
    result.add_argument("--minimum-recall", type=float, default=0.90)
    result.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    return result


if __name__ == "__main__":
    run(parser().parse_args())
