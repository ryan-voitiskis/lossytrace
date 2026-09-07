#!/usr/bin/env python3
"""Score-free oracle integration of explicit alignment validity and configuration.

No metric, decoder, playback or human-data entry point is provided. Validation
checks record consistency, not the provenance or truth of the input waveform.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

import perceptual_degradation_alignment_validity_successor as development


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/oracle-validity-integration-plan.json"
PLAN_SHA = "99e87c837c0e7ef365dc03623b781ed46ec0eec5e84dbe12bf2b38549e14d138"
ALIGN = development.successor
MONO, TOPOLOGY = ALIGN.legacy, ALIGN.topology
RECORD_KIND = "perceptual_degradation_full_reference_oracle_score_free_v2"
MODES = {"subtle": 4.0, "quality_metric": 8.0}
ARTIFACTS = development.oracle.ARTIFACT_COMPONENTS
BINDINGS = {
    "research_contract": "docs/research/perceptual-degradation-contract-20260803.md",
    "alignment_implementation": "scripts/perceptual_degradation_alignment_v3.py",
    "alignment_development_report": "research/toolchains/evidence/perceptual-degradation-alignment-validity-successor-synthetic-20260907-001.json",
    "legacy_oracle": "scripts/perceptual_degradation_oracle.py",
    "probability_target_contract": "benchmarks/perceptual-degradation-v1/perceptual-target-semantics-plan.json",
}
DIAGNOSTIC_KEYS = {
    "integer_delay_samples", "fractional_delay_samples", "ambiguity_margin",
    "aligned_frames", "active_seconds", "edge_trim_seconds", "correlation",
    "gain", "drift", "structural", "search",
}
EARLY_REASONS = {"invalid_numeric_input", "no_valid_coarse_correlation", "no_valid_sample_correlation"}
CORRELATION_REASONS = {"insufficient_overlap", "invalid_numeric_input", "zero_energy", "zero_centered_energy", "numeric_failure"}
TOPOLOGY_REASONS = {"invalid_channel_shape", "unsupported_channel_map", "channel_topology_mismatch", "channel_map_mismatch"}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def fields(value: Any, names: set[str], label: str) -> None:
    require(type(value) is dict and set(value) == names, f"{label} field set differs")


def numeric(value: Any, label: str, *, nullable: bool = False, minimum: float | None = None, maximum: float | None = None, integer: bool = False) -> None:
    if nullable and value is None:
        return
    require(type(value) is int if integer else type(value) in (int, float), f"{label} numeric type differs")
    require(math.isfinite(value), f"{label} must be finite")
    require(minimum is None or value >= minimum, f"{label} below bound")
    require(maximum is None or value <= maximum, f"{label} above bound")


def reasons(value: Any, allowed: set[str], label: str) -> None:
    require(type(value) is list and all(type(item) is str for item in value), f"{label} reason type differs")
    require(value == sorted(set(value)) and set(value) <= allowed, f"{label} reason set differs")


def load_plan() -> dict[str, Any]:
    require(development.fixtures.sha(PLAN) == PLAN_SHA, "integration plan bytes differ")
    plan = json.loads(PLAN.read_text())
    require(set(plan["bindings"]) == set(BINDINGS), "integration binding inventory differs")
    for key, relative in BINDINGS.items():
        require(plan["bindings"][key] == {"path": relative, "sha256": development.fixtures.sha(ROOT / relative)}, "integration predecessor binding differs")
    require(plan["integration_contract"]["comparison_modes_minimum_active_seconds"] == MODES, "comparison modes differ")
    development.load_plan()
    return plan


def _counts(value: Any) -> None:
    fields(value, {"valid", "invalid"}, "search counts")
    numeric(value["valid"], "valid candidate count", minimum=0, integer=True)
    require(type(value["invalid"]) is dict and set(value["invalid"]) <= CORRELATION_REASONS, "invalid candidate reasons differ")
    for count in value["invalid"].values():
        numeric(count, "invalid candidate count", minimum=1, integer=True)


def _correlation(value: Any, frames: int) -> None:
    fields(value, {"value", "magnitude", "reason", "overlap_frames", "sampled_frames"}, "correlation")
    numeric(value["overlap_frames"], "correlation overlap", minimum=0, integer=True)
    numeric(value["sampled_frames"], "correlation sample count", minimum=0, maximum=value["overlap_frames"], integer=True)
    require(value["overlap_frames"] == frames, "correlation overlap differs from alignment")
    if value["value"] is None:
        require(value["reason"] in CORRELATION_REASONS and value["magnitude"] is None, "invalid correlation has fabricated magnitude or reason")
    else:
        numeric(value["value"], "signed correlation", minimum=-1, maximum=1)
        numeric(value["magnitude"], "correlation magnitude", minimum=0, maximum=1)
        require(value["reason"] is None and value["sampled_frames"] > 0, "defined correlation validity differs")
        require(value["magnitude"] == abs(value["value"]), "signed and magnitude correlations differ")
        stride = max(1, frames // MONO.MAX_CORRELATION_SAMPLES)
        require(frames >= 16 and value["sampled_frames"] == math.ceil(frames / stride), "selected correlation sampling support differs")


def _window(value: Any, count: int) -> None:
    fields(value, {"window_count", "valid_window_count", "invalid_reasons", "clock_drift_ppm", "residual_samples", "minimum_correlation", "reason"}, "window audit")
    require(type(value["window_count"]) is int and value["window_count"] == count, "window count differs")
    numeric(value["valid_window_count"], "valid window count", minimum=0, maximum=count, integer=True)
    require(type(value["invalid_reasons"]) is dict and set(value["invalid_reasons"]) <= {"no_valid_local_candidate"}, "window invalid reasons differ")
    for number in value["invalid_reasons"].values():
        numeric(number, "invalid window count", minimum=1, integer=True)
    if value["reason"] is None:
        require(value["valid_window_count"] == count and value["invalid_reasons"] == {}, "complete window audit has missing evidence")
        numeric(value["clock_drift_ppm"], "window drift")
        numeric(value["residual_samples"], "window residual", minimum=0)
        numeric(value["minimum_correlation"], "window correlation", minimum=0, maximum=1)
    else:
        require(value["reason"] in {"insufficient_window_span", "incomplete_valid_windows", "degenerate_window_positions", "fractional_peak_unavailable"}, "window failure reason differs")
        require(all(value[key] is None for key in ("clock_drift_ppm", "residual_samples", "minimum_correlation")), "unavailable window audit has invented estimates")
        if value["reason"] == "incomplete_valid_windows":
            require(value["valid_window_count"] < count and sum(value["invalid_reasons"].values()) == count - value["valid_window_count"], "incomplete window counts differ")
        elif value["reason"] == "degenerate_window_positions":
            require(value["valid_window_count"] == count and not value["invalid_reasons"], "degenerate window counts differ")
        else:
            require(value["valid_window_count"] == 0 and not value["invalid_reasons"], "unexecuted window counts differ")


def _gain(value: Any) -> None:
    fields(value, {"linear_gain", "observed_gain_db", "polarity", "reason"}, "gain")
    if value["reason"] == "zero_fitted_gain":
        numeric(value["linear_gain"], "zero fitted gain")
        require(value["linear_gain"] == 0 and value["observed_gain_db"] is None and value["polarity"] is None, "zero gain has invented dB or polarity")
    elif value["reason"] == "zero_reference_energy":
        require(all(value[key] is None for key in ("linear_gain", "observed_gain_db", "polarity")), "undefined gain has invented values")
    elif value["reason"] == "linear_gain_not_representable":
        require(value["linear_gain"] is None and value["polarity"] in {"preserved", "inverted"}, "nonrepresentable gain differs")
        numeric(value["observed_gain_db"], "nonrepresentable gain dB")
    else:
        require(value["reason"] is None, "gain reason differs")
        numeric(value["linear_gain"], "linear gain")
        numeric(value["observed_gain_db"], "gain dB")
        require(value["linear_gain"] != 0, "defined gain is zero")
        require(value["polarity"] == ("inverted" if value["linear_gain"] < 0 else "preserved"), "gain polarity differs")
        reconstructed = math.copysign(10 ** (value["observed_gain_db"] / 20), value["linear_gain"])
        require(math.isclose(value["linear_gain"], reconstructed, rel_tol=1e-12, abs_tol=math.ulp(value["linear_gain"])), "gain scales disagree")


def _channel(value: Any, sample_rate: int, reference_frames: int, test_frames: int, minimum_active: float) -> None:
    fields(value, {"channel", "status", "reasons", "diagnostics"}, "channel")
    d = value["diagnostics"]
    fields(d, DIAGNOSTIC_KEYS, "channel diagnostics")
    require(type(d["search"]) is dict and set(d["search"]) <= {"coarse", "sample"}, "search stages differ")
    for counts in d["search"].values():
        _counts(counts)
    if d["correlation"] is None:
        require(all(d[key] is None for key in DIAGNOSTIC_KEYS - {"search"}), "unavailable alignment has invented diagnostics")
        reasons(value["reasons"], EARLY_REASONS, "early channel")
        require(value["status"] == "unsupported" and len(value["reasons"]) == 1, "unavailable channel status differs")
        reason = value["reasons"][0]
        if reason == "invalid_numeric_input":
            require(d["search"] == {}, "invalid numeric channel ran a search")
        elif reason == "no_valid_coarse_correlation":
            require(set(d["search"]) == {"coarse"} and d["search"]["coarse"]["valid"] == 0, "coarse failure counts differ")
        else:
            require(set(d["search"]) == {"coarse", "sample"} and d["search"]["coarse"]["valid"] > 0 and d["search"]["sample"]["valid"] == 0, "sample failure counts differ")
        return
    require(set(d["search"]) == {"coarse", "sample"} and all(item["valid"] > 0 for item in d["search"].values()), "estimated alignment lacks valid candidates")
    numeric(d["integer_delay_samples"], "integer delay", integer=True)
    numeric(d["fractional_delay_samples"], "fractional delay", nullable=True, minimum=-0.5, maximum=0.5)
    numeric(d["ambiguity_margin"], "ambiguity margin", nullable=True, minimum=0, maximum=1)
    numeric(d["aligned_frames"], "aligned frames", minimum=1, maximum=min(reference_frames, test_frames), integer=True)
    numeric(d["active_seconds"], "active seconds", minimum=0)
    numeric(d["edge_trim_seconds"], "edge trim", minimum=0)
    envelope_block = max(1, round(sample_rate / MONO.ENVELOPE_RATE_HZ))
    search_boundary = (math.ceil(2 * sample_rate / envelope_block) + 1) * envelope_block
    require(abs(d["integer_delay_samples"]) <= search_boundary, "delay outside producer coarse-plus-refinement search boundary")
    expected_frames = MONO._overlap(reference_frames, test_frames, d["integer_delay_samples"])[2]
    require(d["aligned_frames"] == expected_frames, "aligned frame count differs from delay")
    trim = reference_frames + test_frames - 2 * expected_frames
    require(d["edge_trim_seconds"] == trim / sample_rate, "edge trim calculation differs")
    # The producer counts active blocks, including a retained final partial block.
    block = max(1, sample_rate // 20)
    require(d["active_seconds"] <= math.ceil(expected_frames / block) * block / sample_rate, "active duration exceeds available blocks")
    _correlation(d["correlation"], expected_frames)
    require(d["correlation"]["value"] is not None, "selected lag has undefined correlation")
    _gain(d["gain"])
    _window(d["drift"], 5)
    _window(d["structural"], 7)
    for name, seconds in (("drift", 2), ("structural", 1)):
        if name == "structural" and d["fractional_delay_samples"] is None:
            require(d[name]["reason"] == "fractional_peak_unavailable", "structural audit used an unavailable fractional lag")
        elif MONO._overlap(reference_frames, test_frames, round(d["integer_delay_samples"] + d["fractional_delay_samples"]) if name == "structural" else d["integer_delay_samples"])[2] < sample_rate * seconds:
            require(d[name]["reason"] == "insufficient_window_span", "short alignment has invented window support")
        else:
            require(d[name]["reason"] not in {"insufficient_window_span", "fractional_peak_unavailable"}, "window failure contradicts available alignment")
    expected = []
    if d["fractional_delay_samples"] is None:
        expected.append("fractional_peak_unavailable")
    if d["ambiguity_margin"] is None:
        expected.append("ambiguity_margin_unavailable")
    elif d["ambiguity_margin"] < MONO.MIN_AMBIGUITY_MARGIN:
        expected.append("ambiguous_alignment_peak")
    if d["active_seconds"] < minimum_active:
        expected.append("insufficient_active_audio")
    if d["correlation"]["magnitude"] < MONO.MIN_ALIGNMENT_CORRELATION:
        expected.append("low_alignment_correlation")
    for name in ("drift", "structural"):
        audit = d[name]
        if audit["reason"] is not None:
            expected.append(f"{name}_windows_unavailable")
        elif audit["minimum_correlation"] < MONO.MIN_ALIGNMENT_CORRELATION:
            expected.append("low_alignment_correlation" if name == "drift" else "low_structural_window_correlation")
    if d["drift"]["clock_drift_ppm"] is not None and abs(d["drift"]["clock_drift_ppm"]) > MONO.MAX_CLOCK_DRIFT_PPM:
        expected.append("clock_drift_exceeds_limit")
    if d["drift"]["residual_samples"] is not None and d["drift"]["residual_samples"] > MONO.MAX_NONLINEAR_DRIFT_RESIDUAL_SAMPLES:
        expected.append("nonlinear_drift")
    if d["structural"]["residual_samples"] is not None and d["structural"]["residual_samples"] > TOPOLOGY.MAX_STRUCTURAL_RESIDUAL_SAMPLES:
        expected.append("structural_edit_suspected")
    if d["gain"]["reason"] is not None:
        expected.append("gain_or_polarity_unavailable")
    elif abs(d["gain"]["observed_gain_db"]) > MONO.MAX_GAIN_ABS_DB:
        expected.append("gain_exceeds_limit")
    if trim / sample_rate > MONO.MAX_EDGE_TRIM_SECONDS or trim / min(reference_frames, test_frames) > MONO.MAX_EDGE_TRIM_FRACTION:
        expected.append("excessive_trim")
    require(value["reasons"] == sorted(set(expected)), "channel reasons disagree with configured diagnostics")
    require(value["status"] == ("unsupported" if expected else "supported"), "channel status disagrees with diagnostics")


def _all(values: list[Any], function) -> Any:
    return function(values) if values and all(value is not None for value in values) else None


def validate_alignment(record: Any, comparison_mode: str) -> list[str]:
    try:
        require(comparison_mode in MODES, "comparison mode differs")
        fields(record, {"schema_version", "record_kind", "case_id", "status", "public_verdict_enabled", "input", "alignment", "support", "sample_correction_applied", "perceptual_claim"}, "alignment")
        require(type(record["schema_version"]) is int and record["schema_version"] == 1 and record["record_kind"] == ALIGN.RECORD_KIND, "alignment record identity differs")
        require(all(record[key] is False for key in ("public_verdict_enabled", "sample_correction_applied", "perceptual_claim")), "alignment execution boundary differs")
        identity = record["case_id"]
        require(type(identity) is str and len(identity) == 69 and identity.startswith("case-") and all(char in "0123456789abcdef" for char in identity[5:]), "case identity differs")
        fields(record["input"], {"sample_rate_hz", "reference", "test"}, "input")
        rate = record["input"]["sample_rate_hz"]
        numeric(rate, "sample rate", minimum=1, integer=True)
        for side in (record["input"]["reference"], record["input"]["test"]):
            fields(side, {"channel_count", "channel_map", "frames"}, "input side")
            numeric(side["channel_count"], "channel count", minimum=0, maximum=2, integer=True)
            numeric(side["frames"], "input frames", minimum=0, integer=True)
            require(type(side["channel_map"]) is list and all(type(name) is str and name in {"M", "L", "R"} for name in side["channel_map"]), "declared channel map is outside prototype representation")
        ref, test = record["input"]["reference"], record["input"]["test"]
        fields(record["alignment"], {"summary", "channels"}, "alignment payload")
        channels = record["alignment"]["channels"]
        require(type(channels) is list and len(channels) <= 2, "channel records differ")
        fields(record["support"], {"reasons", "limits_id", "predecessor_limits_ids"}, "alignment support")
        require(record["support"]["limits_id"] == ALIGN.LIMITS_ID and record["support"]["predecessor_limits_ids"] == [MONO.LIMITS_ID, TOPOLOGY.LIMITS_ID], "alignment limits binding differs")
        if not channels:
            reasons(record["support"]["reasons"], TOPOLOGY_REASONS, "topology")
            require(record["support"]["reasons"] and record["status"] == "unsupported", "empty channel evidence cannot be supported")
            expected_reasons = []
            if ref["channel_count"] != test["channel_count"]:
                expected_reasons.append("channel_topology_mismatch")
            if ref["channel_map"] != test["channel_map"] or any(len(side["channel_map"]) != side["channel_count"] for side in (ref, test)):
                expected_reasons.append("channel_map_mismatch")
            if any(tuple(side["channel_map"]) not in TOPOLOGY.SUPPORTED_CHANNEL_MAPS for side in (ref, test)):
                expected_reasons.append("unsupported_channel_map")
            # Ragged channel lengths are not recoverable from this first-channel
            # summary. Preserve a producer-declared rejection, never infer a pass.
            if "invalid_channel_shape" in record["support"]["reasons"] or any(side["frames"] == 0 or side["channel_count"] == 0 for side in (ref, test)):
                expected_reasons.append("invalid_channel_shape")
            expected_reasons = sorted(expected_reasons)
        else:
            require(ref["channel_count"] == test["channel_count"] == len(channels) and ref["channel_map"] == test["channel_map"], "channel topology disagrees with channel evidence")
            require(tuple(ref["channel_map"]) in TOPOLOGY.SUPPORTED_CHANNEL_MAPS and [item["channel"] for item in channels] == ref["channel_map"], "channel identity projection differs")
            for channel in channels:
                _channel(channel, rate, ref["frames"], test["frames"], MODES[comparison_mode])
            expected_reasons = sorted({reason for channel in channels for reason in channel["reasons"]})
        d = [channel["diagnostics"] for channel in channels]
        lags = [item["integer_delay_samples"] + item["fractional_delay_samples"] if item["integer_delay_samples"] is not None and item["fractional_delay_samples"] is not None else None for item in d]
        common = _all(lags, lambda values: math.fsum(values) / len(values))
        spread = _all(lags, lambda values: max(values) - min(values))
        expected_summary = {
            "integer_delay_samples": math.floor(common + 0.5) if common is not None else None,
            "fractional_delay_samples": common - math.floor(common + 0.5) if common is not None else None,
            "channel_lag_spread_samples": spread,
            "minimum_correlation": _all([item["correlation"]["magnitude"] if item["correlation"] else None for item in d], min),
            "minimum_structural_window_correlation": _all([item["structural"]["minimum_correlation"] if item["structural"] else None for item in d], min),
            "clock_drift_ppm": _all([item["drift"]["clock_drift_ppm"] if item["drift"] else None for item in d], lambda values: math.fsum(values) / len(values)),
            "aligned_frames": _all([item["aligned_frames"] for item in d], min),
            "active_seconds": _all([item["active_seconds"] for item in d], min),
        }
        require(canonical(record["alignment"]["summary"]) == canonical(expected_summary), "complete-channel summary differs or imputes missing evidence")
        if spread is not None and spread > TOPOLOGY.MAX_CHANNEL_LAG_DISAGREEMENT_SAMPLES:
            expected_reasons = sorted(set(expected_reasons) | {"channel_alignment_disagreement"})
        require(record["support"]["reasons"] == expected_reasons and record["status"] == ("unsupported" if expected_reasons else "supported"), "alignment support disagrees with channel evidence")
        canonical(record)
    except (ValueError, TypeError, KeyError, OverflowError, IndexError) as error:
        return [f"invalid alignment record: {error}"]
    return []


def _envelope(alignment: dict[str, Any], comparison_mode: str) -> dict[str, Any]:
    unsupported = alignment["status"] == "unsupported"
    return {
        "schema_version": 1, "record_kind": RECORD_KIND, "assessment_mode": "full_reference",
        "case_id": alignment["case_id"], "result_state": "unsupported_alignment" if unsupported else "execution_blocked",
        "public_verdict_enabled": False,
        "alignment_configuration": {"comparison_mode": comparison_mode, "minimum_active_seconds": MODES[comparison_mode], "maximum_delay_seconds": 2.0, "producer_sha256": "d9296e62a806a811d281cac93ae65f9bfcaab310aa5dfe12127bfc09199b7581"},
        "alignment": copy.deepcopy(alignment),
        "evidence_scope": {"input_provenance": "unverified_by_assembler", "clean_reference_eligibility": "unverified", "synthetic_origin_inferred_from_record": False, "metric_or_human_execution_performed_by_assembler": False, "sample_correction_performed_by_assembler": False},
        "metric_execution": {"state": "not_run_alignment_unsupported" if unsupported else "not_authorized", "suite_selected": False, "raw_outputs": None},
        "human_calibration": {"state": "unavailable", "mapping_id": None, "evidence_id": None, "prediction_unit": None, "population_averaging_rule": None},
        "outcomes": {"categorical_state": "indeterminate", "impairment_severity": None, "impairment_severity_interval": None,
                     "correct_response_probability": None, "correct_response_probability_interval": None,
                     "audible_condition_probability": None, "audible_condition_probability_interval": None,
                     "artifact_profile": {"state": "unavailable", "components": {key: None for key in ARTIFACTS}}},
        "support": {"supported": False, "alignment_reason_codes": alignment["support"]["reasons"][:],
                    "abstention_reasons": (["alignment_unsupported"] if unsupported else []) + ["source_provenance_unverified", "human_calibration_unavailable", "perceptual_metric_execution_not_authorized"]},
        "uncertainty": {"state": "unquantified", "interval_level": None, "replicates": 0},
        "bindings": {"integration_plan_sha256": PLAN_SHA, "alignment_limits_id": ALIGN.LIMITS_ID, "metric_execution_gate_id": None, "oracle_mapping_id": None},
    }


def assemble_score_free(alignment: Any, *, comparison_mode: str) -> dict[str, Any]:
    load_plan()
    errors = validate_alignment(alignment, comparison_mode)
    require(not errors, "; ".join(errors))
    return _envelope(alignment, comparison_mode)


def validate_score_free_record(record: Any) -> list[str]:
    try:
        require(type(record) is dict, "oracle record must be an object")
        mode = record["alignment_configuration"]["comparison_mode"]
        errors = validate_alignment(record["alignment"], mode)
        require(not errors, "; ".join(errors))
        require(canonical(record) == canonical(_envelope(record["alignment"], mode)), "oracle envelope has altered fields, outcomes or execution boundaries")
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return [f"invalid score-free oracle: {error}"]
    return []


def synthetic_records() -> list[tuple[str, dict[str, Any]]]:
    load_plan()
    f = development.fixtures
    f.reserve()
    base = [[value / 2**20 for value in channel] for channel in f.fixture(f.FAMILIES[0])]
    gap = base[0][:]
    gap[4800:7200] = [0.0] * 2400
    doubled = [channel * 2 for channel in base]
    records = []
    for name, mode, reference, test, ref_map, test_map in (
        ("identity_subtle", "subtle", base, base, ["L", "R"], ["L", "R"]),
        ("relative_polarity_subtle", "subtle", base, [base[0], [-value for value in base[1]]], ["L", "R"], ["L", "R"]),
        ("dropout_subtle", "subtle", base, [base[0], [0.0] * len(base[1])], ["L", "R"], ["L", "R"]),
        ("silent_window_subtle", "subtle", [gap], [gap], ["M"], ["M"]),
        ("identity_quality_six_seconds", "quality_metric", base, base, ["L", "R"], ["L", "R"]),
        ("identity_quality_twelve_seconds", "quality_metric", doubled, doubled, ["L", "R"], ["L", "R"]),
        ("topology_mismatch", "subtle", base, [base[0]], ["L", "R"], ["M"]),
    ):
        f.reserve()
        before = copy.deepcopy((reference, test))
        alignment = ALIGN.align_channels(reference_channels=reference, test_channels=test, reference_channel_map=ref_map,
                                         test_channel_map=test_map, sample_rate_hz=2000, recipe_identity=f"oracle-validity-integration-20260907-001:{name}",
                                         minimum_active_seconds=MODES[mode], maximum_delay_seconds=2.0)
        require((reference, test) == before, "synthetic alignment changed samples")
        record = assemble_score_free(alignment, comparison_mode=mode)
        require(record["alignment"] == alignment and not validate_score_free_record(record), "oracle integration did not preserve valid input")
        records.append((name, record))
    return records


def build_report() -> dict[str, Any]:
    plan = load_plan()
    records = synthetic_records()
    cases = [{"construction": name, "comparison_mode": record["alignment_configuration"]["comparison_mode"],
              "result_state": record["result_state"], "support": record["support"],
              "alignment_summary": development.fixtures.formatted(record["alignment"]["alignment"]["summary"]),
              "alignment_raw_nulls_preserved": True, "score_free_record_valid": not validate_score_free_record(record)} for name, record in records]
    return {"schema_version": 1, "report_id": plan["plan_id"], "state": "synthetic_oracle_validity_integration_complete",
            "plan_sha256": PLAN_SHA, "implementation_sha256": development.fixtures.sha(Path(__file__)), "bindings": plan["bindings"],
            "integration_contract": plan["integration_contract"], "claim_boundary": plan["claim_boundary"],
            "case_count": len(cases), "execution_blocked_count": sum(item["result_state"] == "execution_blocked" for item in cases),
            "unsupported_alignment_count": sum(item["result_state"] == "unsupported_alignment" for item in cases),
            "cases": cases, "common_unavailable_outcomes": records[0][1]["outcomes"],
            "generic_assembler_input_provenance": "unverified_by_assembler", "runner_input_origin": "declared_in_memory_synthetic_constructions_only",
            "real_audio_accessed": False, "samples_changed_by_alignment_or_assembler": False, "next_requirement": plan["next_requirement"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(development.fixtures.canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
