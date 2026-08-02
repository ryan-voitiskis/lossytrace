#!/usr/bin/env python3
"""Freeze v2 source allocation from identity metadata only.

The exact candidate index and allocation are private.  The committed output is
an aggregate containing counts and hashes, never source/member identifiers or
machine paths.  This program enumerates archive directories and provider
metadata but does not decode, extract, hash, or measure audio payloads.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import re
import tarfile
import tempfile
import types
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
PRIVATE_INDEX_STATE = "source_candidate_index_identity_only"
PRIVATE_ALLOCATION_STATE = "source_allocation_frozen_identity_only"
PUBLIC_STATE = "source_allocation_path_free_evidence"
V1_SOURCE_ID = "consumed_v1_non_holdout"
RWC_SOURCE_ID = "rwc_music_v2_2026"
VCTK_SOURCE_ID = "vctk_clean_56spk_2017"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RWC_DOMAIN_BY_COLLECTION = {
    "C": "classical_music",
    "G": "genre_music",
    "J": "jazz_music",
    "P": "popular_music",
    "R": "royalty_free_music",
}
RAVDESS_DOMAIN_BY_KIND = {"speech": "acted_speech", "song": "acted_song"}


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as output:
        output.write(payload)
        temporary = Path(output.name)
    temporary.replace(path)


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def ensure_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def ensure_no_nul(value: str, label: str) -> None:
    if not value or "\0" in value:
        raise ValueError(f"{label} is empty or contains NUL")


def safe_relative_path(value: str, label: str) -> str:
    member = PurePosixPath(value)
    if (
        not value
        or member.is_absolute()
        or ".." in member.parts
        or member.as_posix() != value
    ):
        raise ValueError(f"{label} is not a canonical relative path")
    ensure_no_nul(value, label)
    return value


def import_script(repository_root: Path, filename: str, module_name: str) -> types.ModuleType:
    path = repository_root / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not import {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_rule_map(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rules.get("source_rules")
    if not isinstance(rows, list) or not rows:
        raise ValueError("source allocation rules are absent")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("source_id"), str):
            raise ValueError("source allocation rule is invalid")
        source_id = str(row["source_id"])
        if source_id in result:
            raise ValueError("source allocation rule is duplicated")
        result[source_id] = row
    return result


def validate_rules(rules: dict[str, Any]) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "state": "source_allocation_rules_frozen_before_execution",
        "audio_generated": False,
        "scores_opened": False,
        "existing_v1_holdouts_included": False,
        "selection_uses_waveform_content": False,
        "selection_uses_duration": False,
        "selection_uses_measurements_or_labels": False,
    }
    for field, value in expected.items():
        if rules.get(field) != value:
            raise ValueError(f"source allocation rule {field} differs")
    if not isinstance(rules.get("source_identity_checkpoint_commit"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", str(rules.get("source_identity_checkpoint_commit"))
    ):
        raise ValueError("source identity checkpoint commit is invalid")
    selection = rules.get("member_selection")
    identifier = rules.get("identifier_derivation")
    if not isinstance(selection, dict) or not isinstance(identifier, dict):
        raise ValueError("selection or identifier rules are absent")
    for value, label in (
        (selection.get("ranking_prefix"), "member ranking prefix"),
        (identifier.get("group_id_prefix"), "group ID prefix"),
    ):
        if not isinstance(value, str) or not value.endswith("\0"):
            raise ValueError(f"{label} must end in NUL")
    if selection.get("selection_count_per_retained_group") != 1:
        raise ValueError("source allocation must select one member per group")
    source_rule_map(rules)


def verify_public_bindings(
    repository_root: Path, rules: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    bindings = rules.get("input_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("input bindings are absent")
    contract = bindings.get("factorial_contract")
    if not isinstance(contract, dict):
        raise ValueError("factorial contract binding is absent")
    contract_path = repository_root / safe_relative_path(
        str(contract.get("path")), "factorial contract path"
    )
    if sha256_file(contract_path) != ensure_sha256(
        contract.get("sha256"), "factorial contract binding"
    ):
        raise ValueError("factorial contract binding differs")

    records = bindings.get("source_identity_records")
    if not isinstance(records, list):
        raise ValueError("source identity record bindings are absent")
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("source_id"), str):
            raise ValueError("source identity record binding is invalid")
        source_id = str(record["source_id"])
        if source_id in result:
            raise ValueError("source identity record binding is duplicated")
        for path_field, hash_field in (
            ("rules_path", "rules_sha256"),
            ("family_rules_path", "family_rules_sha256"),
            ("evidence_path", "evidence_sha256"),
        ):
            if path_field not in record:
                continue
            path = repository_root / safe_relative_path(
                str(record[path_field]), f"{source_id} {path_field}"
            )
            if sha256_file(path) != ensure_sha256(
                record.get(hash_field), f"{source_id} {hash_field}"
            ):
                raise ValueError(f"{source_id} {path_field} binding differs")
        evidence_path = repository_root / str(record["evidence_path"])
        evidence = load_object(evidence_path)
        if (
            evidence.get("source_id") != source_id
            or evidence.get("state") != "source_identity_evidence_only"
            or evidence.get("scores_opened") is not False
            or evidence.get("selection_authorized") is not False
        ):
            raise ValueError(f"{source_id} source identity boundary differs")
        result[source_id] = record
    return result


def opaque_group_id(rules: dict[str, Any], source_id: str, raw_group_key: str) -> str:
    ensure_no_nul(source_id, "source ID")
    ensure_no_nul(raw_group_key, "raw group key")
    identifier = rules["identifier_derivation"]
    payload = (
        str(identifier["group_id_prefix"]).encode("utf-8")
        + source_id.encode("utf-8")
        + b"\0"
        + raw_group_key.encode("utf-8")
    )
    return f"{source_id}-{hashlib.sha256(payload).hexdigest()}"


def candidate(
    rules: dict[str, Any],
    *,
    source_id: str,
    partition: str,
    raw_group_key: str,
    member_id: str,
    source_collection_id: str,
    source_lineage_id: str,
    source_domain: str,
    provenance_tier: str,
    input_artifact_id: str,
    locator: dict[str, str],
    factors: dict[str, Any],
) -> dict[str, Any]:
    ensure_no_nul(member_id, "member ID")
    for value in locator.values():
        if isinstance(value, str) and value.startswith("/"):
            raise ValueError("candidate locator contains an absolute path")
    group_id = opaque_group_id(rules, source_id, raw_group_key)
    return {
        "source_id": source_id,
        "evidence_partition": partition,
        "group_id": group_id,
        "partition_group": group_id,
        "member_id": member_id,
        "source_collection_id": source_collection_id,
        "source_lineage_id": source_lineage_id,
        "source_domain": source_domain,
        "provenance_tier": provenance_tier,
        "input_artifact_id": input_artifact_id,
        "locator": locator,
        "factors": factors,
    }


def verify_artifact(
    path: Path, expected_sha256: str, input_artifact_id: str
) -> dict[str, Any]:
    digest = sha256_file(path)
    if digest != ensure_sha256(expected_sha256, f"{input_artifact_id} SHA-256"):
        raise ValueError(f"{input_artifact_id} bytes differ from source audit")
    return {"bytes": path.stat().st_size, "sha256": digest}


def build_v1_candidates(
    rules: dict[str, Any], manifest_path: Path, v1_audio_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    binding = rules["input_bindings"]["consumed_v1_non_holdout_manifest"]
    manifest_sha256 = sha256_file(manifest_path)
    if manifest_sha256 != ensure_sha256(binding.get("sha256"), "v1 manifest SHA-256"):
        raise ValueError("consumed v1 manifest binding differs")
    manifest = load_object(manifest_path)
    if manifest.get("holdout_scores_opened") is not False:
        raise ValueError("consumed v1 manifest holdout boundary differs")
    rows = manifest.get("cases")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("consumed v1 manifest cases are invalid")
    source_rule = source_rule_map(rules)[V1_SOURCE_ID]
    class_by_domain = source_rule.get("base_class_by_source_domain")
    if not isinstance(class_by_domain, dict):
        raise ValueError("consumed v1 base classes are absent")
    excluded_domains = set(source_rule.get("excluded_source_domains", []))
    all_domains = {str(row.get("source_domain")) for row in rows}
    if all_domains != set(class_by_domain) | excluded_domains:
        raise ValueError("consumed v1 source-domain boundary differs")
    controlled_groups = {
        str(row["source_group"])
        for row in rows
        if row.get("source_domain") == "public_tier_a_controlled"
    }
    original_groups = {
        str(row["source_group"])
        for row in rows
        if row.get("source_domain") == "public_tier_a_originals"
    }
    if controlled_groups != original_groups or len(controlled_groups) != 48:
        raise ValueError("public Tier A original/controlled group cross-check differs")

    selected_rows = [
        row
        for row in rows
        if row.get("source_domain") in class_by_domain
        and row.get("expectation") == "negative"
        and row.get("class") == class_by_domain[row["source_domain"]]
    ]
    candidates: list[dict[str, Any]] = []
    for row in selected_rows:
        required = (
            "case_id",
            "source_group",
            "partition_group",
            "source_domain",
            "relative_path",
            "source_corpus_id",
            "provenance_tier",
        )
        if any(not isinstance(row.get(field), str) for field in required):
            raise ValueError("consumed v1 base row identity is invalid")
        relative_path = safe_relative_path(str(row["relative_path"]), "v1 relative path")
        if not (v1_audio_root / relative_path).is_file():
            raise ValueError("consumed v1 base member is absent")
        raw_group_key = str(row["source_group"])
        if row["partition_group"] != raw_group_key:
            raise ValueError("consumed v1 base group and partition group differ")
        candidates.append(
            candidate(
                rules,
                source_id=V1_SOURCE_ID,
                partition="mechanism_development",
                raw_group_key=raw_group_key,
                member_id=str(row["case_id"]),
                source_collection_id=str(row["source_corpus_id"]),
                source_lineage_id=str(row["source_corpus_id"]),
                source_domain=str(row["source_domain"]),
                provenance_tier=str(row["provenance_tier"]),
                input_artifact_id="consumed_v1_non_holdout_manifest",
                locator={"relative_path": relative_path},
                factors={
                    "v1_class": str(row["class"]),
                    "v1_original_split": str(row.get("original_split", "")),
                },
            )
        )
    verify_source_candidate_counts(rules, V1_SOURCE_ID, candidates)
    return candidates, {
        "consumed_v1_non_holdout_manifest": {
            "bytes": manifest_path.stat().st_size,
            "sha256": manifest_sha256,
        }
    }


def build_vctk_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root, "audit-audio-integrity-v2-vctk.py", "lossytrace_v2_vctk_audit"
    )
    rule_path = repository_root / "benchmarks/audio-integrity-v2/vctk-source-group-rules.json"
    source_rules = load_object(rule_path)
    evidence = load_object(
        repository_root
        / "research/sources/evidence/vctk-clean-56spk-2017-observed-20260802.json"
    )
    base = source_root / "vctk-clean-56spk-2017"
    audio_path = base / "clean_trainset_56spk_wav.zip"
    speaker_path = base / "vctk-speaker-info.txt"
    archive_bindings = evidence.get("archive_bindings")
    if not isinstance(archive_bindings, dict) or not isinstance(
        archive_bindings.get("audio"), dict
    ):
        raise ValueError("VCTK audited audio binding is absent")
    artifacts = {
        "vctk_clean_audio": verify_artifact(
            audio_path,
            archive_bindings["audio"]["local_sha256"],
            "vctk_clean_audio",
        ),
        "vctk_speaker_info": verify_artifact(
            speaker_path,
            source_rules["supporting_artifacts"]["speaker_info"]["local_sha256"],
            "vctk_speaker_info",
        ),
    }
    speaker_metadata = module.parse_speaker_info(speaker_path)
    candidates: list[dict[str, Any]] = []
    with zipfile.ZipFile(audio_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            match = module.AUDIO_MEMBER.fullmatch(member.filename)
            if match is None:
                raise ValueError("VCTK audio archive contains an unexpected member")
            speaker, utterance = match.groups()
            metadata = speaker_metadata.get(speaker)
            if metadata is None:
                raise ValueError("VCTK selected speaker metadata is absent")
            candidates.append(
                candidate(
                    rules,
                    source_id=VCTK_SOURCE_ID,
                    partition="encoder_transfer",
                    raw_group_key=speaker,
                    member_id=member.filename,
                    source_collection_id="vctk-clean-56spk-2017",
                    source_lineage_id="vctk-clean-56spk-2017",
                    source_domain="studio_speech",
                    provenance_tier="tier_a_confirmed_pcm",
                    input_artifact_id="vctk_clean_audio",
                    locator={"archive_member": member.filename},
                    factors={
                        "speaker_id": speaker,
                        "utterance_id": utterance,
                        "gender": str(metadata["gender"]),
                        "accent": str(metadata["accent"]),
                    },
                )
            )
    verify_source_candidate_counts(rules, VCTK_SOURCE_ID, candidates, pre_cap=True)
    return candidates, artifacts


def build_ravdess_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root,
        "audit-audio-integrity-v2-ravdess.py",
        "lossytrace_v2_ravdess_audit",
    )
    evidence = load_object(
        repository_root
        / "research/sources/evidence/ravdess-1.0.0-observed-20260802.json"
    )
    base = source_root / "ravdess-1.0.0"
    paths = {
        "speech": base / "Audio_Speech_Actors_01-24.zip",
        "song": base / "Audio_Song_Actors_01-24.zip",
    }
    artifacts = {
        f"ravdess_{kind}_audio": verify_artifact(
            path, evidence["archive_bindings"][kind]["local_sha256"], f"ravdess_{kind}_audio"
        )
        for kind, path in paths.items()
    }
    excluded = set(
        source_rule_map(rules)["ravdess_audio_1_0_0"].get("excluded_member_ids", [])
    )
    observed_excluded: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for kind, path in sorted(paths.items()):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                match = module.AUDIO_MEMBER.fullmatch(member.filename)
                if match is None:
                    raise ValueError("RAVDESS archive contains an unexpected member")
                directory_actor = match.group(1)
                fields = module.validate_factor_fields(
                    kind, directory_actor, match.groups()[1:]
                )
                if member.filename in excluded:
                    observed_excluded.add(member.filename)
                    continue
                modality, channel, emotion, intensity, statement, repetition, actor = fields
                candidates.append(
                    candidate(
                        rules,
                        source_id="ravdess_audio_1_0_0",
                        partition="encoder_transfer",
                        raw_group_key=actor,
                        member_id=member.filename,
                        source_collection_id=f"ravdess-audio-{kind}-1-0-0",
                        source_lineage_id="ravdess-audio-1-0-0",
                        source_domain=RAVDESS_DOMAIN_BY_KIND[kind],
                        provenance_tier="tier_a_confirmed_pcm",
                        input_artifact_id=f"ravdess_{kind}_audio",
                        locator={"archive_member": member.filename},
                        factors={
                            "archive_kind": kind,
                            "modality": modality,
                            "vocal_channel": channel,
                            "emotion": emotion,
                            "intensity": intensity,
                            "statement": statement,
                            "repetition": repetition,
                            "actor_id": actor,
                        },
                    )
                )
    if observed_excluded != excluded:
        raise ValueError("RAVDESS repeated-PCM exclusion identities differ")
    verify_source_candidate_counts(rules, "ravdess_audio_1_0_0", candidates)
    return candidates, artifacts


def build_fsdd_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root, "audit-audio-integrity-v2-fsdd.py", "lossytrace_v2_fsdd_audit"
    )
    source_rules = load_object(
        repository_root / "benchmarks/audio-integrity-v2/fsdd-source-group-rules.json"
    )
    path = source_root / "fsdd-v1.0.10/free-spoken-digit-dataset-1.0.10.zip"
    artifacts = {
        "fsdd_audio": verify_artifact(
            path, source_rules["artifact"]["local_sha256"], "fsdd_audio"
        )
    }
    root_prefix = str(source_rules["expected"]["archive_root_prefix"])
    candidates: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            if member.is_dir() or not member.filename.startswith(root_prefix):
                continue
            member_id = member.filename[len(root_prefix) :]
            match = module.AUDIO_MEMBER.fullmatch(member_id)
            if match is None:
                continue
            digit, speaker, repetition = match.groups()
            candidates.append(
                candidate(
                    rules,
                    source_id="fsdd_v1_0_10",
                    partition="encoder_transfer",
                    raw_group_key=speaker,
                    member_id=member_id,
                    source_collection_id="fsdd-v1-0-10",
                    source_lineage_id="fsdd-v1-0-10",
                    source_domain="home_recorded_bandwidth_limited_digit_speech",
                    provenance_tier="tier_a_confirmed_pcm",
                    input_artifact_id="fsdd_audio",
                    locator={"archive_member": member.filename},
                    factors={
                        "digit": int(digit),
                        "speaker_id": speaker,
                        "repetition_index": int(repetition),
                        "native_sample_rate_hz": 8000,
                    },
                )
            )
    verify_source_candidate_counts(rules, "fsdd_v1_0_10", candidates)
    return candidates, artifacts


def build_tinysol_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root,
        "audit-audio-integrity-v2-tinysol.py",
        "lossytrace_v2_tinysol_audit",
    )
    source_rules = load_object(
        repository_root / "benchmarks/audio-integrity-v2/tinysol-source-group-rules.json"
    )
    evidence = load_object(
        repository_root
        / "research/sources/evidence/tinysol-6.0-observed-20260802.json"
    )
    base = source_root / "tinysol-6.0"
    audio_path = base / "TinySOL.tar.gz"
    metadata_path = base / "TinySOL_metadata.csv"
    artifacts = {
        "tinysol_audio": verify_artifact(
            audio_path, evidence["archive_bindings"]["audio"]["sha256"], "tinysol_audio"
        ),
        "tinysol_metadata": verify_artifact(
            metadata_path,
            evidence["archive_bindings"]["metadata"]["sha256"],
            "tinysol_metadata",
        ),
    }
    metadata_rows, _ = module.parse_metadata(metadata_path, source_rules["expected"])
    archive_audio_ids: set[str] = set()
    with tarfile.open(audio_path, mode="r:gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith("./"):
                continue
            member_id = member.name[2:]
            if member_id.endswith(".wav"):
                archive_audio_ids.add(member_id)
    if archive_audio_ids != set(metadata_rows):
        raise ValueError("TinySOL archive and metadata identities differ")
    candidates: list[dict[str, Any]] = []
    for member_id, row in sorted(metadata_rows.items()):
        if bool(row["digitally_retuned"]):
            continue
        family = member_id.split("/", maxsplit=1)[0]
        candidates.append(
            candidate(
                rules,
                source_id="tinysol_6_0",
                partition="encoder_transfer",
                raw_group_key="tinysol-common-collection",
                member_id=member_id,
                source_collection_id="tinysol-6-0",
                source_lineage_id="tinysol-sol-common-collection",
                source_domain="isolated_acoustic_instrument",
                provenance_tier="tier_a_confirmed_pcm",
                input_artifact_id="tinysol_audio",
                locator={"archive_member": f"./{member_id}"},
                factors={
                    "family": family,
                    "instrument_abbreviation": str(row["instrument_abbreviation"]),
                    "pitch_id": int(row["pitch_id"]),
                    "dynamics": str(row["dynamics"]),
                    "instance_token": str(row["instance_token"]),
                    "retuning_class": str(row["retuning_class"]),
                },
            )
        )
    verify_source_candidate_counts(rules, "tinysol_6_0", candidates)
    return candidates, artifacts


def build_sonyc_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root,
        "audit-audio-integrity-v2-sonyc-backgrounds.py",
        "lossytrace_v2_sonyc_audit",
    )
    evidence = load_object(
        repository_root
        / "research/sources/evidence/sonyc-backgrounds-1.0.0-observed-20260802.json"
    )
    path = source_root / "sonyc-backgrounds-1.0.0/SONYC-Backgrounds.tar.gz"
    artifacts = {
        "sonyc_backgrounds_audio": verify_artifact(
            path,
            evidence["archive_binding"]["local_sha256"],
            "sonyc_backgrounds_audio",
        )
    }
    candidates: list[dict[str, Any]] = []
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            match = module.AUDIO_MEMBER.fullmatch(member.name)
            if match is None:
                if member.name == module.README_MEMBER:
                    continue
                raise ValueError("SONYC archive contains an unexpected member")
            split, sensor, date, hour, instance = match.groups()
            candidates.append(
                candidate(
                    rules,
                    source_id="sonyc_backgrounds_1_0_0",
                    partition="encoder_transfer",
                    raw_group_key=sensor,
                    member_id=member.name,
                    source_collection_id="sonyc-backgrounds-1-0-0",
                    source_lineage_id="sonyc-backgrounds-1-0-0",
                    source_domain="urban_sensor_soundscape",
                    provenance_tier="tier_a_confirmed_pcm",
                    input_artifact_id="sonyc_backgrounds_audio",
                    locator={"archive_member": member.name},
                    factors={
                        "provider_split": split,
                        "sensor_id": sensor,
                        "recording_date": date,
                        "hour": hour,
                        "instance": instance,
                    },
                )
            )
    verify_source_candidate_counts(rules, "sonyc_backgrounds_1_0_0", candidates)
    return candidates, artifacts


def build_satp_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root, "audit-audio-integrity-v2-satp.py", "lossytrace_v2_satp_audit"
    )
    source_rules = load_object(
        repository_root / "benchmarks/audio-integrity-v2/satp-source-group-rules.json"
    )
    evidence = load_object(
        repository_root / "research/sources/evidence/satp-1.5-observed-20260802.json"
    )
    base = source_root / "satp-1.5"
    audio_path = base / "SATP WAV.zip"
    readme_path = base / "README.md"
    artifacts = {
        "satp_audio": verify_artifact(
            audio_path, evidence["archive_binding"]["local_sha256"], "satp_audio"
        ),
        "satp_readme": verify_artifact(
            readme_path, source_rules["readme_sha256"], "satp_readme"
        ),
    }
    rows = module.parse_recording_table(readme_path.read_text(encoding="utf-8"))
    calibration_ids = set(source_rules["calibration_readme_recording_ids"])
    metadata = {row["recording_id"]: row for row in rows if row["recording_id"] not in calibration_ids}
    archive_calibration = set(source_rules["calibration_archive_recording_ids"])
    observed_ids: set[str] = set()
    candidates: list[dict[str, Any]] = []
    with zipfile.ZipFile(audio_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            match = module.AUDIO_MEMBER.fullmatch(member.filename)
            if match is None:
                raise ValueError("SATP archive contains an unexpected member")
            recording_id = match.group(1)
            if recording_id in archive_calibration:
                continue
            row = metadata.get(recording_id)
            if row is None or recording_id in observed_ids:
                raise ValueError("SATP archive and README identities differ")
            observed_ids.add(recording_id)
            raw_group_key = module.coordinate_group_key(row)
            candidates.append(
                candidate(
                    rules,
                    source_id="satp_soundscapes_1_5",
                    partition="external_transfer",
                    raw_group_key=raw_group_key,
                    member_id=member.filename,
                    source_collection_id="satp-soundscapes-1-5",
                    source_lineage_id="satp-soundscapes-1-5",
                    source_domain="urban_binaural_soundscape",
                    provenance_tier="tier_a_confirmed_pcm",
                    input_artifact_id="satp_audio",
                    locator={"archive_member": member.filename},
                    factors={
                        "recording_id": recording_id,
                        "location": str(row["location"]),
                        "latitude": str(row["latitude"]),
                        "longitude": str(row["longitude"]),
                        "recording_date": str(row["recording_date"]),
                    },
                )
            )
    if observed_ids != set(metadata):
        raise ValueError("SATP archive and README reference identities differ")
    verify_source_candidate_counts(rules, "satp_soundscapes_1_5", candidates)
    return candidates, artifacts


def build_lombard_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    module = import_script(
        repository_root,
        "audit-audio-integrity-v2-lombard-grid.py",
        "lossytrace_v2_lombard_audit",
    )
    evidence = load_object(
        repository_root
        / "research/sources/evidence/lombard-grid-2018-observed-20260802.json"
    )
    audio_path = source_root / "lombardgrid_audio.zip"
    metadata_path = source_root / "lombardgrid_json.zip"
    artifacts = {
        "lombard_audio": verify_artifact(
            audio_path, evidence["archive_bindings"]["audio"]["sha256"], "lombard_audio"
        ),
        "lombard_metadata": verify_artifact(
            metadata_path,
            evidence["archive_bindings"]["metadata"]["sha256"],
            "lombard_metadata",
        ),
    }
    candidates: list[dict[str, Any]] = []
    with zipfile.ZipFile(metadata_path) as metadata_archive:
        rows = module.load_metadata(metadata_archive)
    correct_keys = collections.Counter(
        (str(row.get("SPKR")), str(row.get("COND")), str(row.get("UTTERANCE")))
        for row in rows
        if row.get("STATUS") == "CORRECT"
    )
    with zipfile.ZipFile(audio_path) as audio_archive:
        for member in audio_archive.infolist():
            if member.is_dir():
                continue
            match = module.CANONICAL_AUDIO_NAME.fullmatch(member.filename)
            if match is None:
                continue
            speaker, condition, utterance = match.groups()
            if correct_keys[(speaker, condition, utterance)] != 1:
                continue
            candidates.append(
                candidate(
                    rules,
                    source_id="lombard_grid_2018",
                    partition="external_transfer",
                    raw_group_key=speaker,
                    member_id=member.filename,
                    source_collection_id="lombard-grid-2018",
                    source_lineage_id="lombard-grid-2018",
                    source_domain="laboratory_lombard_speech",
                    provenance_tier="tier_a_confirmed_pcm",
                    input_artifact_id="lombard_audio",
                    locator={"archive_member": member.filename},
                    factors={
                        "talker_id": speaker,
                        "condition": condition,
                        "utterance": utterance,
                    },
                )
            )
    verify_source_candidate_counts(rules, "lombard_grid_2018", candidates)
    return candidates, artifacts


def rwc_family_map(
    metadata: dict[str, dict[str, str]], family_rules: dict[str, Any]
) -> tuple[set[str], dict[str, str]]:
    excluded: set[str] = set()
    for row in family_rules.get("eligibility_exclusions", []):
        collection = str(row["collection_id"])
        minimum = int(row["piece_number_minimum"])
        maximum = int(row["piece_number_maximum"])
        excluded.update(
            rwc_id
            for rwc_id, metadata_row in metadata.items()
            if metadata_row["CollID"] == collection
            and minimum <= int(metadata_row["PieceNo"]) <= maximum
        )
    label_to_family: dict[str, str] = {}
    for merge in family_rules.get("family_merges", []):
        family_key = f"declared-family:{merge['family_id']}"
        for label in merge["artist_labels"]:
            if label in label_to_family:
                raise ValueError("RWC family merge labels overlap")
            label_to_family[str(label)] = family_key
    result: dict[str, str] = {}
    for rwc_id, row in metadata.items():
        if rwc_id in excluded:
            continue
        label = row["Artist"].strip()
        result[rwc_id] = label_to_family.get(label, f"artist-label:{label}")
    return excluded, result


def build_rwc_candidates(
    rules: dict[str, Any], repository_root: Path, source_root: Path
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    audio_module = import_script(
        repository_root, "audit-audio-integrity-v2-rwc.py", "lossytrace_v2_rwc_audit"
    )
    metadata_module = import_script(
        repository_root,
        "audit-audio-integrity-v2-rwc-metadata.py",
        "lossytrace_v2_rwc_metadata_audit",
    )
    evidence = load_object(
        repository_root
        / "research/sources/evidence/rwc-music-v2-2026-observed-20260802.json"
    )
    family_rules = load_object(
        repository_root / "benchmarks/audio-integrity-v2/rwc-artist-family-rules.json"
    )
    metadata_path = source_root / "rwc-annotations/metadata.csv"
    if sha256_file(metadata_path) != family_rules["metadata_sha256"]:
        raise ValueError("RWC metadata binding differs")
    metadata = audio_module.load_metadata(metadata_path)
    excluded, family_by_id = rwc_family_map(metadata, family_rules)
    artifacts: dict[str, dict[str, Any]] = {
        "rwc_metadata": {
            "bytes": metadata_path.stat().st_size,
            "sha256": sha256_file(metadata_path),
        }
    }
    observed_ids: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for collection in sorted(RWC_DOMAIN_BY_COLLECTION):
        filename = f"RWC-{collection}.zip"
        path = source_root / "rwc-music-v2-2026" / filename
        artifact_id = f"rwc_{collection.lower()}_audio"
        artifacts[artifact_id] = verify_artifact(
            path, evidence["archive_bindings"][filename]["local_sha256"], artifact_id
        )
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                match = audio_module.AUDIO_MEMBER.fullmatch(member.filename)
                if match is None:
                    raise ValueError("RWC archive contains an unexpected member")
                directory_collection, rwc_id, id_collection, _ = match.groups()
                if directory_collection != collection or id_collection != collection:
                    raise ValueError("RWC archive collection identity differs")
                if rwc_id in observed_ids or rwc_id not in metadata:
                    raise ValueError("RWC archive metadata identity differs")
                observed_ids.add(rwc_id)
                if rwc_id in excluded:
                    continue
                row = metadata[rwc_id]
                raw_family = family_by_id[rwc_id]
                normalized_title = metadata_module.normalized_work_title(row["Title"])
                if not normalized_title:
                    raise ValueError("RWC normalized work title is empty")
                candidates.append(
                    candidate(
                        rules,
                        source_id=RWC_SOURCE_ID,
                        partition="external_transfer",
                        raw_group_key=raw_family,
                        member_id=member.filename,
                        source_collection_id=f"rwc-music-v2-{collection.lower()}",
                        source_lineage_id="rwc-music-v2-2026",
                        source_domain=RWC_DOMAIN_BY_COLLECTION[collection],
                        provenance_tier="tier_a_confirmed_pcm",
                        input_artifact_id=artifact_id,
                        locator={"archive_member": member.filename},
                        factors={
                            "rwc_id": rwc_id,
                            "collection_id": collection,
                            "artist_family": raw_family,
                            "artist_label": str(row["Artist"]),
                            "work_title": str(row["Title"]),
                            "normalized_work_title": normalized_title,
                            "legacy_disc": str(row["CDNo"]),
                            "legacy_track": str(row["TrackNo"]),
                            "audio_start_seconds": str(row["audio_start"]),
                            "audio_end_seconds": str(row["audio_end"]),
                        },
                    )
                )
    if observed_ids != set(metadata):
        raise ValueError("RWC archive and metadata identity sets differ")
    verify_source_candidate_counts(rules, RWC_SOURCE_ID, candidates)
    return candidates, artifacts


def verify_source_candidate_counts(
    rules: dict[str, Any],
    source_id: str,
    candidates: list[dict[str, Any]],
    *,
    pre_cap: bool = False,
) -> None:
    source_rule = source_rule_map(rules)[source_id]
    if len(candidates) != source_rule.get("expected_candidate_count"):
        raise ValueError(f"{source_id} candidate count differs")
    group_count = len({row["group_id"] for row in candidates})
    expected_key = "expected_pre_cap_group_count" if pre_cap else "expected_retained_group_count"
    if group_count != source_rule.get(expected_key):
        raise ValueError(f"{source_id} candidate group count differs")


def build_candidate_index(
    rules: dict[str, Any],
    repository_root: Path,
    source_root: Path,
    v1_manifest: Path,
    v1_audio_root: Path,
    rules_sha256: str,
) -> dict[str, Any]:
    verify_public_bindings(repository_root, rules)
    builders = [
        lambda: build_v1_candidates(rules, v1_manifest, v1_audio_root),
        lambda: build_vctk_candidates(rules, repository_root, source_root),
        lambda: build_ravdess_candidates(rules, repository_root, source_root),
        lambda: build_fsdd_candidates(rules, repository_root, source_root),
        lambda: build_tinysol_candidates(rules, repository_root, source_root),
        lambda: build_sonyc_candidates(rules, repository_root, source_root),
        lambda: build_satp_candidates(rules, repository_root, source_root),
        lambda: build_lombard_candidates(rules, repository_root, source_root),
        lambda: build_rwc_candidates(rules, repository_root, source_root),
    ]
    candidates: list[dict[str, Any]] = []
    input_artifacts: dict[str, dict[str, Any]] = {}
    for build in builders:
        rows, artifacts = build()
        candidates.extend(rows)
        overlap = set(input_artifacts) & set(artifacts)
        if overlap:
            raise ValueError("private input artifact IDs overlap")
        input_artifacts.update(artifacts)
    candidates.sort(
        key=lambda row: (str(row["source_id"]), str(row["group_id"]), str(row["member_id"]))
    )
    identity_keys = {(row["source_id"], row["member_id"]) for row in candidates}
    if len(identity_keys) != len(candidates):
        raise ValueError("candidate member identity is duplicated")
    expected = rules["expected"]
    if len(candidates) != expected.get("candidate_count"):
        raise ValueError("total candidate count differs")
    return {
        "schema_version": SCHEMA_VERSION,
        "state": PRIVATE_INDEX_STATE,
        "rules_id": rules["rules_id"],
        "rules_sha256": rules_sha256,
        "source_identity_checkpoint_commit": rules["source_identity_checkpoint_commit"],
        "audio_generated": False,
        "scores_opened": False,
        "waveform_content_inspected": False,
        "duration_used_for_selection": False,
        "absolute_paths_recorded": False,
        "input_artifacts": dict(sorted(input_artifacts.items())),
        "candidates": candidates,
    }


def member_rank(rules: dict[str, Any], row: dict[str, Any]) -> tuple[bytes, str]:
    source_id = str(row["source_id"])
    group_id = str(row["group_id"])
    member_id = str(row["member_id"])
    for value, label in (
        (source_id, "rank source ID"),
        (group_id, "rank group ID"),
        (member_id, "rank member ID"),
    ):
        ensure_no_nul(value, label)
    prefix = str(rules["member_selection"]["ranking_prefix"]).encode("utf-8")
    payload = (
        prefix
        + source_id.encode("utf-8")
        + b"\0"
        + group_id.encode("utf-8")
        + b"\0"
        + member_id.encode("utf-8")
    )
    return hashlib.sha256(payload).digest(), member_id


def apply_vctk_cap(
    rules: dict[str, Any], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    source_rule = source_rule_map(rules)[VCTK_SOURCE_ID]
    cap = source_rule["group_cap"]
    by_gender: dict[str, set[str]] = collections.defaultdict(set)
    gender_by_group: dict[str, str] = {}
    speaker_by_group: dict[str, str] = {}
    for row in candidates:
        group_id = str(row["group_id"])
        gender = str(row["factors"]["gender"])
        speaker = str(row["factors"]["speaker_id"])
        if group_id in gender_by_group and (
            gender_by_group[group_id] != gender or speaker_by_group[group_id] != speaker
        ):
            raise ValueError("VCTK group factors are inconsistent")
        gender_by_group[group_id] = gender
        speaker_by_group[group_id] = speaker
        by_gender[gender].add(group_id)
    selected_groups: set[str] = set()
    selected_counts: dict[str, int] = {}
    prefix = str(cap["ranking_prefix"]).encode("utf-8")
    target = int(cap["selected_per_gender"])
    for gender in sorted(by_gender):
        ranked = sorted(
            by_gender[gender],
            key=lambda group_id: (
                hashlib.sha256(prefix + speaker_by_group[group_id].encode("utf-8")).digest(),
                speaker_by_group[group_id],
            ),
        )
        if len(ranked) < target:
            raise ValueError("VCTK gender cap lacks enough groups")
        retained = ranked[:target]
        selected_groups.update(retained)
        selected_counts[gender] = len(retained)
    filtered = [row for row in candidates if row["group_id"] in selected_groups]
    if len(selected_groups) != source_rule["expected_retained_group_count"]:
        raise ValueError("VCTK capped group count differs")
    return filtered, selected_counts


def select_rwc(
    rules: dict[str, Any], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source_rule = source_rule_map(rules)[RWC_SOURCE_ID]
    work_rule = source_rule["work_title_constraint"]
    best_edge: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        group_id = str(row["group_id"])
        title = str(row["factors"]["normalized_work_title"])
        key = (group_id, title)
        if key not in best_edge or member_rank(rules, row) < member_rank(
            rules, best_edge[key]
        ):
            best_edge[key] = row
    adjacency: dict[str, list[str]] = collections.defaultdict(list)
    for group_id, title in best_edge:
        adjacency[group_id].append(title)
    for group_id, titles in adjacency.items():
        titles.sort(
            key=lambda title: (
                member_rank(rules, best_edge[(group_id, title)]),
                title,
            )
        )
    family_prefix = str(work_rule["family_order_prefix"]).encode("utf-8")
    families = sorted(
        adjacency,
        key=lambda group_id: (
            hashlib.sha256(family_prefix + group_id.encode("utf-8")).digest(),
            group_id,
        ),
    )
    title_owner: dict[str, str] = {}
    family_choice: dict[str, dict[str, Any]] = {}

    def augment(group_id: str, seen_titles: set[str]) -> bool:
        for title in adjacency[group_id]:
            if title in seen_titles:
                continue
            seen_titles.add(title)
            owner = title_owner.get(title)
            if owner is None or augment(owner, seen_titles):
                title_owner[title] = group_id
                family_choice[group_id] = best_edge[(group_id, title)]
                return True
        return False

    for family in families:
        if not augment(family, set()):
            raise ValueError("RWC artist families lack a complete unique-title matching")
    expected = int(source_rule["expected_retained_group_count"])
    if len(family_choice) != expected or len(title_owner) != expected:
        raise ValueError("RWC unique-title matching count differs")
    return list(family_choice.values())


def select_candidates(
    rules: dict[str, Any],
    rules_sha256: str,
    candidate_index: dict[str, Any],
    candidate_index_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        candidate_index.get("state") != PRIVATE_INDEX_STATE
        or candidate_index.get("rules_id") != rules.get("rules_id")
        or candidate_index.get("rules_sha256") != rules_sha256
        or candidate_index.get("audio_generated") is not False
        or candidate_index.get("scores_opened") is not False
    ):
        raise ValueError("candidate index boundary differs")
    raw_candidates = candidate_index.get("candidates")
    if not isinstance(raw_candidates, list) or not all(
        isinstance(row, dict) for row in raw_candidates
    ):
        raise ValueError("candidate index rows are invalid")
    candidates = list(raw_candidates)
    vctk_rows = [row for row in candidates if row["source_id"] == VCTK_SOURCE_ID]
    capped_vctk, vctk_gender_counts = apply_vctk_cap(rules, vctk_rows)
    candidates = [row for row in candidates if row["source_id"] != VCTK_SOURCE_ID]
    candidates.extend(capped_vctk)

    rwc_rows = [row for row in candidates if row["source_id"] == RWC_SOURCE_ID]
    selected = select_rwc(rules, rwc_rows)
    generic = [row for row in candidates if row["source_id"] != RWC_SOURCE_ID]
    by_group: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in generic:
        by_group[str(row["group_id"])].append(row)
    selected.extend(min(rows, key=lambda row: member_rank(rules, row)) for rows in by_group.values())
    selected.sort(
        key=lambda row: (
            str(row["evidence_partition"]),
            str(row["source_id"]),
            str(row["group_id"]),
        )
    )
    group_ids = [str(row["group_id"]) for row in selected]
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("selected source groups are duplicated")
    expected = rules["expected"]
    if len(selected) != expected["selected_member_count"]:
        raise ValueError("selected member count differs")
    partition_counts = collections.Counter(str(row["evidence_partition"]) for row in selected)
    source_counts = collections.Counter(str(row["source_id"]) for row in selected)
    if dict(sorted(partition_counts.items())) != expected["partition_counts"]:
        raise ValueError("selected partition counts differ")
    if dict(sorted(source_counts.items())) != expected["source_counts"]:
        raise ValueError("selected source counts differ")
    rwc_titles = [
        str(row["factors"]["normalized_work_title"])
        for row in selected
        if row["source_id"] == RWC_SOURCE_ID
    ]
    if len(rwc_titles) != len(set(rwc_titles)):
        raise ValueError("selected RWC work titles repeat")
    allocation = {
        "schema_version": SCHEMA_VERSION,
        "state": PRIVATE_ALLOCATION_STATE,
        "rules_id": rules["rules_id"],
        "rules_sha256": candidate_index["rules_sha256"],
        "candidate_index_sha256": candidate_index_sha256,
        "source_identity_checkpoint_commit": rules["source_identity_checkpoint_commit"],
        "audio_generated": False,
        "scores_opened": False,
        "waveform_content_inspected": False,
        "duration_used_for_selection": False,
        "absolute_paths_recorded": False,
        "selected": selected,
    }
    diagnostics = {
        "vctk_selected_groups_per_gender": dict(sorted(vctk_gender_counts.items())),
        "rwc_selected_unique_normalized_title_count": len(set(rwc_titles)),
    }
    return allocation, diagnostics


def recursively_reject_absolute_paths(value: Any, label: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            recursively_reject_absolute_paths(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            recursively_reject_absolute_paths(child, f"{label}[{index}]")
    elif isinstance(value, str) and value.startswith("/"):
        raise ValueError(f"{label} contains an absolute path")


def recursively_reject_keys(value: Any, forbidden: set[str], label: str) -> None:
    if isinstance(value, dict):
        overlap = forbidden & set(value)
        if overlap:
            raise ValueError(f"{label} contains forbidden keys: {sorted(overlap)}")
        for key, child in value.items():
            recursively_reject_keys(child, forbidden, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            recursively_reject_keys(child, forbidden, f"{label}[{index}]")


def count_nested(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row[field]) for row in rows).items()))


def public_aggregate(
    rules: dict[str, Any],
    rules_sha256: str,
    candidate_index: dict[str, Any],
    candidate_index_sha256: str,
    allocation: dict[str, Any],
    allocation_sha256: str,
    diagnostics: dict[str, Any],
    replay_candidate_index: Path | None,
    replay_allocation: Path | None,
) -> dict[str, Any]:
    candidates = candidate_index["candidates"]
    selected = allocation["selected"]
    replay_verified = False
    if (replay_candidate_index is None) != (replay_allocation is None):
        raise ValueError("both replay comparison artifacts are required")
    if replay_candidate_index is not None and replay_allocation is not None:
        if sha256_file(replay_candidate_index) != candidate_index_sha256:
            raise ValueError("candidate-index replay differs")
        if sha256_file(replay_allocation) != allocation_sha256:
            raise ValueError("source-allocation replay differs")
        replay_verified = True
    candidate_counts = count_nested(candidates, "source_id")
    selected_source_counts = count_nested(selected, "source_id")
    selected_partition_counts = count_nested(selected, "evidence_partition")
    selected_domain_counts = count_nested(selected, "source_domain")
    aggregate = {
        "schema_version": SCHEMA_VERSION,
        "state": PUBLIC_STATE,
        "rules_id": rules["rules_id"],
        "rules_sha256": rules_sha256,
        "source_identity_checkpoint_commit": rules["source_identity_checkpoint_commit"],
        "audio_generated": False,
        "scores_opened": False,
        "waveform_content_inspected": False,
        "duration_used_for_selection": False,
        "measurements_or_labels_used_for_selection": False,
        "existing_v1_holdouts_included": False,
        "paths_redacted": True,
        "candidate_summary": {
            "candidate_count": len(candidates),
            "candidate_counts_by_source": candidate_counts,
        },
        "selected_summary": {
            "selected_member_count": len(selected),
            "selected_group_count": len({row["group_id"] for row in selected}),
            "selected_counts_by_partition": selected_partition_counts,
            "selected_counts_by_source": selected_source_counts,
            "selected_counts_by_source_domain": selected_domain_counts,
            "source_domain_count_by_partition": {
                partition: len(
                    {
                        str(row["source_domain"])
                        for row in selected
                        if row["evidence_partition"] == partition
                    }
                )
                for partition in sorted(selected_partition_counts)
            },
        },
        "constraint_checks": {
            **diagnostics,
            "one_selected_member_per_retained_group": True,
            "rwc_normalized_work_titles_unique": True,
            "transfer_partition_group_floors_preserved": True,
        },
        "private_artifact_bindings": {
            "candidate_index_bytes": len(canonical_json_bytes(candidate_index)),
            "candidate_index_sha256": candidate_index_sha256,
            "source_allocation_bytes": len(canonical_json_bytes(allocation)),
            "source_allocation_sha256": allocation_sha256,
        },
        "reproducibility": {
            "canonical_json": "UTF-8, sorted keys, two-space indentation, LF newline",
            "complete_replays_byte_identical": replay_verified,
            "timing_fields_emitted": False,
        },
        "selection_boundary": {
            "private_exact_identities_committed": False,
            "public_case_level_output_committed": False,
            "factor_levels_frozen": False,
            "toolchain_bindings_frozen": False,
            "fractional_assignment_frozen": False,
        },
        "next_gate": "Freeze factor levels separately; do not generate benchmark audio or open mechanism scores before factor, toolchain, and fractional-assignment freezes are all committed.",
    }
    privacy = rules["privacy"]
    recursively_reject_keys(
        aggregate, set(privacy["public_aggregate_forbidden_keys"]), "public aggregate"
    )
    recursively_reject_absolute_paths(aggregate, "public aggregate")
    return aggregate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-audit-root", type=Path, required=True)
    parser.add_argument("--v1-manifest", type=Path, required=True)
    parser.add_argument("--v1-audio-root", type=Path, required=True)
    parser.add_argument("--candidate-index-output", type=Path, required=True)
    parser.add_argument("--allocation-output", type=Path, required=True)
    parser.add_argument("--aggregate-output", type=Path, required=True)
    parser.add_argument("--compare-candidate-index", type=Path)
    parser.add_argument("--compare-allocation", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository_root = args.repository_root.resolve()
    rules_path = args.rules.resolve()
    rules = load_object(rules_path)
    validate_rules(rules)
    rules_sha256 = sha256_file(rules_path)
    candidate_index = build_candidate_index(
        rules,
        repository_root,
        args.source_audit_root.resolve(),
        args.v1_manifest.resolve(),
        args.v1_audio_root.resolve(),
        rules_sha256,
    )
    recursively_reject_absolute_paths(candidate_index, "candidate index")
    candidate_index_sha256 = sha256_bytes(canonical_json_bytes(candidate_index))
    allocation, diagnostics = select_candidates(
        rules, rules_sha256, candidate_index, candidate_index_sha256
    )
    recursively_reject_absolute_paths(allocation, "allocation")
    allocation_sha256 = sha256_bytes(canonical_json_bytes(allocation))
    aggregate = public_aggregate(
        rules,
        rules_sha256,
        candidate_index,
        candidate_index_sha256,
        allocation,
        allocation_sha256,
        diagnostics,
        args.compare_candidate_index,
        args.compare_allocation,
    )
    write_json_atomic(args.candidate_index_output, candidate_index)
    write_json_atomic(args.allocation_output, allocation)
    write_json_atomic(args.aggregate_output, aggregate)


if __name__ == "__main__":
    main()
