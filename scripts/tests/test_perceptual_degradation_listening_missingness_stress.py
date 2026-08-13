from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/perceptual_degradation_listening_missingness_stress.py"
)
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-missingness-stress-plan.json"
)
REPORT = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-missingness-stress-20260814-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_missingness_stress", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ListeningMissingnessStressTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_plan_and_committed_report_validate_and_replay(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(self.report, MODULE.build_report(self.plan))

    def test_report_preserves_no_outcome_and_no_collection_boundary(self) -> None:
        for key in (
            "audio_accessed",
            "audio_generated",
            "listener_identities_accessed",
            "outcome_values_generated",
            "outcome_values_read",
            "human_collection_performed",
        ):
            self.assertFalse(self.report[key], key)
        self.assertTrue(
            all(value is False for value in self.report["claim_boundary"].values())
        )

    def test_complete_and_contiguous_prefixes_preserve_v3_balance(self) -> None:
        expected_counts = {
            "sources120-subtle3-mushra3": (765, 688),
            "sources120-subtle5-mushra5": (496, 446),
            "sources120-subtle8-mushra6": (345, 310),
            "sources120-subtle15-mushra6": (227, 204),
        }
        for option in self.report["options"]:
            by_id = {
                item["scenario_id"]: item
                for item in option["scenario_results"]
            }
            complete = by_id["complete-issued-prefix"]["summary"]
            prefix = by_id["contiguous-session-prefix-90"]["summary"]
            self.assertEqual(
                expected_counts[option["option_id"]],
                (
                    complete["scheduled_session_slots"],
                    prefix["session_slots_with_any_retained_trial"],
                ),
            )
            for summary in (complete, prefix):
                self.assertTrue(
                    summary["all_methods_strict_retained_balance_gate_passed"]
                )
                self.assertTrue(
                    summary["all_methods_minimum_judgment_support_gate_passed"]
                )
                for method in ("subtle", "mushra"):
                    values = summary["methods"][method]
                    self.assertLessEqual(values["trial_exposure_range"], 1)
                    self.assertLessEqual(
                        values["trial_block_position_maximum_range"], 1
                    )
                    self.assertLessEqual(
                        values["candidate_position_maximum_range"], 1
                    )
                    self.assertEqual(120, values["source_groups_retained"])

    def test_mcar_replicates_do_not_preserve_strict_schedule_balance(self) -> None:
        expected_support_passes = {
            "sources120-subtle3-mushra3": (256, 256),
            "sources120-subtle5-mushra5": (256, 256),
            "sources120-subtle8-mushra6": (256, 256),
            "sources120-subtle15-mushra6": (200, 40),
        }
        replicate_total = 0
        strict_pass_total = 0
        for option in self.report["options"]:
            by_id = {
                item["scenario_id"]: item
                for item in option["scenario_results"]
            }
            session = by_id["hash-mcar-session-90"]["aggregate"]
            trial = by_id["hash-mcar-trial-90"]["aggregate"]
            self.assertEqual(
                expected_support_passes[option["option_id"]],
                (
                    session["minimum_judgment_support_gate_pass_count"],
                    trial["minimum_judgment_support_gate_pass_count"],
                ),
            )
            for aggregate in (session, trial):
                replicate_total += aggregate["replicate_count"]
                strict_pass_total += aggregate[
                    "strict_retained_balance_gate_pass_count"
                ]
                self.assertEqual(256, aggregate["replicate_count"])
                self.assertEqual(
                    0, aggregate["strict_retained_balance_gate_pass_count"]
                )
                for method in ("subtle", "mushra"):
                    self.assertGreater(
                        aggregate["methods"][method]["trial_exposure_range"][
                            "p95"
                        ],
                        1,
                    )
                    self.assertGreater(
                        aggregate["methods"][method][
                            "candidate_position_maximum_range"
                        ]["p95"],
                        1,
                    )
        self.assertEqual(2048, replicate_total)
        self.assertEqual(0, strict_pass_total)

    def test_structured_masks_expose_position_and_source_failure(self) -> None:
        for option in self.report["options"]:
            by_id = {
                item["scenario_id"]: item
                for item in option["scenario_results"]
            }
            phase = by_id["exposure-phase-every-tenth"]["summary"]
            source = by_id["source-correlated-10-percent"]["summary"]
            self.assertFalse(
                phase["all_methods_strict_retained_balance_gate_passed"]
            )
            self.assertGreater(
                max(
                    phase["methods"][method][
                        "candidate_position_maximum_range"
                    ]
                    for method in ("subtle", "mushra")
                ),
                1,
            )
            self.assertFalse(
                source["all_methods_minimum_judgment_support_gate_passed"]
            )
            for method in ("subtle", "mushra"):
                self.assertEqual(
                    108, source["methods"][method]["source_groups_retained"]
                )
                self.assertEqual(
                    12,
                    source["methods"][method][
                        "source_groups_with_zero_judgments"
                    ],
                )

    def test_decision_does_not_promote_a_missingness_mechanism_or_fix(self) -> None:
        decision = self.report["decision"]
        self.assertTrue(decision["v3_complete_issued_prefixes_pass"])
        self.assertTrue(
            decision["contiguous_90_percent_session_prefixes_pass_balance"]
        )
        self.assertTrue(decision["v3_issued_schedule_repair_remains_valid"])
        self.assertTrue(
            decision["power_recalculation_required_for_structured_missingness"]
        )
        for key in (
            "all_mcar_replicates_preserve_strict_balance",
            "all_structured_stresses_preserve_strict_balance",
            "scalar_90_percent_usable_rate_proves_retained_balance",
            "scalar_90_percent_usable_rate_proves_source_support",
            "mcar_mechanism_empirically_established",
            "post_assignment_missingness_policy_ready",
            "missing_response_imputation_selected",
            "inverse_probability_weighting_selected",
            "replacement_assignment_selected",
            "exclusion_policy_selected",
            "allocation_policy_selected",
            "operational_design_selected",
            "listener_count_frozen",
            "human_collection_authorized",
            "recruitment_authorized",
            "no_reference_work_eligible",
            "public_verdict_enabled",
        ):
            self.assertFalse(decision[key], key)

    def test_plan_validation_rejects_authority_assumption_and_claim_drift(self) -> None:
        mutations = []
        for section, key, value in (
            ("authorization", "observed_response_access_authorized", True),
            ("authorization", "human_collection_authorized", True),
            ("authorization", "public_verdict_enabled", True),
            ("stress_contract", "usable_trial_rate", 0.95),
            ("stress_contract", "mcar_replicates", 32),
            ("stress_contract", "missing_response_imputation_selected", True),
            ("claim_boundary", "mcar_replay_proves_mcar_in_collection", True),
        ):
            changed = copy.deepcopy(self.plan)
            changed[section][key] = value
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertTrue(MODULE.validate_plan(changed))

    def test_plan_validation_rejects_binding_scenario_and_option_drift(self) -> None:
        changed_binding = copy.deepcopy(self.plan)
        changed_binding["bindings"]["allocator_v3"]["sha256"] = "0" * 64
        self.assertIn(
            "bound file hash differs: allocator_v3",
            MODULE.validate_plan(changed_binding),
        )
        changed_scenario = copy.deepcopy(self.plan)
        changed_scenario["scenarios"].pop()
        self.assertIn("scenario inventory differs", MODULE.validate_plan(changed_scenario))
        changed_option = copy.deepcopy(self.plan)
        changed_option["frontier_options"][3]["eligible_prefix"] = 226
        self.assertIn("frontier options differ", MODULE.validate_plan(changed_option))


if __name__ == "__main__":
    unittest.main()
