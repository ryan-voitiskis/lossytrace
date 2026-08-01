#!/usr/bin/env python3
"""Train once on broad disjoint sources and evaluate a frozen transfer set."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


BASE_SCRIPT = (
    Path(__file__).resolve().parent
    / "train-audio-integrity-source-paired-crnn.py"
)
BASE_SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_source_paired_base",
    BASE_SCRIPT,
)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError(f"could not load paired CRNN base: {BASE_SCRIPT}")
BASE = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)

TRAINING_DOMAINS = {
    "dev-": "tier_b_private_full_mix",
    "tier-b-nsynth-train-instrument-": "tier_b_nsynth_train",
}
EXPECTED_TRANSFER_DOMAINS = {
    "tier_a_choralebricks",
    "tier_a_groove",
    "tier_a_guitarset",
    "tier_a_vocalset",
    "tier_b_nsynth",
}


def training_domain(source_group: str) -> str:
    matches = [
        domain
        for prefix, domain in TRAINING_DOMAINS.items()
        if source_group.startswith(prefix)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"training source group has no unambiguous domain: {source_group}"
        )
    return matches[0]


def load_training_cases(
    manifests: list[Path],
    audio_roots: list[Path],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        for source_case in BASE.load_json(manifest).get("cases", []):
            case = dict(source_case)
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise SystemExit(f"{manifest}: case has no valid case_id")
            previous = by_id.setdefault(case_id, case)
            if previous != case:
                raise SystemExit(f"conflicting training case: {case_id}")
    cases = sorted(by_id.values(), key=lambda item: item["case_id"])
    if not cases:
        raise SystemExit("training manifests contain no cases")
    for case in cases:
        case_id = case["case_id"]
        if case.get("split") != "development":
            raise SystemExit(f"{case_id}: training case is not development")
        expectation = case.get("expectation")
        if expectation not in BASE.CLASS_TO_LABEL:
            raise SystemExit(f"{case_id}: unsupported training expectation")
        source_group = case.get("source_group")
        partition_group = case.get("partition_group", source_group)
        if not isinstance(source_group, str) or not source_group:
            raise SystemExit(f"{case_id}: missing training source_group")
        if partition_group != source_group:
            raise SystemExit(
                f"{case_id}: training partition_group must equal source_group"
            )
        relative_path = case.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            raise SystemExit(f"{case_id}: missing training relative_path")
        if not relative_path.startswith("generated/"):
            raise SystemExit(
                f"{case_id}: compact training audio must be under generated/"
            )
        case["partition_group"] = partition_group
        case["_audio_path"] = str(
            BASE.resolve_across_roots(audio_roots, relative_path)
        )
        case["_label"] = BASE.CLASS_TO_LABEL[expectation]
        case["_training_domain"] = training_domain(source_group)
    return cases


def validate_training_counts(
    cases: list[dict[str, Any]],
    *,
    expected_groups: int,
    expected_cases: int,
    expected_negatives: int,
    expected_positives: int,
    expected_pairs: int,
    seed: int,
) -> dict[str, Any]:
    groups = {case["partition_group"] for case in cases}
    observed = (
        len(groups),
        len(cases),
        sum(case["_label"] == 0 for case in cases),
        sum(case["_label"] == 1 for case in cases),
    )
    expected = (
        expected_groups,
        expected_cases,
        expected_negatives,
        expected_positives,
    )
    if observed != expected:
        raise SystemExit(
            "training groups/cases/negatives/positives differ: "
            f"observed={observed} expected={expected}"
        )
    pairs = BASE.source_paired_epoch_plan(cases, seed, 1)
    if len(pairs) != expected_pairs:
        raise SystemExit(
            f"training pair count differs: {len(pairs)} != {expected_pairs}"
        )
    by_domain = {}
    for domain in sorted({case["_training_domain"] for case in cases}):
        selected = [
            case for case in cases if case["_training_domain"] == domain
        ]
        by_domain[domain] = {
            "case_count": len(selected),
            "source_group_count": len(
                {case["partition_group"] for case in selected}
            ),
            "negative_count": sum(case["_label"] == 0 for case in selected),
            "controlled_positive_count": sum(
                case["_label"] == 1 for case in selected
            ),
        }
    if set(by_domain) != set(TRAINING_DOMAINS.values()):
        raise SystemExit(f"training domain set differs: {sorted(by_domain)}")
    return {
        "case_count": len(cases),
        "source_group_count": len(groups),
        "negative_count": observed[2],
        "controlled_positive_count": observed[3],
        "source_pair_count_per_complete_epoch": len(pairs),
        "domains": by_domain,
    }


def validation_groups(
    cases: list[dict[str, Any]],
    seed: int,
    fraction: float = 0.2,
) -> set[str]:
    groups_by_domain: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        groups_by_domain[case["_training_domain"]].add(
            case["partition_group"]
        )
    result = set()
    for domain, groups in sorted(groups_by_domain.items()):
        ordered = sorted(
            groups,
            key=lambda group: (
                BASE.stable_hash_int(seed, "broad-validation", domain, group),
                group,
            ),
        )
        count = max(1, round(len(ordered) * fraction))
        count = min(count, len(ordered) - 1)
        if count < 1:
            raise SystemExit(f"{domain}: not enough training groups")
        result.update(ordered[:count])
    return result


def metrics_by_training_domain(
    results: list[dict[str, Any]],
    boundary: float,
) -> dict[str, dict[str, Any]]:
    return {
        domain: BASE.report_metrics(
            [
                result
                for result in results
                if result["_training_domain"] == domain
            ],
            boundary,
        )
        for domain in sorted(
            {result["_training_domain"] for result in results}
        )
    }


def score_training_cases(
    model,
    cases,
    **kwargs,
) -> list[dict[str, Any]]:
    scoring_cases = [
        {
            **case,
            "_domain": case["_training_domain"],
        }
        for case in cases
    ]
    results = BASE.score_cases(model, scoring_cases, **kwargs)
    domain_by_id = {
        case["case_id"]: case["_training_domain"] for case in cases
    }
    for result in results:
        result["_training_domain"] = domain_by_id[result["case_id"]]
    return results


def validate_inputs(args) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    training_cases = load_training_cases(
        args.training_manifest,
        args.training_audio_root,
    )
    training_validation = validate_training_counts(
        training_cases,
        expected_groups=args.expected_training_groups,
        expected_cases=args.expected_training_cases,
        expected_negatives=args.expected_training_negatives,
        expected_positives=args.expected_training_positives,
        expected_pairs=args.expected_training_pairs,
        seed=args.seed,
    )
    training_fingerprint_commitment = BASE.verify_fingerprints(
        args.training_fingerprints,
        training_cases,
    )
    transfer_domain_map = BASE.load_json(args.transfer_domain_map)
    transfer_cases = BASE.merged_cases(
        args.transfer_manifest,
        args.transfer_audio_root,
        transfer_domain_map,
    )
    transfer_fingerprint_commitment = BASE.verify_fingerprints(
        args.transfer_fingerprints,
        transfer_cases,
    )
    transfer_groups = {case["partition_group"] for case in transfer_cases}
    training_groups = {case["partition_group"] for case in training_cases}
    overlap = sorted(training_groups & transfer_groups)
    if overlap:
        raise SystemExit(
            f"training and transfer source groups overlap: {overlap[:3]}"
        )
    transfer_domains = {case["_domain"] for case in transfer_cases}
    if transfer_domains != EXPECTED_TRANSFER_DOMAINS:
        raise SystemExit(
            f"transfer domain set differs: {sorted(transfer_domains)}"
        )
    validation = {
        "training": {
            **training_validation,
            "manifest_commitment": BASE.manifest_commitment(
                args.training_manifest
            ),
            "fingerprint_commitment": training_fingerprint_commitment,
        },
        "transfer": {
            "case_count": len(transfer_cases),
            "source_group_count": len(transfer_groups),
            "negative_count": sum(
                case["_label"] == 0 for case in transfer_cases
            ),
            "controlled_positive_count": sum(
                case["_label"] == 1 for case in transfer_cases
            ),
            "domains": sorted(transfer_domains),
            "manifest_commitment": BASE.manifest_commitment(
                args.transfer_manifest
            ),
            "fingerprint_commitment": transfer_fingerprint_commitment,
            "labels_previously_observed": True,
            "release_heldout": False,
        },
        "source_group_overlap_count": 0,
        "model_definition_sha256": BASE.MODEL_DEFINITION_SHA256,
    }
    return validation, training_cases, transfer_cases


def run(args) -> None:
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite report: {args.report}")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to reuse output directory: {args.output_dir}")
    if not 0 < args.minimum_recall <= 1:
        raise SystemExit("--minimum-recall must be in (0, 1]")
    if args.max_epochs < 1 or args.patience < 1 or args.batch_size < 1:
        raise SystemExit("epoch, patience, and batch values must be positive")
    validation, all_training_cases, transfer_cases = validate_inputs(args)
    if args.command == "validate":
        print(json.dumps(validation, indent=2, sort_keys=True))
        return

    np, sf, torch, torchaudio, nn, DataLoader, Dataset = (
        BASE.import_ml_stack()
    )
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    torch.use_deterministic_algorithms(True, warn_only=True)
    device = BASE.select_device(torch, args.device)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    selected_validation_groups = validation_groups(
        all_training_cases,
        args.seed,
    )
    training_cases = [
        case
        for case in all_training_cases
        if case["partition_group"] not in selected_validation_groups
    ]
    validation_cases = [
        case
        for case in all_training_cases
        if case["partition_group"] in selected_validation_groups
    ]
    if {
        case["partition_group"] for case in training_cases
    } & {
        case["partition_group"] for case in validation_cases
    }:
        raise RuntimeError("training and validation source groups overlap")

    args.output_dir.mkdir(parents=True)
    model = BASE.build_model(torch, torchaudio, nn).to(device)
    parameter_count = sum(
        parameter.numel() for parameter in model.parameters()
    )
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=args.learning_rate,
    )
    criterion = nn.CrossEntropyLoss()
    TrainingDataset = BASE.make_training_dataset_class(Dataset)
    checkpoint = args.output_dir / "broad-transfer.pt"
    epochs = []
    best_selection = None
    best_epoch = 0
    without_improvement = 0

    print(
        f"[broad training] train={len(training_cases)} "
        f"validation={len(validation_cases)} "
        f"transfer={len(transfer_cases)}"
    )
    for epoch in range(1, args.max_epochs + 1):
        plan = BASE.source_paired_epoch_plan(
            training_cases,
            args.seed,
            epoch,
        )
        dataset = TrainingDataset(
            plan,
            seed=args.seed,
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
        total_case_loss = 0.0
        total_pairwise_loss = 0.0
        pair_total = 0
        for negative_waveforms, positive_waveforms in loader:
            negative_waveforms = negative_waveforms.to(device)
            positive_waveforms = positive_waveforms.to(device)
            pair_count = len(negative_waveforms)
            waveforms = torch.cat(
                (negative_waveforms, positive_waveforms),
                dim=0,
            )
            cutoff = 14_000.0 + torch.rand(
                pair_count,
                device=device,
            ) * (BASE.TARGET_SAMPLE_RATE / 2 - 14_000.0)
            shared_cutoff = torch.cat((cutoff, cutoff), dim=0)
            optimizer.zero_grad(set_to_none=True)
            logits = model(waveforms, mask_cutoff_hz=shared_cutoff)
            loss, case_loss, pairwise_loss = BASE.source_paired_objective(
                logits,
                pair_count,
                criterion,
                torch,
            )
            if not torch.isfinite(loss):
                raise RuntimeError("non-finite broad training loss")
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().cpu()) * pair_count
            total_case_loss += (
                float(case_loss.detach().cpu()) * pair_count
            )
            total_pairwise_loss += (
                float(pairwise_loss.detach().cpu()) * pair_count
            )
            pair_total += pair_count

        validation_results = score_training_cases(
            model,
            validation_cases,
            batch_size=args.batch_size,
            device=device,
            np=np,
            sf=sf,
            torch=torch,
            torchaudio=torchaudio,
        )
        validation_scores = [
            result["score"] for result in validation_results
        ]
        validation_labels = [
            BASE.CLASS_TO_LABEL[result["expectation"]]
            for result in validation_results
        ]
        boundary = BASE.strict_zero_false_positive_boundary(
            validation_scores,
            validation_labels,
        )
        pooled_metrics = BASE.report_metrics(
            validation_results,
            boundary,
        )
        domain_metrics = metrics_by_training_domain(
            validation_results,
            boundary,
        )
        training_loss = total_loss / pair_total
        recalls = [metrics["recall"] for metrics in domain_metrics.values()]
        aucs = [metrics["auc"] for metrics in domain_metrics.values()]
        selection = (
            min(recalls),
            pooled_metrics["recall"],
            min(aucs),
            pooled_metrics["auc"],
            -pooled_metrics["log_loss"],
        )
        improved = best_selection is None or selection > best_selection
        epoch_result = {
            "epoch": epoch,
            "training_loss": training_loss,
            "training_case_loss": total_case_loss / pair_total,
            "training_pairwise_loss": total_pairwise_loss / pair_total,
            "training_pair_count": pair_total,
            "validation_boundary_exclusive": boundary,
            "validation_pooled": pooled_metrics,
            "validation_by_training_domain": domain_metrics,
            "selected": improved,
        }
        epochs.append(epoch_result)
        print(
            f"[epoch {epoch:02}] train_loss={training_loss:.6f} "
            f"min_domain_recall={min(recalls):.6f} "
            f"pooled_recall={pooled_metrics['recall']:.6f} "
            f"pooled_auc={pooled_metrics['auc']:.6f}"
        )
        if improved:
            best_selection = selection
            best_epoch = epoch
            without_improvement = 0
            BASE.save_checkpoint_atomic(
                torch,
                checkpoint,
                {
                    "schema_version": 1,
                    "seed": args.seed,
                    "epoch": epoch,
                    "model_definition": BASE.MODEL_DEFINITION,
                    "model_definition_sha256": (
                        BASE.MODEL_DEFINITION_SHA256
                    ),
                    "model_state": model.state_dict(),
                    "validation_boundary_exclusive": boundary,
                    "validation_pooled": pooled_metrics,
                    "validation_by_training_domain": domain_metrics,
                    "validation_case_results": validation_results,
                },
            )
        else:
            without_improvement += 1
        BASE.write_atomic(
            args.output_dir / "partial-report.json",
            {
                "schema_version": 1,
                "state": "partial_development_research",
                "best_epoch": best_epoch,
                "epochs": epochs,
            },
        )
        if without_improvement >= args.patience:
            break

    saved = torch.load(
        checkpoint,
        map_location=device,
        weights_only=False,
    )
    if (
        saved["model_definition_sha256"]
        != BASE.MODEL_DEFINITION_SHA256
    ):
        raise RuntimeError("checkpoint model definition differs")
    model.load_state_dict(saved["model_state"])
    boundary = float(saved["validation_boundary_exclusive"])
    transfer_results = BASE.score_cases(
        model,
        transfer_cases,
        batch_size=args.batch_size,
        device=device,
        np=np,
        sf=sf,
        torch=torch,
        torchaudio=torchaudio,
    )
    for result in transfer_results:
        result["boundary_exclusive"] = boundary
        result["predicted_positive"] = result["score"] >= boundary
    transfer_pooled = BASE.report_metrics(
        transfer_results,
        boundary,
    )
    transfer_by_domain = {}
    for domain in sorted(EXPECTED_TRANSFER_DOMAINS):
        selected = [
            result
            for result in transfer_results
            if result["domain"] == domain
        ]
        transfer_by_domain[domain] = {
            **BASE.report_metrics(selected, boundary),
            "by_class": BASE.by_class_counts(selected, boundary),
        }
    gate_passed = all(
        metrics["false_positives"] == 0
        and metrics["recall"] is not None
        and metrics["recall"] >= args.minimum_recall
        for metrics in transfer_by_domain.values()
    )
    report = {
        "schema_version": 1,
        "state": "development_research_only",
        "method": "broad_mixed_domain_source_paired_crnn",
        "reproduction_boundary": (
            "predeclared_source_paired_model_trained_only_on_disjoint_groups"
        ),
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
        "model_definition": BASE.MODEL_DEFINITION,
        "model_definition_sha256": BASE.MODEL_DEFINITION_SHA256,
        "parameter_count": parameter_count,
        "training": {
            "optimizer": "adam",
            "learning_rate": args.learning_rate,
            "pair_batch_size": args.batch_size,
            "maximum_epochs": args.max_epochs,
            "patience": args.patience,
            "seed": args.seed,
            "training_case_count": len(training_cases),
            "training_source_group_count": len(
                {case["partition_group"] for case in training_cases}
            ),
            "validation_case_count": len(validation_cases),
            "validation_source_group_count": len(
                selected_validation_groups
            ),
            "checkpoint_selection": [
                "minimum_strict_recall_across_training_domains",
                "pooled_strict_recall",
                "minimum_training_domain_auc",
                "pooled_auc",
                "negative_pooled_log_loss",
            ],
            "epochs": epochs,
        },
        "checkpoint": {
            "name": str(checkpoint.relative_to(args.output_dir)),
            "sha256": BASE.sha256_file(checkpoint),
            "size_bytes": checkpoint.stat().st_size,
            "best_epoch": best_epoch,
            "boundary_exclusive": boundary,
            "validation_pooled": saved["validation_pooled"],
            "validation_by_training_domain": saved[
                "validation_by_training_domain"
            ],
            "validation_case_results": saved[
                "validation_case_results"
            ],
        },
        "transfer": {
            "pooled": transfer_pooled,
            "by_domain": transfer_by_domain,
            "case_predictions": sorted(
                transfer_results,
                key=lambda result: result["case_id"],
            ),
        },
        "gate": {
            "minimum_recall_per_transfer_domain": args.minimum_recall,
            "maximum_false_positives_per_transfer_domain": 0,
            "passed": gate_passed,
        },
        "disposition": (
            "development_transfer_gate_passed_requires_independent_review"
            if gate_passed
            else "failed_development_transfer_gate"
        ),
    }
    BASE.write_atomic(args.report, report)
    BASE.write_atomic(args.output_dir / "final-report.json", report)
    print(
        f"wrote {args.report}; disposition={report['disposition']} "
        f"TP={transfer_pooled['true_positives']}/"
        f"{transfer_pooled['positive_count']} "
        f"FP={transfer_pooled['false_positives']}/"
        f"{transfer_pooled['negative_count']}"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("validate", "run"))
    result.add_argument(
        "--training-manifest",
        action="append",
        type=Path,
        required=True,
    )
    result.add_argument(
        "--training-fingerprints",
        action="append",
        type=Path,
        required=True,
    )
    result.add_argument(
        "--training-audio-root",
        action="append",
        type=Path,
        required=True,
    )
    result.add_argument(
        "--transfer-manifest",
        action="append",
        type=Path,
        required=True,
    )
    result.add_argument(
        "--transfer-fingerprints",
        action="append",
        type=Path,
        required=True,
    )
    result.add_argument(
        "--transfer-audio-root",
        action="append",
        type=Path,
        required=True,
    )
    result.add_argument(
        "--transfer-domain-map",
        type=Path,
        required=True,
    )
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--expected-training-groups", type=int, default=240)
    result.add_argument("--expected-training-cases", type=int, default=1720)
    result.add_argument(
        "--expected-training-negatives",
        type=int,
        default=600,
    )
    result.add_argument(
        "--expected-training-positives",
        type=int,
        default=1120,
    )
    result.add_argument("--expected-training-pairs", type=int, default=3200)
    result.add_argument("--seed", type=int, default=20260731)
    result.add_argument("--batch-size", type=int, default=16)
    result.add_argument("--max-epochs", type=int, default=20)
    result.add_argument("--patience", type=int, default=5)
    result.add_argument("--learning-rate", type=float, default=0.001)
    result.add_argument("--minimum-recall", type=float, default=0.90)
    result.add_argument(
        "--device",
        choices=("auto", "cpu", "mps"),
        default="auto",
    )
    return result


if __name__ == "__main__":
    run(parser().parse_args())
