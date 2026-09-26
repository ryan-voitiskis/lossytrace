from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/validate_perceptual_degradation_source_trait_provider_capability_screen.py"
)
OBSERVATION = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-source-trait-provider-capability-screen-20260814-001.json"
)
SPEC = importlib.util.spec_from_file_location(
    "source_trait_provider_capability_screen", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def observation() -> dict:
    return json.loads(OBSERVATION.read_text(encoding="utf-8"))


class SourceTraitProviderCapabilityScreenTest(unittest.TestCase):
    def test_committed_observation_validates(self) -> None:
        self.assertEqual([], MODULE.validate_committed_observation())

    def test_audio_member_and_trait_boundaries_remain_closed(self) -> None:
        value = observation()
        value["access_boundary"]["provider_audio_accessed"] = True
        value["access_boundary"]["exact_member_selected"] = True
        value["access_boundary"]["source_trait_assigned"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("access boundary differs: provider_audio_accessed", errors)
        self.assertIn("access boundary differs: exact_member_selected", errors)
        self.assertIn("access boundary differs: source_trait_assigned", errors)

    def test_provider_capability_cannot_be_promoted_to_candidate(self) -> None:
        value = observation()
        quiet = value["provider_capability_observations"][0]
        quiet["exact_member_candidate_identified"] = True
        value["trait_disposition"]["quiet"]["all_proof_obligations_satisfied"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("quiet provider capability differs", errors)
        self.assertIn(
            "trait disposition differs: quiet.all_proof_obligations_satisfied",
            errors,
        )

    def test_clipped_search_mechanism_is_not_capture_provenance(self) -> None:
        value = observation()
        clipped = value["provider_capability_observations"][1]
        clipped["provenance_obligation_status"][
            "source_or_capture_chain_clipping_record"
        ] = "established"
        value["decision"]["naturally_clipped_candidate_identified"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("clipped provenance boundary differs", errors)
        self.assertIn(
            "decision differs: naturally_clipped_candidate_identified", errors
        )

    def test_policy_cannot_treat_tags_or_containers_as_provenance(self) -> None:
        value = observation()
        value["screen_policy"]["uploader_tag_alone_is_capture_chain_provenance"] = True
        value["screen_policy"][
            "lossless_container_alone_proves_original_coding_history"
        ] = True
        self.assertIn("screen policy differs", MODULE.validate_observation(value))

    def test_scientific_and_public_gates_remain_closed(self) -> None:
        value = observation()
        value["decision"]["source_trait_manifest_frozen"] = True
        value["decision"]["no_reference_work_eligible"] = True
        value["claim_boundary"]["public_cli_changed"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("decision differs: source_trait_manifest_frozen", errors)
        self.assertIn("decision differs: no_reference_work_eligible", errors)
        self.assertIn(
            "claim boundary must remain false: public_cli_changed", errors
        )


if __name__ == "__main__":
    unittest.main()
