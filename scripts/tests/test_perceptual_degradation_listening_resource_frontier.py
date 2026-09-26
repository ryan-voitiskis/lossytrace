from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_listening_resource_frontier.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-operational-resource-frontier-plan.json"
)
REPORT = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-operational-resource-frontier-20260814-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_resource_frontier", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ListeningResourceFrontierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_plan_and_committed_report_validate_and_replay(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(self.report, MODULE.build_report(self.plan))

    def test_symbolic_manifest_has_structure_but_no_audio(self) -> None:
        manifest = MODULE.make_symbolic_manifest(self.plan)
        self.assertEqual([], MODULE.ALLOCATOR.validate_manifest(manifest))
        self.assertEqual(120, len({item["source_group_id"] for item in manifest["stimuli"]}))
        self.assertEqual(840, len(manifest["stimuli"]))
        self.assertEqual(240, len(manifest["trials"]))
        self.assertFalse(manifest["human_collection_authorized"])
        self.assertNotIn("private_audio_sha256", json.dumps(manifest))
        self.assertTrue(
            all(
                item["delivery"]["delivery_class"] == "generated_synthetic"
                for item in manifest["stimuli"]
            )
        )

    def test_listener_slot_frontier_and_cycle_sensitivity_are_exact(self) -> None:
        expected = {
            3: (765, 1185, 840, 1301, 5204),
            5: (496, 768, 600, 929, 3716),
            8: (345, 535, 360, 558, 2232),
            15: (227, 352, 240, 372, 1488),
        }
        self.assertEqual(4, len(self.report["frontier"]))
        for row in self.report["frontier"]:
            subtle = row["transparent_trials_per_eligible_listener"]
            self.assertEqual(
                expected[subtle],
                (
                    row[
                        "minimum_eligible_listener_slots_per_stratum_device_partition"
                    ],
                    row[
                        "minimum_enrolled_listener_slots_per_stratum_device_partition"
                    ],
                    row[
                        "cycle_rounded_eligible_listener_slots_per_stratum_device_partition"
                    ],
                    row[
                        "cycle_rounded_enrolled_listener_slots_per_stratum_device_partition"
                    ],
                    row[
                        "cycle_rounded_enrolled_listener_slots_for_four_partitions"
                    ],
                ),
            )
        decision = self.report["decision"]
        self.assertEqual(
            1408,
            decision[
                "minimum_enrolled_listener_slots_for_four_partitions_at_protocol_caps"
            ],
        )
        self.assertEqual(
            1488,
            decision[
                "minimum_cycle_rounded_enrolled_listener_slots_for_four_"
                "partitions_at_protocol_caps"
            ],
        )

    def test_allocator_replay_fails_closed_on_candidate_position_balance(self) -> None:
        expected_raw_ranges = {
            3: (3, 3, 7, 7),
            5: (5, 5, 5, 5),
            8: (8, 6, 1, 3),
            15: (13, 6, 3, 2),
        }
        expected_cycle_position_ranges = {
            3: (7, 7),
            5: (5, 5),
            8: (0, 3),
            15: (2, 2),
        }
        for row in self.report["frontier"]:
            subtle = row["transparent_trials_per_eligible_listener"]
            raw = row["minimum_eligible_prefix_balance"]
            cycle = row["cycle_rounded_eligible_prefix_balance"]
            self.assertEqual(
                expected_raw_ranges[subtle],
                (
                    raw["subtle_trial_exposure_range"],
                    raw["mushra_trial_exposure_range"],
                    raw["subtle_candidate_position_maximum_range"],
                    raw["mushra_candidate_position_maximum_range"],
                ),
            )
            self.assertEqual(0, cycle["subtle_trial_exposure_range"])
            self.assertEqual(0, cycle["mushra_trial_exposure_range"])
            self.assertEqual(
                expected_cycle_position_ranges[subtle],
                (
                    cycle["subtle_candidate_position_maximum_range"],
                    cycle["mushra_candidate_position_maximum_range"],
                ),
            )
            self.assertFalse(row["minimum_eligible_prefix_balance_passes"])
            self.assertFalse(row["cycle_rounded_eligible_prefix_balance_passes"])
            self.assertFalse(row["selected"])
        decision = self.report["decision"]
        self.assertFalse(decision["all_raw_minimum_prefixes_pass_balance_audit"])
        self.assertFalse(decision["all_cycle_rounded_prefixes_pass_balance_audit"])
        self.assertTrue(
            decision["all_cycle_rounded_trial_exposures_pass_balance_audit"]
        )
        self.assertTrue(
            decision["allocator_successor_required_for_candidate_position_balance"]
        )

    def test_report_preserves_authorization_and_claim_boundaries(self) -> None:
        self.assertFalse(self.report["audio_accessed"])
        self.assertFalse(self.report["audio_generated"])
        self.assertFalse(self.report["listener_responses_opened"])
        self.assertFalse(self.report["human_collection_performed"])
        decision = self.report["decision"]
        self.assertEqual(0, decision["qualified_source_group_count"])
        self.assertEqual(0, decision["allocated_source_group_count"])
        for key in (
            "cycle_rounded_sensitivity_selected",
            "allocation_policy_frozen",
            "missingness_balance_proven",
            "listener_count_frozen",
            "operational_design_selected",
            "session_timing_qualified",
            "human_collection_authorized",
            "recruitment_authorized",
            "no_reference_work_eligible",
            "public_verdict_enabled",
        ):
            self.assertFalse(decision[key], key)
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))

    def test_plan_validation_rejects_authority_and_claim_drift(self) -> None:
        mutations = []
        for section, key, value in (
            ("authorization", "new_audio_acquisition_authorized", True),
            ("authorization", "human_collection_authorized", True),
            ("authorization", "public_verdict_enabled", True),
            ("symbolic_fixture", "contains_audio", True),
            ("design_grid", "selected_design_option", "sources120-subtle15-mushra6"),
            ("balance_audit", "maximum_candidate_position_range", 2),
            ("claim_boundary", "resource_frontier_is_listening_evidence", True),
        ):
            changed = copy.deepcopy(self.plan)
            changed[section][key] = value
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertTrue(MODULE.validate_plan(changed))


if __name__ == "__main__":
    unittest.main()
