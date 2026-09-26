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
    / "validate-perceptual-degradation-odaq-reference-authorization.py"
)
SPEC = importlib.util.spec_from_file_location("odaq_reference_authorization", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def authorization() -> dict:
    return MODULE.load_json(MODULE.AUTHORIZATION)


def freeze() -> dict:
    return MODULE.load_json(MODULE.FREEZE)


class OdaqReferenceAuthorizationTest(unittest.TestCase):
    def test_committed_authorization_validates(self) -> None:
        self.assertEqual([], MODULE.validate(authorization(), freeze()))

    def test_provider_and_reference_inventory_must_match_freeze(self) -> None:
        value = authorization()
        value["provider"]["record_id"] += 1
        value["references"][0]["crc32"] = "00000000"
        errors = MODULE.validate(value, freeze())
        self.assertIn("authorized provider differs from freeze", errors)
        self.assertIn("authorized references differ from freeze", errors)

    def test_processed_scores_and_collection_remain_closed(self) -> None:
        value = authorization()
        value["processed_condition_access_authorized"] = True
        value["listening_score_access_authorized"] = True
        value["listener_response_collection_authorized"] = True
        errors = MODULE.validate(value, freeze())
        self.assertIn(
            "authorization boundary must remain false: processed_condition_access_authorized",
            errors,
        )
        self.assertIn(
            "authorization boundary must remain false: listening_score_access_authorized",
            errors,
        )
        self.assertIn(
            "authorization boundary must remain false: listener_response_collection_authorized",
            errors,
        )

    def test_source_limit_and_attribution_acceptance_are_required(self) -> None:
        value = authorization()
        value["source_decision"][
            "one_provider_development_only_limit_accepted"
        ] = False
        value["source_decision"]["bound_attribution_requirements_accepted"] = False
        self.assertIn(
            "responsible-human source decision differs",
            MODULE.validate(value, freeze()),
        )

    def test_playback_declaration_cannot_claim_observed_qualification(self) -> None:
        value = authorization()
        value["playback_declaration"]["state"] = "qualified"
        value["playback_declaration"]["physical_playback_qualified"] = True
        errors = MODULE.validate(value, freeze())
        self.assertIn("playback declaration state differs", errors)
        self.assertIn("physical playback was prematurely qualified", errors)

    def test_private_absolute_paths_are_rejected(self) -> None:
        value = copy.deepcopy(authorization())
        value["playback_declaration"]["local_path"] = "/Users/example/private"
        self.assertIn(
            "authorization must not contain a private absolute path",
            MODULE.validate(value, freeze()),
        )


if __name__ == "__main__":
    unittest.main()
