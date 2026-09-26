from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import random
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_paired_resampling.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-paired-resampling-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("paired_resampling", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ResamplingStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = M.load_plan()
        cls.experiment = cls.plan["experiment"]
        cls.engine = M.load_engine()
        cls.analysis = cls.engine.load_module("analysis")
        cls.paired = cls.engine.load_module("paired")
        cls.decisions = cls.engine.load_module("decisions")
        cls.coordinates = cls.decisions.COORDINATES
        cls.response = staticmethod(cls.engine.response_factory(cls.paired))

    def scenario(self, name):
        return next(x for x in self.experiment["scenarios"] if x["id"] == name)

    def test_plan_and_predecessor_tampering_fail_closed(self):
        with mock.patch.object(Path, "read_bytes", return_value=b"{}"), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        with mock.patch.object(M, "sha", return_value="0"*64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_generating_distributions_preserve_zero_population_effect_means(self):
        distributions = [self.experiment["listener_ticks_and_weights"], self.experiment["residual_ticks_and_weights"], *self.experiment["source_ticks_and_weights"].values()]
        for items in distributions:
            self.assertEqual(0, sum(value*weight for value, weight in items))
        rare = self.engine.distribution(self.experiment["source_ticks_and_weights"]["rare"])
        self.assertAlmostEqual(.6**2, self.engine.variance(rare)/100)

    def test_scenario_and_replicate_are_exactly_declared(self):
        scenario = copy.deepcopy(self.scenario("matched_boundary"))
        scenario["scales"][0] = True
        with self.assertRaises(ValueError):
            M.rng_for(self.experiment, scenario, 0, "panel")
        for replicate in (-1, True, 128, 1.0):
            with self.assertRaises(ValueError):
                M.rng_for(self.experiment, self.scenario("matched_boundary"), replicate, "panel")
        with self.assertRaises(ValueError):
            M.rng_for(self.experiment, self.scenario("matched_boundary"), 0, "unknown")

    def test_generated_panels_are_bounded_repeatable_and_role_linked(self):
        for scenario in self.experiment["scenarios"]:
            generated, absent = M.generated_panel(self.experiment, scenario, 0, self.engine)
            self.assertEqual((generated, absent), M.generated_panel(self.experiment, scenario, 0, self.engine))
            self.assertEqual(288, len(generated))
            self.assertTrue(all(-40 <= x[2] <= 40 for x in generated))
            matrix, complete = M.linked_matrix(generated, self.experiment, self.response)
            self.assertEqual(sum(x[3] for x in generated), len(complete))
            for listener, source, difference, accepted in generated:
                self.assertEqual(difference if accepted else None, matrix[listener][source])

    def test_declared_selective_missingness_rules(self):
        generated, _ = M.generated_panel(self.experiment, self.scenario("outcome_missing_boundary"), 0, self.engine)
        self.assertTrue(all(accepted == (difference > -10) for _, _, difference, accepted in generated))
        generated, _ = M.generated_panel(self.experiment, self.scenario("source_missing_boundary"), 0, self.engine)
        for source in range(12):
            self.assertEqual(1, len({accepted for _, s, _, accepted in generated if s == source}))

    def test_missing_latent_outcomes_do_not_leak_into_method_inputs(self):
        panels = [[(i, j, value, False) for i in range(24) for j in range(12)] for value in (-40, 40)]
        low, high = [M.linked_matrix(panel, self.experiment, self.response) for panel in panels]
        self.assertEqual(low, high)
        self.assertEqual([], low[1])
        self.assertEqual((Fraction(-4), Fraction(4)), M.summary(low[0])["finite_bounds"])

    def test_assignment_grid_cannot_drop_or_duplicate_a_cell(self):
        panel, _ = M.generated_panel(self.experiment, self.scenario("matched_boundary"), 0, self.engine)
        for broken in (panel[:-1], panel + [panel[0]]):
            with self.assertRaises(ValueError):
                M.linked_matrix(broken, self.experiment, self.response)

    def test_invalid_matrices_are_rejected(self):
        for matrix in (None, [], [[]], [[0], []], [[True]], [[41]], [[-41]], [[1.5]], [[0]*13], [[0]]*25):
            with self.assertRaises(ValueError):
                M.validate_matrix(matrix)

    def test_finite_bounds_contain_every_tiny_completion_and_are_sharp(self):
        matrix = [[10, None], [-10, None]]
        bounds = M.summary(matrix)["finite_bounds"]
        means = [Fraction(a+b, 40) for a, b in itertools.product((-40, 0, 40), repeat=2)]
        self.assertEqual((min(means), max(means)), bounds)
        self.assertTrue(all(bounds[0] <= x <= bounds[1] for x in means))
        self.assertEqual(4, bounds[1]-bounds[0])

    def test_finite_panel_bounds_are_not_population_confidence_intervals(self):
        bounds = M.summary([[-10, -10], [-10, -10]])["finite_bounds"]
        self.assertEqual((Fraction(-1), Fraction(-1)), bounds)
        self.assertFalse(bounds[0] <= 0 <= bounds[1])

    def test_weighted_intersections_match_literal_row_column_resampling(self):
        matrix = [[-10, None], [20, 5]]
        ticks, masks = [[-10, 0], [20, 5]], [[1, 0], [1, 1]]
        for rows, columns in itertools.product(itertools.product(range(2), repeat=2), repeat=2):
            row_counts = [rows.count(i) for i in range(2)]
            column_counts = [columns.count(j) for j in range(2)]
            literal = [matrix[i][j] for i in rows for j in columns if matrix[i][j] is not None]
            self.assertEqual((sum(literal), len(literal)), M.weighted_totals(ticks, masks, row_counts, column_counts))

    def test_multinomial_weights_preserve_each_dimension(self):
        for size in (1, 2, 12, 24):
            weights = M.multinomial_counts(random.Random(13), size)
            self.assertEqual(size, sum(weights))
            self.assertEqual(size, len(weights))
            self.assertTrue(all(type(x) is int and x >= 0 for x in weights))
        for size in (0, True, 25, 1.0):
            with self.assertRaises(ValueError):
                M.multinomial_counts(random.Random(13), size)

    def test_bootstrap_repeatability_prefix_and_missing_counts(self):
        matrix = [[-10, None], [20, 5]]
        first = M.bootstrap_sums(matrix, random.Random(19), 32)
        doubled = M.bootstrap_sums(matrix, random.Random(19), 64)
        self.assertEqual(first, doubled[:32])
        self.assertTrue(all(0 <= count <= 4 and abs(total) <= 40*count for total, count in first))
        for count in (0, True, 2049, 2.5):
            with self.assertRaises(ValueError):
                M.bootstrap_sums(matrix, random.Random(19), count)

    def test_exact_quantile_interpolation_and_boundaries(self):
        values = [(-2, 1), (0, 1)]
        self.assertEqual(Fraction(-1), M.ratio_quantile(values, 40))
        self.assertEqual(Fraction(-79, 40), M.ratio_quantile(values, 1))
        self.assertEqual(Fraction(-2), M.ratio_quantile(values, 0))
        self.assertEqual(Fraction(0), M.ratio_quantile(values, 80))
        self.assertEqual(Fraction(1, 3), M.ratio_quantile([(1, 3)], 79))

    def test_quantile_sort_matches_independent_exact_fraction_order(self):
        rng = random.Random(72)
        values = []
        for _ in range(1000):
            denominator = rng.randrange(1, 2881)
            values.append((rng.randrange(-4*denominator, 4*denominator+1), denominator))
        ordered = sorted(Fraction(n, d) for n, d in values)
        for tail in (1, 40, 79):
            index, remainder = divmod(999*tail, 80)
            expected = ((80-remainder)*ordered[index] + remainder*ordered[index+1])/80
            self.assertEqual(expected, M.ratio_quantile(values, tail))

    def test_invalid_quantile_ratios_and_tails_fail_closed(self):
        for values in ([], [(True, 1)], [(0, True)], [(0, 0)], [(0, 2881)], [(5, 1)], [[0, 1]], [(1.0, 1)]):
            with self.assertRaises(ValueError):
                M.ratio_quantile(values, 1)
        for tail in (-1, True, 81, 1.5):
            with self.assertRaises(ValueError):
                M.ratio_quantile([(0, 1)], tail)

    def test_complete_data_produces_equal_candidate_intervals_without_fake_bound_midpoint(self):
        matrix = [[-20, -10], [-10, 0]]
        fits = M.crossed_intervals(matrix, M.bootstrap_sums(matrix, random.Random(1), 128))
        self.assertEqual(fits[M.METHODS[1]]["interval"], fits[M.METHODS[2]]["interval"])
        self.assertEqual(-1, fits[M.METHODS[1]]["point"])
        self.assertIsNone(fits[M.METHODS[2]]["point"])

    def test_empty_draw_is_retained_without_conditional_resampling(self):
        fits = M.crossed_intervals([[-10, None], [-10, None]], [(0, 0), (-40, 4)])
        cc, bounded = fits[M.METHODS[1]], fits[M.METHODS[2]]
        self.assertEqual("empty_bootstrap_draw", cc["failure"])
        self.assertIsNone(cc["interval"])
        self.assertEqual(1, cc["empty_draws"])
        self.assertEqual(1, bounded["empty_draws"])
        self.assertIsNotNone(bounded["interval"])

    def test_all_missing_data_produces_only_uninformative_bounds(self):
        matrix = [[None, None], [None, None]]
        fits = M.crossed_intervals(matrix, M.bootstrap_sums(matrix, random.Random(1), 32))
        self.assertEqual("no_complete_data", fits[M.METHODS[1]]["failure"])
        self.assertEqual((Fraction(-4), Fraction(4)), fits[M.METHODS[2]]["interval"])
        self.assertEqual("indeterminate", M.state(fits[M.METHODS[2]], M.summary(matrix)["counts"], self.coordinates))

    def test_basic_interval_boundary_is_exact_and_not_rounded_into_a_claim(self):
        fits = M.crossed_intervals([[-10]], [(-10, 1)]*32)
        counts = dict(self.coordinates["minimum_support"])
        for fit in fits.values():
            self.assertEqual((Fraction(-1), Fraction(-1)), fit["interval"])
            self.assertEqual("indeterminate", M.state(fit, counts, self.coordinates))

    def test_interval_only_severity_logic_agrees_with_bound_adapter(self):
        counts = dict(self.coordinates["minimum_support"])
        for lower, upper in ((-2, -1.5), (-1, 0), (-.5, 0), (-2, -1), (-2, 0)):
            fit = {"estimate": (lower+upper)/2, "lower": lower, "upper": upper, "converged": True, **counts}
            self.assertEqual(self.decisions.evidence(fit, "paired_sdg")["state"], M.state(M.result((lower, upper)), counts, self.coordinates))

    def test_legacy_failures_are_retained_and_unrelated_errors_escape(self):
        self.assertEqual("no_complete_data", M.legacy_interval([], self.analysis, self.engine)["failure"])
        for message in self.engine.NUMERICAL_FAILURES:
            with mock.patch.object(self.analysis, "_fit_gaussian", side_effect=ValueError(message)):
                self.assertEqual("numerical_failure", M.legacy_interval([{}], self.analysis, self.engine)["failure"])
        with mock.patch.object(self.analysis, "_fit_gaussian", side_effect=ValueError("unknown")), self.assertRaisesRegex(ValueError, "unknown"):
            M.legacy_interval([{}], self.analysis, self.engine)

    def test_failure_support_coverage_and_point_denominators_stay_separate(self):
        acc = M.accumulator()
        counts = {"listeners": 24, "sources": 1, "responses": 24}
        M.observe(acc, M.result((-2, 0)), counts, -1, self.coordinates, True)
        M.observe(acc, M.result(failure="empty_bootstrap_draw"), counts, -1, self.coordinates, True)
        report = M.aggregate(acc, 2, self.engine)
        self.assertEqual(2, report["return_and_cover_rate"]["denominator"])
        self.assertEqual(1, report["coverage_given_returned"]["denominator"])
        self.assertEqual(0, report["coverage_given_count_supported"]["denominator"])
        self.assertIsNone(report["bias_given_point_estimate"])
        self.assertEqual(2, report["rare_source_absent_panels"])
        self.assertEqual(1, report["rare_absent_coverage_given_returned"]["denominator"])

    def test_boundary_claims_count_as_wrong_not_useful_abstentions(self):
        acc = M.accumulator()
        counts = dict(self.coordinates["minimum_support"])
        for interval in ((-2, -1.1), (-.9, 0), (-2, 0)):
            M.observe(acc, M.result(interval), counts, -1, self.coordinates, False)
        report = M.aggregate(acc, 3, self.engine)
        self.assertEqual(2, report["wrong_decision_rate"]["numerator"])
        self.assertEqual(0, report["correct_decision_rate"]["numerator"])
        self.assertEqual(1, report["indeterminate_rate"]["numerator"])

    def test_doubling_distinguishes_translation_from_width_change(self):
        for later, width_change in (((-1, 1), 0), ((-3, 1), 2), ((-1, -1), 2)):
            with self.subTest(later=later):
                fits = [{name: M.result(tuple(map(Fraction, limits))) for name in M.METHODS[1:]}
                        for limits in ((-2, 0), later)]
                with mock.patch.object(M, "crossed_intervals", side_effect=fits):
                    case = M.simulate_case(self.experiment, self.scenario("matched_boundary"), 1, 2,
                                           self.engine, self.analysis, self.coordinates, self.response)
                for diagnostic in case["bootstrap_doubling_diagnostic"].values():
                    self.assertEqual(1, diagnostic["both_intervals_returned"])
                    self.assertEqual(1, diagnostic["maximum_endpoint_change"])
                    self.assertEqual(width_change, diagnostic["maximum_width_change"])

    def test_reduced_smoke_is_not_a_full_or_independent_result(self):
        report = M.build_report(1, 16)
        self.assertEqual("reduced_synthetic_smoke_only", report["state"])
        self.assertEqual(12, len(report["scenarios"]))
        for case in report["scenarios"]:
            self.assertFalse(case["finite_panel_bounds"]["is_population_confidence_interval"])
            self.assertEqual(1, case["bootstrap_doubling_diagnostic"][M.METHODS[1]]["panels"])
        for args in ((0, 16), (True, 16), (129, 16), (1, 0), (1, True), (1, 1025)):
            with self.assertRaises(ValueError):
                M.build_report(*args)


class ResamplingReplayTest(unittest.TestCase):
    def test_full_golden_replay_preserves_scope_and_all_denominators(self):
        report = M.build_report()
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(report))
        self.assertEqual("synthetic_resampling_comparison_complete", report["state"])
        self.assertEqual(12, len(report["scenarios"]))
        for case in report["scenarios"]:
            for result in case["methods"].values():
                self.assertEqual(128, result["returned_intervals"] + sum(result["failures"].values()))
                self.assertEqual(128, sum(result["diagnostic_decisions"].values()))
        for key in ("method_selected_for_human_calibration", "human_interval_coverage_validated", "human_materiality_margin_selected",
                    "audibility_coverage_evaluated", "familywise_coverage_evaluated", "independent_method_validation_complete",
                    "human_responses_observed", "oracle_truth_eligible", "no_reference_training_eligible", "objective_complete"):
            self.assertIs(False, report[key])
        for marker in (b"/Users/", b"participant-", b"stimulus-", b".wav", b".flac"):
            self.assertNotIn(marker, M.canonical(report))

    def test_cli_exposes_no_observed_input_or_tuning(self):
        for args in ([], ["--synthetic", "--input", "unopened.json"], ["--synthetic", "--draws", "16"]):
            run = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, run.returncode)
            self.assertEqual(b"", run.stdout)


if __name__ == "__main__":
    unittest.main()
