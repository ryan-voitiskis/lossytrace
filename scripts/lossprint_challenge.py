#!/usr/bin/env python3
"""Prospective, metadata-only selection for the fixed Lossprint challenge.

No audio decoder or inference is invoked by this module. Private output stays
outside the repository; only aggregate counts and binding hashes are public.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audio_integrity_v2_baseline_common import (
    EXPECTED_DOMAINS, assert_public_path_free, load_development_cases,
    load_object, resolve_beneath, sha256_file,
)

ANALYSIS_SHA = "0937dfec3f9d5d203ec3d8c1700a3ae947226999e72a379b226c4c825fab96f9"
CONSTRUCTOR_SHA = "0fe9bde6eed57a61d3c721d5bfd8cd36031b9981442c39dc502162aeeab3a1b1"
SEED = "lossprint-first-challenge-20260927:"
DESIGN = Path(__file__).resolve().parents[1] / "docs/research/lossprint-first-challenge-design-20260927.md"


def write_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")


def select_cases(cases: list[dict], domains: set[str] = EXPECTED_DOMAINS,
                 per_domain: int = 5, cap: int = 1200) -> tuple[list[dict], list[dict]]:
    if not cases or any(c["evidence_partition"] != "mechanism_development" for c in cases):
        raise ValueError("only nonempty mechanism development may be selected")
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate case identity")
    if {c["source_domain"] for c in cases} != domains:
        raise ValueError("source domains differ")
    selected = set()
    for domain in sorted(domains):
        groups = {c["source_group"] for c in cases if c["source_domain"] == domain}
        if len(groups) < per_domain:
            raise ValueError("insufficient groups for fixed selection")
        ranking = sorted(groups, key=lambda g: (hashlib.sha256((SEED + g).encode()).hexdigest(), g))
        selected.update((domain, g) for g in ranking[:per_domain])
    rows = sorted((dict(c) for c in cases if (c["source_domain"], c["source_group"]) in selected),
                  key=lambda c: c["case_id"])
    by_id = {c["case_id"]: c for c in rows}
    for c in rows:
        if c["expectation"] == "controlled_positive":
            ref = by_id.get(c["reference_case_id"])
            if ref is None or ref["expectation"] != "negative" or any(
                ref[k] != c[k] for k in ("source_group", "source_domain", "partition_group")
            ):
                raise ValueError("selected positive lacks in-population negative reference")
        elif c["expectation"] != "negative":
            raise ValueError("unknown label")
    representatives = {}
    artifact_keys = {}
    for c in rows:
        key = (c["_analysis_pcm_sha256"], c["lossless_wrapper_id"])
        if c["audio_sha256"] in artifact_keys and artifact_keys[c["audio_sha256"]] != key:
            raise ValueError("artifact identity maps to inconsistent PCM/wrapper")
        artifact_keys[c["audio_sha256"]] = key
        rep = representatives.setdefault(key, c)
        if any(rep[k] != c[k] for k in ("audio_sha256", "audio_bytes", "frame_count",
                                       "sample_rate_hz", "channel_count")):
            raise ValueError("PCM/wrapper aliases do not have identical artifact metadata")
        c["representative_case_id"] = rep["case_id"]
    if len(representatives) > cap:
        raise ValueError("selection exceeds prospective artifact cap; do not truncate")
    return rows, sorted(representatives.values(), key=lambda c: c["case_id"])


def unsupported_reason(c: dict) -> str | None:
    if c["channel_count"] not in (1, 2):
        return "channels_outside_mono_stereo"
    if not 8000 <= c["sample_rate_hz"] <= 384000:
        return "sample_rate_outside_8k_384k"
    if c["frame_count"] < 2 * c["sample_rate_hz"]:
        return "duration_below_two_seconds"
    return None


def summarize(rows: list[dict], representatives: list[dict]) -> dict:
    domains = {}
    for domain in sorted({c["source_domain"] for c in rows}):
        subset = [c for c in rows if c["source_domain"] == domain]
        domains[domain] = {
            "groups": len({c["source_group"] for c in subset}),
            "cases": len(subset),
            "labels": dict(sorted(Counter(c["expectation"] for c in subset).items())),
            "codecs": dict(sorted(Counter(c.get("codec_family") or "none" for c in subset).items())),
            "history_classes": dict(sorted(Counter(c["history_class"] for c in subset).items())),
            "post_transforms": dict(sorted(Counter(
                "+".join(c.get("post_transform_ids", [])) or "identity" for c in subset).items())),
            "declared_unsupported_cases": sum(unsupported_reason(c) is not None for c in subset),
        }
    result = {"schema_version": 1, "purpose": "metadata_only_fixed_selection",
              "case_count": len(rows), "artifact_count": len(representatives),
              "unique_pcm_count": len({c["_analysis_pcm_sha256"] for c in rows}),
              "domain_group_entries": sum(d["groups"] for d in domains.values()),
              "planned_slots": 2 * len(representatives), "domains": domains,
              "minimum_seconds": min(c["frame_count"] / c["sample_rate_hz"] for c in rows),
              "maximum_seconds": max(c["frame_count"] / c["sample_rate_hz"] for c in rows),
              "waveforms_opened": False, "scores_opened": False, "public_verdict_enabled": False}
    assert_public_path_free(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--constructor", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if sha256_file(args.analysis) != ANALYSIS_SHA or sha256_file(args.constructor) != CONSTRUCTOR_SHA:
        raise ValueError("historical manifest hashes differ")
    rows, reps = select_cases(load_development_cases(load_object(args.analysis), load_object(args.constructor)))
    for c in rows:
        # Containment and file metadata only: no waveform bytes opened here.
        artifact = resolve_beneath(args.audio_root, c["relative_path"])
        if not artifact.is_file() or artifact.stat().st_size != c["audio_bytes"]:
            raise ValueError("relocated artifact absent or size differs")
        c["declared_unsupported_reason"] = unsupported_reason(c)
    bindings = {"analysis_manifest_sha256": ANALYSIS_SHA, "constructor_manifest_sha256": CONSTRUCTOR_SHA,
                "selector_sha256": sha256_file(Path(__file__)), "design_sha256": sha256_file(DESIGN),
                "common_module_sha256": sha256_file(Path(__file__).with_name("audio_integrity_v2_baseline_common.py"))}
    public = summarize(rows, reps)
    args.output.mkdir(parents=False, exist_ok=False)
    private = {"bindings": bindings, "audio_root": str(args.audio_root.resolve()), "cases": rows,
               "representative_ids": [c["case_id"] for c in reps]}
    write_new(args.output / "selection-private.json", private)
    public.update(bindings)
    public["private_selection_sha256"] = sha256_file(args.output / "selection-private.json")
    assert_public_path_free(public)
    write_new(args.output / "selection-public.json", public)
    print(json.dumps(public, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
