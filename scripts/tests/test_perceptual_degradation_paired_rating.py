from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_paired_rating.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-paired-rating-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("paired_rating", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PairedRatingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = MODULE.build_synthetic_report()

    def setUp(self) -> None:
        self.assignment = MODULE.synthetic_assignment("symmetric-error", 0, 0)
        self.presentation = MODULE.presentation_assignment(self.assignment)
        self.events = MODULE.synthetic_events(self.assignment)

    def resolve(self, events: list[dict] | None = None) -> dict:
        response = MODULE.reduce_events(self.presentation, self.events if events is None else events)
        return MODULE.resolve_response(self.assignment, response)

    def test_roles_not_choice_or_grade_order_determine_signed_target(self) -> None:
        for source, chosen, condition_grade, hidden_grade in itertools.product(
            (0, 1), ("A", "B"), (10, 11, 20, 35, 49, 50), (10, 11, 20, 35, 49, 50)
        ):
            assignment = MODULE.synthetic_assignment("equal-top", 0, source)
            events = MODULE.synthetic_events(assignment)
            events[0]["position"] = chosen
            for event in events[1:3]:
                event["grade_ticks"] = condition_grade if event["position"] == assignment["condition_position"] else hidden_grade
            response = MODULE.reduce_events(MODULE.presentation_assignment(assignment), events)
            target = MODULE.resolve_response(assignment, response)
            self.assertEqual((condition_grade - hidden_grade) / 10, target["paired_sdg"])
            self.assertEqual(condition_grade, target["condition_grade_ticks"])
            self.assertEqual(hidden_grade, target["hidden_reference_grade_ticks"])
            self.assertEqual(chosen == assignment["condition_position"], target["forced_choice_correct"])
            self.assertTrue(target["complete_pair_analysis_eligible"])
            self.assertFalse(target["scientific_truth_eligible"])

    def test_incorrect_choice_is_retained_with_positive_difference(self) -> None:
        assignment = MODULE.synthetic_assignment("positive-difference", 0, 0)
        target = MODULE.resolve_response(assignment, MODULE.reduce_events(MODULE.presentation_assignment(assignment), MODULE.synthetic_events(assignment)))
        self.assertFalse(target["forced_choice_correct"])
        self.assertEqual(4.0, target["paired_sdg"])
        self.assertTrue(target["complete_pair_analysis_eligible"])

    def test_symmetric_errors_do_not_become_impairment(self) -> None:
        result = next(row for row in self.report["scenarios"] if row["synthetic_scenario"] == "symmetric-error")
        self.assertEqual(0, result["signed_paired_mean"])
        self.assertEqual(0, result["signed_crossed_effects_estimate"])
        self.assertEqual(-0.6, result["counterfactual_correct_only_mean"])
        self.assertEqual(-0.6, result["counterfactual_selected_grade_offset_mean"])
        self.assertEqual(-0.3, result["counterfactual_nonpositive_clipped_mean"])
        self.assertEqual(144, result["incorrect_choices_retained"])

    def test_correct_only_filter_changes_the_target(self) -> None:
        result = next(row for row in self.report["scenarios"] if row["synthetic_scenario"] == "choice-correlated")
        self.assertEqual(-0.5, result["signed_crossed_effects_estimate"])
        self.assertEqual(-2, result["counterfactual_correct_only_mean"])
        self.assertEqual(-1.5, result["counterfactual_selected_grade_offset_mean"])
        self.assertEqual(-1, result["counterfactual_nonpositive_clipped_mean"])

    def test_common_grade_offset_cancels_without_assuming_reference_is_five(self) -> None:
        result = next(row for row in self.report["scenarios"] if row["synthetic_scenario"] == "common-offset")
        self.assertEqual(-1, result["signed_crossed_effects_estimate"])
        self.events[1]["grade_ticks"] = 30
        self.events[2]["grade_ticks"] = 40
        before = self.resolve()
        for event in self.events[1:3]:
            event["grade_ticks"] += 5
        self.assertEqual(before["paired_sdg"], self.resolve()["paired_sdg"])

    def test_empty_partial_and_unsubmitted_pairs_are_incomplete_without_imputation(self) -> None:
        for count in range(4):
            response = MODULE.reduce_events(self.presentation, self.events[:count])
            target = MODULE.resolve_response(self.assignment, response)
            self.assertEqual("incomplete", response["trial_status"])
            self.assertIsNone(target["paired_sdg"])
            self.assertFalse(target["complete_pair_analysis_eligible"])
            if count == 0:
                self.assertIsNone(target["forced_choice_correct"])
            if count >= 2:
                self.assertEqual(44, target["condition_grade_ticks"])

    def test_both_ratings_require_explicit_entry(self) -> None:
        for prefix in ([], self.events[:1], self.events[:2]):
            with self.assertRaisesRegex(ValueError, "both explicit grades"):
                MODULE.reduce_events(self.presentation, prefix + [{"sequence": len(prefix), "kind": "submit"}])

    def test_pre_choice_grades_and_choice_changes_rejected(self) -> None:
        grade = {**self.events[1], "sequence": 0}
        with self.assertRaisesRegex(ValueError, "precede grades"):
            MODULE.reduce_events(self.presentation, [grade])
        with self.assertRaisesRegex(ValueError, "already locked"):
            MODULE.reduce_events(self.presentation, self.events[:1] + [{**self.events[0], "sequence": 1}])

    def test_grade_revision_before_submit_is_allowed(self) -> None:
        events = self.events[:3] + [{"sequence": 3, "kind": "grade", "position": "A", "grade_ticks": 45}, {"sequence": 4, "kind": "submit"}]
        self.assertEqual(-0.5, self.resolve(events)["paired_sdg"])

    def test_rating_order_does_not_change_target(self) -> None:
        events = [self.events[0], {**self.events[2], "sequence": 1}, {**self.events[1], "sequence": 2}, self.events[3]]
        self.assertEqual(self.resolve(), self.resolve(events))

    def test_post_submit_changes_and_duplicate_or_noninteger_sequences_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "already submitted"):
            MODULE.reduce_events(self.presentation, self.events + [{**self.events[1], "sequence": 4}])
        for value in (0, True, 1.0, -1, 9):
            events = copy.deepcopy(self.events)
            events[1]["sequence"] = value
            with self.assertRaises(ValueError):
                MODULE.reduce_events(self.presentation, events)

    def test_invalid_grade_types_and_ranges_rejected(self) -> None:
        for value in (True, None, "50", 50.0, math.nan, math.inf, 9, 51, -4):
            events = copy.deepcopy(self.events)
            events[1]["grade_ticks"] = value
            with self.assertRaises(ValueError):
                MODULE.reduce_events(self.presentation, events)

    def test_presentation_contains_no_roles_recipes_or_group_identity(self) -> None:
        public = MODULE.canonical_bytes(self.presentation)
        for marker in (b"condition", b"reference", b"participant", b"source_group", b"scenario", b"recipe", b"partition"):
            self.assertNotIn(marker, public)

    def test_assignment_source_partition_and_presentation_bindings_cannot_drift(self) -> None:
        response = MODULE.reduce_events(self.presentation, self.events)
        for field, value in (("source_group_id", "source-elsewhere"), ("partition", "transfer"), ("condition_position", "B"), ("fixture_only", 1)):
            assignment = copy.deepcopy(self.assignment)
            assignment[field] = value
            with self.assertRaises(ValueError):
                MODULE.resolve_response(assignment, response)
        other = MODULE.synthetic_assignment("symmetric-error", 1, 0)
        with self.assertRaisesRegex(ValueError, "another assignment"):
            MODULE.resolve_response(other, response)
        self.presentation["candidate_ids"]["A"] = self.presentation["candidate_ids"]["B"]
        response = MODULE.reduce_events(self.presentation, self.events)
        with self.assertRaisesRegex(ValueError, "presentation binding"):
            MODULE.resolve_response(self.assignment, response)

    def test_unknown_fields_roles_and_legacy_single_grade_rejected(self) -> None:
        for field in ("role", "path", "codec", "forced_choice_correct", "sdg"):
            events = copy.deepcopy(self.events)
            events[1][field] = "not-accepted"
            with self.assertRaises(ValueError):
                MODULE.reduce_events(self.presentation, events)
            response = MODULE.reduce_events(self.presentation, self.events)
            response[field] = "not-accepted"
            with self.assertRaises(ValueError):
                MODULE.resolve_response(self.assignment, response)
        legacy = {"forced_choice_position": "A", "subjective_difference_grade": -2}
        with self.assertRaises(ValueError):
            MODULE.resolve_response(self.assignment, legacy)

    def test_observed_inconsistent_or_injected_responses_rejected(self) -> None:
        for field, value in (("state", "observed"), ("fixture_only", False), ("fixture_only", 1), ("forced_choice_position", None), ("forced_choice_position", "C"), ("grade_ticks_by_position", {"A": 40, "B": None}), ("grade_ticks_by_position", {"A": 40, "B": True})):
            response = MODULE.reduce_events(self.presentation, self.events)
            response[field] = value
            with self.assertRaises(ValueError):
                MODULE.resolve_response(self.assignment, response)

    def test_all_declared_fixtures_balance_positions_within_listener_and_source(self) -> None:
        for scenario in MODULE.SCENARIOS:
            assignments = [MODULE.synthetic_assignment(scenario, listener, source) for listener in range(24) for source in range(12)]
            for key, count, expected in (("listener_index", 24, 6), ("source_index", 12, 12)):
                for index in range(count):
                    self.assertEqual(expected, sum(row[key] == index and row["condition_position"] == "A" for row in assignments))

    def test_numerical_solver_uses_all_pairs_and_retains_positive_and_zero_results(self) -> None:
        expected = [0, 0, -0.5, -1, 4]
        self.assertEqual(expected, [row["signed_crossed_effects_estimate"] for row in self.report["scenarios"]])
        for row in self.report["scenarios"]:
            self.assertEqual((24, 12, 288), (row["listeners"], row["sources"], row["complete_pairs"]))
        self.assertIsNone(self.report["scenarios"][-1]["counterfactual_correct_only_mean"])

    def test_plan_prohibits_authority_changes_target_clipping_and_binding_redirection(self) -> None:
        original = json.loads(MODULE.PLAN.read_text())
        for section, field, value in (("access_boundary", "human_collection_authorized", True), ("access_boundary", "synthetic_execution_only", 1), ("rating_contract", "paired_sdg_range", [-4, 0]), ("rating_contract", "correct_choice_only_filter_allowed", True), ("rating_contract", "legacy_numeric_gates_transferred", True)):
            plan = copy.deepcopy(original)
            plan[section][field] = value
            with mock.patch.object(MODULE.json, "loads", return_value=plan), self.assertRaises(ValueError):
                MODULE.load_plan()
        plan = copy.deepcopy(original)
        plan["bindings"]["predecessor_analysis"]["path"] = "unopened.py"
        with mock.patch.object(MODULE.json, "loads", return_value=plan), self.assertRaises(ValueError):
            MODULE.load_plan()

    def test_replay_is_byte_identical_aggregate_only_and_not_truth(self) -> None:
        expected = MODULE.canonical_bytes(self.report)
        self.assertEqual(expected, MODULE.canonical_bytes(MODULE.build_synthetic_report()))
        self.assertEqual(expected, EVIDENCE.read_bytes())
        for marker in (b"participant-", b"stimulus-", b"session-", b"/Users/", b".wav"):
            self.assertNotIn(marker, expected)
        for field in ("legacy_thresholds_applied", "human_responses_observed", "scientific_gate_evaluated", "live_player_implemented", "objective_complete"):
            self.assertIs(False, self.report[field])

    def test_cli_cannot_accept_response_files(self) -> None:
        for args in ([], ["--synthetic", "--input", "unopened.json"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"", result.stdout)


if __name__ == "__main__":
    unittest.main()
