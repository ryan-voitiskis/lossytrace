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
    / "validate-perceptual-degradation-odaq-delivery-authorization.py"
)
SPEC = importlib.util.spec_from_file_location("odaq_delivery_authorization", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return MODULE.load_json(MODULE.PLAN)


def synthetic_authorization(value: dict) -> dict:
    return {
        "schema_version": 1,
        "authorization_id": "perceptual-degradation-odaq-reference-delivery-authorization-20260813-001",
        "authorized_on": "2026-08-13",
        "state": "responsible_human_authorized_exact_clean_reference_projection_only",
        "responsible_human_authorization_present": True,
        "bindings": MODULE.expected_authorization_bindings(value),
        "authorization_scope": MODULE.expected_authorization_scope(value),
        "execution_constraints": MODULE.expected_execution_constraints(),
        "claim_boundary": MODULE.expected_claim_boundary(),
        "canonical_decision": MODULE.CANONICAL_DECISION,
    }


class OdaqDeliveryAuthorizationTest(unittest.TestCase):
    def test_committed_execution_plan_validates_and_remains_closed(self) -> None:
        value = plan()
        self.assertEqual([], MODULE.validate_plan(value))
        self.assertFalse(
            value["authorization_gate"]["responsible_human_authorization_present"]
        )
        self.assertFalse(value["access_boundary"]["retained_reference_access_authorized"])
        self.assertFalse(
            value["access_boundary"]["retained_reference_projection_authorized"]
        )

    def test_synthetic_future_authorization_shape_validates(self) -> None:
        value = plan()
        authorization = synthetic_authorization(value)
        self.assertEqual([], MODULE.validate_authorization(authorization, value))

    def test_authorization_must_bind_exact_inventory_and_evidence(self) -> None:
        value = plan()
        authorization = synthetic_authorization(value)
        authorization["authorization_scope"]["retained_inventory_sha256"] = "0" * 64
        authorization["bindings"]["playback_qualification_result"]["sha256"] = "0" * 64
        errors = MODULE.validate_authorization(authorization, value)
        self.assertIn("authorization evidence bindings differ", errors)
        self.assertIn("authorization scope differs", errors)

    def test_processed_scores_metrics_and_collection_cannot_be_enabled(self) -> None:
        value = plan()
        for key in (
            "provider_processed_condition_access_authorized",
            "provider_listening_score_access_authorized",
            "perceptual_metric_execution_authorized",
            "degradation_rating_collection_authorized",
            "listener_response_collection_authorized",
            "sealed_evidence_access_authorized",
            "public_verdict_authorized",
        ):
            with self.subTest(key=key):
                authorization = synthetic_authorization(value)
                authorization["authorization_scope"][key] = True
                self.assertIn(
                    "authorization scope differs",
                    MODULE.validate_authorization(authorization, value),
                )

    def test_authorization_requires_two_replays_attribution_and_disk_reserve(self) -> None:
        value = plan()
        authorization = synthetic_authorization(value)
        authorization["authorization_scope"]["two_fresh_private_replays_authorized"] = False
        authorization["authorization_scope"]["attribution_attachment_authorized"] = False
        authorization["execution_constraints"]["minimum_free_disk_gib"] = 14
        errors = MODULE.validate_authorization(authorization, value)
        self.assertIn("authorization scope differs", errors)
        self.assertIn("authorization execution constraints differ", errors)

    def test_private_paths_are_rejected(self) -> None:
        value = plan()
        authorization = synthetic_authorization(value)
        authorization["bindings"]["private"] = {
            "path": "/Users/example/reference.wav",
            "sha256": "0" * 64,
        }
        errors = MODULE.validate_authorization(authorization, value)
        self.assertIn("authorization evidence bindings differ", errors)
        self.assertIn("authorization must not contain a private absolute path", errors)

    def test_json_schema_matches_the_pure_validator_boundary(self) -> None:
        value = plan()
        schema_path = ROOT / value["bindings"]["authorization_schema"]["path"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            sorted(synthetic_authorization(value)), sorted(schema["required"])
        )
        self.assertTrue(
            schema["properties"]["authorization_scope"]["properties"]
            ["retained_reference_access_authorized"]["const"]
        )
        self.assertFalse(
            schema["properties"]["authorization_scope"]["properties"]
            ["perceptual_metric_execution_authorized"]["const"]
        )

    def test_plan_cannot_self_authorize(self) -> None:
        value = copy.deepcopy(plan())
        value["authorization_gate"]["responsible_human_authorization_present"] = True
        value["authorization_gate"]["retained_reference_read_authorized"] = True
        value["access_boundary"]["retained_reference_access_authorized"] = True
        errors = MODULE.validate_plan(value)
        self.assertIn("pending authorization gate differs", errors)
        self.assertIn("access boundary differs: retained_reference_access_authorized", errors)


if __name__ == "__main__":
    unittest.main()
