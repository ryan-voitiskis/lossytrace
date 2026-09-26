"""Shared, verdict-free helpers for the v2 development baselines."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PLAN_ID = "lossytrace-v2-development-baselines-20260802-001"
ANALYSIS_MANIFEST_ID = "lossytrace-v2-factorial-manifest-20260802-001"
MECHANISM_PARTITION = "mechanism_development"
EXPECTED_CASE_COUNT = 9_653
EXPECTED_UNIQUE_PCM_COUNT = 7_701
EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT = 9_513
EXPECTED_SOURCE_GROUP_COUNT = 527
EXPECTED_DOMAINS = {
    "demand_maestro_consumed_transfer",
    "musdb18hq_consumed_transfer",
    "nsynth_test_sparse",
    "nsynth_train_sparse",
    "private_full_mix_training",
    "public_tier_a_controlled",
}
FORBIDDEN_PUBLIC_KEYS = {
    "audio_sha256",
    "case_id",
    "member_id",
    "partition_group",
    "pcm_sha256",
    "relative_path",
    "source_group",
}


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, allow_nan=False, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
        output.flush()
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(prefix: bytes, value: object) -> str:
    encoded = json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(prefix + encoded).hexdigest()


def safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} is absent")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\0" in value:
        raise ValueError(f"{label} is unsafe")
    return value


def resolve_beneath(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / safe_relative_path(relative, "artifact path")).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("artifact path escapes the benchmark root") from error
    return path


def assert_public_path_free(value: object, key: str | None = None) -> None:
    if key in FORBIDDEN_PUBLIC_KEYS:
        raise ValueError(f"public result contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_public_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_public_path_free(child, key)
    elif isinstance(value, str) and value.startswith("/"):
        raise ValueError("public result contains an absolute path")


def _checkpoint_case_id(checkpoint: dict[str, Any]) -> str:
    assignment_id = checkpoint.get("cell", {}).get("assignment_id")
    if not isinstance(assignment_id, str) or len(assignment_id) != 64:
        raise ValueError("constructor checkpoint assignment identity is invalid")
    return f"case-{assignment_id}"


def load_development_cases(
    analysis_manifest: dict[str, Any], constructor_manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    if (
        analysis_manifest.get("schema_version") != 2
        or analysis_manifest.get("manifest_id") != ANALYSIS_MANIFEST_ID
        or analysis_manifest.get("features_computed") is not False
        or analysis_manifest.get("scores_opened") is not False
        or analysis_manifest.get("public_verdict_enabled") is not False
        or constructor_manifest.get("features_computed") is not False
        or constructor_manifest.get("scores_opened") is not False
        or constructor_manifest.get("public_verdict_enabled") is not False
    ):
        raise ValueError("private input manifest state differs")
    checkpoints = {
        _checkpoint_case_id(row): row
        for row in constructor_manifest.get("checkpoints", [])
    }
    if len(checkpoints) != len(constructor_manifest.get("checkpoints", [])):
        raise ValueError("constructor checkpoint identities are not unique")

    cases: list[dict[str, Any]] = []
    all_manifest_ids = {
        row.get("case_id") for row in analysis_manifest.get("cases", [])
    }
    if None in all_manifest_ids or len(all_manifest_ids) != len(
        analysis_manifest.get("cases", [])
    ):
        raise ValueError("analysis case identities are invalid")
    for source in analysis_manifest.get("cases", []):
        if source.get("evidence_partition") != MECHANISM_PARTITION:
            continue
        case = dict(source)
        case_id = case["case_id"]
        checkpoint = checkpoints.get(case_id)
        if checkpoint is None:
            raise ValueError(f"development case has no checkpoint: {case_id}")
        pcm = checkpoint.get("analysis_pcm", {})
        cell = checkpoint.get("cell", {})
        if (
            checkpoint.get("artifact_sha256") != case.get("audio_sha256")
            or checkpoint.get("artifact_bytes") != case.get("audio_bytes")
            or checkpoint.get("artifact_relative_path") != case.get("relative_path")
            or pcm.get("frame_count") != case.get("frame_count")
            or pcm.get("sample_rate_hz") != case.get("sample_rate_hz")
            or pcm.get("channel_count") != case.get("channel_count")
            or pcm.get("sample_width_bytes") != 2
            or cell.get("group_id") != case.get("source_group")
            or cell.get("evidence_partition") != MECHANISM_PARTITION
            or cell.get("expectation") != case.get("expectation")
        ):
            raise ValueError(f"analysis and construction records differ: {case_id}")
        pcm_sha256 = pcm.get("pcm_sha256")
        if not isinstance(pcm_sha256, str) or len(pcm_sha256) != 64:
            raise ValueError(f"analysis PCM identity is invalid: {case_id}")
        reference = case.get("reference_case_id")
        if case.get("expectation") == "controlled_positive":
            if reference not in all_manifest_ids:
                raise ValueError(f"positive reference is absent: {case_id}")
        elif case.get("expectation") != "negative":
            raise ValueError(f"development expectation differs: {case_id}")
        case["_analysis_pcm_sha256"] = pcm_sha256
        cases.append(case)

    cases.sort(key=lambda row: row["case_id"])
    if (
        len(cases) != EXPECTED_CASE_COUNT
        or len({row["source_group"] for row in cases}) != EXPECTED_SOURCE_GROUP_COUNT
        or {row["source_domain"] for row in cases} != EXPECTED_DOMAINS
        or sum(row["expectation"] == "controlled_positive" for row in cases)
        != 4_988
        or sum(row["expectation"] == "negative" for row in cases) != 4_665
    ):
        raise ValueError("mechanism-development population differs")
    by_id = {row["case_id"]: row for row in cases}
    for case in cases:
        if case["expectation"] != "controlled_positive":
            continue
        reference = by_id.get(case["reference_case_id"])
        if reference is None or any(
            reference[field] != case[field]
            for field in ("source_group", "partition_group", "evidence_partition")
        ):
            raise ValueError(f"matched development reference differs: {case['case_id']}")
    return cases


def representatives_by_pcm_and_wrapper(
    cases: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for case in cases:
        key = (case["_analysis_pcm_sha256"], case["lossless_wrapper_id"])
        previous = selected.get(key)
        if previous is None or case["case_id"] < previous["case_id"]:
            selected[key] = case
    output = sorted(selected.values(), key=lambda row: row["case_id"])
    if len(output) != EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT:
        raise ValueError("PCM/wrapper representative count differs")
    return output


def representatives_by_pcm(
    cases: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for case in cases:
        key = case["_analysis_pcm_sha256"]
        previous = selected.get(key)
        if previous is None or case["case_id"] < previous["case_id"]:
            selected[key] = case
    output = sorted(selected.values(), key=lambda row: row["case_id"])
    if len(output) != EXPECTED_UNIQUE_PCM_COUNT:
        raise ValueError("unique analysis-PCM count differs")
    return output


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "median": statistics.median(values) if values else None,
        "p05": quantile(values, 0.05),
        "p95": quantile(values, 0.95),
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def wilson_lower(successes: int, total: int, z: float = 1.6448536269514722) -> float | None:
    if total <= 0 or not 0 <= successes <= total:
        return None
    proportion = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = proportion + z2 / (2.0 * total)
    spread = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z2 / (4.0 * total * total)
    )
    return (centre - spread) / denominator


def paired_effects(
    cases: list[dict[str, Any]], scores: dict[str, float]
) -> dict[str, Any]:
    by_id = {row["case_id"]: row for row in cases}
    unique_pairs: dict[tuple[str, str], dict[str, Any]] = {}
    eligible_pair_cell_count = 0
    for case in cases:
        if case["expectation"] != "controlled_positive":
            continue
        reference = by_id[case["reference_case_id"]]
        if (
            case["_analysis_pcm_sha256"] not in scores
            or reference["_analysis_pcm_sha256"] not in scores
        ):
            continue
        eligible_pair_cell_count += 1
        key = (
            case["_analysis_pcm_sha256"],
            reference["_analysis_pcm_sha256"],
        )
        delta = scores[case["_analysis_pcm_sha256"]] - scores[
            reference["_analysis_pcm_sha256"]
        ]
        row = {
            "delta": delta,
            "source_group": case["source_group"],
            "source_domain": case["source_domain"],
            "codec_family": case["codec_family"],
            "encoder_lineage": case["encoder_lineage_id"],
            "encoder_setting": case["encoder_setting_id"],
            "post_transform": (
                case["post_transform_ids"][0]
                if case.get("post_transform_ids")
                else "identity"
            ),
        }
        previous = unique_pairs.get(key)
        if previous is not None and any(
            previous[field] != row[field]
            for field in ("source_group", "source_domain", "codec_family")
        ):
            raise ValueError("identical PCM pair crosses a primary grouping factor")
        # Some intentionally redundant wrapper/factorial cells are observationally
        # identical. Count the PCM pair once and give identity the stable attribution.
        attribution_key = lambda value: (
            value["post_transform"] != "identity",
            value["post_transform"],
            value["encoder_lineage"],
            value["encoder_setting"],
        )
        if previous is None or attribution_key(row) < attribution_key(previous):
            unique_pairs[key] = row

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_group: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            by_group[row["source_group"]].append(row["delta"])
        group_deltas = [statistics.median(values) for values in by_group.values()]
        positive = sum(value > 0.0 for value in group_deltas)
        return {
            "unique_pcm_pair_count": len(rows),
            "source_group_count": len(group_deltas),
            "positive_direction_source_group_count": positive,
            "zero_direction_source_group_count": sum(
                value == 0.0 for value in group_deltas
            ),
            "negative_direction_source_group_count": sum(
                value < 0.0 for value in group_deltas
            ),
            "positive_direction_rate": positive / len(group_deltas)
            if group_deltas
            else None,
            "one_sided_95_percent_wilson_lower": wilson_lower(
                positive, len(group_deltas)
            ),
            "group_median_delta": numeric_summary(group_deltas),
        }

    rows = list(unique_pairs.values())
    output: dict[str, Any] = {"overall": summarize(rows)}
    output["overall"]["eligible_factorial_pair_cell_count"] = (
        eligible_pair_cell_count
    )
    output["overall"]["collapsed_factorial_alias_count"] = (
        eligible_pair_cell_count - len(rows)
    )
    for field in (
        "source_domain",
        "codec_family",
        "encoder_lineage",
        "encoder_setting",
        "post_transform",
    ):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row[field]].append(row)
        output[f"by_{field}"] = {
            name: summarize(group_rows) for name, group_rows in sorted(grouped.items())
        }
    return output
