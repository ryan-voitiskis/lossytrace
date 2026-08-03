from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "perceptual_degradation_visqol_cross_environment.py"
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "visqol-synthetic-second-environment-plan.json"
)
FIRST_REPLAY = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "visqol-synthetic-replay-observed-20260803-001.json"
)
SECOND_BUILD_OBSERVATION = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "visqol-synthetic-second-build-observed-20260803-001.json"
)
COMPARISON_OBSERVATION = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "visqol-synthetic-cross-environment-observed-20260803-001.json"
)
WORKFLOW = (
    ROOT / ".github" / "workflows" / "visqol-synthetic-second-environment.yml"
)
SPEC = importlib.util.spec_from_file_location("visqol_cross_environment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_visqol_second_environment",
    ROOT
    / "scripts"
    / "validate-perceptual-degradation-visqol-second-environment-plan.py",
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
sys.modules[VALIDATOR_SPEC.name] = VALIDATOR
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)
OBSERVATION_VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_visqol_cross_environment_observation",
    ROOT
    / "scripts"
    / "validate-perceptual-degradation-visqol-cross-environment-observation.py",
)
assert OBSERVATION_VALIDATOR_SPEC and OBSERVATION_VALIDATOR_SPEC.loader
OBSERVATION_VALIDATOR = importlib.util.module_from_spec(OBSERVATION_VALIDATOR_SPEC)
sys.modules[OBSERVATION_VALIDATOR_SPEC.name] = OBSERVATION_VALIDATOR
OBSERVATION_VALIDATOR_SPEC.loader.exec_module(OBSERVATION_VALIDATOR)


class VisqolCrossEnvironmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        self.first = json.loads(FIRST_REPLAY.read_text(encoding="utf-8"))
        self.second_build = json.loads(
            SECOND_BUILD_OBSERVATION.read_text(encoding="utf-8")
        )
        self.comparison = json.loads(
            COMPARISON_OBSERVATION.read_text(encoding="utf-8")
        )

    def test_exact_replay_passes_without_perceptual_claims(self) -> None:
        report = MODULE.compare(self.first, copy.deepcopy(self.first), self.plan)
        self.assertTrue(report["score_determinism_pass"])
        self.assertTrue(report["comparison_complete"])
        self.assertFalse(report["synthetic_scores_are_human_truth"])
        self.assertFalse(report["audibility_or_materiality_threshold_selected"])
        self.assertFalse(report["public_verdict_enabled"])

    def test_second_environment_plan_is_valid_closed_and_synthetic_only(self) -> None:
        self.assertEqual([], VALIDATOR.validate(self.plan))
        self.assertFalse(self.plan["authorization"]["synthetic_fixture_execution"])
        self.assertFalse(
            self.plan["authorization"]["public_or_retained_audio_execution"]
        )
        self.assertEqual(
            "6c7807891cb5cb267649f09fbc20eecc22a3b2f62e50698e38134b2e08d18d5f",
            self.plan["visqol"]["binary_sha256"],
        )
        self.assertTrue(self.plan["visqol"]["synthetic_replay_complete"])
        self.assertEqual(2, len(self.plan["prior_attempts"]))
        self.assertTrue(
            all(
                not attempt["synthetic_scores_produced"]
                for attempt in self.plan["prior_attempts"]
            )
        )

    def test_workflow_binds_nonsemantic_gcc13_compatibility_include(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("push:", source)
        self.assertIn("--cxxopt=-include", source)
        self.assertIn("--cxxopt=cstdint", source)
        self.assertIn("--cxxopt=-DFLATBUFFERS_LOCALE_INDEPENDENT=1", source)
        self.assertIn("--host_cxxopt=-include", source)
        self.assertIn("--host_cxxopt=cstdint", source)
        self.assertIn(
            "--host_cxxopt=-DFLATBUFFERS_LOCALE_INDEPENDENT=1", source
        )

    def test_plan_rejects_perceptual_threshold_or_retained_authorization(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["authorization"]["retained_audio_access"] = True
        changed["cross_environment_comparison"][
            "tolerance_is_audibility_or_materiality_threshold"
        ] = True
        errors = VALIDATOR.validate(changed)
        self.assertIn("authorization.retained_audio_access must remain false", errors)
        self.assertIn(
            "numeric tolerance must not be a perceptual threshold", errors
        )

    def test_delta_beyond_frozen_tolerance_fails(self) -> None:
        second = copy.deepcopy(self.first)
        second["results"][0]["mos_lqo"] += 2e-12
        report = MODULE.compare(self.first, second, self.plan)
        self.assertFalse(report["score_determinism_pass"])
        identity = next(
            item for item in report["results"] if item["case_id"] == "synthetic-identity"
        )
        self.assertFalse(identity["within_frozen_tolerance"])

    def test_case_or_fixture_drift_is_rejected(self) -> None:
        second = copy.deepcopy(self.first)
        second["fixture_set_id"] = "different"
        with self.assertRaisesRegex(ValueError, "fixture set differs"):
            MODULE.compare(self.first, second, self.plan)

    def test_observed_cross_environment_result_is_exact_and_bounded(self) -> None:
        self.assertEqual(
            [], OBSERVATION_VALIDATOR.validate(self.second_build, self.comparison)
        )
        self.assertTrue(self.comparison["score_determinism_pass"])
        self.assertEqual(
            0,
            self.second_build["synthetic_replay_summary"][
                "maximum_observed_absolute_delta"
            ],
        )
        self.assertFalse(
            self.second_build["boundaries"]["synthetic_scores_are_human_truth"]
        )
        self.assertFalse(
            self.comparison["audibility_or_materiality_threshold_selected"]
        )

    def test_observation_rejects_nonzero_delta_or_retained_access(self) -> None:
        changed_build = copy.deepcopy(self.second_build)
        changed_comparison = copy.deepcopy(self.comparison)
        changed_build["boundaries"]["retained_audio_accessed"] = True
        changed_comparison["results"][0]["absolute_deltas"]["mos_lqo"] = 1e-13
        errors = OBSERVATION_VALIDATOR.validate(changed_build, changed_comparison)
        self.assertIn(
            "second build boundary must remain false: retained_audio_accessed",
            errors,
        )
        self.assertIn(
            "comparison delta is nonzero: synthetic-bandwidth-loss", errors
        )


if __name__ == "__main__":
    unittest.main()
