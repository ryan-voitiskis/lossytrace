#!/usr/bin/env python3
"""Seal, freeze, and evaluate the private audio-integrity release gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
BENCHMARK_HARNESS_PATH = SCRIPT_PATH.with_name(
    "benchmark-audio-integrity.py"
)
OPAQUE_IDENTIFIER_FORBIDDEN = re.compile(
    r"(aac|aiff|dither|flac|gain|lossy|lowpass|mp3|opus|original|trim|vorbis|wav)",
    re.IGNORECASE,
)
BLIND_CASE_FIELDS = (
    "case_id",
    "source_group",
    "partition_group",
    "relative_path",
    "provenance_tier",
    "split",
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_private_atomic(path: Path, value: dict) -> None:
    if path.exists():
        raise SystemExit(f"refusing to replace existing gate artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def replace_private_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def unique_cases(manifest: dict, label: str) -> list[dict]:
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"{label}: cases must be a non-empty array")
    if any(not isinstance(case, dict) for case in cases):
        raise SystemExit(f"{label}: every case must be an object")
    case_ids = [case.get("case_id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        raise SystemExit(f"{label}: every case needs a non-empty case_id")
    if len(case_ids) != len(set(case_ids)):
        raise SystemExit(f"{label}: case IDs are not unique")
    for field in (
        "source_group",
        "relative_path",
        "provenance_tier",
        "split",
        "class",
        "expectation",
    ):
        if any(
            not isinstance(case.get(field), str) or not case[field]
            for case in cases
        ):
            raise SystemExit(f"{label}: every case needs a non-empty {field}")
    return cases


def fingerprint_map(fingerprints: dict, case_ids: set[str], label: str) -> dict:
    values = fingerprints.get("case_sha256")
    if not isinstance(values, dict) or set(values) != case_ids:
        raise SystemExit(f"{label}: fingerprints do not match manifest cases")
    if any(not valid_sha256(value) for value in values.values()):
        raise SystemExit(f"{label}: fingerprints must be lowercase SHA-256")
    return values


def opaque_identifier(case: dict) -> bool:
    relative = Path(case["relative_path"])
    return not (
        OPAQUE_IDENTIFIER_FORBIDDEN.search(case["case_id"])
        or OPAQUE_IDENTIFIER_FORBIDDEN.search(case["source_group"])
        or OPAQUE_IDENTIFIER_FORBIDDEN.search(case["partition_group"])
        or OPAQUE_IDENTIFIER_FORBIDDEN.search(relative.stem)
    )


def command_seal(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    blind_path = args.blind_manifest.expanduser().resolve()
    labels_path = args.labels.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    output_paths = (blind_path, labels_path, output_path)
    if len(set(output_paths)) != len(output_paths):
        raise SystemExit("seal outputs must be three different paths")
    if any(path.exists() for path in output_paths):
        raise SystemExit("refusing to replace an existing seal artifact")
    if manifest_path in output_paths or fingerprints_path in output_paths:
        raise SystemExit("seal outputs must not replace an input")
    if args.minimum_negative_source_groups <= 0:
        raise SystemExit("--minimum-negative-source-groups must be positive")
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    cases = unique_cases(manifest, "held-out manifest")
    case_ids = {case["case_id"] for case in cases}
    fingerprint_map(fingerprints, case_ids, "held-out manifest")
    if any(case.get("split") != "held_out" for case in cases):
        raise SystemExit("held-out seal accepts held_out cases only")
    if any(
        case.get("expectation") not in {"negative", "controlled_positive"}
        for case in cases
    ):
        raise SystemExit(
            "held-out labels must be negative or controlled_positive"
        )
    if any(
        case.get("provenance_tier") != "tier_a_confirmed_pcm"
        for case in cases
    ):
        raise SystemExit("release held-out cases must all be Tier A")
    if any(
        not isinstance(case.get("partition_group"), str)
        or not case["partition_group"]
        for case in cases
    ):
        raise SystemExit(
            "release held-out cases require opaque partition_group values"
        )
    if any(not opaque_identifier(case) for case in cases):
        raise SystemExit(
            "held-out case IDs and filenames must be opaque before sealing"
        )

    negative_groups = {
        case["source_group"]
        for case in cases
        if case["expectation"] == "negative"
    }
    positive_count = sum(
        case["expectation"] == "controlled_positive" for case in cases
    )
    if len(negative_groups) < args.minimum_negative_source_groups:
        raise SystemExit(
            f"held-out corpus has {len(negative_groups)} negative source "
            f"groups; {args.minimum_negative_source_groups} required"
        )
    if positive_count == 0:
        raise SystemExit("held-out corpus contains no controlled positives")

    labels = {
        "schema_version": 1,
        "seal_id": args.seal_id,
        "source_corpus_id": manifest.get("corpus_id"),
        "source_manifest_sha256": sha256_file(manifest_path),
        "cases": [
            {
                "case_id": case["case_id"],
                "source_group": case["source_group"],
                "partition_group": case["partition_group"],
                "provenance_tier": case["provenance_tier"],
                "class": case["class"],
                "expectation": case["expectation"],
            }
            for case in cases
        ],
    }
    blind_manifest = {
        "schema_version": manifest.get("schema_version"),
        "corpus_id": f"{args.seal_id}-blind",
        "corpus_version": manifest.get("corpus_version"),
        "audio_root_env": manifest.get("audio_root_env"),
        "analysis_max_seconds": manifest.get("analysis_max_seconds"),
        "repetitions": manifest.get("repetitions"),
        "sealed_from_manifest_sha256": sha256_file(manifest_path),
        "recipes_omitted": True,
        "cases": [
            {
                **{key: case[key] for key in BLIND_CASE_FIELDS},
                "class": "sealed_case",
                "expectation": "blind_case_study",
            }
            for case in cases
        ],
    }
    write_private_atomic(labels_path, labels)
    write_private_atomic(blind_path, blind_manifest)
    seal = {
        "schema_version": 1,
        "seal_id": args.seal_id,
        "state": "sealed_unopened",
        "created_at": now(),
        "labels_opened": False,
        "evaluation_count": 0,
        "source_manifest_sha256": sha256_file(manifest_path),
        "blind_manifest_path": str(blind_path),
        "blind_manifest_sha256": sha256_file(blind_path),
        "labels_path": str(labels_path),
        "labels_sha256": sha256_file(labels_path),
        "fingerprints_path": str(fingerprints_path),
        "fingerprints_sha256": sha256_file(fingerprints_path),
        "case_count": len(cases),
        "source_group_count": len({case["source_group"] for case in cases}),
        "partition_group_count": len(
            {case["partition_group"] for case in cases}
        ),
        "negative_source_group_count": len(negative_groups),
        "minimum_negative_source_groups_at_seal": (
            args.minimum_negative_source_groups
        ),
    }
    write_private_atomic(output_path, seal)
    print(
        f"sealed {len(cases)} opaque held-out cases from "
        f"{len(negative_groups)} Tier A negative source groups; labels unopened"
    )
    return 0


def group_commitments(
    cases: list[dict],
    field: str = "source_group",
) -> list[str]:
    return sorted(
        hashlib.sha256(
            f"reklawdbox-audio-integrity-{field}-v1:{group}".encode()
        ).hexdigest()
        for group in {case.get(field) or case["source_group"] for case in cases}
    )


def require_rate(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise SystemExit(f"{name} must be between 0 and 1")


def merge_development_inputs(
    manifest_paths: list[Path],
    fingerprint_paths: list[Path],
) -> tuple[list[dict], list[dict], dict[str, str]]:
    if len(manifest_paths) != len(fingerprint_paths):
        raise SystemExit(
            "repeat --development-manifest and --development-fingerprints "
            "the same number of times"
        )
    by_id: dict[str, dict] = {}
    by_fingerprint: dict[str, str] = {}
    evidence = []
    for manifest_path, fingerprints_path in zip(
        manifest_paths,
        fingerprint_paths,
        strict=True,
    ):
        manifest = load_json(manifest_path)
        fingerprints = load_json(fingerprints_path)
        cases = unique_cases(manifest, f"development manifest {manifest_path}")
        case_ids = {case["case_id"] for case in cases}
        case_fingerprints = fingerprint_map(
            fingerprints,
            case_ids,
            f"development manifest {manifest_path}",
        )
        for case in cases:
            if "partition_group" in case and (
                not isinstance(case["partition_group"], str)
                or not case["partition_group"]
            ):
                raise SystemExit(
                    f"{manifest_path}: partition_group must be non-empty"
                )
            previous = by_id.setdefault(case["case_id"], case)
            if previous != case:
                raise SystemExit(
                    f"conflicting development case: {case['case_id']}"
                )
            previous_fingerprint = by_fingerprint.setdefault(
                case["case_id"],
                case_fingerprints[case["case_id"]],
            )
            if previous_fingerprint != case_fingerprints[case["case_id"]]:
                raise SystemExit(
                    f"conflicting development fingerprint: {case['case_id']}"
                )
        evidence.append(
            {
                "manifest_sha256": sha256_file(manifest_path),
                "fingerprints_sha256": sha256_file(fingerprints_path),
                "case_count": len(cases),
            }
        )
    return (
        [by_id[case_id] for case_id in sorted(by_id)],
        evidence,
        by_fingerprint,
    )


def compression_feature_family(feature: object) -> str | None:
    if not isinstance(feature, str):
        return None
    if not feature.startswith("compression_trace."):
        return None
    leaf = feature.removeprefix("compression_trace.")
    if leaf.startswith("spectral_edge_"):
        return "spectral_edge"
    if "hole" in leaf:
        return "spectral_holes"
    if "rupture" in leaf:
        return "band_rupture"
    if leaf in {
        "transform_alignment_score",
        "transform_alignment_small_coefficient_fraction",
    }:
        return "transform_alignment"
    return None


def command_freeze(args: argparse.Namespace) -> int:
    for name, value in (
        ("--minimum-development-recall", args.minimum_development_recall),
        ("--minimum-heldout-recall", args.minimum_heldout_recall),
        (
            "--maximum-false-positive-upper-95",
            args.maximum_false_positive_upper_95,
        ),
        (
            "--maximum-invariant-relative-delta",
            args.maximum_invariant_relative_delta,
        ),
    ):
        require_rate(name, value)
    if not args.obvious_positive_class:
        raise SystemExit("at least one --obvious-positive-class is required")
    if not args.hard_negative_class:
        raise SystemExit("at least one --hard-negative-class is required")
    if not args.invariant_control_class:
        raise SystemExit("at least one --invariant-control-class is required")
    if not args.reference_negative_class:
        raise SystemExit("at least one --reference-negative-class is required")
    if args.minimum_negative_source_groups <= 0:
        raise SystemExit("--minimum-negative-source-groups must be positive")
    if args.minimum_invariant_source_groups <= 0:
        raise SystemExit("--minimum-invariant-source-groups must be positive")
    if not 1 <= args.minimum_timing_repetitions <= 20:
        raise SystemExit("--minimum-timing-repetitions must be in 1..=20")
    for name, value in (
        (
            "--maximum-p95-runtime-overhead-percent",
            args.maximum_p95_runtime_overhead_percent,
        ),
        (
            "--maximum-peak-memory-increase-percent",
            args.maximum_peak_memory_increase_percent,
        ),
    ):
        if not math.isfinite(value) or value < 0:
            raise SystemExit(f"{name} must be finite and non-negative")

    report_path = args.development_report.expanduser().resolve()
    runner_path = args.runner.expanduser().resolve()
    manifest_paths = [
        path.expanduser().resolve() for path in args.development_manifest
    ]
    fingerprint_paths = [
        path.expanduser().resolve()
        for path in args.development_fingerprints
    ]
    candidate_paths = [
        path.expanduser().resolve()
        for path in args.development_candidate
    ]
    seal_path = args.heldout_seal.expanduser().resolve()
    if not runner_path.is_file():
        raise SystemExit(f"frozen benchmark runner does not exist: {runner_path}")
    if not BENCHMARK_HARNESS_PATH.is_file():
        raise SystemExit(
            f"benchmark harness does not exist: {BENCHMARK_HARNESS_PATH}"
        )
    runner_sha256 = sha256_file(runner_path)
    harness_sha256 = sha256_file(BENCHMARK_HARNESS_PATH)
    report = load_json(report_path)
    seal = load_json(seal_path)
    cases, development_inputs, development_fingerprints = merge_development_inputs(
        manifest_paths,
        fingerprint_paths,
    )
    if any(case.get("split") != "development" for case in cases):
        raise SystemExit("freeze accepts development cases only")
    disposition = report.get("disposition", {})
    if (
        disposition.get("held_out_opened") is not False
        or disposition.get("public_verdict_enabled") is not False
    ):
        raise SystemExit("development report has an unsafe disposition")
    candidate_evidence = report.get("candidate_evidence")
    if not isinstance(candidate_evidence, list) or not candidate_evidence:
        raise SystemExit(
            "development report lacks candidate implementation commitments"
        )
    for evidence in candidate_evidence:
        if (
            not isinstance(evidence, dict)
            or evidence.get("runner_sha256") != runner_sha256
            or evidence.get("harness_sha256") != harness_sha256
            or evidence.get("feature_version") != 0
            or not valid_sha256(evidence.get("report_sha256"))
            or not isinstance(evidence.get("case_count"), int)
            or evidence["case_count"] <= 0
        ):
            raise SystemExit(
                "development candidate evidence differs from the frozen "
                "runner or benchmark harness"
            )
    evidence_by_hash = {
        evidence["report_sha256"]: evidence
        for evidence in candidate_evidence
    }
    if len(evidence_by_hash) != len(candidate_evidence):
        raise SystemExit("development report repeats candidate evidence")
    candidate_hashes = {sha256_file(path) for path in candidate_paths}
    if (
        len(candidate_hashes) != len(candidate_paths)
        or candidate_hashes != set(evidence_by_hash)
    ):
        raise SystemExit(
            "development candidates do not match the policy report evidence"
        )
    development_case_by_id = {case["case_id"]: case for case in cases}
    candidate_case_ids = set()
    for candidate_path in candidate_paths:
        candidate = load_json(candidate_path)
        evidence = evidence_by_hash[sha256_file(candidate_path)]
        candidate_cases = candidate.get("results")
        if (
            candidate.get("feature_version") != 0
            or candidate.get("runner_sha256") != runner_sha256
            or candidate.get("harness_sha256") != harness_sha256
            or not isinstance(candidate_cases, list)
            or len(candidate_cases) != evidence["case_count"]
        ):
            raise SystemExit(
                f"development candidate contract differs: {candidate_path}"
            )
        for row in candidate_cases:
            if not isinstance(row, dict):
                raise SystemExit("development candidate row must be an object")
            case_id = row.get("case_id")
            if case_id not in development_case_by_id:
                raise SystemExit(
                    f"unexpected development candidate case: {case_id}"
                )
            case = development_case_by_id[case_id]
            for field in (
                "source_group",
                "split",
                "provenance_tier",
                "class",
                "expectation",
            ):
                if row.get(field) != case[field]:
                    raise SystemExit(
                        f"{case_id}: development candidate {field} differs"
                    )
            if case.get("partition_group") is not None and row.get(
                "partition_group"
            ) != case.get("partition_group"):
                raise SystemExit(
                    f"{case_id}: development candidate partition_group differs"
                )
            runner = row.get("runner")
            if (
                not isinstance(runner, dict)
                or runner.get("audio_sha256")
                != development_fingerprints[case_id]
                or runner.get("feature_version") != 0
            ):
                raise SystemExit(
                    f"{case_id}: development runner evidence differs"
                )
            candidate_case_ids.add(case_id)
    if candidate_case_ids != set(development_case_by_id):
        raise SystemExit(
            "development candidate union does not match committed manifests"
        )
    if seal.get("state") != "sealed_unopened" or seal.get("labels_opened"):
        raise SystemExit("held-out seal is not unopened")
    if seal.get("evaluation_count") != 0:
        raise SystemExit("held-out seal has already been evaluated")
    if (
        seal.get("negative_source_group_count", 0)
        < args.minimum_negative_source_groups
    ):
        raise SystemExit("held-out seal is smaller than the frozen release gate")

    nested = report.get("nested_grouped_evaluation", {})
    for field in (
        "negative_count",
        "false_positive_count",
        "controlled_positive_count",
        "detected_positive_count",
    ):
        if (
            not isinstance(nested.get(field), int)
            or isinstance(nested[field], bool)
            or nested[field] < 0
        ):
            raise SystemExit(
                f"development report has invalid nested {field}"
            )
    if nested.get("false_positive_count") != 0:
        raise SystemExit(
            "cannot freeze an explainable policy with nested false positives"
        )
    nested_positive_count = nested.get("controlled_positive_count", 0)
    nested_detected_count = nested.get("detected_positive_count", 0)
    if nested_positive_count <= 0:
        raise SystemExit("development report has no controlled positives")
    expected_negative_count = sum(
        case["expectation"] == "negative" for case in cases
    )
    expected_positive_count = sum(
        case["expectation"] == "controlled_positive" for case in cases
    )
    if (
        report.get("case_count") != len(cases)
        or nested.get("negative_count") != expected_negative_count
        or nested_positive_count != expected_positive_count
    ):
        raise SystemExit(
            "development report counts do not match the committed manifests"
        )
    obvious_classes = set(args.obvious_positive_class)
    obvious_positive_counts = Counter(
        case["class"]
        for case in cases
        if case["expectation"] == "controlled_positive"
        and case["class"] in obvious_classes
    )
    if set(obvious_positive_counts) != obvious_classes:
        raise SystemExit(
            "development manifests do not cover every obvious-positive class"
        )
    nested_by_class = nested.get("detected_by_class")
    if not isinstance(nested_by_class, dict):
        raise SystemExit("development report lacks detected_by_class")
    obvious_detected_counts = {
        class_name: nested_by_class.get(class_name, 0)
        for class_name in obvious_classes
    }
    obvious_detected_count = sum(obvious_detected_counts.values())
    obvious_positive_count = sum(obvious_positive_counts.values())
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in nested_by_class.values()
    ):
        raise SystemExit("development detected_by_class is invalid")
    if (
        nested_detected_count > nested_positive_count
        or obvious_detected_count > obvious_positive_count
        or any(
            obvious_detected_counts[class_name]
            > obvious_positive_counts[class_name]
            for class_name in obvious_classes
        )
        or sum(nested_by_class.values()) != nested_detected_count
    ):
        raise SystemExit("development detected counts are inconsistent")
    development_recall = nested_detected_count / nested_positive_count
    obvious_development_recall_by_class = {
        class_name: obvious_detected_counts[class_name]
        / obvious_positive_counts[class_name]
        for class_name in sorted(obvious_classes)
    }
    obvious_development_recall = (
        obvious_detected_count / obvious_positive_count
    )
    if any(
        recall < args.minimum_development_recall
        for recall in obvious_development_recall_by_class.values()
    ):
        raise SystemExit(
            "nested development recall is below the required "
            f"{args.minimum_development_recall:.6f} for an "
            "obvious-positive class"
        )
    policy = report.get("full_development_policy")
    if not isinstance(policy, dict):
        raise SystemExit("development report has no full policy")
    first = policy.get("first")
    second = policy.get("second")
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise SystemExit("development policy must contain two feature rules")
    if first.get("family") == second.get("family"):
        raise SystemExit("frozen feature rules must use different families")
    for rule in (first, second):
        actual_family = compression_feature_family(rule.get("feature", ""))
        if actual_family is None or actual_family != rule.get("family"):
            raise SystemExit(
                "frozen rules must use correctly labelled production "
                "compression_trace feature families"
            )
        if rule.get("direction") not in {"higher", "lower"}:
            raise SystemExit("frozen rule has an unsupported direction")
        if (
            not isinstance(rule.get("threshold"), (int, float))
            or isinstance(rule["threshold"], bool)
            or not math.isfinite(rule["threshold"])
        ):
            raise SystemExit("frozen rule threshold must be finite")

    frozen_policy = {
        "kind": "two_explainable_families",
        "minimum_reason_family_count": 2,
        "first": {
            key: first[key]
            for key in ("feature", "family", "direction", "threshold")
        },
        "second": {
            key: second[key]
            for key in ("feature", "family", "direction", "threshold")
        },
    }
    release_gates = {
        "minimum_negative_source_groups": args.minimum_negative_source_groups,
        "maximum_observed_false_positive_count": 0,
        "maximum_false_positive_upper_95": (
            args.maximum_false_positive_upper_95
        ),
        "obvious_positive_classes": sorted(obvious_classes),
        "minimum_obvious_positive_recall_lower_95": (
            args.minimum_heldout_recall
        ),
        "hard_negative_classes": sorted(set(args.hard_negative_class)),
        "reference_negative_classes": sorted(
            set(args.reference_negative_class)
        ),
        "invariant_control_classes": sorted(
            set(args.invariant_control_class)
        ),
        "minimum_invariant_source_groups": (
            args.minimum_invariant_source_groups
        ),
        "maximum_invariant_relative_delta": (
            args.maximum_invariant_relative_delta
        ),
        "minimum_timing_repetitions": args.minimum_timing_repetitions,
        "required_runtime_jobs": 1,
        "maximum_p95_runtime_overhead_percent": (
            args.maximum_p95_runtime_overhead_percent
        ),
        "maximum_peak_memory_increase_percent": (
            args.maximum_peak_memory_increase_percent
        ),
    }
    implementation_commitment = {
        "runner_sha256": runner_sha256,
        "benchmark_harness_sha256": harness_sha256,
        "release_gate_script_sha256": sha256_file(SCRIPT_PATH),
    }
    frozen_payload = {
        "frozen_policy": frozen_policy,
        "release_gates": release_gates,
        "implementation_commitment": implementation_commitment,
    }
    freeze = {
        "schema_version": 1,
        "freeze_id": args.freeze_id,
        "state": "frozen_before_heldout",
        "created_at": now(),
        "heldout_opened": False,
        "public_verdict_enabled": False,
        "feature_version": 0,
        "development_evidence": {
            "report_sha256": sha256_file(report_path),
            "inputs": development_inputs,
            "case_count": len(cases),
            "source_group_count": len(
                {case["source_group"] for case in cases}
            ),
            "source_group_commitments": group_commitments(cases),
            "partition_group_count": len(
                {
                    case.get("partition_group", case["source_group"])
                    for case in cases
                }
            ),
            "partition_group_commitments": group_commitments(
                cases,
                "partition_group",
            ),
            "nested_recall": development_recall,
            "nested_obvious_positive_recall": obvious_development_recall,
            "nested_obvious_positive_recall_by_class": (
                obvious_development_recall_by_class
            ),
            "nested_false_positive_count": nested["false_positive_count"],
        },
        "heldout_commitment": {
            "seal_id": seal["seal_id"],
            "seal_sha256": sha256_file(seal_path),
            "blind_manifest_sha256": seal["blind_manifest_sha256"],
            "labels_sha256": seal["labels_sha256"],
            "fingerprints_sha256": seal["fingerprints_sha256"],
        },
        **frozen_payload,
        "policy_and_gate_digest": canonical_sha256(frozen_payload),
    }
    write_private_atomic(args.output, freeze)
    print(
        f"froze policy {args.freeze_id} before held-out labels; "
        "obvious-positive development "
        f"recall={obvious_development_recall:.6f}"
    )
    return 0


def flatten_numeric(value: object, prefix: str = "") -> dict[str, float]:
    result: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else key
            result.update(flatten_numeric(child, name))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if math.isfinite(numeric):
            result[prefix] = numeric
    return result


def feature_passes(value: float, rule: dict) -> bool:
    if rule["direction"] == "higher":
        return value > rule["threshold"]
    return value < rule["threshold"]


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def wilson_interval(successes: int, total: int) -> dict | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return {
        "low": max(0.0, center - radius),
        "high": min(1.0, center + radius),
    }


def candidate_rows(paths: list[Path]) -> tuple[dict[str, dict], list[dict]]:
    rows: dict[str, dict] = {}
    runtime_records = []
    for path in paths:
        report = load_json(path)
        repetitions = report.get("repetitions")
        runtime = report.get("runtime")
        report_rows = report.get("results")
        if (
            not isinstance(repetitions, int)
            or not 1 <= repetitions <= 20
            or not isinstance(runtime, dict)
            or not isinstance(runtime.get("jobs"), int)
        ):
            raise SystemExit(f"{path}: invalid timing metadata")
        if not isinstance(report_rows, list) or not report_rows:
            raise SystemExit(f"{path}: results must be a non-empty array")
        runtime_records.append(
            {
                "path": str(path),
                "feature_version": report.get("feature_version"),
                "runner_sha256": report.get("runner_sha256"),
                "harness_sha256": report.get("harness_sha256"),
                "analysis_max_seconds": report.get("analysis_max_seconds"),
                "repetitions": repetitions,
                "runtime": runtime,
            }
        )
        for row in report_rows:
            if not isinstance(row, dict):
                raise SystemExit(f"{path}: every result row must be an object")
            case_id = row.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise SystemExit(f"{path}: result row has no case_id")
            previous = rows.setdefault(case_id, row)
            if previous != row:
                raise SystemExit(f"conflicting candidate result: {case_id}")
    if not rows:
        raise SystemExit("candidate reports contain no result rows")
    return rows, runtime_records


def label_rows(labels: dict) -> dict[str, dict]:
    cases = labels.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("sealed labels contain no cases")
    rows = {case["case_id"]: case for case in cases}
    if len(rows) != len(cases):
        raise SystemExit("sealed labels contain duplicate case IDs")
    return rows


def selected_metrics(rows: list[dict]) -> dict:
    negatives = [row for row in rows if row["expectation"] == "negative"]
    positives = [
        row for row in rows if row["expectation"] == "controlled_positive"
    ]
    selected = [row for row in rows if row["selected"]]
    false_positives = [
        row for row in selected if row["expectation"] == "negative"
    ]
    true_positives = [
        row
        for row in selected
        if row["expectation"] == "controlled_positive"
    ]
    precision = (
        len(true_positives) / len(selected) if selected else None
    )
    return {
        "negative_count": len(negatives),
        "false_positive_count": len(false_positives),
        "false_positive_rate": (
            len(false_positives) / len(negatives) if negatives else None
        ),
        "false_positive_rate_95_percent_ci": wilson_interval(
            len(false_positives),
            len(negatives),
        ),
        "controlled_positive_count": len(positives),
        "detected_positive_count": len(true_positives),
        "recall": len(true_positives) / len(positives) if positives else None,
        "recall_95_percent_ci": wilson_interval(
            len(true_positives),
            len(positives),
        ),
        "selected_count": len(selected),
        "precision_on_evaluation_mix": precision,
        "precision_95_percent_ci": wilson_interval(
            len(true_positives),
            len(selected),
        ),
    }


def negative_source_group_metrics(rows: list[dict]) -> dict:
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["expectation"] == "negative":
            by_group[row["source_group"]].append(row)
    alerted_groups = [
        source_group
        for source_group, group_rows in by_group.items()
        if any(row["selected"] for row in group_rows)
    ]
    return {
        "negative_source_group_count": len(by_group),
        "alerted_source_group_count": len(alerted_groups),
        "alerted_source_group_rate": (
            len(alerted_groups) / len(by_group) if by_group else None
        ),
        "alerted_source_group_rate_95_percent_ci": wilson_interval(
            len(alerted_groups),
            len(by_group),
        ),
    }


def invariant_metrics(rows: list[dict], gates: dict, policy: dict) -> dict:
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_group[row["source_group"]].append(row)
    references = set(gates["reference_negative_classes"])
    controls = set(gates["invariant_control_classes"])
    deltas = []
    missing_pairs = []
    complete_source_groups = []
    for source_group, group_rows in sorted(by_group.items()):
        reference_rows = [
            row for row in group_rows if row["class"] in references
        ]
        control_rows = [row for row in group_rows if row["class"] in controls]
        present_control_classes = {row["class"] for row in control_rows}
        if not present_control_classes:
            continue
        if (
            len(reference_rows) != 1
            or present_control_classes != controls
            or len(control_rows) != len(controls)
        ):
            missing_pairs.append(source_group)
            continue
        complete_source_groups.append(source_group)
        reference = reference_rows[0]
        for control in control_rows:
            for rule in (policy["first"], policy["second"]):
                feature = rule["feature"]
                if (
                    feature not in reference["features"]
                    or feature not in control["features"]
                ):
                    missing_pairs.append(f"{source_group}:{feature}")
                    continue
                baseline = reference["features"][feature]
                changed = control["features"][feature]
                scale = max(abs(baseline), abs(changed), 1.0e-6)
                deltas.append(abs(changed - baseline) / scale)
    return {
        "comparison_count": len(deltas),
        "complete_source_group_count": len(complete_source_groups),
        "missing_pair_count": len(missing_pairs),
        "missing_pairs": missing_pairs,
        "maximum_relative_delta": max(deltas) if deltas else None,
        "p95_relative_delta": quantile(deltas, 0.95),
    }


def command_evaluate(args: argparse.Namespace) -> int:
    freeze_path = args.freeze.expanduser().resolve()
    seal_path = args.seal.expanduser().resolve()
    blind_path = args.blind_manifest.expanduser().resolve()
    labels_path = args.labels.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    memory_path = args.memory_report.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if output_path.exists():
        raise SystemExit(
            f"refusing to replace existing gate artifact: {output_path}"
        )
    freeze = load_json(freeze_path)
    seal = load_json(seal_path)
    if args.confirm_seal_id != seal.get("seal_id"):
        raise SystemExit("seal confirmation differs from seal record")
    if freeze.get("state") != "frozen_before_heldout":
        raise SystemExit("policy is not frozen before held-out evaluation")
    if seal.get("state") != "sealed_unopened" or seal.get("labels_opened"):
        raise SystemExit("held-out labels are not in the unopened state")
    if seal.get("evaluation_count") != 0:
        raise SystemExit("held-out seal has already been evaluated")
    commitment = freeze["heldout_commitment"]
    if commitment["seal_id"] != seal["seal_id"]:
        raise SystemExit("freeze and held-out seal IDs differ")
    if sha256_file(seal_path) != commitment["seal_sha256"]:
        raise SystemExit("held-out seal changed after policy freeze")
    for path, seal_field, freeze_field in (
        (blind_path, "blind_manifest_sha256", "blind_manifest_sha256"),
        (labels_path, "labels_sha256", "labels_sha256"),
        (fingerprints_path, "fingerprints_sha256", "fingerprints_sha256"),
    ):
        digest = sha256_file(path)
        if digest != seal[seal_field] or digest != commitment[freeze_field]:
            raise SystemExit(f"sealed artifact hash differs: {path}")

    frozen_payload = {
        "frozen_policy": freeze["frozen_policy"],
        "release_gates": freeze["release_gates"],
        "implementation_commitment": freeze["implementation_commitment"],
    }
    if canonical_sha256(frozen_payload) != freeze["policy_and_gate_digest"]:
        raise SystemExit(
            "frozen policy, release gates, or implementation were modified"
        )
    implementation = freeze["implementation_commitment"]
    if (
        implementation.get("release_gate_script_sha256")
        != sha256_file(SCRIPT_PATH)
        or not BENCHMARK_HARNESS_PATH.is_file()
        or implementation.get("benchmark_harness_sha256")
        != sha256_file(BENCHMARK_HARNESS_PATH)
    ):
        raise SystemExit(
            "release gate or benchmark harness changed after policy freeze"
        )
    blind = load_json(blind_path)
    blind_cases = unique_cases(blind, "blind manifest")
    blind_ids = {case["case_id"] for case in blind_cases}
    if any(
        case.get("expectation") != "blind_case_study"
        or case.get("class") != "sealed_case"
        for case in blind_cases
    ):
        raise SystemExit("blind manifest exposes or changes held-out labels")
    if any(
        set(case) != {*BLIND_CASE_FIELDS, "class", "expectation"}
        for case in blind_cases
    ):
        raise SystemExit("blind manifest contains unapproved case fields")
    fingerprints = load_json(fingerprints_path)
    expected_fingerprints = fingerprint_map(
        fingerprints,
        blind_ids,
        "blind manifest",
    )
    candidates, runtime_records = candidate_rows(args.candidate)
    if set(candidates) != blind_ids:
        raise SystemExit("candidate reports do not match blind manifest")
    if any(
        record["feature_version"] != freeze["feature_version"]
        or record["runner_sha256"] != implementation["runner_sha256"]
        or record["harness_sha256"]
        != implementation["benchmark_harness_sha256"]
        for record in runtime_records
    ):
        raise SystemExit(
            "candidate implementation differs from the frozen implementation"
        )
    blind_by_id = {case["case_id"]: case for case in blind_cases}
    for case_id, row in candidates.items():
        blind_case = blind_by_id[case_id]
        for field in (
            "source_group",
            "partition_group",
            "split",
            "provenance_tier",
            "class",
            "expectation",
        ):
            if row.get(field) != blind_case[field]:
                raise SystemExit(
                    f"{case_id}: candidate {field} differs from blind manifest"
                )
        runner = row.get("runner")
        if not isinstance(runner, dict):
            raise SystemExit(f"{case_id}: candidate runner is missing")
        if runner.get("audio_sha256") != expected_fingerprints[case_id]:
            raise SystemExit(f"{case_id}: candidate audio fingerprint differs")
        if (
            runner.get("feature_version") != freeze["feature_version"]
            or not isinstance(runner.get("repetitions"), int)
            or runner["repetitions"]
            < freeze["release_gates"]["minimum_timing_repetitions"]
        ):
            raise SystemExit(
                f"{case_id}: runner version or repetition count differs"
            )
        overhead = runner.get("runtime_overhead_percent")
        if (
            not isinstance(overhead, (int, float))
            or isinstance(overhead, bool)
            or not math.isfinite(overhead)
        ):
            raise SystemExit(f"{case_id}: runtime overhead is invalid")
    expected_analysis_max_seconds = blind.get("analysis_max_seconds")
    if any(
        record["analysis_max_seconds"] != expected_analysis_max_seconds
        for record in runtime_records
    ):
        raise SystemExit(
            "candidate analysis duration differs from blind manifest"
        )

    heldout_source_commitments = set(group_commitments(blind_cases))
    development_source_commitments = set(
        freeze["development_evidence"]["source_group_commitments"]
    )
    if heldout_source_commitments & development_source_commitments:
        raise SystemExit("development and held-out source groups overlap")
    heldout_partition_commitments = set(
        group_commitments(blind_cases, "partition_group")
    )
    development_partition_commitments = set(
        freeze["development_evidence"]["partition_group_commitments"]
    )
    if heldout_partition_commitments & development_partition_commitments:
        raise SystemExit(
            "development and held-out partition groups overlap"
        )

    memory = load_json(memory_path)
    if memory.get("schema_version") != 1:
        raise SystemExit("memory report schema_version must be 1")
    memory_case_ids = memory.get("case_ids")
    if (
        memory.get("manifest_sha256") != sha256_file(blind_path)
        or memory.get("fingerprints_sha256") != sha256_file(fingerprints_path)
        or not isinstance(memory_case_ids, list)
        or any(not isinstance(case_id, str) for case_id in memory_case_ids)
        or len(memory_case_ids) != len(set(memory_case_ids))
        or set(memory_case_ids) != blind_ids
        or memory.get("case_count") != len(blind_ids)
        or memory.get("feature_version") != freeze["feature_version"]
        or memory.get("runner_sha256") != implementation["runner_sha256"]
        or memory.get("harness_sha256")
        != implementation["benchmark_harness_sha256"]
    ):
        raise SystemExit(
            "memory report is not bound to every sealed held-out case"
        )
    baseline_peak = memory.get("baseline_peak_rss_bytes")
    prototype_peak = memory.get("prototype_peak_rss_bytes")
    if (
        not isinstance(baseline_peak, int)
        or not isinstance(prototype_peak, int)
        or baseline_peak <= 0
        or prototype_peak <= 0
    ):
        raise SystemExit("memory report peak RSS values must be positive integers")
    observations = memory.get("observations")
    if not isinstance(observations, list) or len(observations) != len(blind_ids):
        raise SystemExit("memory report lacks complete per-case observations")
    observation_by_id = {}
    for observation in observations:
        if not isinstance(observation, dict):
            raise SystemExit("memory observation must be an object")
        case_id = observation.get("case_id")
        baseline = observation.get("baseline_peak_rss_bytes")
        prototype = observation.get("prototype_peak_rss_bytes")
        if (
            not isinstance(case_id, str)
            or case_id in observation_by_id
            or not isinstance(baseline, int)
            or isinstance(baseline, bool)
            or baseline <= 0
            or not isinstance(prototype, int)
            or isinstance(prototype, bool)
            or prototype <= 0
        ):
            raise SystemExit("memory observation is invalid")
        observation_by_id[case_id] = observation
    if (
        set(observation_by_id) != blind_ids
        or max(
            observation["baseline_peak_rss_bytes"]
            for observation in observations
        )
        != baseline_peak
        or max(
            observation["prototype_peak_rss_bytes"]
            for observation in observations
        )
        != prototype_peak
    ):
        raise SystemExit("memory report aggregates differ from observations")

    # This state change deliberately occurs before parsing labels. A crash or
    # failed evaluation after this point leaves the seal non-reusable.
    pre_open_seal_sha256 = sha256_file(seal_path)
    seal["state"] = "labels_opening"
    seal["labels_opened"] = True
    seal["labels_opened_at"] = now()
    seal["evaluation_count"] = 1
    seal["evaluation_freeze_sha256"] = sha256_file(freeze_path)
    replace_private_atomic(seal_path, seal)

    labels = load_json(labels_path)
    if sha256_file(labels_path) != commitment["labels_sha256"]:
        raise SystemExit("sealed labels changed while opening")
    labels_by_id = label_rows(labels)
    if set(labels_by_id) != blind_ids:
        raise SystemExit("sealed labels do not match blind cases")
    for case_id, label in labels_by_id.items():
        blind_case = blind_by_id[case_id]
        if (
            label.get("source_group") != blind_case["source_group"]
            or label.get("partition_group")
            != blind_case["partition_group"]
            or label.get("provenance_tier")
            != blind_case["provenance_tier"]
        ):
            raise SystemExit(f"{case_id}: sealed identity fields differ")

    policy = freeze["frozen_policy"]
    rows = []
    for case_id in sorted(candidates):
        candidate = candidates[case_id]
        label = labels_by_id[case_id]
        features = {}
        runner = candidate["runner"]
        for namespace in (
            "compression_trace",
            "stereo_trace",
            "transform_grid_probe",
        ):
            features.update(flatten_numeric(runner.get(namespace), namespace))
        rules = (policy["first"], policy["second"])
        measured_families = [
            rule["family"] for rule in rules if rule["feature"] in features
        ]
        passing_families = [
            rule["family"]
            for rule in rules
            if rule["feature"] in features
            and feature_passes(features[rule["feature"]], rule)
        ]
        rows.append(
            {
                "case_id": case_id,
                "source_group": label["source_group"],
                "provenance_tier": label["provenance_tier"],
                "class": label["class"],
                "expectation": label["expectation"],
                "features": features,
                "measured_reason_families": measured_families,
                "passing_reason_families": passing_families,
                "selected": len(passing_families)
                >= policy["minimum_reason_family_count"],
            }
        )

    gates = freeze["release_gates"]
    metrics = selected_metrics(rows)
    negative_group_metrics = negative_source_group_metrics(rows)
    class_metrics = {}
    for class_name in sorted({row["class"] for row in rows}):
        class_rows = [row for row in rows if row["class"] == class_name]
        class_metrics[class_name] = selected_metrics(class_rows)
    obvious_rows = [
        row for row in rows if row["class"] in gates["obvious_positive_classes"]
    ]
    obvious_metrics = selected_metrics(obvious_rows)
    obvious_metrics_by_class = {
        class_name: class_metrics[class_name]
        for class_name in gates["obvious_positive_classes"]
        if class_name in class_metrics
    }
    hard_negative_rows = [
        row for row in rows if row["class"] in gates["hard_negative_classes"]
    ]
    hard_negative_selected = sum(row["selected"] for row in hard_negative_rows)
    present_classes = {row["class"] for row in rows}
    hard_negative_coverage = (
        set(gates["hard_negative_classes"]) <= present_classes
    )
    obvious_positive_coverage = (
        set(gates["obvious_positive_classes"]) <= present_classes
    )
    reference_coverage = (
        set(gates["reference_negative_classes"]) <= present_classes
    )
    invariant_coverage = (
        set(gates["invariant_control_classes"]) <= present_classes
    )
    overhead_values = [
        row["runner"]["runtime_overhead_percent"] for row in candidates.values()
    ]
    timing_eligible = all(
        record["repetitions"] >= gates["minimum_timing_repetitions"]
        and record["runtime"].get("jobs") == gates["required_runtime_jobs"]
        for record in runtime_records
    )
    runtime_p95 = quantile(overhead_values, 0.95)
    memory_increase_percent = (
        (prototype_peak / baseline_peak - 1.0) * 100.0
    )
    invariants = invariant_metrics(rows, gates, policy)
    false_positive_group_ci = negative_group_metrics[
        "alerted_source_group_rate_95_percent_ci"
    ]
    obvious_class_recall_passes = all(
        metrics_for_class["recall_95_percent_ci"] is not None
        and metrics_for_class["recall_95_percent_ci"]["low"]
        >= gates["minimum_obvious_positive_recall_lower_95"]
        for metrics_for_class in obvious_metrics_by_class.values()
    )
    gate_results = {
        "minimum_negative_source_groups": (
            negative_group_metrics["negative_source_group_count"]
            >= gates["minimum_negative_source_groups"]
        ),
        "zero_observed_false_positives": (
            metrics["false_positive_count"]
            <= gates["maximum_observed_false_positive_count"]
            and negative_group_metrics["alerted_source_group_count"] == 0
        ),
        "false_positive_upper_95": (
            false_positive_group_ci is not None
            and false_positive_group_ci["high"]
            <= gates["maximum_false_positive_upper_95"]
        ),
        "required_class_coverage": (
            hard_negative_coverage
            and obvious_positive_coverage
            and reference_coverage
            and invariant_coverage
        ),
        "hard_negative_classes": (
            hard_negative_coverage and hard_negative_selected == 0
        ),
        "obvious_positive_recall": (
            obvious_positive_coverage
            and obvious_class_recall_passes
        ),
        "two_reason_families": all(
            len(row["passing_reason_families"])
            >= policy["minimum_reason_family_count"]
            for row in rows
            if row["selected"]
        ),
        "invariant_measurement_stability": (
            reference_coverage
            and invariant_coverage
            and invariants["comparison_count"] > 0
            and invariants["complete_source_group_count"]
            >= gates["minimum_invariant_source_groups"]
            and invariants["missing_pair_count"] == 0
            and invariants["maximum_relative_delta"]
            <= gates["maximum_invariant_relative_delta"]
        ),
        "runtime_overhead": (
            timing_eligible
            and runtime_p95 is not None
            and runtime_p95
            <= gates["maximum_p95_runtime_overhead_percent"]
        ),
        "peak_memory": (
            memory_increase_percent
            <= gates["maximum_peak_memory_increase_percent"]
        ),
    }
    passed = all(gate_results.values())
    result = {
        "schema_version": 1,
        "freeze_id": freeze["freeze_id"],
        "seal_id": seal["seal_id"],
        "evaluated_at": now(),
        "pre_open_seal_sha256": pre_open_seal_sha256,
        "freeze_sha256": sha256_file(freeze_path),
        "policy_and_gate_digest": freeze["policy_and_gate_digest"],
        "disposition": {
            "state": "release_gate_passed" if passed else "release_gate_failed",
            "release_gate_passed": passed,
            "eligible_for_integration_review": passed,
            "public_verdict_enabled": False,
            "reason": (
                "All frozen gates passed; product integration still requires "
                "explicit review."
                if passed
                else "One or more frozen gates failed; the positive verdict "
                "must remain disabled and this held-out set must not be retuned."
            ),
        },
        "gate_results": gate_results,
        "metrics": metrics,
        "negative_source_group_metrics": negative_group_metrics,
        "metrics_by_class": class_metrics,
        "obvious_positive_metrics": obvious_metrics,
        "obvious_positive_metrics_by_class": obvious_metrics_by_class,
        "hard_negative_selected_count": hard_negative_selected,
        "negative_source_group_count": negative_group_metrics[
            "negative_source_group_count"
        ],
        "invariant_measurements": invariants,
        "runtime": {
            "eligible": timing_eligible,
            "p95_overhead_percent": runtime_p95,
            "component_reports": runtime_records,
        },
        "peak_memory": {
            "measurement_method": memory.get("measurement_method"),
            "baseline_peak_rss_bytes": baseline_peak,
            "prototype_peak_rss_bytes": prototype_peak,
            "increase_percent": memory_increase_percent,
        },
        "results": [
            {
                key: value
                for key, value in row.items()
                if key != "features"
            }
            for row in rows
        ],
    }
    write_private_atomic(output_path, result)
    seal = load_json(seal_path)
    seal["state"] = "evaluated"
    seal["evaluation_completed_at"] = now()
    seal["evaluation_output_path"] = str(output_path)
    seal["evaluation_output_sha256"] = sha256_file(output_path)
    seal["release_gate_passed"] = passed
    replace_private_atomic(seal_path, seal)
    print(
        f"opened sealed labels exactly once; release gate "
        f"{'passed' if passed else 'failed'}"
    )
    return 0 if passed else 2


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    seal = commands.add_parser("seal")
    seal.add_argument("--manifest", type=Path, required=True)
    seal.add_argument("--fingerprints", type=Path, required=True)
    seal.add_argument("--seal-id", required=True)
    seal.add_argument(
        "--minimum-negative-source-groups",
        type=int,
        default=150,
    )
    seal.add_argument("--blind-manifest", type=Path, required=True)
    seal.add_argument("--labels", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    seal.set_defaults(function=command_seal)

    freeze = commands.add_parser("freeze")
    freeze.add_argument("--development-report", type=Path, required=True)
    freeze.add_argument(
        "--development-manifest",
        type=Path,
        action="append",
        required=True,
    )
    freeze.add_argument(
        "--development-fingerprints",
        type=Path,
        action="append",
        required=True,
    )
    freeze.add_argument(
        "--development-candidate",
        type=Path,
        action="append",
        required=True,
    )
    freeze.add_argument("--runner", type=Path, required=True)
    freeze.add_argument("--heldout-seal", type=Path, required=True)
    freeze.add_argument("--freeze-id", required=True)
    freeze.add_argument("--minimum-development-recall", type=float, required=True)
    freeze.add_argument("--minimum-heldout-recall", type=float, required=True)
    freeze.add_argument(
        "--maximum-false-positive-upper-95",
        type=float,
        required=True,
    )
    freeze.add_argument(
        "--minimum-negative-source-groups",
        type=int,
        default=150,
    )
    freeze.add_argument(
        "--minimum-invariant-source-groups",
        type=int,
        default=40,
    )
    freeze.add_argument(
        "--maximum-invariant-relative-delta",
        type=float,
        required=True,
    )
    freeze.add_argument(
        "--maximum-p95-runtime-overhead-percent",
        type=float,
        default=10.0,
    )
    freeze.add_argument(
        "--maximum-peak-memory-increase-percent",
        type=float,
        required=True,
    )
    freeze.add_argument(
        "--minimum-timing-repetitions",
        type=int,
        default=3,
    )
    freeze.add_argument(
        "--obvious-positive-class",
        action="append",
        required=True,
    )
    freeze.add_argument(
        "--hard-negative-class",
        action="append",
        required=True,
    )
    freeze.add_argument(
        "--reference-negative-class",
        action="append",
        required=True,
    )
    freeze.add_argument(
        "--invariant-control-class",
        action="append",
        required=True,
    )
    freeze.add_argument("--output", type=Path, required=True)
    freeze.set_defaults(function=command_freeze)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--freeze", type=Path, required=True)
    evaluate.add_argument("--seal", type=Path, required=True)
    evaluate.add_argument("--blind-manifest", type=Path, required=True)
    evaluate.add_argument("--labels", type=Path, required=True)
    evaluate.add_argument("--fingerprints", type=Path, required=True)
    evaluate.add_argument("--candidate", type=Path, action="append", required=True)
    evaluate.add_argument("--memory-report", type=Path, required=True)
    evaluate.add_argument("--confirm-seal-id", required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.set_defaults(function=command_evaluate)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.function(arguments))
