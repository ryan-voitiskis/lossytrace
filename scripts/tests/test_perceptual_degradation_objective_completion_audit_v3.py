from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v3.py"
PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "objective-completion-audit-plan-20260814-003.json"
)
REPORT = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-objective-completion-audit-20260814-003.json"
)
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v3", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ObjectiveCompletionAuditV3Test(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))

    def test_report_is_deterministic_and_still_incomplete(self) -> None:
        first = MODULE.build_report(plan())
        second = MODULE.build_report(plan())
        self.assertEqual(first, second)
        self.assertFalse(first["summary"]["objective_complete"])
        self.assertEqual(14, first["summary"]["requirement_count"])
        self.assertEqual(4, first["summary"]["satisfied_count"])
        self.assertEqual(10, first["summary"]["unsatisfied_count"])

    def test_committed_report_is_exact_replay(self) -> None:
        expected = MODULE.canonical_json_bytes(MODULE.build_report(plan()))
        self.assertEqual(expected, REPORT.read_bytes())

    def test_provider_route_is_not_promoted_to_quiet_or_clipped_candidate(self) -> None:
        report = MODULE.build_report(plan())
        self.assertTrue(report["summary"]["quiet_provider_capability_route_found"])
        self.assertFalse(report["summary"]["quiet_candidate_identified"])
        self.assertFalse(report["summary"]["naturally_clipped_candidate_identified"])
        self.assertFalse(report["summary"]["source_trait_manifest_frozen"])
        self.assertEqual(7, report["summary"]["required_source_trait_count"])
        self.assertEqual(5, report["summary"]["source_trait_candidate_record_count"])

    def test_source_and_negative_requirements_remain_incomplete(self) -> None:
        requirements = {
            item["requirement_id"]: item for item in MODULE.build_report(plan())["requirements"]
        }
        source = requirements["truth_bearing_source_manifest_feasible_and_frozen"]
        negatives = requirements[
            "difficult_natural_and_production_negatives_preserved_in_evaluation"
        ]
        self.assertEqual(
            "arithmetic_feasible_trait_candidates_incomplete_exact_manifest_unfrozen",
            source["state"],
        )
        self.assertFalse(source["satisfied"])
        self.assertEqual(
            "proof_contract_ready_candidate_coverage_incomplete_not_evaluated",
            negatives["state"],
        )
        self.assertFalse(negatives["satisfied"])

    def test_selected_resampler_is_not_promoted_to_integration_or_oracle_pass(self) -> None:
        report = MODULE.build_report(plan())
        self.assertTrue(report["summary"]["oracle_drift_resampler_selected"])
        self.assertFalse(report["summary"]["oracle_drift_resampler_integrated"])
        self.assertFalse(
            report["evidence_checks"]["oracle_drift_resampler_integration_authorized"]
        )
        self.assertFalse(
            report["evidence_checks"]["legacy_metric_rate_conversion_is_drift_integration"]
        )
        oracle = next(
            item
            for item in report["requirements"]
            if item["requirement_id"]
            == "deterministic_human_calibrated_full_reference_oracle_passed"
        )
        self.assertEqual(
            "technical_resampler_frozen_integration_and_scientific_validation_closed",
            oracle["state"],
        )
        self.assertFalse(oracle["satisfied"])

    def test_authority_and_promotion_policies_fail_closed(self) -> None:
        value = plan()
        value["authorization"]["exact_member_metadata_audit_authorized"] = True
        value["authorization"]["drift_resampler_integration_authorized"] = True
        value["authorization"]["perceptual_metric_execution_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(value))

        value = plan()
        value["completion_policy"][
            "provider_capability_counts_as_exact_trait_candidate"
        ] = True
        value["completion_policy"]["frozen_resampler_counts_as_oracle_integration"] = True
        value["completion_policy"][
            "legacy_metric_rate_conversion_counts_as_drift_integration"
        ] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(value))

    def test_only_contract_and_safety_boundaries_are_satisfied(self) -> None:
        report = MODULE.build_report(plan())
        satisfied = {
            item["requirement_id"]
            for item in report["requirements"]
            if item["satisfied"]
        }
        self.assertEqual(
            {
                "estimand_is_degradation_not_history",
                "declared_playback_chain_qualified",
                "public_cli_remains_verdict_free",
                "rigorous_negative_is_accepted_success",
            },
            satisfied,
        )
        self.assertFalse(report["no_reference_training_performed"])
        self.assertFalse(report["public_verdict_enabled"])


if __name__ == "__main__":
    unittest.main()
