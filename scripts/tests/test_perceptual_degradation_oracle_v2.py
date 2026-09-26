from __future__ import annotations

import copy
import importlib
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
MODULE = importlib.import_module("perceptual_degradation_oracle_v2")


class OracleValidityIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = dict(MODULE.synthetic_records())

    def alignment(self, name="identity_subtle"):
        return copy.deepcopy(self.records[name]["alignment"])

    def assert_invalid(self, alignment, mode="subtle"):
        self.assertTrue(MODULE.validate_alignment(alignment, mode))
        with self.assertRaises(ValueError):
            MODULE.assemble_score_free(alignment, comparison_mode=mode)

    def test_all_seven_real_producer_records_validate(self):
        self.assertEqual(7, len(self.records))
        for record in self.records.values():
            self.assertEqual([], MODULE.validate_score_free_record(record))
            self.assertFalse(record["support"]["supported"])

    def test_expected_state_transitions(self):
        expected = {
            "identity_subtle": "execution_blocked",
            "relative_polarity_subtle": "execution_blocked",
            "dropout_subtle": "unsupported_alignment",
            "silent_window_subtle": "unsupported_alignment",
            "identity_quality_six_seconds": "unsupported_alignment",
            "identity_quality_twelve_seconds": "execution_blocked",
            "topology_mismatch": "unsupported_alignment",
        }
        self.assertEqual(expected, {name: record["result_state"] for name, record in self.records.items()})

    def test_duration_modes_are_explicit_and_not_interchangeable(self):
        subtle = self.records["identity_subtle"]
        quality = self.records["identity_quality_six_seconds"]
        self.assertEqual(4.0, subtle["alignment_configuration"]["minimum_active_seconds"])
        self.assertEqual(8.0, quality["alignment_configuration"]["minimum_active_seconds"])
        self.assertEqual(["insufficient_active_audio"], quality["support"]["alignment_reason_codes"])
        self.assert_invalid(self.alignment(), "quality_metric")
        self.assert_invalid(self.alignment("identity_quality_six_seconds"), "subtle")

    def test_twelve_second_fixture_does_not_enable_metric_execution(self):
        record = self.records["identity_quality_twelve_seconds"]
        self.assertEqual(12.0, record["alignment"]["alignment"]["summary"]["active_seconds"])
        self.assertFalse(record["metric_execution"]["suite_selected"])
        self.assertEqual("not_authorized", record["metric_execution"]["state"])
        self.assertIsNone(record["bindings"]["metric_execution_gate_id"])

    def test_missing_channel_minimum_is_not_imputed(self):
        alignment = self.alignment("dropout_subtle")
        self.assertIsNone(alignment["alignment"]["summary"]["minimum_correlation"])
        for invented in (0.0, 1.0, -1.0):
            broken = copy.deepcopy(alignment)
            broken["alignment"]["summary"]["minimum_correlation"] = invented
            self.assert_invalid(broken)

    def test_supported_claim_cannot_override_missing_channel(self):
        alignment = self.alignment("dropout_subtle")
        alignment["status"] = "supported"
        alignment["support"]["reasons"] = []
        alignment["alignment"]["channels"][1]["status"] = "supported"
        alignment["alignment"]["channels"][1]["reasons"] = []
        self.assert_invalid(alignment)

    def test_invalid_correlation_cannot_be_relabelled_as_perfect(self):
        alignment = self.alignment()
        correlation = alignment["alignment"]["channels"][0]["diagnostics"]["correlation"]
        correlation["reason"] = "zero_energy"
        self.assert_invalid(alignment)

    def test_valid_negative_one_is_preserved(self):
        record = self.records["relative_polarity_subtle"]
        correlation = record["alignment"]["alignment"]["channels"][1]["diagnostics"]["correlation"]
        self.assertAlmostEqual(-1.0, correlation["value"])
        self.assertAlmostEqual(1.0, correlation["magnitude"])
        self.assertIsNone(correlation["reason"])

    def test_inconsistent_signed_and_absolute_values_are_rejected(self):
        alignment = self.alignment()
        alignment["alignment"]["channels"][0]["diagnostics"]["correlation"]["magnitude"] = 0.5
        self.assert_invalid(alignment)

    def test_wrong_correlation_sample_count_is_rejected(self):
        alignment = self.alignment()
        alignment["alignment"]["channels"][0]["diagnostics"]["correlation"]["sampled_frames"] = 1
        self.assert_invalid(alignment)

    def test_zero_gain_cannot_keep_finite_db_and_polarity(self):
        alignment = self.alignment()
        gain = alignment["alignment"]["channels"][0]["diagnostics"]["gain"]
        gain.update(linear_gain=0.0, observed_gain_db=-999.0, polarity="preserved", reason="zero_fitted_gain")
        self.assert_invalid(alignment)

    def test_gain_polarity_and_scale_must_agree(self):
        for key, value in (("polarity", "inverted"), ("linear_gain", 0.5), ("observed_gain_db", -6.0)):
            alignment = self.alignment()
            alignment["alignment"]["channels"][0]["diagnostics"]["gain"][key] = value
            self.assert_invalid(alignment)

    def test_subnormal_gain_rounding_does_not_invent_invalidity(self):
        gain = MODULE.ALIGN.gain_diagnostics([1.0], [5e-324])
        self.assertIsNone(gain["reason"])
        MODULE._gain(gain)

    def test_committed_report_matches_live_fixture_projection(self):
        path = ROOT / "research/toolchains/evidence/perceptual-degradation-oracle-validity-integration-synthetic-20260907-001.json"
        report = json.loads(path.read_text())
        self.assertEqual(MODULE.development.fixtures.sha(Path(MODULE.__file__)), report["implementation_sha256"])
        self.assertEqual(MODULE.PLAN_SHA, report["plan_sha256"])
        self.assertEqual(7, report["case_count"])
        self.assertEqual(3, report["execution_blocked_count"])
        self.assertEqual(4, report["unsupported_alignment_count"])
        self.assertEqual(list(self.records), [case["construction"] for case in report["cases"]])
        for case in report["cases"]:
            record = self.records[case["construction"]]
            self.assertEqual(record["result_state"], case["result_state"])
            self.assertEqual(record["support"], case["support"])
            self.assertEqual(MODULE.development.fixtures.formatted(record["alignment"]["alignment"]["summary"]), case["alignment_summary"])

    def test_missing_local_windows_keep_estimates_null(self):
        record = self.records["silent_window_subtle"]
        channel = record["alignment"]["alignment"]["channels"][0]["diagnostics"]
        self.assertEqual(4, channel["drift"]["valid_window_count"])
        self.assertEqual(6, channel["structural"]["valid_window_count"])
        for audit in ("drift", "structural"):
            for key in ("clock_drift_ppm", "residual_samples", "minimum_correlation"):
                alignment = self.alignment("silent_window_subtle")
                alignment["alignment"]["channels"][0]["diagnostics"][audit][key] = 1.0
                self.assert_invalid(alignment)

    def test_incomplete_window_counts_cannot_claim_completion(self):
        alignment = self.alignment("silent_window_subtle")
        alignment["alignment"]["channels"][0]["diagnostics"]["drift"]["valid_window_count"] = 5
        self.assert_invalid(alignment)

    def test_channel_reasons_cannot_be_dropped(self):
        alignment = self.alignment("silent_window_subtle")
        alignment["support"]["reasons"] = []
        self.assert_invalid(alignment)

    def test_low_correlation_cannot_remain_supported(self):
        alignment = self.alignment()
        correlation = alignment["alignment"]["channels"][0]["diagnostics"]["correlation"]
        correlation.update(value=0.1, magnitude=0.1)
        self.assert_invalid(alignment)

    def test_ambiguity_and_gain_limits_cannot_be_ignored(self):
        alignment = self.alignment()
        alignment["alignment"]["channels"][0]["diagnostics"]["ambiguity_margin"] = 0.0
        self.assert_invalid(alignment)
        alignment = self.alignment()
        alignment["alignment"]["channels"][0]["diagnostics"]["gain"].update(linear_gain=0.1, observed_gain_db=-20.0)
        self.assert_invalid(alignment)

    def test_channel_average_does_not_hide_per_channel_drift_rejection(self):
        alignment = self.alignment()
        for channel, drift in zip(alignment["alignment"]["channels"], (-101.0, 101.0), strict=True):
            channel["diagnostics"]["drift"]["clock_drift_ppm"] = drift
            channel["reasons"] = ["clock_drift_exceeds_limit"]
            channel["status"] = "unsupported"
        alignment["support"]["reasons"] = ["clock_drift_exceeds_limit"]
        alignment["status"] = "unsupported"
        self.assertEqual([], MODULE.validate_alignment(alignment, "subtle"))
        record = MODULE.assemble_score_free(alignment, comparison_mode="subtle")
        self.assertEqual(0.0, record["alignment"]["alignment"]["summary"]["clock_drift_ppm"])
        self.assertEqual("unsupported_alignment", record["result_state"])

    def test_topology_failure_is_preserved_and_not_fabricated(self):
        alignment = self.alignment("topology_mismatch")
        self.assertEqual(["channel_map_mismatch", "channel_topology_mismatch"], alignment["support"]["reasons"])
        alignment["support"]["reasons"] = ["unsupported_channel_map"]
        self.assert_invalid(alignment)

    def test_channel_removal_and_reordering_are_rejected(self):
        for operation in (lambda channels: channels.pop(), lambda channels: channels.reverse()):
            alignment = self.alignment()
            operation(alignment["alignment"]["channels"])
            self.assert_invalid(alignment)

    def test_boolean_and_nonfinite_numeric_values_are_rejected(self):
        for value in (True, False, math.nan, math.inf, -math.inf, "1"):
            alignment = self.alignment()
            alignment["alignment"]["channels"][0]["diagnostics"]["active_seconds"] = value
            self.assert_invalid(alignment)

    def test_false_flags_cannot_be_replaced_with_zero(self):
        alignment = self.alignment()
        alignment["public_verdict_enabled"] = 0
        self.assert_invalid(alignment)
        record = copy.deepcopy(self.records["identity_subtle"])
        record["public_verdict_enabled"] = 0
        self.assertTrue(MODULE.validate_score_free_record(record))

    def test_stale_identity_binding_and_unknown_mode_fail_closed(self):
        for key, value in (("record_kind", "perceptual_degradation_alignment_v2"), ("case_id", "invalid")):
            alignment = self.alignment()
            alignment[key] = value
            self.assert_invalid(alignment)
        self.assert_invalid(self.alignment(), "unselected")
        alignment = self.alignment()
        alignment["support"]["limits_id"] = "stale"
        self.assert_invalid(alignment)

    def test_nested_malformed_inputs_return_errors(self):
        for path in (("input",), ("alignment",), ("support",), ("alignment", "channels"), ("alignment", "summary")):
            alignment = self.alignment()
            target = alignment
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = None
            self.assert_invalid(alignment)
        for value in (None, [], False, "unknown"):
            self.assertTrue(MODULE.validate_alignment(value, "subtle"))
            self.assertTrue(MODULE.validate_score_free_record(value))

    def test_assembly_does_not_alias_callers_mutable_alignment(self):
        alignment = self.alignment()
        before = copy.deepcopy(alignment)
        result = MODULE.assemble_score_free(alignment, comparison_mode="subtle")
        self.assertEqual(before, alignment)
        alignment["alignment"]["channels"][0]["diagnostics"]["correlation"]["value"] = 0.0
        self.assertEqual(before, result["alignment"])

    def test_origin_and_clean_reference_eligibility_are_not_inferred(self):
        for record in self.records.values():
            self.assertEqual("unverified_by_assembler", record["evidence_scope"]["input_provenance"])
            self.assertEqual("unverified", record["evidence_scope"]["clean_reference_eligibility"])
            self.assertFalse(record["evidence_scope"]["synthetic_origin_inferred_from_record"])

    def test_probability_targets_are_distinct_and_unavailable(self):
        for record in self.records.values():
            outcomes = record["outcomes"]
            self.assertNotIn("audibility_probability", outcomes)
            for key in ("correct_response_probability", "audible_condition_probability", "impairment_severity"):
                self.assertIsNone(outcomes[key])
                self.assertIsNone(outcomes[f"{key}_interval"])
            self.assertIsNone(record["human_calibration"]["prediction_unit"])
            self.assertIsNone(record["human_calibration"]["population_averaging_rule"])
            self.assertTrue(all(value is None for value in outcomes["artifact_profile"]["components"].values()))

    def test_fabricated_oracle_outcomes_and_authority_are_rejected(self):
        for path, value in (
            (("outcomes", "correct_response_probability"), 0.5),
            (("outcomes", "audible_condition_probability"), 0.0),
            (("outcomes", "impairment_severity"), 0.0),
            (("outcomes", "categorical_state"), "transparent"),
            (("support", "supported"), True),
            (("metric_execution", "suite_selected"), True),
            (("metric_execution", "raw_outputs"), {}),
            (("uncertainty", "interval_level"), 0.95),
            (("evidence_scope", "input_provenance"), "verified"),
            (("human_calibration", "state"), "calibrated"),
            (("alignment_configuration", "minimum_active_seconds"), 0.1),
        ):
            record = copy.deepcopy(self.records["identity_subtle"])
            record[path[0]][path[1]] = value
            self.assertTrue(MODULE.validate_score_free_record(record))

    def test_serialization_round_trip_preserves_null_and_sign(self):
        for record in self.records.values():
            decoded = json.loads(MODULE.canonical(record))
            self.assertEqual(record, decoded)
            self.assertEqual([], MODULE.validate_score_free_record(decoded))

    def test_plan_mutation_and_resource_floor_fail_closed(self):
        with patch.object(MODULE, "PLAN_SHA", "0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            MODULE.synthetic_records()
        with patch.object(MODULE.development.fixtures.shutil, "disk_usage") as usage:
            usage.return_value.free = 15 * 1024**3 - 1
            with self.assertRaisesRegex(ValueError, "reserve"):
                MODULE.synthetic_records()

    def test_cli_rejects_audio_route_even_with_synthetic_flag(self):
        result = subprocess.run([sys.executable, str(Path(MODULE.__file__)), "--synthetic", "--input", "undeclared.wav"], capture_output=True, text=True, check=False)
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("unrecognized arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
