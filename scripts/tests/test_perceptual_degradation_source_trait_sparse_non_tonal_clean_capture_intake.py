from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_intake.py"
SPEC = importlib.util.spec_from_file_location("clean_capture_intake", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanCaptureIntakeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.fixture = MODULE.load_json(MODULE.FIXTURE_PATH)
        cls.report = MODULE.build_public_report(cls.plan, cls.fixture)

    def test_plan_and_committed_report_replay_exactly(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_synthetic_fixture_passes_all_eight_gates(self) -> None:
        errors = MODULE.validate_manifest(self.fixture)
        self.assertEqual(MODULE.GATE_ORDER, list(errors))
        self.assertTrue(all(not values for values in errors.values()))
        self.assertEqual(8, self.report["execution"]["gate_pass_count"])
        self.assertFalse(self.report["decision"]["live_delivery_accepted"])
        self.assertFalse(self.report["audio_accessed"])

    def test_processing_container_quiet_and_safety_tamper_fail_closed(self) -> None:
        tampered = copy.deepcopy(self.fixture)
        tampered["processing"]["transformations"] = ["normalization"]
        tampered["file"]["container"]["duration_seconds"] = "8.000"
        tampered["file"]["container"]["peak_dbfs"] = "-1.000"
        tampered["capture"]["pre_event_quiet_seconds"] = "1.000"
        tampered["capture"]["safe_non_hazardous_event_confirmed"] = False
        errors = MODULE.validate_manifest(tampered)
        self.assertTrue(errors["transformation_history"])
        self.assertIn("duration outside frozen range", errors["container_and_duration"])
        self.assertIn("peak headroom differs", errors["container_and_duration"])
        self.assertIn("pre-event quiet margin differs", errors["quiet_context_and_single_event_declaration"])
        self.assertIn("safe event declaration differs", errors["safety_declaration"])

    def test_rights_channel_and_path_tamper_fail_closed(self) -> None:
        tampered = copy.deepcopy(self.fixture)
        tampered["rights"]["licence"] = "all rights reserved"
        tampered["capture"]["channels"][0]["microphone_make_model"] = ""
        tampered["file"]["logical_name"] = "/private/capture.wav"
        errors = MODULE.validate_manifest(tampered)
        self.assertIn("licence is not allowed", errors["rights_and_attribution"])
        self.assertIn("channel field missing: microphone_make_model", errors["complete_channel_capture_chain"])
        self.assertIn("logical WAV name differs", errors["original_wav_lineage"])
        self.assertTrue(any("forbidden path" in value for value in errors["exact_member_and_source_group_identity"]))

    def test_malformed_nested_objects_return_errors_instead_of_crashing(self) -> None:
        tampered = copy.deepcopy(self.fixture)
        tampered["rights"] = []
        tampered["capture"] = []
        tampered["file"] = []
        errors = MODULE.validate_manifest(tampered)
        self.assertIn("rights must be an object", errors["rights_and_attribution"])
        self.assertIn("capture must be an object", errors["complete_channel_capture_chain"])
        self.assertIn("file must be an object", errors["original_wav_lineage"])

    def test_public_projection_excludes_private_manifest_material(self) -> None:
        serialized = json.dumps(self.report, sort_keys=True)
        for forbidden in (
            "rights_holder_identity",
            "location_and_room_description",
            "logical_name",
            "microphone_make_model",
            self.fixture["file"]["sha256"],
        ):
            self.assertNotIn(forbidden, serialized)

    def test_live_cli_path_is_closed(self) -> None:
        completed = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(1, completed.returncode)
        self.assertIn("live delivery acceptance is not authorized", completed.stdout)

    def test_plan_authority_and_binding_tamper_fail_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["authorization"]["live_delivery_acceptance_authorized"] = True
        tampered["bindings"]["acquisition_specification"]["sha256"] = "0" * 64
        errors = MODULE.validate_plan(tampered)
        self.assertIn("authorization differs: live_delivery_acceptance_authorized", errors)
        self.assertIn("binding hash differs: acquisition_specification", errors)


if __name__ == "__main__":
    unittest.main()
