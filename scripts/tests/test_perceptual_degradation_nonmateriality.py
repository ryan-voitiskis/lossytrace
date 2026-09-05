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
SCRIPT = ROOT / "scripts/perceptual_degradation_nonmateriality.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-nonmateriality-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("nonmateriality", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NonmaterialityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.build_synthetic_report()

    def enclosed(self, severity=None, audible=None, design="paired"):
        return MODULE.envelope(design, {
            "audibility": MODULE.example_fit(.85, .78, .92) if audible is None else audible,
            "paired_sdg": MODULE.example_fit(-.4, -.6, -.2) if severity is None else severity,
        })

    def test_nonmateriality_needs_interval_on_nonmaterial_side(self):
        for estimate, lower, upper, state in ((-.4, -.6, -.2, "nonmaterial_supported"),
                                               (-1.5, -1.8, -1.2, "material_supported"),
                                               (-1, -1.2, -.8, "indeterminate")):
            result = MODULE.evidence(MODULE.example_fit(estimate, lower, upper), "paired_sdg")
            self.assertEqual(state, result["state"])

    def test_exact_material_boundaries_are_indeterminate_in_both_directions(self):
        for family, intervals in (("paired_sdg", ((-1.2, -1.4, -1), (-.8, -1, -.6), (-1, -1, -1))),
                                  ("mushra_loss", ((12, 10, 14), (8, 6, 10), (10, 10, 10)))):
            for estimate, lower, upper in intervals:
                self.assertEqual("indeterminate", MODULE.evidence(MODULE.example_fit(estimate, lower, upper), family)["state"])

    def test_near_boundaries_are_compared_without_rounding(self):
        for boundary, direction, expected in ((-1, math.inf, "nonmaterial_supported"), (-1, -math.inf, "material_supported")):
            value = math.nextafter(boundary, direction)
            self.assertEqual(expected, MODULE.evidence(MODULE.example_fit(value, value, value), "paired_sdg")["state"])

    def test_mushra_and_paired_direction_agree_after_sign_and_scale_change(self):
        for d in (-3, -1.1, -1, -.9, 0, 1, 3):
            pair = MODULE.example_fit(d, d - .1, d + .1)
            loss = MODULE.example_fit(-10*d, -10*(d + .1), -10*(d - .1))
            self.assertEqual(MODULE.evidence(pair, "paired_sdg")["state"], MODULE.evidence(loss, "mushra_loss")["state"])

    def test_positive_paired_differences_and_unbounded_intervals_are_not_clipped(self):
        fit = MODULE.example_fit(4 + 1e-14, 3.8, 4.2)
        original = copy.deepcopy(fit)
        self.assertEqual("nonmaterial_supported", MODULE.evidence(fit, "paired_sdg")["state"])
        self.assertEqual(original, fit)
        with self.assertRaises(ValueError):
            MODULE.evidence(MODULE.example_fit(4.01, 3.8, 4.2), "paired_sdg")

    def test_legacy_diagnostic_fits_do_not_become_paired_observations(self):
        for item in self.report["legacy_generated_counterfactuals"]:
            self.assertEqual({"legacy_sdg_diagnostic"}, set(item["successor"]["severity_by_required_method"]))
        with self.assertRaises(ValueError):
            MODULE.evidence(MODULE.example_fit(.5, .2, .8), "legacy_sdg_diagnostic")

    def test_missing_insufficient_unconverged_states_are_distinct(self):
        fit = MODULE.example_fit(-.4, -.6, -.2)
        cases = [(None, "missing_estimate"), ({**fit, "listeners": 23}, "insufficient_support"),
                 ({**fit, "sources": 11}, "insufficient_support"), ({**fit, "responses": 95}, "insufficient_support"),
                 ({**fit, "converged": False}, "unconverged_estimate"),
                 ({"fit_failure": "nonconvergence"}, "unconverged_estimate")]
        for value, reason in cases:
            self.assertEqual({"state": "indeterminate", "reason": reason}, MODULE.evidence(value, "paired_sdg"))

    def test_malformed_intervals_counts_flags_and_failures_rejected(self):
        fit = MODULE.example_fit(-.4, -.6, -.2)
        for key, value in (("estimate", True), ("estimate", "-.4"), ("estimate", float("nan")),
                           ("lower", float("-inf")), ("upper", -.8), ("listeners", True), ("sources", -1),
                           ("responses", 12), ("converged", 1), ("path", "unopened")):
            with self.assertRaises(ValueError):
                MODULE.evidence({**fit, key: value}, "paired_sdg")
        for value in ([], True, {}, {"fit_failure": "other"}, {"fit_failure": "nonconvergence", "estimate": 0}):
            with self.assertRaises(ValueError):
                MODULE.evidence(value, "paired_sdg")
        with self.assertRaises(ValueError):
            MODULE.evidence(fit, "codec")

    def test_probability_range_and_equivalence_boundaries_are_strict(self):
        for lower, upper, state in ((.46, .54, "chance_equivalent"), (.45, .54, "indeterminate"),
                                    (.46, .55, "indeterminate"), (.4, .6, "indeterminate")):
            self.assertEqual(state, MODULE.evidence(MODULE.example_fit(.5, lower, upper), "audibility")["state"])
        for lower, upper in ((-.1, .6), (.4, 1.1)):
            with self.assertRaises(ValueError):
                MODULE.evidence(MODULE.example_fit(.5, lower, upper), "audibility")

    def test_summary_requires_both_axes_and_preserves_null(self):
        unresolved = MODULE.evaluate_synthetic(self.enclosed(MODULE.example_fit(-1, -1.2, -.8)))
        self.assertEqual("indeterminate", unresolved["synthetic_research_summary"])
        self.assertIsNone(unresolved["material_condition_label"])
        nonmaterial = MODULE.evaluate_synthetic(self.enclosed())
        self.assertEqual("audible_nonmaterial", nonmaterial["synthetic_research_summary"])
        self.assertIs(False, nonmaterial["material_condition_label"])
        material = MODULE.evaluate_synthetic(self.enclosed(MODULE.example_fit(-1.5, -1.8, -1.2)))
        self.assertEqual("materially_degraded", material["synthetic_research_summary"])
        self.assertIs(True, material["material_condition_label"])

    def test_nonmateriality_alone_does_not_establish_transparency(self):
        unresolved = MODULE.evaluate_synthetic(self.enclosed(audible=MODULE.example_fit(.5, .4, .6)))
        self.assertEqual("nonmaterial_supported", unresolved["severity_evidence_state"])
        self.assertEqual("indeterminate", unresolved["synthetic_research_summary"])
        transparent = MODULE.evaluate_synthetic(self.enclosed(audible=MODULE.example_fit(.5, .46, .54)))
        self.assertEqual("transparent", transparent["synthetic_research_summary"])

    def test_chance_equivalence_and_materiality_conflict_abstains(self):
        result = MODULE.evaluate_synthetic(self.enclosed(MODULE.example_fit(-1.5, -1.8, -1.2), MODULE.example_fit(.5, .46, .54)))
        self.assertTrue(result["detectability_severity_conflict"])
        self.assertEqual("indeterminate", result["synthetic_research_summary"])

    def test_bridge_missing_method_cannot_be_silently_dropped(self):
        enclosed = self.enclosed(design="bridge")
        with self.assertRaises(ValueError):
            MODULE.evaluate_synthetic(enclosed)
        enclosed["models"]["mushra_loss"] = None
        result = MODULE.evaluate_synthetic(enclosed)
        self.assertEqual("indeterminate", result["severity_evidence_state"])
        self.assertIsNone(result["material_condition_label"])

    def test_bridge_unresolved_is_not_explicit_conflict(self):
        models = {"audibility": MODULE.example_fit(.85, .78, .92), "paired_sdg": MODULE.example_fit(-1.5, -1.8, -1.2),
                  "mushra_loss": MODULE.example_fit(10, 8, 12)}
        result = MODULE.evaluate_synthetic(MODULE.envelope("bridge", models))
        self.assertEqual("indeterminate", result["severity_evidence_state"])
        models["mushra_loss"] = MODULE.example_fit(4, 2, 6)
        self.assertEqual("discordant", MODULE.evaluate_synthetic(MODULE.envelope("bridge", models))["severity_evidence_state"])

    def test_full_bridge_truth_table_requires_agreement(self):
        grid = MODULE.decision_grid()
        self.assertEqual(48, len(grid))
        for row in grid:
            a, s, m = row["detectability_case"], row["paired_case"], row["mushra_case"]
            expected = "indeterminate"
            if a == "audible" and s == m == "material":
                expected = "materially_degraded"
            if a == "audible" and s == m == "nonmaterial":
                expected = "audible_nonmaterial"
            if a == "chance_equivalent" and s == m == "nonmaterial":
                expected = "transparent"
            self.assertEqual(expected, row["result"]["synthetic_research_summary"])

    def test_model_and_method_order_do_not_change_result(self):
        value = self.enclosed(design="bridge")
        value["models"]["mushra_loss"] = MODULE.example_fit(4, 2, 6)
        result = MODULE.evaluate_synthetic(value)
        value["models"] = dict(reversed(list(value["models"].items())))
        self.assertEqual(result, MODULE.evaluate_synthetic(value))

    def test_observed_input_source_labels_and_unknown_methods_rejected(self):
        for key, value in (("state", "observed"), ("fixture_only", 1), ("scientific_truth_eligible", True),
                           ("analysis_unit", "per_source_pair"), ("model_scope", "population_marginal"),
                           ("design", "automatic"), ("design", []), ("path", "unopened")):
            enclosed = self.enclosed()
            enclosed[key] = value
            with self.assertRaises(ValueError):
                MODULE.evaluate_synthetic(enclosed)
        enclosed = self.enclosed()
        enclosed["models"]["metric_score"] = 5
        with self.assertRaises(ValueError):
            MODULE.evaluate_synthetic(enclosed)

    def test_real_legacy_classifier_reproduces_both_unsafe_fallthroughs(self):
        cases = self.report["legacy_generated_counterfactuals"]
        self.assertEqual({"transparent", "audible_nonmaterial"}, {item["legacy_summary"] for item in cases})
        for item in cases:
            self.assertLess(item["legacy_sdg_interval"][0], -1)
            self.assertGreater(item["legacy_sdg_interval"][1], -1)
            self.assertEqual("indeterminate", item["successor"]["synthetic_research_summary"])

    def test_paired_integration_preserves_range_missingness_and_solver_failure(self):
        cases = {item["synthetic_scenario"]: item for item in self.report["paired_numerical_integration"]}
        self.assertEqual(6, len(cases))
        self.assertEqual(-1, cases["common-offset"]["paired_fit"]["estimate"])
        self.assertEqual("indeterminate", cases["common-offset"]["result"]["severity_evidence_state"])
        positive = cases["positive-difference"]
        self.assertEqual(4, positive["paired_fit"]["estimate"])
        self.assertGreater(positive["paired_fit"]["upper"], 4)
        self.assertEqual({"fit_failure": "nonconvergence"}, positive["correct_response_fit"])
        self.assertEqual("indeterminate", positive["result"]["synthetic_research_summary"])
        missing = cases["half-complete"]
        self.assertEqual((144, 144, 12), (missing["complete_pairs"], missing["incomplete_pairs"], missing["paired_fit"]["listeners"]))
        self.assertEqual("insufficient_support", missing["result"]["severity_by_required_method"]["paired_sdg"]["reason"])

    def test_plan_and_bindings_are_fail_closed(self):
        original = json.loads(MODULE.PLAN.read_text())
        for section, key, value in (("access_boundary", "human_collection_authorized", True),
                                    ("access_boundary", "synthetic_execution_only", 1),
                                    ("execution", "workers", 6),
                                    ("decision_contract", "scientific_thresholds_selected", True),
                                    ("diagnostic_coordinates", "paired_sdg_material_boundary", -.5)):
            plan = copy.deepcopy(original)
            plan[section][key] = value
            with mock.patch.object(MODULE.json, "loads", return_value=plan), self.assertRaises(ValueError):
                MODULE.load_plan()
        for key, value in (("path", "unopened.py"), ("sha256", "0" * 64)):
            plan = copy.deepcopy(original)
            plan["bindings"]["analysis"][key] = value
            with mock.patch.object(MODULE.json, "loads", return_value=plan), self.assertRaises(ValueError):
                MODULE.load_plan()

    def test_numerical_failure_handler_does_not_swallow_other_errors(self):
        analysis = MODULE.module("analysis")
        paired = MODULE.module("paired")
        with mock.patch.object(analysis, "_fit_logistic", side_effect=ValueError("unrelated failure")), self.assertRaisesRegex(ValueError, "unrelated failure"):
            MODULE.paired_integration(analysis, paired)

    def test_report_is_exact_repeatable_aggregate_and_never_scientific_truth(self):
        encoded = MODULE.canonical_bytes(self.report)
        self.assertEqual(encoded, MODULE.canonical_bytes(MODULE.build_synthetic_report()))
        self.assertEqual(encoded, EVIDENCE.read_bytes())
        for field in ("legacy_evidence_reclassified", "scientific_thresholds_selected", "interval_coverage_validated",
                      "human_responses_observed", "oracle_truth_eligible", "per_source_evaluation_eligible", "objective_complete"):
            self.assertIs(False, self.report[field])
        for marker in (b"/Users/", b"participant-", b"stimulus-", b".wav", b".flac"):
            self.assertNotIn(marker, encoded)

    def test_cli_has_no_observed_input_or_output_path_option(self):
        for args in ([], ["--synthetic", "--input", "unopened.json"], ["--synthetic", "--output", "unopened.json"]):
            run = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, run.returncode)
            self.assertEqual(b"", run.stdout)


if __name__ == "__main__":
    unittest.main()
