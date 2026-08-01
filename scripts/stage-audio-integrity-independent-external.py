#!/usr/bin/env python3
"""Stage the compact independent PCM external-transfer corpus.

The implementation reuses the already tested journal, recovery, transform,
and sealing machinery from the MUSDB stager while changing the corpus
contract, source inventory, class namespace, and frozen-candidate checks.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "stage-audio-integrity-musdb18hq-external.py"
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_controlled_stager_base",
    BASE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"cannot load controlled stager base: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

RUN_ID = "audio-integrity-independent-pcm-gate-20260731-001"
CORPUS_ID = "audio-integrity-independent-controlled-v29-20260731-001"
CORPUS_VERSION = 1
CANDIDATE_ID = (
    "verified-mp3-two-grid-edge-v29-independent-transfer-v1"
)
PROFILE = "verified-mp3-two-grid-v29"
EXPECTED_SOURCE_COUNT = 36
INVARIANT_SOURCE_COUNT = 10
EXPECTED_CASE_COUNT = (
    EXPECTED_SOURCE_COUNT * 11 + INVARIANT_SOURCE_COUNT * 4
)
EXPECTED_NEGATIVE_COUNT = EXPECTED_SOURCE_COUNT * 4
EXPECTED_POSITIVE_COUNT = EXPECTED_CASE_COUNT - EXPECTED_NEGATIVE_COUNT
EXPECTED_GROUP_COUNT = EXPECTED_SOURCE_COUNT * 11
CORPUS_TERMS = (
    "MAESTRO 3.0.0 CC BY-NC-SA 4.0 and DEMAND attribution/share-alike "
    "local non-commercial research evidence only; preserve attribution "
    "and do not ship the audio with Reklawdbox."
)

BASE.RUN_ID = RUN_ID
BASE.CORPUS_ID = CORPUS_ID
BASE.CORPUS_VERSION = CORPUS_VERSION
BASE.CANDIDATE_ID = CANDIDATE_ID
BASE.PROFILE = PROFILE
BASE.EXPECTED_SOURCE_RUN_ID = RUN_ID
BASE.EXPECTED_SOURCE_COUNT = EXPECTED_SOURCE_COUNT
BASE.INVARIANT_SOURCE_COUNT = INVARIANT_SOURCE_COUNT
BASE.CORPUS_TERMS = CORPUS_TERMS

ORIGINAL_BUILD_PLAN = BASE.build_plan


def tool_commitment() -> dict:
    return {
        "path": str(Path(__file__).resolve()),
        "sha256": BASE.sha256_file(Path(__file__).resolve()),
        "base_path": str(BASE_PATH),
        "base_sha256": BASE.sha256_file(BASE_PATH),
    }


def build_plan(acquisition_path: Path, acquisition: dict) -> dict:
    BASE.INVARIANT_SOURCE_COUNT = 0
    try:
        plan = ORIGINAL_BUILD_PLAN(acquisition_path, acquisition)
    finally:
        BASE.INVARIANT_SOURCE_COUNT = INVARIANT_SOURCE_COUNT
    invariant_sources = set()
    for provider in ("demand-v1.0", "maestro-v3.0.0"):
        ranked = sorted(
            (
                record
                for record in acquisition["completed"]
                if record["provider"] == provider
            ),
            key=lambda record: hashlib.sha256(
                (
                    record["source_id"]
                    + ":"
                    + record["output_sha256"]
                ).encode()
            ).hexdigest(),
        )
        invariant_sources.update(
            record["source_id"] for record in ranked[:5]
        )
    if len(invariant_sources) != INVARIANT_SOURCE_COUNT:
        raise SystemExit("balanced invariant source inventory differs")
    group_by_id = {
        group["group_id"]: group
        for group in plan["transformation_groups"]
    }
    invariant_specs = (
        (
            "aac-lc-128-gain-minus3db-to-flac16",
            "musdb_aac_lc_128_gain_minus3db_to_flac16",
            ".flac",
            "flac16",
            "volume=-3dB",
        ),
        (
            "aac-lc-128-trim-137-to-flac16",
            "musdb_aac_lc_128_trim_137_to_flac16",
            ".flac",
            "flac16",
            "atrim=start_sample=137",
        ),
        (
            "aac-lc-128-to-wav16",
            "musdb_aac_lc_128_to_wav16",
            ".wav",
            "wav16",
            None,
        ),
        (
            "aac-lc-128-to-aiff24",
            "musdb_aac_lc_128_to_aiff24",
            ".aiff",
            "aiff24",
            None,
        ),
    )
    for source_id in sorted(invariant_sources):
        group = group_by_id[f"{source_id}-aac-lc-128"]
        for suffix, class_name, extension, kind, post_filter in invariant_specs:
            value = BASE.case(
                source_id,
                suffix,
                class_name=class_name,
                expectation="controlled_positive",
                extension=extension,
            )
            plan["manifest"]["cases"].append(value)
            group["outputs"].append(
                BASE.output(
                    value,
                    kind=kind,
                    post_filter=post_filter,
                )
            )
    plan["manifest"]["cases"].sort(
        key=lambda value: value["case_id"]
    )
    plan["corpus"]["case_count"] = len(plan["manifest"]["cases"])
    plan["corpus"]["controlled_positive_count"] += (
        INVARIANT_SOURCE_COUNT * 4
    )
    plan["corpus"]["invariant_source_count"] = INVARIANT_SOURCE_COUNT
    plan["corpus"]["invariant_source_ids"] = sorted(invariant_sources)
    plan["transformation_inventory_sha256"] = BASE.canonical_sha256(
        plan["transformation_groups"]
    )
    seen_cases: set[int] = set()
    case_values = list(plan["manifest"]["cases"])
    case_values.extend(
        output["case"]
        for group in plan["transformation_groups"]
        for output in group["outputs"]
    )
    for value in case_values:
        identity = id(value)
        if identity in seen_cases:
            continue
        seen_cases.add(identity)
        class_name = value["class"]
        if not class_name.startswith("musdb_"):
            raise SystemExit(f"unexpected inherited class: {class_name}")
        value["class"] = "independent_" + class_name.removeprefix(
            "musdb_"
        )
    cases = plan["manifest"]["cases"]
    plan["manifest"]["audio_root_env"] = (
        "LOSSYTRACE_RESEARCH_INDEPENDENT_EXTERNAL_ROOT"
    )
    plan["manifest"]["usage_terms"] = CORPUS_TERMS
    plan["corpus"]["terms"] = CORPUS_TERMS
    plan["corpus"]["provider_counts"] = dict(
        sorted(
            Counter(
                record["provider"]
                for record in acquisition["completed"]
            ).items()
        )
    )
    plan["corpus"]["class_counts"] = dict(
        sorted(Counter(value["class"] for value in cases).items())
    )
    plan["tool"] = tool_commitment()
    return plan


BASE.build_plan = build_plan


def command_plan(args: argparse.Namespace) -> int:
    acquisition_path = args.acquisition.expanduser().resolve()
    acquisition, _ = BASE.validate_acquisition(acquisition_path)
    plan = build_plan(acquisition_path, acquisition)
    if (
        plan["corpus"]["case_count"] != EXPECTED_CASE_COUNT
        or plan["corpus"]["negative_count"] != EXPECTED_NEGATIVE_COUNT
        or plan["corpus"]["controlled_positive_count"]
        != EXPECTED_POSITIVE_COUNT
        or plan["corpus"]["group_count"] != EXPECTED_GROUP_COUNT
        or plan["corpus"]["provider_counts"]
        != {"demand-v1.0": 18, "maestro-v3.0.0": 18}
    ):
        raise SystemExit("planned independent corpus inventory differs")
    BASE.write_new_json(args.output.expanduser().resolve(), plan)
    print(
        f"planned {EXPECTED_CASE_COUNT} cases from "
        f"{EXPECTED_SOURCE_COUNT} sources without opening features"
    )
    return 0


def validate_precommit(
    path: Path,
    *,
    plan_path: Path,
    plan: dict,
) -> dict:
    precommit = BASE.load_json(path)
    tools = precommit.get("tools", {})
    corpus_plan = precommit.get("corpus_plan", {})
    if (
        precommit.get("schema_version") != 1
        or precommit.get("state") != "frozen_before_external_transfer"
        or precommit.get("candidate_id") != CANDIDATE_ID
        or precommit.get("candidate_frozen") is not True
        or precommit.get("external_transfer_feature_scores_opened")
        is not False
        or precommit.get("release_heldout_opened") is not False
        or precommit.get("public_verdict_enabled") is not False
        or precommit.get("feature_version") != 0
        or precommit.get("transform_profile") != PROFILE
        or corpus_plan.get("sha256") != BASE.sha256_file(plan_path)
        or corpus_plan.get("transformation_inventory_sha256")
        != plan["transformation_inventory_sha256"]
        or tools.get("stager_sha256")
        != BASE.sha256_file(Path(__file__).resolve())
        or tools.get("base_stager_sha256")
        != BASE.sha256_file(BASE_PATH)
    ):
        raise SystemExit("frozen independent candidate/stager differs")
    return precommit


BASE.validate_precommit = validate_precommit


def command_verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    state = BASE.load_json(root / "staging-state.json")
    seal = BASE.load_json(root / "seal.json")
    manifest = BASE.load_json(root / "manifest.json")
    fingerprints = BASE.load_json(root / "fingerprints.json")
    provenance = BASE.load_json(root / "provenance-ledger.json")
    plan = BASE.load_json(root / "corpus-plan.json")
    precommit = BASE.load_json(root / "candidate-precommit.json")
    if (
        state.get("state") != "staging_complete"
        or state.get("seal_sha256")
        != BASE.sha256_file(root / "seal.json")
        or seal.get("state") != "retained_controlled_corpus_complete"
        or seal.get("case_count") != EXPECTED_CASE_COUNT
        or seal.get("source_count") != EXPECTED_SOURCE_COUNT
        or seal.get("negative_count") != EXPECTED_NEGATIVE_COUNT
        or seal.get("controlled_positive_count")
        != EXPECTED_POSITIVE_COUNT
        or seal.get("external_transfer_feature_scores_opened") is not False
        or seal.get("release_heldout_opened") is not False
        or seal.get("public_verdict_enabled") is not False
        or manifest != plan.get("manifest")
        or precommit.get("candidate_id") != CANDIDATE_ID
        or fingerprints.get("case_sha256") is None
        or provenance.get("lossy_intermediates_retained") is not False
    ):
        raise SystemExit("retained independent corpus contract differs")
    expected_top_level = {
        ".partial",
        "audio",
        "candidate-precommit.json",
        "corpus-plan.json",
        "fingerprints.json",
        "manifest.json",
        "provenance-ledger.json",
        "seal.json",
        "staging-state.json",
    }
    if {path.name for path in root.iterdir()} != expected_top_level:
        raise SystemExit("retained corpus top-level inventory differs")
    audio_entries = list((root / "audio").iterdir())
    if any(
        not path.is_file() or path.is_symlink()
        for path in audio_entries
    ):
        raise SystemExit("retained audio has non-file entries")
    if {
        path.relative_to(root).as_posix() for path in audio_entries
    } != {
        value["relative_path"] for value in seal["audio_inventory"]
    }:
        raise SystemExit("retained audio file inventory differs")
    for value in seal["metadata_inventory"]:
        path = BASE.resolve_beneath(root, value["relative_path"])
        if (
            path.stat().st_size != value["bytes"]
            or BASE.sha256_file(path) != value["sha256"]
        ):
            raise SystemExit(f"{value['relative_path']}: metadata differs")
    for value in seal["audio_inventory"]:
        path = BASE.resolve_beneath(root, value["relative_path"])
        if (
            path.is_symlink()
            or path.stat().st_size != value["bytes"]
            or BASE.sha256_file(path) != value["sha256"]
            or fingerprints["case_sha256"].get(value["case_id"])
            != value["sha256"]
        ):
            raise SystemExit(f"{value['case_id']}: audio differs")
    partial = root / ".partial"
    if not partial.is_dir() or any(partial.iterdir()):
        raise SystemExit("retained corpus has unexpected partials")
    integrity = BASE.canonical_sha256(
        {
            "metadata_inventory": seal["metadata_inventory"],
            "audio_inventory": seal["audio_inventory"],
        }
    )
    if integrity != seal["integrity_sha256"]:
        raise SystemExit("retained corpus integrity commitment differs")
    print(
        f"verified {seal['case_count']} retained cases; "
        f"seal SHA-256 {BASE.sha256_file(root / 'seal.json')}"
    )
    return 0


BASE.command_plan = command_plan
BASE.command_verify = command_verify


def main() -> int:
    args = BASE.parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
