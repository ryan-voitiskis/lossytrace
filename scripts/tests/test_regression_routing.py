from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import run_regression_tests as runner


class RegressionRoutingTests(unittest.TestCase):
    def test_exact_archival_inventory(self):
        self.assertEqual(len(runner.HISTORICAL), 23)
        self.assertIn("test_audio_integrity_v2_public_decoder_probe", runner.HISTORICAL)
        self.assertIn("test_perceptual_degradation_objective_completion_audit_v22", runner.HISTORICAL)

    def test_current_tests_cannot_be_silently_omitted(self):
        names = set(runner.HISTORICAL) | {"test_lossprint_challenge", "test_future_feature"}
        current, historical = runner.split_modules(names)
        self.assertEqual(set(current) | set(historical), names)
        self.assertFalse(set(current) & set(historical))
        self.assertEqual(current, ["test_future_feature", "test_lossprint_challenge"])

    def test_missing_historical_module_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            runner.split_modules(set())

    def test_historical_edits_and_deletions_cannot_be_relabelled(self):
        self.assertTrue(runner.preserved("research/result.json", b"original", b"original"))
        self.assertFalse(runner.preserved("research/result.json", b"original", b"updated"))
        self.assertFalse(runner.preserved("research/result.json", b"original", b"original extra"))

    def test_status_is_append_only(self):
        self.assertTrue(runner.preserved("docs/research/status.md", b"old\n", b"old\nnew\n"))
        self.assertFalse(runner.preserved("docs/research/status.md", b"old\n", b"rewritten\n"))

    def test_script_invocation_can_import_repository_namespace(self):
        script_dir = str(Path(runner.__file__).parent)
        code = (f"import sys; sys.path.insert(0, {script_dir!r}); "
                "import run_regression_tests as r; "
                "raise SystemExit(not r.run_current(['test_audio_integrity_relocation']))")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-c", code], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
