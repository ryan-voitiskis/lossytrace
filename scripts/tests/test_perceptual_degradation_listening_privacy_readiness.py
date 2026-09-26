from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_listening_privacy_readiness.py"
PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "listening-privacy-readiness-audit-plan.json"
)
REPORT = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-listening-privacy-readiness-20260814-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_privacy_readiness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ListeningPrivacyReadinessTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))

    def test_report_is_deterministic_and_exactly_committed(self) -> None:
        first = MODULE.build_report(plan())
        second = MODULE.build_report(plan())
        self.assertEqual(first, second)
        self.assertEqual([], MODULE.validate_report(first))
        self.assertEqual(MODULE.canonical_bytes(first), REPORT.read_bytes())

    def test_linkable_participant_codes_are_pseudonymous_not_deidentified(self) -> None:
        report = MODULE.build_report(plan())
        classification = report["response_data_classification"]
        self.assertTrue(classification["participant_code_present"])
        self.assertTrue(classification["cross_record_linkage_present"])
        self.assertEqual(
            "pseudonymous_research_response_data", classification["classification"]
        )
        self.assertFalse(classification["deidentified_or_anonymous"])
        self.assertTrue(classification["successor_must_not_call_linkable_data_deidentified"])

    def test_schema_and_local_player_are_minimized_but_not_operational_approval(self) -> None:
        report = MODULE.build_report(plan())
        observations = report["structural_observations"]
        self.assertTrue(observations["response_schema_closed_world"])
        self.assertEqual([], observations["forbidden_direct_identifier_fields_present"])
        self.assertEqual([], observations["local_player_forbidden_api_tokens_present"])
        self.assertTrue(
            report["decision"]["data_minimization_structure_ready_for_successor_design"]
        )
        self.assertFalse(report["decision"]["privacy_package_operationally_ready"])

    def test_operational_values_and_collection_remain_closed(self) -> None:
        report = MODULE.build_report(plan())
        self.assertEqual(10, len(report["operational_fields"]))
        self.assertTrue(all(value is None for value in report["operational_fields"].values()))
        for key in (
            "response_storage_authorized",
            "human_collection_authorized",
            "no_reference_work_eligible",
            "public_verdict_enabled",
        ):
            self.assertFalse(report["decision"][key])

    def test_authority_and_classification_promotion_fail_closed(self) -> None:
        value = plan()
        value["authorization"]["response_storage_authorized"] = True
        value["authorization"]["human_collection_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(value))

        value = plan()
        value["privacy_classification_policy"][
            "pseudonymous_response_data_is_deidentified"
        ] = True
        self.assertIn(
            "privacy classification policy differs", MODULE.validate_plan(value)
        )

    def test_mutated_report_cannot_claim_readiness_or_collection(self) -> None:
        report = MODULE.build_report(plan())
        report["response_data_classification"]["deidentified_or_anonymous"] = True
        report["operational_fields"]["responsible_researcher_and_contact"] = "set"
        report["decision"]["privacy_package_operationally_ready"] = True
        report["decision"]["human_collection_authorized"] = True
        errors = MODULE.validate_report(report)
        self.assertIn("response data classification differs", errors)
        self.assertIn("operational fields must remain unresolved", errors)
        self.assertIn(
            "decision must remain false: privacy_package_operationally_ready", errors
        )
        self.assertIn("decision must remain false: human_collection_authorized", errors)


if __name__ == "__main__":
    unittest.main()
