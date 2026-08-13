from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validate-perceptual-degradation-visqol-only-successor-readiness.py"
)
DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "visqol-only-successor-readiness-disposition.json"
)
SPEC = importlib.util.spec_from_file_location("visqol_successor_readiness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def disposition() -> dict:
    return json.loads(DISPOSITION.read_text(encoding="utf-8"))


class VisqolOnlySuccessorReadinessTest(unittest.TestCase):
    def test_committed_disposition_validates(self) -> None:
        self.assertEqual([], MODULE.validate(disposition()))

    def test_readiness_cannot_select_or_authorize_successor(self) -> None:
        value = disposition()
        value["decision"]["selected_successor_option"] = (
            "preregister_visqol_only_full_reference_candidate"
        )
        value["decision"]["execution_authorized_by_this_disposition"] = True
        errors = MODULE.validate(value)
        self.assertIn("successor option was prematurely selected", errors)
        self.assertIn("disposition cannot authorize execution", errors)

    def test_synthetic_replay_cannot_become_scientific_readiness(self) -> None:
        value = disposition()
        value["readiness"]["scientific_readiness"] = True
        value["claim_boundary"]["synthetic_replay_proves_perceptual_validity"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "readiness finding must remain false: scientific_readiness", errors
        )
        self.assertIn(
            "claim boundary must remain false: synthetic_replay_proves_perceptual_validity",
            errors,
        )

    def test_mos_cannot_be_promoted_to_lossytrace_truth(self) -> None:
        value = disposition()
        value["claim_boundary"]["mos_lqo_is_lossytrace_audibility_probability"] = True
        value["claim_boundary"]["mos_lqo_is_lossytrace_materiality_truth"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "claim boundary must remain false: mos_lqo_is_lossytrace_audibility_probability",
            errors,
        )
        self.assertIn(
            "claim boundary must remain false: mos_lqo_is_lossytrace_materiality_truth",
            errors,
        )

    def test_stereo_claim_and_artifact_truth_remain_forbidden(self) -> None:
        value = disposition()
        value["readiness"]["stereo_profile_supported_by_visqol"] = True
        value["artifact_profile_boundary"][
            "patch_or_frequency_similarity_may_be_used_as_truth_labels"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "readiness finding must remain false: stereo_profile_supported_by_visqol",
            errors,
        )
        self.assertIn(
            "similarity diagnostics cannot become artifact truth", errors
        )

    def test_artifact_components_remain_null_until_calibrated(self) -> None:
        value = disposition()
        value["artifact_profile_boundary"]["bandwidth_loss"] = "reported"
        self.assertIn(
            "artifact component cannot be prematurely populated: bandwidth_loss",
            MODULE.validate(value),
        )

    def test_audio_metric_and_no_reference_authority_remain_closed(self) -> None:
        value = disposition()
        value["access_boundary"]["retained_audio_access_authorized"] = True
        value["access_boundary"]["perceptual_metric_execution_authorized"] = True
        value["access_boundary"]["no_reference_training_authorized"] = True
        self.assertIn("access boundary differs", MODULE.validate(value))

    def test_predecessor_two_family_schema_requires_new_version(self) -> None:
        value = disposition()
        value["required_score_blind_successor_amendment"][
            "predecessor_exactly_two_family_schema_requires_new_version"
        ] = False
        self.assertIn(
            "required successor amendment differs: predecessor_exactly_two_family_schema_requires_new_version",
            MODULE.validate(value),
        )


if __name__ == "__main__":
    unittest.main()
