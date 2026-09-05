from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_independent_groups.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-independent-groups-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("independent_groups", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class IndependentGroupsStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = M.load_plan()
        cls.engine = M.load_engine()

    def test_plan_and_predecessor_bytes_fail_closed(self):
        with mock.patch.object(M, "sha", return_value="0"*64), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        actual_sha = M.sha
        with mock.patch.object(M, "sha", side_effect=lambda path: actual_sha(path) if path == M.PLAN else "0"*64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_binomial_masses_match_literal_independent_bit_enumeration(self):
        for count, theta in itertools.product(range(1, 6), (Fraction(0), Fraction(1, 5), Fraction(1, 2), Fraction(1))):
            literal = [Fraction(0)]*(count+1)
            for bits in itertools.product((0, 1), repeat=count):
                k = sum(bits)
                literal[k] += theta**k * (1-theta)**(count-k)
            self.assertEqual(tuple(literal), M.binomial_masses(count, theta))

    def test_invalid_counts_and_probabilities_are_rejected(self):
        M.binomial_masses(1, Fraction(1, 2))
        M.binomial_masses(4, Fraction(1, 2))
        M.tails(1, Fraction(1, 2))
        for count in (0, True, 41, 1.5):
            with self.assertRaises(ValueError):
                M.binomial_masses(count, Fraction(1, 2))
        for theta in (True, .5, -1, Fraction(-1, 2), Fraction(3, 2)):
            with self.assertRaises(ValueError):
                M.binomial_masses(4, theta)
        for count, theta in ((True, Fraction(1, 2)), (1.0, Fraction(1, 2)), (1, .5)):
            with self.assertRaises(ValueError):
                M.tails(count, theta)
        for k in (-1, True, 5, 1.0):
            with self.assertRaises(ValueError):
                M.exact_events(k, 4, Fraction(1, 2))
        for copies in (0, True, 41, 2.0):
            with self.assertRaises(ValueError):
                M.enumerate_case(self.engine, 4, copies, Fraction(1, 2))

    def test_exact_probability_serializes_large_integers_losslessly(self):
        value = Fraction(1, 10**80)
        result = M.probability(value)
        self.assertEqual(value, Fraction(result))
        self.assertIsInstance(result, str)
        for bad in (0, .5, Fraction(-1), Fraction(2)):
            with self.assertRaises(ValueError):
                M.probability(bad)

    def test_exact_tails_are_inclusive_and_sum_with_the_point_mass(self):
        for count in (1, 4, 20):
            masses = M.binomial_masses(count, Fraction(1, 5))
            cdf, tail = M.tails(count, Fraction(1, 5))
            for k in range(count+1):
                self.assertEqual(sum(masses[:k+1]), cdf[k])
                self.assertEqual(sum(masses[k:]), tail[k])
                self.assertEqual(1+masses[k], cdf[k]+tail[k])

    def test_noncoverage_is_strict_at_exact_tail_equality(self):
        self.assertFalse(M.exact_events(0, 1, Fraction(19, 20))["upper_noncoverage"])
        self.assertTrue(M.exact_events(0, 1, Fraction(96, 100))["upper_noncoverage"])
        self.assertFalse(M.exact_events(1, 1, Fraction(1, 20))["lower_noncoverage"])
        self.assertTrue(M.exact_events(1, 1, Fraction(4, 100))["lower_noncoverage"])

    def test_exact_tail_decisions_match_closed_form_single_trial_limits(self):
        for theta in (Fraction(0), Fraction(1, 100), Fraction(1, 20), Fraction(1, 2), Fraction(19, 20), Fraction(1)):
            self.assertEqual(theta > Fraction(19, 20), M.exact_events(0, 1, theta)["upper_noncoverage"])
            self.assertEqual(theta < Fraction(1, 20), M.exact_events(1, 1, theta)["lower_noncoverage"])
            self.assertFalse(M.exact_events(0, 1, theta)["safety_guard_pass"])
            self.assertFalse(M.exact_events(1, 1, theta)["sensitivity_guard_pass"])

    def test_exact_noncoverage_is_complement_symmetric(self):
        for count in (1, 4, 20):
            for k in range(count+1):
                for theta in (Fraction(1, 5), Fraction(79, 100)):
                    first = M.exact_events(k, count, theta)
                    second = M.exact_events(count-k, count, 1-theta)
                    self.assertEqual(first["upper_noncoverage"], second["lower_noncoverage"])

    def test_zero_event_and_all_event_exact_gate_boundaries(self):
        for count in range(1, 41):
            theta = Fraction(1, 2)
            self.assertEqual(Fraction(9, 10)**count <= M.ALPHA, M.exact_events(0, count, theta)["safety_guard_pass"])
            self.assertEqual(Fraction(4, 5)**count <= M.ALPHA, M.exact_events(count, count, theta)["sensitivity_guard_pass"])

    def test_exact_boundary_root_is_outward_bracketed(self):
        for count in (1, 4, 20, 40):
            bracket = M.exact_boundary_brackets(count)
            lo, hi = map(Fraction, bracket["all_event_lower"])
            upper_lo, upper_hi = map(Fraction, bracket["zero_event_upper"])
            self.assertLessEqual(lo**count, M.ALPHA)
            self.assertGreaterEqual(hi**count, M.ALPHA)
            self.assertLessEqual(hi-lo, Fraction(1, 2**64))
            self.assertEqual((1-hi, 1-lo), (upper_lo, upper_hi))

    def test_source_and_partition_wilson_agree_without_multiplicity(self):
        case = M.enumerate_case(self.engine, 20, 1, Fraction(11, 100))
        self.assertEqual(case["guard_probabilities"][M.METHODS[0]], case["guard_probabilities"][M.METHODS[1]])

    def test_partition_results_are_invariant_to_related_source_count(self):
        cases = [M.enumerate_case(self.engine, 4, copies, Fraction(1, 5)) for copies in (1, 2, 4, 40)]
        for method in M.METHODS[1:]:
            self.assertTrue(all(case["guard_probabilities"][method] == cases[0]["guard_probabilities"][method] for case in cases))

    def test_actual_legacy_guard_equals_the_enumerated_source_counts(self):
        for count, copies in itertools.product((1, 4), (1, 2, 4)):
            for k in range(count+1):
                rows = [{"source_group_id": f"source-{i}-{j}", "partition_group_id": f"partition-{i}",
                         "oracle": {"materially_degraded": i < k}}
                        for i in range(count) for j in range(copies)]
                for mode in ("any_event", "all_success"):
                    guard = self.engine._source_group_guard(rows, "materially_degraded", mode=mode)
                    self.assertEqual(self.engine.wilson_bounds(k*copies, count*copies), (guard["lower_one_sided_95"], guard["upper_one_sided_95"]))

    def test_fully_shared_source_mean_variance_uses_partition_count(self):
        theta, count, copies = Fraction(1, 5), 4, 10
        masses = M.binomial_masses(count, theta)
        variance = sum(mass * (Fraction(k, count)-theta)**2 for k, mass in enumerate(masses))
        self.assertEqual(theta*(1-theta)/count, variance)
        self.assertEqual(copies, variance/(theta*(1-theta)/(count*copies)))

    def test_all_outcomes_are_accounted_and_exact_bounds_control_tail_error(self):
        for count, theta in itertools.product((1, 4, 20, 40), (Fraction(1, 5), Fraction(79, 100))):
            case = M.enumerate_case(self.engine, count, 4, theta)
            self.assertEqual(count+1, case["outcomes_enumerated"])
            self.assertEqual("1/1", case["probability_mass"])
            for event in M.EVENTS[:2]:
                rate = case["guard_probabilities"][M.METHODS[2]][event]
                self.assertLessEqual(Fraction(rate), M.ALPHA)

    def test_false_combined_component_lower_bounds_use_extreme_event_mass(self):
        case = M.enumerate_case(self.engine, 1, 40, Fraction(1, 5))
        self.assertEqual(M.probability(Fraction(4, 5)), case["false_combined_safety_component_zero_event_lower_bound"])
        self.assertEqual(M.probability(Fraction(1, 5)), case["false_combined_sensitivity_component_all_event_lower_bound"])
        at_boundary = M.enumerate_case(self.engine, 1, 40, Fraction(1, 10))
        self.assertFalse(at_boundary["safety_claim_would_be_false"])
        self.assertEqual(M.probability(Fraction(0)), at_boundary["false_combined_safety_component_zero_event_lower_bound"])
        self.assertFalse(case["full_reference_gate_probability_evaluated"])

    def test_regrouping_changes_only_partition_identity_and_legacy_accepts_it(self):
        base = self.engine.synthetic_records()
        original = copy.deepcopy(base)
        for count in (1, 20, 40):
            changed = M.partition_variant(base, count)
            self.assertEqual([], self.engine.validate_records(changed))
            self.assertEqual(count, len({row["partition_group_id"] for row in changed}))
            self.assertEqual(40, len({row["source_group_id"] for row in changed}))
            for before, after in zip(base, changed, strict=True):
                self.assertEqual({k: v for k, v in before.items() if k != "partition_group_id"}, {k: v for k, v in after.items() if k != "partition_group_id"})
        self.assertEqual(original, base)
        for count in (0, True, 3, 80, 1.0):
            with self.assertRaises(ValueError):
                M.partition_variant(base, count)

    def test_unequal_cluster_sizes_change_the_target_weighting(self):
        examples = M.weighting_examples(self.plan["experiment"])
        self.assertEqual(["1/2", "1/2"], [x["equal_partition_mean"] for x in examples])
        self.assertEqual(["1/10", "9/10"], [x["equal_source_mean"] for x in examples])

    def test_serialization_keeps_finite_probability_endpoints_as_floats(self):
        self.assertEqual(b'{\n  "lower": 0.0,\n  "upper": 1.0\n}\n', M.canonical(M.rounded({"lower": float(0), "upper": float(1)})))
        with self.assertRaises(ValueError):
            M.rounded(float("nan"))


class IndependentGroupsReplayTest(unittest.TestCase):
    def test_full_replay_and_closed_scientific_scope(self):
        report = M.build_report()
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(report))
        self.assertEqual(128, report["case_count"])
        self.assertEqual(16, len(report["extreme_outcome_bounds"]))
        self.assertTrue(report["legacy_fixture_boundary_check"]["rate_components_invariant_to_partition_regrouping"])
        for variant in report["legacy_fixture_boundary_check"]["variants"]:
            for component in variant["rate_components"].values():
                self.assertEqual(10000, component["bootstrap_draws"])
                self.assertEqual(10000, component["valid_draws"])
        for key in ("method_selected", "population_sampling_frame_established", "human_interval_coverage_validated",
                    "human_responses_observed", "metric_scores_observed", "scientific_gate_evaluated",
                    "oracle_truth_eligible", "no_reference_training_eligible", "objective_complete"):
            self.assertIs(False, report[key])
        for marker in (b"/Users/", b".wav", b".flac", b"participant-", b"case-"):
            self.assertNotIn(marker, M.canonical(report))

    def test_cli_has_no_observed_input_or_tuning_options(self):
        for args in ([], ["--synthetic", "--input", "unopened.json"], ["--synthetic", "--replicates", "16"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"", result.stdout)


if __name__ == "__main__":
    unittest.main()
