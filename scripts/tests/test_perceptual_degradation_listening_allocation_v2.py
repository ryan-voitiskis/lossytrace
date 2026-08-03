from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V1_SCRIPT = ROOT / "scripts/perceptual_degradation_listening_allocation.py"
V1_SCHEMA = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/listening-stimulus-manifest.schema.json"
)
V2_SCHEMA = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/listening-stimulus-manifest-v2.schema.json"
)
V2_SCRIPT = ROOT / "scripts/perceptual_degradation_listening_allocation_v2.py"
MANIFEST = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/listening-stimulus-manifest.synthetic.json"
)
SPEC = importlib.util.spec_from_file_location("listening_allocation_v2", V2_SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest_v2() -> dict:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    value["schema_version"] = 2
    return value


class ListeningAllocationV2Test(unittest.TestCase):
    def test_historical_v1_files_remain_byte_bound(self) -> None:
        self.assertEqual(
            "a9f94e6bc3789de2af78473df0c5f433029186dcb0aad18a709d9a0f237603a6",
            hashlib.sha256(V1_SCHEMA.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            "2fbe6a0782e6f7652bf60924f27141c511402adea6d0bbb532c4b371edb7d2fc",
            hashlib.sha256(V1_SCRIPT.read_bytes()).hexdigest(),
        )

    def test_v2_schema_requires_transparency_candidate(self) -> None:
        schema = json.loads(V2_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(2, schema["properties"]["schema_version"]["const"])
        condition_classes = schema["$defs"]["stimulus"]["properties"][
            "condition_class"
        ]["enum"]
        self.assertIn("transparency_candidate", condition_classes)
        self.assertNotIn("transparent_codec", condition_classes)

    def test_v2_candidate_validates_without_truth_assignment(self) -> None:
        value = manifest_v2()
        value["stimuli"][2]["condition_class"] = "transparency_candidate"
        value["stimuli"][2]["controlled_codec_intervention"] = True
        self.assertEqual([], MODULE.validate_manifest(value))

    def test_v2_rejects_old_transparency_label(self) -> None:
        value = manifest_v2()
        value["stimuli"][2]["condition_class"] = "transparent_codec"
        self.assertIn(
            "stimulus-s0003: v2 requires transparency_candidate",
            MODULE.validate_manifest(value),
        )

    def test_v2_reuses_v1_randomization_without_exposing_recipes(self) -> None:
        value = manifest_v2()
        value["stimuli"][2]["condition_class"] = "transparency_candidate"
        value["stimuli"][2]["controlled_codec_intervention"] = True
        first = MODULE.allocate(value, "participant", "seed", 4)
        second = MODULE.allocate(copy.deepcopy(value), "participant", "seed", 4)
        self.assertEqual(first, second)
        self.assertEqual(2, first["schema_version"])
        self.assertEqual(2, first["manifest_schema_version"])
        self.assertFalse(first["condition_recipes_included"])
        self.assertNotIn("transparency_candidate", json.dumps(first))


if __name__ == "__main__":
    unittest.main()
