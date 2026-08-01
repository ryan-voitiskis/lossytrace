#!/usr/bin/env python3
"""Evaluate lossy-trace CNNs with entire source domains held out."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn.functional as functional
from torch import nn
from torch.utils.data import (
    DataLoader,
    Dataset,
    WeightedRandomSampler,
)

TRAINING_SCRIPT = Path(__file__).with_name("train-audio-integrity-cnn.py")
MERGE_SCRIPT = Path(__file__).with_name(
    "merge-audio-integrity-cnn-feature-caches.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CNN = load_module("reklaw_audio_integrity_cnn_training", TRAINING_SCRIPT)
MERGER = load_module("reklaw_audio_integrity_cache_merger", MERGE_SCRIPT)

REPRESENTATIONS = {
    "absolute_v1": {
        "schema_version": 1,
        "input_channels": 1,
        "description": (
            "Original normalized log-magnitude spectrogram. Retained as the "
            "shortcut-prone baseline."
        ),
        "channels": ["absolute_log_magnitude"],
    },
    "content_residual_v1": {
        "schema_version": 1,
        "input_channels": 3,
        "description": (
            "Local frequency residual, local time residual, and frequency "
            "gradient. Absolute spectral envelope is omitted to reduce "
            "source-content shortcuts."
        ),
        "channels": [
            "four_x_frequency_residual_9_bins",
            "four_x_time_residual_9_frames",
            "four_x_frequency_first_difference",
        ],
        "clamp": [-1.0, 1.0],
    },
    "hybrid_v1": {
        "schema_version": 1,
        "input_channels": 4,
        "description": (
            "Absolute spectrogram plus the three content-residual channels."
        ),
        "channels": [
            "absolute_log_magnitude",
            "four_x_frequency_residual_9_bins",
            "four_x_time_residual_9_frames",
            "four_x_frequency_first_difference",
        ],
        "clamp_residual_channels": [-1.0, 1.0],
    },
}
TRAINING_OBJECTIVES = {
    "binary_v1": {
        "schema_version": 1,
        "description": (
            "Independent clip-level binary cross entropy. Retained as the "
            "baseline objective."
        ),
    },
    "paired_rank_v1": {
        "schema_version": 1,
        "description": (
            "Within-source, same-clip-index positive-versus-negative ranking "
            "with a secondary binary calibration loss. Shared augmentation "
            "is applied to each pair."
        ),
    },
}
NORMALIZATIONS = {
    "batch_v1": {
        "schema_version": 1,
        "layer": "BatchNorm2d",
        "depends_on_training_domain_running_statistics": True,
    },
    "group_v1": {
        "schema_version": 1,
        "layer": "GroupNorm",
        "group_count": 4,
        "depends_on_training_domain_running_statistics": False,
    },
}
SAMPLING_STRATEGIES = {
    "natural_v1": {
        "schema_version": 1,
        "description": (
            "Each training clip appears once per epoch before DataLoader "
            "shuffling; source domains retain their natural sizes."
        ),
    },
    "source_domain_balanced_v1": {
        "schema_version": 1,
        "description": (
            "Replacement sampling weights each clip inversely to the number "
            "of training clips in its source domain."
        ),
    },
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def write_atomic(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace report: {path}")
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


def representation_sha256(name: str) -> str:
    return sha256_json(REPRESENTATIONS[name])


def objective_definition(
    name: str,
    *,
    ranking_margin: float,
    ranking_weight: float,
    classification_weight: float,
) -> dict:
    definition = dict(TRAINING_OBJECTIVES[name])
    if name == "paired_rank_v1":
        definition.update(
            {
                "ranking_loss": "softplus(margin-positive_logit+negative_logit)",
                "ranking_margin": ranking_margin,
                "ranking_weight": ranking_weight,
                "classification_loss": (
                    "binary_cross_entropy_with_logits"
                ),
                "classification_weight": classification_weight,
                "pair_key": ["source_group", "clip_index"],
            }
        )
    return definition


def transform_batch(
    batch: torch.Tensor,
    representation: str,
) -> torch.Tensor:
    if representation == "absolute_v1":
        return batch
    frequency_smooth = functional.avg_pool2d(
        batch,
        kernel_size=(9, 1),
        stride=1,
        padding=(4, 0),
        count_include_pad=False,
    )
    time_smooth = functional.avg_pool2d(
        batch,
        kernel_size=(1, 9),
        stride=1,
        padding=(0, 4),
        count_include_pad=False,
    )
    frequency_residual = ((batch - frequency_smooth) * 4.0).clamp(
        -1.0,
        1.0,
    )
    time_residual = ((batch - time_smooth) * 4.0).clamp(-1.0, 1.0)
    frequency_gradient = functional.pad(
        torch.diff(batch, dim=2),
        (0, 0, 1, 0),
    )
    frequency_gradient = (frequency_gradient * 4.0).clamp(-1.0, 1.0)
    residuals = torch.cat(
        [
            frequency_residual,
            time_residual,
            frequency_gradient,
        ],
        dim=1,
    )
    if representation == "content_residual_v1":
        return residuals
    if representation == "hybrid_v1":
        return torch.cat([batch, residuals], dim=1)
    raise ValueError(f"unknown representation: {representation}")


class DomainClipDataset(Dataset):
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
            nyquist = metadata["sample_rate"] * 0.5
            minimum_cutoff = min(14_000.0, nyquist)
            if (
                minimum_cutoff < nyquist
                and self.random.random() < self.mask_probability
            ):
                cutoff = self.random.uniform(minimum_cutoff, nyquist)
                first_masked_bin = math.ceil(
                    cutoff / nyquist * (feature.shape[1] - 1)
                )
                feature[:, first_masked_bin:, :] = 0.0
            if self.random.random() < self.level_shift_probability:
                feature = (
                    feature + self.random.uniform(-0.05, 0.025)
                ).clamp(0.0, 1.0)
        label = float(
            metadata["expectation"] == "controlled_positive"
        )
        return feature, torch.tensor(label, dtype=torch.float32)


class PairedDomainClipDataset(Dataset):
    def __init__(
        self,
        features: torch.Tensor,
        metadata: list[dict],
        indices: list[int],
        *,
        seed: int,
        mask_probability: float,
        level_shift_probability: float,
    ):
        self.features = features
        self.metadata = metadata
        self.random = random.Random(seed)
        self.mask_probability = mask_probability
        self.level_shift_probability = level_shift_probability
        negatives: dict[tuple[str, int], list[int]] = defaultdict(list)
        positive_indices = []
        for index in indices:
            item = metadata[index]
            key = (item["source_group"], item["clip_index"])
            if item["expectation"] == "negative":
                negatives[key].append(index)
            elif item["expectation"] == "controlled_positive":
                positive_indices.append(index)
        self.pairs = []
        for positive_index in positive_indices:
            item = metadata[positive_index]
            key = (item["source_group"], item["clip_index"])
            if key not in negatives:
                raise RuntimeError(
                    "positive clip has no within-source negative pair: "
                    f"{item['case_id']} clip {item['clip_index']}"
                )
            self.pairs.append((positive_index, tuple(negatives[key])))
        if not self.pairs:
            raise RuntimeError("paired training set contains no pairs")

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(
        self,
        item: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        positive_index, negative_options = self.pairs[item]
        negative_index = self.random.choice(negative_options)
        positive = self.features[positive_index].float().unsqueeze(0)
        negative = self.features[negative_index].float().unsqueeze(0)
        if self.random.random() < self.mask_probability:
            positive_rate = self.metadata[positive_index]["sample_rate"]
            negative_rate = self.metadata[negative_index]["sample_rate"]
            minimum_fraction = max(
                min(14_000.0 / (positive_rate * 0.5), 1.0),
                min(14_000.0 / (negative_rate * 0.5), 1.0),
            )
            if minimum_fraction < 1.0:
                cutoff_fraction = self.random.uniform(
                    minimum_fraction,
                    1.0,
                )
                first_masked_bin = math.ceil(
                    cutoff_fraction * (positive.shape[1] - 1)
                )
                positive[:, first_masked_bin:, :] = 0.0
                negative[:, first_masked_bin:, :] = 0.0
        if self.random.random() < self.level_shift_probability:
            shift = self.random.uniform(-0.05, 0.025)
            positive = (positive + shift).clamp(0.0, 1.0)
            negative = (negative + shift).clamp(0.0, 1.0)
        return positive, negative


def domain_balancing_weights(
    dataset: Dataset,
    metadata: list[dict],
) -> list[float]:
    if isinstance(dataset, DomainClipDataset):
        source_indices = dataset.indices
    elif isinstance(dataset, PairedDomainClipDataset):
        source_indices = [
            positive_index
            for positive_index, _negative_options in dataset.pairs
        ]
    else:
        raise TypeError("unsupported dataset for domain balancing")
    counts: dict[str, int] = defaultdict(int)
    for index in source_indices:
        counts[metadata[index]["source_domain"]] += 1
    if len(counts) < 2:
        raise RuntimeError(
            "domain-balanced sampling requires at least two domains"
        )
    return [
        1.0 / counts[metadata[index]["source_domain"]]
        for index in source_indices
    ]


class LossyTraceCnn(nn.Module):
    def __init__(self, input_channels: int, normalization: str):
        super().__init__()
        channels = (input_channels, 8, 16, 24, 32)
        layers: list[nn.Module] = []
        for incoming, outgoing in zip(channels, channels[1:]):
            if normalization == "batch_v1":
                normalization_layer: nn.Module = nn.BatchNorm2d(
                    outgoing
                )
            elif normalization == "group_v1":
                normalization_layer = nn.GroupNorm(4, outgoing)
            else:
                raise ValueError(
                    f"unknown normalization: {normalization}"
                )
            layers.extend(
                [
                    nn.Conv2d(incoming, outgoing, 3, padding=1),
                    normalization_layer,
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


def stable_seed(*values: object) -> int:
    digest = hashlib.sha256(
        ":".join(str(value) for value in values).encode()
    ).hexdigest()
    return int(digest[:8], 16)


def domain_holdout_split(
    metadata: list[dict],
    test_domain: str,
    *,
    early_stop_group_fraction: float,
    early_stop_seed: int,
) -> tuple[set[str], set[str], set[str]]:
    group_domain: dict[str, str] = {}
    for item in metadata:
        group = item["partition_group"]
        previous = group_domain.setdefault(group, item["source_domain"])
        if previous != item["source_domain"]:
            raise RuntimeError(
                f"partition group crosses source domains: {group}"
            )
    domains = sorted(set(group_domain.values()))
    if test_domain not in domains:
        raise ValueError(f"unknown test domain: {test_domain}")
    test_groups = {
        group
        for group, domain in group_domain.items()
        if domain == test_domain
    }
    early_stop_groups: set[str] = set()
    train_groups: set[str] = set()
    for domain in domains:
        if domain == test_domain:
            continue
        groups = sorted(
            group
            for group, assigned_domain in group_domain.items()
            if assigned_domain == domain
        )
        if len(groups) < 2:
            raise RuntimeError(
                f"training domain has fewer than two groups: {domain}"
            )
        random.Random(
            stable_seed(early_stop_seed, test_domain, domain)
        ).shuffle(groups)
        validation_count = max(
            1,
            min(
                len(groups) - 1,
                round(len(groups) * early_stop_group_fraction),
            ),
        )
        early_stop_groups.update(groups[:validation_count])
        train_groups.update(groups[validation_count:])
    all_groups = set(group_domain)
    if (
        train_groups & early_stop_groups
        or train_groups & test_groups
        or early_stop_groups & test_groups
        or train_groups | early_stop_groups | test_groups != all_groups
    ):
        raise RuntimeError("domain holdout split is not a partition")
    return train_groups, early_stop_groups, test_groups


def score_indices(
    model: nn.Module,
    features: torch.Tensor,
    indices: list[int],
    *,
    representation: str,
    batch_size: int,
    device: torch.device,
) -> dict[int, float]:
    probabilities: dict[int, float] = {}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            selected = indices[start : start + batch_size]
            batch = features[selected].float().unsqueeze(1).to(device)
            transformed = transform_batch(batch, representation)
            values = torch.sigmoid(model(transformed)).cpu().tolist()
            probabilities.update(zip(selected, values))
    return probabilities


def train_domain_fold(
    fold: int,
    test_domain: str,
    train_indices: list[int],
    early_stop_indices: list[int],
    test_indices: list[int],
    *,
    features: torch.Tensor,
    metadata: list[dict],
    representation: str,
    objective: str,
    ranking_margin: float,
    ranking_weight: float,
    classification_weight: float,
    normalization: str,
    sampling: str,
    device: torch.device,
    epochs: int,
    patience_limit: int,
    batch_size: int,
    seed: int,
    mask_probability: float,
    level_shift_probability: float,
    model_dir: Path,
) -> tuple[dict[int, float], dict[int, float], dict]:
    fold_seed = stable_seed(seed, test_domain)
    torch.manual_seed(fold_seed)
    model = LossyTraceCnn(
        REPRESENTATIONS[representation]["input_channels"],
        normalization,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=1.0e-3,
        weight_decay=1.0e-4,
    )
    loss_function = nn.BCEWithLogitsLoss()
    generator = torch.Generator().manual_seed(fold_seed)
    if objective == "binary_v1":
        training_dataset: Dataset = DomainClipDataset(
            features,
            metadata,
            train_indices,
            augment=True,
            seed=fold_seed,
            mask_probability=mask_probability,
            level_shift_probability=level_shift_probability,
        )
    elif objective == "paired_rank_v1":
        training_dataset = PairedDomainClipDataset(
            features,
            metadata,
            train_indices,
            seed=fold_seed,
            mask_probability=mask_probability,
            level_shift_probability=level_shift_probability,
        )
    else:
        raise ValueError(f"unknown training objective: {objective}")
    if sampling == "natural_v1":
        train_loader = DataLoader(
            training_dataset,
            batch_size=batch_size,
            shuffle=True,
            generator=generator,
        )
    elif sampling == "source_domain_balanced_v1":
        sampler = WeightedRandomSampler(
            domain_balancing_weights(training_dataset, metadata),
            num_samples=len(training_dataset),
            replacement=True,
            generator=generator,
        )
        train_loader = DataLoader(
            training_dataset,
            batch_size=batch_size,
            sampler=sampler,
        )
    else:
        raise ValueError(f"unknown sampling strategy: {sampling}")
    early_stop_loader = DataLoader(
        DomainClipDataset(
            features,
            metadata,
            early_stop_indices,
            augment=False,
            seed=fold_seed,
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
        for training_batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            if objective == "binary_v1":
                batch, labels = training_batch
                batch = transform_batch(
                    batch.to(device),
                    representation,
                )
                labels = labels.to(device)
                loss = loss_function(model(batch), labels)
            else:
                positive, negative = training_batch
                positive = transform_batch(
                    positive.to(device),
                    representation,
                )
                negative = transform_batch(
                    negative.to(device),
                    representation,
                )
                positive_logits = model(positive)
                negative_logits = model(negative)
                ranking_loss = functional.softplus(
                    ranking_margin
                    - positive_logits
                    + negative_logits
                ).mean()
                classification_logits = torch.cat(
                    [positive_logits, negative_logits]
                )
                classification_labels = torch.cat(
                    [
                        torch.ones_like(positive_logits),
                        torch.zeros_like(negative_logits),
                    ]
                )
                classification_loss = loss_function(
                    classification_logits,
                    classification_labels,
                )
                loss = (
                    ranking_weight * ranking_loss
                    + classification_weight * classification_loss
                )
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.detach().cpu()))
        model.eval()
        early_stop_losses = []
        with torch.no_grad():
            for batch, labels in early_stop_loader:
                batch = transform_batch(
                    batch.to(device),
                    representation,
                )
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
            f"[{fold + 1}/6 {test_domain}] epoch={epoch:02} "
            f"train={train_loss:.4f} early_stop={early_stop_loss:.4f}",
            flush=True,
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
            if patience >= patience_limit:
                break
    if best_state is None:
        raise RuntimeError("training did not produce a model")
    model.load_state_dict(best_state)
    model_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = model_dir / f"holdout-{test_domain}.pt"
    if checkpoint_path.exists() or checkpoint_path.is_symlink():
        raise SystemExit(f"refusing to replace checkpoint: {checkpoint_path}")
    torch.save(
        {
            "schema_version": 1,
            "state_dict": best_state,
            "representation": REPRESENTATIONS[representation],
            "representation_id": representation,
            "representation_sha256": representation_sha256(
                representation
            ),
            "objective": objective_definition(
                objective,
                ranking_margin=ranking_margin,
                ranking_weight=ranking_weight,
                classification_weight=classification_weight,
            ),
            "objective_id": objective,
            "normalization": NORMALIZATIONS[normalization],
            "normalization_id": normalization,
            "sampling": SAMPLING_STRATEGIES[sampling],
            "sampling_id": sampling,
            "feature_definition": CNN.FEATURE_DEFINITION,
            "feature_definition_sha256": (
                CNN.FEATURE_DEFINITION_SHA256
            ),
            "held_out_source_domain": test_domain,
            "seed": seed,
        },
        checkpoint_path,
    )
    validation_probabilities = score_indices(
        model,
        features,
        early_stop_indices,
        representation=representation,
        batch_size=batch_size,
        device=device,
    )
    test_probabilities = score_indices(
        model,
        features,
        test_indices,
        representation=representation,
        batch_size=batch_size,
        device=device,
    )
    return validation_probabilities, test_probabilities, {
        "fold": fold + 1,
        "held_out_source_domain": test_domain,
        "best_inner_early_stop_loss": best_loss,
        "epochs_run": len(history),
        "outer_test_labels_used_for_epoch_selection": False,
        "outer_test_labels_used_for_boundary_selection": False,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "history": history,
    }


def aggregate_case_scores(
    probabilities: dict[int, float],
    metadata: list[dict],
) -> list[dict]:
    by_case: dict[str, list[float]] = defaultdict(list)
    case_metadata: dict[str, dict] = {}
    for index, probability in probabilities.items():
        item = metadata[index]
        by_case[item["case_id"]].append(probability)
        case_metadata[item["case_id"]] = item
    rows = []
    for case_id in sorted(by_case):
        values = by_case[case_id]
        if len(values) != len(CNN.CLIP_FRACTIONS):
            raise RuntimeError(f"{case_id}: scored clip count differs")
        item = case_metadata[case_id]
        rows.append(
            {
                "case_id": case_id,
                "source_group": item["source_group"],
                "partition_group": item["partition_group"],
                "source_domain": item["source_domain"],
                "class": item["class"],
                "expectation": item["expectation"],
                "clip_count": len(values),
                "lossy_probability_mean": statistics.fmean(values),
                "lossy_probability_min": min(values),
                "lossy_probability_max": max(values),
            }
        )
    return rows


def metric_summary(rows: list[dict], boundary: float) -> dict:
    negatives = [
        row
        for row in rows
        if row["expectation"] == "negative"
    ]
    positives = [
        row
        for row in rows
        if row["expectation"] == "controlled_positive"
    ]
    negative_values = [
        row["lossy_probability_mean"] for row in negatives
    ]
    positive_values = [
        row["lossy_probability_mean"] for row in positives
    ]
    return {
        "case_level_auc": CNN.auc(
            positive_values,
            negative_values,
        ),
        "boundary": boundary,
        "false_positive_count": sum(
            value > boundary for value in negative_values
        ),
        "negative_count": len(negative_values),
        "controlled_positives_above_boundary": sum(
            value > boundary for value in positive_values
        ),
        "controlled_positive_count": len(positive_values),
        "controlled_positive_recall": (
            sum(value > boundary for value in positive_values)
            / len(positive_values)
        ),
    }


def validate_regular_file(label: str, path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if path.is_symlink() or resolved.is_symlink() or not resolved.is_file():
        raise SystemExit(f"{label} is not a regular file: {resolved}")
    return resolved


def command(args: argparse.Namespace) -> int:
    if not 0.0 < args.early_stop_group_fraction < 0.5:
        raise SystemExit(
            "--early-stop-group-fraction must be between 0 and 0.5"
        )
    for name, value in (
        ("--mask-probability", args.mask_probability),
        ("--level-shift-probability", args.level_shift_probability),
    ):
        if not 0.0 <= value <= 1.0:
            raise SystemExit(f"{name} must be between 0 and 1")
    if args.epochs < 1 or args.patience < 1 or args.batch_size < 1:
        raise SystemExit("epochs, patience, and batch size must be positive")
    if (
        args.ranking_margin < 0.0
        or args.ranking_weight <= 0.0
        or args.classification_weight < 0.0
    ):
        raise SystemExit(
            "ranking margin and classification weight must be non-negative; "
            "ranking weight must be positive"
        )
    output = args.output.expanduser().resolve()
    model_dir = args.model_dir.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace report: {output}")
    if model_dir.exists() or model_dir.is_symlink():
        raise SystemExit(f"refusing to replace model directory: {model_dir}")
    manifests = [
        validate_regular_file("manifest", path)
        for path in args.manifest
    ]
    feature_cache = validate_regular_file(
        "feature cache",
        args.feature_cache,
    )
    cache_record_path = validate_regular_file(
        "feature cache record",
        args.feature_cache_record,
    )
    domain_map_path = validate_regular_file(
        "domain map",
        args.domain_map,
    )
    cache_record = load_json(cache_record_path)
    if cache_record.get("disposition") != {
        "state": "merged_development_feature_cache",
        "audio_fingerprints_reverified_live": False,
        "release_evidence": False,
        "public_verdict_enabled": False,
        "reason": (
            "Features were restored from independently verified research "
            "archives. This avoids restoring private audio but cannot "
            "replace live fingerprint verification for release evidence."
        ),
    }:
        raise SystemExit("feature cache record disposition differs")
    recorded_cache = cache_record.get("merged_cache", {})
    if (
        Path(recorded_cache.get("path", "")).resolve() != feature_cache
        or recorded_cache.get("bytes") != feature_cache.stat().st_size
        or recorded_cache.get("sha256") != sha256_file(feature_cache)
    ):
        raise SystemExit("feature cache differs from its evidence record")

    cases = CNN.merged_cases(manifests)
    signature = CNN.manifest_signature(manifests, cases)
    if cache_record.get("manifest_signature") != signature:
        raise SystemExit("cache record belongs to different manifests")
    domain_map, domain_rules = MERGER.load_domain_rules(domain_map_path)
    case_domain, domain_stats = MERGER.assign_domains(
        cases,
        domain_map,
        domain_rules,
    )
    recorded_domain_map = cache_record.get("domain_map", {})
    if (
        recorded_domain_map.get("map_id") != domain_map["map_id"]
        or recorded_domain_map.get("sha256")
        != sha256_file(domain_map_path)
        or recorded_domain_map.get("domain_stats") != domain_stats
    ):
        raise SystemExit("domain map differs from cache evidence")

    payload = torch.load(
        feature_cache,
        map_location="cpu",
        weights_only=False,
    )
    if (
        payload.get("schema_version") != 2
        or payload.get("manifest_signature") != signature
        or payload.get("feature_definition")
        != CNN.FEATURE_DEFINITION
        or payload.get("feature_definition_sha256")
        != CNN.FEATURE_DEFINITION_SHA256
        or payload.get("source_domain_map_id") != domain_map["map_id"]
        or payload.get("source_domain_map_sha256")
        != sha256_file(domain_map_path)
    ):
        raise SystemExit("feature cache contract differs")
    cases_by_id = {case["case_id"]: case for case in cases}
    normalized_metadata, cached_cases = (
        MERGER.validate_cache_metadata(
            cache=feature_cache,
            payload=payload,
            cases_by_id=cases_by_id,
            case_domain=case_domain,
        )
    )
    if cached_cases != set(cases_by_id):
        raise SystemExit("feature cache does not cover every case")
    metadata = payload["metadata"]
    if normalized_metadata != metadata:
        raise SystemExit("feature cache metadata is not normalized")
    features: torch.Tensor = payload["features"]
    device = CNN.choose_device(args.device)
    domains = [rule["domain_id"] for rule in domain_rules]
    print(
        f"training {args.representation}/{args.objective} on {device}; "
        f"normalization={args.normalization} "
        f"sampling={args.sampling} "
        f"domains={len(domains)} cases={len(cases)} clips={len(metadata)}",
        flush=True,
    )

    out_of_domain: dict[int, float] = {}
    rows = []
    fold_reports = []
    for fold, test_domain in enumerate(domains):
        train_groups, early_stop_groups, test_groups = (
            domain_holdout_split(
                metadata,
                test_domain,
                early_stop_group_fraction=(
                    args.early_stop_group_fraction
                ),
                early_stop_seed=args.early_stop_seed,
            )
        )
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
        test_indices = [
            index
            for index, item in enumerate(metadata)
            if item["partition_group"] in test_groups
        ]
        validation_probabilities, test_probabilities, report = (
            train_domain_fold(
                fold,
                test_domain,
                train_indices,
                early_stop_indices,
                test_indices,
                features=features,
                metadata=metadata,
                representation=args.representation,
                objective=args.objective,
                ranking_margin=args.ranking_margin,
                ranking_weight=args.ranking_weight,
                classification_weight=args.classification_weight,
                normalization=args.normalization,
                sampling=args.sampling,
                device=device,
                epochs=args.epochs,
                patience_limit=args.patience,
                batch_size=args.batch_size,
                seed=args.seed,
                mask_probability=args.mask_probability,
                level_shift_probability=(
                    args.level_shift_probability
                ),
                model_dir=model_dir,
            )
        )
        validation_rows = aggregate_case_scores(
            validation_probabilities,
            metadata,
        )
        validation_negatives = [
            row["lossy_probability_mean"]
            for row in validation_rows
            if row["expectation"] == "negative"
        ]
        if not validation_negatives:
            raise RuntimeError(
                f"{test_domain}: validation has no negative cases"
            )
        validation_boundary = max(validation_negatives)
        test_rows = aggregate_case_scores(
            test_probabilities,
            metadata,
        )
        for row in test_rows:
            row.update(
                {
                    "fold": fold + 1,
                    "validation_calibrated_boundary": (
                        validation_boundary
                    ),
                    "above_validation_calibrated_boundary": (
                        row["lossy_probability_mean"]
                        > validation_boundary
                    ),
                }
            )
        report.update(
            {
                "training_partition_group_count": len(
                    train_groups
                ),
                "inner_early_stop_partition_group_count": len(
                    early_stop_groups
                ),
                "outer_test_partition_group_count": len(test_groups),
                "inner_validation_case_count": len(validation_rows),
                "validation_calibrated_metrics": metric_summary(
                    test_rows,
                    validation_boundary,
                ),
            }
        )
        overlap = set(out_of_domain) & set(test_probabilities)
        if overlap:
            raise RuntimeError("a clip was scored by multiple folds")
        out_of_domain.update(test_probabilities)
        rows.extend(test_rows)
        fold_reports.append(report)
    if len(out_of_domain) != len(metadata) or len(rows) != len(cases):
        raise RuntimeError(
            "domain holdout did not score every clip and case exactly once"
        )

    negatives = [
        row["lossy_probability_mean"]
        for row in rows
        if row["expectation"] == "negative"
    ]
    diagnostic_boundary = max(negatives)
    diagnostic_metrics = metric_summary(rows, diagnostic_boundary)
    validation_calibrated_false_positives = sum(
        report["validation_calibrated_metrics"][
            "false_positive_count"
        ]
        for report in fold_reports
    )
    validation_calibrated_true_positives = sum(
        report["validation_calibrated_metrics"][
            "controlled_positives_above_boundary"
        ]
        for report in fold_reports
    )
    positive_count = sum(
        row["expectation"] == "controlled_positive" for row in rows
    )
    negative_count = len(rows) - positive_count
    class_summary = {}
    for class_name in sorted({row["class"] for row in rows}):
        selected = [
            row for row in rows if row["class"] == class_name
        ]
        values = [
            row["lossy_probability_mean"] for row in selected
        ]
        class_summary[class_name] = {
            "case_count": len(selected),
            "median": statistics.median(values),
            "minimum": min(values),
            "maximum": max(values),
            "above_fold_validation_boundary": sum(
                row["above_validation_calibrated_boundary"]
                for row in selected
            ),
        }

    report = {
        "schema_version": 1,
        "report_id": args.report_id,
        "disposition": {
            "state": "development_domain_generalization_research",
            "release_evidence": False,
            "public_verdict_enabled": False,
            "held_out_release_data_opened": False,
            "reason": (
                "All evaluated cases are development data. The merged cache "
                "was restored from verified archives without live audio "
                "fingerprint verification, and model selection remains "
                "ongoing."
            ),
        },
        "trainer_source_sha256": sha256_file(Path(__file__).resolve()),
        "baseline_training_library_sha256": sha256_file(
            TRAINING_SCRIPT
        ),
        "cache_merge_library_sha256": sha256_file(MERGE_SCRIPT),
        "manifest_signature": signature,
        "feature_cache": {
            "path": str(feature_cache),
            "bytes": feature_cache.stat().st_size,
            "sha256": sha256_file(feature_cache),
            "record": str(cache_record_path),
            "record_sha256": sha256_file(cache_record_path),
        },
        "feature_definition": CNN.FEATURE_DEFINITION,
        "feature_definition_sha256": (
            CNN.FEATURE_DEFINITION_SHA256
        ),
        "domain_map": {
            "path": str(domain_map_path),
            "sha256": sha256_file(domain_map_path),
            "map_id": domain_map["map_id"],
            "domain_stats": domain_stats,
        },
        "representation_id": args.representation,
        "representation": REPRESENTATIONS[args.representation],
        "representation_sha256": representation_sha256(
            args.representation
        ),
        "objective_id": args.objective,
        "objective": objective_definition(
            args.objective,
            ranking_margin=args.ranking_margin,
            ranking_weight=args.ranking_weight,
            classification_weight=args.classification_weight,
        ),
        "objective_sha256": sha256_json(
            objective_definition(
                args.objective,
                ranking_margin=args.ranking_margin,
                ranking_weight=args.ranking_weight,
                classification_weight=args.classification_weight,
            )
        ),
        "normalization_id": args.normalization,
        "normalization": NORMALIZATIONS[args.normalization],
        "normalization_sha256": sha256_json(
            NORMALIZATIONS[args.normalization]
        ),
        "sampling_id": args.sampling,
        "sampling": SAMPLING_STRATEGIES[args.sampling],
        "sampling_sha256": sha256_json(
            SAMPLING_STRATEGIES[args.sampling]
        ),
        "device": str(device),
        "torch_version": torch.__version__,
        "seed": args.seed,
        "early_stop_seed": args.early_stop_seed,
        "source_domain_count": len(domains),
        "case_count": len(rows),
        "clip_count": len(metadata),
        "augmentation": {
            "random_high_frequency_mask_probability": (
                args.mask_probability
            ),
            "random_high_frequency_mask_minimum_hz": 14_000,
            "below_28khz_sample_rate_mask_behavior": "no_op",
            "random_level_shift_probability": (
                args.level_shift_probability
            ),
        },
        "cross_validation": {
            "outer_group": "source_domain",
            "outer_fold_count": len(domains),
            "inner_early_stop_group": "partition_group",
            "inner_early_stop_stratified_by": "source_domain",
            "inner_early_stop_group_fraction": (
                args.early_stop_group_fraction
            ),
            "outer_test_labels_used_for_epoch_selection": False,
            "outer_test_labels_used_for_boundary_selection": False,
        },
        "metrics": {
            "validation_calibrated": {
                "false_positive_count": (
                    validation_calibrated_false_positives
                ),
                "negative_count": negative_count,
                "controlled_positives_above_boundary": (
                    validation_calibrated_true_positives
                ),
                "controlled_positive_count": positive_count,
                "controlled_positive_recall": (
                    validation_calibrated_true_positives
                    / positive_count
                ),
                "uses_one_independently_fitted_model_and_validation_boundary_per_fold": (
                    True
                ),
            },
            "combined_out_of_domain_diagnostic": {
                **diagnostic_metrics,
                "boundary_selected_after_combining_outer_test_labels": (
                    True
                ),
                "release_metric": False,
            },
        },
        "development_numeric_target": {
            "maximum_false_positive_count": 0,
            "minimum_controlled_positive_recall": 0.90,
            "passed_with_validation_calibrated_boundaries": (
                validation_calibrated_false_positives == 0
                and validation_calibrated_true_positives
                / positive_count
                >= 0.90
            ),
            "passing_does_not_authorize_release": True,
        },
        "by_class": class_summary,
        "folds": fold_reports,
        "results": sorted(rows, key=lambda row: row["case_id"]),
    }
    write_atomic(output, report)
    print(
        f"wrote domain-holdout report to {output}; "
        f"validation-calibrated FP={validation_calibrated_false_positives}/"
        f"{negative_count} TP={validation_calibrated_true_positives}/"
        f"{positive_count}",
        flush=True,
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--manifest",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument("--feature-cache", type=Path, required=True)
    result.add_argument(
        "--feature-cache-record",
        type=Path,
        required=True,
    )
    result.add_argument("--domain-map", type=Path, required=True)
    result.add_argument(
        "--representation",
        choices=sorted(REPRESENTATIONS),
        required=True,
    )
    result.add_argument(
        "--objective",
        choices=sorted(TRAINING_OBJECTIVES),
        default="binary_v1",
    )
    result.add_argument(
        "--normalization",
        choices=sorted(NORMALIZATIONS),
        default="batch_v1",
    )
    result.add_argument(
        "--sampling",
        choices=sorted(SAMPLING_STRATEGIES),
        default="natural_v1",
    )
    result.add_argument("--model-dir", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--report-id", required=True)
    result.add_argument("--epochs", type=int, default=20)
    result.add_argument("--patience", type=int, default=4)
    result.add_argument("--batch-size", type=int, default=32)
    result.add_argument("--seed", type=int, default=20260731)
    result.add_argument("--early-stop-seed", type=int, default=20260731)
    result.add_argument("--ranking-margin", type=float, default=1.0)
    result.add_argument("--ranking-weight", type=float, default=1.0)
    result.add_argument(
        "--classification-weight",
        type=float,
        default=0.25,
    )
    result.add_argument(
        "--early-stop-group-fraction",
        type=float,
        default=0.20,
    )
    result.add_argument("--mask-probability", type=float, default=0.70)
    result.add_argument(
        "--level-shift-probability",
        type=float,
        default=0.50,
    )
    result.add_argument("--device", default="auto")
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
