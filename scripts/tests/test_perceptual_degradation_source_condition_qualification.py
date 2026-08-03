from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "scripts/validate-perceptual-degradation-source-condition-qualification.py"
)
PLAN = (
    REPO_ROOT
    / "benchmarks/perceptual-degradation-v1/source-condition-qualification-plan.json"
)
SPEC = importlib.util.spec_from_file_location("source_condition_qualification", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class SourceConditionQualificationTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_nominal_quality_cannot_assign_transparency_truth(self) -> None:
        value = plan()
        policy = value["codec_condition_candidates"]["ground_truth_policy"]
        policy["nominal_upper_quality_implies_transparency"] = True
        policy["transparency_truth_state"] = "transparent"
        errors = MODULE.validate(value)
        self.assertIn("nominal quality must not imply transparency", errors)
        self.assertIn("transparency truth was assigned before listening", errors)

    def test_consumed_source_cannot_become_a_candidate(self) -> None:
        value = plan()
        candidate = copy.deepcopy(value["source_candidates"][0])
        candidate["source_id"] = "consumed_v1_non_holdout"
        value["source_candidates"].append(candidate)
        self.assertIn(
            "forbidden source candidate: consumed_v1_non_holdout",
            MODULE.validate(value),
        )

    def test_condition_template_must_match_bound_partition(self) -> None:
        value = plan()
        value["codec_condition_candidates"]["development_template_ids"][0] = (
            "transfer-mp3-bladeenc-cbr96-default"
        )
        self.assertIn(
            "condition partition differs: transfer-mp3-bladeenc-cbr96-default",
            MODULE.validate(value),
        )

    def test_access_authority_cannot_expand(self) -> None:
        value = plan()
        value["access_boundary"]["provider_audio_acquisition_authorized"] = True
        self.assertIn(
            "access boundary must remain false: provider_audio_acquisition_authorized",
            MODULE.validate(value),
        )

    def test_incomplete_gates_cannot_be_claimed_complete(self) -> None:
        value = plan()
        value["decision"]["licences_frozen"] = True
        value["decision"]["source_and_condition_manifest_freezable"] = True
        errors = MODULE.validate(value)
        self.assertIn("incomplete decision must remain false: licences_frozen", errors)
        self.assertIn(
            "incomplete decision must remain false: source_and_condition_manifest_freezable",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
