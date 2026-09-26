import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave


SPEC = importlib.util.spec_from_file_location(
    "lossprint_qualification", Path(__file__).parents[1] / "lossprint_qualification.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QualificationTests(unittest.TestCase):
    def test_saved_aggregate_binds_executed_plan_and_runner(self):
        root = Path(__file__).parents[2]
        evidence = json.loads((root / "research/baselines/lossprint/evidence/"
                               "software-qualification-20260927-001.json").read_text())
        self.assertEqual(evidence["plan_sha256"], MODULE.digest(
            root / "docs/research/lossprint-qualification-plan-20260927.md"))
        self.assertEqual(evidence["runner_sha256"], MODULE.digest(Path(MODULE.__file__)))
        self.assertEqual(evidence["model_sha256"], MODULE.MODEL_SHA256)
        self.assertEqual(evidence["planned_slots"], len(MODULE.CASES) * 2)
        self.assertIsNone(evidence["detector_accuracy"])
        self.assertFalse(evidence["public_verdict_enabled"])

    def row(self, score=0.2):
        return {"path": "/synthetic.wav", "transcode_probability": score,
                "verdict": "clean", "encoder": None, "bitrate_kbps": None}

    def records(self):
        return [{"round": rnd, "case_id": case[0], "expected_rejection": case[4],
                 "passed": True, **({"normalized": self.row()} if case[4] is None else {})}
                for rnd in (1, 2) for case in MODULE.CASES]

    def test_fixture_inventory_and_denominators(self):
        result = MODULE.aggregate(self.records(), True, True)
        self.assertTrue(result["passed"])
        self.assertEqual(result["eligible_slots"], 18)
        self.assertEqual(result["ineligible_slots"], 6)
        self.assertIsNone(result["detector_accuracy"])
        self.assertFalse(result["public_verdict_enabled"])

    def test_missing_reordered_or_duplicated_slots_cannot_pass(self):
        rows = self.records()
        for changed in (rows[:-1], list(reversed(rows)), rows[:-1] + [rows[0]]):
            with self.subTest(changed=changed[-1]["case_id"]):
                self.assertFalse(MODULE.aggregate(changed, True, True)["passed"])

    def test_replay_mismatch_fails(self):
        rows = self.records()
        rows[15]["normalized"]["transcode_probability"] = 0.3
        self.assertFalse(MODULE.aggregate(rows, True, True)["exact_replay_match"])

    def test_wrapper_mismatch_fails_even_when_repeated(self):
        rows = self.records()
        for row in rows:
            if row["case_id"] == "wrapper_flac":
                row["normalized"]["transcode_probability"] = 0.3
        result = MODULE.aggregate(rows, True, True)
        self.assertTrue(result["exact_replay_match"])
        self.assertFalse(result["passed"])

    def test_integrity_or_pcm_mismatch_fails(self):
        for integrity, wrappers in ((False, True), (True, False)):
            self.assertFalse(MODULE.aggregate(self.records(), integrity, wrappers)["passed"])

    def test_not_started_and_timeout_stay_in_denominator(self):
        rows = self.records()
        rows[0].update(passed=False, not_started=True)
        rows[1].update(passed=False, timeout=True)
        result = MODULE.aggregate(rows, True, True)
        self.assertEqual(result["accounted_slots"], 24)
        self.assertEqual(result["eligible_completed"], 16)
        self.assertEqual(result["timeouts"], 1)
        self.assertEqual(result["not_started"], 1)
        self.assertFalse(result["passed"])

    def test_normalization_removes_only_identity(self):
        row = self.row()
        result = MODULE.normalize(json.dumps(row), Path("/synthetic.wav"))
        self.assertEqual(result, {key: value for key, value in row.items() if key != "path"})
        with self.assertRaises(ValueError):
            MODULE.normalize(json.dumps(row), Path("/wrong.wav"))

    def test_threshold_boundary_retains_upstream_label(self):
        row = self.row(0.5)
        with self.assertRaises(ValueError):
            MODULE.normalize(json.dumps(row), Path("/synthetic.wav"))
        row.update(verdict="transcode", encoder="ffmpeg_aac", bitrate_kbps=192.0)
        self.assertEqual(MODULE.normalize(json.dumps(row), Path("/synthetic.wav"))["encoder"],
                         "ffmpeg_aac")

    def test_nonfinite_boolean_and_invalid_outputs_fail(self):
        for score in (float("nan"), float("inf"), -0.1, 1.1, True, "0.2"):
            with self.subTest(score=score), self.assertRaises(ValueError):
                MODULE.normalize(json.dumps(self.row(score)), Path("/synthetic.wav"))
        for mutation in ({"unexpected": 3}, {"encoder": "mp3"}, {"bitrate_kbps": 192}):
            row = self.row()
            row.update(mutation)
            with self.assertRaises(ValueError):
                MODULE.normalize(json.dumps(row), Path("/synthetic.wav"))

    def test_noise_recipe_and_wav_are_exact(self):
        expected_first = ((1664525 + 1013904223) >> 18) - 8192
        data = MODULE.pcm(8, 2)
        self.assertEqual(len(data), 32)
        self.assertEqual(int.from_bytes(data[:2], "little", signed=True), expected_first)
        self.assertEqual(data, MODULE.pcm(8, 2))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "numeric.wav"
            generated = MODULE.write_wav(path, 8000, 2, 1)
            with wave.open(str(path), "rb") as reader:
                self.assertEqual(reader.getparams()[:4], (2, 2, 8000, 4000))
                self.assertEqual(reader.readframes(4000), generated)

    def test_timeout_records_partial_output(self):
        error = subprocess.TimeoutExpired(["fake"], 60, output=b"partial", stderr=b"detail")
        with patch.object(MODULE.subprocess, "run", side_effect=error):
            result = MODULE.invoke(["fake"], 60)
        self.assertTrue(result["timeout"])
        self.assertIsNone(result["returncode"])
        self.assertEqual(result["stdout"], "partial")

    def test_spawn_failure_is_accounted(self):
        with patch.object(MODULE.subprocess, "run", side_effect=OSError("unavailable")):
            result = MODULE.invoke(["fake"], 60)
        self.assertIsNone(result["returncode"])
        self.assertIn("unavailable", result["stderr"])


if __name__ == "__main__":
    unittest.main()
