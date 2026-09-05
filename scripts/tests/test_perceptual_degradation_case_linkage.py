from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_case_linkage.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-case-linkage-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("case_linkage", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class CaseLinkageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = M.load_engine()
        cls.registry = M.registry_for(cls.engine, "choice-correlated")
        cls.responses = M.fixture_responses(cls.engine, cls.registry, "complete")
        cls.targets = M.assemble(cls.engine, cls.registry, cls.responses)

    def test_plan_and_bound_predecessors_fail_closed(self):
        with mock.patch.object(M, "sha", return_value="0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        actual = M.sha
        with mock.patch.object(M, "sha", side_effect=lambda path: actual(path) if path == M.PLAN else "0" * 64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_presentation_aliases_are_not_cases_or_sources(self):
        registry = self.registry
        aliases = {entry["assignment"]["candidate_ids"][entry["assignment"]["condition_position"]] for entry in registry["assignments"]}
        self.assertEqual(288, len(aliases))
        self.assertEqual(12, len(registry["cases"]))
        self.assertEqual(12, len({case["source_group_id"] for case in registry["cases"]}))
        self.assertEqual(6, len({case["leakage_group_id"] for case in registry["cases"]}))
        self.assertTrue(all(target["summary"]["assigned_listeners"] == 24 for target in self.targets))

    def test_source_and_reference_identity_are_shared_across_scenarios(self):
        other = M.registry_for(self.engine, "positive-difference")
        for first, second in zip(self.registry["cases"], other["cases"], strict=True):
            for key in ("source_group_id", "reference_id", "leakage_group_id"):
                self.assertEqual(first[key], second[key])
            for key in ("case_id", "condition_id", "analysis_group_id"):
                self.assertNotEqual(first[key], second[key])

    def test_case_identity_corruption_is_rejected(self):
        for field in M.CASE_KEYS:
            changed = copy.deepcopy(self.registry)
            changed["cases"][0][field] = "synthetic-wrong"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "registry"):
                M.assemble(self.engine, changed, self.responses)

    def test_assignment_linkage_corruption_is_rejected(self):
        for field in ("participant_id", "source_group_id", "analysis_group_id", "condition_position", "trial_id", "partition"):
            changed = copy.deepcopy(self.registry)
            changed["assignments"][0]["assignment"][field] = "synthetic-wrong"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "registry"):
                M.assemble(self.engine, changed, self.responses)
        changed = copy.deepcopy(self.registry)
        changed["assignments"][0]["case_id"] = changed["cases"][1]["case_id"]
        with self.assertRaises(ValueError):
            M.assemble(self.engine, changed, self.responses)

    def test_role_alias_swap_is_rejected(self):
        changed = copy.deepcopy(self.registry)
        aliases = changed["assignments"][0]["assignment"]["candidate_ids"]
        aliases["A"], aliases["B"] = aliases["B"], aliases["A"]
        with self.assertRaises(ValueError):
            M.assemble(self.engine, changed, self.responses)

    def test_missing_or_duplicate_planned_assignment_is_rejected(self):
        for duplicate in (False, True):
            changed = copy.deepcopy(self.registry)
            if duplicate:
                changed["assignments"].append(copy.deepcopy(changed["assignments"][0]))
            else:
                changed["assignments"].pop()
            with self.assertRaises(ValueError):
                M.assemble(self.engine, changed, self.responses)

    def test_duplicate_or_unknown_response_assignment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            M.assemble(self.engine, self.registry, self.responses + [self.responses[0]])
        for key in ("unknown", True, [], None):
            changed = copy.deepcopy(self.responses)
            changed[0]["assignment_id"] = key
            with self.assertRaisesRegex(ValueError, "unknown"):
                M.assemble(self.engine, self.registry, changed)

    def test_response_from_another_trial_is_rejected(self):
        changed = copy.deepcopy(self.responses)
        changed[0]["response"] = changed[1]["response"]
        with self.assertRaisesRegex(ValueError, "another assignment"):
            M.assemble(self.engine, self.registry, changed)

    def test_response_metadata_and_presentation_tampering_are_rejected(self):
        for field, value in (("presentation_sha256", "0" * 64), ("fixture_only", False), ("state", "observed")):
            changed = copy.deepcopy(self.responses)
            changed[0]["response"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                M.assemble(self.engine, self.registry, changed)

    def test_response_order_does_not_change_the_join_or_summaries(self):
        self.assertEqual(self.targets, M.assemble(self.engine, self.registry, list(reversed(self.responses))))

    def test_complete_case_summary_matches_direct_signed_tick_arithmetic(self):
        for target in self.targets:
            summary = target["summary"]
            self.assertEqual(24, summary["complete_pairs"])
            self.assertEqual(12, summary["correct_choices"])
            self.assertEqual(12, summary["incorrect_choices_retained"])
            # Twelve -2 and twelve +1 differences, not selected-candidate grades.
            self.assertEqual("-1/2", summary["observed_signed_paired_mean"])
            self.assertEqual("-1/2", summary["planned_panel_signed_paired_mean"])
            self.assertEqual("1/2", summary["observed_correct_choice_fraction"])

    def test_positive_differences_and_incorrect_choices_remain(self):
        registry = M.registry_for(self.engine, "positive-difference")
        targets = M.assemble(self.engine, registry, M.fixture_responses(self.engine, registry, "complete"))
        for target in targets:
            self.assertEqual("4/1", target["summary"]["observed_signed_paired_mean"])
            self.assertEqual(24, target["summary"]["incorrect_choices_retained"])
            self.assertEqual("0/1", target["summary"]["observed_correct_choice_fraction"])

    def test_incomplete_pairs_keep_choices_and_separate_denominators(self):
        targets = M.assemble(self.engine, self.registry, M.fixture_responses(self.engine, self.registry, "incorrect_pairs_unsubmitted"))
        for target in targets:
            summary = target["summary"]
            self.assertEqual((24, 12, 12), (summary["locked_choices"], summary["complete_pairs"], summary["missing_pairs"]))
            self.assertEqual("-2/1", summary["observed_signed_paired_mean"])
            self.assertIsNone(summary["planned_panel_signed_paired_mean"])
            self.assertEqual("1/2", summary["planned_panel_correct_choice_fraction"])

    def test_entirely_missing_case_is_not_dropped(self):
        targets = M.assemble(self.engine, self.registry, M.fixture_responses(self.engine, self.registry, "one_case_absent"))
        self.assertEqual(12, len(targets))
        self.assertEqual([0] * 11 + [24], [target["summary"]["absent_responses"] for target in targets])
        last = targets[-1]["summary"]
        self.assertIsNone(last["observed_signed_paired_mean"])
        self.assertIsNone(last["planned_panel_correct_choice_fraction"])

    def test_empty_response_list_is_missing_not_zero_outcome(self):
        targets = M.assemble(self.engine, self.registry, [])
        self.assertEqual(12, len(targets))
        for target in targets:
            self.assertEqual(24, target["summary"]["absent_responses"])
            self.assertIsNone(target["summary"]["observed_signed_paired_mean"])
            self.assertIsNone(target["summary"]["observed_correct_choice_fraction"])

    def test_received_empty_trial_and_absent_response_are_distinct(self):
        assignment = self.registry["assignments"][0]["assignment"]
        response = self.engine.reduce_events(self.engine.presentation_assignment(assignment), [])
        targets = M.assemble(self.engine, self.registry, [{"assignment_id": assignment["assignment_id"], "response": response}])
        self.assertEqual((1, 23, 24), tuple(targets[0]["summary"][key] for key in ("received_responses", "absent_responses", "missing_pairs")))

    def test_synthetic_complete_fractions_never_become_population_targets(self):
        for target in self.targets:
            for key in ("population_correct_response_probability", "population_paired_mean", "population_interval", "material_condition_label", "audible_condition_label", "independent_sampling_unit_count"):
                self.assertIsNone(target["summary"][key])
            self.assertIs(False, target["scientific_truth_eligible"])

    def test_aggregate_adapter_targets_are_not_case_targets(self):
        prior = json.loads((ROOT / M.BINDINGS["target_semantics_report"]).read_text())
        for target in prior["baseline_targets"] + [prior["intermediate_target"]]:
            with self.assertRaises(ValueError):
                M.route_case_summary(target, self.registry["cases"], M.FINITE_SCOPE)

    def test_forged_eligibility_or_aggregate_unit_cannot_route(self):
        for field, value in (("fixture_only", 1), ("scientific_truth_eligible", True), ("analysis_unit", "aggregate_analysis_group"), ("summary_scope", "population")):
            changed = copy.deepcopy(self.targets[0])
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                M.route_case_summary(changed, self.registry["cases"], M.FINITE_SCOPE)

    def test_all_scientific_consumer_requests_are_closed(self):
        for scope in ("source_condition_population_target", "scientific_source_label", "population_generalization", "legacy_full_reference_evaluation", None, True):
            with self.assertRaises(ValueError):
                M.route_case_summary(self.targets[0], self.registry["cases"], scope)

    def test_crossed_identity_on_a_consumer_target_is_rejected(self):
        changed = copy.deepcopy(self.targets[0])
        changed["linkage"]["reference_id"] = self.targets[1]["linkage"]["reference_id"]
        with self.assertRaisesRegex(ValueError, "linkage"):
            M.route_case_summary(changed, self.registry["cases"], M.FINITE_SCOPE)

    def test_population_evidence_cannot_be_hidden_in_finite_summary(self):
        for key in M.NULL_KEYS:
            changed = copy.deepcopy(self.targets[0])
            changed["summary"][key] = 1
            with self.assertRaisesRegex(ValueError, "scientific"):
                M.route_case_summary(changed, self.registry["cases"], M.FINITE_SCOPE)

    def test_finite_summary_count_and_mean_corruption_fail_closed(self):
        changes = [(key, True) for key in M.COUNT_KEYS] + [
            ("received_responses", 23), ("correct_choices", 13), ("complete_pairs", 12),
            ("observed_correct_choice_fraction", "2/3"), ("planned_panel_correct_choice_fraction", None),
        ]
        changes.extend(("observed_signed_paired_mean", value) for value in (None, 0, "nan", "1/0", "5/1", "-2/4", "1/7"))
        changes.append(("planned_panel_signed_paired_mean", None))
        for field, value in changes:
            changed = copy.deepcopy(self.targets[0])
            changed["summary"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                M.route_case_summary(changed, self.registry["cases"], M.FINITE_SCOPE)

    def test_fraction_serialization_is_exact_and_zero_denominator_is_null(self):
        self.assertEqual("-1/2", M.rational(-120, 240))
        self.assertEqual("0/1", M.rational(0, 24))
        self.assertIsNone(M.rational(0, 0))
        for pair in ((True, 2), (1, True), (1, -1), (.5, 2)):
            with self.assertRaises(ValueError):
                M.rational(*pair)

    def test_inputs_are_not_mutated(self):
        registry, responses = copy.deepcopy(self.registry), copy.deepcopy(self.responses)
        M.assemble(self.engine, registry, responses)
        self.assertEqual(self.registry, registry)
        self.assertEqual(self.responses, responses)

    def test_unknown_or_undeclared_fixture_variants_fail(self):
        for scenario in (True, None, "unknown"):
            with self.assertRaises(ValueError):
                M.registry_for(self.engine, scenario)
        for variant in (True, None, "unknown"):
            with self.assertRaises(ValueError):
                M.fixture_responses(self.engine, self.registry, variant)
        with self.assertRaises(ValueError):
            M.fixture_responses(self.engine, M.registry_for(self.engine, "equal-top"), "all_absent")


class CaseLinkageReplayTest(unittest.TestCase):
    def test_full_replay_matches_aggregate_evidence_and_closed_scope(self):
        report = M.build_report()
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(report))
        self.assertEqual(8, len(report["panels"]))
        self.assertEqual(4, report["aggregate_adapter_targets_rejected"])
        self.assertEqual({"scenarios": 5, "listeners": 24, "planned_presentations": 1440, "stable_cases": 60, "source_groups": 12, "leakage_groups": 6, "independent_sampling_unit_count": None}, report["complete_fixture_inventory"])
        for key in ("scientific_source_labels_supported", "population_inference_supported", "source_identity_verified_from_media", "human_responses_observed", "sampling_frame_established", "interval_coverage_validated", "legacy_evaluator_replaced", "scientific_gate_evaluated", "full_reference_oracle_validated", "objective_complete"):
            self.assertIs(False, report[key])
        for marker in (b"/Users/", b"participant-synthetic-", b"case-synthetic-", b"source-synthetic-", b"assignment-", b"stimulus-", b".wav", b".flac"):
            self.assertNotIn(marker, M.canonical(report))

    def test_cli_rejects_observed_inputs_or_tuning(self):
        for args in ([], ["--synthetic", "--input", "unopened.json"], ["--synthetic", "--listeners", "48"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
