from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validate_perceptual_degradation_source_trait_quiet_alternative_metadata_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "source_trait_quiet_alternative_metadata_audit", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceTraitQuietAlternativeMetadataAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_committed_audit_validates(self) -> None:
        self.assertEqual([], MODULE.validate_committed())

    def test_audio_and_descriptor_access_remain_closed(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["access_boundary"]["audio_samples_read"] = True
        changed["access_boundary"]["audio_descriptors_computed_or_read"] = True
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("closed access boundary differs: audio_samples_read", errors)
        self.assertIn(
            "closed access boundary differs: audio_descriptors_computed_or_read",
            errors,
        )

    def test_quiet_candidate_requires_lossless_gain_and_no_processing(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["quiet_audit"]["public_container_metadata"][
            "original_upload_is_lossless"
        ] = False
        changed["quiet_audit"]["quiet_scene_and_capture_record"][
            "capture_gain_setting"
        ] = None
        changed["quiet_audit"]["quiet_scene_and_capture_record"][
            "post_capture_processing_applied"
        ] = True
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("quiet original lossless metadata differs", errors)
        self.assertIn("quiet capture gain differs", errors)
        self.assertIn("quiet transformation history differs", errors)

    def test_quiet_candidate_cannot_be_promoted_to_trait_truth(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["quiet_audit"]["trait_assigned"] = True
        changed["decision"]["quiet_trait_truth_established"] = True
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("quiet trait must remain unassigned", errors)
        self.assertIn(
            "decision must remain false: quiet_trait_truth_established", errors
        )

    def test_related_upload_cannot_be_promoted_to_independent_contrast(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["quiet_audit"]["relationship_boundary"][
            "related_member_is_independent_contrast"
        ] = True
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("related quiet member must remain non-independent", errors)

    def test_scientific_and_public_gates_remain_closed(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["summary"]["source_trait_manifest_frozen"] = True
        changed["decision"]["no_reference_work_eligible"] = True
        changed["claim_boundary"]["public_verdict_enabled"] = True
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("summary differs", errors)
        self.assertIn("decision must remain false: no_reference_work_eligible", errors)
        self.assertIn("report claim boundary must remain false", errors)

    def test_private_paths_are_rejected(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["private_path"] = "/Users/example/private.wav"
        self.assertIn("report exposes a private path", MODULE.validate_report(changed))


if __name__ == "__main__":
    unittest.main()
