from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_listening_analysis.py"
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/listening-analysis-plan.json"
SCHEMA = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/listening-response-envelope.schema.json"
)
EVIDENCE = (
    ROOT
    / "research/toolchains/evidence/perceptual-degradation-listening-analysis-synthetic-20260813-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_analysis", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ListeningAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = MODULE.synthetic_dataset()
        cls.report = MODULE.analyse(cls.dataset)

    def test_plan_is_bound_to_implementation_constants(self) -> None:
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.assertEqual([], MODULE.validate_plan(plan))
        self.assertEqual(
            hashlib.sha256(PLAN.read_bytes()).hexdigest(),
            self.report["analysis_plan_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            self.report["implementation_sha256"],
        )

    def test_schema_preserves_synthetic_only_collection_boundary(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual("synthetic_fixture_only", properties["state"]["const"])
        self.assertFalse(properties["human_collection_authorized"]["const"])
        self.assertFalse(properties["human_responses_observed"]["const"])
        response_text = json.dumps(schema["$defs"]["response"])
        for forbidden in ("codec", "encoder", "filename", "path", "metric_score"):
            self.assertNotIn(forbidden, response_text)

    def test_synthetic_replay_exercises_all_truth_states_without_scientific_claim(self) -> None:
        truths = {
            item["analysis_group_id"]: item["human_truth"]
            for item in self.report["primary_groups"]
        }
        self.assertEqual(
            {
                "group-audible-nonmaterial": "audible_nonmaterial",
                "group-material-bridge": "materially_degraded",
                "group-transparent": "transparent",
            },
            truths,
        )
        self.assertFalse(self.report["scientific_gate_evaluated"])
        self.assertFalse(
            self.report["collection_or_oracle_gate"]["collection_eligible"]
        )
        self.assertFalse(
            self.report["collection_or_oracle_gate"]["oracle_truth_eligible"]
        )

    def test_bridge_preserves_material_reference_points(self) -> None:
        mapping = self.report["bridge_mapping"]
        self.assertEqual(
            {"sdg": -1.0, "mushra_loss": 10.0, "severity": 25.0},
            mapping["material_reference_points"],
        )
        anchors = {
            item["role"]: (item["mushra_loss"], item["severity"])
            for item in mapping["knots"]
            if item["role"] != "development_bridge"
        }
        self.assertEqual((0.0, 0.0), anchors["hidden_reference_anchor"])
        self.assertEqual((10.0, 25.0), anchors["material_boundary_anchor"])
        self.assertEqual((100.0, 100.0), anchors["maximum_loss_anchor"])
        severities = [item["severity"] for item in mapping["knots"]]
        self.assertEqual(severities, sorted(severities))

    def test_observed_human_responses_fail_closed(self) -> None:
        value = copy.deepcopy(self.dataset)
        value["human_responses_observed"] = True
        errors = MODULE.validate_dataset(value)
        self.assertIn("observed human responses are forbidden", errors)
        with self.assertRaisesRegex(ValueError, "observed human responses are forbidden"):
            MODULE.analyse(value)

    def test_duplicate_idempotency_key_fails_closed(self) -> None:
        value = copy.deepcopy(self.dataset)
        value["responses"][1]["idempotency_key"] = value["responses"][0][
            "idempotency_key"
        ]
        self.assertTrue(
            any(
                "duplicate idempotency key" in error
                for error in MODULE.validate_dataset(value)
            )
        )

    def test_response_scale_and_session_binding_fail_closed(self) -> None:
        value = copy.deepcopy(self.dataset)
        value["responses"][0]["sdg"] = -4.1
        value["responses"][1]["participant_id"] = value["sessions"][1][
            "participant_id"
        ]
        errors = MODULE.validate_dataset(value)
        self.assertTrue(any("SDG differs" in error for error in errors))
        self.assertTrue(any("session binding differs" in error for error in errors))

    def test_source_and_condition_group_leakage_fail_closed(self) -> None:
        source_value = copy.deepcopy(self.dataset)
        source_value["responses"][1]["source_group_id"] = source_value[
            "responses"
        ][0]["source_group_id"]
        self.assertTrue(
            any(
                "source crosses partition groups" in error
                for error in MODULE.validate_dataset(source_value)
            )
        )
        condition_value = copy.deepcopy(self.dataset)
        condition_value["responses"][15]["condition_stimulus_id"] = condition_value[
            "responses"
        ][0]["condition_stimulus_id"]
        self.assertTrue(
            any(
                "condition crosses analysis groups" in error
                for error in MODULE.validate_dataset(condition_value)
            )
        )

    def test_underpowered_group_abstains(self) -> None:
        value = copy.deepcopy(self.dataset)
        included = {session["participant_id"] for session in value["sessions"][:10]}
        value["sessions"] = value["sessions"][:10]
        value["responses"] = [
            response
            for response in value["responses"]
            if response["participant_id"] in included
        ]
        report = MODULE.analyse(value)
        self.assertTrue(
            all(
                item["human_truth"] == "indeterminate"
                for item in report["primary_groups"]
            )
        )

    def test_quality_flagged_sessions_are_sensitivity_only(self) -> None:
        value = copy.deepcopy(self.dataset)
        for session in value["sessions"]:
            session["checks"]["hidden_reference_quality_pass"] = False
        report = MODULE.analyse(value)
        self.assertEqual([], report["primary_groups"])
        self.assertEqual(3, len(report["sensitivity_groups"]))
        self.assertEqual(
            [
                "group-audible-nonmaterial",
                "group-material-bridge",
                "group-transparent",
            ],
            report["sensitivity_disagreements"],
        )

    def test_bridge_disagreement_is_indeterminate(self) -> None:
        value = copy.deepcopy(self.dataset)
        for response in value["responses"]:
            if (
                response["analysis_group_id"] == "group-material-bridge"
                and response["method"] == "mushra"
            ):
                response["condition_score"] = response["hidden_reference_score"] - 5.0
        report = MODULE.analyse(value)
        group = next(
            item
            for item in report["primary_groups"]
            if item["analysis_group_id"] == "group-material-bridge"
        )
        self.assertTrue(group["sdg_material_signal"])
        self.assertFalse(group["mushra_material_signal"])
        self.assertTrue(group["bridge_disagreement"])
        self.assertEqual("indeterminate", group["human_truth"])

    def test_analysis_is_byte_deterministic(self) -> None:
        first = MODULE._json_bytes(MODULE.analyse(copy.deepcopy(self.dataset)))
        second = MODULE._json_bytes(MODULE.analyse(copy.deepcopy(self.dataset)))
        self.assertEqual(first, second)
        self.assertEqual(first, EVIDENCE.read_bytes())

    def test_cli_has_no_real_response_input_and_refuses_overwrite(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--responses"', source)
        self.assertNotIn('add_argument("--input"', source)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            first = subprocess.run(
                ["python3", str(SCRIPT), "--synthetic-output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            second = subprocess.run(
                ["python3", str(SCRIPT), "--synthetic-output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, second.returncode)
            self.assertIn("refusing to replace output", second.stderr)


if __name__ == "__main__":
    unittest.main()
