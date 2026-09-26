from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/perceptual_degradation_odaq_retained_drift_validation_readiness.py"
)
SPEC = importlib.util.spec_from_file_location("odaq_drift_readiness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def synthetic_authorization(plan: dict) -> dict:
    return {
        "schema_version": 1,
        "authorization_id": "perceptual-degradation-odaq-retained-drift-validation-authorization-20260814-001",
        "authorized_on": "2026-08-14",
        "state": "responsible_human_authorized_exact_odaq_clean_reference_drift_validation_only",
        "responsible_human_authorization_present": True,
        "bindings": MODULE.expected_authorization_bindings(plan),
        "authorization_scope": MODULE.expected_authorization_scope(plan),
        "execution_constraints": MODULE.expected_authorization_execution_constraints(),
        "claim_boundary": MODULE.expected_authorization_claim_boundary(),
        "canonical_decision": MODULE.CANONICAL_DECISION,
    }


class OdaqRetainedDriftValidationReadinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_plan_validates_and_live_execution_remains_closed(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertFalse(
            self.plan["authorization_gate"]["responsible_human_authorization_present"]
        )
        self.assertFalse(
            self.plan["authorization_gate"]["live_runner_implementation_authorized"]
        )
        self.assertFalse(self.plan["authorization_gate"]["live_execution_authorized"])

    def test_report_is_deterministic_exact_and_metadata_only(self) -> None:
        second = MODULE.build_report(self.plan)
        self.assertEqual(MODULE.canonical_bytes(self.report), MODULE.canonical_bytes(second))
        self.assertEqual([], MODULE.validate_report(self.report))
        self.assertEqual(MODULE.canonical_bytes(self.report), MODULE.REPORT_PATH.read_bytes())
        self.assertTrue(self.report["all_readiness_gates_pass"])
        self.assertFalse(self.report["execution_observation"]["retained_reference_accessed"])

    def test_synthetic_future_authorization_shape_validates(self) -> None:
        authorization = synthetic_authorization(self.plan)
        self.assertEqual([], MODULE.validate_authorization(authorization, self.plan))

    def test_json_schema_matches_pure_authorization_validator(self) -> None:
        authorization = synthetic_authorization(self.plan)
        schema_path = ROOT / self.plan["bindings"]["authorization_schema"]["path"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(sorted(authorization), sorted(schema["required"]))
        scope = schema["properties"]["authorization_scope"]["properties"]
        self.assertTrue(scope["retained_reference_access_authorized"]["const"])
        self.assertFalse(scope["provider_processed_condition_access_authorized"]["const"])
        self.assertFalse(scope["perceptual_metric_execution_authorized"]["const"])

        authorization["authorization_id"] = "unbound"
        authorization["authorized_on"] = "soon"
        errors = MODULE.validate_authorization(authorization, self.plan)
        self.assertIn("authorization identity differs", errors)
        self.assertIn("authorization date differs", errors)

    def test_future_authorization_binds_exact_inventory_and_protocol(self) -> None:
        authorization = synthetic_authorization(self.plan)
        authorization["authorization_scope"]["retained_inventory_sha256"] = "0" * 64
        authorization["bindings"]["synthetic_estimator_report"]["sha256"] = "0" * 64
        errors = MODULE.validate_authorization(authorization, self.plan)
        self.assertIn("authorization evidence bindings differ", errors)
        self.assertIn("authorization scope differs", errors)

    def test_processed_scores_codecs_metrics_humans_and_models_stay_closed(self) -> None:
        for key in (
            "retained_derived_audio_authorized",
            "provider_processed_condition_access_authorized",
            "provider_listening_score_access_authorized",
            "actual_codec_generation_authorized",
            "perceptual_metric_execution_authorized",
            "human_playback_authorized",
            "degradation_rating_collection_authorized",
            "listener_response_collection_authorized",
            "sealed_evidence_access_authorized",
            "no_reference_training_authorized",
            "public_verdict_authorized",
        ):
            with self.subTest(key=key):
                authorization = synthetic_authorization(self.plan)
                authorization["authorization_scope"][key] = True
                self.assertIn(
                    "authorization scope differs",
                    MODULE.validate_authorization(authorization, self.plan),
                )

    def test_protocol_segment_fits_shortest_acquired_reference(self) -> None:
        protocol = self.plan["validation_protocol"]
        evidence = self.plan["qualified_evidence"]
        self.assertEqual(288000, protocol["analysis_frame_count"])
        self.assertGreaterEqual(
            evidence["minimum_source_frame_count"], protocol["analysis_frame_count"]
        )
        last_end = (
            protocol["window_start_frames"][-1] + protocol["window_frame_count"]
        )
        self.assertLessEqual(last_end, protocol["analysis_frame_count"])

    def test_plan_cannot_self_authorize_or_promote_claims(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["authorization_gate"]["responsible_human_authorization_present"] = True
        plan["authorization_gate"]["live_execution_authorized"] = True
        self.assertIn("authorization gate differs", MODULE.validate_plan(plan))

        plan = copy.deepcopy(self.plan)
        plan["claim_boundary"]["full_reference_oracle_validated"] = True
        plan["claim_boundary"]["no_reference_work_eligible"] = True
        self.assertIn("claim boundary differs", MODULE.validate_plan(plan))

    def test_private_paths_and_audio_payloads_are_absent(self) -> None:
        encoded = json.dumps(self.report, sort_keys=True)
        self.assertNotIn("/Users/", encoded)
        self.assertNotIn("Application Support", encoded)
        self.assertNotIn(".wav", encoded.lower())
        self.assertNotIn("pcm_payload", encoded)
        self.assertNotIn("per_reference_sha256", encoded)


if __name__ == "__main__":
    unittest.main()
