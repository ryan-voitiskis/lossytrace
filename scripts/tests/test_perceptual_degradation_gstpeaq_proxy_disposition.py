from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/validate-perceptual-degradation-gstpeaq-proxy-disposition.py"
)
DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "gstpeaq-proxy-score-blind-disposition.json"
)
SPEC = importlib.util.spec_from_file_location("gstpeaq_proxy_disposition", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def disposition() -> dict:
    return json.loads(DISPOSITION.read_text(encoding="utf-8"))


class GstpeaqProxyDispositionTest(unittest.TestCase):
    def test_committed_disposition_validates(self) -> None:
        self.assertEqual([], MODULE.validate(disposition()))

    def test_software_licence_cannot_be_promoted_to_patent_consent(self) -> None:
        value = disposition()
        observation_path = (
            ROOT / value["bindings"]["public_legal_observation"]["path"]
        )
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        observation["gstpeaq_repository"][
            "software_copyright_licence_is_patent_consent"
        ] = True
        errors = self.validate_with_observation(value, observation)
        self.assertIn(
            "software licence boundary must remain false: software_copyright_licence_is_patent_consent",
            errors,
        )

    def test_itu_database_cannot_be_promoted_to_authoritative_clearance(self) -> None:
        value = disposition()
        observation_path = (
            ROOT / value["bindings"]["public_legal_observation"]["path"]
        )
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        observation["itu_patent_database"]["database_certified_complete"] = True
        observation["itu_patent_database"][
            "database_proves_a_licence_was_granted_to_lossytrace"
        ] = True
        errors = self.validate_with_observation(value, observation)
        self.assertIn(
            "ITU database limit must remain false: database_certified_complete",
            errors,
        )
        self.assertIn(
            "ITU database limit must remain false: database_proves_a_licence_was_granted_to_lossytrace",
            errors,
        )

    def test_research_label_cannot_invent_experimental_use_clearance(self) -> None:
        value = disposition()
        value["findings"][
            "australian_experimental_use_clearly_applies_to_metric_as_research_tool"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "finding must remain false: australian_experimental_use_clearly_applies_to_metric_as_research_tool",
            errors,
        )

    def test_proxy_execution_and_scores_remain_closed(self) -> None:
        value = disposition()
        value["access_boundary"]["gstpeaq_execution_authorized"] = True
        value["access_boundary"]["perceptual_metric_execution_authorized"] = True
        value["access_boundary"]["metric_score_access_authorized"] = True
        self.assertIn("access boundary differs", MODULE.validate(value))

    def test_current_two_family_candidate_cannot_advance(self) -> None:
        value = disposition()
        value["frozen_disposition"][
            "current_two_primary_family_candidate_may_advance"
        ] = True
        value["frozen_disposition"][
            "current_two_primary_family_candidate_stop_condition_triggered"
        ] = False
        errors = MODULE.validate(value)
        self.assertIn(
            "frozen disposition must remain false: current_two_primary_family_candidate_may_advance",
            errors,
        )
        self.assertIn(
            "current two-family stop condition must be triggered",
            errors,
        )

    def test_candidate_stop_cannot_become_full_objective_negative(self) -> None:
        value = disposition()
        value["frozen_disposition"][
            "proxy_failure_is_full_objective_negative_result"
        ] = True
        value["claim_boundary"][
            "stopped_candidate_is_rigorous_full_objective_negative"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "frozen disposition must remain false: proxy_failure_is_full_objective_negative_result",
            errors,
        )
        self.assertIn(
            "claim boundary must remain false: stopped_candidate_is_rigorous_full_objective_negative",
            errors,
        )

    def test_successor_cannot_be_silently_selected(self) -> None:
        value = disposition()
        value["decision"][
            "selected_successor_option"
        ] = "preregister_simpler_full_reference_successor"
        value["decision"]["silent_family_replacement_forbidden"] = False
        errors = MODULE.validate(value)
        self.assertIn("successor option was prematurely selected", errors)
        self.assertIn("silent family replacement must remain forbidden", errors)

    def validate_with_observation(
        self, value: dict, observation: dict
    ) -> list[str]:
        import hashlib
        import os
        import tempfile

        handle, raw_path = tempfile.mkstemp(
            prefix=".tmp-gstpeaq-public-legal-observation-",
            suffix=".json",
            dir=ROOT / "research/toolchains/evidence",
        )
        os.close(handle)
        path = Path(raw_path)
        try:
            path.write_text(json.dumps(observation), encoding="utf-8")
            value["bindings"]["public_legal_observation"]["path"] = str(
                path.relative_to(ROOT)
            )
            value["bindings"]["public_legal_observation"]["sha256"] = (
                hashlib.sha256(path.read_bytes()).hexdigest()
            )
            return MODULE.validate(value)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
