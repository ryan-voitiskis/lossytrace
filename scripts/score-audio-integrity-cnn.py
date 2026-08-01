#!/usr/bin/env python3
"""Score an untouched private corpus with previously trained fold models."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import torch

TRAINING_SCRIPT = Path(__file__).with_name("train-audio-integrity-cnn.py")


def load_training_module():
    spec = importlib.util.spec_from_file_location(
        "reklaw_audio_integrity_cnn_training",
        TRAINING_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load training implementation: {TRAINING_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CNN = load_training_module()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace score report: {path}")
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


def group_fold_mapping(report: dict, path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for row in report.get("results", []):
        source_group = row["source_group"]
        fold = row["fold"]
        previous = mapping.setdefault(source_group, fold)
        if previous != fold:
            raise SystemExit(
                f"{path}: source group {source_group} occurs in multiple folds"
            )
    if not mapping:
        raise SystemExit(f"{path}: model report contains no scored source groups")
    return mapping


def score_model_set(
    *,
    features: torch.Tensor,
    metadata: list[dict],
    group_fold: dict[str, int],
    model_dir: Path,
    device: torch.device,
    batch_size: int,
) -> dict[str, list[float]]:
    missing_groups = sorted(
        {item["source_group"] for item in metadata} - set(group_fold)
    )
    if missing_groups:
        raise SystemExit(
            "scoring corpus contains source groups absent from training folds: "
            f"{missing_groups[:5]}"
        )

    scores: dict[str, list[float]] = defaultdict(list)
    for fold in sorted(set(group_fold.values())):
        checkpoint = model_dir / f"fold-{fold}.pt"
        if not checkpoint.is_file():
            raise SystemExit(f"missing fold checkpoint: {checkpoint}")
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        model = CNN.LossyTraceCnn().to(device)
        model.load_state_dict(state)
        model.eval()
        indices = [
            index
            for index, item in enumerate(metadata)
            if group_fold[item["source_group"]] == fold
        ]
        with torch.no_grad():
            for start in range(0, len(indices), batch_size):
                batch_indices = indices[start : start + batch_size]
                batch = features[batch_indices].float().unsqueeze(1).to(device)
                probabilities = torch.sigmoid(model(batch)).cpu().tolist()
                for index, probability in zip(batch_indices, probabilities):
                    scores[metadata[index]["case_id"]].append(probability)
    return scores


def score_unseen_model_set(
    *,
    features: torch.Tensor,
    metadata: list[dict],
    folds: list[int],
    model_dir: Path,
    device: torch.device,
    batch_size: int,
) -> dict[str, list[float]]:
    scores: dict[str, list[float]] = defaultdict(list)
    all_indices = list(range(len(metadata)))
    for fold in folds:
        checkpoint = model_dir / f"fold-{fold}.pt"
        if not checkpoint.is_file():
            raise SystemExit(f"missing fold checkpoint: {checkpoint}")
        state = torch.load(
            checkpoint,
            map_location="cpu",
            weights_only=True,
        )
        model = CNN.LossyTraceCnn().to(device)
        model.load_state_dict(state)
        model.eval()
        with torch.no_grad():
            for start in range(0, len(all_indices), batch_size):
                indices = all_indices[start : start + batch_size]
                batch = features[indices].float().unsqueeze(1).to(device)
                probabilities = torch.sigmoid(model(batch)).cpu().tolist()
                for index, probability in zip(indices, probabilities):
                    scores[metadata[index]["case_id"]].append(probability)
    return scores


def auc(positives: list[float], negatives: list[float]) -> float:
    return sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    ) / (len(positives) * len(negatives))


def validate_cached_metadata_identity(payload: dict, cases: list[dict]) -> None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, list):
        raise SystemExit("legacy feature cache has no metadata list")
    expected = {case["case_id"]: case for case in cases}
    observed: dict[str, list[dict]] = defaultdict(list)
    for item in metadata:
        if not isinstance(item, dict) or not isinstance(
            item.get("case_id"),
            str,
        ):
            raise SystemExit("legacy feature cache contains invalid metadata")
        observed[item["case_id"]].append(item)
    if set(observed) != set(expected):
        raise SystemExit(
            "legacy feature cache metadata and manifests contain different "
            "case IDs"
        )
    expected_clip_indices = list(range(len(CNN.CLIP_FRACTIONS)))
    for case_id, case in expected.items():
        items = observed[case_id]
        clip_indices = [item.get("clip_index") for item in items]
        if any(not isinstance(index, int) for index in clip_indices) or (
            sorted(clip_indices) != expected_clip_indices
        ):
            raise SystemExit(
                f"{case_id}: legacy feature cache clip indices differ"
            )
        for item in items:
            for field, expected_value in (
                ("source_group", case["source_group"]),
                (
                    "partition_group",
                    case.get("partition_group", case["source_group"]),
                ),
                ("class", case["class"]),
                ("expectation", case["expectation"]),
            ):
                observed_value = (
                    item.get(field, item.get("source_group"))
                    if field == "partition_group"
                    else item.get(field)
                )
                if observed_value != expected_value:
                    raise SystemExit(
                        f"{case_id}: legacy feature cache {field} differs"
                    )


def command(args: argparse.Namespace) -> int:
    if len(args.model_report) != len(args.model_dir):
        raise SystemExit("--model-report and --model-dir counts must match")
    if not args.model_report:
        raise SystemExit("at least one model report and directory are required")
    fixed_thresholds = sorted(set(args.fixed_threshold or []))
    if any(
        not 0.0 <= threshold <= 1.0
        for threshold in fixed_thresholds
    ):
        raise SystemExit("--fixed-threshold must be between 0 and 1")

    cases = CNN.merged_cases(args.manifest)
    root = args.audio_root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"audio root is not a directory: {root}")
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace score report: {args.output}")
    if args.feature_cache.is_symlink():
        raise SystemExit(
            f"feature cache must not be a symlink: {args.feature_cache}"
        )
    signature = CNN.manifest_signature(args.manifest, cases)
    fingerprint_signature = (
        CNN.verify_audio_fingerprints(
            args.fingerprints,
            cases,
            [root],
        )
        if args.fingerprints
        else None
    )
    legacy_feature_cache_adopted = False
    legacy_manifest_signature_adopted = False
    if args.feature_cache.is_file():
        payload = torch.load(
            args.feature_cache,
            map_location="cpu",
            weights_only=False,
        )
        cached_manifest_signature = payload.get("manifest_signature")
        if cached_manifest_signature != signature:
            if not args.allow_legacy_feature_cache:
                raise SystemExit(
                    "feature cache belongs to a different manifest"
                )
            validate_cached_metadata_identity(payload, cases)
            legacy_feature_cache_adopted = True
            legacy_manifest_signature_adopted = True
        cached_definition = payload.get("feature_definition_sha256")
        if cached_definition != CNN.FEATURE_DEFINITION_SHA256:
            if cached_definition is None and args.allow_legacy_feature_cache:
                legacy_feature_cache_adopted = True
            else:
                raise SystemExit(
                    "feature cache belongs to a different or uncommitted "
                    "feature definition"
                )
    else:
        payload = CNN.prepare_features(
            cases,
            [root],
            signature=signature,
            cache=args.feature_cache,
        )
    features: torch.Tensor = payload["features"]
    metadata: list[dict] = payload["metadata"]
    if len(features) != len(metadata):
        raise SystemExit("feature cache shape mismatch")

    device = CNN.choose_device(args.device)
    model_set_scores = []
    model_set_records = []
    expected_mapping: dict[str, int] | None = None
    for report_path, model_dir in zip(args.model_report, args.model_dir):
        report_path = report_path.expanduser().resolve()
        model_dir = model_dir.expanduser().resolve()
        if report_path.is_symlink() or not report_path.is_file():
            raise SystemExit(
                f"model report is not a regular file: {report_path}"
            )
        if model_dir.is_symlink() or not model_dir.is_dir():
            raise SystemExit(
                f"model directory is not a regular directory: {model_dir}"
            )
        report = load_json(report_path)
        mapping = group_fold_mapping(report, report_path)
        if expected_mapping is None:
            expected_mapping = mapping
        elif mapping != expected_mapping:
            raise SystemExit(
                "model reports use different source-group fold assignments"
            )
        if args.unseen_source_policy == "ensemble-all-folds":
            overlap = sorted(
                {item["source_group"] for item in metadata}
                & set(mapping)
            )
            if overlap:
                raise SystemExit(
                    "ensemble-all-folds requires every scoring source group "
                    f"to be unseen; overlap begins with {overlap[:5]}"
                )
            scores = score_unseen_model_set(
                features=features,
                metadata=metadata,
                folds=sorted(set(mapping.values())),
                model_dir=model_dir,
                device=device,
                batch_size=args.batch_size,
            )
        else:
            scores = score_model_set(
                features=features,
                metadata=metadata,
                group_fold=mapping,
                model_dir=model_dir,
                device=device,
                batch_size=args.batch_size,
            )
        model_set_scores.append(scores)
        checkpoint_records = []
        for fold in sorted(set(mapping.values())):
            checkpoint = model_dir / f"fold-{fold}.pt"
            checkpoint_records.append(
                {
                    "fold": fold,
                    "bytes": checkpoint.stat().st_size,
                    "sha256": sha256_file(checkpoint),
                }
            )
        model_set_records.append(
            {
                "training_report": str(report_path),
                "training_report_sha256": sha256_file(report_path),
                "training_schema_version": report.get("schema_version"),
                "training_seed": report.get("seed"),
                "training_fold_seed": report.get("fold_seed"),
                "training_case_level_auc": report.get("metrics", {}).get(
                    "case_level_auc"
                ),
                "unseen_source_policy": args.unseen_source_policy,
                "checkpoints": checkpoint_records,
            }
        )

    case_metadata = {case["case_id"]: case for case in cases}
    rows = []
    for case_id in sorted(case_metadata):
        per_model_scores = [
            statistics.fmean(scores[case_id]) for scores in model_set_scores
        ]
        clip_counts = [len(scores[case_id]) for scores in model_set_scores]
        expected_clip_count = len(CNN.CLIP_FRACTIONS)
        if args.unseen_source_policy == "ensemble-all-folds":
            expected_clip_count *= len(set(expected_mapping.values()))
        if set(clip_counts) != {expected_clip_count}:
            raise RuntimeError(f"{case_id}: unexpected clip score count")
        case = case_metadata[case_id]
        rows.append(
            {
                "case_id": case_id,
                "source_group": case["source_group"],
                "class": case["class"],
                "expectation": case["expectation"],
                "fold": (
                    None
                    if args.unseen_source_policy == "ensemble-all-folds"
                    else expected_mapping[case["source_group"]]
                ),
                "clip_count_per_model": clip_counts[0],
                "model_scores": per_model_scores,
                "lossy_probability_mean": statistics.fmean(per_model_scores),
                "lossy_probability_minimum_model": min(per_model_scores),
                "lossy_probability_maximum_model": max(per_model_scores),
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
    if not negatives or not positives:
        raise SystemExit("scoring requires both negative and positive cases")
    zero_false_positive_boundary = max(negatives)
    by_class = {}
    for class_name in sorted({row["class"] for row in rows}):
        class_rows = [row for row in rows if row["class"] == class_name]
        values = [row["lossy_probability_mean"] for row in class_rows]
        by_class[class_name] = {
            "cases": len(values),
            "median": statistics.median(values),
            "minimum": min(values),
            "maximum": max(values),
            "above_fixed_model_floor_0_9": sum(value > 0.9 for value in values),
            "above_zero_false_positive_boundary": sum(
                value > zero_false_positive_boundary for value in values
            ),
        }

    fixed_threshold_evaluations = []
    for threshold in fixed_thresholds:
        selected = [
            row
            for row in rows
            if row["lossy_probability_mean"] > threshold
        ]
        false_positives = [
            row
            for row in selected
            if row["expectation"] == "negative"
        ]
        detected = [
            row
            for row in selected
            if row["expectation"] == "controlled_positive"
        ]
        fixed_threshold_evaluations.append(
            {
                "threshold": threshold,
                "comparison": "strictly_greater",
                "negative_count": len(negatives),
                "false_positive_count": len(false_positives),
                "false_positive_case_ids": sorted(
                    row["case_id"] for row in false_positives
                ),
                "controlled_positive_count": len(positives),
                "detected_positive_count": len(detected),
                "detected_by_class": dict(
                    sorted(
                        Counter(row["class"] for row in detected).items()
                    )
                ),
            }
        )

    write_atomic(
        args.output,
        {
            "schema_version": 1,
            "disposition": {
                "state": (
                    "external_development_evaluation"
                    if args.unseen_source_policy == "ensemble-all-folds"
                    else "development_settings_holdout"
                ),
                "held_out_source_groups": (
                    args.unseen_source_policy == "ensemble-all-folds"
                ),
                "thresholds_retuned": False,
                "models_retrained": False,
                "release_evidence": False,
                "public_verdict_enabled": False,
                "reason": (
                    "Previously trained fold models scored unseen development "
                    "source groups by averaging every fold model."
                    if args.unseen_source_policy == "ensemble-all-folds"
                    else (
                        "Codec settings were withheld from training, but the "
                        "source groups are reused Tier B development material."
                    )
                ),
            },
            "manifest_signature": signature,
            "fingerprint_signature": fingerprint_signature,
            "fingerprints_verified": bool(args.fingerprints),
            "feature_definition": CNN.FEATURE_DEFINITION,
            "feature_definition_sha256": (
                CNN.FEATURE_DEFINITION_SHA256
            ),
            "feature_cache_sha256": sha256_file(args.feature_cache),
            "legacy_feature_cache_adopted": legacy_feature_cache_adopted,
            "legacy_manifest_signature_adopted": (
                legacy_manifest_signature_adopted
            ),
            "cached_manifest_signature": payload.get(
                "manifest_signature"
            ),
            "device": str(device),
            "torch_version": torch.__version__,
            "numpy_version": CNN.np.__version__,
            "soundfile_version": CNN.sf.__version__,
            "model_sets": model_set_records,
            "source_group_count": len(
                {row["source_group"] for row in rows}
            ),
            "case_count": len(rows),
            "clip_fractions": CNN.CLIP_FRACTIONS,
            "metrics": {
                "case_level_auc": auc(positives, negatives),
                "zero_false_positive_boundary": zero_false_positive_boundary,
                "controlled_positives_above_boundary": sum(
                    value > zero_false_positive_boundary
                    for value in positives
                ),
                "controlled_positives_above_fixed_model_floor_0_9": sum(
                    value > 0.9 for value in positives
                ),
                "controlled_positive_count": len(positives),
                "negative_count": len(negatives),
            },
            "fixed_threshold_evaluations": fixed_threshold_evaluations,
            "by_class": by_class,
            "results": rows,
        },
    )
    label = (
        "unseen development scores"
        if args.unseen_source_policy == "ensemble-all-folds"
        else "settings-holdout scores"
    )
    print(f"wrote {label} to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, action="append", required=True)
    result.add_argument("--audio-root", type=Path, required=True)
    result.add_argument("--fingerprints", type=Path, action="append")
    result.add_argument("--feature-cache", type=Path, required=True)
    result.add_argument(
        "--allow-legacy-feature-cache",
        action="store_true",
        help=(
            "adopt an otherwise matching cache created before the feature "
            "definition commitment was stored"
        ),
    )
    result.add_argument("--model-report", type=Path, action="append", required=True)
    result.add_argument("--model-dir", type=Path, action="append", required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--batch-size", type=int, default=32)
    result.add_argument("--device", default="auto")
    result.add_argument(
        "--fixed-threshold",
        type=float,
        action="append",
        help=(
            "report a caller-supplied strict score threshold without "
            "calibrating it on this corpus"
        ),
    )
    result.add_argument(
        "--unseen-source-policy",
        choices=("refuse", "ensemble-all-folds"),
        default="refuse",
    )
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
