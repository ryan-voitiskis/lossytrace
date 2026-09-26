#!/usr/bin/env python3
"""Deterministic synthetic-only listening-response analysis preparation.

The library functions validate and analyse an already de-identified response
envelope.  The command-line surface deliberately generates synthetic fixtures
only; it cannot open a response file or authorize human collection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Callable


PLAN_ID = "perceptual-degradation-listening-analysis-20260813-001"
FIXTURE_ID = "perceptual-degradation-listening-analysis-synthetic-20260813-001"
Z_THRESHOLD = 2.2414027276
AUDIBILITY_CHANCE = 0.5
AUDIBILITY_POINT_GATE = 0.75
EQUIVALENCE_INTERVAL = (0.45, 0.55)
SDG_MATERIAL_THRESHOLD = -1.0
MUSHRA_LOSS_MATERIAL_THRESHOLD = 10.0
VARIANCE_COMPONENTS = {
    "audibility": {"listener_sd": 0.45, "source_sd": 0.35},
    "sdg": {"listener_sd": 0.25, "source_sd": 0.30, "residual_sd": 0.50},
    "mushra_loss": {
        "listener_sd": 4.0,
        "source_sd": 5.0,
        "residual_sd": 8.0,
    },
}
MIN_LISTENERS = 24
MIN_SOURCES = 12
MIN_RESPONSES = 96
MAX_ITERATIONS = 100
CONVERGENCE_TOLERANCE = 1e-10
OPAQUE_ID = re.compile(r"^[a-z][a-z0-9-]{7,63}$")
PARTICIPANT_ID = re.compile(r"^participant-[0-9a-f]{24}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/perceptual-degradation-v1/listening-analysis-plan.json"
)


def _sha(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _logistic(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-value)
        return 1.0 / (1.0 + inverse)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def _round(value: float | None, digits: int = 10) -> float | None:
    return None if value is None else round(value, digits)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("analysis plan identity differs")
    if plan.get("state") != "score_blind_analysis_frozen_synthetic_execution_only":
        errors.append("analysis plan state differs")
    authorization = plan.get("authorization", {})
    if authorization != {
        "human_collection_authorized": False,
        "observed_response_analysis_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "synthetic_fixture_execution_only": True,
    }:
        errors.append("analysis authorization boundary differs")
    models = plan.get("hierarchical_models", {})
    expected_components = {
        "audibility": (0.45, 0.35, None),
        "sdg": (0.25, 0.30, 0.50),
        "mushra_loss": (4.0, 5.0, 8.0),
    }
    for family, expected in expected_components.items():
        model = models.get(family, {})
        observed = (
            model.get("listener_sd"),
            model.get("source_sd"),
            model.get("residual_sd"),
        )
        if observed != expected:
            errors.append(f"{family} variance components differ")
    if models.get("maximum_iterations") != MAX_ITERATIONS:
        errors.append("maximum iterations differ")
    if models.get("convergence_tolerance") != CONVERGENCE_TOLERANCE:
        errors.append("convergence tolerance differs")
    decisions = plan.get("decision_rules", {})
    expected_decisions = {
        "multiplicity_adjusted_one_sided_z": Z_THRESHOLD,
        "minimum_listeners": MIN_LISTENERS,
        "minimum_source_groups": MIN_SOURCES,
        "minimum_responses": MIN_RESPONSES,
    }
    for key, expected in expected_decisions.items():
        if decisions.get(key) != expected:
            errors.append(f"decision rule differs: {key}")
    anchors = plan.get("bridge_mapping", {}).get("preserved_reference_points")
    if anchors != [
        {"sdg": 0, "mushra_loss": 0, "severity": 0},
        {"sdg": -1, "mushra_loss": 10, "severity": 25},
        {"mushra_loss": 100, "severity": 100},
    ]:
        errors.append("bridge reference points differ")
    report = plan.get("report_boundary", {})
    if any(
        report.get(key) is not expected
        for key, expected in {
            "path_free_aggregate_only": True,
            "synthetic_scientific_gate_evaluated": False,
            "synthetic_oracle_truth_eligible": False,
            "synthetic_collection_eligible": False,
            "public_verdict_enabled": False,
        }.items()
    ):
        errors.append("report boundary differs")
    return errors


def _matvec(
    rows: list[tuple[int, int, float]],
    weights: list[float],
    listener_count: int,
    source_count: int,
    listener_precision: float,
    source_precision: float,
) -> Callable[[list[float]], list[float]]:
    size = 1 + listener_count + source_count

    def apply(vector: list[float]) -> list[float]:
        result = [0.0] * size
        for (listener, source, _), weight in zip(rows, weights, strict=True):
            listener_index = 1 + listener
            source_index = 1 + listener_count + source
            projected = (
                vector[0] + vector[listener_index] + vector[source_index]
            )
            contribution = weight * projected
            result[0] += contribution
            result[listener_index] += contribution
            result[source_index] += contribution
        for index in range(listener_count):
            position = 1 + index
            result[position] += listener_precision * vector[position]
        for index in range(source_count):
            position = 1 + listener_count + index
            result[position] += source_precision * vector[position]
        return result

    return apply


def _conjugate_gradient(
    apply: Callable[[list[float]], list[float]],
    rhs: list[float],
    *,
    tolerance: float = 1e-12,
    maximum_iterations: int | None = None,
) -> list[float]:
    size = len(rhs)
    limit = maximum_iterations or max(200, size * 8)
    solution = [0.0] * size
    residual = rhs.copy()
    direction = residual.copy()
    residual_norm = sum(value * value for value in residual)
    initial_norm = max(residual_norm, 1.0)
    if residual_norm == 0.0:
        return solution
    for _ in range(limit):
        product = apply(direction)
        denominator = sum(a * b for a, b in zip(direction, product, strict=True))
        if denominator <= 0.0:
            raise ValueError("hierarchical normal equations are not positive definite")
        alpha = residual_norm / denominator
        solution = [
            value + alpha * step
            for value, step in zip(solution, direction, strict=True)
        ]
        next_residual = [
            value - alpha * delta
            for value, delta in zip(residual, product, strict=True)
        ]
        next_norm = sum(value * value for value in next_residual)
        if next_norm <= tolerance * tolerance * initial_norm:
            return solution
        beta = next_norm / residual_norm
        direction = [
            value + beta * previous
            for value, previous in zip(next_residual, direction, strict=True)
        ]
        residual = next_residual
        residual_norm = next_norm
    raise ValueError("hierarchical normal equations did not converge")


def _encode_rows(
    observations: list[dict[str, Any]], outcome: Callable[[dict[str, Any]], float]
) -> tuple[list[tuple[int, int, float]], int, int]:
    listener_ids = sorted({item["participant_id"] for item in observations})
    source_ids = sorted({item["source_group_id"] for item in observations})
    listener_index = {value: index for index, value in enumerate(listener_ids)}
    source_index = {value: index for index, value in enumerate(source_ids)}
    rows = [
        (
            listener_index[item["participant_id"]],
            source_index[item["source_group_id"]],
            outcome(item),
        )
        for item in observations
    ]
    return rows, len(listener_ids), len(source_ids)


def _fit_logistic(
    observations: list[dict[str, Any]],
) -> dict[str, float | int | bool]:
    rows, listener_count, source_count = _encode_rows(
        observations, lambda item: float(item["forced_choice_correct"])
    )
    listener_precision = 1.0 / VARIANCE_COMPONENTS["audibility"]["listener_sd"] ** 2
    source_precision = 1.0 / VARIANCE_COMPONENTS["audibility"]["source_sd"] ** 2
    parameters = [0.0] * (1 + listener_count + source_count)
    mean = sum(item[2] for item in rows) / len(rows)
    bounded_mean = min(1.0 - 1e-6, max(1e-6, mean))
    parameters[0] = math.log(bounded_mean / (1.0 - bounded_mean))
    converged = False
    weights: list[float] = []
    iterations = 0
    for iterations in range(1, MAX_ITERATIONS + 1):
        probabilities = []
        weights = []
        for listener, source, _ in rows:
            eta = (
                parameters[0]
                + parameters[1 + listener]
                + parameters[1 + listener_count + source]
            )
            probability = min(1.0 - 1e-9, max(1e-9, _logistic(eta)))
            probabilities.append(probability)
            weights.append(probability * (1.0 - probability))
        rhs = [0.0] * len(parameters)
        for (listener, source, outcome), probability in zip(
            rows, probabilities, strict=True
        ):
            residual = outcome - probability
            rhs[0] += residual
            rhs[1 + listener] += residual
            rhs[1 + listener_count + source] += residual
        for index in range(listener_count):
            position = 1 + index
            rhs[position] -= listener_precision * parameters[position]
        for index in range(source_count):
            position = 1 + listener_count + index
            rhs[position] -= source_precision * parameters[position]
        apply = _matvec(
            rows,
            weights,
            listener_count,
            source_count,
            listener_precision,
            source_precision,
        )
        step = _conjugate_gradient(apply, rhs)
        parameters = [
            value + delta for value, delta in zip(parameters, step, strict=True)
        ]
        if max(abs(value) for value in step) <= CONVERGENCE_TOLERANCE:
            converged = True
            break
    if not converged:
        raise ValueError("hierarchical logistic model did not converge")
    apply = _matvec(
        rows,
        weights,
        listener_count,
        source_count,
        listener_precision,
        source_precision,
    )
    inverse_column = _conjugate_gradient(apply, [1.0] + [0.0] * (len(parameters) - 1))
    standard_error = math.sqrt(max(0.0, inverse_column[0]))
    estimate = _logistic(parameters[0])
    lower = _logistic(parameters[0] - Z_THRESHOLD * standard_error)
    upper = _logistic(parameters[0] + Z_THRESHOLD * standard_error)
    return {
        "estimate": estimate,
        "lower": lower,
        "upper": upper,
        "standard_error_link_scale": standard_error,
        "listeners": listener_count,
        "sources": source_count,
        "responses": len(rows),
        "iterations": iterations,
        "converged": converged,
    }


def _fit_gaussian(
    observations: list[dict[str, Any]],
    outcome: Callable[[dict[str, Any]], float],
    family: str,
) -> dict[str, float | int | bool]:
    rows, listener_count, source_count = _encode_rows(observations, outcome)
    components = VARIANCE_COMPONENTS[family]
    residual_variance = components["residual_sd"] ** 2
    listener_precision = 1.0 / components["listener_sd"] ** 2
    source_precision = 1.0 / components["source_sd"] ** 2
    weights = [1.0 / residual_variance] * len(rows)
    rhs = [0.0] * (1 + listener_count + source_count)
    for listener, source, value in rows:
        weighted = value / residual_variance
        rhs[0] += weighted
        rhs[1 + listener] += weighted
        rhs[1 + listener_count + source] += weighted
    apply = _matvec(
        rows,
        weights,
        listener_count,
        source_count,
        listener_precision,
        source_precision,
    )
    parameters = _conjugate_gradient(apply, rhs)
    inverse_column = _conjugate_gradient(apply, [1.0] + [0.0] * (len(parameters) - 1))
    standard_error = math.sqrt(max(0.0, inverse_column[0]))
    estimate = parameters[0]
    return {
        "estimate": estimate,
        "lower": estimate - Z_THRESHOLD * standard_error,
        "upper": estimate + Z_THRESHOLD * standard_error,
        "standard_error": standard_error,
        "listeners": listener_count,
        "sources": source_count,
        "responses": len(rows),
        "iterations": 1,
        "converged": True,
    }


def _enough(result: dict[str, Any]) -> bool:
    return (
        result["listeners"] >= MIN_LISTENERS
        and result["sources"] >= MIN_SOURCES
        and result["responses"] >= MIN_RESPONSES
    )


def _audibility_state(result: dict[str, Any]) -> str:
    if not _enough(result):
        return "audibility_indeterminate"
    if result["lower"] > AUDIBILITY_CHANCE and result["estimate"] >= AUDIBILITY_POINT_GATE:
        return "audible"
    if result["lower"] > EQUIVALENCE_INTERVAL[0] and result["upper"] < EQUIVALENCE_INTERVAL[1]:
        return "not_demonstrably_audible"
    return "audibility_indeterminate"


def _session_primary_eligible(session: dict[str, Any]) -> bool:
    checks = session["checks"]
    return all(
        checks[key]
        for key in (
            "consent_present",
            "eligibility_pass",
            "stimulus_binding_pass",
            "delivery_pass",
            "fixed_level_pass",
            "training_complete",
            "timing_pass",
            "response_completeness_pass",
            "hidden_reference_quality_pass",
            "anchor_quality_pass",
        )
    ) and not checks["duplicate_evidence"]


def _session_sensitivity_eligible(session: dict[str, Any]) -> bool:
    checks = session["checks"]
    return all(
        checks[key]
        for key in (
            "consent_present",
            "eligibility_pass",
            "stimulus_binding_pass",
            "delivery_pass",
            "fixed_level_pass",
            "training_complete",
            "timing_pass",
            "response_completeness_pass",
        )
    ) and not checks["duplicate_evidence"]


def validate_dataset(dataset: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_top = {
        "schema_version",
        "dataset_id",
        "state",
        "fixture_only",
        "human_collection_authorized",
        "human_responses_observed",
        "manifest_id",
        "manifest_sha256",
        "analysis_plan_id",
        "sessions",
        "responses",
    }
    if set(dataset) != required_top:
        errors.append("dataset fields differ from the frozen response envelope")
    if dataset.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if dataset.get("state") != "synthetic_fixture_only":
        errors.append("only synthetic_fixture_only state is accepted")
    if dataset.get("fixture_only") is not True:
        errors.append("fixture_only must be true")
    if dataset.get("human_collection_authorized") is not False:
        errors.append("human collection must remain unauthorized")
    if dataset.get("human_responses_observed") is not False:
        errors.append("observed human responses are forbidden")
    if dataset.get("analysis_plan_id") != PLAN_ID:
        errors.append("analysis plan ID differs")
    for key in ("dataset_id", "manifest_id"):
        if not OPAQUE_ID.fullmatch(str(dataset.get(key, ""))):
            errors.append(f"{key} is not opaque")
    if not SHA256.fullmatch(str(dataset.get("manifest_sha256", ""))):
        errors.append("manifest SHA-256 differs")

    sessions = dataset.get("sessions", [])
    session_by_id: dict[str, dict[str, Any]] = {}
    participant_sessions: set[tuple[str, str]] = set()
    check_keys = {
        "consent_present",
        "eligibility_pass",
        "stimulus_binding_pass",
        "delivery_pass",
        "fixed_level_pass",
        "training_complete",
        "timing_pass",
        "response_completeness_pass",
        "duplicate_evidence",
        "hidden_reference_quality_pass",
        "anchor_quality_pass",
    }
    for index, session in enumerate(sessions):
        required = {"session_id", "participant_id", "assignment_id", "partition", "checks"}
        if set(session) != required:
            errors.append(f"session {index}: fields differ")
            continue
        session_id = session.get("session_id")
        participant_id = session.get("participant_id")
        if not OPAQUE_ID.fullmatch(str(session_id or "")):
            errors.append(f"session {index}: session ID is not opaque")
        if not PARTICIPANT_ID.fullmatch(str(participant_id or "")):
            errors.append(f"session {index}: participant ID differs")
        if not OPAQUE_ID.fullmatch(str(session.get("assignment_id", ""))):
            errors.append(f"session {index}: assignment ID is not opaque")
        if session.get("partition") not in {"development", "calibration", "transfer"}:
            errors.append(f"session {index}: partition is unauthorized")
        checks = session.get("checks", {})
        if set(checks) != check_keys or any(type(value) is not bool for value in checks.values()):
            errors.append(f"session {index}: checks differ")
        if session_id in session_by_id:
            errors.append(f"session {index}: duplicate session ID")
        elif isinstance(session_id, str):
            session_by_id[session_id] = session
        pair = (str(participant_id), str(session_id))
        if pair in participant_sessions:
            errors.append(f"session {index}: duplicate participant/session")
        participant_sessions.add(pair)

    response_ids: set[str] = set()
    idempotency_keys: set[str] = set()
    source_partition_groups: dict[str, str] = {}
    condition_groups: dict[str, str] = {}
    forbidden_keys = {"filename", "path", "codec", "encoder", "metric_score", "identity", "ip_address", "location"}
    for index, response in enumerate(dataset.get("responses", [])):
        required = {
            "response_id",
            "idempotency_key",
            "session_id",
            "participant_id",
            "trial_id",
            "analysis_group_id",
            "condition_stimulus_id",
            "source_group_id",
            "partition_group_id",
            "partition",
            "method",
            "forced_choice_correct",
            "sdg",
            "condition_score",
            "hidden_reference_score",
        }
        if set(response) != required:
            errors.append(f"response {index}: fields differ")
            continue
        if forbidden_keys.intersection(response):
            errors.append(f"response {index}: outcome-revealing metadata is forbidden")
        response_id = response.get("response_id")
        key = response.get("idempotency_key")
        if not SHA256.fullmatch(str(response_id or "")):
            errors.append(f"response {index}: response ID differs")
        if not SHA256.fullmatch(str(key or "")):
            errors.append(f"response {index}: idempotency key differs")
        if response_id in response_ids:
            errors.append(f"response {index}: duplicate response ID")
        if key in idempotency_keys:
            errors.append(f"response {index}: duplicate idempotency key")
        response_ids.add(str(response_id))
        idempotency_keys.add(str(key))
        for field in (
            "trial_id",
            "analysis_group_id",
            "condition_stimulus_id",
            "source_group_id",
            "partition_group_id",
        ):
            if not OPAQUE_ID.fullmatch(str(response.get(field, ""))):
                errors.append(f"response {index}: {field} is not opaque")
        source_id = response.get("source_group_id")
        partition_group_id = response.get("partition_group_id")
        previous_partition_group = source_partition_groups.setdefault(
            str(source_id), str(partition_group_id)
        )
        if previous_partition_group != partition_group_id:
            errors.append(f"response {index}: source crosses partition groups")
        condition_id = response.get("condition_stimulus_id")
        analysis_group_id = response.get("analysis_group_id")
        previous_analysis_group = condition_groups.setdefault(
            str(condition_id), str(analysis_group_id)
        )
        if previous_analysis_group != analysis_group_id:
            errors.append(f"response {index}: condition crosses analysis groups")
        session = session_by_id.get(response.get("session_id"))
        if session is None:
            errors.append(f"response {index}: unknown session")
        elif (
            response.get("participant_id") != session["participant_id"]
            or response.get("partition") != session["partition"]
        ):
            errors.append(f"response {index}: session binding differs")
        method = response.get("method")
        if method == "subtle":
            if type(response.get("forced_choice_correct")) is not bool:
                errors.append(f"response {index}: subtle forced choice differs")
            sdg = response.get("sdg")
            if not isinstance(sdg, (int, float)) or isinstance(sdg, bool) or not -4.0 <= sdg <= 0.0:
                errors.append(f"response {index}: SDG differs")
            if response.get("condition_score") is not None or response.get("hidden_reference_score") is not None:
                errors.append(f"response {index}: subtle MUSHRA fields must be null")
        elif method == "mushra":
            if response.get("forced_choice_correct") is not None or response.get("sdg") is not None:
                errors.append(f"response {index}: MUSHRA subtle fields must be null")
            for field in ("condition_score", "hidden_reference_score"):
                value = response.get(field)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 100.0:
                    errors.append(f"response {index}: {field} differs")
        else:
            errors.append(f"response {index}: method differs")
    return errors


def _analyse_groups(dataset: dict[str, Any], sensitivity: bool) -> list[dict[str, Any]]:
    eligibility = _session_sensitivity_eligible if sensitivity else _session_primary_eligible
    sessions = {item["session_id"]: item for item in dataset["sessions"]}
    responses = [item for item in dataset["responses"] if eligibility(sessions[item["session_id"]])]
    groups: list[dict[str, Any]] = []
    for group_id in sorted({item["analysis_group_id"] for item in responses}):
        grouped = [item for item in responses if item["analysis_group_id"] == group_id]
        partitions = sorted({item["partition"] for item in grouped})
        if len(partitions) != 1:
            raise ValueError(f"analysis group crosses partitions: {group_id}")
        subtle = [item for item in grouped if item["method"] == "subtle"]
        mushra = [item for item in grouped if item["method"] == "mushra"]
        audibility = _fit_logistic(subtle) if subtle else None
        if audibility is not None:
            audibility["state"] = _audibility_state(audibility)
        sdg = _fit_gaussian(subtle, lambda item: float(item["sdg"]), "sdg") if subtle else None
        mushra_loss = (
            _fit_gaussian(
                mushra,
                lambda item: float(item["hidden_reference_score"] - item["condition_score"]),
                "mushra_loss",
            )
            if mushra
            else None
        )
        sdg_material = bool(sdg and _enough(sdg) and sdg["upper"] < SDG_MATERIAL_THRESHOLD)
        mushra_material = bool(
            mushra_loss and _enough(mushra_loss) and mushra_loss["lower"] > MUSHRA_LOSS_MATERIAL_THRESHOLD
        )
        severity_available = bool(sdg or mushra_loss)
        if sdg and mushra_loss:
            material_signal = sdg_material and mushra_material
            severity_conflict = sdg_material != mushra_material
        elif sdg:
            material_signal = sdg_material
            severity_conflict = False
        else:
            material_signal = mushra_material
            severity_conflict = False
        audibility_state = audibility["state"] if audibility else "audibility_indeterminate"
        if severity_conflict or not severity_available:
            truth = "indeterminate"
        elif audibility_state == "audible" and material_signal:
            truth = "materially_degraded"
        elif audibility_state == "audible":
            truth = "audible_nonmaterial"
        elif audibility_state == "not_demonstrably_audible" and not material_signal:
            truth = "transparent"
        else:
            truth = "indeterminate"
        groups.append(
            {
                "analysis_group_id": group_id,
                "partition": partitions[0],
                "audibility": _public_model(audibility),
                "sdg": _public_model(sdg),
                "mushra_loss": _public_model(mushra_loss),
                "sdg_material_signal": sdg_material,
                "mushra_material_signal": mushra_material,
                "bridge_disagreement": severity_conflict,
                "material_severity_signal": material_signal,
                "human_truth": truth,
            }
        )
    return groups


def _public_model(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    result = dict(value)
    for key in ("estimate", "lower", "upper", "standard_error", "standard_error_link_scale"):
        if key in result:
            result[key] = _round(result[key])
    return result


def _bridge_mapping(groups: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    for group in groups:
        if group["partition"] != "development" or group["sdg"] is None or group["mushra_loss"] is None:
            continue
        pairs.append(
            {
                "analysis_group_id": group["analysis_group_id"],
                "mushra_loss": group["mushra_loss"]["estimate"],
                "sdg_severity": min(100.0, max(0.0, -25.0 * group["sdg"]["estimate"])),
            }
        )
    knots = [
        {"mushra_loss": 0.0, "severity": 0.0, "role": "hidden_reference_anchor"},
        {"mushra_loss": 10.0, "severity": 25.0, "role": "material_boundary_anchor"},
    ]
    for pair in sorted(pairs, key=lambda item: (item["mushra_loss"], item["analysis_group_id"])):
        loss = min(100.0, max(0.0, pair["mushra_loss"]))
        if math.isclose(loss, 0.0) or math.isclose(loss, 10.0) or math.isclose(loss, 100.0):
            continue
        if loss < 10.0:
            severity = min(25.0, max(0.0, pair["sdg_severity"]))
        else:
            severity = min(100.0, max(25.0, pair["sdg_severity"]))
        knots.append({"mushra_loss": loss, "severity": severity, "role": "development_bridge"})
    knots.append({"mushra_loss": 100.0, "severity": 100.0, "role": "maximum_loss_anchor"})
    knots.sort(key=lambda item: (item["mushra_loss"], item["role"]))
    # Deterministic PAVA over bridge knots. Boundary anchors are protected by
    # clipping each side of the 10-point material boundary before pooling.
    for lower, upper in ((0.0, 10.0), (10.0, 100.0)):
        indices = [index for index, knot in enumerate(knots) if lower <= knot["mushra_loss"] <= upper]
        values = [knots[index]["severity"] for index in indices]
        blocks: list[dict[str, Any]] = []
        for local_index, value in enumerate(values):
            blocks.append({"start": local_index, "end": local_index, "weight": 1.0, "value": value})
            while len(blocks) >= 2 and blocks[-2]["value"] > blocks[-1]["value"]:
                right = blocks.pop()
                left = blocks.pop()
                weight = left["weight"] + right["weight"]
                blocks.append(
                    {
                        "start": left["start"],
                        "end": right["end"],
                        "weight": weight,
                        "value": (left["value"] * left["weight"] + right["value"] * right["weight"]) / weight,
                    }
                )
        fitted = values.copy()
        for block in blocks:
            for local_index in range(block["start"], block["end"] + 1):
                fitted[local_index] = block["value"]
        for index, value in zip(indices, fitted, strict=True):
            knots[index]["severity"] = value
    for knot in knots:
        if knot["role"] == "hidden_reference_anchor":
            knot["severity"] = 0.0
        elif knot["role"] == "material_boundary_anchor":
            knot["severity"] = 25.0
        elif knot["role"] == "maximum_loss_anchor":
            knot["severity"] = 100.0
        knot["mushra_loss"] = _round(knot["mushra_loss"])
        knot["severity"] = _round(knot["severity"])
    return {
        "method": "development_only_hierarchical_estimates_then_bounded_isotonic_pava_v1",
        "development_bridge_group_count": len(pairs),
        "sdg_transform": "severity=clip(-25*sdg,0,100)",
        "material_reference_points": {"sdg": -1.0, "mushra_loss": 10.0, "severity": 25.0},
        "knots": knots,
    }


def analyse(dataset: dict[str, Any]) -> dict[str, Any]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan_errors = validate_plan(plan)
    if plan_errors:
        raise ValueError("; ".join(plan_errors))
    errors = validate_dataset(dataset)
    if errors:
        raise ValueError("; ".join(errors))
    primary = _analyse_groups(dataset, sensitivity=False)
    sensitivity = _analyse_groups(dataset, sensitivity=True)
    primary_by_id = {item["analysis_group_id"]: item["human_truth"] for item in primary}
    sensitivity_by_id = {item["analysis_group_id"]: item["human_truth"] for item in sensitivity}
    eligible_primary = sum(_session_primary_eligible(item) for item in dataset["sessions"])
    eligible_sensitivity = sum(_session_sensitivity_eligible(item) for item in dataset["sessions"])
    return {
        "schema_version": 1,
        "report_id": "listening-analysis-" + _sha(dataset["dataset_id"], PLAN_ID)[:24],
        "state": "synthetic_listening_analysis_plumbing_only",
        "fixture_only": True,
        "scientific_gate_evaluated": False,
        "human_collection_authorized": False,
        "human_responses_observed": False,
        "analysis_plan_id": PLAN_ID,
        "analysis_plan_sha256": _file_sha256(PLAN_PATH),
        "implementation_sha256": _file_sha256(Path(__file__).resolve()),
        "dataset_id": dataset["dataset_id"],
        "manifest_id": dataset["manifest_id"],
        "manifest_sha256": dataset["manifest_sha256"],
        "model": {
            "audibility": "penalized_logistic_crossed_listener_source_random_intercepts",
            "severity": "penalized_gaussian_crossed_listener_source_random_intercepts",
            "variance_components": VARIANCE_COMPONENTS,
            "variance_components_frozen_from_score_blind_power_model": True,
            "multiplicity_adjusted_one_sided_z": Z_THRESHOLD,
            "raw_means_are_ground_truth": False,
        },
        "eligibility": {
            "sessions_total": len(dataset["sessions"]),
            "sessions_primary": eligible_primary,
            "sessions_sensitivity": eligible_sensitivity,
            "outcome_blind_exclusions_only": True,
        },
        "primary_groups": primary,
        "sensitivity_groups": sensitivity,
        "sensitivity_disagreements": sorted(
            group_id
            for group_id in set(primary_by_id) | set(sensitivity_by_id)
            if primary_by_id.get(group_id) != sensitivity_by_id.get(group_id)
        ),
        "bridge_mapping": _bridge_mapping(primary),
        "collection_or_oracle_gate": {
            "collection_eligible": False,
            "oracle_truth_eligible": False,
            "reason": "synthetic responses exercise analysis plumbing but cannot establish audibility or perceptual quality",
        },
    }


def _participant(index: int) -> str:
    return "participant-" + _sha(FIXTURE_ID, "participant", str(index))[:24]


def synthetic_dataset() -> dict[str, Any]:
    sessions = []
    responses = []
    listener_count = 240
    source_count = 120
    judgments = 15
    groups = (
        ("group-transparent", 10, -0.15, None),
        ("group-audible-nonmaterial", 17, -0.45, None),
        ("group-material-bridge", 18, -1.55, 20.0),
    )
    for listener in range(listener_count):
        participant_id = _participant(listener)
        session_id = "session-" + _sha(FIXTURE_ID, "session", str(listener))[:24]
        sessions.append(
            {
                "session_id": session_id,
                "participant_id": participant_id,
                "assignment_id": "assignment-" + _sha(FIXTURE_ID, "assignment", str(listener))[:24],
                "partition": "development",
                "checks": {
                    "consent_present": True,
                    "eligibility_pass": True,
                    "stimulus_binding_pass": True,
                    "delivery_pass": True,
                    "fixed_level_pass": True,
                    "training_complete": True,
                    "timing_pass": True,
                    "response_completeness_pass": True,
                    "duplicate_evidence": False,
                    "hidden_reference_quality_pass": True,
                    "anchor_quality_pass": True,
                },
            }
        )
        for group_id, correct_per_twenty, sdg_mean, mushra_loss in groups:
            for judgment in range(judgments):
                source = (listener * 7 + judgment * 11) % source_count
                source_id = f"source-{source:04d}"
                trial_id = "trial-" + _sha(group_id, source_id, "subtle")[:24]
                token = _sha(FIXTURE_ID, participant_id, group_id, str(judgment), "subtle")
                correct = int(token[:8], 16) % 20 < correct_per_twenty
                noise = ((int(token[8:16], 16) % 9) - 4) * 0.025
                responses.append(
                    {
                        "response_id": _sha(token, "response"),
                        "idempotency_key": _sha(token, "idempotency"),
                        "session_id": session_id,
                        "participant_id": participant_id,
                        "trial_id": trial_id,
                        "analysis_group_id": group_id,
                        "condition_stimulus_id": "stimulus-" + _sha(group_id, source_id)[:24],
                        "source_group_id": source_id,
                        "partition_group_id": "partition-" + _sha(source_id)[:24],
                        "partition": "development",
                        "method": "subtle",
                        "forced_choice_correct": correct,
                        "sdg": min(0.0, max(-4.0, sdg_mean + noise)),
                        "condition_score": None,
                        "hidden_reference_score": None,
                    }
                )
                if mushra_loss is not None:
                    mushra_token = _sha(FIXTURE_ID, participant_id, group_id, str(judgment), "mushra")
                    mushra_noise = ((int(mushra_token[:8], 16) % 9) - 4) * 0.5
                    hidden = 96.0 + ((int(mushra_token[8:16], 16) % 5) - 2) * 0.5
                    responses.append(
                        {
                            "response_id": _sha(mushra_token, "response"),
                            "idempotency_key": _sha(mushra_token, "idempotency"),
                            "session_id": session_id,
                            "participant_id": participant_id,
                            "trial_id": "trial-" + _sha(group_id, source_id, "mushra")[:24],
                            "analysis_group_id": group_id,
                            "condition_stimulus_id": "stimulus-" + _sha(group_id, source_id)[:24],
                            "source_group_id": source_id,
                            "partition_group_id": "partition-" + _sha(source_id)[:24],
                            "partition": "development",
                            "method": "mushra",
                            "forced_choice_correct": None,
                            "sdg": None,
                            "condition_score": max(0.0, hidden - mushra_loss + mushra_noise),
                            "hidden_reference_score": hidden,
                        }
                    )
    return {
        "schema_version": 1,
        "dataset_id": FIXTURE_ID,
        "state": "synthetic_fixture_only",
        "fixture_only": True,
        "human_collection_authorized": False,
        "human_responses_observed": False,
        "manifest_id": "manifest-synthetic-listening-analysis-v1",
        "manifest_sha256": _sha("synthetic-manifest-no-audio"),
        "analysis_plan_id": PLAN_ID,
        "sessions": sessions,
        "responses": responses,
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-output", type=Path, required=True)
    args = parser.parse_args()
    if args.synthetic_output.exists() or args.synthetic_output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.synthetic_output}")
    report = analyse(synthetic_dataset())
    args.synthetic_output.parent.mkdir(parents=True, exist_ok=True)
    args.synthetic_output.write_bytes(_json_bytes(report))
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "state": report["state"],
                "scientific_gate_evaluated": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
