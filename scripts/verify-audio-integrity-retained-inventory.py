#!/usr/bin/env python3
"""Verify retained-corpus file commitments after a recorded relocation."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path


CORPUS_FILE_FIELDS = {
    "candidate_precommit_sha256": "candidate-precommit.json",
    "corpus_plan_sha256": "corpus-plan.json",
    "fingerprints_sha256": "fingerprints.json",
    "future_fingerprints_sha256": "future-fingerprints.json",
    "future_manifest_sha256": "future-manifest.json",
    "integrity_sha256": "integrity.json",
    "manifest_sha256": "manifest.json",
    "provenance_ledger_sha256": "provenance-ledger.json",
    "seal_sha256": "seal.json",
    "source_inventory_sha256": "source-inventory.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
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


def relocate(path_value: str, relocation: dict) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(f"inventory path is not absolute: {path_value}")
    source = Path(relocation["source"])
    destination = Path(relocation["destination"])
    try:
        relative = path.relative_to(source)
    except ValueError:
        if path.is_relative_to(destination):
            return path
        raise ValueError("inventory path is outside the recorded relocation") from None
    return destination / relative


class Verification:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def file(
        self,
        check_id: str,
        path: Path,
        expected_sha256: str,
        expected_bytes: int | None = None,
    ) -> dict:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"{check_id}: committed file is missing or not regular")
        if expected_bytes is not None and path.stat().st_size != expected_bytes:
            raise ValueError(f"{check_id}: byte count differs")
        actual = sha256_file(path)
        if actual != expected_sha256:
            raise ValueError(f"{check_id}: SHA-256 differs")
        self.checks.append(
            {
                "id": check_id,
                "kind": "file_sha256",
                "sha256": actual,
                "bytes": path.stat().st_size,
            }
        )
        return load_object(path) if path.suffix == ".json" else {}

    def semantic(self, check_id: str, passed: bool) -> None:
        if not passed:
            raise ValueError(f"{check_id}: semantic commitment differs")
        self.checks.append({"id": check_id, "kind": "semantic", "passed": True})

    def observation(self, check_id: str, passed: bool, limitation: str) -> None:
        if not passed:
            raise ValueError(f"{check_id}: observed relationship differs")
        self.checks.append(
            {
                "id": check_id,
                "kind": "informational_observation",
                "passed": True,
                "cryptographically_committed": False,
                "limitation": limitation,
            }
        )


def verify(inventory_path: Path, relocation_path: Path) -> dict:
    inventory = load_object(inventory_path)
    relocation = load_object(relocation_path)
    if inventory.get("schema_version") != 1 or relocation.get("schema_version") != 1:
        raise ValueError("inventory and relocation schemas must both be 1")
    if relocation.get("operation") != "same-filesystem-directory-rename":
        raise ValueError("unsupported relocation operation")
    source = Path(relocation.get("source", ""))
    recorded_destination = Path(relocation.get("destination", ""))
    if not source.is_absolute() or not recorded_destination.is_absolute():
        raise ValueError("relocation source and destination must be absolute")
    destination = Path(relocation["destination"]).resolve()
    if inventory_path.parent.resolve() != destination:
        raise ValueError("inventory is not at the recorded destination")

    verification = Verification()
    inventory_sha256 = sha256_file(inventory_path)
    retained = relocation.get("verification", {}).get("retained_inventory", {})
    verification.semantic(
        "relocation_inventory_binding",
        retained.get("file") == inventory_path.name
        and retained.get("sha256_before_and_after") == inventory_sha256,
    )
    inode_before = relocation.get("verification", {}).get("device_and_inode_before")
    inode_after = relocation.get("verification", {}).get("device_and_inode_after")
    verification.semantic(
        "relocation_inode_binding",
        isinstance(inode_before, str)
        and bool(inode_before)
        and inode_before == inode_after,
    )

    superseded = destination / "retained-corpora-inventory-20260731-004.json"
    verification.file(
        "superseded_inventory",
        superseded,
        inventory["superseded_inventory_sha256"],
    )

    total_cases = 0
    for corpus_index, corpus in enumerate(inventory.get("corpora", [])):
        root = relocate(corpus["root"], relocation).resolve()
        if not root.is_relative_to(destination):
            raise ValueError(f"corpus_{corpus_index}: relocated root escapes destination")
        manifest_cases_by_field: dict[str, list[dict]] = {}
        for field, file_name in CORPUS_FILE_FIELDS.items():
            expected = corpus.get(field)
            if expected is None:
                continue
            value = verification.file(
                f"corpus_{corpus_index}_{field.removesuffix('_sha256')}",
                root / file_name,
                expected,
            )
            if field in {"manifest_sha256", "future_manifest_sha256"}:
                cases = value.get("cases")
                if not isinstance(cases, list):
                    raise ValueError(f"corpus_{corpus_index}: cases must be an array")
                manifest_cases_by_field[field] = cases
                case_ids = [
                    case.get("case_id") if isinstance(case, dict) else None
                    for case in cases
                ]
                source_group_values = [
                    case.get("source_group") if isinstance(case, dict) else None
                    for case in cases
                ]
                verification.semantic(
                    f"corpus_{corpus_index}_{field}_case_ids",
                    all(isinstance(case_id, str) and case_id for case_id in case_ids)
                    and len(case_ids) == len(set(case_ids)),
                )
                verification.semantic(
                    f"corpus_{corpus_index}_{field}_source_groups_well_formed",
                    all(
                        isinstance(source_group, str) and source_group
                        for source_group in source_group_values
                    ),
                )
        observed_cases = manifest_cases_by_field.get("manifest_sha256", [])
        future_cases = manifest_cases_by_field.get("future_manifest_sha256", [])
        expected_observed = corpus.get("candidate_evaluated_case_count")
        if expected_observed is None:
            expected_observed = corpus["case_count"] - corpus.get(
                "future_only_unevaluated_case_count", 0
            )
        verification.semantic(
            f"corpus_{corpus_index}_observed_case_count",
            len(observed_cases) == expected_observed,
        )
        expected_future = corpus.get("future_only_unevaluated_case_count", 0)
        observed_by_id = {case["case_id"]: case for case in observed_cases}
        future_by_id = {case["case_id"]: case for case in future_cases}
        if future_cases:
            future_only_ids = future_by_id.keys() - observed_by_id.keys()
            overlapping_ids = future_by_id.keys() & observed_by_id.keys()
            verification.semantic(
                f"corpus_{corpus_index}_future_manifest_superset",
                observed_by_id.keys() <= future_by_id.keys()
                and all(
                    observed_by_id[case_id] == future_by_id[case_id]
                    for case_id in overlapping_ids
                ),
            )
            all_cases = future_cases
        else:
            future_only_ids = set()
            all_cases = observed_cases
        verification.semantic(
            f"corpus_{corpus_index}_future_only_case_count",
            len(future_only_ids) == expected_future,
        )
        all_case_ids = [case["case_id"] for case in all_cases]
        verification.semantic(
            f"corpus_{corpus_index}_combined_case_count",
            len(all_cases) == corpus["case_count"]
            and len(all_case_ids) == len(set(all_case_ids)),
        )
        source_groups = {case["source_group"] for case in all_cases}
        verification.semantic(
            f"corpus_{corpus_index}_source_group_count",
            len(source_groups) == corpus["source_group_count"],
        )
        total_cases += corpus["case_count"]
    verification.semantic(
        "all_retained_case_count",
        total_cases == inventory["case_totals"]["all_retained_corpora"],
    )

    for source_index, retained_source in enumerate(inventory.get("retained_sources", [])):
        if "artifact" in retained_source and "sha256" in retained_source:
            root = relocate(retained_source["root"], relocation)
            verification.file(
                f"retained_source_{source_index}_artifact",
                root / retained_source["artifact"],
                retained_source["sha256"],
                retained_source.get("bytes"),
            )
        if "fetch_record" in retained_source:
            root = relocate(retained_source["root"], relocation)
            verification.file(
                f"retained_source_{source_index}_fetch_record",
                root / retained_source["fetch_record"],
                retained_source["fetch_record_sha256"],
            )
        if "archive" in retained_source:
            archive_path = relocate(retained_source["archive"], relocation)
            verification.file(
                f"retained_source_{source_index}_archive",
                archive_path,
                retained_source["sha256"],
                retained_source.get("bytes"),
            )
            record_path = relocate(retained_source["archive_record"], relocation)
            if "archive_record_sha256" in retained_source:
                record = verification.file(
                    f"retained_source_{source_index}_archive_record",
                    record_path,
                    retained_source["archive_record_sha256"],
                )
                binding = verification.semantic
            else:
                record = load_object(record_path)
                binding = lambda check_id, passed: verification.observation(
                    check_id,
                    passed,
                    "The inventory names this record but does not commit its SHA-256.",
                )
            record_archive = record.get("archive")
            if isinstance(record_archive, dict):
                record_sha = record_archive.get("sha256")
            else:
                record_sha = record.get("archive_sha256")
            binding(
                f"retained_source_{source_index}_archive_record_binding",
                record_sha == retained_source["sha256"],
            )
        if "acquisition_record" in retained_source:
            root = relocate(retained_source["root"], relocation)
            acquisition = verification.file(
                f"retained_source_{source_index}_acquisition",
                root / retained_source["acquisition_record"],
                retained_source["acquisition_record_sha256"],
            )
            for field in (
                "member_inventory_sha256",
                "source_output_inventory_sha256",
                "source_plan_sha256",
            ):
                if field not in retained_source:
                    continue
                acquisition_field = "plan_sha256" if field == "source_plan_sha256" else field
                verification.semantic(
                    f"retained_source_{source_index}_{field.removesuffix('_sha256')}",
                    acquisition.get(acquisition_field) == retained_source[field],
                )

    for archive_index, archive in enumerate(inventory.get("research_archives", [])):
        archive_path = relocate(archive["archive"], relocation)
        record_path = relocate(archive["archive_record"], relocation)
        verification.file(
            f"research_archive_{archive_index}",
            archive_path,
            archive["archive_sha256"],
            archive["archive_bytes"],
        )
        record = verification.file(
            f"research_archive_{archive_index}_record",
            record_path,
            archive["archive_record_sha256"],
        )
        if isinstance(record.get("archive"), dict):
            record_archive_sha = record["archive"].get("sha256")
            embedded_sha = record.get("embedded_integrity", {}).get("sha256")
        else:
            record_archive_sha = record.get("archive_sha256")
            embedded_sha = record.get("artifact_integrity_sha256")
        verification.semantic(
            f"research_archive_{archive_index}_record_archive_binding",
            record_archive_sha == archive["archive_sha256"],
        )
        verification.semantic(
            f"research_archive_{archive_index}_embedded_integrity_binding",
            embedded_sha == archive["embedded_integrity_sha256"],
        )

    cleanup = inventory["live_research_cleanup"]
    verification.file(
        "live_research_cleanup_record",
        relocate(cleanup["record"], relocation),
        cleanup["record_sha256"],
    )
    release_gate = inventory["release_gate"]
    verification.semantic(
        "release_gate_still_closed",
        release_gate.get("heldout_labels_opened") is False
        and release_gate.get("public_verdict_enabled") is False
        and release_gate.get("hand_built_candidate_sequence_stopped") is True,
    )
    return {
        "schema_version": 1,
        "state": "retained_inventory_verified",
        "inventory_id": inventory["inventory_id"],
        "inventory_sha256": inventory_sha256,
        "relocation_sha256": sha256_file(relocation_path),
        "verified_check_count": len(verification.checks),
        "checks": verification.checks,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--relocation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        value = verify(
            args.inventory.expanduser().resolve(),
            args.relocation.expanduser().resolve(),
        )
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(f"verified {value['verified_check_count']} retained commitments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
