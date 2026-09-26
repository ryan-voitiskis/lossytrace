#!/usr/bin/env python3
"""Score-free full-reference oracle envelope and deterministic replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import perceptual_degradation_alignment_v2 as alignment_v2  # noqa: E402


PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "full-reference-oracle-score-free-plan.json"
)
SCHEMA = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "full-reference-oracle-score-free.schema.json"
)
REPLAY = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-oracle-score-free-replay-20260813-001.json"
)
RECORD_KIND = "perceptual_degradation_full_reference_oracle_score_free_v1"
REPLAY_ID = "perceptual-degradation-oracle-score-free-replay-20260813-001"
METRIC_GATE_ID = "perceptual-degradation-v1-metric-execution-20260803-010"
ARTIFACT_COMPONENTS = (
    "masking_relative_error",
    "bandwidth_loss",
    "temporal_modulation_damage",
    "transient_smearing_or_pre_echo",
    "tonal_or_birdie_noise",
    "stereo_image_or_phase_change",
    "segment_worst_case_impairment",
)
ALIGNMENT_REASON_CODES = {
    "ambiguous_alignment_peak",
    "insufficient_active_audio",
    "low_alignment_correlation",
    "clock_drift_exceeds_limit",
    "nonlinear_drift",
    "gain_exceeds_limit",
    "excessive_trim",
    "invalid_numeric_input",
    "invalid_channel_shape",
    "unsupported_channel_map",
    "channel_topology_mismatch",
    "channel_map_mismatch",
    "channel_alignment_disagreement",
    "structural_edit_suspected",
    "low_structural_window_correlation",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _metric_families(execution_state: str) -> list[dict[str, Any]]:
    reason = (
        "alignment_unsupported"
        if execution_state == "not_run_alignment_unsupported"
        else "perceptual_metric_execution_not_authorized"
    )
    return [
        {
            "family_id": "visqol_audio_v3_3_3",
            "execution_state": execution_state,
            "raw_primary_output": "mos_lqo",
            "raw_primary_value": None,
            "supporting_outputs_present": False,
            "reason": reason,
        },
        {
            "family_id": "gstpeaq_proxy_v0_6_1",
            "execution_state": execution_state,
            "raw_primary_output": "proxy_odg",
            "raw_primary_value": None,
            "supporting_outputs_present": False,
            "reason": reason,
        },
    ]


def _outcomes() -> dict[str, Any]:
    return {
        "categorical_state": "indeterminate",
        "impairment_severity": None,
        "impairment_severity_interval": None,
        "audibility_probability": None,
        "audibility_probability_interval": None,
        "artifact_profile": {
            "state": "unavailable",
            "components": {key: None for key in ARTIFACT_COMPONENTS},
        },
    }


def assemble_score_free(alignment: dict[str, Any]) -> dict[str, Any]:
    """Wrap score-free alignment without inventing metric or human truth."""

    if alignment.get("record_kind") != "perceptual_degradation_alignment_v2":
        raise ValueError("alignment record kind differs")
    if alignment.get("public_verdict_enabled") is not False:
        raise ValueError("alignment record improperly enables a public verdict")
    alignment_status = alignment.get("status")
    if alignment_status not in {"supported", "unsupported"}:
        raise ValueError("alignment status differs")
    alignment_support = alignment.get("support", {})
    alignment_reasons = (
        alignment_support.get("reasons", [])
        if isinstance(alignment_support, dict)
        else []
    )
    if (
        not isinstance(alignment_reasons, list)
        or not all(isinstance(reason, str) for reason in alignment_reasons)
        or not set(alignment_reasons) <= ALIGNMENT_REASON_CODES
    ):
        raise ValueError("alignment reasons differ")
    if alignment_status == "supported" and alignment_reasons:
        raise ValueError("supported alignment contains abstention reasons")
    if alignment_status == "unsupported" and not alignment_reasons:
        raise ValueError("unsupported alignment lacks an abstention reason")

    result_state = (
        "unsupported_alignment"
        if alignment_status == "unsupported"
        else "execution_blocked"
    )
    metric_state = (
        "not_run_alignment_unsupported"
        if alignment_status == "unsupported"
        else "not_authorized"
    )
    abstention_reasons = (
        ["alignment_unsupported"]
        if alignment_status == "unsupported"
        else [
            "human_calibration_unavailable",
            "perceptual_metric_execution_not_authorized",
        ]
    )
    record = {
        "schema_version": 1,
        "record_kind": RECORD_KIND,
        "assessment_mode": "full_reference",
        "case_id": alignment["case_id"],
        "result_state": result_state,
        "public_verdict_enabled": False,
        "evidence_scope": {
            "fixture_class": "synthetic_structural",
            "retained_audio_accessed": False,
            "public_or_provider_audio_accessed": False,
            "perceptual_metric_executed": False,
            "human_score_accessed": False,
            "sealed_evidence_opened": False,
        },
        "alignment": alignment,
        "metric_families": _metric_families(metric_state),
        "human_calibration": {
            "state": "unavailable",
            "mapping_id": None,
            "human_evidence_id": None,
        },
        "outcomes": _outcomes(),
        "support": {
            "supported": False,
            "abstention_reasons": abstention_reasons,
            "alignment_reason_codes": sorted(alignment_reasons),
        },
        "uncertainty": {
            "state": "unquantified",
            "interval_level": None,
            "source_group_bootstrap_replicates": 0,
        },
        "bindings": {
            "alignment_limits_id": alignment_v2.LIMITS_ID,
            "metric_execution_gate_id": METRIC_GATE_ID,
            "oracle_mapping_id": None,
        },
    }
    errors = validate_score_free_record(record)
    if errors:
        raise ValueError("invalid score-free oracle record: " + "; ".join(errors))
    return record


def _validate_alignment_record(alignment: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_keys = {
        "schema_version",
        "record_kind",
        "case_id",
        "status",
        "public_verdict_enabled",
        "input",
        "alignment",
        "support",
    }
    if set(alignment) != expected_keys:
        errors.append("alignment field set differs")
    if alignment.get("schema_version") != 1:
        errors.append("alignment schema version differs")
    if alignment.get("record_kind") != "perceptual_degradation_alignment_v2":
        errors.append("alignment record kind differs")
    if alignment.get("public_verdict_enabled") is not False:
        errors.append("alignment public verdict differs")

    input_record = alignment.get("input", {})
    if not isinstance(input_record, dict) or set(input_record) != {
        "sample_rate_hz",
        "reference",
        "test",
    }:
        errors.append("alignment input field set differs")
        input_record = {}
    sample_rate = input_record.get("sample_rate_hz")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate < 1:
        errors.append("alignment sample rate differs")
    side_records: dict[str, dict[str, Any]] = {}
    for side_id in ("reference", "test"):
        side = input_record.get(side_id, {})
        if not isinstance(side, dict) or set(side) != {
            "channel_count",
            "channel_map",
            "frames",
        }:
            errors.append(f"alignment side field set differs: {side_id}")
            continue
        count = side.get("channel_count")
        channel_map = side.get("channel_map")
        frames = side.get("frames")
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or count not in {1, 2}
            or not isinstance(channel_map, list)
            or len(channel_map) != count
            or tuple(channel_map) not in alignment_v2.SUPPORTED_CHANNEL_MAPS
        ):
            errors.append(f"alignment side topology differs: {side_id}")
        if not isinstance(frames, int) or isinstance(frames, bool) or frames < 1:
            errors.append(f"alignment side frame count differs: {side_id}")
        side_records[side_id] = side

    summary = alignment.get("alignment", {})
    expected_summary_keys = {
        "integer_delay_samples",
        "fractional_delay_samples",
        "clock_drift_ppm",
        "aligned_frames",
        "active_seconds",
        "minimum_correlation",
        "minimum_ambiguity_margin",
        "edge_trim_seconds",
        "channel_lag_spread_samples",
        "structural_residual_samples",
        "minimum_structural_window_correlation",
        "channels",
    }
    if not isinstance(summary, dict) or set(summary) != expected_summary_keys:
        errors.append("alignment summary field set differs")
        summary = {}
    for key in ("integer_delay_samples", "aligned_frames"):
        value = summary.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"alignment integer field differs: {key}")
    if isinstance(summary.get("aligned_frames"), int) and summary["aligned_frames"] < 0:
        errors.append("alignment aligned frames differ")
    numeric_keys = expected_summary_keys - {
        "integer_delay_samples",
        "aligned_frames",
        "channels",
    }
    for key in sorted(numeric_keys):
        value = summary.get(key)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            errors.append(f"alignment numeric field differs: {key}")
    fractional = summary.get("fractional_delay_samples")
    if isinstance(fractional, (int, float)) and not -0.5 <= fractional <= 0.5:
        errors.append("alignment fractional delay differs")
    for key in ("minimum_correlation", "minimum_structural_window_correlation"):
        value = summary.get(key)
        if isinstance(value, (int, float)) and not -1.0 <= value <= 1.0:
            errors.append(f"alignment correlation bound differs: {key}")
    for key in (
        "active_seconds",
        "minimum_ambiguity_margin",
        "edge_trim_seconds",
        "channel_lag_spread_samples",
        "structural_residual_samples",
    ):
        value = summary.get(key)
        if isinstance(value, (int, float)) and value < 0.0:
            errors.append(f"alignment nonnegative field differs: {key}")
    channels = summary.get("channels", [])
    if not isinstance(channels, list) or len(channels) > 2:
        errors.append("alignment channel summaries differ")
        channels = []
    expected_channel_keys = {
        "channel",
        "integer_delay_samples",
        "fractional_delay_samples",
        "observed_gain_db",
        "polarity",
        "correlation",
    }
    for index, channel in enumerate(channels):
        if not isinstance(channel, dict) or set(channel) != expected_channel_keys:
            errors.append(f"alignment channel field set differs: {index}")
            continue
        if channel.get("channel") not in {"M", "L", "R"}:
            errors.append(f"alignment channel identity differs: {index}")
        if channel.get("polarity") not in {"preserved", "inverted"}:
            errors.append(f"alignment channel polarity differs: {index}")
        if not isinstance(channel.get("integer_delay_samples"), int) or isinstance(
            channel.get("integer_delay_samples"), bool
        ):
            errors.append(f"alignment channel integer delay differs: {index}")
        for key in ("fractional_delay_samples", "observed_gain_db", "correlation"):
            value = channel.get(key)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
            ):
                errors.append(f"alignment channel numeric field differs: {index}:{key}")
        fractional = channel.get("fractional_delay_samples")
        if isinstance(fractional, (int, float)) and not -0.5 <= fractional <= 0.5:
            errors.append(f"alignment channel fractional delay differs: {index}")
        correlation = channel.get("correlation")
        if isinstance(correlation, (int, float)) and not -1.0 <= correlation <= 1.0:
            errors.append(f"alignment channel correlation differs: {index}")

    support = alignment.get("support", {})
    if not isinstance(support, dict) or set(support) != {"reasons", "limits_id"}:
        errors.append("alignment support field set differs")
        support = {}
    reasons = support.get("reasons", [])
    valid_reason_list = (
        isinstance(reasons, list)
        and all(isinstance(reason, str) for reason in reasons)
        and reasons == sorted(set(reasons))
        and set(reasons) <= ALIGNMENT_REASON_CODES
    )
    if not valid_reason_list:
        errors.append("alignment reasons differ")
        reasons = []
    if support.get("limits_id") != alignment_v2.LIMITS_ID:
        errors.append("alignment limits binding differs")
    status = alignment.get("status")
    if status == "supported":
        if reasons:
            errors.append("supported alignment contains abstention reasons")
        reference = side_records.get("reference", {})
        test = side_records.get("test", {})
        if reference.get("channel_map") != test.get("channel_map"):
            errors.append("supported alignment topology differs")
        if [channel.get("channel") for channel in channels] != reference.get(
            "channel_map"
        ):
            errors.append("supported alignment channel summaries differ")
    elif status == "unsupported":
        if not reasons:
            errors.append("unsupported alignment lacks an abstention reason")
    else:
        errors.append("alignment status differs")
    return errors


def validate_score_free_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_keys = {
        "schema_version",
        "record_kind",
        "assessment_mode",
        "case_id",
        "result_state",
        "public_verdict_enabled",
        "evidence_scope",
        "alignment",
        "metric_families",
        "human_calibration",
        "outcomes",
        "support",
        "uncertainty",
        "bindings",
    }
    if set(record) != expected_keys:
        errors.append("record field set differs")
    if record.get("schema_version") != 1 or record.get("record_kind") != RECORD_KIND:
        errors.append("record identity differs")
    if record.get("assessment_mode") != "full_reference":
        errors.append("assessment mode differs")
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or len(case_id) != 69 or not case_id.startswith("case-"):
        errors.append("case identity differs")
    elif any(character not in "0123456789abcdef" for character in case_id[5:]):
        errors.append("case identity differs")
    if record.get("public_verdict_enabled") is not False:
        errors.append("public verdict must remain disabled")

    scope = record.get("evidence_scope", {})
    if not isinstance(scope, dict):
        errors.append("evidence scope differs")
        scope = {}
    if scope.get("fixture_class") != "synthetic_structural":
        errors.append("fixture class differs")
    for key in (
        "retained_audio_accessed",
        "public_or_provider_audio_accessed",
        "perceptual_metric_executed",
        "human_score_accessed",
        "sealed_evidence_opened",
    ):
        if scope.get(key) is not False:
            errors.append(f"evidence scope must remain false: {key}")

    alignment = record.get("alignment", {})
    if not isinstance(alignment, dict):
        errors.append("alignment record differs")
        alignment = {}
    errors.extend(_validate_alignment_record(alignment))
    alignment_status = alignment.get("status")
    alignment_support = alignment.get("support", {})
    if not isinstance(alignment_support, dict):
        alignment_support = {}
    raw_reasons = alignment_support.get("reasons", [])
    reasons = raw_reasons if isinstance(raw_reasons, list) else []
    if alignment.get("case_id") != case_id:
        errors.append("alignment case identity differs")
    if alignment.get("record_kind") != "perceptual_degradation_alignment_v2":
        errors.append("alignment record kind differs")
    if alignment.get("public_verdict_enabled") is not False:
        errors.append("alignment public verdict differs")
    if (
        not isinstance(raw_reasons, list)
        or not all(isinstance(reason, str) for reason in reasons)
        or not set(reasons) <= ALIGNMENT_REASON_CODES
    ):
        errors.append("alignment reasons differ")
        reasons = []
    elif alignment_status == "supported" and reasons:
        errors.append("supported alignment contains abstention reasons")
    elif alignment_status == "unsupported" and not reasons:
        errors.append("unsupported alignment lacks an abstention reason")

    expected_state = {
        "supported": "execution_blocked",
        "unsupported": "unsupported_alignment",
    }.get(alignment_status)
    if expected_state is None or record.get("result_state") != expected_state:
        errors.append("result state does not match alignment support")
    support = record.get("support", {})
    if not isinstance(support, dict):
        errors.append("oracle support differs")
        support = {}
    if support.get("supported") is not False:
        errors.append("score-free record cannot claim support")
    if support.get("alignment_reason_codes") != sorted(reasons):
        errors.append("alignment reason projection differs")
    expected_abstention = (
        ["alignment_unsupported"]
        if alignment_status == "unsupported"
        else [
            "human_calibration_unavailable",
            "perceptual_metric_execution_not_authorized",
        ]
    )
    if support.get("abstention_reasons") != expected_abstention:
        errors.append("abstention reasons differ")

    expected_metric_state = (
        "not_run_alignment_unsupported"
        if alignment_status == "unsupported"
        else "not_authorized"
    )
    if record.get("metric_families") != _metric_families(expected_metric_state):
        errors.append("metric-family boundary differs")
    if record.get("human_calibration") != {
        "state": "unavailable",
        "mapping_id": None,
        "human_evidence_id": None,
    }:
        errors.append("human calibration boundary differs")
    if record.get("outcomes") != _outcomes():
        errors.append("score-free outcomes must remain unavailable")
    if record.get("uncertainty") != {
        "state": "unquantified",
        "interval_level": None,
        "source_group_bootstrap_replicates": 0,
    }:
        errors.append("score-free uncertainty differs")
    if record.get("bindings") != {
        "alignment_limits_id": alignment_v2.LIMITS_ID,
        "metric_execution_gate_id": METRIC_GATE_ID,
        "oracle_mapping_id": None,
    }:
        errors.append("oracle bindings differ")
    serialized = json.dumps(record, sort_keys=True)
    if any(value in serialized for value in ("/Users/", "Application Support", "file://")):
        errors.append("score-free record contains a private path")
    return errors


def _synthetic_alignment(*, supported: bool) -> dict[str, Any]:
    recipe = (
        "oracle-score-free-supported-stereo"
        if supported
        else "oracle-score-free-unsupported-topology"
    )
    channel_summary = {
        "channel": "L",
        "integer_delay_samples": 0,
        "fractional_delay_samples": 0.0,
        "observed_gain_db": 0.0,
        "polarity": "preserved",
        "correlation": 1.0,
    }
    alignment = {
        "integer_delay_samples": 0,
        "fractional_delay_samples": 0.0,
        "clock_drift_ppm": 0.0,
        "aligned_frames": 12_000 if supported else 0,
        "active_seconds": 6.0 if supported else 0.0,
        "minimum_correlation": 1.0 if supported else 0.0,
        "minimum_ambiguity_margin": 0.02 if supported else 0.0,
        "edge_trim_seconds": 0.0,
        "channel_lag_spread_samples": 0.0,
        "structural_residual_samples": 0.0,
        "minimum_structural_window_correlation": 1.0 if supported else 0.0,
        "channels": (
            [channel_summary, {**channel_summary, "channel": "R"}]
            if supported
            else []
        ),
    }
    return {
        "schema_version": 1,
        "record_kind": "perceptual_degradation_alignment_v2",
        "case_id": alignment_v2.mono.case_id(recipe),
        "status": "supported" if supported else "unsupported",
        "public_verdict_enabled": False,
        "input": {
            "sample_rate_hz": 2_000,
            "reference": {
                "channel_count": 2,
                "channel_map": ["L", "R"],
                "frames": 12_000,
            },
            "test": {
                "channel_count": 2 if supported else 1,
                "channel_map": ["L", "R"] if supported else ["M"],
                "frames": 12_000,
            },
        },
        "alignment": alignment,
        "support": {
            "reasons": (
                []
                if supported
                else ["channel_map_mismatch", "channel_topology_mismatch"]
            ),
            "limits_id": alignment_v2.LIMITS_ID,
        },
    }


def synthetic_records() -> list[dict[str, Any]]:
    return [
        assemble_score_free(_synthetic_alignment(supported=True)),
        assemble_score_free(_synthetic_alignment(supported=False)),
    ]


def build_replay() -> dict[str, Any]:
    records = synthetic_records()
    replay = {
        "schema_version": 1,
        "replay_id": REPLAY_ID,
        "state": "score_free_oracle_envelope_replayed_metrics_and_human_truth_closed",
        "records": records,
        "record_inventory_sha256": sha256_bytes(canonical_bytes(records)),
        "summary": {
            "record_count": 2,
            "execution_blocked_count": 1,
            "unsupported_alignment_count": 1,
            "estimated_count": 0,
        },
        "access_boundary": {
            "synthetic_numeric_fixtures_only": True,
            "retained_audio_accessed": False,
            "public_or_provider_audio_accessed": False,
            "perceptual_metric_executed": False,
            "human_score_accessed": False,
            "sealed_evidence_opened": False,
            "public_verdict_enabled": False,
        },
        "paths_redacted": True,
    }
    errors = validate_replay(replay)
    if errors:
        raise ValueError("invalid score-free replay: " + "; ".join(errors))
    return replay


def validate_replay(replay: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if replay.get("schema_version") != 1 or replay.get("replay_id") != REPLAY_ID:
        errors.append("replay identity differs")
    if replay.get("state") != (
        "score_free_oracle_envelope_replayed_metrics_and_human_truth_closed"
    ):
        errors.append("replay state differs")
    records = replay.get("records", [])
    if not isinstance(records, list) or len(records) != 2:
        errors.append("replay record count differs")
        records = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"invalid replay record: {index}")
        else:
            errors.extend(
                f"record {index}: {error}" for error in validate_score_free_record(record)
            )
    if records and replay.get("record_inventory_sha256") != sha256_bytes(
        canonical_bytes(records)
    ):
        errors.append("replay record inventory differs")
    states = [record.get("result_state") for record in records if isinstance(record, dict)]
    if replay.get("summary") != {
        "record_count": 2,
        "execution_blocked_count": states.count("execution_blocked"),
        "unsupported_alignment_count": states.count("unsupported_alignment"),
        "estimated_count": 0,
    }:
        errors.append("replay summary differs")
    boundary = replay.get("access_boundary", {})
    if boundary.get("synthetic_numeric_fixtures_only") is not True:
        errors.append("synthetic-only boundary differs")
    for key in (
        "retained_audio_accessed",
        "public_or_provider_audio_accessed",
        "perceptual_metric_executed",
        "human_score_accessed",
        "sealed_evidence_opened",
        "public_verdict_enabled",
    ):
        if boundary.get(key) is not False:
            errors.append(f"replay access boundary must remain false: {key}")
    if replay.get("paths_redacted") is not True:
        errors.append("replay paths must remain redacted")
    return errors


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("plan schema version differs")
    if plan.get("plan_id") != "full-reference-oracle-score-free-plan-20260813-001":
        errors.append("plan identity differs")
    if plan.get("state") != "score_free_schema_replay_complete_metric_and_human_gates_closed":
        errors.append("plan state differs")
    expected_bindings = {
        "research_plan",
        "metric_execution_gate",
        "alignment_topology_freeze",
        "oracle_schema",
        "oracle_implementation",
        "oracle_tests",
        "score_free_replay",
        "score_free_report",
    }
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("plan binding set differs")
    else:
        for binding_id, binding in bindings.items():
            relative = Path(str(binding.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"invalid repository-relative binding: {binding_id}")
                continue
            path = ROOT / relative
            if not path.is_file():
                errors.append(f"missing bound file: {binding_id}")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"bound file hash differs: {binding_id}")
    if plan.get("completed_prerequisite") != {
        "research_plan_required_record": "score_free_schema_replay",
        "score_free_schema_replay_complete": True,
        "synthetic_replay_byte_identical": True,
        "supported_alignment_distinguished_from_execution_block": True,
        "alignment_failure_distinguished_from_metric_execution": True,
    }:
        errors.append("completed prerequisite differs")
    boundary = plan.get("access_boundary", {})
    if boundary.get("synthetic_numeric_fixture_execution_authorized") is not True:
        errors.append("synthetic fixture authority differs")
    for key in (
        "retained_audio_access_authorized",
        "public_or_provider_audio_access_authorized",
        "perceptual_metric_execution_authorized",
        "human_score_access_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
        "sealed_evidence_access_authorized",
        "public_verdict_authorized",
    ):
        if boundary.get(key) is not False:
            errors.append(f"plan access boundary must remain false: {key}")
    if plan.get("authorized_next_step") != (
        "Preserve this score-free envelope. Complete only separately authorized "
        "clean-reference delivery and listening preparation; do not execute either "
        "perceptual metric, inspect human scores, train a no-reference estimator, or "
        "enable a public verdict."
    ):
        errors.append("authorized next step differs")
    serialized = json.dumps(plan, sort_keys=True)
    if any(value in serialized for value in ("/Users/", "Application Support", "file://")):
        errors.append("plan contains a private path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    replay_parser = subcommands.add_parser("replay")
    replay_parser.add_argument("--output", type=Path)
    validate_replay_parser = subcommands.add_parser("validate-replay")
    validate_replay_parser.add_argument("--input", type=Path, default=REPLAY)
    validate_plan_parser = subcommands.add_parser("validate-plan")
    validate_plan_parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args()

    if args.command == "replay":
        value = build_replay()
        if args.output:
            if args.output.exists():
                raise ValueError("refusing to replace score-free replay output")
            args.output.write_bytes(canonical_bytes(value))
        else:
            sys.stdout.buffer.write(canonical_bytes(value))
        return 0
    if args.command == "validate-replay":
        errors = validate_replay(load_json(args.input))
        status = "score_free_oracle_replay_valid"
    else:
        errors = validate_plan(load_json(args.plan))
        status = "score_free_oracle_plan_valid_metrics_and_human_truth_closed"
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({"status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
