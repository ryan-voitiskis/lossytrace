#!/usr/bin/env python3
"""Compose the retained, already-observed corpora into one private manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Component:
    relative_manifest: str
    corpus_id: str
    source_domain: str
    expected_cases: int


COMPONENTS = (
    Component(
        "private-compact-training-corpora/20260731-001/manifest.json",
        "audio-integrity-private-compact-training-20260731-001",
        "private_full_mix_training",
        520,
    ),
    Component(
        "public-sparse-training-corpora/20260731-001/manifest.json",
        "audio-integrity-nsynth-sparse-training-20260731-001",
        "nsynth_train_sparse",
        1_200,
    ),
    Component(
        "public-negative-corpora/20260730-001/manifest.json",
        "audio-integrity-public-tier-a-development-negatives-20260730-001",
        "public_tier_a_originals",
        48,
    ),
    Component(
        "public-controlled-transcodes/20260730-001/manifest.json",
        "audio-integrity-public-tier-a-controlled-transcodes-20260730-001",
        "public_tier_a_controlled",
        288,
    ),
    Component(
        "public-hard-negative-corpora/20260731-001/manifest.json",
        "audio-integrity-nsynth-hard-negatives-v1",
        "nsynth_test_sparse",
        318,
    ),
    Component(
        "external-transfer-sqam/20260731-001/manifest.json",
        "audio-integrity-external-transfer-sqam-20260731-001",
        "sqam_consumed_transfer",
        700,
    ),
    Component(
        "external-transfer-musdb18hq-controlled/20260731-001/manifest.json",
        "audio-integrity-musdb18hq-controlled-20260731-001",
        "musdb18hq_consumed_transfer",
        1_770,
    ),
    Component(
        "external-transfer-independent-controlled-v29/20260731-001/manifest.json",
        "audio-integrity-independent-controlled-v29-20260731-001",
        "demand_maestro_consumed_transfer",
        436,
    ),
)

EXPECTED_CASES = 5_280
EXPECTED_SOURCE_GROUPS = 597


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise ValueError(f"refusing to replace existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def compose(corpus_root: Path) -> dict:
    corpus_root = corpus_root.expanduser().resolve()
    if not corpus_root.is_dir():
        raise ValueError(f"corpus root does not exist: {corpus_root}")

    cases: list[dict] = []
    records: list[dict] = []
    seen_case_ids: set[str] = set()
    for component in COMPONENTS:
        manifest_path = corpus_root / component.relative_manifest
        manifest = load_object(manifest_path)
        if manifest.get("schema_version") != 1:
            raise ValueError(f"{manifest_path}: schema_version must be 1")
        if manifest.get("corpus_id") != component.corpus_id:
            raise ValueError(
                f"{manifest_path}: unexpected corpus_id {manifest.get('corpus_id')!r}"
            )
        component_cases = manifest.get("cases")
        if not isinstance(component_cases, list):
            raise ValueError(f"{manifest_path}: cases must be an array")
        if len(component_cases) != component.expected_cases:
            raise ValueError(
                f"{manifest_path}: expected {component.expected_cases} cases, "
                f"found {len(component_cases)}"
            )
        component_root = Path(component.relative_manifest).parent
        for source_case in component_cases:
            case = dict(source_case)
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise ValueError(f"{manifest_path}: case_id is required")
            if case_id in seen_case_ids:
                raise ValueError(f"duplicate case_id across components: {case_id}")
            seen_case_ids.add(case_id)
            relative_path = case.get("relative_path")
            if not isinstance(relative_path, str) or not relative_path:
                raise ValueError(f"{manifest_path}: {case_id} has no relative_path")
            combined_path = component_root / relative_path
            if combined_path.is_absolute() or ".." in combined_path.parts:
                raise ValueError(f"{manifest_path}: unsafe relative path for {case_id}")
            case["relative_path"] = combined_path.as_posix()
            case["original_split"] = case.get("split")
            case["split"] = "development"
            case["evidence_partition"] = "observed_development"
            case["source_domain"] = component.source_domain
            case["source_corpus_id"] = component.corpus_id
            cases.append(case)
        records.append(
            {
                "corpus_id": component.corpus_id,
                "case_count": len(component_cases),
                "manifest_relative_path": component.relative_manifest,
                "manifest_sha256": sha256_file(manifest_path),
                "source_domain": component.source_domain,
            }
        )

    source_groups = {case["source_group"] for case in cases}
    if len(cases) != EXPECTED_CASES:
        raise ValueError(f"expected {EXPECTED_CASES} total cases, found {len(cases)}")
    if len(source_groups) != EXPECTED_SOURCE_GROUPS:
        raise ValueError(
            f"expected {EXPECTED_SOURCE_GROUPS} source groups, found {len(source_groups)}"
        )
    return {
        "schema_version": 1,
        "composition_schema_version": 1,
        "corpus_id": "audio-integrity-observed-baseline-20260801-001",
        "corpus_version": 1,
        "audio_root_env": "LOSSYTRACE_RESEARCH_ROOT",
        "analysis_max_seconds": 30.0,
        "repetitions": 1,
        "evidence_partition": "observed_development",
        "holdout_scores_opened": False,
        "component_manifests": records,
        "cases": sorted(cases, key=lambda case: case["case_id"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = compose(args.corpus_root)
        write_new(args.output.expanduser().resolve(), manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"wrote {len(manifest['cases'])} observed cases from "
        f"{len(manifest['component_manifests'])} retained manifests to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
