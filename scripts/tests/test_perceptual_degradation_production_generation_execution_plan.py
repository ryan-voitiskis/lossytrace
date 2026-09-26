from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/validate-perceptual-degradation-production-generation-execution-plan.py"
)
PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/production-generation-execution-plan.json"
)
SPEC = importlib.util.spec_from_file_location("production_generation_execution", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ProductionGenerationExecutionPlanTest(unittest.TestCase):
    def test_committed_execution_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_actual_audio_and_outcomes_cannot_be_authorized(self) -> None:
        value = plan()
        value["authority"]["actual_source_audio_authorized"] = True
        value["outcome_boundary"]["perceptual_truth_included"] = True
        errors = MODULE.validate(value)
        self.assertIn("execution authority differs", errors)
        self.assertIn(
            "outcome boundary differs: perceptual_truth_included", errors
        )

    def test_case_set_must_match_all_frozen_recipes(self) -> None:
        value = plan()
        value["synthetic_cases"][-1] = value["synthetic_cases"][0]
        errors = MODULE.validate(value)
        self.assertIn("exactly 12 unique synthetic cases are required", errors)
        self.assertIn("synthetic case set differs from recipe plan", errors)

    def test_two_fresh_byte_identical_replays_are_required(self) -> None:
        value = plan()
        value["replay_protocol"]["replay_count"] = 1
        value["replay_protocol"]["path_free_reports_required"] = False
        self.assertIn("replay protocol differs", MODULE.validate(value))

    def test_execution_cannot_be_premarked_observed(self) -> None:
        value = plan()
        value["decision"]["synthetic_execution_observed"] = True
        self.assertIn(
            "premature execution completion: synthetic_execution_observed",
            MODULE.validate(value),
        )


if __name__ == "__main__":
    unittest.main()
