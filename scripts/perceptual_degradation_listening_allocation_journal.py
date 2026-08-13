#!/usr/bin/env python3
"""Synthetic-only audit of an append-only listening allocation journal."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, NamedTuple


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "listening-allocation-journal-audit-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-listening-allocation-journal-audit-"
    "20260814-001.json"
)
GENESIS_SHA256 = "0" * 64
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
STREAM_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{7,63}$")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ALLOCATOR = _load_module(
    "perceptual_degradation_allocator_v3_for_journal",
    ROOT / "scripts/perceptual_degradation_listening_allocation_v3.py",
)
RESOURCE = _load_module(
    "perceptual_degradation_resource_frontier_for_journal",
    ROOT / "scripts/perceptual_degradation_listening_resource_frontier.py",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


EXPECTED_AUTHORIZATION = {
    "synthetic_journal_audit_authorized": True,
    "real_listener_software_authorized": False,
    "participant_contact_authorized": False,
    "identity_storage_authorized": False,
    "response_storage_authorized": False,
    "human_collection_authorized": False,
    "recruitment_authorized": False,
    "retained_audio_read_authorized": False,
    "new_audio_acquisition_authorized": False,
    "stimulus_generation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_CANDIDATE_CONTRACT = {
    "database": "sqlite_single_database_file",
    "journal_mode": "WAL",
    "synchronous_mode": "FULL",
    "reservation_transaction": "BEGIN_IMMEDIATE",
    "stream_configuration": "immutable_and_sha256_bound",
    "reservation_rows": "insert_only_with_update_and_delete_triggers",
    "allocation_index": (
        "zero_based_contiguous_per_stream_derived_inside_transaction"
    ),
    "request_id": "opaque_sha256_unique_per_stream",
    "request_binding": "opaque_sha256_no_identity_or_outcome",
    "eligibility_attestation": (
        "opaque_sha256_synthetic_only_semantics_unfrozen"
    ),
    "event_chain": (
        "sha256_over_canonical_row_and_previous_event_sha256"
    ),
    "idempotent_retry": (
        "same_request_id_binding_and_attestation_returns_same_index"
    ),
    "conflicting_retry": (
        "same_request_id_with_changed_binding_or_attestation_rejected"
    ),
    "participant_key_stored": False,
    "identity_stored": False,
    "response_stored": False,
    "outcome_stored": False,
    "timestamp_stored": False,
}

EXPECTED_WORKLOAD = {
    "concurrency_trials": 16,
    "streams_per_trial": 2,
    "unique_requests_per_stream": 96,
    "calls_per_request": 3,
    "maximum_workers": 24,
    "restart_requests_per_fault": 24,
    "logical_fault_points": [
        "before_begin",
        "after_begin_before_insert",
        "after_insert_before_commit",
        "after_commit_before_reply",
    ],
    "immutability_probes": [
        "reservation_update",
        "reservation_delete",
        "stream_update",
        "stream_delete",
    ],
    "tamper_detection_probes": [
        "event_hash_change",
        "request_binding_change",
        "middle_row_delete",
    ],
    "v3_integration_prefix": 192,
    "v3_trial_limits": {"subtle": 8, "mushra": 6},
}


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("plan_id") != (
        "perceptual-degradation-listening-allocation-journal-audit-"
        "20260814-001"
    ):
        errors.append("plan_id differs")
    if plan.get("state") != (
        "synthetic_allocation_journal_candidate_audit_no_operational_selection"
    ):
        errors.append("state differs")
    expected_bindings = {
        "listening_preparation_gate",
        "listening_protocol",
        "response_envelope_schema",
        "allocator_v3",
        "allocator_v3_audit_plan",
        "allocator_v3_audit_report",
        "resource_frontier_plan",
        "symbolic_manifest_builder",
        "missingness_plan",
        "missingness_report",
        "retained_design_plan",
        "retained_design_report",
    }
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("bindings differ")
    else:
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"binding {binding_id} must be an object")
                continue
            relative = binding.get("path")
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"binding {binding_id} path must be relative")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"binding {binding_id} path is missing")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"binding {binding_id} sha256 differs")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization differs")
    if plan.get("candidate_contract") != EXPECTED_CANDIDATE_CONTRACT:
        errors.append("candidate contract differs")
    if plan.get("audit_workload") != EXPECTED_WORKLOAD:
        errors.append("audit workload differs")
    claims = plan.get("claim_boundary")
    if not isinstance(claims, dict) or not claims:
        errors.append("claim boundary missing")
    elif any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return errors


class StreamConfig(NamedTuple):
    stream_id: str
    manifest_id: str
    manifest_sha256: str
    allocator_policy_id: str
    allocation_seed_sha256: str
    subtle_trial_limit: int
    mushra_trial_limit: int
    eligibility_contract_id: str

    def validate(self) -> None:
        if not STREAM_ID_PATTERN.fullmatch(self.stream_id):
            raise ValueError("stream_id must be an opaque identifier")
        if not STREAM_ID_PATTERN.fullmatch(self.manifest_id):
            raise ValueError("manifest_id must be an opaque identifier")
        for name, value in (
            ("manifest_sha256", self.manifest_sha256),
            ("allocation_seed_sha256", self.allocation_seed_sha256),
        ):
            if not SHA256_PATTERN.fullmatch(value):
                raise ValueError(f"{name} must be a SHA-256 digest")
        if not STREAM_ID_PATTERN.fullmatch(self.allocator_policy_id):
            raise ValueError("allocator_policy_id must be an opaque identifier")
        if not STREAM_ID_PATTERN.fullmatch(self.eligibility_contract_id):
            raise ValueError("eligibility_contract_id must be opaque")
        for name, value in (
            ("subtle_trial_limit", self.subtle_trial_limit),
            ("mushra_trial_limit", self.mushra_trial_limit),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.subtle_trial_limit + self.mushra_trial_limit == 0:
            raise ValueError("at least one trial limit must be positive")

    def payload(self) -> dict[str, Any]:
        return {
            "state": "synthetic_audit_only",
            "stream_id": self.stream_id,
            "manifest_id": self.manifest_id,
            "manifest_sha256": self.manifest_sha256,
            "allocator_policy_id": self.allocator_policy_id,
            "allocation_seed_sha256": self.allocation_seed_sha256,
            "subtle_trial_limit": self.subtle_trial_limit,
            "mushra_trial_limit": self.mushra_trial_limit,
            "eligibility_contract_id": self.eligibility_contract_id,
            "human_collection_authorized": False,
            "identity_stored": False,
            "response_stored": False,
            "outcome_stored": False,
        }

    @property
    def config_sha256(self) -> str:
        return canonical_sha256(self.payload())


class LogicalFault(RuntimeError):
    """A precommit fault whose operation must be absent after close."""


class CommittedReplyLost(RuntimeError):
    """A committed operation whose response was not delivered to its caller."""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS streams (
    stream_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state = 'synthetic_audit_only'),
    manifest_id TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    allocator_policy_id TEXT NOT NULL,
    allocation_seed_sha256 TEXT NOT NULL,
    subtle_trial_limit INTEGER NOT NULL CHECK (subtle_trial_limit >= 0),
    mushra_trial_limit INTEGER NOT NULL CHECK (mushra_trial_limit >= 0),
    eligibility_contract_id TEXT NOT NULL,
    human_collection_authorized INTEGER NOT NULL CHECK (
        human_collection_authorized = 0
    ),
    identity_stored INTEGER NOT NULL CHECK (identity_stored = 0),
    response_stored INTEGER NOT NULL CHECK (response_stored = 0),
    outcome_stored INTEGER NOT NULL CHECK (outcome_stored = 0),
    config_sha256 TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS reservations (
    stream_id TEXT NOT NULL,
    allocation_index INTEGER NOT NULL CHECK (allocation_index >= 0),
    request_id TEXT NOT NULL,
    request_binding_sha256 TEXT NOT NULL,
    eligibility_attestation_sha256 TEXT NOT NULL,
    previous_event_sha256 TEXT NOT NULL,
    event_sha256 TEXT NOT NULL,
    PRIMARY KEY (stream_id, allocation_index),
    UNIQUE (stream_id, request_id),
    FOREIGN KEY (stream_id) REFERENCES streams(stream_id)
);

CREATE TRIGGER IF NOT EXISTS streams_no_update
BEFORE UPDATE ON streams
BEGIN
    SELECT RAISE(ABORT, 'streams are immutable');
END;

CREATE TRIGGER IF NOT EXISTS streams_no_delete
BEFORE DELETE ON streams
BEGIN
    SELECT RAISE(ABORT, 'streams are append-only');
END;

CREATE TRIGGER IF NOT EXISTS reservations_no_update
BEFORE UPDATE ON reservations
BEGIN
    SELECT RAISE(ABORT, 'reservations are immutable');
END;

CREATE TRIGGER IF NOT EXISTS reservations_no_delete
BEFORE DELETE ON reservations
BEGIN
    SELECT RAISE(ABORT, 'reservations are append-only');
END;
"""

EXPECTED_TRIGGERS = {
    "streams_no_update",
    "streams_no_delete",
    "reservations_no_update",
    "reservations_no_delete",
}
EXPECTED_STREAM_COLUMNS = {
    "stream_id",
    "state",
    "manifest_id",
    "manifest_sha256",
    "allocator_policy_id",
    "allocation_seed_sha256",
    "subtle_trial_limit",
    "mushra_trial_limit",
    "eligibility_contract_id",
    "human_collection_authorized",
    "identity_stored",
    "response_stored",
    "outcome_stored",
    "config_sha256",
}
EXPECTED_RESERVATION_COLUMNS = {
    "stream_id",
    "allocation_index",
    "request_id",
    "request_binding_sha256",
    "eligibility_attestation_sha256",
    "previous_event_sha256",
    "event_sha256",
}


def event_payload(
    *,
    stream_id: str,
    allocation_index: int,
    request_id: str,
    request_binding_sha256: str,
    eligibility_attestation_sha256: str,
    previous_event_sha256: str,
) -> dict[str, Any]:
    return {
        "stream_id": stream_id,
        "allocation_index": allocation_index,
        "request_id": request_id,
        "request_binding_sha256": request_binding_sha256,
        "eligibility_attestation_sha256": eligibility_attestation_sha256,
        "previous_event_sha256": previous_event_sha256,
    }


class AllocationJournal:
    def __init__(self, path: Path, *, timeout_seconds: float = 30.0):
        self.path = Path(path)
        self.timeout_seconds = timeout_seconds

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            f"PRAGMA busy_timeout = {round(self.timeout_seconds * 1000)}"
        )
        return connection

    def initialize_database(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            journal_mode = connection.execute(
                "PRAGMA journal_mode = WAL"
            ).fetchone()[0]
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(SCHEMA_SQL)
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            if str(journal_mode).upper() != "WAL" or synchronous != 2:
                raise RuntimeError("required SQLite durability settings unavailable")
            return {
                "journal_mode": str(journal_mode).upper(),
                "synchronous": "FULL" if synchronous == 2 else str(synchronous),
            }
        finally:
            connection.close()

    def initialize_stream(self, config: StreamConfig) -> bool:
        config.validate()
        self.initialize_database()
        payload = config.payload()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM streams WHERE stream_id = ?",
                (config.stream_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO streams (
                        stream_id, state, manifest_id, manifest_sha256,
                        allocator_policy_id, allocation_seed_sha256,
                        subtle_trial_limit, mushra_trial_limit,
                        eligibility_contract_id, human_collection_authorized,
                        identity_stored, response_stored, outcome_stored,
                        config_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["stream_id"],
                        payload["state"],
                        payload["manifest_id"],
                        payload["manifest_sha256"],
                        payload["allocator_policy_id"],
                        payload["allocation_seed_sha256"],
                        payload["subtle_trial_limit"],
                        payload["mushra_trial_limit"],
                        payload["eligibility_contract_id"],
                        0,
                        0,
                        0,
                        0,
                        config.config_sha256,
                    ),
                )
                connection.commit()
                return True
            if existing["config_sha256"] != config.config_sha256:
                raise ValueError("stream configuration conflict")
            connection.commit()
            return False
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def reserve(
        self,
        *,
        stream_id: str,
        request_id: str,
        request_binding_sha256: str,
        eligibility_attestation_sha256: str,
        fault_point: str | None = None,
    ) -> dict[str, Any]:
        if not STREAM_ID_PATTERN.fullmatch(stream_id):
            raise ValueError("stream_id must be an opaque identifier")
        for name, value in (
            ("request_id", request_id),
            ("request_binding_sha256", request_binding_sha256),
            ("eligibility_attestation_sha256", eligibility_attestation_sha256),
        ):
            if not SHA256_PATTERN.fullmatch(value):
                raise ValueError(f"{name} must be a SHA-256 digest")
        allowed_faults = {
            None,
            "before_begin",
            "after_begin_before_insert",
            "after_insert_before_commit",
            "after_commit_before_reply",
        }
        if fault_point not in allowed_faults:
            raise ValueError("unsupported fault point")
        if fault_point == "before_begin":
            raise LogicalFault("fault before transaction begin")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if fault_point == "after_begin_before_insert":
                raise LogicalFault("fault after begin and before insert")
            stream = connection.execute(
                "SELECT config_sha256 FROM streams WHERE stream_id = ?",
                (stream_id,),
            ).fetchone()
            if stream is None:
                raise ValueError("unknown stream")
            existing = connection.execute(
                """
                SELECT * FROM reservations
                WHERE stream_id = ? AND request_id = ?
                """,
                (stream_id, request_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["request_binding_sha256"]
                    != request_binding_sha256
                    or existing["eligibility_attestation_sha256"]
                    != eligibility_attestation_sha256
                ):
                    raise ValueError("conflicting idempotent reservation retry")
                connection.commit()
                return {
                    "stream_id": stream_id,
                    "allocation_index": existing["allocation_index"],
                    "event_sha256": existing["event_sha256"],
                    "created": False,
                    "idempotent_retry": True,
                    "human_collection_authorized": False,
                }

            previous = connection.execute(
                """
                SELECT allocation_index, event_sha256
                FROM reservations WHERE stream_id = ?
                ORDER BY allocation_index DESC LIMIT 1
                """,
                (stream_id,),
            ).fetchone()
            if previous is None:
                allocation_index = 0
                previous_event_sha256 = GENESIS_SHA256
            else:
                allocation_index = previous["allocation_index"] + 1
                previous_event_sha256 = previous["event_sha256"]
            payload = event_payload(
                stream_id=stream_id,
                allocation_index=allocation_index,
                request_id=request_id,
                request_binding_sha256=request_binding_sha256,
                eligibility_attestation_sha256=(
                    eligibility_attestation_sha256
                ),
                previous_event_sha256=previous_event_sha256,
            )
            event_sha256 = canonical_sha256(payload)
            connection.execute(
                """
                INSERT INTO reservations (
                    stream_id, allocation_index, request_id,
                    request_binding_sha256, eligibility_attestation_sha256,
                    previous_event_sha256, event_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stream_id,
                    allocation_index,
                    request_id,
                    request_binding_sha256,
                    eligibility_attestation_sha256,
                    previous_event_sha256,
                    event_sha256,
                ),
            )
            if fault_point == "after_insert_before_commit":
                raise LogicalFault("fault after insert and before commit")
            connection.commit()
            if fault_point == "after_commit_before_reply":
                raise CommittedReplyLost("commit succeeded but reply was lost")
            return {
                "stream_id": stream_id,
                "allocation_index": allocation_index,
                "event_sha256": event_sha256,
                "created": True,
                "idempotent_retry": False,
                "human_collection_authorized": False,
            }
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def checkpoint(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        finally:
            connection.close()


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def verify_journal(
    path: Path,
    *,
    expected_configs: dict[str, StreamConfig] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        stream_columns = _table_columns(connection, "streams")
        reservation_columns = _table_columns(connection, "reservations")
        if stream_columns != EXPECTED_STREAM_COLUMNS:
            errors.append("stream columns differ")
        if reservation_columns != EXPECTED_RESERVATION_COLUMNS:
            errors.append("reservation columns differ")
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
        }
        if triggers != EXPECTED_TRIGGERS:
            errors.append("append-only triggers differ")
        streams = connection.execute(
            "SELECT * FROM streams ORDER BY stream_id"
        ).fetchall()
        observed_ids = {row["stream_id"] for row in streams}
        if expected_configs is not None and observed_ids != set(expected_configs):
            errors.append("stream set differs")
        stream_summaries = []
        total_reservations = 0
        for stream in streams:
            payload = {
                "state": stream["state"],
                "stream_id": stream["stream_id"],
                "manifest_id": stream["manifest_id"],
                "manifest_sha256": stream["manifest_sha256"],
                "allocator_policy_id": stream["allocator_policy_id"],
                "allocation_seed_sha256": stream["allocation_seed_sha256"],
                "subtle_trial_limit": stream["subtle_trial_limit"],
                "mushra_trial_limit": stream["mushra_trial_limit"],
                "eligibility_contract_id": stream["eligibility_contract_id"],
                "human_collection_authorized": bool(
                    stream["human_collection_authorized"]
                ),
                "identity_stored": bool(stream["identity_stored"]),
                "response_stored": bool(stream["response_stored"]),
                "outcome_stored": bool(stream["outcome_stored"]),
            }
            if canonical_sha256(payload) != stream["config_sha256"]:
                errors.append(f"stream config hash differs: {stream['stream_id']}")
            if any(
                payload[key]
                for key in (
                    "human_collection_authorized",
                    "identity_stored",
                    "response_stored",
                    "outcome_stored",
                )
            ):
                errors.append(f"stream authority differs: {stream['stream_id']}")
            if expected_configs is not None:
                expected = expected_configs.get(stream["stream_id"])
                if expected is not None and stream["config_sha256"] != (
                    expected.config_sha256
                ):
                    errors.append(
                        f"expected stream config differs: {stream['stream_id']}"
                    )
            reservations = connection.execute(
                """
                SELECT * FROM reservations WHERE stream_id = ?
                ORDER BY allocation_index
                """,
                (stream["stream_id"],),
            ).fetchall()
            previous_event_sha256 = GENESIS_SHA256
            request_ids: set[str] = set()
            for expected_index, row in enumerate(reservations):
                if row["allocation_index"] != expected_index:
                    errors.append(
                        f"allocation index gap: {stream['stream_id']}"
                    )
                if row["request_id"] in request_ids:
                    errors.append(f"duplicate request: {stream['stream_id']}")
                request_ids.add(row["request_id"])
                if row["previous_event_sha256"] != previous_event_sha256:
                    errors.append(f"event chain differs: {stream['stream_id']}")
                payload = event_payload(
                    stream_id=row["stream_id"],
                    allocation_index=row["allocation_index"],
                    request_id=row["request_id"],
                    request_binding_sha256=row["request_binding_sha256"],
                    eligibility_attestation_sha256=(
                        row["eligibility_attestation_sha256"]
                    ),
                    previous_event_sha256=row["previous_event_sha256"],
                )
                if canonical_sha256(payload) != row["event_sha256"]:
                    errors.append(f"event hash differs: {stream['stream_id']}")
                previous_event_sha256 = row["event_sha256"]
            total_reservations += len(reservations)
            stream_summaries.append(
                {
                    "stream_id": stream["stream_id"],
                    "reservation_count": len(reservations),
                    "first_allocation_index": 0 if reservations else None,
                    "last_allocation_index": (
                        len(reservations) - 1 if reservations else None
                    ),
                    "contiguous": all(
                        row["allocation_index"] == index
                        for index, row in enumerate(reservations)
                    ),
                    "unique_request_count": len(request_ids),
                    "terminal_event_sha256": previous_event_sha256,
                    "human_collection_authorized": False,
                }
            )
        return {
            "valid": not errors,
            "errors": sorted(set(errors)),
            "stream_count": len(streams),
            "reservation_count": total_reservations,
            "streams": stream_summaries,
            "identity_columns_present": bool(
                {"participant_id", "participant_key", "identity"}
                & (stream_columns | reservation_columns)
            ),
            "response_or_outcome_columns_present": bool(
                {"response", "outcome", "score", "rating"}
                & (stream_columns | reservation_columns)
            ),
        }
    finally:
        connection.close()


def _synthetic_config(
    *,
    stream_id: str,
    manifest_id: str = "manifest-symbolic-journal-0001",
    manifest_sha256: str | None = None,
    subtle_trial_limit: int = 8,
    mushra_trial_limit: int = 6,
) -> StreamConfig:
    return StreamConfig(
        stream_id=stream_id,
        manifest_id=manifest_id,
        manifest_sha256=manifest_sha256 or digest("synthetic-manifest"),
        allocator_policy_id=ALLOCATOR.POLICY_ID,
        allocation_seed_sha256=digest("synthetic-allocation-seed"),
        subtle_trial_limit=subtle_trial_limit,
        mushra_trial_limit=mushra_trial_limit,
        eligibility_contract_id="synthetic-pre-reservation-eligibility-v1",
    )


def _request_parts(*parts: str) -> tuple[str, str, str]:
    return (
        digest("request-id", *parts),
        digest("request-binding", *parts),
        digest("eligibility-attestation", *parts),
    )


def audit_concurrency(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    workload = plan["audit_workload"]
    passed = 0
    created_total = 0
    idempotent_total = 0
    expected_unique_per_trial = (
        workload["streams_per_trial"]
        * workload["unique_requests_per_stream"]
    )
    expected_calls_per_trial = (
        expected_unique_per_trial * workload["calls_per_request"]
    )
    for trial in range(workload["concurrency_trials"]):
        path = root / f"concurrency-{trial:03d}.sqlite3"
        journal = AllocationJournal(path)
        configs = {
            f"stream-audit-{trial:03d}-{stream:02d}": _synthetic_config(
                stream_id=f"stream-audit-{trial:03d}-{stream:02d}"
            )
            for stream in range(workload["streams_per_trial"])
        }
        for config in configs.values():
            journal.initialize_stream(config)
        calls = []
        for stream_id in configs:
            for request_index in range(
                workload["unique_requests_per_stream"]
            ):
                request_id, binding, attestation = _request_parts(
                    str(trial), stream_id, str(request_index)
                )
                for duplicate_index in range(workload["calls_per_request"]):
                    calls.append(
                        {
                            "order": digest(
                                "call-order",
                                str(trial),
                                stream_id,
                                str(request_index),
                                str(duplicate_index),
                            ),
                            "stream_id": stream_id,
                            "request_id": request_id,
                            "request_binding_sha256": binding,
                            "eligibility_attestation_sha256": attestation,
                        }
                    )
        calls.sort(key=lambda value: value["order"])

        def reserve(call: dict[str, str]) -> dict[str, Any]:
            return journal.reserve(
                stream_id=call["stream_id"],
                request_id=call["request_id"],
                request_binding_sha256=call["request_binding_sha256"],
                eligibility_attestation_sha256=(
                    call["eligibility_attestation_sha256"]
                ),
            )

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=workload["maximum_workers"]
        ) as executor:
            results = list(executor.map(reserve, calls))
        created = sum(result["created"] for result in results)
        idempotent = sum(result["idempotent_retry"] for result in results)
        verification = verify_journal(path, expected_configs=configs)
        stream_counts_pass = all(
            stream["reservation_count"]
            == workload["unique_requests_per_stream"]
            and stream["contiguous"]
            and stream["unique_request_count"]
            == workload["unique_requests_per_stream"]
            for stream in verification["streams"]
        )
        trial_passed = (
            verification["valid"]
            and created == expected_unique_per_trial
            and idempotent
            == expected_calls_per_trial - expected_unique_per_trial
            and stream_counts_pass
        )
        passed += trial_passed
        created_total += created
        idempotent_total += idempotent
    trial_count = workload["concurrency_trials"]
    return {
        "trial_count": trial_count,
        "trials_passed": passed,
        "all_trials_passed": passed == trial_count,
        "streams_per_trial": workload["streams_per_trial"],
        "unique_requests_per_stream": workload[
            "unique_requests_per_stream"
        ],
        "calls_per_request": workload["calls_per_request"],
        "maximum_workers": workload["maximum_workers"],
        "total_calls": trial_count * expected_calls_per_trial,
        "created_reservations": created_total,
        "idempotent_retries": idempotent_total,
        "conflicting_retries_accepted": 0,
        "identity_values_included": False,
        "response_or_outcome_values_included": False,
    }


def audit_restart(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    workload = plan["audit_workload"]
    path = root / "restart.sqlite3"
    journal = AllocationJournal(path)
    config = _synthetic_config(stream_id="stream-restart-audit-0001")
    journal.initialize_stream(config)
    fault_results = []
    committed_before_reply_total = 0
    retry_created_total = 0
    retry_idempotent_total = 0
    for fault_point in workload["logical_fault_points"]:
        committed_before_reply = 0
        retry_created = 0
        retry_idempotent = 0
        for request_index in range(workload["restart_requests_per_fault"]):
            request_id, binding, attestation = _request_parts(
                "restart", fault_point, str(request_index)
            )
            try:
                journal.reserve(
                    stream_id=config.stream_id,
                    request_id=request_id,
                    request_binding_sha256=binding,
                    eligibility_attestation_sha256=attestation,
                    fault_point=fault_point,
                )
                raise AssertionError("fault injection did not raise")
            except CommittedReplyLost:
                committed_before_reply += 1
            except LogicalFault:
                pass
            retry_journal = AllocationJournal(path)
            result = retry_journal.reserve(
                stream_id=config.stream_id,
                request_id=request_id,
                request_binding_sha256=binding,
                eligibility_attestation_sha256=attestation,
            )
            retry_created += result["created"]
            retry_idempotent += result["idempotent_retry"]
        expected_committed = (
            workload["restart_requests_per_fault"]
            if fault_point == "after_commit_before_reply"
            else 0
        )
        fault_results.append(
            {
                "fault_point": fault_point,
                "request_count": workload["restart_requests_per_fault"],
                "committed_before_reply_count": committed_before_reply,
                "retry_created_count": retry_created,
                "retry_idempotent_count": retry_idempotent,
                "expected_semantics_passed": (
                    committed_before_reply == expected_committed
                    and retry_idempotent == expected_committed
                    and retry_created
                    == workload["restart_requests_per_fault"]
                    - expected_committed
                ),
            }
        )
        committed_before_reply_total += committed_before_reply
        retry_created_total += retry_created
        retry_idempotent_total += retry_idempotent
    verification = verify_journal(
        path, expected_configs={config.stream_id: config}
    )
    expected_total = (
        len(workload["logical_fault_points"])
        * workload["restart_requests_per_fault"]
    )
    return {
        "fault_results": fault_results,
        "fault_points_passed": sum(
            value["expected_semantics_passed"] for value in fault_results
        ),
        "all_fault_points_passed": (
            all(value["expected_semantics_passed"] for value in fault_results)
            and verification["valid"]
            and verification["reservation_count"] == expected_total
        ),
        "expected_exact_once_reservations": expected_total,
        "verified_reservations": verification["reservation_count"],
        "committed_before_reply_count": committed_before_reply_total,
        "retry_created_count": retry_created_total,
        "retry_idempotent_count": retry_idempotent_total,
        "contiguous_after_restart": all(
            value["contiguous"] for value in verification["streams"]
        ),
        "logical_connection_close_only": True,
        "process_kill_simulated": False,
        "power_loss_simulated": False,
    }


def _raw_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def audit_immutability_and_conflicts(
    plan: dict[str, Any], root: Path
) -> dict[str, Any]:
    path = root / "immutability.sqlite3"
    journal = AllocationJournal(path)
    config = _synthetic_config(stream_id="stream-immutable-audit-0001")
    journal.initialize_stream(config)
    request_id, binding, attestation = _request_parts("immutable", "0")
    journal.reserve(
        stream_id=config.stream_id,
        request_id=request_id,
        request_binding_sha256=binding,
        eligibility_attestation_sha256=attestation,
    )
    blocked_probes = []
    statements = {
        "reservation_update": (
            "UPDATE reservations SET allocation_index = 2 "
            "WHERE stream_id = ? AND allocation_index = 0"
        ),
        "reservation_delete": (
            "DELETE FROM reservations WHERE stream_id = ? "
            "AND allocation_index = 0"
        ),
        "stream_update": (
            "UPDATE streams SET manifest_id = 'manifest-mutated' "
            "WHERE stream_id = ?"
        ),
        "stream_delete": "DELETE FROM streams WHERE stream_id = ?",
    }
    for probe in plan["audit_workload"]["immutability_probes"]:
        connection = _raw_connection(path)
        blocked = False
        try:
            connection.execute(statements[probe], (config.stream_id,))
        except sqlite3.IntegrityError:
            blocked = True
        finally:
            connection.close()
        blocked_probes.append({"probe": probe, "blocked": blocked})

    conflict_rejected = False
    try:
        journal.reserve(
            stream_id=config.stream_id,
            request_id=request_id,
            request_binding_sha256=digest("changed-binding"),
            eligibility_attestation_sha256=attestation,
        )
    except ValueError as error:
        conflict_rejected = str(error) == (
            "conflicting idempotent reservation retry"
        )
    config_conflict_rejected = False
    conflicting_config = StreamConfig(
        **{
            **config._asdict(),
            "manifest_sha256": digest("changed-manifest"),
        }
    )
    try:
        journal.initialize_stream(conflicting_config)
    except ValueError as error:
        config_conflict_rejected = str(error) == "stream configuration conflict"
    verification = verify_journal(
        path, expected_configs={config.stream_id: config}
    )
    return {
        "probe_results": blocked_probes,
        "all_update_and_delete_probes_blocked": all(
            value["blocked"] for value in blocked_probes
        ),
        "conflicting_retry_rejected": conflict_rejected,
        "conflicting_stream_configuration_rejected": config_conflict_rejected,
        "journal_valid_after_probes": verification["valid"],
        "reservation_count_after_probes": verification["reservation_count"],
    }


def _backup_database(source_path: Path, target_path: Path) -> None:
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def audit_tamper_detection(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    base = root / "tamper-base.sqlite3"
    journal = AllocationJournal(base)
    config = _synthetic_config(stream_id="stream-tamper-audit-0001")
    journal.initialize_stream(config)
    for index in range(5):
        request_id, binding, attestation = _request_parts("tamper", str(index))
        journal.reserve(
            stream_id=config.stream_id,
            request_id=request_id,
            request_binding_sha256=binding,
            eligibility_attestation_sha256=attestation,
        )
    journal.checkpoint()
    results = []
    statements = {
        "event_hash_change": (
            "UPDATE reservations SET event_sha256 = '" + "f" * 64 + "' "
            "WHERE stream_id = ? AND allocation_index = 2"
        ),
        "request_binding_change": (
            "UPDATE reservations SET request_binding_sha256 = '"
            + "e" * 64
            + "' WHERE stream_id = ? AND allocation_index = 2"
        ),
        "middle_row_delete": (
            "DELETE FROM reservations WHERE stream_id = ? "
            "AND allocation_index = 2"
        ),
    }
    for probe in plan["audit_workload"]["tamper_detection_probes"]:
        target = root / f"tamper-{probe}.sqlite3"
        _backup_database(base, target)
        connection = _raw_connection(target)
        try:
            connection.executescript(
                "DROP TRIGGER reservations_no_update; "
                "DROP TRIGGER reservations_no_delete;"
            )
            connection.execute(statements[probe], (config.stream_id,))
        finally:
            connection.close()
        verification = verify_journal(
            target, expected_configs={config.stream_id: config}
        )
        results.append(
            {
                "probe": probe,
                "detected": not verification["valid"],
                "error_classes": verification["errors"],
            }
        )
    return {
        "probe_results": results,
        "all_tamper_probes_detected": all(
            value["detected"] for value in results
        ),
        "base_journal_valid": verify_journal(
            base, expected_configs={config.stream_id: config}
        )["valid"],
    }


def audit_v3_integration(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    workload = plan["audit_workload"]
    resource_plan = load_json(_bound(plan, "resource_frontier_plan"))
    manifest = RESOURCE.make_symbolic_manifest(resource_plan)
    manifest_errors = ALLOCATOR.validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("; ".join(manifest_errors))
    manifest_sha256 = canonical_sha256(manifest)
    seed = resource_plan["symbolic_fixture"]["allocation_seed"]
    limits = workload["v3_trial_limits"]
    path = root / "v3-integration.sqlite3"
    journal = AllocationJournal(path)
    config = _synthetic_config(
        stream_id="stream-v3-integration-0001",
        manifest_id=manifest["manifest_id"],
        manifest_sha256=manifest_sha256,
        subtle_trial_limit=limits["subtle"],
        mushra_trial_limit=limits["mushra"],
    )
    config = StreamConfig(
        **{
            **config._asdict(),
            "allocation_seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        }
    )
    journal.initialize_stream(config)
    prefix = workload["v3_integration_prefix"]
    returned_indices = []
    for index in range(prefix):
        request_id, binding, attestation = _request_parts(
            "v3-integration", str(index)
        )
        result = journal.reserve(
            stream_id=config.stream_id,
            request_id=request_id,
            request_binding_sha256=binding,
            eligibility_attestation_sha256=attestation,
        )
        returned_indices.append(result["allocation_index"])
    verification = verify_journal(
        path, expected_configs={config.stream_id: config}
    )
    audit = ALLOCATOR.audit_prefixes(
        manifest,
        prefix,
        [prefix],
        seed,
        subtle_trial_limit=limits["subtle"],
        mushra_trial_limit=limits["mushra"],
    )
    return {
        "prefix": prefix,
        "trial_limits": limits,
        "journal_indices_exact_range": returned_indices == list(range(prefix)),
        "journal_verification_passed": verification["valid"],
        "v3_all_prefixes_balance_gate_passed": audit[
            "all_prefixes_balance_gate_passed"
        ],
        "maximum_trial_exposure_range": audit[
            "maximum_trial_exposure_range_across_all_prefixes"
        ],
        "maximum_trial_block_position_range": audit[
            "maximum_trial_block_position_range_across_all_prefixes"
        ],
        "maximum_candidate_position_range": audit[
            "maximum_candidate_position_range_across_all_prefixes"
        ],
        "participant_keys_stored": False,
        "responses_included": False,
    }


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    preparation_gate = load_json(_bound(plan, "listening_preparation_gate"))
    if preparation_gate["human_collection_authorized"]:
        raise ValueError("bound preparation gate unexpectedly authorizes collection")
    if preparation_gate["response_storage_authorized"]:
        raise ValueError("bound preparation gate unexpectedly authorizes storage")
    allocator_audit = load_json(_bound(plan, "allocator_v3_audit_report"))
    if not allocator_audit["decision"][
        "v3_all_audited_contiguous_prefixes_passed"
    ]:
        raise ValueError("bound v3 audit does not pass")
    missingness = load_json(_bound(plan, "missingness_report"))
    if missingness["decision"]["post_assignment_missingness_policy_ready"]:
        raise ValueError("bound missingness policy unexpectedly ready")
    retained = load_json(_bound(plan, "retained_design_report"))
    if retained["decision"]["operational_design_selected"]:
        raise ValueError("bound retained design unexpectedly selected")

    with tempfile.TemporaryDirectory(
        prefix="lossytrace-allocation-journal-audit-"
    ) as temporary:
        temporary_root = Path(temporary)
        concurrency = audit_concurrency(plan, temporary_root)
        restart = audit_restart(plan, temporary_root)
        immutability = audit_immutability_and_conflicts(plan, temporary_root)
        tamper = audit_tamper_detection(plan, temporary_root)
        v3_integration = audit_v3_integration(plan, temporary_root)
    candidate_passed = all(
        (
            concurrency["all_trials_passed"],
            restart["all_fault_points_passed"],
            immutability["all_update_and_delete_probes_blocked"],
            immutability["conflicting_retry_rejected"],
            immutability["conflicting_stream_configuration_rejected"],
            immutability["journal_valid_after_probes"],
            tamper["all_tamper_probes_detected"],
            tamper["base_journal_valid"],
            v3_integration["journal_indices_exact_range"],
            v3_integration["journal_verification_passed"],
            v3_integration["v3_all_prefixes_balance_gate_passed"],
        )
    )
    return {
        "schema_version": 1,
        "report_id": plan["plan_id"],
        "state": "synthetic_allocation_journal_candidate_audit_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "audio_accessed": False,
        "participant_identities_accessed": False,
        "responses_generated": False,
        "responses_read": False,
        "outcomes_generated": False,
        "outcomes_read": False,
        "human_collection_performed": False,
        "public_verdict_enabled": False,
        "database_candidate": {
            "journal_mode": "WAL",
            "synchronous_mode": "FULL",
            "reservation_transaction": "BEGIN_IMMEDIATE",
            "single_database_file_only": True,
            "temporary_audit_databases_retained": False,
        },
        "concurrency_audit": concurrency,
        "restart_audit": restart,
        "immutability_and_conflict_audit": immutability,
        "tamper_detection_audit": tamper,
        "v3_integration_audit": v3_integration,
        "decision": {
            "candidate_passed_synthetic_single_database_audit": candidate_passed,
            "concurrent_unique_reservation_passed": concurrency[
                "all_trials_passed"
            ],
            "logical_restart_exact_once_passed": restart[
                "all_fault_points_passed"
            ],
            "append_only_mutation_guards_passed": immutability[
                "all_update_and_delete_probes_blocked"
            ],
            "tamper_evidence_verifier_passed": tamper[
                "all_tamper_probes_detected"
            ],
            "v3_contiguous_prefix_integration_passed": v3_integration[
                "v3_all_prefixes_balance_gate_passed"
            ],
            "real_eligibility_contract_frozen": False,
            "multi_process_or_multi_host_deployment_proven": False,
            "power_loss_durability_proven": False,
            "response_atomicity_proven": False,
            "privacy_ownership_and_backup_policy_frozen": False,
            "missingness_or_exclusion_policy_selected": False,
            "operational_policy_selected": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_responsible_human_decision": (
                "Decide whether the synthetic single-database candidate is "
                "credible enough to justify a separately frozen operational "
                "policy. Selection would still require real pre-reservation "
                "eligibility semantics, deployment and backup boundaries, "
                "response atomicity, monitoring, exclusions, missingness, "
                "recovery and explicit collection authority."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("report schema_version differs")
    if report.get("state") != (
        "synthetic_allocation_journal_candidate_audit_complete"
    ):
        errors.append("report state differs")
    for key in (
        "audio_accessed",
        "participant_identities_accessed",
        "responses_generated",
        "responses_read",
        "outcomes_generated",
        "outcomes_read",
        "human_collection_performed",
        "public_verdict_enabled",
    ):
        if report.get(key) is not False:
            errors.append(f"report {key} must be false")
    decision = report.get("decision", {})
    for key in (
        "real_eligibility_contract_frozen",
        "multi_process_or_multi_host_deployment_proven",
        "power_loss_durability_proven",
        "response_atomicity_proven",
        "privacy_ownership_and_backup_policy_frozen",
        "missingness_or_exclusion_policy_selected",
        "operational_policy_selected",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision {key} must be false")
    claims = report.get("claim_boundary")
    if not isinstance(claims, dict) or any(
        value is not False for value in claims.values()
    ):
        errors.append("report claim boundary must remain false")
    return errors


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    plan = load_json(args.plan)
    report = build_report(plan, args.plan)
    errors = validate_report(report)
    if errors:
        raise SystemExit("; ".join(errors))
    write_report(report, args.output)
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "candidate_passed": report["decision"][
                    "candidate_passed_synthetic_single_database_audit"
                ],
                "collection_authorized": report["decision"][
                    "human_collection_authorized"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
