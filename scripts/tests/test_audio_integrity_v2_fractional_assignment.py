from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "freeze-audio-integrity-v2-fractional-assignment.py"
SPEC = importlib.util.spec_from_file_location("v2_fractional_assignment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RULES = MODULE.load_object(
    ROOT / "benchmarks/audio-integrity-v2/fractional-assignment-rules.json"
)


def source(group_id: str, domain: str) -> dict[str, str]:
    return {
        "group_id": group_id,
        "evidence_partition": "mechanism_development",
        "source_collection_id": "collection",
        "source_domain": domain,
        "provenance_tier": "tier_a_confirmed_pcm",
    }


class FractionalAssignmentTest(unittest.TestCase):
    def test_hash_text_matches_frozen_serialization(self) -> None:
        payload = (
            MODULE.RANKING_PREFIX
            + "purpose\0mechanism_development\0music\0group"
        ).encode()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            MODULE.hash_text(
                "purpose", "mechanism_development", "music", "group"
            ),
        )

    def test_rules_are_preassignment_and_verdict_free(self) -> None:
        self.assertEqual(
            "lossytrace-v2-fractional-assignment-20260802-004",
            RULES["assignment_rules_id"],
        )
        self.assertEqual(
            "fractional_assignment_rules_frozen_before_private_assignment",
            RULES["state"],
        )
        self.assertFalse(RULES["audio_generated"])
        self.assertFalse(RULES["waveform_content_inspected"])
        self.assertFalse(RULES["signal_statistics_used"])
        self.assertFalse(RULES["scores_opened"])
        self.assertFalse(RULES["selection_authorized"])
        self.assertFalse(RULES["public_state"]["public_verdict_enabled"])

    def test_domain_balanced_selection_uses_every_available_domain_first(self) -> None:
        rows = [
            source("a1", "a"),
            source("a2", "a"),
            source("a3", "a"),
            source("b1", "b"),
            source("b2", "b"),
            source("c1", "c"),
        ]
        selected = MODULE.domain_balanced_select(rows, 5, "fixture")
        counts = {}
        for row in selected:
            counts[row["source_domain"]] = counts.get(row["source_domain"], 0) + 1
        self.assertEqual({"a", "b", "c"}, set(counts))
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        self.assertEqual(selected, MODULE.domain_balanced_select(rows, 5, "fixture"))

    def test_categorical_cycle_is_exactly_balanced(self) -> None:
        observed = MODULE.cycle_levels(["mono", "stereo"], "fixture", 120)
        self.assertEqual(60, observed.count("mono"))
        self.assertEqual(60, observed.count("stereo"))

    def test_transform_minimum_is_only_an_eligibility_predicate(self) -> None:
        transform = {
            "transform_id": "trim-head-250ms",
            "parameters": {"minimum_input_milliseconds": 500},
        }
        self.assertFalse(
            MODULE.transform_supported_by_header(transform, 3999, 8000)
        )
        self.assertTrue(
            MODULE.transform_supported_by_header(transform, 4000, 8000)
        )

    def test_filter_preserves_frozen_ranking_within_eligible_groups(self) -> None:
        rows = [source("a", "one"), source("b", "one"), source("c", "two")]
        unsupported = {
            "a": frozenset(),
            "b": frozenset({"duration-prefix-3s"}),
            "c": frozenset(),
        }
        eligible = MODULE.eligible_transform_groups(
            rows, "duration-prefix-3s", unsupported
        )
        self.assertEqual({"a", "c"}, {row["group_id"] for row in eligible})
        self.assertEqual(
            MODULE.domain_balanced_select(eligible, 2, "frozen-purpose"),
            MODULE.domain_balanced_select(eligible, 2, "frozen-purpose"),
        )

    def test_positive_cell_has_exact_matched_reference(self) -> None:
        row = source("group", "domain")
        builder = MODULE.CellBuilder({"group": row})
        setting = {
            "codec_family": "mp3",
            "expanded_setting_id": "setting--mono",
            "encoder_id": "encoder",
            "lineage_id": "lineage",
            "channel_treatment_id": "mono",
            "expected_sample_rate_hz": 44100,
        }
        builder.add_positive(
            row,
            setting,
            "decoder",
            "gain-minus6db-q31",
            "flac16",
            "transform_positive",
        )
        cells = builder.finish()
        positive = next(cell for cell in cells if cell["expectation"] == "controlled_positive")
        reference = next(
            cell for cell in cells if cell["assignment_id"] == positive["matched_reference_assignment_id"]
        )
        source_reference = next(
            cell
            for cell in cells
            if cell["assignment_id"] == positive["source_reference_assignment_id"]
        )
        self.assertEqual("identity", source_reference["transform_id"])
        self.assertEqual(
            source_reference["assignment_id"],
            reference["source_reference_assignment_id"],
        )
        for field in (
            "group_id",
            "channel_treatment_id",
            "target_sample_rate_hz",
            "transform_id",
            "wrapper_id",
        ):
            self.assertEqual(positive[field], reference[field])

    def test_public_rules_do_not_contain_private_paths_or_scores(self) -> None:
        serialized = json.dumps(RULES, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("Library/Application Support", serialized)
        self.assertNotIn("audio_sha256", serialized)

    def test_rules_bind_exact_generator_bytes(self) -> None:
        self.assertEqual(
            MODULE.sha256_file(SCRIPT), RULES["generator_binding"]["sha256"]
        )


if __name__ == "__main__":
    unittest.main()
