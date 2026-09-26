#!/usr/bin/env python3
"""Deterministic score-blind power simulation for listening-study design."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import NormalDist
from typing import Any


SIMULATION_SEED = "lossytrace-perceptual-listening-power-v1-20260803"
DEFAULT_REPLICATES = 20_000
ALPHA = 0.05
MULTIPLICITY_FAMILIES = 4
AUDIBILITY_EQUIVALENCE = (0.45, 0.55)
AUDIBILITY_POINT_GATE = 0.75
SDG_MATERIAL_THRESHOLD = -1.0
MUSHRA_LOSS_MATERIAL_THRESHOLD = 10.0
LISTENER_LOGIT_SD = 0.45
SOURCE_LOGIT_SD = 0.35
SDG_LISTENER_SD = 0.25
SDG_SOURCE_SD = 0.30
SDG_RESIDUAL_SD = 0.50
MUSHRA_LISTENER_SD = 4.0
MUSHRA_SOURCE_SD = 5.0
MUSHRA_RESIDUAL_SD = 8.0
DESIGNS = (
    {"design_id": "d24-s12-j4", "design_class": "candidate", "listeners": 24, "sources": 12, "judgements_per_listener": 4},
    {"design_id": "d48-s24-j8", "design_class": "candidate", "listeners": 48, "sources": 24, "judgements_per_listener": 8},
    {"design_id": "d72-s36-j12", "design_class": "candidate", "listeners": 72, "sources": 36, "judgements_per_listener": 12},
    {"design_id": "d96-s48-j12", "design_class": "candidate", "listeners": 96, "sources": 48, "judgements_per_listener": 12},
    {"design_id": "d240-s120-j15", "design_class": "feasibility_stress", "listeners": 240, "sources": 120, "judgements_per_listener": 15},
)


def seed_integer(seed: str) -> int:
    return int(hashlib.sha256(seed.encode()).hexdigest(), 16)


def z_threshold() -> float:
    return NormalDist().inv_cdf(1 - ALPHA / MULTIPLICITY_FAMILIES)


def _probability_se(p: float, design: dict[str, Any]) -> float:
    listeners = design["listeners"]
    sources = design["sources"]
    observations = listeners * design["judgements_per_listener"]
    slope = p * (1 - p)
    variance = (
        (slope * LISTENER_LOGIT_SD) ** 2 / listeners
        + (slope * SOURCE_LOGIT_SD) ** 2 / sources
        + p * (1 - p) / observations
    )
    return math.sqrt(variance)


def _continuous_se(
    design: dict[str, Any], listener_sd: float, source_sd: float, residual_sd: float
) -> float:
    observations = design["listeners"] * design["judgements_per_listener"]
    variance = (
        listener_sd**2 / design["listeners"]
        + source_sd**2 / design["sources"]
        + residual_sd**2 / observations
    )
    return math.sqrt(variance)


def _rate(successes: int, replicates: int) -> float:
    return round(successes / replicates, 6)


def simulate_design(
    design: dict[str, Any], *, replicates: int, seed: str = SIMULATION_SEED
) -> dict[str, Any]:
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    rng = random.Random(seed_integer(seed + "\0" + design["design_id"]))
    z = z_threshold()
    audibility = []
    for truth in (0.50, 0.65, 0.75, 0.80, 0.85):
        se = _probability_se(truth, design)
        audible = equivalent = 0
        for _ in range(replicates):
            estimate = min(1.0, max(0.0, rng.gauss(truth, se)))
            lower = estimate - z * se
            upper = estimate + z * se
            audible += lower > 0.5 and estimate >= AUDIBILITY_POINT_GATE
            equivalent += (
                lower > AUDIBILITY_EQUIVALENCE[0]
                and upper < AUDIBILITY_EQUIVALENCE[1]
            )
        audibility.append(
            {
                "truth_probability": truth,
                "planning_standard_error": round(se, 8),
                "audible_gate_power": _rate(audible, replicates),
                "chance_equivalence_power": _rate(equivalent, replicates),
            }
        )

    sdg_se = _continuous_se(
        design, SDG_LISTENER_SD, SDG_SOURCE_SD, SDG_RESIDUAL_SD
    )
    sdg = []
    for truth in (-0.75, -1.0, -1.25, -1.5):
        material = 0
        for _ in range(replicates):
            estimate = rng.gauss(truth, sdg_se)
            material += estimate + z * sdg_se < SDG_MATERIAL_THRESHOLD
        sdg.append(
            {
                "truth_mean_sdg": truth,
                "planning_standard_error": round(sdg_se, 8),
                "material_severity_power": _rate(material, replicates),
            }
        )

    mushra_se = _continuous_se(
        design, MUSHRA_LISTENER_SD, MUSHRA_SOURCE_SD, MUSHRA_RESIDUAL_SD
    )
    mushra = []
    for truth in (5.0, 10.0, 15.0, 20.0):
        material = 0
        for _ in range(replicates):
            estimate = rng.gauss(truth, mushra_se)
            material += estimate - z * mushra_se > MUSHRA_LOSS_MATERIAL_THRESHOLD
        mushra.append(
            {
                "truth_mean_loss_points": truth,
                "planning_standard_error": round(mushra_se, 8),
                "material_severity_power": _rate(material, replicates),
            }
        )
    return {
        **design,
        "total_judgements_per_aggregate_stratum": design["listeners"]
        * design["judgements_per_listener"],
        "audibility": audibility,
        "sdg_severity": sdg,
        "mushra_loss_severity": mushra,
    }


def build_report(replicates: int = DEFAULT_REPLICATES) -> dict[str, Any]:
    results = [simulate_design(item, replicates=replicates) for item in DESIGNS]
    def equivalence_power(item: dict[str, Any]) -> float:
        return next(
            row["chance_equivalence_power"]
            for row in item["audibility"]
            if row["truth_probability"] == 0.5
        )

    candidate_powers = [
        equivalence_power(item)
        for item in results
        if item["design_class"] == "candidate"
    ]
    stress_powers = [
        equivalence_power(item)
        for item in results
        if item["design_class"] == "feasibility_stress"
    ]
    return {
        "schema_version": 1,
        "report_id": "perceptual-degradation-listening-power-20260803-001",
        "state": "score_blind_design_simulation_no_listener_count_frozen",
        "simulation_seed": SIMULATION_SEED,
        "replicates_per_design_and_truth": replicates,
        "observed_audio_scores_or_listener_responses_used": False,
        "multiplicity": {
            "family_count": MULTIPLICITY_FAMILIES,
            "familywise_alpha": ALPHA,
            "one_sided_normal_threshold": round(z_threshold(), 10),
        },
        "planning_model": {
            "audibility": "logit_scale_listener_and_source_random_intercepts_plus_binomial_residual",
            "severity": "listener_and_source_random_intercepts_plus_continuous_residual",
            "analysis_approximation": "known_design_variance_normal_interval_for_power_planning_only",
            "final_analysis_substitute": False,
        },
        "frozen_targets": {
            "audibility_chance": 0.5,
            "audibility_point_gate": AUDIBILITY_POINT_GATE,
            "audibility_equivalence_interval": list(AUDIBILITY_EQUIVALENCE),
            "sdg_material_threshold": SDG_MATERIAL_THRESHOLD,
            "mushra_loss_material_threshold": MUSHRA_LOSS_MATERIAL_THRESHOLD,
        },
        "design_results": results,
        "decision": {
            "listener_count_frozen": False,
            "main_collection_authorized": False,
            "equivalence_power_target": 0.8,
            "maximum_candidate_equivalence_power": max(candidate_powers),
            "maximum_stress_equivalence_power": max(stress_powers),
            "candidate_equivalence_target_met": max(candidate_powers) >= 0.8,
            "stress_equivalence_target_met": max(stress_powers) >= 0.8,
            "operationally_feasible_design_identified": False,
            "reason": "The equivalence target is unattainable in all candidate designs. The feasibility-stress design is not an operational proposal because it requires 240 trained listeners, 120 source groups, and 3,600 judgments for each transparent aggregate stratum.",
            "authorized_next_step": "Expand score-blind source and allocation design or preregister a scientifically justified aggregate transparent stratum; do not relax the equivalence interval after outcomes are opened.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.replicates)
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "candidate_equivalence_target_met": report["decision"][
                    "candidate_equivalence_target_met"
                ],
                "maximum_candidate_equivalence_power": report["decision"][
                    "maximum_candidate_equivalence_power"
                ],
                "maximum_stress_equivalence_power": report["decision"][
                    "maximum_stress_equivalence_power"
                ],
                "status": report["state"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
