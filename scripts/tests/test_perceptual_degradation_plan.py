from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-perceptual-degradation-plan.py"
PLAN_PATH = ROOT / "benchmarks" / "perceptual-degradation-v1" / "research-plan.json"
SPEC = importlib.util.spec_from_file_location("perceptual_degradation_plan", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class PerceptualDegradationPlanTest(unittest.TestCase):
    def test_frozen_plan_is_valid_and_verdict_free(self) -> None:
        self.assertEqual([], MODULE.validate(PLAN))
        self.assertFalse(PLAN["public_state"]["public_verdict_enabled"])
        self.assertFalse(PLAN["score_access"]["retained_metric_scores_opened"])
        self.assertFalse(PLAN["human_truth"]["main_collection_authorized"])

    def test_exact_two_metric_families_are_bound(self) -> None:
        families = PLAN["primary_metric_families"]
        self.assertEqual(2, len(families))
        self.assertEqual(
            {"visqol_audio_v3_3_3", "gstpeaq_proxy_v0_6_1"},
            {family["family_id"] for family in families},
        )

    def test_contract_and_literature_review_are_hash_bound(self) -> None:
        for binding in PLAN["bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], MODULE.sha256_file(path))

    def test_validator_rejects_score_access_and_public_verdict(self) -> None:
        changed = copy.deepcopy(PLAN)
        changed["score_access"]["sealed_labels_opened"] = True
        changed["public_state"]["public_verdict_enabled"] = True
        errors = MODULE.validate(changed)
        self.assertIn("score_access.sealed_labels_opened must be false", errors)
        self.assertIn("public verdict must remain disabled", errors)

    def test_validator_preserves_transparent_lossy_negatives(self) -> None:
        changed = copy.deepcopy(PLAN)
        changed["required_negative_classes"].remove("transparent_lossy_encode")
        self.assertIn(
            "transparent lossy encodes must remain negative controls",
            MODULE.validate(changed),
        )

    def test_validator_enforces_resource_limits(self) -> None:
        changed = copy.deepcopy(PLAN)
        changed["resources"]["sustained_worker_limit"] = 7
        changed["resources"]["minimum_free_disk_gib"] = 14
        errors = MODULE.validate(changed)
        self.assertIn("sustained worker limit must not exceed 6", errors)
        self.assertIn("minimum free disk reserve must be at least 15 GiB", errors)


if __name__ == "__main__":
    unittest.main()
