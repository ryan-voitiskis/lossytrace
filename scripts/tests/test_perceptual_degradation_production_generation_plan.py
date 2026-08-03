from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-perceptual-degradation-production-generation-plan.py"
PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/production-generation-control-plan.json"
)
SPEC = importlib.util.spec_from_file_location("production_generation_plan", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ProductionGenerationPlanTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_recipe_cannot_assign_perceptual_truth(self) -> None:
        value = plan()
        value["production_control_recipes"][0]["perceptual_truth"] = "material"
        value["input_contract"]["condition_truth_state"] = "transparent"
        errors = MODULE.validate(value)
        self.assertIn("condition truth was assigned before listening", errors)
        self.assertIn(
            "production recipe truth or algorithm differs: production-hard-clip-minus6dbfs-v1",
            errors,
        )

    def test_cross_codec_recipe_must_use_distinct_bound_codecs(self) -> None:
        value = plan()
        recipe = next(
            item
            for item in value["codec_generation_recipes"]
            if item["family"] == "cross_codec_generation"
        )
        recipe["expanded_setting_ids"][1] = recipe["expanded_setting_ids"][0]
        self.assertIn(
            f"cross-codec recipe repeats a codec: {recipe['recipe_id']}",
            MODULE.validate(value),
        )

    def test_repeated_recipe_must_repeat_exact_setting(self) -> None:
        value = plan()
        recipe = next(
            item
            for item in value["codec_generation_recipes"]
            if item["family"] == "repeated_same_codec" and "mp3" in item["recipe_id"]
        )
        recipe["expanded_setting_ids"][1] = "dev-mp3-lame-cbr96-default--stereo"
        self.assertIn(
            f"repeated-codec recipe differs: {recipe['recipe_id']}",
            MODULE.validate(value),
        )

    def test_access_and_completion_cannot_expand(self) -> None:
        value = plan()
        value["access_boundary"]["stimulus_generation_authorized"] = True
        value["decision"]["synthetic_replay_complete"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "access boundary must remain false: stimulus_generation_authorized", errors
        )
        self.assertIn("premature recipe completion: synthetic_replay_complete", errors)

    def test_intermediate_resampler_is_exact_and_dither_free(self) -> None:
        value = plan()
        resampler = value["codec_generation_execution"]["intermediate_resampler"]
        resampler["filter_template"] = "aresample={target}"
        resampler["dither_applied"] = True
        errors = MODULE.validate(value)
        self.assertIn("intermediate resampler filter differs", errors)
        self.assertIn(
            "intermediate resampler boundary differs: dither_applied", errors
        )


if __name__ == "__main__":
    unittest.main()
