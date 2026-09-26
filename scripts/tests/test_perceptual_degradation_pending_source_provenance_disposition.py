from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validate-perceptual-degradation-pending-source-provenance-disposition.py"
)
DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "pending-source-provenance-disposition.json"
)
SPEC = importlib.util.spec_from_file_location("pending_source_disposition", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def disposition() -> dict:
    return json.loads(DISPOSITION.read_text(encoding="utf-8"))


class PendingSourceProvenanceDispositionTest(unittest.TestCase):
    def test_committed_disposition_validates(self) -> None:
        self.assertEqual([], MODULE.validate(disposition()))

    def test_pcm_delivery_cannot_be_promoted_to_lossless_origin(self) -> None:
        value = disposition()
        observation = self.load_observation(value)
        observation["shared_limits"][
            "pcm_delivery_container_proves_lossless_origin"
        ] = True
        errors = self.validate_with_observation(value, observation)
        self.assertIn(
            "shared provenance limit must remain false: pcm_delivery_container_proves_lossless_origin",
            errors,
        )

    def test_creative_commons_permission_cannot_become_coding_provenance(self) -> None:
        value = disposition()
        observation = self.load_observation(value)
        observation["shared_limits"][
            "creative_commons_permission_proves_lossless_origin"
        ] = True
        errors = self.validate_with_observation(value, observation)
        self.assertIn(
            "shared provenance limit must remain false: creative_commons_permission_proves_lossless_origin",
            errors,
        )

    def test_codec_history_inference_cannot_certify_clean_truth(self) -> None:
        value = disposition()
        value["qualification_rule"][
            "decoded_pcm_codec_history_inference_is_admissible_provenance"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "qualification rule must remain false: decoded_pcm_codec_history_inference_is_admissible_provenance",
            errors,
        )

    def test_unknown_origin_candidates_cannot_be_promoted(self) -> None:
        value = disposition()
        value["candidate_dispositions"][0][
            "truth_bearing_clean_reference_eligible"
        ] = True
        value["allocation_consequence"][
            "musicnet_repairs_final_music_domain"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "candidate was promoted to clean truth: musicnet_5120004", errors
        )
        self.assertIn(
            "allocation consequence must remain false: musicnet_repairs_final_music_domain",
            errors,
        )

    def test_rejection_cannot_become_unsupported_lossy_assertion(self) -> None:
        value = disposition()
        value["candidate_dispositions"][1][
            "actual_prior_lossy_coding_asserted"
        ] = True
        value["claim_boundary"]["fsd50k_is_asserted_to_contain_lossy_audio"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "candidate was asserted lossy without evidence: fsd50k_4060432_allowed_items",
            errors,
        )
        self.assertIn(
            "claim boundary must remain false: fsd50k_is_asserted_to_contain_lossy_audio",
            errors,
        )

    def test_source_successor_cannot_be_silently_selected(self) -> None:
        value = disposition()
        value["decision"]["selected_successor_option"] = (
            "narrow_primary_domain_claim"
        )
        value["successor_options"][1][
            "audio_access_authorized_by_this_disposition"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn("source successor was prematurely selected", errors)
        self.assertIn(
            "source option prematurely authorizes audio: narrow_primary_domain_claim",
            errors,
        )

    def test_candidate_stop_cannot_become_full_objective_negative(self) -> None:
        value = disposition()
        value["claim_boundary"][
            "candidate_rejection_is_full_objective_negative_result"
        ] = True
        value["decision"]["final_recommendation_frozen"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "claim boundary must remain false: candidate_rejection_is_full_objective_negative_result",
            errors,
        )
        self.assertIn("final recommendation was prematurely frozen", errors)

    def test_audio_metrics_scores_and_training_remain_closed(self) -> None:
        value = disposition()
        value["access_boundary"]["new_audio_acquisition_authorized"] = True
        value["access_boundary"]["perceptual_metric_execution_authorized"] = True
        value["access_boundary"]["listening_score_access_authorized"] = True
        value["access_boundary"]["no_reference_training_authorized"] = True
        self.assertIn("access boundary differs", MODULE.validate(value))

    @staticmethod
    def load_observation(value: dict) -> dict:
        path = ROOT / value["bindings"]["public_provenance_observation"]["path"]
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def validate_with_observation(value: dict, observation: dict) -> list[str]:
        handle, raw_path = tempfile.mkstemp(
            prefix=".tmp-pending-source-public-provenance-",
            suffix=".json",
            dir=ROOT / "research/toolchains/evidence",
        )
        os.close(handle)
        path = Path(raw_path)
        try:
            path.write_text(json.dumps(observation), encoding="utf-8")
            value["bindings"]["public_provenance_observation"]["path"] = str(
                path.relative_to(ROOT)
            )
            value["bindings"]["public_provenance_observation"]["sha256"] = (
                hashlib.sha256(path.read_bytes()).hexdigest()
            )
            return MODULE.validate(value)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
