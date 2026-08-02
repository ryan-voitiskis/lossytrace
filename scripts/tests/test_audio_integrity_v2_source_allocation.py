from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "freeze-audio-integrity-v2-sources.py"
)
SPEC = importlib.util.spec_from_file_location("source_allocation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
source_allocation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source_allocation)


def fixture_rules() -> dict:
    return {
        "schema_version": 1,
        "rules_id": "fixture-source-allocation",
        "state": "source_allocation_rules_frozen_before_execution",
        "source_identity_checkpoint_commit": "a" * 40,
        "audio_generated": False,
        "scores_opened": False,
        "existing_v1_holdouts_included": False,
        "selection_uses_waveform_content": False,
        "selection_uses_duration": False,
        "selection_uses_measurements_or_labels": False,
        "identifier_derivation": {
            "group_id_prefix": "fixture-group\0",
        },
        "member_selection": {
            "ranking_prefix": "fixture-member\0",
            "selection_count_per_retained_group": 1,
        },
        "source_rules": [
            {
                "source_id": "vctk_clean_56spk_2017",
                "expected_retained_group_count": 4,
                "group_cap": {
                    "ranking_prefix": "fixture-vctk-cap\0",
                    "selected_per_gender": 2,
                },
            },
            {
                "source_id": "rwc_music_v2_2026",
                "expected_retained_group_count": 3,
                "work_title_constraint": {
                    "family_order_prefix": "fixture-rwc-family\0",
                },
            },
        ],
        "privacy": {
            "public_aggregate_forbidden_keys": ["case_id", "member_id"]
        },
    }


def fixture_candidate(
    source_id: str,
    group_id: str,
    member_id: str,
    *,
    title: str | None = None,
    gender: str | None = None,
    speaker: str | None = None,
) -> dict:
    factors = {}
    if title is not None:
        factors["normalized_work_title"] = title
    if gender is not None:
        factors["gender"] = gender
    if speaker is not None:
        factors["speaker_id"] = speaker
    return {
        "source_id": source_id,
        "group_id": group_id,
        "member_id": member_id,
        "factors": factors,
    }


class SourceAllocationTests(unittest.TestCase):
    def test_canonical_json_is_byte_stable(self) -> None:
        left = source_allocation.canonical_json_bytes({"b": 2, "a": 1})
        right = source_allocation.canonical_json_bytes({"a": 1, "b": 2})
        self.assertEqual(left, right)
        self.assertTrue(left.endswith(b"\n"))

    def test_group_ids_are_domain_separated(self) -> None:
        rules = fixture_rules()
        first = source_allocation.opaque_group_id(rules, "source-a", "same")
        replay = source_allocation.opaque_group_id(rules, "source-a", "same")
        other = source_allocation.opaque_group_id(rules, "source-b", "same")
        self.assertEqual(first, replay)
        self.assertNotEqual(first, other)
        self.assertRaises(
            ValueError,
            source_allocation.opaque_group_id,
            rules,
            "source-a",
            "bad\0group",
        )

    def test_vctk_cap_is_balanced_and_content_independent(self) -> None:
        rules = fixture_rules()
        candidates = []
        for gender in ("F", "M"):
            for index in range(3):
                group = f"{gender}-{index}"
                for utterance in range(2):
                    candidates.append(
                        fixture_candidate(
                            "vctk_clean_56spk_2017",
                            group,
                            f"{group}-{utterance}.wav",
                            gender=gender,
                            speaker=f"p{gender}{index}",
                        )
                    )
        selected, counts = source_allocation.apply_vctk_cap(rules, candidates)
        self.assertEqual(counts, {"F": 2, "M": 2})
        self.assertEqual(len({row["group_id"] for row in selected}), 4)
        replay, replay_counts = source_allocation.apply_vctk_cap(
            rules, list(reversed(candidates))
        )
        self.assertEqual(
            {row["group_id"] for row in selected},
            {row["group_id"] for row in replay},
        )
        self.assertEqual(counts, replay_counts)

    def test_rwc_matching_finds_complete_unique_title_assignment(self) -> None:
        rules = fixture_rules()
        candidates = [
            fixture_candidate("rwc_music_v2_2026", "family-a", "a-shared", title="shared"),
            fixture_candidate("rwc_music_v2_2026", "family-a", "a-only", title="a-only"),
            fixture_candidate("rwc_music_v2_2026", "family-b", "b-shared", title="shared"),
            fixture_candidate("rwc_music_v2_2026", "family-c", "c-only", title="c-only"),
        ]
        selected = source_allocation.select_rwc(rules, candidates)
        self.assertEqual(len(selected), 3)
        self.assertEqual(len({row["group_id"] for row in selected}), 3)
        self.assertEqual(
            len({row["factors"]["normalized_work_title"] for row in selected}),
            3,
        )
        replay = source_allocation.select_rwc(rules, list(reversed(candidates)))
        self.assertEqual(
            sorted(row["member_id"] for row in selected),
            sorted(row["member_id"] for row in replay),
        )

    def test_rwc_matching_stops_when_complete_assignment_is_impossible(self) -> None:
        rules = fixture_rules()
        candidates = [
            fixture_candidate("rwc_music_v2_2026", "family-a", "a", title="shared"),
            fixture_candidate("rwc_music_v2_2026", "family-b", "b", title="shared"),
            fixture_candidate("rwc_music_v2_2026", "family-c", "c", title="other"),
        ]
        with self.assertRaisesRegex(ValueError, "complete unique-title"):
            source_allocation.select_rwc(rules, candidates)

    def test_public_privacy_checks_reject_identifiers_and_paths(self) -> None:
        forbidden = {"case_id", "member_id"}
        with self.assertRaisesRegex(ValueError, "forbidden keys"):
            source_allocation.recursively_reject_keys(
                {"nested": [{"member_id": "private"}]}, forbidden, "fixture"
            )
        with self.assertRaisesRegex(ValueError, "absolute path"):
            source_allocation.recursively_reject_absolute_paths(
                {"nested": "/private/path"}, "fixture"
            )

    def test_atomic_json_writer_uses_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            value = {"z": [2, 1], "a": False}
            source_allocation.write_json_atomic(path, value)
            self.assertEqual(path.read_bytes(), source_allocation.canonical_json_bytes(value))
            self.assertEqual(json.loads(path.read_text()), value)


if __name__ == "__main__":
    unittest.main()
