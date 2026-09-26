from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validate-perceptual-degradation-visqol-dependency-sbom-disposition.py"
)
DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "visqol-only-dependency-sbom-disposition.json"
)
SPEC = importlib.util.spec_from_file_location("visqol_dependency_sbom", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def disposition() -> dict:
    return json.loads(DISPOSITION.read_text(encoding="utf-8"))


class VisqolDependencySbomDispositionTest(unittest.TestCase):
    def test_committed_disposition_validates(self) -> None:
        self.assertEqual([], MODULE.validate(disposition()))

    def test_binding_mutation_fails(self) -> None:
        value = disposition()
        value["bindings"]["direct_dependency_license_observation"][
            "sha256"
        ] = "0" * 64
        self.assertIn(
            "bound file hash differs: direct_dependency_license_observation",
            MODULE.validate(value),
        )

    def test_direct_screen_cannot_be_promoted_to_complete_sbom(self) -> None:
        value = disposition()
        value["readiness"]["complete_binary_sbom_available"] = True
        value["readiness"][
            "dependency_redistribution_and_sbom_review_complete"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "readiness boundary must remain false: complete_binary_sbom_available",
            errors,
        )
        self.assertIn(
            "readiness boundary must remain false: "
            "dependency_redistribution_and_sbom_review_complete",
            errors,
        )

    def test_repository_names_cannot_be_promoted_to_closure(self) -> None:
        value = disposition()
        value["readiness"]["complete_transitive_dependency_closure_available"] = (
            True
        )
        self.assertIn(
            "readiness boundary must remain false: "
            "complete_transitive_dependency_closure_available",
            MODULE.validate(value),
        )

    def test_disposition_cannot_select_or_execute_successor(self) -> None:
        value = disposition()
        value["decision"]["successor_option_selected"] = "visqol_only"
        value["decision"]["successor_can_be_executed_from_current_evidence"] = (
            True
        )
        self.assertIn("decision boundary differs", MODULE.validate(value))

    def test_disposition_cannot_authorize_rebuild(self) -> None:
        value = disposition()
        value["decision"]["new_build_authorized_by_this_disposition"] = True
        self.assertIn("decision boundary differs", MODULE.validate(value))

    def test_audio_score_metric_and_training_boundaries_fail_closed(self) -> None:
        for key in (
            "test_audio_read",
            "model_bytes_read",
            "binary_read",
            "software_built",
            "perceptual_metric_executed",
            "retained_audio_accessed",
            "scores_opened",
            "no_reference_training_performed",
            "public_verdict_enabled",
        ):
            value = copy.deepcopy(disposition())
            value["access_boundary"][key] = True
            self.assertIn(
                f"access boundary must remain false: {key}",
                MODULE.validate(value),
            )

    def test_claims_remain_fail_closed(self) -> None:
        value = disposition()
        value["claim_boundary"][
            "direct_license_screen_is_complete_transitive_review"
        ] = True
        self.assertIn(
            "claim boundary must remain false: "
            "direct_license_screen_is_complete_transitive_review",
            MODULE.validate(value),
        )


if __name__ == "__main__":
    unittest.main()
