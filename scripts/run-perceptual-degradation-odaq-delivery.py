#!/usr/bin/env python3
"""Project the authorized ODAQ clean references into two private PCM replays."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-delivery-authorization-20260814.json"
)
PUBLIC_ACQUISITION_RESULT = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-result-20260813.json"
)
ATTRIBUTION_AUDIT = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-odaq-attribution-audit-20260804-001.json"
)
AUTHORIZATION_SCRIPT = (
    ROOT / "scripts" / "validate-perceptual-degradation-odaq-delivery-authorization.py"
)
ACQUISITION_SCRIPT = (
    ROOT / "scripts" / "acquire-perceptual-degradation-odaq-references.py"
)
PROJECTION_SCRIPT = ROOT / "scripts" / "prepare-perceptual-degradation-odaq-delivery.py"
MINIMUM_FREE_BYTES = 15 * 1024**3


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AUTH = load_module("odaq_delivery_authorization", AUTHORIZATION_SCRIPT)
ACQUIRE = load_module("odaq_reference_acquisition", ACQUISITION_SCRIPT)
PROJECT = load_module("odaq_delivery_projection", PROJECTION_SCRIPT)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return ACQUIRE.sha256_file(path)


def inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def atomic_bytes(path: Path, value: bytes, mode: int = 0o600) -> None:
    partial = path.with_name(f"{path.name}.partial")
    with partial.open("wb") as output:
        output.write(value)
        output.flush()
        os.fsync(output.fileno())
    partial.replace(path)
    path.chmod(mode)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, json_bytes(value))


def committed_authorization(path: Path = AUTHORIZATION) -> tuple[dict[str, Any], str]:
    plan = AUTH.load_json(AUTH.PLAN)
    plan_errors = AUTH.validate_plan(plan)
    authorization = load_json(path)
    errors = plan_errors + AUTH.validate_authorization(authorization, plan)
    if errors:
        raise ValueError("authorization validation failed: " + "; ".join(errors))
    return authorization, sha256_file(path)


def expected_source_inventory() -> dict[str, Any]:
    result = load_json(PUBLIC_ACQUISITION_RESULT)
    retained = result["retained_inventory"]
    return {
        "reference_count": retained["reference_count"],
        "retained_audio_bytes": retained["retained_audio_bytes"],
        "completed_inventory_sha256": retained["completed_inventory_sha256"],
        "sample_rate_hz": retained["sample_rate_hz"],
        "channel_count": retained["channel_count"],
        "float32_reference_count": 7,
        "extensible_s24_reference_count": 9,
    }


def attribution_context(audit: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    records: dict[str, dict[str, Any]] = {}
    for collection in ("licence_records", "dependency_licence_records"):
        values = audit.get(collection)
        if not isinstance(values, list):
            raise ValueError(f"attribution collection differs: {collection}")
        for record in values:
            record_id = record.get("licence_record_id") if isinstance(record, dict) else None
            if not isinstance(record_id, str) or record_id in records:
                raise ValueError("attribution record identity differs")
            records[record_id] = record
    groups: dict[str, dict[str, Any]] = {}
    for group in audit.get("listening_groups", []):
        folder_id = group.get("folder_id") if isinstance(group, dict) else None
        if not isinstance(folder_id, str) or folder_id in groups:
            raise ValueError("attribution listening-group identity differs")
        groups[folder_id] = group
    return records, groups


def validate_source_inventory(
    source_root: Path,
    expected: dict[str, Any],
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    root = source_root.resolve()
    if inside_repository(root):
        raise ValueError("retained source root must remain outside the repository")
    state_path = root / "acquisition.json"
    sources_root = root / "sources"
    partial_root = root / ".partial"
    if (
        root.is_symlink()
        or not root.is_dir()
        or state_path.is_symlink()
        or not state_path.is_file()
        or sources_root.is_symlink()
        or not sources_root.is_dir()
        or partial_root.is_symlink()
        or not partial_root.is_dir()
    ):
        raise ValueError("retained source layout differs")
    if {item.name for item in root.iterdir()} != {"acquisition.json", "sources", ".partial"}:
        raise ValueError("retained source root contains an unexpected entry")
    if any(partial_root.iterdir()):
        raise ValueError("retained source partial directory is not empty")

    state = load_json(state_path)
    completed = state.get("completed")
    if not isinstance(completed, list):
        raise ValueError("retained completed inventory differs")
    if (
        state.get("schema_version") != 1
        or state.get("state") != "reference_acquisition_complete"
        or state.get("completed_count") != expected["reference_count"]
        or len(completed) != expected["reference_count"]
        or state.get("retained_audio_bytes") != expected["retained_audio_bytes"]
        or state.get("completed_inventory_sha256") != expected["completed_inventory_sha256"]
        or ACQUIRE.completed_inventory_sha256(completed) != expected["completed_inventory_sha256"]
        or state.get("minimum_free_bytes", 0) < MINIMUM_FREE_BYTES
    ):
        raise ValueError("retained source journal differs from the frozen inventory")
    for key in ("processed_condition_opened", "listening_score_opened", "metric_score_opened"):
        if state.get(key) is not False:
            raise ValueError(f"retained source access boundary differs: {key}")

    attribution_records, groups = attribution_context(audit)
    expected_files: set[str] = set()
    seen_ids: set[str] = set()
    float_count = 0
    integer_count = 0
    for record in completed:
        if not isinstance(record, dict):
            raise ValueError("retained source record differs")
        relative = Path(str(record.get("relative_path", "")))
        opaque_id = record.get("opaque_reference_id")
        folder_id = record.get("folder_id")
        if (
            not isinstance(opaque_id, str)
            or opaque_id in seen_ids
            or relative.parts != ("sources", f"{opaque_id}.wav")
            or relative.is_absolute()
        ):
            raise ValueError("retained source path or identity differs")
        seen_ids.add(opaque_id)
        expected_files.add(relative.name)
        group = groups.get(str(folder_id))
        licence_ids = record.get("licence_record_ids")
        if (
            group is None
            or group.get("source_id") != record.get("source_id")
            or group.get("licence_record_ids") != licence_ids
            or not isinstance(licence_ids, list)
            or not licence_ids
            or any(
                record_id not in attribution_records
                or attribution_records[record_id].get("attribution_notice_ready") is not True
                for record_id in licence_ids
            )
        ):
            raise ValueError("retained attribution binding differs")
        path = root / relative
        ACQUIRE.verify_retained(path, record)
        geometry = record.get("pcm_geometry", {})
        if (
            geometry.get("sample_rate_hz") != expected["sample_rate_hz"]
            or geometry.get("channel_count") != expected["channel_count"]
        ):
            raise ValueError("retained source PCM geometry differs")
        if geometry.get("sample_encoding") == "ieee_float_pcm" and geometry.get("bit_depth") == 32:
            float_count += 1
        elif (
            geometry.get("sample_encoding") == "signed_integer_pcm"
            and geometry.get("bit_depth") == 24
            and geometry.get("container_encoding") == "wave_format_extensible"
        ):
            integer_count += 1
        else:
            raise ValueError("retained source encoding differs")
    actual_files = {item.name for item in sources_root.iterdir() if item.is_file() and not item.is_symlink()}
    if actual_files != expected_files or len(list(sources_root.iterdir())) != len(expected_files):
        raise ValueError("retained source file inventory differs")
    if (
        float_count != expected["float32_reference_count"]
        or integer_count != expected["extensible_s24_reference_count"]
    ):
        raise ValueError("retained source encoding distribution differs")
    return completed


def delivery_id(authorization_sha256: str, opaque_reference_id: str) -> str:
    digest = sha256_bytes(f"{authorization_sha256}:{opaque_reference_id}".encode())
    return f"odaq-delivery-{digest[:24]}"


def output_inventory_sha256(completed: list[dict[str, Any]]) -> str:
    return sha256_bytes(json.dumps(completed, sort_keys=True, separators=(",", ":")).encode())


def new_replay_state(
    authorization: dict[str, Any], authorization_sha256: str, reference_count: int
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "state": "private_delivery_projection_in_progress",
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": authorization_sha256,
        "input_inventory_sha256": authorization["authorization_scope"]["retained_inventory_sha256"],
        "reference_count": reference_count,
        "minimum_free_bytes": MINIMUM_FREE_BYTES,
        "maximum_workers": 1,
        "processed_condition_opened": False,
        "listening_score_opened": False,
        "perceptual_metric_executed": False,
        "listener_response_collected": False,
        "sealed_evidence_opened": False,
        "public_verdict_emitted": False,
        "completed": [],
    }


def prepare_replay_root(
    root: Path,
    authorization: dict[str, Any],
    authorization_sha256: str,
    reference_count: int,
    resume: bool,
) -> dict[str, Any]:
    if inside_repository(root):
        raise ValueError("private replay root must remain outside the repository")
    state_path = root / "delivery.json"
    if resume:
        if not state_path.is_file() or state_path.is_symlink():
            raise ValueError("resume requires an existing regular delivery journal")
        state = load_json(state_path)
        expected = new_replay_state(authorization, authorization_sha256, reference_count)
        for key, value in expected.items():
            if key not in {"state", "completed"} and state.get(key) != value:
                raise ValueError(f"existing replay journal differs: {key}")
        if state.get("state") not in {
            "private_delivery_projection_in_progress",
            "private_delivery_projection_complete",
        } or not isinstance(state.get("completed"), list):
            raise ValueError("existing replay journal state differs")
        for directory in (root / "sources", root / ".partial"):
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("existing replay directory differs")
        return state
    if root.exists() and any(root.iterdir()):
        raise ValueError("fresh replay root must be empty")
    (root / "sources").mkdir(parents=True, mode=0o700)
    (root / ".partial").mkdir(mode=0o700)
    root.chmod(0o700)
    state = new_replay_state(authorization, authorization_sha256, reference_count)
    atomic_json(state_path, state)
    return state


def assert_projection_matches_source(record: dict[str, Any], projection: dict[str, Any]) -> None:
    geometry = record["pcm_geometry"]
    expected = {
        "sample_rate_hz": geometry["sample_rate_hz"],
        "channel_count": geometry["channel_count"],
        "input_bit_depth": geometry["bit_depth"],
        "frame_count": geometry["frame_count"],
        "input_sample_encoding": geometry["sample_encoding"],
    }
    for key, value in expected.items():
        if projection.get(key) != value:
            raise ValueError(f"projected source geometry differs: {key}")


def completed_record(
    source: dict[str, Any],
    authorization_sha256: str,
    output: bytes,
    projection: dict[str, Any],
) -> dict[str, Any]:
    opaque_id = delivery_id(authorization_sha256, source["opaque_reference_id"])
    return {
        "source_opaque_reference_id": source["opaque_reference_id"],
        "opaque_delivery_id": opaque_id,
        "relative_path": f"sources/{opaque_id}.wav",
        "source_sha256": source["sha256"],
        "source_byte_length": source["byte_length"],
        "output_sha256": sha256_bytes(output),
        "output_byte_length": len(output),
        "source_pcm_geometry": source["pcm_geometry"],
        "output_pcm_geometry": {
            "sample_rate_hz": projection["sample_rate_hz"],
            "channel_count": projection["channel_count"],
            "bit_depth": projection["output_bit_depth"],
            "frame_count": projection["frame_count"],
            "sample_encoding": projection["output_sample_encoding"],
            "container_encoding": projection["output_container_encoding"],
        },
        "operation": projection["operation"],
        "licence_record_ids": source["licence_record_ids"],
    }


def verify_completed_output(root: Path, record: dict[str, Any]) -> None:
    relative = Path(str(record.get("relative_path", "")))
    if relative.parts != ("sources", f"{record.get('opaque_delivery_id')}.wav"):
        raise ValueError("completed output path differs")
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("completed output is absent or not regular")
    if path.stat().st_size != record.get("output_byte_length") or sha256_file(path) != record.get("output_sha256"):
        raise ValueError("completed output integrity differs")


def attribution_attachment(
    authorization_sha256: str,
    completed: list[dict[str, Any]],
    audit: dict[str, Any],
) -> dict[str, Any]:
    records, _ = attribution_context(audit)
    referenced_ids = sorted({record_id for item in completed for record_id in item["licence_record_ids"]})
    return {
        "schema_version": 1,
        "state": "private_odaq_attribution_attached_out_of_band",
        "authorization_sha256": authorization_sha256,
        "attribution_audit": {
            "path": str(ATTRIBUTION_AUDIT.relative_to(ROOT)),
            "sha256": sha256_file(ATTRIBUTION_AUDIT),
        },
        "mappings": [
            {
                "opaque_delivery_id": item["opaque_delivery_id"],
                "source_opaque_reference_id": item["source_opaque_reference_id"],
                "licence_record_ids": item["licence_record_ids"],
            }
            for item in completed
        ],
        "licence_records": [records[record_id] for record_id in referenced_ids],
    }


def run_replay(
    *,
    source_root: Path,
    replay_root: Path,
    records: list[dict[str, Any]],
    authorization: dict[str, Any],
    authorization_sha256: str,
    audit: dict[str, Any],
    resume: bool,
    disk_free: Callable[[Path], int] | None = None,
) -> dict[str, Any]:
    root = replay_root.resolve()
    state = prepare_replay_root(root, authorization, authorization_sha256, len(records), resume)
    completed_by_source = {item["source_opaque_reference_id"]: item for item in state["completed"]}
    if len(completed_by_source) != len(state["completed"]):
        raise ValueError("existing replay journal contains duplicate sources")
    get_free = disk_free or (lambda path: shutil.disk_usage(path).free)
    for source in records:
        source_id = source["opaque_reference_id"]
        existing = completed_by_source.get(source_id)
        if existing is not None:
            verify_completed_output(root, existing)
            continue
        if get_free(root) - source["byte_length"] < MINIMUM_FREE_BYTES:
            raise ValueError("delivery projection would cross the 15 GiB disk reserve")
        source_path = source_root.resolve() / source["relative_path"]
        value = source_path.read_bytes()
        if len(value) != source["byte_length"] or sha256_bytes(value) != source["sha256"]:
            raise ValueError("retained source changed after inventory verification")
        output, projection = PROJECT.project_delivery_wav(value)
        assert_projection_matches_source(source, projection)
        item = completed_record(source, authorization_sha256, output, projection)
        destination = root / item["relative_path"]
        partial = root / ".partial" / f"{item['opaque_delivery_id']}.wav.partial"
        atomic_bytes(partial, output)
        if destination.exists():
            if destination.is_symlink() or destination.read_bytes() != output:
                raise ValueError("unjournaled delivery output differs")
            partial.unlink()
        else:
            partial.replace(destination)
            destination.chmod(0o600)
        state["completed"].append(item)
        completed_by_source[source_id] = item
        atomic_json(root / "delivery.json", state)

    if len(state["completed"]) != len(records):
        raise ValueError("delivery replay did not complete every reference")
    attachment = attribution_attachment(authorization_sha256, state["completed"], audit)
    atomic_json(root / "attribution.json", attachment)
    state["state"] = "private_delivery_projection_complete"
    state["completed_count"] = len(state["completed"])
    state["output_inventory_sha256"] = output_inventory_sha256(state["completed"])
    state["attribution_sha256"] = sha256_file(root / "attribution.json")
    atomic_json(root / "delivery.json", state)
    return state


def execute(
    source_root: Path,
    replay_roots: list[Path],
    authorization_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    if len(replay_roots) != 2 or replay_roots[0].resolve() == replay_roots[1].resolve():
        raise ValueError("exactly two distinct private replay roots are required")
    for root in replay_roots:
        if inside_repository(root):
            raise ValueError("private replay roots must remain outside the repository")
        if not resume and root.exists() and any(root.iterdir()):
            raise ValueError("both private replay roots must be fresh")
    authorization, authorization_sha256 = committed_authorization(authorization_path)
    audit = load_json(ATTRIBUTION_AUDIT)
    records = validate_source_inventory(source_root, expected_source_inventory(), audit)
    states = [
        run_replay(
            source_root=source_root,
            replay_root=root,
            records=records,
            authorization=authorization,
            authorization_sha256=authorization_sha256,
            audit=audit,
            resume=resume,
        )
        for root in replay_roots
    ]
    if states[0]["completed"] != states[1]["completed"]:
        raise ValueError("private replay inventories are not byte-identical")
    if states[0]["output_inventory_sha256"] != states[1]["output_inventory_sha256"]:
        raise ValueError("private replay inventory digests differ")
    if (replay_roots[0].resolve() / "attribution.json").read_bytes() != (
        replay_roots[1].resolve() / "attribution.json"
    ).read_bytes():
        raise ValueError("private replay attribution attachments differ")
    return {
        "status": "private_odaq_delivery_two_replays_complete",
        "reference_count": len(records),
        "input_inventory_sha256": authorization["authorization_scope"]["retained_inventory_sha256"],
        "output_inventory_sha256": states[0]["output_inventory_sha256"],
        "replay_inventories_byte_identical": True,
        "attribution_attachments_byte_identical": True,
        "minimum_free_disk_gib_preserved": 15,
        "maximum_workers": 1,
        "processed_conditions_opened": False,
        "scores_or_metrics_opened": False,
        "listener_collection_performed": False,
        "sealed_evidence_opened": False,
        "public_verdict_emitted": False,
        "private_paths_redacted": True,
        "per_reference_hashes_redacted": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--replay-root", type=Path, action="append", required=True)
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = execute(args.source_root, args.replay_root, args.authorization, args.resume)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
