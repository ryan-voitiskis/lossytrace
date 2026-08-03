from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "perceptual_degradation_listening_allocation.py"
SPEC = importlib.util.spec_from_file_location("listening_allocation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def stimulus(stimulus_id: str, role: str, active: float = 10) -> dict:
    condition_class = {
        "reference": "reference",
        "hidden_reference": "reference",
        "condition": "pcm_control",
        "anchor_low": "anchor",
        "anchor_mid": "anchor",
    }[role]
    return {
        "stimulus_id": stimulus_id,
        "source_group_id": "source-0001",
        "partition_group_id": "partition-0001",
        "partition": "development",
        "domain": "music",
        "role": role,
        "condition_class": condition_class,
        "controlled_codec_intervention": False,
        "duration_seconds": 10,
        "active_seconds": active,
        "sample_rate_hz": 48000,
        "channel_count": 2,
        "channel_map": "L_R",
        "private_audio_sha256": "a" * 64,
        "licence_record_id": "licence-0001",
    }


def manifest() -> dict:
    stimuli = [
        stimulus("reference-0001", "reference"),
        stimulus("hiddenref-0001", "hidden_reference"),
        stimulus("condition-0001", "condition"),
        stimulus("anchorlow-0001", "anchor_low"),
        stimulus("anchormid-0001", "anchor_mid"),
    ]
    return {
        "schema_version": 1,
        "manifest_id": "manifest-synthetic-0001",
        "state": "score_blind_preparation",
        "human_collection_authorized": False,
        "condition_recipes_visible_to_listener": False,
        "stimuli": stimuli,
        "trials": [
            {
                "trial_id": "trial-subtle-0001",
                "method": "subtle",
                "partition": "development",
                "visible_reference_id": "reference-0001",
                "candidate_ids": ["hiddenref-0001", "condition-0001"],
            },
            {
                "trial_id": "trial-mushra-0001",
                "method": "mushra",
                "partition": "development",
                "visible_reference_id": "reference-0001",
                "candidate_ids": [
                    "hiddenref-0001",
                    "condition-0001",
                    "anchorlow-0001",
                    "anchormid-0001",
                ],
            },
        ],
    }


class ListeningAllocationTest(unittest.TestCase):
    def test_manifest_is_valid_and_assignment_is_deterministic_and_blind(self) -> None:
        value = manifest()
        self.assertEqual([], MODULE.validate_manifest(value))
        first = MODULE.allocate(value, "participant-private", "seed-public")
        second = MODULE.allocate(value, "participant-private", "seed-public")
        self.assertEqual(first, second)
        self.assertFalse(first["participant_key_included"])
        self.assertFalse(first["condition_recipes_included"])
        self.assertNotIn("participant-private", str(first))
        self.assertEqual(2, len(first["blocks"]))

    def test_participants_receive_distinct_assignments(self) -> None:
        first = MODULE.allocate(manifest(), "participant-one", "seed-public")
        second = MODULE.allocate(manifest(), "participant-two", "seed-public")
        self.assertNotEqual(first["assignment_id"], second["assignment_id"])

    def test_subtle_trial_requires_one_hidden_reference_and_condition(self) -> None:
        changed = copy.deepcopy(manifest())
        changed["trials"][0]["candidate_ids"] = [
            "condition-0001",
            "anchorlow-0001",
        ]
        errors = MODULE.validate_manifest(changed)
        self.assertIn(
            "trial-subtle-0001: exactly one hidden reference is required", errors
        )

    def test_mushra_requires_both_anchors_and_eight_active_seconds(self) -> None:
        changed = copy.deepcopy(manifest())
        changed["stimuli"][3]["active_seconds"] = 7
        changed["trials"][1]["candidate_ids"].remove("anchormid-0001")
        errors = MODULE.validate_manifest(changed)
        self.assertIn(
            "trial-mushra-0001: MUSHRA requires low and mid anchors", errors
        )
        self.assertIn(
            "trial-mushra-0001: MUSHRA active duration is below 8 seconds", errors
        )

    def test_codec_class_requires_controlled_intervention(self) -> None:
        changed = copy.deepcopy(manifest())
        changed["stimuli"][2]["condition_class"] = "transparent_codec"
        errors = MODULE.validate_manifest(changed)
        self.assertIn(
            "condition-0001: codec class requires controlled intervention", errors
        )


if __name__ == "__main__":
    unittest.main()
