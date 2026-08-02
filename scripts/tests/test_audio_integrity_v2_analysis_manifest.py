from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "compose-audio-integrity-v2-analysis-manifest.py"
PLAN_PATH = ROOT / "benchmarks" / "audio-integrity-v2" / "analysis-manifest-plan.json"
SPEC = importlib.util.spec_from_file_location("v2_analysis_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class AudioIntegrityV2AnalysisManifestTest(unittest.TestCase):
    def test_plan_is_score_free_and_binds_generator(self) -> None:
        self.assertEqual(
            "analysis_manifest_materialization_frozen_before_replay", PLAN["state"]
        )
        self.assertFalse(PLAN["features_computed"])
        self.assertFalse(PLAN["scores_opened"])
        self.assertFalse(PLAN["public_verdict_enabled"])
        self.assertEqual(2, PLAN["complete_replays_required"])
        self.assertEqual(1, len(PLAN["correction_history"]))
        self.assertEqual(
            0, PLAN["correction_history"][0]["artifact_bytes_read_before_correction"]
        )
        self.assertEqual(
            MODULE.sha256_file(SCRIPT), PLAN["bindings"]["generator_sha256"]
        )

    def test_private_identifiers_are_recipe_addressed(self) -> None:
        identity = "a" * 64
        self.assertEqual(f"case-{identity}", MODULE.case_id(identity))
        self.assertEqual(f"recipe-{identity}", MODULE.recipe_id(identity))

    def test_recipe_digest_is_deterministic_and_source_bound(self) -> None:
        arguments = {
            "cell": {"assignment_id": "b" * 64, "transform_id": "identity"},
            "construction_plan_sha256": "c" * 64,
            "generator_sha256": "d" * 64,
            "toolchain_sha256": "e" * 64,
            "source_assignment_id": "f" * 64,
            "tool_ids": ["tool-a"],
        }
        first = MODULE.recipe_definition(**arguments)
        second = MODULE.recipe_definition(**arguments)
        self.assertEqual(first, second)
        changed = MODULE.recipe_definition(
            **{**arguments, "source_assignment_id": "0" * 64}
        )
        self.assertNotEqual(first["command_sha256"], changed["command_sha256"])

    def test_public_output_rejects_private_identity_and_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "private key"):
            MODULE.assert_public_path_free({"case_id": "private"})
        with self.assertRaisesRegex(ValueError, "absolute path"):
            MODULE.assert_public_path_free({"note": "/private/output"})


if __name__ == "__main__":
    unittest.main()
