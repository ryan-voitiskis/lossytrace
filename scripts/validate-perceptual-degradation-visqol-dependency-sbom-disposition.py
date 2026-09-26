#!/usr/bin/env python3
"""Validate the fail-closed ViSQOL dependency and SBOM disposition."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "visqol-only-dependency-sbom-disposition.json"
)
DISPOSITION_ID = (
    "perceptual-degradation-visqol-only-dependency-sbom-disposition-20260814-001"
)
OBSERVATION_ID = (
    "perceptual-degradation-visqol-direct-dependency-license-observation-"
    "20260814-001"
)

EXPECTED_COMPONENTS = {
    "visqol": "Apache-2.0",
    "abseil-cpp": "Apache-2.0",
    "protobuf": "BSD-3-Clause",
    "tensorflow-lite": "Apache-2.0",
    "armadillo-headers": "Apache-2.0",
    "pffft": "LicenseRef-UCAR-PFFFT-Permissive",
    "libsvm": "BSD-3-Clause",
    "visqol-audio-model": "Apache-2.0-top-level-repository-record-only",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _bound(disposition: dict[str, Any], binding_id: str) -> Path:
    return ROOT / disposition["bindings"][binding_id]["path"]


def validate(disposition: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if disposition.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if disposition.get("disposition_id") != DISPOSITION_ID:
        errors.append("disposition identity differs")
    if disposition.get("state") != (
        "direct_license_screen_passed_complete_binary_sbom_and_"
        "redistribution_review_blocked"
    ):
        errors.append("disposition state differs")

    expected_bindings = {
        "successor_readiness_disposition",
        "direct_dependency_license_observation",
        "first_environment_build_observation",
        "second_environment_build_observation",
        "cross_environment_observation",
        "reproducible_workspace_patch",
    }
    if set(disposition.get("bindings", {})) != expected_bindings:
        errors.append("binding inventory differs")
    for binding_id, binding in disposition.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
    if errors:
        return errors

    observation = load_json(
        _bound(disposition, "direct_dependency_license_observation")
    )
    first_build = load_json(_bound(disposition, "first_environment_build_observation"))
    second_build = load_json(
        _bound(disposition, "second_environment_build_observation")
    )
    comparison = load_json(_bound(disposition, "cross_environment_observation"))
    successor = load_json(_bound(disposition, "successor_readiness_disposition"))

    if observation.get("observation_id") != OBSERVATION_ID:
        errors.append("direct dependency observation identity differs")
    upstream = observation.get("upstream", {})
    if (
        upstream.get("git_commit")
        != "c3aa2e498e0f7f14202643594335a0b9ee40bdd9"
        or upstream.get("production_target") != "//:visqol"
    ):
        errors.append("pinned upstream or production target differs")

    components = observation.get("declared_production_components", [])
    component_licenses = {
        item.get("component_id"): item.get("license_expression")
        for item in components
    }
    if component_licenses != EXPECTED_COMPONENTS:
        errors.append("declared production component or license set differs")
    if any(item.get("license_record_observed") is not True for item in components):
        errors.append("every declared component must bind a license record")

    screen = observation.get("screen_result", {})
    expected_true = {
        "direct_software_license_records_observed",
        (
            "direct_software_copyright_licenses_permit_redistribution_"
            "subject_to_conditions"
        ),
    }
    expected_false = {
        "model_separate_asset_notice_observed",
        "complete_transitive_dependency_closure_observed",
        "exact_binary_linkage_observed",
        "complete_binary_sbom_generated",
        "redistribution_notice_bundle_generated",
        "binary_redistribution_ready",
    }
    for key in expected_true:
        if screen.get(key) is not True:
            errors.append(f"direct screen fact must remain true: {key}")
    for key in expected_false:
        if screen.get(key) is not False:
            errors.append(f"direct screen boundary must remain false: {key}")

    first_resolution = first_build.get("repository_resolution", {})
    second_resolution = second_build.get("repository_resolution", {})
    existing = disposition.get("observed_existing_build_evidence", {})
    if (
        existing.get("repository_name_projection_count") != 46
        or first_resolution.get("repository_count") != 46
        or second_resolution.get("repository_count") != 46
        or first_resolution.get("repository_names")
        != second_resolution.get("repository_names")
    ):
        errors.append("cross-environment repository-name evidence differs")
    if (
        existing.get("first_binary_sha256")
        != first_build.get("files", {}).get("binary", {}).get("sha256")
        or existing.get("second_binary_sha256")
        != second_build.get("files", {}).get("binary", {}).get("sha256")
        or existing.get("binary_hashes_identical") is not False
    ):
        errors.append("binary identity evidence differs")
    comparison_deltas = [
        delta
        for result in comparison.get("results", [])
        for delta in result.get("absolute_deltas", {}).values()
    ]
    if (
        comparison.get("score_determinism_pass") is not True
        or not comparison_deltas
        or any(delta != 0 for delta in comparison_deltas)
        or existing.get("synthetic_scores_identical") is not True
    ):
        errors.append("synthetic score comparison differs")

    readiness = disposition.get("readiness", {})
    readiness_true = {
        "direct_declared_license_screen_complete",
        "internal_research_candidate_preregisterable",
    }
    readiness_false = {
        "direct_declared_license_conflict_observed",
        "complete_transitive_dependency_closure_available",
        "complete_binary_sbom_available",
        "redistribution_notice_bundle_available",
        "dependency_redistribution_and_sbom_review_complete",
        "binary_redistribution_ready",
        "metric_successor_selected",
        "metric_execution_ready",
        "scientific_readiness",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    }
    for key in readiness_true:
        if readiness.get(key) is not True:
            errors.append(f"readiness fact must remain true: {key}")
    for key in readiness_false:
        if readiness.get(key) is not False:
            errors.append(f"readiness boundary must remain false: {key}")
    if successor.get("readiness", {}).get(
        "dependency_redistribution_and_sbom_review_complete"
    ) is not False:
        errors.append("predecessor dependency review must remain incomplete")

    decision = disposition.get("decision", {})
    if (
        decision.get("successor_option_selected") is not None
        or decision.get("direct_license_screen_changes_successor_recommendation")
        is not False
        or decision.get("successor_remains_preregisterable") is not True
        or decision.get("successor_can_be_distributed_from_current_evidence")
        is not False
        or decision.get("successor_can_be_executed_from_current_evidence")
        is not False
        or decision.get("new_build_authorized_by_this_disposition") is not False
    ):
        errors.append("decision boundary differs")

    access = disposition.get("access_boundary", {})
    if access.get("public_text_metadata_read") is not True:
        errors.append("public text metadata read must be recorded")
    if access.get("software_source_archive_license_member_read") is not True:
        errors.append("software license-member read must be recorded")
    for key, value in access.items():
        if key not in {
            "public_text_metadata_read",
            "software_source_archive_license_member_read",
        } and value is not False:
            errors.append(f"access boundary must remain false: {key}")
    for key, value in disposition.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disposition", type=Path, default=DEFAULT_DISPOSITION)
    args = parser.parse_args()
    disposition = load_json(args.disposition)
    errors = validate(disposition)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"validated {DISPOSITION_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
