from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-perceptual-degradation-permissive-source-fallback.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "permissive-listening-source-fallback-plan.json"
)
SPEC = importlib.util.spec_from_file_location("permissive_source_fallback", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class PermissiveSourceFallbackTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_audio_or_score_access_cannot_be_authorized(self) -> None:
        value = plan()
        value["access_boundary"]["provider_audio_acquisition_authorized"] = True
        value["access_boundary"]["listening_score_opened"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "access boundary must remain false: provider_audio_acquisition_authorized",
            errors,
        )
        self.assertIn("access boundary must remain false: listening_score_opened", errors)

    def test_noncommercial_or_share_alike_sources_cannot_enter_fallback(self) -> None:
        value = plan()
        value["licence_policy"]["allowed_classes"].append("cc_by_nc")
        value["licence_policy"][
            "noncommercial_determination_required_for_this_fallback"
        ] = True
        value["licence_policy"]["share_alike_obligation_present_in_this_fallback"] = True
        errors = MODULE.validate(value)
        self.assertIn("permissive licence classes differ", errors)
        self.assertIn("fallback must not depend on a noncommercial licence", errors)
        self.assertIn("fallback must not contain ShareAlike sources", errors)

    def test_simulated_odaq_conditions_cannot_become_codec_truth(self) -> None:
        value = plan()
        value["eligible_future_roles"][
            "published_simulated_artifacts_as_actual_codec_conditions"
        ] = True
        value["claim_boundary"]["published_scores_calibrate_actual_codec_audibility"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "ineligible future role was enabled: published_simulated_artifacts_as_actual_codec_conditions",
            errors,
        )
        self.assertIn(
            "simulated-artifact scores cannot calibrate codec audibility", errors
        )

    def test_one_provider_cannot_be_promoted_to_transfer_evidence(self) -> None:
        value = plan()
        value["selected_reference_population"]["provider_stratum_count"] = 16
        value["eligible_future_roles"]["independent_music_provider_transfer"] = True
        value["claim_boundary"]["one_provider_is_multiple_independent_providers"] = True
        errors = MODULE.validate(value)
        self.assertIn("ODAQ must remain one provider stratum", errors)
        self.assertIn(
            "ineligible future role was enabled: independent_music_provider_transfer",
            errors,
        )
        self.assertIn(
            "one provider cannot be promoted to independent providers", errors
        )


if __name__ == "__main__":
    unittest.main()
