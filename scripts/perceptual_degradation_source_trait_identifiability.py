#!/usr/bin/env python3
"""Replay score-blind source-trait identifiability witnesses."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "source-trait-identifiability-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-source-trait-identifiability-20260814-001.json"
)
PLAN_ID = "perceptual-degradation-source-trait-identifiability-20260814-001"
REPORT_ID = PLAN_ID

EXPECTED_AUTHORIZATION = {
    "committed_metadata_read_authorized": True,
    "synthetic_numeric_fixture_execution_authorized": True,
    "actual_source_audio_access_authorized": False,
    "retained_odaq_reference_read_authorized": False,
    "provider_audio_access_authorized": False,
    "exact_member_selection_authorized": False,
    "source_trait_assignment_authorized": False,
    "stimulus_generation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "response_or_outcome_access_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_RESOURCES = {
    "minimum_free_disk_gib": 15,
    "maximum_workers": 1,
    "fresh_temporary_directories": True,
    "replay_count": 2,
    "byte_identical_reports_required": True,
    "retain_generated_audio": False,
}

EXPECTED_TRAITS = [
    "natural_bandwidth_limit",
    "quiet",
    "sparse",
    "tonal",
    "synthetic",
    "noisy",
    "clipped",
]

EXPECTED_WITNESSES = {
    "natural-bandwidth-versus-generated-lowpass",
    "quiet-source-versus-attenuated-source",
    "synthetic-noise-versus-recorded-noise",
    "source-clipping-versus-intentional-flat-top",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def require_disk_reserve(path: Path, minimum_free_gib: int) -> int:
    free = shutil.disk_usage(path).free
    if free < minimum_free_gib * 1024**3:
        raise ValueError(f"free disk is below {minimum_free_gib} GiB reserve")
    return free


def _bound(plan: dict[str, Any], binding_id: str, root: Path = ROOT) -> Path:
    return root / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_source_trait_identifiability_contract_frozen_before_replay"
    ):
        errors.append("plan state differs")
    expected_bindings = {
        "research_contract",
        "research_plan",
        "source_condition_qualification",
        "source_candidate_plan",
        "odaq_acquisition_result",
        "negative_control_topology_plan",
        "negative_control_topology_report",
        "negative_control_technical_repair_plan",
        "negative_control_technical_repair_report",
    }
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("bindings differ")
    else:
        for binding_id, binding in bindings.items():
            relative = binding.get("path") if isinstance(binding, dict) else None
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"binding {binding_id} path differs")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"binding {binding_id} path is missing")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"binding {binding_id} sha256 differs")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization differs")
    if plan.get("resources") != EXPECTED_RESOURCES:
        errors.append("resources differ")
    policy = plan.get("qualification_policy", {})
    if policy.get("required_trait_ids") != EXPECTED_TRAITS:
        errors.append("required trait inventory differs")
    for key in (
        "pcm_descriptor_is_provenance",
        "generated_transform_can_substitute_for_natural_trait",
        "shared_candidate_can_establish_independent_trait_contrasts",
        "nominal_metadata_can_assign_perceptual_truth",
        "trait_members_may_be_selected_from_metric_or_listener_outcomes",
    ):
        if policy.get(key) is not False:
            errors.append(f"qualification policy {key} must be false")
    if policy.get("exact_member_assignment_requires_separate_authorization") is not True:
        errors.append("exact-member authorization policy differs")
    obligations = plan.get("trait_proof_obligations")
    if not isinstance(obligations, dict) or list(obligations) != EXPECTED_TRAITS:
        errors.append("trait proof obligations differ")
    witnesses = plan.get("non_identifiability_witnesses", [])
    if {row.get("witness_id") for row in witnesses} != EXPECTED_WITNESSES:
        errors.append("non-identifiability witnesses differ")
    for row in witnesses:
        if (
            row.get("expected_pcm_relation") != "byte_identical"
            or len(row.get("latent_histories", [])) != 2
        ):
            errors.append(f"witness contract differs: {row.get('witness_id')}")
    fixtures = plan.get("overlap_and_contrast_fixtures", {})
    expected_fixture_ids = [
        "sparse-tonal-overlap",
        "sparse-nontonal-contrast",
        "tonal-nonsparse-contrast",
    ]
    if [row.get("fixture_id") for row in fixtures.get("fixtures", [])] != expected_fixture_ids:
        errors.append("overlap fixture inventory differs")
    candidates = plan.get("candidate_record_expectations")
    if not isinstance(candidates, dict) or list(candidates) != EXPECTED_TRAITS:
        errors.append("candidate expectations differ")
    claims = plan.get("claim_boundary")
    if not isinstance(claims, dict) or not claims:
        errors.append("claim boundary missing")
    elif any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return sorted(set(errors))


def pcm_s16(samples: Sequence[int]) -> bytes:
    if any(value < -32768 or value > 32767 for value in samples):
        raise ValueError("sample outside signed-16 range")
    return struct.pack(f"<{len(samples)}h", *samples)


def _noise_sample(index: int, prefix: str) -> int:
    digest = hashlib.sha256(prefix.encode("ascii") + index.to_bytes(8, "big")).digest()
    return (int.from_bytes(digest[:2], "big") % 24001) - 12000


def _tone_sample(index: int, sample_rate: int, tone_hz: int, amplitude: int) -> int:
    return round(amplitude * math.sin(2.0 * math.pi * tone_hz * index / sample_rate))


def witness_fixture(fixture_id: str) -> bytes:
    sample_rate = 8000
    frames = 8000
    if fixture_id == "bandlimited-multitone-s16-v1":
        samples = [
            round(
                7000 * math.sin(2 * math.pi * 300 * i / sample_rate)
                + 5000 * math.sin(2 * math.pi * 1100 * i / sample_rate)
            )
            for i in range(frames)
        ]
    elif fixture_id == "quiet-tone-s16-v1":
        samples = [_tone_sample(i, sample_rate, 500, 128) for i in range(frames)]
    elif fixture_id == "deterministic-noise-s16-v1":
        samples = [_noise_sample(i, "source-trait-witness-noise-v1\0") for i in range(frames)]
    elif fixture_id == "flat-top-wave-s16-v1":
        samples = []
        for i in range(frames):
            raw = _tone_sample(i, sample_rate, 500, 24000)
            samples.append(max(-10000, min(10000, raw)))
    else:
        raise ValueError(f"unknown witness fixture: {fixture_id}")
    return pcm_s16(samples)


def replay_non_identifiability_witness(row: dict[str, Any]) -> dict[str, Any]:
    fixture = witness_fixture(row["fixture_id"])
    first_history_pcm = bytes(fixture)
    second_history_pcm = bytes(fixture)
    return {
        "witness_id": row["witness_id"],
        "fixture_id": row["fixture_id"],
        "latent_history_count": len(row["latent_histories"]),
        "latent_histories": row["latent_histories"],
        "first_pcm_sha256": sha256_bytes(first_history_pcm),
        "second_pcm_sha256": sha256_bytes(second_history_pcm),
        "pcm_byte_count": len(fixture),
        "pcm_byte_identical": first_history_pcm == second_history_pcm,
        "conclusion": row["conclusion"],
        "source_member_included": False,
        "trait_truth_included": False,
    }


def overlap_fixture_samples(
    fixture_id: str, *, sample_rate: int, total_frames: int, block_frames: int, tone_hz: int
) -> list[int]:
    active_blocks = {1, 7}
    values: list[int] = []
    for index in range(total_frames):
        block = index // block_frames
        if fixture_id == "sparse-tonal-overlap":
            value = _tone_sample(index, sample_rate, tone_hz, 12000) if block in active_blocks else 0
        elif fixture_id == "sparse-nontonal-contrast":
            value = _noise_sample(index, "source-trait-overlap-noise-v1\0") if block in active_blocks else 0
        elif fixture_id == "tonal-nonsparse-contrast":
            value = _tone_sample(index, sample_rate, tone_hz, 12000)
        else:
            raise ValueError(f"unknown overlap fixture: {fixture_id}")
        values.append(value)
    return values


def active_block_count(samples: Sequence[int], block_frames: int) -> int:
    return sum(
        any(value != 0 for value in samples[start : start + block_frames])
        for start in range(0, len(samples), block_frames)
    )


def tone_projection_share(
    samples: Sequence[int], sample_rate: int, tone_hz: int, block_frames: int
) -> float:
    active_indices = [
        index
        for start in range(0, len(samples), block_frames)
        if any(value != 0 for value in samples[start : start + block_frames])
        for index in range(start, min(start + block_frames, len(samples)))
    ]
    energy = sum(float(samples[index]) ** 2 for index in active_indices)
    if energy == 0:
        return 0.0
    sine = [math.sin(2 * math.pi * tone_hz * i / sample_rate) for i in active_indices]
    cosine = [math.cos(2 * math.pi * tone_hz * i / sample_rate) for i in active_indices]
    sin_norm = sum(value * value for value in sine)
    cos_norm = sum(value * value for value in cosine)
    sin_dot = sum(samples[index] * basis for index, basis in zip(active_indices, sine))
    cos_dot = sum(samples[index] * basis for index, basis in zip(active_indices, cosine))
    projected = sin_dot * sin_dot / sin_norm + cos_dot * cos_dot / cos_norm
    return min(1.0, projected / energy)


def replay_overlap_fixture(contract: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    sample_rate = contract["sample_rate_hz"]
    total_frames = sample_rate * contract["duration_seconds"]
    block_frames = contract["block_frames"]
    samples = overlap_fixture_samples(
        row["fixture_id"],
        sample_rate=sample_rate,
        total_frames=total_frames,
        block_frames=block_frames,
        tone_hz=contract["tone_hz"],
    )
    return {
        "fixture_id": row["fixture_id"],
        "frame_count": len(samples),
        "block_count": len(samples) // block_frames,
        "active_block_count": active_block_count(samples, block_frames),
        "tone_projection_share": round(
            tone_projection_share(
                samples, sample_rate, contract["tone_hz"], block_frames
            ),
            9,
        ),
        "pcm_sha256": sha256_bytes(pcm_s16(samples)),
        "source_member_included": False,
        "trait_truth_included": False,
    }


def audit_candidate_records(plan: dict[str, Any]) -> list[dict[str, Any]]:
    topology = load_json(_bound(plan, "negative_control_topology_plan"))
    observed = {
        row["class_id"]: row for row in topology["negative_class_topology"]["source_trait_axis"]
    }
    rows = []
    for trait_id in EXPECTED_TRAITS:
        expected = plan["candidate_record_expectations"][trait_id]
        row = observed[trait_id]
        candidate_ids = row.get("candidate_ids", [])
        matches = (
            candidate_ids == expected["candidate_ids"]
            and row.get("readiness") == expected["readiness"]
        )
        if not matches:
            raise ValueError(f"candidate record differs: {trait_id}")
        rows.append(
            {
                "trait_id": trait_id,
                "candidate_ids": candidate_ids,
                "readiness": row["readiness"],
                "candidate_record_matches_bound_topology": True,
                "exact_members_frozen": False,
                "trait_assigned": False,
            }
        )
    return rows


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    witnesses = [
        replay_non_identifiability_witness(row)
        for row in plan["non_identifiability_witnesses"]
    ]
    overlap_contract = plan["overlap_and_contrast_fixtures"]
    overlaps = [
        replay_overlap_fixture(overlap_contract, row)
        for row in overlap_contract["fixtures"]
    ]
    return {
        "proof_obligation_audit": [
            {
                "trait_id": trait_id,
                "common_proof_obligation_count": len(
                    plan["qualification_policy"]["common_proof_obligations"]
                ),
                "descriptor_evidence": plan["trait_proof_obligations"][trait_id]["descriptor_evidence"],
                "provenance_evidence": plan["trait_proof_obligations"][trait_id]["provenance_evidence"],
                "independent_contrast": plan["trait_proof_obligations"][trait_id]["independent_contrast"],
                "proof_obligations_frozen": True,
                "proof_obligations_satisfied_by_current_replay": False,
            }
            for trait_id in EXPECTED_TRAITS
        ],
        "non_identifiability_witnesses": witnesses,
        "overlap_and_contrast_cases": overlaps,
        "candidate_record_audit": audit_candidate_records(plan),
    }


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    require_disk_reserve(ROOT, plan["resources"]["minimum_free_disk_gib"])
    payload_bytes: list[bytes] = []
    for _ in range(plan["resources"]["replay_count"]):
        with tempfile.TemporaryDirectory(
            prefix="lossytrace-source-trait-identifiability-"
        ) as directory:
            output = Path(directory) / "payload.json"
            output.write_bytes(canonical_bytes(build_payload(plan)))
            payload_bytes.append(output.read_bytes())
    payload_hashes = [sha256_bytes(value) for value in payload_bytes]
    if len(set(payload_bytes)) != 1:
        raise ValueError("fresh replay payloads differ")
    payload = json.loads(payload_bytes[0])
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_source_trait_identifiability_replayed",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "authority": plan["authorization"],
        "resources": {
            "minimum_free_disk_gib_preserved": plan["resources"]["minimum_free_disk_gib"],
            "maximum_workers_used": 1,
            "generated_audio_retained": False,
        },
        "replay_observation": {
            "fresh_temporary_replay_count": len(payload_bytes),
            "payload_sha256s": payload_hashes,
            "byte_identical": len(set(payload_bytes)) == 1,
            "paths_included": False,
            "timing_included": False,
        },
        **payload,
        "summary": {
            "required_source_trait_count": len(EXPECTED_TRAITS),
            "proof_obligation_record_count": len(payload["proof_obligation_audit"]),
            "non_identifiability_witness_count": len(payload["non_identifiability_witnesses"]),
            "byte_identical_pcm_witness_count": sum(
                row["pcm_byte_identical"] for row in payload["non_identifiability_witnesses"]
            ),
            "overlap_and_contrast_fixture_count": len(payload["overlap_and_contrast_cases"]),
            "explicit_candidate_record_count": sum(
                bool(row["candidate_ids"]) for row in payload["candidate_record_audit"]
            ),
            "missing_explicit_candidate_traits": [
                row["trait_id"] for row in payload["candidate_record_audit"] if not row["candidate_ids"]
            ],
            "actual_audio_accessed": False,
            "source_member_selected": False,
            "trait_truth_included": False,
            "perceptual_metric_executed": False,
            "listener_response_collected": False,
            "public_verdict_enabled": False,
        },
        "decision": {
            "source_trait_proof_contract_ready": True,
            "pcm_only_trait_assignment_rejected": True,
            "independent_sparse_tonal_contrasts_required": True,
            "exact_member_provenance_audit_ready": True,
            "quiet_candidate_identified": False,
            "naturally_clipped_candidate_identified": False,
            "exact_source_trait_members_frozen": False,
            "source_trait_scientific_coverage_complete": False,
            "human_truth_present": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_gate": (
                "Obtain separate authority for an exact-member metadata and provenance audit, "
                "then require independent quiet, clipped, sparse and tonal candidates before "
                "any source-trait manifest can be frozen."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("state") != "score_blind_source_trait_identifiability_replayed":
        errors.append("report state differs")
    if report.get("authority") != EXPECTED_AUTHORIZATION:
        errors.append("report authority differs")
    replay = report.get("replay_observation", {})
    if (
        replay.get("fresh_temporary_replay_count") != 2
        or replay.get("byte_identical") is not True
        or len(set(replay.get("payload_sha256s", []))) != 1
        or replay.get("paths_included") is not False
        or replay.get("timing_included") is not False
    ):
        errors.append("replay observation differs")
    witnesses = report.get("non_identifiability_witnesses", [])
    if {row.get("witness_id") for row in witnesses} != EXPECTED_WITNESSES:
        errors.append("witness inventory differs")
    for row in witnesses:
        if (
            row.get("pcm_byte_identical") is not True
            or row.get("first_pcm_sha256") != row.get("second_pcm_sha256")
            or row.get("source_member_included") is not False
            or row.get("trait_truth_included") is not False
        ):
            errors.append(f"witness result differs: {row.get('witness_id')}")
    overlap = {row.get("fixture_id"): row for row in report.get("overlap_and_contrast_cases", [])}
    expected = {
        "sparse-tonal-overlap": (2, 0.99, None),
        "sparse-nontonal-contrast": (2, None, 0.05),
        "tonal-nonsparse-contrast": (10, 0.99, None),
    }
    if set(overlap) != set(expected):
        errors.append("overlap inventory differs")
    else:
        for fixture_id, (blocks, minimum, maximum) in expected.items():
            row = overlap[fixture_id]
            share = row.get("tone_projection_share", -1)
            if row.get("active_block_count") != blocks:
                errors.append(f"active block count differs: {fixture_id}")
            if minimum is not None and share < minimum:
                errors.append(f"tone projection too low: {fixture_id}")
            if maximum is not None and share > maximum:
                errors.append(f"tone projection too high: {fixture_id}")
            if row.get("trait_truth_included") is not False:
                errors.append(f"trait truth leaked: {fixture_id}")
    candidate_rows = report.get("candidate_record_audit", [])
    if [row.get("trait_id") for row in candidate_rows] != EXPECTED_TRAITS:
        errors.append("candidate record audit differs")
    summary = report.get("summary", {})
    if summary.get("missing_explicit_candidate_traits") != ["quiet", "clipped"]:
        errors.append("missing candidate summary differs")
    for key in (
        "actual_audio_accessed",
        "source_member_selected",
        "trait_truth_included",
        "perceptual_metric_executed",
        "listener_response_collected",
        "public_verdict_enabled",
    ):
        if summary.get(key) is not False:
            errors.append(f"summary {key} must be false")
    decision = report.get("decision", {})
    for key in (
        "quiet_candidate_identified",
        "naturally_clipped_candidate_identified",
        "exact_source_trait_members_frozen",
        "source_trait_scientific_coverage_complete",
        "human_truth_present",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision {key} must be false")
    claims = report.get("claim_boundary")
    if not isinstance(claims, dict) or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
                "witness_count": report["summary"]["non_identifiability_witness_count"],
                "replays_byte_identical": report["replay_observation"]["byte_identical"],
                "actual_audio_accessed": report["summary"]["actual_audio_accessed"],
                "source_members_frozen": report["decision"]["exact_source_trait_members_frozen"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
