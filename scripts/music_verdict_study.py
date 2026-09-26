#!/usr/bin/env python3
"""Metadata-only independence/power preflight for the finished-music study.

This checks curated assertions and grouping, not the truth of provenance or
license statements. It never reads audio, trains a model or enables a verdict.
Only aggregate counts and errors are emitted; private identifiers stay private.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

PARTITIONS = {"train": 100, "selection": 40, "calibration": 100, "evaluation": 300}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
IDENTITY_KEYS = ("artist_ids", "session_ids", "lineage_ids")
ROW_KEYS = {
    "source_id", "partition", *IDENTITY_KEYS, "provider_id", "audio_sha256",
    "consumed", "sealed", "real_finished_music", "provenance_status",
    "rights_status", "provenance_refs", "rights_refs",
}


def _counts(k: int, n: int) -> None:
    if type(k) is not int or type(n) is not int or not 0 <= k <= n or n < 1:
        raise ValueError("counts must be integers with 0 <= k <= n and n >= 1")


def binomial_cdf(k: int, n: int, p: float) -> float:
    """P[X <= k], evaluated as a log-sum-exp to avoid endpoint underflow."""
    _counts(k, n)
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("p must be finite and in [0, 1]")
    if p == 0 or k == n:
        return 1.0
    if p == 1:
        return 0.0
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
             + i * math.log(p) + (n - i) * math.log1p(-p) for i in range(k + 1)]
    peak = max(terms)
    return min(1.0, math.exp(peak) * math.fsum(math.exp(v - peak) for v in terms))


def exact_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """One-sided Clopper-Pearson upper confidence bound, not a posterior."""
    _counts(k, n)
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be finite and between zero and one")
    if k == n:
        return 1.0
    if k == 0:
        return -math.expm1(math.log(alpha) / n)
    low, high = k / n, 1.0
    for _ in range(64):
        mid = (low + high) / 2
        if binomial_cdf(k, n, mid) > alpha:
            low = mid
        else:
            high = mid
    return high


def exact_lower(k: int, n: int, alpha: float = 0.05) -> float:
    _counts(k, n)
    return 1.0 - exact_upper(n - k, n, alpha)


def zero_alert_sample_minimum(ceiling: float = 0.01, alpha: float = 0.05) -> int:
    if not (math.isfinite(ceiling) and 0 < ceiling < 1
            and math.isfinite(alpha) and 0 < alpha < 1):
        raise ValueError("ceiling and alpha must be finite and between zero and one")
    return math.ceil(math.log(alpha) / math.log1p(-ceiling))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def _refs(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(v) for v in value)


def _identities(value: object) -> bool:
    return _refs(value) and len(value) == len(set(value))


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def audit_inventory(document: dict) -> dict:
    """Check a private, manually qualified metadata inventory; fail closed.

    Identities must be reconciled globally before this function is called.
    A source hash is an additional duplicate key, never a provenance proof.
    Shared provider alone is not a grouping edge; its generalization boundary
    is checked separately by a wholly held-out provider requirement.
    """
    if (not isinstance(document, dict) or set(document) != {"schema_version", "sources"}
            or type(document["schema_version"]) is not int or document["schema_version"] != 1
            or not isinstance(document["sources"], list)):
        raise ValueError("invalid inventory envelope")
    rows = document["sources"]
    seen = set()
    errors = Counter()
    valid = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            errors["invalid_row_schema"] += 1
            continue
        if (not all(_text(row[k]) for k in ("source_id", "provider_id"))
                or not all(_identities(row[k]) for k in IDENTITY_KEYS)
                or not isinstance(row["partition"], str) or row["partition"] not in PARTITIONS
                or not isinstance(row["audio_sha256"], str)
                or not SHA256.fullmatch(row["audio_sha256"])
                or not all(type(row[k]) is bool for k in
                           ("consumed", "sealed", "real_finished_music"))
                or not _refs(row["provenance_refs"]) or not _refs(row["rights_refs"])):
            errors["invalid_or_missing_metadata"] += 1
            continue
        if row["source_id"] in seen:
            errors["duplicate_source_id"] += 1
        seen.add(row["source_id"])
        if row["sealed"]:
            errors["historically_sealed_source"] += 1
        if row["consumed"] and row["partition"] in {"calibration", "evaluation"}:
            errors["consumed_calibration_or_evaluation"] += 1
        if not row["real_finished_music"]:
            errors["outside_finished_music_population"] += 1
        if row["provenance_status"] != "qualified_pcm_chain":
            errors["unqualified_negative_provenance"] += 1
        if row["rights_status"] not in ("research_and_weights_cleared", "research_only"):
            errors["unqualified_research_rights"] += 1
        valid.append(row)

    # Transitive artist/session/work/hash components, not nominal track count.
    parent = list(range(len(valid)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    identities = {}
    for i, row in enumerate(valid):
        for key in (*IDENTITY_KEYS, "audio_sha256"):
            values = [row[key]] if key == "audio_sha256" else row[key]
            for value in values:
                identity = (key, value)
                if identity in identities:
                    parent[root(i)] = root(identities[identity])
                else:
                    identities[identity] = i

    components = defaultdict(list)
    for i, row in enumerate(valid):
        components[root(i)].append(row)
    counts = Counter()
    eval_providers = Counter()
    non_eval_providers = set()
    for members in components.values():
        partitions = {r["partition"] for r in members}
        if len(partitions) != 1:
            errors["cross_partition_identity_component"] += 1
            continue
        partition = next(iter(partitions))
        counts[partition] += 1
        if partition in {"calibration", "evaluation"} and len(members) != 1:
            errors["multiple_representatives_in_calibration_or_evaluation"] += 1
        if partition == "evaluation":
            providers = {r["provider_id"] for r in members}
            if len(providers) != 1:
                errors["ambiguous_evaluation_provider"] += 1
            else:
                eval_providers[next(iter(providers))] += 1
        else:
            non_eval_providers.update(r["provider_id"] for r in members)
    for partition, minimum in PARTITIONS.items():
        if counts[partition] < minimum:
            errors[f"insufficient_{partition}_groups"] += 1
    if len(eval_providers) < 3:
        errors["insufficient_evaluation_provider_strata"] += 1
    if any(n < 30 for n in eval_providers.values()):
        errors["undersized_evaluation_provider_stratum"] += 1
    if not (set(eval_providers) - non_eval_providers):
        errors["no_wholly_held_out_evaluation_provider"] += 1
    rights_cleared = bool(rows) and len(valid) == len(rows) and all(
        r["rights_status"] == "research_and_weights_cleared" for r in valid)
    return {
        "schema_version": 1,
        "state": "metadata_checks_passed" if not errors else "metadata_checks_failed",
        "execution_ready": False,
        "public_verdict_enabled": False,
        "provenance_truth_verified_by_this_tool": False,
        "source_rows": len(rows),
        "identity_components": len(components),
        "groups_by_partition": {k: counts[k] for k in PARTITIONS},
        "evaluation_provider_group_counts": sorted(eval_providers.values()),
        "errors": dict(sorted(errors.items())),
        "weight_rights_asserted_cleared_for_all_rows": rights_cleared,
        "zero_alert_sample_minimum_for_one_percent": zero_alert_sample_minimum(),
        "zero_alert_upper_bound_at_300_groups": exact_upper(0, 300),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path,
                        help="private curated metadata JSON; no audio paths are accepted")
    args = parser.parse_args()
    if args.inventory is None:
        print(json.dumps({"state": "power_calculation_only", "public_verdict_enabled": False,
                          "minimum_zero_alert_groups": zero_alert_sample_minimum(),
                          "zero_alert_upper_bounds": {str(n): exact_upper(0, n)
                                                      for n in (30, 45, 47, 100, 299, 300)}},
                         indent=2, sort_keys=True))
        return 0
    try:
        with args.inventory.open("rb") as stream:
            raw = stream.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("inventory exceeds 16 MiB metadata limit")
        result = audit_inventory(json.loads(raw, object_pairs_hook=_unique_object))
        result["inventory_sha256"] = hashlib.sha256(raw).hexdigest()
    except (ValueError, TypeError, OSError):
        # Do not echo private paths, row values or JSON parser excerpts.
        print(json.dumps({"state": "invalid_inventory", "execution_ready": False,
                          "public_verdict_enabled": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "metadata_checks_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
