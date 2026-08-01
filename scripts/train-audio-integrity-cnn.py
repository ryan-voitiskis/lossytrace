#!/usr/bin/env python3
"""Train and cross-validate a private, cutoff-robust lossy-trace probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

FRAME_SIZE = 512
HOP_SIZE = 256
IMAGE_WIDTH = 172
CLIP_SAMPLES = FRAME_SIZE + (IMAGE_WIDTH - 1) * HOP_SIZE
CLIP_FRACTIONS = (0.12, 0.30, 0.48, 0.66, 0.84)
FEATURE_DEFINITION = {
    "schema_version": 1,
    "channel_reduction": "arithmetic_mean",
    "frame_size": FRAME_SIZE,
    "hop_size": HOP_SIZE,
    "image_width": IMAGE_WIDTH,
    "clip_samples": CLIP_SAMPLES,
    "clip_fractions": CLIP_FRACTIONS,
    "window": "periodic_hann",
    "stft_center": False,
    "magnitude_normalization": "divide_by_sqrt_frame_size",
    "log_floor": 1.0e-12,
    "dynamic_range_db": 120.0,
    "stored_dtype": "float16",
}
FEATURE_DEFINITION_SHA256 = hashlib.sha256(
    json.dumps(
        FEATURE_DEFINITION,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: dict) -> None:
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


def resolve_beneath(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise SystemExit(f"path escapes audio root: {relative}") from error
    return path


def resolve_across_roots(roots: list[Path], relative: str) -> Path:
    matches = [
        path
        for root in roots
        if (path := resolve_beneath(root, relative)).is_file()
    ]
    if not matches:
        raise SystemExit(f"audio is missing from every root: {relative}")
    if len(matches) > 1:
        raise SystemExit(
            f"audio path is ambiguous across roots: {relative}"
        )
    return matches[0]


def manifest_signature(manifests: list[Path], cases: list[dict]) -> str:
    digest = hashlib.sha256()
    for path in manifests:
        digest.update(path.read_bytes())
    for case in cases:
        digest.update(case["case_id"].encode())
        digest.update(case["relative_path"].encode())
    return digest.hexdigest()


def verify_audio_fingerprints(
    fingerprints: list[Path],
    cases: list[dict],
    roots: list[Path],
) -> str:
    expected: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in fingerprints:
        value = load_json(path)
        digest.update(path.read_bytes())
        for case_id, audio_sha256 in value.get("case_sha256", {}).items():
            previous = expected.setdefault(case_id, audio_sha256)
            if previous != audio_sha256:
                raise SystemExit(
                    f"conflicting fingerprint for case: {case_id}"
                )
    case_ids = {case["case_id"] for case in cases}
    if set(expected) != case_ids:
        raise SystemExit(
            "fingerprint files and manifests contain different case IDs"
        )
    for case in cases:
        path = resolve_across_roots(roots, case["relative_path"])
        if sha256_file(path) != expected[case["case_id"]]:
            raise SystemExit(
                f"{case['case_id']}: current audio SHA-256 differs"
            )
    return digest.hexdigest()


def merged_cases(manifests: list[Path]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for path in manifests:
        for case in load_json(path).get("cases", []):
            previous = by_id.setdefault(case["case_id"], case)
            if previous != case:
                raise SystemExit(f"conflicting case definition: {case['case_id']}")
    cases = sorted(by_id.values(), key=lambda case: case["case_id"])
    if not cases:
        raise SystemExit("manifests contain no cases")
    for case in cases:
        if case.get("split") != "development":
            raise SystemExit(
                f"{case['case_id']}: training accepts development cases only"
            )
        if case.get("expectation") not in {"negative", "controlled_positive"}:
            raise SystemExit(
                f"{case['case_id']}: unsupported expectation for training"
            )
    return cases


def extract_clip(path: Path, start: int) -> tuple[torch.Tensor, int]:
    with sf.SoundFile(path) as audio:
        sample_rate = int(audio.samplerate)
        audio.seek(start)
        samples = audio.read(CLIP_SAMPLES, dtype="float32", always_2d=True)
    if len(samples) < CLIP_SAMPLES:
        samples = np.pad(samples, ((0, CLIP_SAMPLES - len(samples)), (0, 0)))
    mono = torch.from_numpy(samples.mean(axis=1))
    spectrum = torch.stft(
        mono,
        n_fft=FRAME_SIZE,
        hop_length=HOP_SIZE,
        win_length=FRAME_SIZE,
        window=torch.hann_window(FRAME_SIZE, periodic=True),
        center=False,
        return_complex=True,
    )
    if spectrum.shape != (FRAME_SIZE // 2 + 1, IMAGE_WIDTH):
        raise RuntimeError(f"{path}: unexpected spectrogram shape {spectrum.shape}")
    magnitude = spectrum.abs() / math.sqrt(FRAME_SIZE)
    level = (1.0 + 20.0 * magnitude.clamp_min(1.0e-12).log10() / 120.0).clamp(
        0.0, 1.0
    )
    return level.half(), sample_rate


def prepare_features(
    cases: list[dict],
    roots: list[Path],
    *,
    signature: str,
    cache: Path,
) -> dict:
    features: list[torch.Tensor] = []
    metadata: list[dict] = []
    for index, case in enumerate(cases, 1):
        print(f"[extract {index:03}/{len(cases)}] {case['case_id']}")
        path = resolve_across_roots(roots, case["relative_path"])
        with sf.SoundFile(path) as audio:
            frame_count = int(audio.frames)
        max_start = max(0, frame_count - CLIP_SAMPLES)
        for clip_index, fraction in enumerate(CLIP_FRACTIONS):
            start = min(max_start, round(max_start * fraction))
            feature, sample_rate = extract_clip(path, start)
            features.append(feature)
            metadata.append(
                {
                    "case_id": case["case_id"],
                    "source_group": case["source_group"],
                    "partition_group": case.get(
                        "partition_group",
                        case["source_group"],
                    ),
                    "class": case["class"],
                    "expectation": case["expectation"],
                    "clip_index": clip_index,
                    "sample_rate": sample_rate,
                }
            )
    payload = {
        "schema_version": 1,
        "manifest_signature": signature,
        "feature_definition": FEATURE_DEFINITION,
        "feature_definition_sha256": FEATURE_DEFINITION_SHA256,
        "features": torch.stack(features),
        "metadata": metadata,
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, cache)
    return payload


class ClipDataset(Dataset):
    def __init__(
        self,
        features: torch.Tensor,
        metadata: list[dict],
        indices: list[int],
        *,
        augment: bool,
        seed: int,
        mask_probability: float,
        level_shift_probability: float,
    ):
        self.features = features
        self.metadata = metadata
        self.indices = indices
        self.augment = augment
        self.random = random.Random(seed)
        self.mask_probability = mask_probability
        self.level_shift_probability = level_shift_probability

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, item: int) -> tuple[torch.Tensor, torch.Tensor]:
        index = self.indices[item]
        feature = self.features[index].float().unsqueeze(0)
        metadata = self.metadata[index]
        if self.augment:
            if self.random.random() < self.mask_probability:
                nyquist = metadata["sample_rate"] * 0.5
                cutoff = self.random.uniform(14_000.0, nyquist)
                first_masked_bin = math.ceil(cutoff / nyquist * (feature.shape[1] - 1))
                feature[:, first_masked_bin:, :] = 0.0
            if self.random.random() < self.level_shift_probability:
                feature = (feature + self.random.uniform(-0.05, 0.025)).clamp(
                    0.0, 1.0
                )
        label = float(metadata["expectation"] == "controlled_positive")
        return feature, torch.tensor(label, dtype=torch.float32)


class LossyTraceCnn(nn.Module):
    def __init__(self):
        super().__init__()
        channels = (1, 8, 16, 24, 32)
        layers: list[nn.Module] = []
        for input_channels, output_channels in zip(channels, channels[1:]):
            layers.extend(
                [
                    nn.Conv2d(input_channels, output_channels, 3, padding=1),
                    nn.BatchNorm2d(output_channels),
                    nn.ReLU(),
                    nn.MaxPool2d(2),
                ]
            )
        self.features = nn.Sequential(*layers)
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d((4, 5)),
            nn.Flatten(),
            nn.Linear(32 * 4 * 5, 64),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Linear(64, 1),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(value)).squeeze(1)


def choose_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def nested_group_split(
    groups: list[str],
    group_fold: dict[str, int],
    outer_fold: int,
    *,
    early_stop_group_fraction: float,
    early_stop_seed: int,
) -> tuple[set[str], set[str], set[str]]:
    test_groups = {
        group
        for group in groups
        if group_fold[group] == outer_fold
    }
    outer_training_groups = [
        group
        for group in groups
        if group_fold[group] != outer_fold
    ]
    random.Random(early_stop_seed + outer_fold).shuffle(
        outer_training_groups
    )
    early_stop_group_count = max(
        1,
        min(
            len(outer_training_groups) - 1,
            round(
                len(outer_training_groups)
                * early_stop_group_fraction
            ),
        ),
    )
    early_stop_groups = set(
        outer_training_groups[:early_stop_group_count]
    )
    train_groups = set(
        outer_training_groups[early_stop_group_count:]
    )
    if (
        train_groups & early_stop_groups
        or train_groups & test_groups
        or early_stop_groups & test_groups
        or train_groups | early_stop_groups | test_groups != set(groups)
    ):
        raise RuntimeError("nested group split is not a disjoint partition")
    return train_groups, early_stop_groups, test_groups


def train_fold(
    fold: int,
    train_indices: list[int],
    early_stop_indices: list[int],
    test_indices: list[int],
    *,
    features: torch.Tensor,
    metadata: list[dict],
    device: torch.device,
    epochs: int,
    batch_size: int,
    seed: int,
    mask_probability: float,
    level_shift_probability: float,
    model_dir: Path,
) -> tuple[dict[int, float], dict]:
    torch.manual_seed(seed + fold)
    model = LossyTraceCnn().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.0e-3, weight_decay=1.0e-4)
    loss_function = nn.BCEWithLogitsLoss()
    generator = torch.Generator().manual_seed(seed + fold)
    train_loader = DataLoader(
        ClipDataset(
            features,
            metadata,
            train_indices,
            augment=True,
            seed=seed + fold,
            mask_probability=mask_probability,
            level_shift_probability=level_shift_probability,
        ),
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    early_stop_loader = DataLoader(
        ClipDataset(
            features,
            metadata,
            early_stop_indices,
            augment=False,
            seed=seed + fold,
            mask_probability=mask_probability,
            level_shift_probability=level_shift_probability,
        ),
        batch_size=batch_size,
    )
    best_loss = math.inf
    best_state: dict | None = None
    patience = 0
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        train_losses = []
        for batch, labels in train_loader:
            batch = batch.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(batch), labels)
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.detach().cpu()))
        model.eval()
        early_stop_losses = []
        with torch.no_grad():
            for batch, labels in early_stop_loader:
                batch = batch.to(device)
                labels = labels.to(device)
                early_stop_losses.append(
                    float(loss_function(model(batch), labels).cpu())
                )
        train_loss = statistics.fmean(train_losses)
        early_stop_loss = statistics.fmean(early_stop_losses)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "early_stop_loss": early_stop_loss,
            }
        )
        print(
            f"[fold {fold + 1}] epoch={epoch:02} "
            f"train={train_loss:.4f} early_stop={early_stop_loss:.4f}"
        )
        if early_stop_loss < best_loss - 1.0e-4:
            best_loss = early_stop_loss
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            patience = 0
        else:
            patience += 1
            if patience >= 4:
                break
    if best_state is None:
        raise RuntimeError("training did not produce a model")
    model.load_state_dict(best_state)
    model_dir.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, model_dir / f"fold-{fold + 1}.pt")

    probabilities: dict[int, float] = {}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(test_indices), batch_size):
            indices = test_indices[start : start + batch_size]
            batch = features[indices].float().unsqueeze(1).to(device)
            values = torch.sigmoid(model(batch)).cpu().tolist()
            probabilities.update(zip(indices, values))
    return probabilities, {
        "fold": fold + 1,
        "best_inner_early_stop_loss": best_loss,
        "epochs_run": len(history),
        "outer_test_labels_used_for_epoch_selection": False,
        "history": history,
    }


def auc(positives: list[float], negatives: list[float]) -> float:
    return sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    ) / (len(positives) * len(negatives))


def command(args: argparse.Namespace) -> int:
    trainer_source_sha256 = sha256_file(Path(__file__).resolve())
    for name, value in (
        ("--mask-probability", args.mask_probability),
        ("--level-shift-probability", args.level_shift_probability),
    ):
        if not 0.0 <= value <= 1.0:
            raise SystemExit(f"{name} must be between 0 and 1")
    if not 0.0 < args.early_stop_group_fraction < 0.5:
        raise SystemExit(
            "--early-stop-group-fraction must be between 0 and 0.5"
        )
    for label, paths in (
        ("manifest", args.manifest),
        ("fingerprints", args.fingerprints),
    ):
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise SystemExit(
                    f"{label} is not a regular file: {path}"
                )
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace model report: {args.output}")
    if args.model_dir.exists() or args.model_dir.is_symlink():
        raise SystemExit(f"refusing to replace model directory: {args.model_dir}")
    if args.feature_cache.is_symlink():
        raise SystemExit(
            f"feature cache must not be a symlink: {args.feature_cache}"
        )
    cases = merged_cases(args.manifest)
    roots = [path.expanduser().resolve() for path in args.audio_root]
    if len(roots) != len(set(roots)):
        raise SystemExit("audio roots must not be repeated")
    for root in roots:
        if root.is_symlink() or not root.is_dir():
            raise SystemExit(f"audio root is not a regular directory: {root}")
    groups = sorted(
        {
            case.get("partition_group", case["source_group"])
            for case in cases
        }
    )
    source_group_count = len(
        {case["source_group"] for case in cases}
    )
    if len(groups) < args.folds:
        raise SystemExit("fewer partition groups than folds")
    signature = manifest_signature(args.manifest, cases)
    fingerprint_signature = verify_audio_fingerprints(
        args.fingerprints,
        cases,
        roots,
    )
    legacy_feature_cache_adopted = False
    if args.feature_cache.is_file():
        payload = torch.load(
            args.feature_cache,
            map_location="cpu",
            weights_only=False,
        )
        if payload.get("manifest_signature") != signature:
            raise SystemExit("feature cache belongs to a different manifest")
        cached_definition = payload.get("feature_definition_sha256")
        if cached_definition != FEATURE_DEFINITION_SHA256:
            if (
                cached_definition is None
                and args.allow_legacy_feature_cache
            ):
                legacy_feature_cache_adopted = True
            else:
                raise SystemExit(
                    "feature cache belongs to a different or uncommitted "
                    "feature definition"
                )
    else:
        payload = prepare_features(
            cases,
            roots,
            signature=signature,
            cache=args.feature_cache,
        )
    features: torch.Tensor = payload["features"]
    metadata: list[dict] = payload["metadata"]
    if len(features) != len(metadata):
        raise SystemExit("feature cache shape mismatch")
    partition_by_case = {
        case["case_id"]: case.get(
            "partition_group",
            case["source_group"],
        )
        for case in cases
    }
    for item in metadata:
        item["partition_group"] = partition_by_case[item["case_id"]]

    shuffled_groups = groups.copy()
    random.Random(args.fold_seed).shuffle(shuffled_groups)
    group_fold = {
        group: index % args.folds for index, group in enumerate(shuffled_groups)
    }
    device = choose_device(args.device)
    print(f"training on {device}; groups={len(groups)} clips={len(metadata)}")
    out_of_fold: dict[int, float] = {}
    fold_reports = []
    for fold in range(args.folds):
        train_groups, early_stop_groups, test_groups = (
            nested_group_split(
                groups,
                group_fold,
                fold,
                early_stop_group_fraction=(
                    args.early_stop_group_fraction
                ),
                early_stop_seed=args.early_stop_seed,
            )
        )
        test_indices = [
            index
            for index, item in enumerate(metadata)
            if item["partition_group"] in test_groups
        ]
        train_indices = [
            index
            for index, item in enumerate(metadata)
            if item["partition_group"] in train_groups
        ]
        early_stop_indices = [
            index
            for index, item in enumerate(metadata)
            if item["partition_group"] in early_stop_groups
        ]
        probabilities, report = train_fold(
            fold,
            train_indices,
            early_stop_indices,
            test_indices,
            features=features,
            metadata=metadata,
            device=device,
            epochs=args.epochs,
            batch_size=args.batch_size,
            seed=args.seed,
            mask_probability=args.mask_probability,
            level_shift_probability=args.level_shift_probability,
            model_dir=args.model_dir,
        )
        report.update(
            {
                "training_partition_group_count": len(train_groups),
                "inner_early_stop_partition_group_count": len(
                    early_stop_groups
                ),
                "outer_test_partition_group_count": len(test_groups),
            }
        )
        out_of_fold.update(probabilities)
        fold_reports.append(report)
    if len(out_of_fold) != len(metadata):
        raise RuntimeError("cross-validation did not score every clip")

    by_case: dict[str, list[float]] = defaultdict(list)
    case_metadata: dict[str, dict] = {}
    for index, item in enumerate(metadata):
        by_case[item["case_id"]].append(out_of_fold[index])
        case_metadata[item["case_id"]] = item
    rows = []
    for case_id in sorted(by_case):
        probabilities = by_case[case_id]
        item = case_metadata[case_id]
        rows.append(
            {
                "case_id": case_id,
                "source_group": item["source_group"],
                "partition_group": item["partition_group"],
                "class": item["class"],
                "expectation": item["expectation"],
                "fold": group_fold[item["partition_group"]] + 1,
                "clip_count": len(probabilities),
                "lossy_probability_mean": statistics.fmean(probabilities),
                "lossy_probability_min": min(probabilities),
                "lossy_probability_max": max(probabilities),
            }
        )
    negatives = [
        row["lossy_probability_mean"]
        for row in rows
        if row["expectation"] == "negative"
    ]
    positives = [
        row["lossy_probability_mean"]
        for row in rows
        if row["expectation"] == "controlled_positive"
    ]
    zero_false_positive_boundary = max(negatives)
    class_summary = {}
    for class_name in sorted({row["class"] for row in rows}):
        class_rows = [row for row in rows if row["class"] == class_name]
        values = [row["lossy_probability_mean"] for row in class_rows]
        class_summary[class_name] = {
            "cases": len(values),
            "median": statistics.median(values),
            "minimum": min(values),
            "maximum": max(values),
            "above_zero_false_positive_boundary": sum(
                value > zero_false_positive_boundary for value in values
            ),
        }
    write_atomic(
        args.output,
        {
            "schema_version": 3,
            "trainer_source_sha256": trainer_source_sha256,
            "manifest_signature": signature,
            "fingerprint_signature": fingerprint_signature,
            "feature_cache_sha256": sha256_file(args.feature_cache),
            "feature_extraction": {
                "definition": FEATURE_DEFINITION,
                "definition_sha256": FEATURE_DEFINITION_SHA256,
                "legacy_feature_cache_adopted": (
                    legacy_feature_cache_adopted
                ),
            },
            "device": str(device),
            "torch_version": torch.__version__,
            "seed": args.seed,
            "fold_seed": args.fold_seed,
            "early_stop_seed": args.early_stop_seed,
            "fold_count": args.folds,
            "source_group_count": source_group_count,
            "partition_group_count": len(groups),
            "audio_root_count": len(roots),
            "clip_fractions": CLIP_FRACTIONS,
            "augmentation": {
                "random_high_frequency_mask_probability": args.mask_probability,
                "random_high_frequency_mask_minimum_hz": 14_000,
                "random_level_shift_probability": args.level_shift_probability,
            },
            "cross_validation": {
                "outer_group": "partition_group",
                "inner_early_stop_group_fraction": (
                    args.early_stop_group_fraction
                ),
                "outer_test_labels_used_for_epoch_selection": False,
            },
            "metrics": {
                "case_level_auc": auc(positives, negatives),
                "zero_false_positive_boundary": zero_false_positive_boundary,
                "controlled_positives_above_boundary": sum(
                    value > zero_false_positive_boundary for value in positives
                ),
                "controlled_positive_count": len(positives),
                "negative_count": len(negatives),
            },
            "by_class": class_summary,
            "folds": fold_reports,
            "results": rows,
        },
    )
    print(f"wrote cross-validation report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, action="append", required=True)
    result.add_argument(
        "--fingerprints",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument(
        "--audio-root",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument("--feature-cache", type=Path, required=True)
    result.add_argument(
        "--allow-legacy-feature-cache",
        action="store_true",
        help=(
            "adopt a pre-contract cache only after external provenance "
            "verification; the report records this exception"
        ),
    )
    result.add_argument("--model-dir", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--folds", type=int, default=5)
    result.add_argument("--epochs", type=int, default=20)
    result.add_argument("--batch-size", type=int, default=32)
    result.add_argument("--seed", type=int, default=20260730)
    result.add_argument("--fold-seed", type=int, default=20260730)
    result.add_argument("--early-stop-seed", type=int, default=20260730)
    result.add_argument(
        "--early-stop-group-fraction",
        type=float,
        default=0.20,
    )
    result.add_argument("--mask-probability", type=float, default=0.70)
    result.add_argument("--level-shift-probability", type=float, default=0.50)
    result.add_argument("--device", default="auto")
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
