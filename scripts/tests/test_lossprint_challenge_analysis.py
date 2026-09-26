from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import run_lossprint_challenge as runner
from test_lossprint_challenge import cases
from lossprint_challenge import select_cases


class AnalysisTests(unittest.TestCase):
    def test_prospective_plan_binds_all_consumed_dependencies(self):
        root = Path(__file__).parents[2]
        plan = json.loads((root / "research/baselines/lossprint/challenge-execution-plan-20260927.json").read_text())
        for relative, expected in plan["repository_bindings"].items():
            with self.subTest(path=relative):
                self.assertEqual(runner.digest(root / relative), expected)
        self.assertEqual(plan["planned_slots"], plan["artifacts"] * 2)
        self.assertEqual(plan["threshold"], .5)

    def fixture(self):
        rows, reps = select_cases(cases(), {"a", "b"})
        selection = {"cases": rows, "representative_ids": [c["case_id"] for c in reps]}
        records = []
        for rnd in (1, 2):
            for c in reps:
                positive = c["expectation"] == "controlled_positive"
                records.append({"round": rnd, "case_id": c["case_id"], "status": "supported",
                                "output": {"verdict": "transcode" if positive else "clean",
                                           "transcode_probability": .9 if positive else .1,
                                           "encoder": "mp3" if positive else None,
                                           "bitrate_kbps": 128 if positive else None}})
        return selection, records

    def test_perfect_fixture_passes_not_independent_validation(self):
        result = runner.analyze(*self.fixture(), True)
        self.assertTrue(result["technical_passed"])
        self.assertTrue(result["continuation_passed"])
        self.assertFalse(result["independent_validation"])
        self.assertFalse(result["public_verdict_enabled"])
        self.assertEqual(result["case_metrics"]["supported_recall"], 1)
        self.assertEqual(result["bitrate"]["eligible_cases"], 0)

    def test_one_negative_alert_fails_even_if_repeated(self):
        selection, rows = self.fixture()
        identity = next(c["case_id"] for c in selection["cases"] if c["expectation"] == "negative")
        for r in rows:
            if r["case_id"] == identity:
                r["output"].update(verdict="transcode", transcode_probability=.7, encoder="mp3", bitrate_kbps=128)
        result = runner.analyze(selection, rows, True)
        self.assertTrue(result["technical_passed"])
        self.assertFalse(result["continuation_passed"])
        self.assertEqual(result["case_metrics"]["false_alert_cases"], 1)

    def test_all_negative_predictions_fail_usefulness(self):
        selection, rows = self.fixture()
        for r in rows:
            r["output"].update(verdict="clean", transcode_probability=.1, encoder=None, bitrate_kbps=None)
        result = runner.analyze(selection, rows, True)
        self.assertTrue(result["technical_passed"])
        self.assertFalse(result["continuation_passed"])

    def test_family_correctness_is_conditional_and_separate(self):
        selection, rows = self.fixture()
        for r in rows:
            if r["output"]["verdict"] == "transcode":
                r["output"]["encoder"] = "vorbis"
        result = runner.analyze(selection, rows, True)
        self.assertTrue(result["continuation_passed"])
        self.assertEqual(result["case_metrics"]["family_accuracy_given_detection"], 0)

    def test_missing_duplicate_or_reordered_slots_fail(self):
        selection, rows = self.fixture()
        for altered in (rows[:-1], rows[:-1] + [rows[0]], list(reversed(rows))):
            self.assertFalse(runner.analyze(selection, altered, True)["technical_passed"])

    def test_replay_mismatch_fails(self):
        selection, rows = self.fixture()
        rows[0]["output"]["transcode_probability"] = .6
        self.assertFalse(runner.analyze(selection, rows, True)["technical_passed"])

    def test_integrity_failure_fails(self):
        self.assertFalse(runner.analyze(*self.fixture(), False)["technical_passed"])

    def test_failure_and_unstarted_remain_in_denominators(self):
        selection, rows = self.fixture()
        rows[0].update(status="failed", output=None)
        rows[1].update(status="not_started", output=None)
        result = runner.analyze(selection, rows, True)
        self.assertFalse(result["technical_passed"])
        self.assertEqual(result["accounted_slots"], 40)
        self.assertEqual(result["case_metrics"]["positive_cases"], 10)
        self.assertEqual(result["case_metrics"]["negative_cases"], 10)

    def test_undeclared_unsupported_fails(self):
        selection, rows = self.fixture()
        for r in rows:
            r.update(status="unsupported", output=None)
        self.assertFalse(runner.analyze(selection, rows, True)["technical_passed"])

    def test_wrapper_difference_fails(self):
        selection, rows = self.fixture()
        original = selection["cases"][0]
        alias = dict(original, case_id="wrapper", representative_case_id="wrapper", lossless_wrapper_id="flac16")
        selection["cases"].append(alias)
        selection["representative_ids"].append("wrapper")
        output = dict(rows[0]["output"], transcode_probability=.85)
        rows.insert(20, {"round": 1, "case_id": "wrapper", "status": "supported", "output": output})
        rows.append({"round": 2, "case_id": "wrapper", "status": "supported", "output": output})
        result = runner.analyze(selection, rows, True)
        self.assertTrue(result["exact_replay_match"])
        self.assertFalse(result["wrapper_consistency"])
        self.assertFalse(result["technical_passed"])

    def test_actual_cli_flags_fixed(self):
        self.assertEqual(runner.command(Path("lossprint"), Path("fixture.wav")),
                         ["lossprint", "--jobs", "1", "--threshold", "0.5", "-o", "jsonl", "fixture.wav"])

    def test_ci_requires_exact_head_workflow_repository_and_success(self):
        ci = {"head_sha": "head", "status": "completed", "conclusion": "success",
              "path": ".github/workflows/ci.yml", "repository": {"full_name": "ryan-voitiskis/lossytrace"}}
        self.assertTrue(runner.ci_matches(ci, "head"))
        self.assertFalse(runner.ci_matches(ci, "different"))
        for mutation in ({"conclusion": "failure"}, {"status": "in_progress"}, {"path": "other"}, {"repository": {}}):
            self.assertFalse(runner.ci_matches(dict(ci, **mutation), "head"))

    def test_aac_normalization_does_not_claim_encoder(self):
        self.assertEqual(runner.family("aac_lc"), runner.family("ffmpeg_aac"))


if __name__ == "__main__":
    unittest.main()
