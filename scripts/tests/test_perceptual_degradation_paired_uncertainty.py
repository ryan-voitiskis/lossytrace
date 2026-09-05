from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import math
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_paired_uncertainty.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-paired-uncertainty-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("paired_uncertainty", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PairedUncertaintyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_plan()
        cls.experiment = cls.plan["experiment"]
        cls.analysis = MODULE.load_module("analysis")
        cls.paired = MODULE.load_module("paired")
        cls.decisions = MODULE.load_module("decisions")
        cls.response = staticmethod(MODULE.response_factory(cls.paired))

    def scenario(self, name):
        return next(item for item in self.experiment["scenarios"] if item["id"] == name)

    def simulate(self, name="matched", count=4):
        return MODULE.simulate_case(self.experiment, self.scenario(name), count, self.analysis, self.decisions, self.response)

    def test_generating_distributions_have_exact_declared_moments(self):
        distributions = MODULE.generating_distributions(self.experiment)
        for values, expected in zip(distributions, (.25**2, .3**2, .5**2), strict=True):
            self.assertAlmostEqual(1, sum(values.values()))
            self.assertAlmostEqual(0, sum(x*p for x, p in values.items()))
            self.assertAlmostEqual(expected, MODULE.variance(values)/100)

    def test_distribution_input_rejects_malformed_or_duplicate_values(self):
        for values in ([], None, [[True, 1]], [[0, True]], [[0, 0]], [[0, -1]], [[0, 1], [0, 2]], [[0]], [[0, 1.5]]):
            with self.assertRaises(ValueError):
                MODULE.distribution(values)

    def test_convolution_matches_independent_brute_force(self):
        values = {-1: .5, 1: .5}
        brute = Counter(sum(items) for items in itertools.product((-1, 1), repeat=4))
        expected = {value: count/16 for value, count in sorted(brute.items())}
        self.assertEqual(expected, MODULE.repeated_sum(values, 4))
        self.assertEqual({0: 1}, MODULE.repeated_sum(values, 0))
        self.assertEqual({0: 1}, MODULE.repeated_sum(values, 4, 0))
        for count, scale in ((True, 1), (-1, 1), (1, -1), (1, 1.5)):
            with self.assertRaises(ValueError):
                MODULE.repeated_sum(values, count, scale)

    def test_finite_discrete_coverage_matches_tiny_enumeration(self):
        experiment = copy.deepcopy(self.experiment)
        experiment["listeners"], experiment["sources"] = 2, 1
        for name in ("listener", "source", "residual"):
            experiment[name + "_ticks_and_integer_weights"] = [[-1, 1], [1, 1]]
        scenario = {"scales": [1, 1, 1], "missingness": "none"}
        result = MODULE.exact_complete_case(experiment, scenario, 1)
        half_width = math.sqrt(.01/2 + .01 + .01/2)
        covered = 0
        for a, b, s, x, y in itertools.product((-1, 1), repeat=5):
            covered += abs((a+b+2*s+x+y)/20) <= half_width
        self.assertAlmostEqual(covered/32, result["enumerated_central_coverage"])
        self.assertAlmostEqual(1, result["probability_mass"])

    def test_complete_population_enumeration_preserves_variance_stress(self):
        matched = MODULE.exact_complete_case(self.experiment, self.scenario("matched"), self.analysis.Z_THRESHOLD)
        doubled = MODULE.exact_complete_case(self.experiment, self.scenario("all_sd_x2"), self.analysis.Z_THRESHOLD)
        self.assertEqual(matched["model_standard_error"], doubled["model_standard_error"])
        self.assertAlmostEqual(2*matched["true_standard_error"], doubled["true_standard_error"])
        self.assertGreater(matched["enumerated_central_coverage"], .96)
        self.assertLess(doubled["enumerated_central_coverage"], .8)
        self.assertIsNone(MODULE.exact_complete_case(self.experiment, self.scenario("outcome_dependent_missing"), self.analysis.Z_THRESHOLD))

    def test_legacy_multiplier_has_central_975_not_95_percent_coverage(self):
        coverage = 2*NormalDist().cdf(self.analysis.Z_THRESHOLD)-1
        self.assertAlmostEqual(.975, coverage, places=10)
        self.assertNotAlmostEqual(.95, coverage)

    def test_generated_panels_are_repeatable_bounded_and_all_assigned(self):
        for scenario in self.experiment["scenarios"]:
            panel = MODULE.generated_panel(self.experiment, scenario, 0)
            self.assertEqual(panel, MODULE.generated_panel(self.experiment, scenario, 0))
            self.assertEqual(288, len(panel))
            self.assertEqual(288, len({(a, b) for a, b, _, _ in panel}))
            self.assertTrue(all(type(d) is int and -40 <= d <= 40 and type(c) is bool for _, _, d, c in panel))
        self.assertNotEqual(MODULE.generated_panel(self.experiment, self.scenario("matched"), 0),
                            MODULE.generated_panel(self.experiment, self.scenario("matched"), 1))

    def test_undeclared_panel_parameters_and_boolean_scales_are_rejected(self):
        for replicate in (-1, True, 128, 1.0):
            with self.assertRaises(ValueError):
                MODULE.generated_panel(self.experiment, self.scenario("matched"), replicate)
        scenario = copy.deepcopy(self.scenario("matched"))
        scenario["scales"][0] = True
        with self.assertRaises(ValueError):
            MODULE.generated_panel(self.experiment, scenario, 0)

    def test_outcome_missingness_does_not_change_the_declared_population(self):
        panel = MODULE.generated_panel(self.experiment, self.scenario("outcome_dependent_missing"), 0)
        for _, _, difference, complete in panel:
            self.assertEqual(difference > -10, complete)
        self.assertTrue(any(not complete for *_, complete in panel))
        self.assertEqual(-10, self.experiment["population_mean_difference_ticks"])

    def test_source_missingness_is_constant_within_source(self):
        panel = MODULE.generated_panel(self.experiment, self.scenario("source_dependent_missing"), 0)
        for source in range(12):
            self.assertEqual(1, len({complete for _, s, _, complete in panel if s == source}))

    def test_independent_missingness_retains_both_directions(self):
        panel = MODULE.generated_panel(self.experiment, self.scenario("independent_missing_quarter"), 0)
        complete = [difference for _, _, difference, accepted in panel if accepted]
        missing = [difference for _, _, difference, accepted in panel if not accepted]
        self.assertTrue(complete and missing)
        self.assertLessEqual(min(complete), -10)
        self.assertLessEqual(min(missing), -10)
        self.assertGreater(max(complete), -10)
        self.assertGreater(max(missing), -10)

    def test_every_possible_signed_difference_reaches_paired_processor(self):
        for source, difference in itertools.product((0, 1), range(-40, 41)):
            result = self.response(0, source, difference, True)
            self.assertEqual(difference/10, result["paired_sdg"])
            self.assertTrue(result["complete_pair_analysis_eligible"])
            missing = self.response(0, source, difference, False)
            self.assertIsNone(missing["paired_sdg"])
            self.assertFalse(missing["complete_pair_analysis_eligible"])
        for difference, complete in ((True, True), (41, True), (-41, True), (0, 1)):
            with self.assertRaises(ValueError):
                self.response(0, 0, difference, complete)

    def test_balanced_solver_matches_independent_mean_and_variance(self):
        result = self.simulate()
        self.assertLess(result["balanced_solver_comparison"]["maximum_mean_error"], 1e-8)
        self.assertLess(result["balanced_solver_comparison"]["maximum_standard_error_error"], 1e-8)
        self.assertEqual(4, result["returned_intervals"])
        self.assertEqual([288, 288], result["complete_response_count_range"])

    def test_rate_denominators_and_boundary_uncertainty(self):
        self.assertIsNone(MODULE.rate(0, 0)["estimate"])
        self.assertIsNone(MODULE.rate(0, 0)["wilson_95_interval"])
        zero, one = MODULE.rate(0, 128), MODULE.rate(128, 128)
        self.assertGreater(zero["wilson_95_interval"][1], 0)
        self.assertLess(one["wilson_95_interval"][0], 1)
        half = MODULE.rate(64, 128)
        self.assertAlmostEqual(math.sqrt(.25/128), half["monte_carlo_standard_error"])
        for numerator, denominator in ((True, 1), (1, 0), (-1, 3), (1, 1.0)):
            with self.assertRaises(ValueError):
                MODULE.rate(numerator, denominator)

    def test_all_missing_replicates_stay_in_accounting(self):
        panel = [(a, b, d, False) for a, b, d, _ in MODULE.generated_panel(self.experiment, self.scenario("matched"), 0)]
        with mock.patch.object(MODULE, "generated_panel", return_value=panel):
            result = self.simulate()
        self.assertEqual(4, result["failures"]["no_complete_data"])
        self.assertEqual(4, result["valid_and_covers_rate"]["denominator"])
        self.assertEqual(0, result["coverage_given_returned"]["denominator"])
        self.assertIsNone(result["bias_given_returned"])
        self.assertEqual(4, result["diagnostic_severity_evidence_counts"]["indeterminate"])

    def test_known_numerical_failures_are_retained_without_resampling(self):
        for message in MODULE.NUMERICAL_FAILURES:
            with mock.patch.object(self.analysis, "_fit_gaussian", side_effect=ValueError(message)) as fitted:
                result = self.simulate()
            self.assertEqual(4, fitted.call_count)
            self.assertEqual(4, result["failures"]["numerical_failure"])
            self.assertEqual(0, result["returned_intervals"])
            self.assertEqual(4, result["valid_and_covers_rate"]["denominator"])

    def test_unrelated_errors_are_not_hidden_as_numerical_failures(self):
        with mock.patch.object(self.analysis, "_fit_gaussian", side_effect=ValueError("unrelated failure")), self.assertRaisesRegex(ValueError, "unrelated failure"):
            self.simulate()

    def test_support_conditioned_rates_are_not_total_population_coverage(self):
        result = self.simulate("source_dependent_missing")
        self.assertEqual(0, result["support_rate"]["numerator"])
        self.assertEqual(0, result["coverage_given_supported"]["denominator"])
        self.assertIsNone(result["coverage_given_supported"]["estimate"])
        self.assertEqual(4, result["coverage_given_returned"]["denominator"])

    def test_partial_fit_failure_has_explicit_different_denominators(self):
        original = self.analysis._fit_gaussian
        calls = []
        def sometimes(*args):
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("hierarchical normal equations did not converge")
            return original(*args)
        with mock.patch.object(self.analysis, "_fit_gaussian", side_effect=sometimes):
            result = self.simulate()
        self.assertEqual(4, result["valid_and_covers_rate"]["denominator"])
        self.assertEqual(3, result["coverage_given_returned"]["denominator"])
        self.assertEqual(1, result["failures"]["numerical_failure"])

    def test_reduced_smoke_is_not_the_full_audit(self):
        smoke = MODULE.build_report(1)
        self.assertEqual("reduced_synthetic_smoke_only", smoke["state"])
        self.assertEqual(1, smoke["replicates_per_scenario"])
        self.assertTrue(all(item["simulation"]["bias_monte_carlo_standard_error"] is None for item in smoke["scenarios"]))
        for value in (0, True, -1, 129, 1.0):
            with self.assertRaises(ValueError):
                MODULE.build_report(value)

    def test_plan_bytes_and_predecessors_are_frozen(self):
        with mock.patch.object(Path, "read_bytes", return_value=b"{}"), self.assertRaisesRegex(ValueError, "plan bytes"):
            MODULE.load_plan()
        with mock.patch.object(MODULE, "sha", return_value="0"*64), self.assertRaisesRegex(ValueError, "predecessor"):
            MODULE.load_plan()
        with self.assertRaises(ValueError):
            MODULE.load_module("arbitrary.py")

    def test_report_matches_full_golden_and_keeps_scientific_gates_closed(self):
        report = MODULE.build_report()
        self.assertEqual(EVIDENCE.read_bytes(), MODULE.canonical_bytes(report))
        self.assertEqual(8, len(report["scenarios"]))
        for item in report["scenarios"]:
            result = item["simulation"]
            self.assertEqual(128, result["returned_intervals"] + sum(result["failures"].values()))
            self.assertEqual(128, sum(result["diagnostic_severity_evidence_counts"].values()))
        for key in ("confidence_interval_coverage_on_humans_validated", "human_materiality_margin_selected", "audibility_coverage_evaluated",
                    "familywise_coverage_evaluated", "human_responses_observed", "oracle_truth_eligible", "no_reference_training_eligible", "objective_complete"):
            self.assertIs(False, report[key])
        encoded = MODULE.canonical_bytes(report)
        for marker in (b"/Users/", b"participant-", b"stimulus-", b".wav", b".flac"):
            self.assertNotIn(marker, encoded)

    def test_cli_exposes_no_observed_input_or_replication_tuning(self):
        for args in ([], ["--synthetic", "--input", "unopened.json"], ["--synthetic", "--replicates", "1"]):
            run = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, run.returncode)
            self.assertEqual(b"", run.stdout)


if __name__ == "__main__":
    unittest.main()
