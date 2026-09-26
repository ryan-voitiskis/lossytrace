from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/perceptual_degradation_listening_allocation_v3_audit.py"
)
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-allocation-v3-symbolic-audit-plan.json"
)
REPORT = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-allocation-v3-symbolic-audit-20260814-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_allocation_v3_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ListeningAllocationV3AuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_plan_and_committed_report_validate_and_replay(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(self.report, MODULE.build_report(self.plan))

    def test_report_binds_symbolic_manifest_without_audio_or_responses(self) -> None:
        self.assertEqual(120, self.report["symbolic_manifest_source_group_count"])
        self.assertEqual(840, self.report["symbolic_manifest_stimulus_count"])
        self.assertEqual(240, self.report["symbolic_manifest_trial_count"])
        self.assertFalse(self.report["audio_accessed"])
        self.assertFalse(self.report["audio_generated"])
        self.assertFalse(self.report["listener_responses_opened"])
        self.assertFalse(self.report["human_collection_performed"])

    def test_v3_repairs_all_audited_prefixes_without_cycle_rounding(self) -> None:
        expected = {
            "sources120-subtle3-mushra3": (765, 840),
            "sources120-subtle5-mushra5": (496, 600),
            "sources120-subtle8-mushra6": (345, 360),
            "sources120-subtle15-mushra6": (227, 240),
        }
        audited_prefixes = 0
        for row in self.report["frontier"]:
            self.assertEqual(
                expected[row["option_id"]],
                (
                    row["raw_minimum_eligible_prefix"],
                    row["cycle_rounded_eligible_prefix"],
                ),
            )
            self.assertFalse(row["v2_raw_minimum_prefix_balance_passed"])
            self.assertFalse(row["v2_cycle_rounded_prefix_balance_passed"])
            audit = row["v3_prefix_audit"]
            audited_prefixes += audit["prefixes_audited"]
            self.assertTrue(audit["all_prefixes_balance_gate_passed"])
            self.assertEqual(
                1, audit["maximum_trial_exposure_range_across_all_prefixes"]
            )
            self.assertEqual(
                1,
                audit[
                    "maximum_trial_block_position_range_across_all_prefixes"
                ],
            )
            self.assertEqual(
                1,
                audit["maximum_candidate_position_range_across_all_prefixes"],
            )
            for count in expected[row["option_id"]]:
                checkpoint = audit["checkpoint_summaries"][str(count)]
                self.assertTrue(checkpoint["balance_gate_passed"])
                self.assertLessEqual(
                    checkpoint["trial_exposure_maximum_range"], 1
                )
                self.assertLessEqual(
                    checkpoint["trial_block_position_maximum_range"], 1
                )
                self.assertLessEqual(
                    checkpoint["candidate_position_maximum_range"], 1
                )
        self.assertEqual(2040, audited_prefixes)
        decision = self.report["decision"]
        self.assertFalse(decision["v2_all_raw_prefixes_passed"])
        self.assertFalse(decision["v2_all_cycle_rounded_prefixes_passed"])
        self.assertTrue(decision["v3_all_audited_contiguous_prefixes_passed"])
        self.assertTrue(
            decision[
                "trial_and_candidate_position_scheduling_technically_repaired"
            ]
        )
        self.assertEqual(
            1,
            decision[
                "v3_maximum_trial_block_position_range_across_all_audits"
            ],
        )
        self.assertFalse(
            decision[
                "raw_minimum_prefix_requires_cycle_rounding_for_schedule_balance"
            ]
        )

    def test_report_preserves_operational_and_scientific_boundaries(self) -> None:
        decision = self.report["decision"]
        self.assertEqual(0, decision["qualified_source_group_count"])
        self.assertEqual(0, decision["allocated_source_group_count"])
        false_keys = (
            "missingness_or_post_assignment_exclusion_balance_proven",
            "concurrent_append_only_allocation_state_implemented",
            "restart_recovery_implemented",
            "allocation_policy_selected",
            "operational_design_selected",
            "listener_count_frozen",
            "human_collection_authorized",
            "recruitment_authorized",
            "no_reference_work_eligible",
            "public_verdict_enabled",
        )
        for key in false_keys:
            self.assertFalse(decision[key], key)
        self.assertTrue(
            all(value is False for value in self.report["claim_boundary"].values())
        )

    def test_plan_validation_rejects_authority_policy_and_claim_drift(self) -> None:
        mutations = []
        for section, key, value in (
            ("authorization", "new_audio_acquisition_authorized", True),
            ("authorization", "human_collection_authorized", True),
            ("authorization", "public_verdict_enabled", True),
            ("policy_contract", "operational_policy_selected", True),
            (
                "policy_contract",
                "missingness_or_post_assignment_exclusion_balance_proven",
                True,
            ),
            (
                "policy_contract",
                "maximum_candidate_position_range_at_every_contiguous_prefix",
                2,
            ),
            ("claim_boundary", "prefix_balance_authorizes_collection", True),
        ):
            changed = copy.deepcopy(self.plan)
            changed[section][key] = value
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertTrue(MODULE.validate_plan(changed))

    def test_plan_validation_rejects_binding_and_grid_drift(self) -> None:
        changed_binding = copy.deepcopy(self.plan)
        changed_binding["bindings"]["allocator_v3"]["sha256"] = "0" * 64
        self.assertIn(
            "bound file hash differs: allocator_v3",
            MODULE.validate_plan(changed_binding),
        )
        changed_grid = copy.deepcopy(self.plan)
        changed_grid["audit_grid"][3]["raw_minimum_eligible_prefix"] = 226
        self.assertIn("audit grid differs", MODULE.validate_plan(changed_grid))


if __name__ == "__main__":
    unittest.main()
