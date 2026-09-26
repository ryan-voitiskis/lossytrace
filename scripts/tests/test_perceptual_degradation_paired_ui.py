from __future__ import annotations

import copy
import hashlib
import importlib.util
import itertools
import json
import subprocess
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_paired_ui.py"
UI = ROOT / "research/listening-paired-ui"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-paired-ui-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("paired_ui", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


class PairedUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paired = MODULE.paired_module()
        cls.report = MODULE.build_synthetic_report()

    def test_fixture_is_exact_role_free_predecessor_projection(self):
        MODULE.validate_fixture()
        text = (UI / "fixture.js").read_text()
        values = json.loads(text.removeprefix(MODULE.PREFIX).removesuffix(MODULE.SUFFIX))
        self.assertEqual(2, len(values))
        self.assertEqual([self.paired.presentation_assignment(item) for item in MODULE.assignments()], values)
        for marker in ("condition_position", "source_group", "participant_id", "recipe", "metric_score", "analysis_group"):
            self.assertNotIn(marker, text)

    def test_both_incorrect_choices_keep_their_signed_targets(self):
        projected = MODULE.project_synthetic_records(MODULE.synthetic_records())
        self.assertEqual([False, False], [row["forced_choice_correct"] for row in projected])
        self.assertEqual([0.6, -0.6], [row["paired_sdg"] for row in projected])
        self.assertTrue(all(row["complete_pair_analysis_eligible"] for row in projected))
        self.assertTrue(all(row["scientific_truth_eligible"] is False for row in projected))

    def test_incomplete_ui_event_records_are_not_imputed(self):
        for count in range(4):
            records = MODULE.synthetic_records()[:1]
            records[0]["events"] = records[0]["events"][:count]
            records[0]["final_grade_ticks_by_position"] = {"A": 50 if count >= 2 else None, "B": 44 if count >= 3 else None}
            row = MODULE.project_synthetic_records(records)[0]
            self.assertIsNone(row["paired_sdg"])
            self.assertFalse(row["complete_pair_analysis_eligible"])

    def test_cleared_or_invalid_final_draft_does_not_reuse_an_earlier_grade(self):
        records = MODULE.synthetic_records()[:1]
        records[0]["events"] = records[0]["events"][:-1]
        records[0]["final_grade_ticks_by_position"]["B"] = None
        row = MODULE.project_synthetic_records(records)[0]
        self.assertEqual(50, row["condition_grade_ticks"])
        self.assertIsNone(row["hidden_reference_grade_ticks"])
        self.assertIsNone(row["paired_sdg"])
        records[0]["events"].append({"sequence": 3, "kind": "submit"})
        with self.assertRaisesRegex(ValueError, "blank final grade"):
            MODULE.project_synthetic_records(records)

    def test_final_grades_must_have_matching_accepted_events(self):
        for value in (True, 49, 44.0, "44", 51):
            records = MODULE.synthetic_records()[:1]
            records[0]["final_grade_ticks_by_position"]["B"] = value
            with self.assertRaises(ValueError):
                MODULE.project_synthetic_records(records)

    def test_unknown_duplicate_or_mismatched_assignments_rejected(self):
        records = MODULE.synthetic_records()
        with self.assertRaises(ValueError):
            MODULE.project_synthetic_records([records[0], records[0]])
        for key, value in (("assignment_id", "assignment-unknown"), ("trial_id", "trial-unknown"), ("candidate_ids", {"A": "stimulus-elsewhere", "B": "stimulus-elsewhere"}), ("fixture_only", 1)):
            altered = copy.deepcopy(records)
            altered[0]["presentation"][key] = value
            with self.assertRaises(ValueError):
                MODULE.project_synthetic_records(altered)
        for value in ([], {}, None, records * 2):
            with self.assertRaises(ValueError):
                MODULE.project_synthetic_records(value)

    def test_observed_or_extra_fields_and_wrong_types_rejected(self):
        for key, value in (("schema_version", True), ("state", "observed"), ("fixture_only", False), ("human_collection_authorized", True), ("path", "not-accepted"), ("sdg", -2), ("forced_choice_correct", True)):
            records = MODULE.synthetic_records()
            records[0][key] = value
            with self.assertRaises(ValueError):
                MODULE.project_synthetic_records(records)

    def test_javascript_and_python_valid_event_parity(self):
        cases = []
        for choice, grade_a, grade_b in itertools.product(("A", "B"), (10, 11, 25, 44, 49, 50), (10, 11, 25, 44, 49, 50)):
            events = [
                {"sequence": 0, "kind": "lock_choice", "position": choice},
                {"sequence": 1, "kind": "grade", "position": "A", "grade_ticks": grade_a},
                {"sequence": 2, "kind": "grade", "position": "B", "grade_ticks": grade_b},
                {"sequence": 3, "kind": "submit"},
            ]
            cases.extend(events[:count] for count in range(5))
        javascript = MODULE.javascript_replay(cases)
        presentation = MODULE.synthetic_records()[0]["presentation"]
        for events, actual in zip(cases, javascript, strict=True):
            expected = self.paired.reduce_events(presentation, events)
            self.assertTrue(actual["accepted"])
            self.assertEqual({key: expected[key] for key in actual["response"]}, actual["response"])

    def test_javascript_and_python_invalid_event_parity(self):
        base = MODULE.synthetic_records()[0]["events"]
        cases = [None, {}, [None], [True], [{"sequence": 0, "kind": "submit"}]]
        for key, value in (("sequence", True), ("sequence", 99), ("kind", "unknown"), ("position", "C"), ("grade_ticks", True), ("grade_ticks", 9), ("grade_ticks", 51), ("grade_ticks", 44.1), ("grade_ticks", None), ("grade_ticks", "44"), ("role", "hidden")):
            events = copy.deepcopy(base)
            events[1][key] = value
            cases.append(events)
        cases.extend([
            base + [{"sequence": 4, "kind": "grade", "position": "A", "grade_ticks": 30}],
            [base[0], {**base[0], "sequence": 1}],
            [{**base[1], "sequence": 0}],
            [base[0]] + [{"sequence": i, "kind": "grade", "position": "A", "grade_ticks": 30} for i in range(1, 101)],
        ])
        javascript = MODULE.javascript_replay(cases)
        presentation = MODULE.synthetic_records()[0]["presentation"]
        for events, result in zip(cases, javascript, strict=True):
            with self.assertRaises(ValueError):
                self.paired.reduce_events(presentation, events)
            self.assertFalse(result["accepted"])

    def test_grade_parser_has_no_defaults_or_noninteger_tick_precision(self):
        values = ["", " ", "0", "5.1", "1.05", "NaN", "Infinity", "4e0", None, 4, True, "1", "1.0", "4.4", "5.0"]
        code = "const c=require(process.argv[1]);const v=JSON.parse(require('node:fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(v.map(c.gradeTicks)));"
        run = subprocess.run(["node", "-e", code, str(UI / "state.js")], input=json.dumps(values), text=True, capture_output=True, check=True)
        self.assertEqual([None] * 11 + [10, 10, 44, 50], json.loads(run.stdout))

    def test_html_has_blank_disabled_grades_and_only_local_text_assets(self):
        parser = Elements()
        parser.feed((UI / "index.html").read_text())
        resources = [attrs[key] for _, attrs in parser.items for key in ("src", "href") if key in attrs]
        self.assertEqual(["style.css", "fixture.js", "state.js", "app.js"], resources)
        for item in resources:
            self.assertTrue((UI / item).is_file())
        controls = {attrs["id"]: (tag, attrs) for tag, attrs in parser.items if "id" in attrs}
        self.assertIn("disabled", controls["grade-field"][1])
        self.assertIn("disabled", controls["submit-pair"][1])
        for key in ("grade-a", "grade-b"):
            self.assertNotIn("value", controls[key][1])
        self.assertFalse(any(tag in ("audio", "video", "iframe", "form") for tag, _ in parser.items))
        csp = next(attrs["content"] for tag, attrs in parser.items if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy")
        for policy in ("connect-src 'none'", "media-src 'none'", "form-action 'none'", "default-src 'none'"):
            self.assertIn(policy, csp)

    def test_application_has_no_audio_network_or_persistence_api(self):
        source = "\n".join((UI / name).read_text() for name in ("app.js", "state.js", "fixture.js"))
        for token in ("AudioContext", "getUserMedia", "MediaRecorder", "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "localStorage", "sessionStorage", "indexedDB", "document.cookie", "navigator.mediaDevices"):
            self.assertNotIn(token, source)
        self.assertIn("human_collection_authorized: false", source)

    def test_plan_bindings_and_access_cannot_be_reinterpreted(self):
        original = json.loads(MODULE.PLAN.read_text())
        for section, key, value in (("access_boundary", "playback_authorized", True), ("access_boundary", "synthetic_execution_only", 1), ("access_boundary", "human_collection_authorized", True)):
            plan = copy.deepcopy(original)
            plan[section][key] = value
            with mock.patch.object(MODULE.json, "loads", return_value=plan), self.assertRaises(ValueError):
                MODULE.load_plan()
        plan = copy.deepcopy(original)
        plan["bindings"]["state_machine"]["path"] = "unopened.js"
        with mock.patch.object(MODULE.json, "loads", return_value=plan), self.assertRaises(ValueError):
            MODULE.load_plan()

    def test_report_replays_exactly_and_does_not_claim_browser_or_human_truth(self):
        actual = MODULE.canonical_bytes(self.report)
        self.assertEqual(actual, MODULE.canonical_bytes(MODULE.build_synthetic_report()))
        self.assertEqual(actual, EVIDENCE.read_bytes())
        for field in ("browser_behavior_verified_by_this_replay", "human_responses_observed", "perceptual_truth_eligible", "playback_qualified", "objective_complete"):
            self.assertIs(False, self.report[field])
        for marker in (b"participant-", b"assignment-", b"stimulus-", b"/Users/", b".wav"):
            self.assertNotIn(marker, actual)

    def test_cli_has_no_response_input_option(self):
        for args in ([], ["--synthetic", "--input", "unopened.json"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"", result.stdout)

    def test_browser_observation_binds_final_sources_without_claiming_listening(self):
        observed = json.loads((ROOT / "research/toolchains/evidence/perceptual-degradation-paired-ui-browser-observed-20260905-001.json").read_text())
        plan = MODULE.load_plan()
        self.assertEqual(plan["bindings"], observed["source_bindings"])
        self.assertEqual(hashlib.sha256(SCRIPT.read_bytes()).hexdigest(), observed["adapter_sha256"])
        self.assertEqual(hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), observed["tests_sha256"])
        self.assertTrue(observed["browser_checks"]["final_draft_missingness_preserved"])
        self.assertTrue(observed["browser_checks"]["complete_records_match_declared_fixtures"])
        self.assertEqual([0.6, -0.6], observed["complete_pair_projection"]["signed_pair_differences"])
        for field in ("human_responses_observed", "perceptual_truth_eligible", "playback_qualified", "browser_binary_binding_complete", "objective_complete"):
            self.assertIs(False, observed[field])
        for item in observed["viewports"]:
            self.assertLessEqual(item["document_width"], item["width"])


if __name__ == "__main__":
    unittest.main()
