#!/usr/bin/env python3
"""Train naive or masked Koops-style CRNN baselines on v2 development."""

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

import audio_integrity_v2_baseline_common as common


SCHEMA_VERSION = 1
RUN_ID = "lossytrace-v2-crnn-baselines-20260802-001"
CONDITIONS = {"naive", "random_high_frequency_mask"}
TARGET_SAMPLE_RATE = 44_100
CLIP_SECONDS = 2
CLIP_SAMPLES = TARGET_SAMPLE_RATE * CLIP_SECONDS
N_FFT = 1_024
HOP_LENGTH = 512
CONV_CHANNELS = (16, 32, 64, 128)
POOL_SHAPES = ((2, 2), (2, 2), (2, 2), (2, 4))
LSTM_HIDDEN_SIZE = 128
LSTM_LAYERS = 2
LABELS = {"negative": 0, "controlled_positive": 1}
MODEL_DEFINITION = {
    "paper": "Koops, Micchi, and Quinton, ISMIR 2024",
    "reproduction_boundary": "paper_aligned_independent_not_exact",
    "input": {
        "target_sample_rate_hz": TARGET_SAMPLE_RATE,
        "mono_downmix": "arithmetic_channel_mean",
        "clip_seconds": CLIP_SECONDS,
        "training_crop": "one_deterministic_random_crop_per_unique_pcm_per_epoch",
        "evaluation_windows": "two_seconds_with_50_percent_overlap",
        "track_aggregation": "arithmetic_mean_softmax_lossy_score",
    },
    "spectrogram": {
        "n_fft": N_FFT,
        "win_length": N_FFT,
        "hop_length": HOP_LENGTH,
        "window": "hann",
        "center": True,
        "pad_mode": "reflect",
        "power": 1.0,
        "normalized": False,
        "post_transform": "log1p_then_per_example_standardize",
    },
    "random_high_frequency_mask": {
        "training_probability_when_enabled": 1.0,
        "cutoff_distribution_hz": [14_000.0, TARGET_SAMPLE_RATE / 2],
        "masked_value": "per_example_standardized_minimum",
        "validation_and_evaluation": False,
    },
    "convolution": {
        "channels": CONV_CHANNELS,
        "kernel": [3, 3],
        "padding": [1, 1],
        "bias": False,
        "operation_order": ["convolution", "relu", "batch_norm", "max_pool"],
        "pool_shapes": POOL_SHAPES,
    },
    "sequence": {
        "kind": "bidirectional_lstm",
        "layers": LSTM_LAYERS,
        "hidden_size": LSTM_HIDDEN_SIZE,
        "input_axis": "post_cnn_time",
    },
    "classification": {
        "outputs": 2,
        "training_loss": "cross_entropy_equivalent_to_two_class_softmax_nll",
        "lossy_score": "softmax_output_1",
        "fixed_classification_boundary": 0.5,
    },
}
MODEL_DEFINITION_SHA256 = common.canonical_sha256(
    b"lossytrace-v2-crnn-model\0", MODEL_DEFINITION
)


def stable_hash_int(*values: object) -> int:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode())
        digest.update(b"\0")
    return int.from_bytes(digest.digest()[:8], "big")


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
            "CRNN baseline requires the pinned numpy, soundfile, torch, and "
            "torchaudio environment"
        ) from error
    return np, sf, torch, torchaudio, nn, DataLoader, Dataset


def validate_plan(
    plan: dict[str, Any],
    *,
    condition: str,
    paths: dict[str, Path],
) -> dict[str, str]:
    if (
        plan.get("schema_version") != 1
        or plan.get("plan_id") != common.PLAN_ID
        or plan.get("state")
        != "mechanism_development_baselines_frozen_before_waveform_decode"
        or plan.get("authorized_evidence_partition") != common.MECHANISM_PARTITION
        or plan.get("encoder_transfer_scores_opened") is not False
        or plan.get("external_transfer_scores_opened") is not False
        or plan.get("public_verdict_enabled") is not False
        or condition not in CONDITIONS
    ):
        raise ValueError("development-baseline plan state differs")
    bindings = plan.get("bindings", {})
    hashes = {"plan_sha256": common.sha256_file(paths["plan"])}
    for path_key, binding_key, label in (
        ("manifest", "private_analysis_manifest_sha256", "analysis manifest"),
        (
            "constructor",
            "private_constructor_manifest_sha256",
            "constructor manifest",
        ),
        ("runner", "crnn_runner_sha256", "CRNN runner"),
        ("requirements", "crnn_requirements_sha256", "CRNN requirements"),
        ("common", "common_module_sha256", "baseline common module"),
    ):
        path = paths[path_key]
        if not path.is_file():
            raise ValueError(f"{label} is absent")
        digest = common.sha256_file(path)
        if bindings.get(binding_key) != digest:
            raise ValueError(f"{label} binding differs")
        hashes[f"{path_key}_sha256"] = digest
    configuration = plan.get("baselines", {}).get("koops_style_crnn_replication", {})
    if (
        configuration.get("conditions") != [
            "naive",
            "random_high_frequency_mask",
        ]
        or configuration.get("model_definition_sha256") != MODEL_DEFINITION_SHA256
        or configuration.get("outer_folds") != sorted(common.EXPECTED_DOMAINS)
        or configuration.get("inner_validation_group_fraction") != 0.2
        or configuration.get("optimizer") != "adam"
        or configuration.get("learning_rate") != 0.001
        or configuration.get("batch_size") != 32
        or configuration.get("maximum_epochs") != 30
        or configuration.get("early_stopping_patience") != 5
        or configuration.get("fixed_boundary") != 0.5
        or configuration.get("device") != "cpu"
        or configuration.get("seed") != 20260802
        or configuration.get("training_population")
        != "one_canonical_case_per_unique_analysis_pcm"
    ):
        raise ValueError("CRNN frozen configuration differs")
    return hashes


def inner_validation_groups(
    cases: list[dict[str, Any]], outer_domain: str, seed: int
) -> set[str]:
    groups_by_domain: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        if case["source_domain"] != outer_domain:
            groups_by_domain[case["source_domain"]].add(case["partition_group"])
    validation: set[str] = set()
    for domain, groups in sorted(groups_by_domain.items()):
        ordered = sorted(
            groups,
            key=lambda group: (
                stable_hash_int(seed, outer_domain, domain, group),
                group,
            ),
        )
        count = min(len(ordered) - 1, max(1, round(len(ordered) * 0.2)))
        if count < 1:
            raise ValueError(f"domain cannot supply grouped validation: {domain}")
        validation.update(ordered[:count])
    return validation


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
                probe = self._cnn_features(torch.zeros(1, CLIP_SAMPLES), False)
            _, channels, frequency, _ = probe.shape
            self.lstm = nn.LSTM(
                input_size=channels * frequency,
                hidden_size=LSTM_HIDDEN_SIZE,
                num_layers=LSTM_LAYERS,
                batch_first=True,
                bidirectional=True,
            )
            self.classifier = nn.Linear(2 * LSTM_HIDDEN_SIZE, 2)

        def _cnn_features(self, waveforms, apply_mask: bool):
            features = torch.log1p(self.spectrogram(waveforms))
            mean = features.mean(dim=(-2, -1), keepdim=True)
            spread = features.std(
                dim=(-2, -1), keepdim=True, unbiased=False
            ).clamp_min(1.0e-6)
            features = (features - mean) / spread
            if apply_mask:
                batch = features.shape[0]
                cutoffs = 14_000.0 + torch.rand(
                    batch, 1, 1, device=features.device
                ) * (TARGET_SAMPLE_RATE / 2.0 - 14_000.0)
                frequencies = torch.linspace(
                    0.0,
                    TARGET_SAMPLE_RATE / 2.0,
                    features.shape[-2],
                    device=features.device,
                ).view(1, -1, 1)
                minimum = features.amin(dim=(-2, -1), keepdim=True)
                features = torch.where(frequencies > cutoffs, minimum, features)
            return self.blocks(features.unsqueeze(1))

        def forward(self, waveforms, apply_mask: bool = False):
            features = self._cnn_features(waveforms, apply_mask)
            sequence = features.permute(0, 3, 1, 2).flatten(start_dim=2)
            _, (hidden, _) = self.lstm(sequence)
            return self.classifier(torch.cat((hidden[-2], hidden[-1]), dim=1))

    return LossyHistoryCrnn()


def crop_fraction(seed: int, epoch: int, case_id: str) -> float:
    return stable_hash_int(seed, "crop", epoch, case_id) / float(2**64 - 1)


def read_crop(
    case: dict[str, Any],
    root: Path,
    fraction: float,
    *,
    start_frame: int | None,
    np,
    sf,
    torch,
    torchaudio,
):
    path = common.resolve_beneath(root, case["relative_path"])
    with sf.SoundFile(path) as audio:
        sample_rate = int(audio.samplerate)
        source_length = round(CLIP_SECONDS * sample_rate)
        maximum_start = max(0, int(audio.frames) - source_length)
        start = (
            min(maximum_start, math.floor(maximum_start * fraction))
            if start_frame is None
            else start_frame
        )
        if not 0 <= start <= maximum_start:
            raise ValueError(f"invalid CRNN crop: {case['case_id']}")
        audio.seek(start)
        samples = audio.read(source_length, dtype="float32", always_2d=True)
    if len(samples) < source_length:
        samples = np.pad(samples, ((0, source_length - len(samples)), (0, 0)))
    mono = torch.from_numpy(samples.mean(axis=1)).reshape(1, -1)
    if sample_rate != TARGET_SAMPLE_RATE:
        mono = torchaudio.functional.resample(mono, sample_rate, TARGET_SAMPLE_RATE)
    mono = mono.flatten()
    if mono.numel() < CLIP_SAMPLES:
        mono = torch.nn.functional.pad(mono, (0, CLIP_SAMPLES - mono.numel()))
    return mono[:CLIP_SAMPLES].contiguous()


def make_dataset_class(Dataset):
    class TrainingDataset(Dataset):
        def __init__(self, cases, root, seed, epoch, np, sf, torch, torchaudio):
            self.cases = cases
            self.root = root
            self.seed = seed
            self.epoch = epoch
            self.np = np
            self.sf = sf
            self.torch = torch
            self.torchaudio = torchaudio

        def __len__(self):
            return len(self.cases)

        def __getitem__(self, index):
            case = self.cases[index]
            waveform = read_crop(
                case,
                self.root,
                crop_fraction(self.seed, self.epoch, case["case_id"]),
                start_frame=None,
                np=self.np,
                sf=self.sf,
                torch=self.torch,
                torchaudio=self.torchaudio,
            )
            return waveform, LABELS[case["expectation"]]

    return TrainingDataset


def window_starts(frame_count: int, sample_rate: int) -> list[int]:
    window = round(CLIP_SECONDS * sample_rate)
    if frame_count <= window:
        return [0]
    return list(range(0, frame_count - window + 1, sample_rate))


def score_cases(
    model,
    cases: list[dict[str, Any]],
    root: Path,
    *,
    batch_size: int,
    np,
    sf,
    torch,
    torchaudio,
) -> list[dict[str, Any]]:
    model.eval()
    results = []
    with torch.no_grad():
        for index, case in enumerate(cases, 1):
            path = common.resolve_beneath(root, case["relative_path"])
            info = sf.info(path)
            starts = window_starts(int(info.frames), int(info.samplerate))
            probabilities: list[float] = []
            for offset in range(0, len(starts), batch_size):
                batch = torch.stack(
                    [
                        read_crop(
                            case,
                            root,
                            0.0,
                            start_frame=start,
                            np=np,
                            sf=sf,
                            torch=torch,
                            torchaudio=torchaudio,
                        )
                        for start in starts[offset : offset + batch_size]
                    ]
                )
                logits = model(batch, apply_mask=False)
                probabilities.extend(torch.softmax(logits, dim=1)[:, 1].tolist())
            score = sum(probabilities) / len(probabilities)
            if not math.isfinite(score) or not 0.0 <= score <= 1.0:
                raise ValueError(f"non-finite CRNN score: {case['case_id']}")
            results.append(
                {
                    "case_id": case["case_id"],
                    "audio_sha256": case["audio_sha256"],
                    "analysis_pcm_sha256": case["_analysis_pcm_sha256"],
                    "lossless_wrapper_id": case["lossless_wrapper_id"],
                    "window_count": len(probabilities),
                    "score": score,
                }
            )
            if index % 100 == 0 or index == len(cases):
                print(f"    [score {index:04d}/{len(cases):04d}]")
    return results


def auc(scores: list[float], labels: list[int]) -> float:
    positives = [score for score, label in zip(scores, labels, strict=True) if label]
    negatives = [score for score, label in zip(scores, labels, strict=True) if not label]
    if not positives or not negatives:
        raise ValueError("AUC requires both labels")
    wins = sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    )
    return wins / (len(positives) * len(negatives))


def log_loss(scores: list[float], labels: list[int]) -> float:
    epsilon = 1.0e-7
    return sum(
        -label * math.log(min(1.0 - epsilon, max(epsilon, score)))
        - (1 - label) * math.log(
            min(1.0 - epsilon, max(epsilon, 1.0 - score))
        )
        for score, label in zip(scores, labels, strict=True)
    ) / len(scores)


def score_metrics(
    rows: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    scores = [row["score"] for row in rows]
    labels = [LABELS[by_id[row["case_id"]]["expectation"]] for row in rows]
    predictions = [score >= 0.5 for score in scores]
    positive = sum(labels)
    negative = len(labels) - positive
    tp = sum(prediction and label for prediction, label in zip(predictions, labels))
    fp = sum(prediction and not label for prediction, label in zip(predictions, labels))
    return {
        "case_count": len(rows),
        "controlled_positive_count": positive,
        "negative_count": negative,
        "true_positive_count": tp,
        "false_negative_count": positive - tp,
        "false_positive_count": fp,
        "true_negative_count": negative - fp,
        "recall_at_fixed_0_5": tp / positive if positive else None,
        "false_positive_rate_at_fixed_0_5": fp / negative if negative else None,
        "auc": auc(scores, labels),
        "log_loss": log_loss(scores, labels),
    }


def save_checkpoint(torch, path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temporary)
    temporary.replace(path)


def load_finished_fold(
    path: Path, fold_binding_sha256: str
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = common.load_object(path)
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("fold_binding_sha256") != fold_binding_sha256
        or not isinstance(value.get("artifact_scores"), list)
    ):
        raise ValueError(f"completed fold binding differs: {path.name}")
    return value


def run_fold(
    *,
    condition: str,
    outer_domain: str,
    canonical_cases: list[dict[str, Any]],
    artifact_cases: list[dict[str, Any]],
    all_cases_by_id: dict[str, dict[str, Any]],
    root: Path,
    output_directory: Path,
    run_binding_sha256: str,
    np,
    sf,
    torch,
    torchaudio,
    nn,
    DataLoader,
    Dataset,
) -> dict[str, Any]:
    fold_binding = {
        "run_binding_sha256": run_binding_sha256,
        "condition": condition,
        "outer_domain": outer_domain,
        "model_definition_sha256": MODEL_DEFINITION_SHA256,
    }
    fold_binding_sha256 = common.canonical_sha256(
        b"lossytrace-v2-crnn-fold\0", fold_binding
    )
    fold_path = output_directory / "fold-results" / f"{outer_domain}.json"
    finished = load_finished_fold(fold_path, fold_binding_sha256)
    if finished is not None:
        print(f"[fold {outer_domain}] resumed completed fold")
        return finished

    validation_groups = inner_validation_groups(canonical_cases, outer_domain, 20260802)
    outer_canonical = [
        row for row in canonical_cases if row["source_domain"] == outer_domain
    ]
    validation = [
        row
        for row in canonical_cases
        if row["source_domain"] != outer_domain
        and row["partition_group"] in validation_groups
    ]
    training = [
        row
        for row in canonical_cases
        if row["source_domain"] != outer_domain
        and row["partition_group"] not in validation_groups
    ]
    outer_artifacts = [
        row for row in artifact_cases if row["source_domain"] == outer_domain
    ]
    group_sets = [
        {row["partition_group"] for row in selected}
        for selected in (training, validation, outer_canonical)
    ]
    if any(group_sets[i] & group_sets[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError("CRNN fold partition groups overlap")

    fold_seed = stable_hash_int(20260802, outer_domain) % (2**31)
    random.seed(fold_seed)
    np.random.seed(fold_seed)
    torch.manual_seed(fold_seed)
    model = build_model(torch, torchaudio, nn)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()
    TrainingDataset = make_dataset_class(Dataset)
    checkpoint_path = output_directory / "checkpoints" / f"{outer_domain}.pt"
    best_selection: tuple[float, float] | None = None
    best_epoch = 0
    no_improvement = 0
    epoch_reports = []
    print(
        f"[fold {outer_domain}] train={len(training)} validation={len(validation)} "
        f"outer_pcm={len(outer_canonical)} outer_artifacts={len(outer_artifacts)}"
    )
    for epoch in range(1, 31):
        ordered = sorted(
            training,
            key=lambda row: (
                stable_hash_int(fold_seed, "epoch", epoch, row["case_id"]),
                row["case_id"],
            ),
        )
        dataset = TrainingDataset(
            ordered, root, fold_seed, epoch, np, sf, torch, torchaudio
        )
        loader = DataLoader(
            dataset, batch_size=32, shuffle=False, num_workers=0
        )
        model.train()
        total_loss = 0.0
        count = 0
        for waveforms, labels in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(
                waveforms,
                apply_mask=condition == "random_high_frequency_mask",
            )
            loss = criterion(logits, labels)
            if not torch.isfinite(loss):
                raise ValueError(f"non-finite CRNN training loss: {outer_domain}")
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(labels)
            count += len(labels)
        validation_scores = score_cases(
            model,
            validation,
            root,
            batch_size=32,
            np=np,
            sf=sf,
            torch=torch,
            torchaudio=torchaudio,
        )
        metrics = score_metrics(validation_scores, all_cases_by_id)
        selection = (-metrics["log_loss"], metrics["auc"])
        improved = best_selection is None or selection > best_selection
        epoch_reports.append(
            {
                "epoch": epoch,
                "training_loss": total_loss / count,
                "validation": metrics,
                "selected": improved,
            }
        )
        print(
            f"[fold {outer_domain} epoch {epoch:02d}] "
            f"loss={total_loss / count:.6f} val_log_loss={metrics['log_loss']:.6f} "
            f"val_auc={metrics['auc']:.6f} selected={improved}"
        )
        if improved:
            best_selection = selection
            best_epoch = epoch
            no_improvement = 0
            save_checkpoint(
                torch,
                checkpoint_path,
                {
                    "fold_binding_sha256": fold_binding_sha256,
                    "epoch": epoch,
                    "model_state": model.state_dict(),
                },
            )
        else:
            no_improvement += 1
            if no_improvement >= 5:
                break

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if (
        checkpoint.get("fold_binding_sha256") != fold_binding_sha256
        or checkpoint.get("epoch") != best_epoch
    ):
        raise ValueError("CRNN checkpoint binding differs")
    model.load_state_dict(checkpoint["model_state"])
    artifact_scores = score_cases(
        model,
        outer_artifacts,
        root,
        batch_size=32,
        np=np,
        sf=sf,
        torch=torch,
        torchaudio=torchaudio,
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "fold_binding": fold_binding,
        "fold_binding_sha256": fold_binding_sha256,
        "outer_domain": outer_domain,
        "training_unique_pcm_count": len(training),
        "validation_unique_pcm_count": len(validation),
        "outer_unique_pcm_count": len(outer_canonical),
        "outer_artifact_count": len(outer_artifacts),
        "training_label_counts": {
            name: sum(row["expectation"] == name for row in training)
            for name in sorted(LABELS)
        },
        "validation_label_counts": {
            name: sum(row["expectation"] == name for row in validation)
            for name in sorted(LABELS)
        },
        "parameter_count": parameter_count,
        "best_epoch": best_epoch,
        "epochs": epoch_reports,
        "checkpoint_sha256": common.sha256_file(checkpoint_path),
        "artifact_scores": artifact_scores,
    }
    common.write_new(fold_path, result)
    return result


def assert_artifact_integrity(cases: list[dict[str, Any]], root: Path) -> None:
    for index, case in enumerate(cases, 1):
        path = common.resolve_beneath(root, case["relative_path"])
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"CRNN artifact is absent or unsafe: {case['case_id']}")
        if common.sha256_file(path) != case["audio_sha256"]:
            raise ValueError(f"CRNN artifact hash differs: {case['case_id']}")
        if index % 250 == 0 or index == len(cases):
            print(f"[artifact {index:04d}/{len(cases):04d}]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--constructor-manifest", required=True, type=Path)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    np, sf, torch, torchaudio, nn, DataLoader, Dataset = import_ml_stack()
    paths = {
        "plan": args.plan.expanduser().resolve(),
        "manifest": args.manifest.expanduser().resolve(),
        "constructor": args.constructor_manifest.expanduser().resolve(),
        "runner": Path(__file__).resolve(),
        "requirements": args.requirements.expanduser().resolve(),
        "common": Path(common.__file__).resolve(),
    }
    root = args.audio_root.expanduser().resolve()
    output_directory = args.output_directory.expanduser().resolve()
    try:
        plan = common.load_object(paths["plan"])
        input_hashes = validate_plan(
            plan, condition=args.condition, paths=paths
        )
        if (
            str(torch.__version__) != "2.8.0"
            or str(torchaudio.__version__) != "2.8.0"
            or str(np.__version__) != "2.3.2"
            or str(sf.__version__) != "0.13.1"
        ):
            raise ValueError("CRNN runtime package versions differ")
        if not root.is_dir() or root.is_symlink():
            raise ValueError("benchmark audio root is absent or unsafe")
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        cases = common.load_development_cases(
            common.load_object(paths["manifest"]),
            common.load_object(paths["constructor"]),
        )
        canonical_cases = common.representatives_by_pcm(cases)
        artifact_cases = common.representatives_by_pcm_and_wrapper(cases)
        assert_artifact_integrity(artifact_cases, root)
        run_binding = {
            "run_id": RUN_ID,
            "condition": args.condition,
            "input_hashes": input_hashes,
            "model_definition_sha256": MODEL_DEFINITION_SHA256,
            "runtime": {
                "python": os.sys.version,
                "numpy": np.__version__,
                "soundfile": sf.__version__,
                "torch": torch.__version__,
                "torchaudio": torchaudio.__version__,
                "device": "cpu",
                "torch_threads": 1,
                "deterministic_algorithms": True,
            },
        }
        run_binding_sha256 = common.canonical_sha256(
            b"lossytrace-v2-crnn-run\0", run_binding
        )
        by_id = {row["case_id"]: row for row in cases}
        folds = [
            run_fold(
                condition=args.condition,
                outer_domain=domain,
                canonical_cases=canonical_cases,
                artifact_cases=artifact_cases,
                all_cases_by_id=by_id,
                root=root,
                output_directory=output_directory,
                run_binding_sha256=run_binding_sha256,
                np=np,
                sf=sf,
                torch=torch,
                torchaudio=torchaudio,
                nn=nn,
                DataLoader=DataLoader,
                Dataset=Dataset,
            )
            for domain in sorted(common.EXPECTED_DOMAINS)
        ]
        artifact_scores = [row for fold in folds for row in fold["artifact_scores"]]
        if len(artifact_scores) != common.EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT:
            raise ValueError("CRNN artifact-score population differs")
        by_audio = {row["audio_sha256"]: row for row in artifact_scores}
        if len(by_audio) != len(artifact_scores):
            raise ValueError("CRNN artifact scores are not unique")
        by_pcm: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in artifact_scores:
            by_pcm[row["analysis_pcm_sha256"]].append(row)
        multi_wrapper = 0
        for pcm_sha256, rows in by_pcm.items():
            if len({row["lossless_wrapper_id"] for row in rows}) < 2:
                continue
            multi_wrapper += 1
            values = {(row["window_count"], row["score"]) for row in rows}
            if len(values) != 1:
                raise ValueError(f"CRNN wrapper invariance failed: {pcm_sha256}")
        case_scores = []
        for case in cases:
            score = by_audio[case["audio_sha256"]]
            case_scores.append(
                {
                    "case_id": case["case_id"],
                    "reference_case_id": case.get("reference_case_id"),
                    "source_group": case["source_group"],
                    "partition_group": case["partition_group"],
                    "source_domain": case["source_domain"],
                    "expectation": case["expectation"],
                    "history_class": case["history_class"],
                    "codec_family": case.get("codec_family"),
                    "encoder_lineage_id": case.get("encoder_lineage_id"),
                    "encoder_setting_id": case.get("encoder_setting_id"),
                    "post_transform_ids": case.get("post_transform_ids", []),
                    "lossless_wrapper_id": case["lossless_wrapper_id"],
                    "audio_sha256": case["audio_sha256"],
                    "analysis_pcm_sha256": case["_analysis_pcm_sha256"],
                    "window_count": score["window_count"],
                    "score": score["score"],
                }
            )
        report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": RUN_ID,
            "plan_id": common.PLAN_ID,
            "state": "mechanism_development_crnn_private_result",
            "condition": args.condition,
            "evidence_partition": common.MECHANISM_PARTITION,
            "independent_validation": False,
            "feature_version": 0,
            "scores_opened": True,
            "encoder_transfer_scores_opened": False,
            "external_transfer_scores_opened": False,
            "public_verdict_enabled": False,
            "thresholds_retuned": False,
            "run_binding": run_binding,
            "run_binding_sha256": run_binding_sha256,
            "model_definition": MODEL_DEFINITION,
            "model_definition_sha256": MODEL_DEFINITION_SHA256,
            "wrapper_invariance": {
                "unique_analysis_pcm_count": len(by_pcm),
                "multi_wrapper_pcm_count": multi_wrapper,
                "pcm_wrapper_representative_count": len(artifact_scores),
                "exact_wrapper_invariance_passed": True,
            },
            "folds": folds,
            "case_scores": case_scores,
        }
        common.write_new(args.output.expanduser().resolve(), report)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"completed {args.condition} CRNN across six development domains; "
        "encoder and external transfer remain sealed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
