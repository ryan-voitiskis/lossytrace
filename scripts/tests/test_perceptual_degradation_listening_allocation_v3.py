from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V1_SCRIPT = ROOT / "scripts/perceptual_degradation_listening_allocation.py"
V2_SCRIPT = ROOT / "scripts/perceptual_degradation_listening_allocation_v2.py"
V3_SCRIPT = ROOT / "scripts/perceptual_degradation_listening_allocation_v3.py"
RESOURCE_SCRIPT = (
    ROOT / "scripts/perceptual_degradation_listening_resource_frontier.py"
)
RESOURCE_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-operational-resource-frontier-plan.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module("listening_allocation_v3", V3_SCRIPT)
RESOURCE = load_module("listening_resource_frontier_for_v3", RESOURCE_SCRIPT)


class ListeningAllocationV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(RESOURCE_PLAN.read_text(encoding="utf-8"))
        cls.manifest = RESOURCE.make_symbolic_manifest(cls.plan)
        cls.seed = cls.plan["symbolic_fixture"]["allocation_seed"]

    def test_historical_allocators_remain_byte_bound(self) -> None:
        self.assertEqual(
            "2fbe6a0782e6f7652bf60924f27141c511402adea6d0bbb532c4b371edb7d2fc",
            hashlib.sha256(V1_SCRIPT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            "8895f8cc3900f776a62c15fb115b674820ba24cdee18772f48399f1d3ea6ea12",
            hashlib.sha256(V2_SCRIPT.read_bytes()).hexdigest(),
        )

    def test_assignment_is_deterministic_blind_and_limit_bound(self) -> None:
        first = MODULE.allocate(
            self.manifest,
            "private-participant-key",
            self.seed,
            227,
            subtle_trial_limit=15,
            mushra_trial_limit=6,
        )
        second = MODULE.allocate(
            copy.deepcopy(self.manifest),
            "private-participant-key",
            self.seed,
            227,
            subtle_trial_limit=15,
            mushra_trial_limit=6,
        )
        self.assertEqual(first, second)
        self.assertEqual(3, first["schema_version"])
        self.assertEqual(2, first["manifest_schema_version"])
        self.assertEqual(MODULE.POLICY_ID, first["allocation_policy_id"])
        self.assertEqual({"subtle": 15, "mushra": 6}, first["trial_limits"])
        self.assertTrue(first["contiguous_post_eligibility_indexing_required"])
        self.assertFalse(first["operational_policy_selected"])
        self.assertFalse(first["human_collection_authorized"])
        self.assertFalse(first["participant_key_included"])
        self.assertFalse(first["condition_recipes_included"])
        self.assertFalse(first["metric_scores_included"])
        self.assertFalse(first["responses_included"])
        encoded = json.dumps(first)
        self.assertNotIn("private-participant-key", encoded)
        self.assertNotIn("condition_class", encoded)
        self.assertNotIn("recipe_id", encoded)

    def test_blocks_have_exact_limits_and_no_duplicate_trial(self) -> None:
        for allocation_index in range(120):
            assignment = MODULE.allocate(
                self.manifest,
                f"participant-{allocation_index}",
                self.seed,
                allocation_index,
                subtle_trial_limit=8,
                mushra_trial_limit=6,
            )
            self.assertEqual(["subtle", "mushra"], [b["method"] for b in assignment["blocks"]])
            for block, expected_limit in zip(assignment["blocks"], (8, 6)):
                trial_ids = [trial["trial_id"] for trial in block["trials"]]
                self.assertEqual(expected_limit, block["trial_limit"])
                self.assertEqual(expected_limit, len(trial_ids))
                self.assertEqual(len(trial_ids), len(set(trial_ids)))

    def test_one_method_may_be_disabled_without_weakening_enabled_balance(self) -> None:
        assignment = MODULE.allocate(
            self.manifest,
            "participant",
            self.seed,
            4,
            subtle_trial_limit=15,
            mushra_trial_limit=0,
        )
        self.assertEqual(
            ["subtle"], [block["method"] for block in assignment["blocks"]]
        )
        audit = MODULE.audit_prefixes(
            self.manifest,
            40,
            [40],
            self.seed,
            subtle_trial_limit=15,
            mushra_trial_limit=0,
        )
        self.assertTrue(audit["all_prefixes_balance_gate_passed"])
        self.assertEqual(
            0,
            audit["checkpoint_summaries"]["40"]["methods"]["mushra"][
                "trial_limit"
            ],
        )

    def test_every_frontier_prefix_passes_balance_gate(self) -> None:
        options = (
            (3, 3, 765, 840),
            (5, 5, 496, 600),
            (8, 6, 345, 360),
            (15, 6, 227, 240),
        )
        for subtle, mushra, raw, cycle in options:
            with self.subTest(subtle=subtle, mushra=mushra):
                audit = MODULE.audit_prefixes(
                    self.manifest,
                    cycle,
                    [raw, cycle],
                    self.seed,
                    subtle_trial_limit=subtle,
                    mushra_trial_limit=mushra,
                )
                self.assertEqual(cycle, audit["prefixes_audited"])
                self.assertTrue(audit["all_prefixes_balance_gate_passed"])
                self.assertEqual(
                    1,
                    audit["maximum_trial_exposure_range_across_all_prefixes"],
                )
                self.assertEqual(
                    1,
                    audit[
                        "maximum_trial_block_position_range_across_all_prefixes"
                    ],
                )
                self.assertEqual(
                    1,
                    audit[
                        "maximum_candidate_position_range_across_all_prefixes"
                    ],
                )
                for checkpoint in (raw, cycle):
                    summary = audit["checkpoint_summaries"][str(checkpoint)]
                    self.assertTrue(summary["balance_gate_passed"])
                    self.assertLessEqual(
                        summary["trial_exposure_maximum_range"], 1
                    )
                    self.assertLessEqual(
                        summary["trial_block_position_maximum_range"], 1
                    )
                    self.assertLessEqual(
                        summary["candidate_position_maximum_range"], 1
                    )

    def test_raw_protocol_cap_prefix_is_balanced_without_cycle_rounding(self) -> None:
        balance = MODULE.audit_balance(
            self.manifest,
            227,
            self.seed,
            subtle_trial_limit=15,
            mushra_trial_limit=6,
        )
        self.assertTrue(balance["balance_gate_passed"])
        self.assertEqual(1, balance["trial_exposure_maximum_range"])
        self.assertEqual(1, balance["trial_block_position_maximum_range"])
        self.assertEqual(1, balance["candidate_position_maximum_range"])
        self.assertEqual(
            (28, 29),
            (
                balance["methods"]["subtle"]["trial_exposure_min"],
                balance["methods"]["subtle"]["trial_exposure_max"],
            ),
        )
        self.assertEqual(
            (11, 12),
            (
                balance["methods"]["mushra"]["trial_exposure_min"],
                balance["methods"]["mushra"]["trial_exposure_max"],
            ),
        )

    def test_non_120_trial_and_five_candidate_case_remains_balanced(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        retained_groups = {
            f"symbolic-source-{index:03d}" for index in range(12)
        }
        manifest["stimuli"] = [
            item
            for item in manifest["stimuli"]
            if item["source_group_id"] in retained_groups
        ]
        manifest["trials"] = [
            trial
            for trial in manifest["trials"]
            if int(trial["trial_id"].rsplit("-", 1)[1]) < 12
        ]
        by_id = {item["stimulus_id"]: item for item in manifest["stimuli"]}
        added = []
        for trial in manifest["trials"]:
            if trial["method"] != "mushra":
                continue
            original_id = next(
                candidate_id
                for candidate_id in trial["candidate_ids"]
                if candidate_id.endswith("mushra-condition")
            )
            clone = copy.deepcopy(by_id[original_id])
            clone["stimulus_id"] = original_id + "-alternate"
            added.append(clone)
            trial["candidate_ids"].append(clone["stimulus_id"])
        manifest["stimuli"].extend(added)
        self.assertEqual([], MODULE.validate_manifest(manifest))

        audit = MODULE.audit_prefixes(
            manifest,
            37,
            [1, 7, 13, 37],
            self.seed,
            subtle_trial_limit=3,
            mushra_trial_limit=4,
        )
        self.assertTrue(audit["all_prefixes_balance_gate_passed"])
        self.assertEqual(
            1, audit["maximum_trial_exposure_range_across_all_prefixes"]
        )
        self.assertEqual(
            1,
            audit["maximum_trial_block_position_range_across_all_prefixes"],
        )
        self.assertEqual(
            1,
            audit["maximum_candidate_position_range_across_all_prefixes"],
        )

    def test_limit_and_index_failures_are_closed(self) -> None:
        cases = (
            ({"subtle_trial_limit": -1, "mushra_trial_limit": 6}, "between"),
            ({"subtle_trial_limit": 16, "mushra_trial_limit": 6}, "between"),
            ({"subtle_trial_limit": 15, "mushra_trial_limit": 7}, "between"),
            ({"subtle_trial_limit": 0, "mushra_trial_limit": 0}, "enabled"),
            ({"subtle_trial_limit": True, "mushra_trial_limit": 6}, "integer"),
        )
        non_divisible = copy.deepcopy(self.manifest)
        non_divisible["trials"] = [
            trial
            for trial in non_divisible["trials"]
            if trial["method"] != "subtle" or not trial["trial_id"].endswith("119")
        ]
        with self.assertRaisesRegex(ValueError, "divisible"):
            MODULE.allocate(
                non_divisible,
                "participant",
                self.seed,
                0,
                subtle_trial_limit=15,
                mushra_trial_limit=6,
            )
        for limits, message in cases:
            with self.subTest(limits=limits):
                with self.assertRaisesRegex(ValueError, message):
                    MODULE.allocate(
                        self.manifest,
                        "participant",
                        self.seed,
                        0,
                        **limits,
                    )
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            MODULE.allocate(
                self.manifest,
                "participant",
                self.seed,
                -1,
                subtle_trial_limit=15,
                mushra_trial_limit=6,
            )
        for invalid_index in (True, 1.5):
            with self.assertRaisesRegex(ValueError, "non-negative integer"):
                MODULE.allocate(
                    self.manifest,
                    "participant",
                    self.seed,
                    invalid_index,
                    subtle_trial_limit=15,
                    mushra_trial_limit=6,
                )
        with self.assertRaisesRegex(ValueError, "participant key"):
            MODULE.allocate(
                self.manifest,
                "",
                self.seed,
                0,
                subtle_trial_limit=15,
                mushra_trial_limit=6,
            )
        with self.assertRaisesRegex(ValueError, "allocation seed"):
            MODULE.allocate(
                self.manifest,
                "participant",
                "",
                0,
                subtle_trial_limit=15,
                mushra_trial_limit=6,
            )
        with self.assertRaisesRegex(ValueError, "allocation seed"):
            MODULE.allocate(
                self.manifest,
                "participant",
                3,
                0,
                subtle_trial_limit=15,
                mushra_trial_limit=6,
            )

    def test_prefix_checkpoints_fail_closed(self) -> None:
        cases = (
            ([], "within"),
            ([0], "within"),
            ([11], "within"),
            ([5, 5], "unique"),
        )
        for checkpoints, message in cases:
            with self.subTest(checkpoints=checkpoints):
                with self.assertRaisesRegex(ValueError, message):
                    MODULE.audit_prefixes(
                        self.manifest,
                        10,
                        checkpoints,
                        self.seed,
                        subtle_trial_limit=3,
                        mushra_trial_limit=3,
                    )
        for maximum in (0, True, 1.5):
            with self.assertRaisesRegex(ValueError, "positive integer"):
                MODULE.audit_prefixes(
                    self.manifest,
                    maximum,
                    [1],
                    self.seed,
                    subtle_trial_limit=3,
                    mushra_trial_limit=3,
                )

    def test_serialization_contains_assignment_only(self) -> None:
        assignment = MODULE.allocate(
            self.manifest,
            "participant",
            self.seed,
            4,
            subtle_trial_limit=3,
            mushra_trial_limit=3,
        )
        encoded = MODULE.serialize_assignment(assignment, "javascript")
        self.assertTrue(encoded.startswith('"use strict";'))
        self.assertIn("globalThis.LOSSYTRACE_ASSIGNMENT", encoded)
        self.assertNotIn("participant\"", encoded)
        self.assertNotIn("condition_class", encoded)


if __name__ == "__main__":
    unittest.main()
