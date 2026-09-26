from __future__ import annotations

import copy
import importlib.util
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_perceptual_target_semantics.py"
SPEC = importlib.util.spec_from_file_location("target_semantics", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PerceptualTargetSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = MODULE.build_synthetic_report()
        listening = MODULE._module("listening_implementation")
        cls.listening = listening.analyse(listening.synthetic_dataset())

    def test_existing_listening_estimates_keep_their_unit_and_interval(self) -> None:
        source = {item["analysis_group_id"]: item for item in self.listening["primary_groups"]}
        for target in self.report["baseline_targets"]:
            model = source[target["synthetic_analysis_group"]]["audibility"]
            self.assertEqual(model["estimate"], target["correct_response_probability"])
            self.assertEqual([model["lower"], model["upper"]], target["correct_response_probability_interval"])
            self.assertEqual(MODULE.SCOPE, target["probability_scope"])
            self.assertIsNone(target["population_marginal_correct_response_probability"])
            self.assertIsNone(target["audible_condition_probability"])
            self.assertFalse(target["per_source_evaluation_eligible"])
            self.assertFalse(target["scientific_truth_eligible"])

    def test_transparent_response_probability_does_not_become_class_probability(self) -> None:
        transparent = next(item for item in self.report["baseline_targets"] if item["synthetic_analysis_group"] == "group-transparent")
        self.assertGreater(transparent["correct_response_probability"], 0.45)
        self.assertLess(transparent["correct_response_probability"], 0.55)
        self.assertEqual("chance_equivalent", transparent["audibility_evidence_state"])
        self.assertIs(False, transparent["audible_condition_label"])
        self.assertIsNone(transparent["audible_condition_probability"])

    def test_intermediate_synthetic_fit_preserves_unknown_label(self) -> None:
        target = self.report["intermediate_target"]
        self.assertEqual("indeterminate", target["audibility_evidence_state"])
        self.assertIsNone(target["audible_condition_label"])
        self.assertGreater(target["correct_response_probability"], 0.55)
        self.assertLess(target["correct_response_probability"], 0.75)

    def test_analytic_brier_witness_matches_irreducible_response_uncertainty(self) -> None:
        witness = self.report["semantic_witnesses"]
        self.assertEqual(0.25, witness["response_brier_at_chance"])
        self.assertEqual(0.25, witness["legacy_class_brier_using_response_probability"])
        self.assertEqual(0.0, witness["class_brier_using_correct_class_probability"])
        self.assertEqual(0.5, witness["legacy_class_ece_using_response_probability"])
        self.assertGreater(witness["response_brier_at_chance"], witness["legacy_class_brier_ceiling"])
        self.assertTrue(witness["legacy_boolean_schema_accepts_all_false_labels"])
        self.assertFalse(witness["all_false_labels_establish_indeterminate_truth"])
        self.assertFalse(witness["gate_transferred_to_response_scoring"])

    def test_missing_probability_is_unknown_not_zero(self) -> None:
        report = copy.deepcopy(self.listening)
        report["primary_groups"][0]["audibility"] = None
        targets = MODULE.project_synthetic_analysis(report)
        first = targets[0]
        self.assertIsNone(first["correct_response_probability"])
        self.assertIsNone(first["correct_response_probability_interval"])
        self.assertIsNone(first["audible_condition_label"])

    def test_observed_or_scientific_report_rejected(self) -> None:
        for field in ("scientific_gate_evaluated", "human_collection_authorized", "human_responses_observed"):
            with self.subTest(field=field):
                report = copy.deepcopy(self.listening)
                report[field] = True
                with self.assertRaises(ValueError):
                    MODULE.project_synthetic_analysis(report)
        report = copy.deepcopy(self.listening)
        report["fixture_only"] = False
        with self.assertRaises(ValueError):
            MODULE.project_synthetic_analysis(report)

    def test_malformed_probability_state_interval_and_provenance_rejected(self) -> None:
        for field, value in (("estimate", math.nan), ("estimate", math.inf), ("estimate", True), ("lower", 0.99), ("state", "false"), ("converged", False)):
            with self.subTest(field=field, value=value):
                report = copy.deepcopy(self.listening)
                report["primary_groups"][0]["audibility"][field] = value
                with self.assertRaises(ValueError):
                    MODULE.project_synthetic_analysis(report)
        for field in ("analysis_plan_sha256", "implementation_sha256"):
            report = copy.deepcopy(self.listening)
            report[field] = "0" * 64
            with self.assertRaises(ValueError):
                MODULE.project_synthetic_analysis(report)

    def test_state_cannot_promote_uncertain_or_transparent_evidence(self) -> None:
        report = copy.deepcopy(self.listening)
        transparent = next(item for item in report["primary_groups"] if item["analysis_group_id"] == "group-transparent")
        transparent["audibility"]["state"] = "audible"
        with self.assertRaisesRegex(ValueError, "conflicts with frozen decision rule"):
            MODULE.project_synthetic_analysis(report)
        transparent["audibility"]["state"] = "not_demonstrably_audible"
        transparent["audibility"]["responses"] = 1
        with self.assertRaisesRegex(ValueError, "conflicts with frozen decision rule"):
            MODULE.project_synthetic_analysis(report)

    def test_duplicate_unknown_or_non_development_groups_rejected(self) -> None:
        report = copy.deepcopy(self.listening)
        report["primary_groups"].append(copy.deepcopy(report["primary_groups"][0]))
        with self.assertRaises(ValueError):
            MODULE.project_synthetic_analysis(report)
        for field, value in (("analysis_group_id", "group-unknown"), ("partition", "final_validation")):
            report = copy.deepcopy(self.listening)
            report["primary_groups"][0][field] = value
            with self.assertRaises(ValueError):
                MODULE.project_synthetic_analysis(report)

    def test_replay_is_byte_identical_and_contains_no_live_evidence(self) -> None:
        self.assertEqual(MODULE.canonical_bytes(self.report), MODULE.canonical_bytes(MODULE.build_synthetic_report()))
        evidence = ROOT / "research/toolchains/evidence/perceptual-degradation-target-semantics-synthetic-20260905-001.json"
        self.assertEqual(MODULE.canonical_bytes(self.report), evidence.read_bytes())
        self.assertFalse(self.report["scientific_gate_evaluated"])
        self.assertFalse(self.report["human_responses_observed"])
        self.assertFalse(self.report["full_reference_oracle_validated"])
        self.assertFalse(self.report["objective_complete"])
        for marker in (b"participant-", b"session-", b"/Users/", b".wav", b"forced_choice_correct"):
            self.assertNotIn(marker, MODULE.canonical_bytes(self.report))

    def test_plan_cannot_open_observed_access_or_redirect_a_binding(self) -> None:
        original = json.loads(MODULE.PLAN.read_text())
        mutations = (
            ("access_boundary", "observed_response_input_authorized", True),
            ("access_boundary", "synthetic_response_analysis_authorized", 1),
            ("target_contract", "indeterminate_audibility_label", False),
            ("target_contract", "analysis_group_to_per_source_label_broadcast_allowed", True),
            ("target_contract", "legacy_brier_ece_auc_gate_transfer_to_response_target_allowed", True),
        )
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                plan = copy.deepcopy(original)
                plan[section][key] = value
                with mock.patch.object(MODULE.json, "loads", return_value=plan):
                    with self.assertRaises(ValueError):
                        MODULE.load_plan()
        plan = copy.deepcopy(original)
        plan["bindings"]["research_contract"]["path"] = "unopened.json"
        with mock.patch.object(MODULE.json, "loads", return_value=plan):
            with self.assertRaisesRegex(ValueError, "binding path differs"):
                MODULE.load_plan()

    def test_cli_has_no_observed_data_input(self) -> None:
        for args in ([], ["--input", "unopened.json"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"", result.stdout)


if __name__ == "__main__":
    unittest.main()
