from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "validate-audio-integrity-v2-factor-levels.py"
)
SPEC = importlib.util.spec_from_file_location("factor_levels", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
factor_levels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(factor_levels)
REPOSITORY_ROOT = SCRIPT.parents[1]
FACTORS = factor_levels.load_object(
    REPOSITORY_ROOT / "benchmarks/audio-integrity-v2/factor-levels.json"
)
CONTRACT = factor_levels.load_object(
    REPOSITORY_ROOT / "benchmarks/audio-integrity-v2/factorial-contract.json"
)
INVENTORY = factor_levels.load_object(
    REPOSITORY_ROOT / "benchmarks/audio-integrity-v2/inventory.json"
)


class FactorLevelTests(unittest.TestCase):
    def test_committed_factor_levels_validate(self) -> None:
        self.assertEqual(
            factor_levels.validate(
                FACTORS, CONTRACT, INVENTORY, REPOSITORY_ROOT
            ),
            [],
        )

    def test_encoder_transfer_lineage_overlap_is_rejected(self) -> None:
        broken = copy.deepcopy(FACTORS)
        row = next(
            item
            for item in broken["codec_setting_templates"]
            if item["template_id"] == "transfer-mp3-bladeenc-cbr96-default"
        )
        row["encoder_id"] = "mp3_lame_4_0"
        row["lineage_id"] = "lame"
        errors = factor_levels.validate(
            broken, CONTRACT, INVENTORY, REPOSITORY_ROOT
        )
        self.assertTrue(
            any("lineages overlap" in error for error in errors), errors
        )

    def test_missing_codec_anchor_is_rejected(self) -> None:
        broken = copy.deepcopy(FACTORS)
        row = next(
            item
            for item in broken["codec_setting_templates"]
            if item["template_id"] == "dev-opus-libopus-cbr96-20ms"
        )
        row.pop("anchor")
        errors = factor_levels.validate(
            broken, CONTRACT, INVENTORY, REPOSITORY_ROOT
        )
        self.assertIn(
            "mechanism_development opus must have exactly one anchor template",
            errors,
        )

    def test_too_few_hard_negative_classes_is_rejected(self) -> None:
        broken = copy.deepcopy(FACTORS)
        broken["pcm_transform_levels"] = broken["pcm_transform_levels"][:8]
        errors = factor_levels.validate(
            broken, CONTRACT, INVENTORY, REPOSITORY_ROOT
        )
        self.assertIn(
            "PCM transforms need at least eight distinct hard-negative classes",
            errors,
        )

    def test_premature_binary_binding_is_rejected(self) -> None:
        broken = copy.deepcopy(FACTORS)
        broken["codec_setting_templates"][0]["binary_sha256"] = "a" * 64
        errors = factor_levels.validate(
            broken, CONTRACT, INVENTORY, REPOSITORY_ROOT
        )
        self.assertTrue(
            any("premature tool/audio bindings" in error for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
